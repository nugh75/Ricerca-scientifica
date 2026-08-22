from ricerca import history
from ricerca.models import Block, SourceResult, Strategy, Work


def ricerca_finta(topic="AI literacy"):
    strategy = Strategy([Block("Concetto", ["AI literacy"])], mesh=["Literacy"])
    works = [Work(title="Uno", year=2024, doi="10.1/x", sources=["openalex"])]
    results = [
        SourceResult("openalex", "OpenAlex", 'query', works=works),
        SourceResult("doaj", "DOAJ", "query", error="HTTP 500"),
    ]
    return history.salva(topic, strategy, results, works)


def test_una_ricerca_salvata_si_rilegge_intera():
    id_voce = ricerca_finta()
    voce = history.voce(id_voce)
    assert voce["topic"] == "AI literacy"
    assert voce["totale"] == 1
    assert [f["errore"] for f in voce["fonti"]] == [None, "HTTP 500"]

    record = history.record(id_voce)
    assert record[0].title == "Uno"
    assert record[0].sources == ["openalex"]

    strategia = history.strategia(id_voce)
    assert strategia.blocks[0].terms == ["AI literacy"]
    assert strategia.mesh == ["Literacy"]


def test_un_abstract_storico_con_marcatura_si_rilegge_pulito():
    strategy = Strategy([Block("Concetto", ["x"])])
    id_voce = history.salva(
        "topic", strategy, [SourceResult("europepmc", "Europe PMC", "q")],
        [Work(title="Uno", abstract="<h4>Background</h4><p>Testo leggibile.</p>")],
    )

    assert history.record(id_voce)[0].abstract == "Background Testo leggibile."


def test_una_cronologia_vecchia_non_richiede_gli_id_bibliometrici():
    id_voce = ricerca_finta()
    record = history.record(id_voce)[0]

    assert record.author_ids == []
    assert record.venue_id == ""


def test_l_elenco_non_porta_i_record():
    ricerca_finta()
    voce = history.elenco()[0]
    assert "record" not in voce
    assert voce["totale"] == 1


def test_le_ricerche_piu_recenti_stanno_in_cima():
    ricerca_finta("prima")
    ricerca_finta("seconda")
    assert [v["topic"] for v in history.elenco()] == ["seconda", "prima"]


def test_la_cronologia_si_ferma_al_limite():
    history.MAX_VOCI  # il limite è dichiarato
    for n in range(history.MAX_VOCI + 3):
        ricerca_finta(f"topic {n}")
    assert len(history.elenco()) == history.MAX_VOCI


def test_eliminare_e_svuotare():
    id_voce = ricerca_finta()
    assert history.elimina(id_voce) is True
    assert history.elimina(id_voce) is False
    ricerca_finta()
    history.svuota()
    assert history.elenco() == []


def test_un_file_illeggibile_non_fa_esplodere_la_cronologia(isolated_config):
    (isolated_config / "cronologia.json").write_text("non è json")
    assert history.elenco() == []
    assert history.record("qualsiasi") == []


def test_il_file_della_cronologia_e_privato(isolated_config):
    import stat

    ricerca_finta()
    modo = (isolated_config / "history.json").stat().st_mode
    assert stat.S_IMODE(modo) == 0o600


def test_i_record_nuovi_vanno_in_coda_senza_duplicare():
    strategy = Strategy(blocks=[Block("B", ["x"])])
    esistenti = [Work(title="Primo", doi="10.1/a"), Work(title="Secondo", doi="10.1/b")]
    id_voce = history.salva(
        "topic", strategy, [SourceResult("openalex", "OpenAlex", "q")], esistenti
    )

    entrati = history.aggiungi(
        id_voce,
        [Work(title="Primo di nuovo", doi="10.1/a"), Work(title="Terzo", doi="10.1/c")],
        "citazioni",
    )
    record = history.record(id_voce)
    assert entrati == 1
    assert [w.title for w in record] == ["Primo", "Secondo", "Terzo"]
    assert record[2].sources == ["citazioni"]


def test_le_decisioni_gia_prese_restano_sul_record_giusto():
    strategy = Strategy(blocks=[Block("B", ["x"])])
    id_voce = history.salva(
        "topic", strategy, [SourceResult("openalex", "OpenAlex", "q")],
        [Work(title="Primo", doi="10.1/a"), Work(title="Secondo", doi="10.1/b")],
    )
    history.decide(id_voce, 1, "incluso", "pertinente")
    history.aggiungi(id_voce, [Work(title="Terzo", doi="10.1/c")], "citazioni")
    record = history.record(id_voce)
    assert record[1].title == "Secondo"
    assert record[1].decisione == "incluso"


def test_la_cronologia_si_filtra_per_argomento_e_si_divide_in_pagine():
    from fastapi.testclient import TestClient
    from ricerca.app import app

    client = TestClient(app)
    for numero in range(30):
        history.salva(
            f"autoefficacia {numero}",
            Strategy([Block("C", ["x"])]),
            [],
            [Work(title=f"W{numero}", sources=["openalex"])],
        )
    history.salva("orientamento scolastico", Strategy([Block("C", ["y"])]), [], [])

    prima = client.get("/cronologia")
    assert "orientamento scolastico" in prima.text
    assert "page 1 of 2" in prima.text

    filtrata = client.get("/cronologia", params={"q": "ORIENTAMENTO"})
    assert "orientamento scolastico" in filtrata.text
    assert "autoefficacia" not in filtrata.text

    assert "No search on this topic" in client.get("/cronologia", params={"q": "zzz"}).text


def test_una_ricerca_salvata_si_riapre_pronta_da_rilanciare():
    from fastapi.testclient import TestClient
    from ricerca.app import app
    from ricerca.models import Filtri

    client = TestClient(app)
    strategia = Strategy(
        blocks=[Block("Concetto", ["self-efficacy", "autoefficacia"])],
        mesh=["Self Efficacy"],
        filtri=Filtri(anno_da=2019, solo_articoli=True, solo_oa=True),
    )
    id_ricerca = history.salva("autoefficacia docenti", strategia, [], [])

    pagina = client.get(f"/cronologia/{id_ricerca}/riesegui").text

    assert 'value="autoefficacia docenti"' in pagina          # l'argomento torna
    assert "self-efficacy, autoefficacia" in pagina           # e i blocchi
    assert 'name="anno_da" min="1900" max="2100" placeholder="2019" value="2019"' in pagina
    assert 'name="solo_articoli" value="true" checked' in pagina
    assert 'name="solo_oa" value="1" checked' in pagina
    assert '<details class="filtri-avanzati" open>' in pagina  # il filtro attivo si vede
    assert "Strategy taken from the search" in pagina


def test_riesegui_una_ricerca_che_non_esiste_torna_alla_cronologia():
    from fastapi.testclient import TestClient
    from ricerca.app import app

    client = TestClient(app)
    risposta = client.get("/cronologia/inesistente/riesegui", follow_redirects=False)
    assert risposta.status_code == 303
    assert risposta.headers["location"] == "/cronologia"
