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
