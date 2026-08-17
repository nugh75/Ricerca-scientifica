from difflib import SequenceMatcher

from .api_clients.base import NormalizedResult


def _normalize_title(t: str) -> str:
    return " ".join(t.lower().split())


def merge_results(
    results_by_source: dict[str, list[NormalizedResult]], threshold: float = 0.85
) -> list[NormalizedResult]:
    merged: list[NormalizedResult] = []
    for results in results_by_source.values():
        for r in results:
            match = None
            for m in merged:
                if r.doi and m.doi:
                    if r.doi.lower() == m.doi.lower():
                        match = m
                        break
                    continue  # both DOIs known and different: never the same work
                similarity = SequenceMatcher(
                    None, _normalize_title(r.title), _normalize_title(m.title)
                ).ratio()
                if similarity >= threshold:
                    match = m
                    break
            if match is None:
                merged.append(r)
            else:
                if not match.oa_pdf_url and r.oa_pdf_url:
                    match.oa_pdf_url = r.oa_pdf_url
                if not match.abstract and r.abstract:
                    match.abstract = r.abstract
    return merged
