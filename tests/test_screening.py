from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient

from ricerca import history
from ricerca.app import app
from ricerca.export import protocollo
from ricerca.models import Block, SourceResult, Strategy, Work

client = TestClient(app)


def ricerca_con_tre_record():
    works = [Work(title=f"Studio {n}", year=2024, doi=f"10.1/{n}", sources=["openalex"]) for n in range(3)]
    results = [SourceResult("openalex", "OpenAlex", "query", works=works)]
    return history.salva("AI literacy", Strategy([Block("C", ["ai"])]), results, works)


def test_le_decisioni_si_registrano_e_si_annullano():
    id_ricerca = ricerca_con_tre_record()
    history.decide(id_ricerca, 0, "incluso", "pertinente")
    history.decide(id_ricerca, 1, "escluso", "fuori tema")

    assert history.record(id_ricerca)[0].decisione == "incluso"
    assert history.record(id_ricerca)[0].motivo == "pertinente"
    assert history.record(id_ricerca)[1].decisione == "escluso"

    history.decide(id_ricerca, 0, "incluso")  # stessa scelta: annulla
    assert history.record(id_ricerca)[0].decisione == ""


def test_uno_stato_inventato_non_viene_registrato():
    id_ricerca = ricerca_con_tre_record()
    history.decide(id_ricerca, 0, "boh")
    assert history.record(id_ricerca)[0].decisione == ""


def test_i_conteggi_seguono_il_diagramma_prisma():
    id_ricerca = ricerca_con_tre_record()
    history.decide(id_ricerca, 0, "incluso")
    history.decide(id_ricerca, 1, "escluso")
    conta = history.conteggi(id_ricerca)
    assert conta["grezzi"] == 3
    assert conta["dopo_deduplica"] == 3
    assert conta["incluso"] == 1 and conta["escluso"] == 1
    assert conta["da_valutare"] == 1


def test_la_rotta_di_screening_aggiorna_cella_e_conteggi():
    id_ricerca = ricerca_con_tre_record()
    pagina = client.post(f"/screening/{id_ricerca}/0", data={"stato": "incluso", "motivo": "utile"})
    assert "scelto" in pagina.text
    assert 'id="conteggi"' in pagina.text
    assert f'id="prisma-{id_ricerca}"' in pagina.text
    assert history.record(id_ricerca)[0].motivo == "utile"


def test_le_motivazioni_sono_aree_di_testo_ridimensionabili():
    id_ricerca = ricerca_con_tre_record()
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text
    assert '<textarea id="motivo-0"' in pagina and 'rows="2"' in pagina
    assert 'class="motivo"' in pagina

    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / "ricerca/static/style.css").read_text()
    regola = css.split(".motivo {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in regola
    assert "resize: vertical" in regola


def test_le_decisioni_finiscono_nel_csv():
    id_ricerca = ricerca_con_tre_record()
    history.decide(id_ricerca, 0, "incluso", "pertinente")
    csv = client.get(f"/export/{id_ricerca}.csv?campi=titolo,decisione,motivo")
    righe = csv.text.splitlines()
    assert righe[0] == "titolo,decisione,motivo"
    assert "incluso,pertinente" in righe[1]


def test_il_protocollo_riporta_stringhe_e_numeri():
    id_ricerca = ricerca_con_tre_record()
    history.decide(id_ricerca, 0, "incluso")
    testo = client.get(f"/export/{id_ricerca}.protocollo.md").text
    assert "# Protocollo di ricerca — AI literacy" in testo
    assert "| OpenAlex | `query` | 3 |" in testo
    assert "- inclusi: 1" in testo
    assert "- non ancora valutati: 2" in testo


def test_il_protocollo_di_una_ricerca_inesistente_non_esplode():
    assert "Protocollo" in protocollo({}, {})


def test_l_affinamento_propone_termini_nuovi():
    works = [
        Work(title="AI literacy and teacher professional development", year=2024, doi="10.1/a"),
        Work(title="Teacher professional development for AI", year=2023, doi="10.1/b"),
        Work(title="Professional development in AI literacy", year=2022, doi="10.1/c"),
    ]
    id_ricerca = history.salva(
        "AI literacy", Strategy([Block("C", ["AI literacy"])]),
        [SourceResult("openalex", "OpenAlex", "q", works=works)], works,
    )
    pagina = client.post(f"/affina/{id_ricerca}")
    assert "professional development" in pagina.text


def test_l_affinamento_dice_quando_non_c_e_nulla_di_nuovo():
    works = [Work(title="AI literacy", year=2024, doi="10.1/a")]
    id_ricerca = history.salva(
        "AI literacy", Strategy([Block("C", ["AI literacy"])]),
        [SourceResult("openalex", "OpenAlex", "q", works=works)], works,
    )
    assert "no terms" in client.post(f"/affina/{id_ricerca}").text


def test_una_decisione_scambia_la_sola_cella():
    """Ridisegnare l'elenco intero spegne il fuoco e le scorciatoie."""

    id_ricerca = ricerca_con_tre_record()
    risposta = client.post(
        f"/screening/{id_ricerca}/0",
        data={"stato": "incluso", "motivo": "", "aggiorna_elenco": "1", "campo": ["titolo"]},
    )

    assert "HX-Retarget" not in risposta.headers
    assert 'id="screening-0"' in risposta.text
    assert f'id="blocco-{id_ricerca}"' not in risposta.text
    assert f'id="prisma-{id_ricerca}"' in risposta.text          # i conteggi seguono lo stesso


def test_con_un_filtro_di_stato_l_elenco_si_ridisegna():
    """Il record deciso deve uscire dall'elenco: la cella non basta."""

    id_ricerca = ricerca_con_tre_record()
    risposta = client.post(
        f"/screening/{id_ricerca}/0",
        data={
            "stato": "incluso", "motivo": "", "aggiorna_elenco": "1",
            "campo": ["titolo"], "filtro_stato": "da_valutare",
        },
    )

    assert risposta.headers["HX-Retarget"] == f"#blocco-{id_ricerca}"
    assert risposta.headers["HX-Reswap"] == "outerHTML"
    assert f'id="blocco-{id_ricerca}"' in risposta.text


def test_le_colonne_decisione_e_motivo_obbligano_a_ridisegnare():
    id_ricerca = ricerca_con_tre_record()
    risposta = client.post(
        f"/screening/{id_ricerca}/0",
        data={
            "stato": "incluso", "motivo": "utile", "aggiorna_elenco": "1",
            "campo": ["titolo", "decisione"],
        },
    )

    assert risposta.headers["HX-Retarget"] == f"#blocco-{id_ricerca}"


def test_il_motivo_resta_chiuso_finche_non_c_e_una_decisione():
    id_ricerca = ricerca_con_tre_record()
    history.decide(id_ricerca, 1, "escluso", "fuori tema")
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text

    aperto = pagina.split('id="screening-1"', 1)[1].split("</span>", 1)[0]
    chiuso = pagina.split('id="screening-0"', 1)[1].split("</span>", 1)[0]
    assert '<details class="motivo-avvolto" open>' in aperto
    assert '<details class="motivo-avvolto" >' in chiuso


def test_la_riga_ha_un_ancoraggio_per_il_fuoco():
    id_ricerca = ricerca_con_tre_record()
    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text

    assert 'data-riga="0" id="riga-0"' in pagina
    base = (Path(__file__).resolve().parent.parent / "ricerca/templates/base.html").read_text()
    assert "rigaDelFuoco" in base
