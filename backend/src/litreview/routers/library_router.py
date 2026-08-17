import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db as db_module
from .. import pdf_utils
from ..config import PDF_DIR

router = APIRouter(prefix="/library", tags=["library"])


class ArticleIn(BaseModel):
    title: str
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    source: str
    abstract: str | None = None
    oa_pdf_url: str | None = None


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["authors"] = json.loads(d["authors"])
    d["extracted_text_ok"] = bool(d["extracted_text_ok"])
    return d


@router.post("")
def add_article(article: ArticleIn, conn=Depends(db_module.get_db)):
    cur = conn.execute(
        "INSERT INTO articles (title, authors, year, doi, source, abstract, "
        "oa_pdf_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            article.title,
            json.dumps(article.authors),
            article.year,
            article.doi,
            article.source,
            article.abstract,
            article.oa_pdf_url,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


@router.get("")
def list_articles(conn=Depends(db_module.get_db)):
    rows = conn.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/{article_id}")
def get_article(article_id: int, conn=Depends(db_module.get_db)):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")
    return _row_to_dict(row)


@router.post("/{article_id}/download")
def download_pdf(article_id: int, conn=Depends(db_module.get_db)):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")
    if not row["oa_pdf_url"]:
        raise HTTPException(status_code=400, detail="no open access PDF url available")

    dest = PDF_DIR / f"{article_id}.pdf"
    try:
        pdf_utils.download_pdf(row["oa_pdf_url"], dest)
    except pdf_utils.PdfDownloadError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    text = pdf_utils.extract_text(dest)
    ok = pdf_utils.has_extractable_text(text)
    conn.execute(
        "UPDATE articles SET pdf_path = ?, extracted_text_ok = ? WHERE id = ?",
        (str(dest), int(ok), article_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _row_to_dict(row)


@router.post("/{article_id}/upload")
def upload_pdf(article_id: int, file: UploadFile, conn=Depends(db_module.get_db)):
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="article not found")

    dest = PDF_DIR / f"{article_id}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = file.file.read()
    dest.write_bytes(content)

    text = pdf_utils.extract_text(dest)
    ok = pdf_utils.has_extractable_text(text)
    conn.execute(
        "UPDATE articles SET pdf_path = ?, extracted_text_ok = ? WHERE id = ?",
        (str(dest), int(ok), article_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _row_to_dict(row)
