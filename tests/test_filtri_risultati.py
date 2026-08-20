from fastapi.testclient import TestClient

from ricerca import config as config_module
from ricerca import history
from ricerca.app import PER_PAGINA, app
from ricerca.config import Config
from ricerca.models import Block, SourceResult, Strategy, Work


client = TestClient(app)


def salva(works: list[Work]) -> str:
    fonti = sorted({fonte for work in works for fonte in work.sources})
    risultati = [SourceResult(fonte, fonte.title(), "q", works=[]) for fonte in fonti]
    return history.salva("filtri", Strategy([Block("C", ["x"])]), risultati, works)


def test_il_testo_cerca_in_tutti_i_record_e_conserva_l_indice_assoluto():
    works = [
        Work(title=f"Studio {indice}", authors=["Mario Rossi"], year=2024,
             doi=f"10.1/{indice}", venue="Rivista", sources=["openalex"])
        for indice in range(PER_PAGINA + 20)
    ]
    works[62] = Work(
        title="Didattica clinica avanzata",
        authors=["Lucía García"],
        year=2021,
        doi="10.5555/bersaglio",
        venue="Educación Médica",
        sources=["pubmed"],
    )
    id_ricerca = salva(works)

    pagina = client.post(
        f"/risultati/{id_ricerca}",
        data={"vista": "tabella", "filtro_testo": "lucia garcia"},
    ).text

    assert "Didattica clinica avanzata" in pagina
    assert "Studio 0" not in pagina
    assert 'data-riga="62"' in pagina
    assert "1 of 70 records" in pagina


def test_anno_fonte_e_screening_si_possono_combinare():
    works = [
        Work(title="Da includere", year=2022, sources=["openalex", "crossref"]),
        Work(title="Anno errato", year=2018, sources=["openalex"]),
        Work(title="Fonte errata", year=2022, sources=["pubmed"]),
        Work(title="Stato errato", year=2022, sources=["openalex"]),
    ]
    id_ricerca = salva(works)
    history.decide(id_ricerca, 0, "incluso", "")
    history.decide(id_ricerca, 3, "escluso", "")

    pagina = client.post(
        f"/risultati/{id_ricerca}",
        data={
            "vista": "tabella",
            "filtro_anno_da": "2020",
            "filtro_anno_a": "2023",
            "filtro_fonte": "openalex",
            "filtro_stato": "incluso",
        },
    ).text

    assert "Da includere" in pagina
    assert "Anno errato" not in pagina
    assert "Fonte errata" not in pagina
    assert "Stato errato" not in pagina
    assert 'option value="openalex" selected' in pagina
    assert 'option value="incluso" selected' in pagina


def test_la_paginazione_mantiene_i_filtri():
    works = []
    for indice in range(PER_PAGINA + 12):
        works.append(Work(
            title=f"Tema comune {indice}", year=2020 + indice % 3,
            sources=["openalex"] if indice % 2 == 0 else ["pubmed"],
        ))
    id_ricerca = salva(works)

    prima = client.post(
        f"/risultati/{id_ricerca}",
        data={"vista": "tabella", "filtro_testo": "tema comune"},
    ).text
    seconda = client.post(
        f"/risultati/{id_ricerca}",
        data={"vista": "tabella", "pagina": "2", "filtro_testo": "tema comune"},
    ).text

    assert 'hx-include="#campi-' in prima
    assert f'#filtri-{id_ricerca}"' in prima
    assert 'value="tema comune"' in seconda
    assert 'data-riga="50"' in seconda
    assert seconda.count('tabindex="0" data-riga=') == 12


def test_un_filtro_senza_corrispondenze_non_sembra_una_ricerca_vuota():
    id_ricerca = salva([Work(title="Studio presente", year=2024, sources=["openalex"])])

    pagina = client.post(
        f"/risultati/{id_ricerca}",
        data={"vista": "tabella", "filtro_testo": "inesistente"},
    ).text

    assert "No records match these filters" in pagina
    assert 'value="inesistente"' in pagina
    assert "Widen the blocks" not in pagina


def test_lo_screening_di_un_risultato_filtrato_usa_l_indice_originale():
    works = [Work(title=f"Studio {indice}", year=2024, sources=["openalex"])
             for indice in range(PER_PAGINA + 15)]
    works[61].title = "Bersaglio unico"
    id_ricerca = salva(works)

    risposta = client.post(
        f"/screening-massa/{id_ricerca}",
        data={
            "stato": "incluso",
            "selezione": "61",
            "vista": "tabella",
            "filtro_testo": "bersaglio unico",
        },
    ).text

    record = history.record(id_ricerca)
    assert record[61].decisione == "incluso"
    assert record[11].decisione == ""
    assert 'data-riga="61"' in risposta
    assert 'value="bersaglio unico"' in risposta


def test_cambiare_stato_aggiorna_anche_un_elenco_filtrato_per_stato():
    id_ricerca = salva([Work(title="Da decidere", year=2024, sources=["openalex"])])

    risposta = client.post(
        f"/screening/{id_ricerca}/0",
        data={
            "stato": "incluso",
            "aggiorna_elenco": "1",
            "vista": "tabella",
            "filtro_stato": "da_valutare",
        },
    ).text

    assert "No records match these filters" in risposta
    assert "Da decidere" not in risposta


def test_la_barra_dei_filtri_e_disponibile_in_italiano():
    config_module.save(Config(configurato="1", lang="it"))
    id_ricerca = salva([Work(title="Studio", year=2024, sources=["openalex"])])

    pagina = client.post(f"/risultati/{id_ricerca}", data={"vista": "tabella"}).text

    assert "Filtra i risultati" in pagina
    assert "Titolo, autore, sede o DOI" in pagina
    assert "Tutte le fonti" in pagina
    assert "Da valutare" in pagina
