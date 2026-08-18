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
    assert "doi = {10.1145/3313831}" in text


def test_bibtex_vuoto_non_esplode():
    assert to_bibtex([]) == ""


def test_csv_ha_intestazione_e_righe():
    rows = to_csv(works()).splitlines()
    assert rows[0].startswith("titolo,autori,anno")
    assert len(rows) == 3
