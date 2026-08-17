from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import keys
from ..api_clients import crossref, openalex, semantic_scholar
from ..api_clients.base import SourceError
from ..deepseek_client import DeepSeekClient

router = APIRouter(prefix="/settings", tags=["settings"])


class KeyPayload(BaseModel):
    value: str


@router.get("/keys")
def list_keys():
    try:
        return {name: keys.has_key(name) for name in keys.KNOWN_KEYS}
    except keys.KeyringUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.put("/keys/{name}")
def set_key(name: str, payload: KeyPayload):
    if name not in keys.KNOWN_KEYS:
        raise HTTPException(status_code=404, detail="unknown key")
    try:
        keys.set_key(name, payload.value)
    except keys.KeyringUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"name": name, "saved": True}


@router.delete("/keys/{name}")
def delete_key(name: str):
    if name not in keys.KNOWN_KEYS:
        raise HTTPException(status_code=404, detail="unknown key")
    try:
        keys.delete_key(name)
    except keys.KeyringUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"name": name, "deleted": True}


def _test_connection(name: str, value: str) -> tuple[bool, str]:
    try:
        if name == "openalex_mailto":
            openalex.search("test", mailto=value, per_page=1)
        elif name == "semantic_scholar_key":
            semantic_scholar.search("test", api_key=value, per_page=1)
        elif name == "crossref_mailto":
            crossref.search("test", mailto=value, per_page=1)
        elif name == "deepseek_api_key":
            DeepSeekClient(value).analyze("summary", "test text for connection check.")
        return True, "ok"
    except SourceError as e:
        return False, e.message
    except Exception as e:
        return False, str(e)


@router.post("/keys/{name}/test")
def test_key(name: str, payload: KeyPayload):
    if name not in keys.KNOWN_KEYS:
        raise HTTPException(status_code=404, detail="unknown key")
    ok, message = _test_connection(name, payload.value)
    return {"name": name, "ok": ok, "message": message}
