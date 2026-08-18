from ricerca.dedup import merge, normalize_doi, normalize_title
from ricerca.models import Work


def test_normalize_doi_toglie_il_prefisso():
    assert normalize_doi("https://doi.org/10.1/ABC") == "10.1/abc"
    assert normalize_doi(None) is None


def test_normalize_title_toglie_accenti_e_punteggiatura():
    assert normalize_title("Perché l'IA: uno studio!") == "perche l ia uno studio"


def test_merge_unisce_per_doi_e_completa_i_campi():
    a = Work(title="Uno", doi="10.1/x", sources=["openalex"])
    b = Work(title="Uno", doi="https://doi.org/10.1/X", year=2024, authors=["Rossi"], sources=["pubmed"])
    merged = merge([a, b])
    assert len(merged) == 1
    assert merged[0].year == 2024
    assert merged[0].authors == ["Rossi"]
    assert merged[0].sources == ["openalex", "pubmed"]


def test_merge_unisce_per_titolo_quando_manca_il_doi():
    works = [
        Work(title="AI Literacy: a Review", sources=["arxiv"]),
        Work(title="ai literacy a review", sources=["doaj"]),
        Work(title="Altro lavoro", sources=["doaj"]),
    ]
    assert len(merge(works)) == 2
