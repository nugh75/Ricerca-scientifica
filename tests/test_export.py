from ricerca.export import to_bibtex, to_csv
from ricerca.models import Work


def works():
    return [
        Work(title="AI Literacy", authors=["Duri Long", "Brian Magerko"], year=2020,
             doi="10.1145/3313831", venue="CHI", url="https://openalex.org/W1", sources=["openalex"]),
        Work(title="AI Literacy", authors=["Duri Long"], year=2020, sources=["arxiv"]),
    ]


def test_bibtex_ha_una_voce_per_record_e_chiavi_uniche():
    text = to_bibtex(works())
    assert text.count("@article{") == 2
    assert "long2020ai," in text
    assert "long2020aia," in text  # chiave duplicata risolta con suffisso
    assert "doi = " not in text  # il DOI non è fra i campi predefiniti


def test_bibtex_vuoto_non_esplode():
    assert to_bibtex([]) == ""


def test_csv_ha_intestazione_e_righe():
    rows = to_csv(works()).splitlines()
    assert rows[0] == "anno,titolo,autori,sede,fonti"
    assert len(rows) == 3


def test_i_campi_scelti_governano_csv_e_bibtex():
    csv_testo = to_csv(works(), ["doi", "titolo"])
    assert csv_testo.splitlines()[0] == "doi,titolo"
    assert "10.1145/3313831" in csv_testo

    bib = to_bibtex(works(), ["doi", "abstract"])
    assert "doi = {10.1145/3313831}" in bib
    assert "author = " not in bib   # non selezionato
    assert "title = " in bib        # il titolo c'è sempre


def test_campi_sconosciuti_ricadono_sui_predefiniti():
    from ricerca.export import normalizza_campi

    assert normalizza_campi(["inventato"]) == list(("anno", "titolo", "autori", "sede", "fonti"))
    assert normalizza_campi(None) == list(("anno", "titolo", "autori", "sede", "fonti"))


def test_apa_formatta_nomi_estesi_e_iniziali():
    from ricerca.export import apa, apa_autore, to_apa

    assert apa_autore("Duri Long") == "Long, D."
    assert apa_autore("Yang Z") == "Yang, Z."          # stile PubMed
    assert apa_autore("Lacruz-Pérez I") == "Lacruz-Pérez, I."
    assert apa_autore("Platone") == "Platone"

    riferimento = apa(works()[0])
    assert riferimento.startswith("Long, D., & Magerko, B. (2020).")
    assert riferimento.endswith("https://doi.org/10.1145/3313831")
    assert "CHI." in riferimento


def test_apa_senza_anno_e_senza_doi():
    from ricerca.export import apa

    assert "(s.d.)." in apa(Work(title="Senza data", authors=["Rossi M"]))
    assert apa(Work(title="Con url", url="https://x/y")).endswith("https://x/y")


def test_to_apa_ordina_alfabeticamente():
    from ricerca.export import to_apa

    testo = to_apa([
        Work(title="B", authors=["Zeta A"], year=2020),
        Work(title="A", authors=["Alfa B"], year=2021),
    ])
    assert testo.index("Alfa") < testo.index("Zeta")


def test_la_chiave_di_citazione_usa_il_cognome_non_l_iniziale():
    from ricerca.export import cite_key, cognome

    assert cognome("Rossi M") == "Rossi"          # stile PubMed
    assert cognome("Duri Long") == "Long"
    assert cognome("Lacruz-Pérez I") == "Lacruz-Pérez"
    assert cognome("Platone") == "Platone"

    chiave = cite_key(Work(title="Studio sulle competenze", authors=["Rossi M"], year=2024), set())
    assert chiave.startswith("rossi2024")


def test_il_csv_esporta_citazioni_e_ritiro():
    from ricerca.export import to_csv
    from ricerca.models import Work

    riga = to_csv([Work(title="X", citazioni=7, ritirato=True)], ["titolo", "citazioni", "ritirato"])
    assert "7" in riga
    assert "True" in riga or "true" in riga.lower()
