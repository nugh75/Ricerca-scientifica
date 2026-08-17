import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import db as db_module
from ..bib_export import export_bib

router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    article_ids: list[int]


@router.post("/bib")
def export(payload: ExportRequest, conn=Depends(db_module.get_db)):
    articles = []
    for aid in payload.article_ids:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (aid,)).fetchone()
        if row is None:
            continue
        d = dict(row)
        d["authors"] = json.loads(d["authors"])
        articles.append(d)
    return {"bib": export_bib(articles)}
