import re

from fastapi.testclient import TestClient

from ricerca import history, lavori, revisioni, wiki
from ricerca.app import app
from ricerca.llm import _parse_wiki_graph
from ricerca.models import Block, SourceResult, Strategy, Work


client = TestClient(app)


def progetto_con_corpus() -> tuple[str, list[dict]]:
    record = [
        Work(
            title="AI literacy in teacher education",
            authors=["Ada Rossi"], year=2024, venue="Education Review", doi="10.1/a",
            abstract="Teachers develop artificial intelligence literacy through reflective practice.",
        ),
        Work(
            title="Responsible AI competence",
            authors=["Luca Bianchi"], year=2023, venue="Education Review", doi="10.1/b",
            abstract="Responsible AI competence is associated with critical reflection.",
        ),
    ]
    id_ricerca = history.salva(
        "AI literacy",
        Strategy([Block("Concept", ["AI literacy"])]),
        [SourceResult("openalex", "OpenAlex", "AI literacy", works=record)],
        record,
    )
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    return id_progetto, revisioni.progetto(id_progetto)["record"]


def test_la_wiki_di_base_collega_fonti_autori_e_sedi():
    id_progetto, _ = progetto_con_corpus()
    artefatto = wiki.crea_base(revisioni.progetto(id_progetto))

    tipi = [nodo["tipo"] for nodo in artefatto["nodi"]]
    assert tipi.count("fonte") == 2
    assert tipi.count("autore") == 2
    assert tipi.count("sede") == 1
    assert {arco["tipo"] for arco in artefatto["archi"]} == {"scritto_da", "pubblicato_in"}
    assert len(artefatto["pagine"]) == 2


def test_l_analisi_semantica_preferisce_gli_studi_inclusi():
    id_progetto, record = progetto_con_corpus()
    revisioni.decidi(id_progetto, record[0]["id"], "abstract", "Ada", "incluso")
    revisioni.decidi(id_progetto, record[1]["id"], "abstract", "Ada", "escluso")

    documenti, ambito = wiki.documenti_semantici(revisioni.progetto(id_progetto))
    assert ambito == "abstract_inclusi"
    assert [voce["id"] for voce in documenti] == [record[0]["id"]]


def test_l_arricchimento_llm_accetta_solo_fonti_e_citazioni_del_corpus():
    id_progetto, record = progetto_con_corpus()
    progetto = revisioni.progetto(id_progetto)
    base = wiki.crea_base(progetto)
    documenti = wiki.documenti_per_llm(progetto)
    primo, secondo = record[0]["id"], record[1]["id"]
    risultato = {
        "concetti": [
            {"id": "c1", "etichetta": "AI literacy", "riassunto": "Competenza sull'AI.", "fonti": [primo], "evidenza": "artificial intelligence literacy"},
            {"id": "c2", "etichetta": "Critical reflection", "riassunto": "Pratica riflessiva.", "fonti": [secondo], "evidenza": "testo inventato"},
            {"id": "c3", "etichetta": "Fuori corpus", "fonti": ["inesistente"]},
        ],
        "relazioni": [
            {"origine": "c1", "destinazione": "c2", "tipo": "associato_a", "fonti": [primo, secondo]},
        ],
    }

    arricchita = wiki.arricchisci(base, [risultato], documenti, "modello-test")
    concetti = [pagina for pagina in arricchita["pagine"] if pagina["tipo"] == "concetto"]
    assert {pagina["titolo"] for pagina in concetti} == {"AI literacy", "Critical reflection"}
    assert next(p for p in concetti if p["titolo"] == "AI literacy")["evidenze"]
    assert not next(p for p in concetti if p["titolo"] == "Critical reflection")["evidenze"]
    assert any(arco["tipo"] == "associato_a" for arco in arricchita["archi"])


def test_il_parser_del_grafo_tollera_il_blocco_markdown():
    risultato = _parse_wiki_graph(
        '```json\n{"concetti":[{"id":"c1"}],"relazioni":[]}\n```'
    )
    assert risultato == {"concetti": [{"id": "c1"}], "relazioni": []}


def test_la_generazione_senza_llm_resta_utilizzabile_dalla_pagina():
    id_progetto, _ = progetto_con_corpus()
    avvio = client.post(f"/revisioni/{id_progetto}/wiki/genera")
    id_lavoro = re.search(r"/revisioni-wiki-lavoro/([A-Za-z0-9_-]+)", avvio.text).group(1)
    lavoro = lavori.attendi(id_lavoro)

    assert lavoro.stato == "finito"
    pagina = client.get(f"/revisioni/{id_progetto}/wiki")
    assert pagina.status_code == 200
    assert "Literature graph" in pagina.text
    assert "AI literacy in teacher education" in pagina.text
    assert revisioni.progetto(id_progetto)["wiki"]["llm_usato"] is False
