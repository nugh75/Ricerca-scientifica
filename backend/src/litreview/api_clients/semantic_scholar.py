import requests

from .base import NormalizedResult, SourceError

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,authors,year,externalIds,abstract,openAccessPdf"


def search(
    query: str, *, api_key: str | None = None, per_page: int = 10
) -> list[NormalizedResult]:
    params = {"query": query, "limit": per_page, "fields": FIELDS}
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise SourceError("semantic_scholar", str(e)) from e

    results = []
    for item in data.get("data", []):
        oa_pdf = item.get("openAccessPdf") or {}
        results.append(
            NormalizedResult(
                title=item.get("title") or "",
                authors=[a.get("name", "") for a in item.get("authors", []) if a.get("name")],
                year=item.get("year"),
                doi=(item.get("externalIds") or {}).get("DOI"),
                source="semantic_scholar",
                abstract=item.get("abstract"),
                oa_pdf_url=oa_pdf.get("url"),
            )
        )
    return results
