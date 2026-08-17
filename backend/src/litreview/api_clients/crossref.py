import requests

from .base import NormalizedResult, SourceError

API_URL = "https://api.crossref.org/works"


def search(
    query: str, *, mailto: str | None = None, per_page: int = 10
) -> list[NormalizedResult]:
    params = {"query": query, "rows": per_page}
    ua = "litreview/1.0"
    if mailto:
        ua += f" (mailto:{mailto})"
    headers = {"User-Agent": ua}
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise SourceError("crossref", str(e)) from e

    items = (data.get("message") or {}).get("items", [])
    results = []
    for item in items:
        title_list = item.get("title") or [""]
        authors = []
        for a in item.get("author", []) or []:
            name = " ".join(filter(None, [a.get("given"), a.get("family")]))
            if name:
                authors.append(name)
        year = None
        date_parts = (item.get("issued") or {}).get("date-parts")
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
        results.append(
            NormalizedResult(
                title=title_list[0],
                authors=authors,
                year=year,
                doi=item.get("DOI"),
                source="crossref",
                abstract=item.get("abstract"),
                oa_pdf_url=None,
            )
        )
    return results
