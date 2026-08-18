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
    assert history.record(id_ricerca)[0].motivo == "utile"


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
