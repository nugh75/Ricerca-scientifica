from fastapi import APIRouter
from pydantic import BaseModel

from .. import keys
from ..api_clients import crossref, doaj, openalex, semantic_scholar
from ..api_clients.base import SourceError
from ..dedup import merge_results

router = APIRouter(prefix="/search", tags=["search"])


def _get_key_or_none(name: str) -> str | None:
    """Sources work without a key (just possibly with tighter rate limits),
    so an unavailable keyring shouldn't fail the search."""
    try:
        return keys.get_key(name)
    except keys.KeyringUnavailableError:
        return None


SOURCE_FUNCS = {
    "openalex": lambda q: openalex.search(q, mailto=_get_key_or_none("openalex_mailto")),
    "semantic_scholar": lambda q: semantic_scholar.search(
        q, api_key=_get_key_or_none("semantic_scholar_key")
    ),
    "crossref": lambda q: crossref.search(q, mailto=_get_key_or_none("crossref_mailto")),
    "doaj": lambda q: doaj.search(q),
}


class SearchRequest(BaseModel):
    query: str
    sources: list[str] = list(SOURCE_FUNCS.keys())


@router.post("")
def search(payload: SearchRequest):
    results_by_source: dict = {}
    errors: dict = {}
    for name in payload.sources:
        fn = SOURCE_FUNCS.get(name)
        if fn is None:
            continue
        try:
            results_by_source[name] = fn(payload.query)
        except SourceError as e:
            errors[name] = e.message
            results_by_source[name] = []
        except Exception as e:
            errors[name] = str(e)
            results_by_source[name] = []

    merged = merge_results(results_by_source)
    return {
        "results": [r.__dict__ for r in merged],
        "errors": errors,
    }
