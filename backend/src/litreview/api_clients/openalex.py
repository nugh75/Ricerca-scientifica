import requests

from .base import NormalizedResult, SourceError

API_URL = "https://api.openalex.org/works"


def search(
    query: str, *, mailto: str | None = None, per_page: int = 10
) -> list[NormalizedResult]:
    params: dict = {"search": query, "per-page": per_page}
    if mailto:
        params["mailto"] = mailto
    try:
        r = requests.get(API_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise SourceError("openalex", str(e)) from e
    results = []
    for item in data.get("results", []):
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in item.get("authorships", [])
        ]
        oa = item.get("open_access") or {}
        results.append(
            NormalizedResult(
                title=item.get("title") or "",
                authors=[a for a in authors if a],
                year=item.get("publication_year"),
                doi=item.get("doi"),
                source="openalex",
                abstract=None,
                oa_pdf_url=oa.get("oa_url"),
            )
        )
    return results
