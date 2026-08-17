import requests

from .base import NormalizedResult, SourceError

API_URL = "https://doaj.org/api/search/articles/{query}"


def search(query: str, *, per_page: int = 10) -> list[NormalizedResult]:
    url = API_URL.format(query=requests.utils.quote(query, safe=""))
    try:
        r = requests.get(url, params={"pageSize": per_page}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise SourceError("doaj", str(e)) from e

    results = []
    for item in data.get("results", []):
        bibjson = item.get("bibjson") or {}
        authors = [a.get("name", "") for a in bibjson.get("author", []) or [] if a.get("name")]
        doi = None
        for ident in bibjson.get("identifier", []) or []:
            if ident.get("type") == "doi":
                doi = ident.get("id")
        pdf_url = None
        for link in bibjson.get("link", []) or []:
            if link.get("type") == "fulltext":
                pdf_url = link.get("url")
        year_raw = bibjson.get("year")
        try:
            year = int(year_raw) if year_raw else None
        except ValueError:
            year = None
        results.append(
            NormalizedResult(
                title=bibjson.get("title") or "",
                authors=authors,
                year=year,
                doi=doi,
                source="doaj",
                abstract=bibjson.get("abstract"),
                oa_pdf_url=pdf_url,
            )
        )
    return results
