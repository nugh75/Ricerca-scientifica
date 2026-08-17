import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from pydantic import BaseModel

from .. import db as db_module
from .. import keys
from .. import pdf_utils
from ..deepseek_client import DeepSeekClient

router = APIRouter(prefix="/library", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    mode: str


class ChatRequest(BaseModel):
    message: str


def _get_client() -> DeepSeekClient:
    try:
        api_key = keys.get_key("deepseek_api_key")
    except keys.KeyringUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API key not configured")
    return DeepSeekClient(api_key)


def _require_article_with_text(article_id: int, conn):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")
    if not row["pdf_path"] or not row["extracted_text_ok"]:
        raise HTTPException(status_code=400, detail="no extractable PDF text for this article")
    return row


@router.post("/{article_id}/analyze")
def analyze(article_id: int, payload: AnalyzeRequest, conn=Depends(db_module.get_db)):
    client = _get_client()
    row = _require_article_with_text(article_id, conn)
    text = pdf_utils.extract_text(Path(row["pdf_path"]))
    authors = json.loads(row["authors"])
    try:
        result = client.analyze(payload.mode, text, title=row["title"], authors=authors, year=row["year"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    analysis = json.loads(row["analysis_json"]) if row["analysis_json"] else {}
    analysis[payload.mode] = result
    conn.execute(
        "UPDATE articles SET analysis_json = ? WHERE id = ?", (json.dumps(analysis), article_id)
    )
    conn.commit()
    return {"article_id": article_id, "mode": payload.mode, "result": result}


@router.post("/{article_id}/chat")
def chat(article_id: int, payload: ChatRequest, conn=Depends(db_module.get_db)):
    client = _get_client()
    row = _require_article_with_text(article_id, conn)
    text = pdf_utils.extract_text(Path(row["pdf_path"]))

    session = conn.execute(
        "SELECT * FROM chat_sessions WHERE article_id = ? ORDER BY id DESC LIMIT 1",
        (article_id,),
    ).fetchone()
    messages = json.loads(session["messages_json"]) if session else []
    messages.append({"role": "user", "content": payload.message})

    try:
        reply = client.chat(text, messages)
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    messages.append({"role": "assistant", "content": reply})

    now = datetime.now(timezone.utc).isoformat()
    if session:
        conn.execute(
            "UPDATE chat_sessions SET messages_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(messages), now, session["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO chat_sessions (article_id, messages_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (article_id, json.dumps(messages), now, now),
        )
    conn.commit()
    return {"article_id": article_id, "reply": reply, "messages": messages}
