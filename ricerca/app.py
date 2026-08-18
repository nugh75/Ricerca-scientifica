"""Rotte dell'applicazione: HTML reso dal server, aggiornato con htmx."""

from __future__ import annotations

import secrets
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config as config_module
from . import keywords, search
from . import sources as sources_registry
from .config import PRESETS, Config
from .export import to_bibtex, to_csv
from .llm import LLMClient, LLMError
from .models import Strategy, Work
from .strategy import heuristic_strategy, strategy_from_form

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Ricerca")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Risultati dell'ultima ricerca, tenuti in memoria per l'export.
# L'app e' locale e mono-utente: non serve un archivio persistente in fase 1.
_EXPORTS: dict[str, list[Work]] = {}


def current_config() -> Config:
    return config_module.load()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    config = current_config()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "sources": sources_registry.executable(),
            "copy_only": sources_registry.copy_only(),
            "selected": sources_registry.DEFAULT_SELECTED,
            "config": config,
            "llm_enabled": config.llm_enabled,
        },
    )


@app.post("/mailto", response_class=HTMLResponse)
async def salva_mailto(request: Request, mailto: str = Form(...)):
    """Scorciatoia dalla pagina iniziale: senza email OpenAlex risponde 429."""

    config = current_config()
    config.mailto = mailto.strip()
    config_module.save(config)
    return templates.TemplateResponse(request, "partials/mailto.html", {"config": config})


@app.post("/suggerimenti", response_class=HTMLResponse)
async def suggerimenti(request: Request, topic: str = Form(...)):
    config = current_config()
    async with httpx.AsyncClient(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as client:
        suggestions = await keywords.gather(topic, client, config)
        strategy = heuristic_strategy(suggestions)
        if config.llm_enabled:
            try:
                blocks = await LLMClient(config, client).blocks_for(
                    topic, suggestions.concepts, suggestions.cooccurring, suggestions.mesh
                )
                strategy = Strategy(blocks=blocks, mesh=suggestions.mesh)
                suggestions.llm_used = True
            except (LLMError, httpx.HTTPError, OSError) as exc:
                suggestions.notes.append(f"LLM non utilizzabile ({str(exc)[:120]}) — blocchi dai soli dati")

    return templates.TemplateResponse(
        request,
        "partials/strategia.html",
        {
            "topic": topic,
            "suggestions": suggestions,
            "strategy": strategy,
            "queries": search.queries_for(strategy),
            "sources": sources_registry.executable(),
            "copy_only": sources_registry.copy_only(),
            "selected": sources_registry.DEFAULT_SELECTED,
            "config": config,
        },
    )


@app.post("/query", response_class=HTMLResponse)
async def query(
    request: Request,
    label: list[str] = Form(default=[]),
    terms: list[str] = Form(default=[]),
    mesh: str = Form(default=""),
):
    strategy = strategy_from_form(label, terms, mesh)
    return templates.TemplateResponse(
        request,
        "partials/query.html",
        {
            "queries": search.queries_for(strategy),
            "sources": sources_registry.executable(),
            "copy_only": sources_registry.copy_only(),
            "config": current_config(),
        },
    )


@app.post("/cerca", response_class=HTMLResponse)
async def cerca(
    request: Request,
    label: list[str] = Form(default=[]),
    terms: list[str] = Form(default=[]),
    mesh: str = Form(default=""),
    fonte: list[str] = Form(default=[]),
    limite: int = Form(default=25),
):
    config = current_config()
    strategy = strategy_from_form(label, terms, mesh)
    results, works = await search.run(strategy, fonte, max(1, min(limite, 100)), config)

    token = secrets.token_urlsafe(8)
    _EXPORTS.clear()
    _EXPORTS[token] = works
    return templates.TemplateResponse(
        request,
        "partials/risultati.html",
        {"results": results, "works": works, "token": token},
    )


@app.get("/export/{token}.bib", response_class=PlainTextResponse)
async def export_bib(token: str):
    return PlainTextResponse(
        to_bibtex(_EXPORTS.get(token, [])),
        headers={"Content-Disposition": 'attachment; filename="ricerca.bib"'},
    )


@app.get("/export/{token}.csv", response_class=PlainTextResponse)
async def export_csv(token: str):
    return PlainTextResponse(
        to_csv(_EXPORTS.get(token, [])),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ricerca.csv"'},
    )


@app.get("/impostazioni", response_class=HTMLResponse)
async def impostazioni(request: Request, salvato: int = 0):
    return templates.TemplateResponse(
        request,
        "impostazioni.html",
        {
            "config": current_config(),
            "presets": PRESETS,
            "salvato": bool(salvato),
            "percorso": config_module.CONFIG_FILE,
            "sources": sources_registry.ALL,
        },
    )


@app.post("/impostazioni")
async def salva_impostazioni(
    mailto: str = Form(default=""),
    llm_base_url: str = Form(default=""),
    llm_model: str = Form(default=""),
    llm_api_key: str = Form(default=""),
    core_api_key: str = Form(default=""),
    s2_api_key: str = Form(default=""),
    ncbi_api_key: str = Form(default=""),
):
    config_module.save(
        Config(
            mailto=mailto.strip(),
            llm_base_url=llm_base_url.strip(),
            llm_model=llm_model.strip(),
            llm_api_key=llm_api_key.strip(),
            core_api_key=core_api_key.strip(),
            s2_api_key=s2_api_key.strip(),
            ncbi_api_key=ncbi_api_key.strip(),
        )
    )
    return RedirectResponse("/impostazioni?salvato=1", status_code=303)


@app.post("/impostazioni/modelli", response_class=HTMLResponse)
async def modelli(request: Request, llm_base_url: str = Form(...), llm_api_key: str = Form(default="")):
    config = Config(llm_base_url=llm_base_url, llm_api_key=llm_api_key, llm_model="-")
    try:
        models = await LLMClient(config).list_models()
        error = None
    except (httpx.HTTPError, OSError, ValueError) as exc:
        models, error = [], str(exc)[:200]
    return templates.TemplateResponse(
        request, "partials/modelli.html", {"models": models, "error": error}
    )
