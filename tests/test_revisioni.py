from fastapi.testclient import TestClient

from ricerca import history, pdf, revisioni
from ricerca.app import app
from ricerca.models import Block, SourceResult, Strategy, Work


client = TestClient(app)


def ricerca_finta(topic="AI literacy"):
    lavori = [
        Work(
            title="AI literacy in teacher education",
            authors=["Ada Rossi"],
            year=2024,
            doi="10.1/a",
            abstract="Teachers develop artificial intelligence literacy.",
            sources=["openalex"],
        ),
        Work(
            title="Responsible AI competence",
            authors=["Luca Bianchi"],
            year=2023,
            doi="10.1/b",
            abstract="A study of responsible AI competence in schools.",
            sources=["openalex"],
        ),
    ]
    return history.salva(
        topic,
        Strategy([Block("Concetto", ["AI literacy"])]),
        [SourceResult("openalex", "OpenAlex", "AI literacy", works=lavori)],
        lavori,
    )


def test_un_progetto_unisce_ricerche_e_deduplica_il_corpus():
    primo = ricerca_finta()
    secondo = history.salva(
        "seconda",
        Strategy([Block("Concetto", ["competence"])]),
        [SourceResult("crossref", "Crossref", "competence")],
        [
            Work(title="Stesso record", doi="10.1/a", sources=["crossref"]),
            Work(title="Nuovo record", doi="10.1/c", sources=["crossref"]),
        ],
    )
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada", "Luca"])

    assert revisioni.collega_ricerca(id_progetto, primo) == 2
    assert revisioni.collega_ricerca(id_progetto, secondo) == 1
    progetto = revisioni.progetto(id_progetto)
    assert len(progetto["ricerche"]) == 2
    assert len(progetto["record"]) == 3
    assert len(progetto["record"][0]["provenienze"]) == 2


def test_scollegare_una_ricerca_conserva_corpus_provenienze_e_decisioni():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    item = revisioni.progetto(id_progetto)["record"][0]["id"]
    revisioni.decidi(id_progetto, item, "abstract", "Ada", "incluso", "pertinente")

    assert revisioni.scollega_ricerca(id_progetto, id_ricerca) is True

    progetto = revisioni.progetto(id_progetto)
    assert progetto["ricerche"] == []
    assert len(progetto["record"]) == 2
    assert progetto["record"][0]["provenienze"][0]["ricerca"] == id_ricerca
    assert progetto["decisioni"][item]["abstract"]["Ada"]["stato"] == "incluso"
    assert progetto["registro"][-1]["azione"] == "ricerca scollegata"


def test_protocollo_versiona_gli_emendamenti_e_controlla_i_campi():
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.salva_protocollo(id_progetto, {
        "domanda": "Quali competenze servono?",
        "framework": "PICO",
        "popolazione": "docenti",
        "concetto": "AI literacy",
        "criteri_inclusione": "studi empirici",
        "criteri_esclusione": "editoriali",
        "piano_sintesi": "sintesi narrativa",
        "frequenza_aggiornamento": "mensile",
    })
    revisioni.salva_protocollo(
        id_progetto,
        {**revisioni.progetto(id_progetto)["protocollo"], "popolazione": "docenti universitari"},
        motivo="Ambito reso più preciso",
    )

    progetto = revisioni.progetto(id_progetto)
    assert progetto["protocollo"]["popolazione"] == "docenti universitari"
    assert progetto["emendamenti"][-1]["motivo"] == "Ambito reso più preciso"
    assert "domanda" not in revisioni.campi_protocollo_mancanti(progetto)


def test_gli_articoli_sentinella_controllano_titolo_e_doi():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    revisioni.salva_protocollo(id_progetto, {
        "articoli_sentinella": "10.1/a\nUn titolo assente",
        "peer_review_strategia": "Verificata con PRESS da Luca",
    })

    esiti = revisioni.controlla_sentinelle(revisioni.progetto(id_progetto))
    assert [e["trovata"] for e in esiti] == [True, False]
    checklist = revisioni.checklist_prisma_s(revisioni.progetto(id_progetto))
    assert next(e for e in checklist if "Peer review" in e["etichetta"])["completo"] is True


def test_doppio_screening_mostra_conflitto_e_consenso():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada", "Luca"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    item = revisioni.progetto(id_progetto)["record"][0]["id"]

    revisioni.decidi(id_progetto, item, "abstract", "Ada", "incluso", "pertinente")
    revisioni.decidi(id_progetto, item, "abstract", "Luca", "escluso", "popolazione")
    assert revisioni.conflitti(id_progetto, "abstract") == [item]

    revisioni.risolvi(id_progetto, item, "abstract", "incluso", "criterio chiarito")
    assert revisioni.conflitti(id_progetto, "abstract") == []
    assert revisioni.stato_finale(revisioni.progetto(id_progetto), item, "abstract") == "incluso"


def test_estrazione_bias_grade_e_gruppo_studio_restano_nel_progetto():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    items = revisioni.progetto(id_progetto)["record"]
    primo, secondo = items[0]["id"], items[1]["id"]

    revisioni.collega_report(id_progetto, secondo, primo)
    revisioni.salva_estrazione(id_progetto, primo, "Ada", {
        "disegno": "studio qualitativo", "popolazione": "docenti",
        "intervento": "corso AI", "outcome": "competenza", "risultati": "miglioramento",
        "nota": "Tabella 2", "pagina": "7",
    })
    revisioni.salva_bias(id_progetto, primo, {
        "strumento": "personalizzato", "giudizio": "alcune criticità",
        "domini": "campionamento", "motivazione": "campione piccolo",
        "evidenza": "n=12", "pagina": "4",
    })
    revisioni.salva_evidenza(id_progetto, {
        "outcome": "competenza AI", "studi": "1", "partecipanti": "12",
        "effetto": "aumento", "certezza": "bassa", "motivazione": "imprecisione",
    })

    progetto = revisioni.progetto(id_progetto)
    assert progetto["gruppi_studio"][secondo] == primo
    assert progetto["estrazioni"][primo]["Ada"]["pagina"] == "7"
    assert progetto["bias"][primo]["giudizio"] == "alcune criticità"
    assert progetto["evidenze"][0]["certezza"] == "bassa"


def test_estrazioni_indipendenti_generano_un_conflitto_risolvibile():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada", "Luca"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    item = revisioni.progetto(id_progetto)["record"][0]["id"]
    revisioni.salva_estrazione(id_progetto, item, "Ada", {"outcome": "competenza"})
    revisioni.salva_estrazione(id_progetto, item, "Luca", {"outcome": "autoefficacia"})
    assert revisioni.conflitto_estrazione(revisioni.progetto(id_progetto), item) is True

    revisioni.salva_consenso_estrazione(id_progetto, item, {"outcome": "competenza"})
    assert revisioni.conflitto_estrazione(revisioni.progetto(id_progetto), item) is False


def test_disponibilita_del_testo_completo_resta_tracciata():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    item = revisioni.progetto(id_progetto)["record"][0]["id"]
    revisioni.salva_testo_completo(id_progetto, item, "richiesto", "email all'autrice")
    assert revisioni.progetto(id_progetto)["testi_completi"][item]["stato"] == "richiesto"


def test_priorita_assistita_spiega_perche_un_record_sale():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    items = revisioni.progetto(id_progetto)["record"]
    revisioni.decidi(id_progetto, items[0]["id"], "abstract", "Ada", "incluso", "")

    ordinati = revisioni.priorita_assistita(revisioni.progetto(id_progetto), "abstract")
    assert ordinati[0]["id"] == items[1]["id"]
    assert "termini" in ordinati[0]
    assert isinstance(ordinati[0]["punteggio"], float)


def test_un_aggiornamento_aggiunge_nuovi_record_e_versiona_quelli_cambiati():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)

    esito = revisioni.integra_aggiornamento(id_progetto, "run-2", [
        Work(title="AI literacy in teacher education", doi="10.1/a", citazioni=9, ritirato=True),
        Work(title="Un lavoro appena pubblicato", doi="10.1/new", year=2026),
    ])

    progetto = revisioni.progetto(id_progetto)
    assert esito == {"nuovi": 1, "modificati": 1, "ritirati": 1}
    assert len(progetto["record"]) == 3
    assert progetto["versioni_record"]
    assert progetto["aggiornamenti"][-1]["nuovi"] == 1


def test_le_pagine_del_workspace_coprono_tutte_le_fasi():
    pagina = client.post(
        "/revisioni",
        data={"titolo": "Review AI", "tipo": "sistematica", "revisori": "Ada, Luca"},
        follow_redirects=True,
    )
    assert pagina.status_code == 200
    for testo in ("Protocol", "Searches", "Abstract screening", "Full text", "Extraction", "Quality", "Synthesis", "Updates"):
        assert testo in pagina.text


def test_il_protocollo_offre_guide_contestuali_accessibili():
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])

    pagina = client.get(f"/revisioni/{id_progetto}")

    assert 'aria-label="Help for Review question"' in pagina.text
    assert "State population, concept or intervention, and expected outcome" in pagina.text


def test_una_ricerca_si_scollega_dalla_rotta_e_torna_disponibile():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)

    pagina = client.post(
        f"/revisioni/{id_progetto}/ricerche/{id_ricerca}/rimuovi",
        follow_redirects=True,
    )

    assert pagina.status_code == 200
    assert revisioni.progetto(id_progetto)["ricerche"] == []
    assert f'<option value="{id_ricerca}">' in pagina.text


def test_lo_screening_apre_pagina_e_pdf_senza_perdere_il_record():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    item = revisioni.progetto(id_progetto)["record"][0]
    work = revisioni.lavori(revisioni.progetto(id_progetto))[0]["work"]
    percorso = pdf.cartella() / pdf.nome_file(work)
    percorso.write_bytes(b"%PDF-1.4\n%%EOF")

    pagina = client.get(f"/revisioni/{id_progetto}")

    assert 'href="https://doi.org/10.1/a"' in pagina.text
    assert f'data-pdf="/revisioni/{id_progetto}/pdf/{item["id"]}"' in pagina.text
    assert f'data-ritorno="#item-abstract-{item["id"]}"' in pagina.text
    risposta_pdf = client.get(f'/revisioni/{id_progetto}/pdf/{item["id"]}')
    assert risposta_pdf.status_code == 200
    assert risposta_pdf.content.startswith(b"%PDF")


def test_lo_screening_mostra_soltanto_il_revisore_attivo():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada", "Luca"])
    revisioni.collega_ricerca(id_progetto, id_ricerca)

    pagina = client.get(f"/revisioni/{id_progetto}?revisore=Luca")
    assert pagina.text.count('name="revisore" value="Luca"') >= 2
    assert 'name="revisore" value="Ada"' not in pagina.text
    assert "decisions stay hidden" in pagina.text


def test_il_workspace_permette_il_flusso_completo_dalle_rotte():
    id_ricerca = ricerca_finta()
    id_progetto = revisioni.crea("Review AI", "sistematica", ["Ada", "Luca"])
    client.post(f"/revisioni/{id_progetto}/ricerche", data={"id_ricerca": id_ricerca})
    item = revisioni.progetto(id_progetto)["record"][0]["id"]

    risposta = client.post(f"/revisioni/{id_progetto}/screening/{item}", data={
        "fase": "abstract", "revisore": "Ada", "stato": "incluso", "motivo": "pertinente",
    }, follow_redirects=True)
    assert risposta.status_code == 200
    assert "Ada" in risposta.text

    esportato = client.get(f"/revisioni/{id_progetto}.md")
    assert esportato.status_code == 200
    assert "Review AI" in esportato.text
    assert "PRISMA-S" in esportato.text
