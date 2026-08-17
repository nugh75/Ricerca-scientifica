from litreview.api_clients.base import NormalizedResult
from litreview.dedup import merge_results


def _r(title, doi=None, source="s", oa_pdf_url=None, abstract=None):
    return NormalizedResult(
        title=title, authors=["A"], year=2020, doi=doi, source=source,
        abstract=abstract, oa_pdf_url=oa_pdf_url,
    )


def test_merge_keeps_distinct_results():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/a")],
        "crossref": [_r("Completely Different Paper", doi="10.2/b")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 2


def test_merge_dedupes_by_doi_case_insensitive():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/ABC")],
        "crossref": [_r("Paper One (slightly different title)", doi="10.1/abc")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 1


def test_merge_dedupes_by_title_similarity_without_doi():
    by_source = {
        "openalex": [_r("A Study of Neural Networks")],
        "crossref": [_r("A Study of Neural Networks.")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 1


def test_merge_fills_missing_oa_pdf_url_from_later_source():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/a", oa_pdf_url=None)],
        "doaj": [_r("Paper One", doi="10.1/a", oa_pdf_url="https://x.org/p.pdf")],
    }
    merged = merge_results(by_source)
    assert len(merged) == 1
    assert merged[0].oa_pdf_url == "https://x.org/p.pdf"


def test_merge_fills_missing_abstract_from_later_source():
    by_source = {
        "openalex": [_r("Paper One", doi="10.1/a", abstract=None)],
        "crossref": [_r("Paper One", doi="10.1/a", abstract="An abstract.")],
    }
    merged = merge_results(by_source)
    assert merged[0].abstract == "An abstract."


def test_merge_empty_input_returns_empty_list():
    assert merge_results({}) == []
