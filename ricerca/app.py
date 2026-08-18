"""Rotte dell'applicazione: HTML reso dal server, aggiornato con htmx."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config as config_module
from . import cache, history, i18n, keywords, pdf, search, watchdog
from . import sources as sources_registry
from .config import PRESETS, Config
from .export import CAMPI, CAMPI_PREDEFINITI, apa, normalizza_campi, to_apa, to_bibtex, to_csv
from .llm import LLMClient, LLMError
from .models import Strategy, Work
from .strategy import heuristic_strategy, strategy_from_form

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["apa_list"] = lambda works: [apa(w) for w in sorted(works, key=lambda w: apa(w).lower())]

@asynccontextmanager
async def ciclo_di_vita(_: FastAPI):
    sorveglianza = asyncio.create_task(watchdog.sorveglia()) if watchdog.attiva() else None
    yield
    if sorveglianza is not None:
        sorveglianza.cancel()


app = FastAPI(title="Ricerca", lifespan=ciclo_di_vita)


@app.post("/battito")
async def battito():
    """La pagina aperta si fa viva."""

    watchdog.stato.battito()
    return PlainTextResponse("", status_code=204)


@app.post("/chiudi")
async def chiudi():
    """La pagina sta per essere chiusa: se non ne arrivano altre, si spegne."""

    watchdog.stato.pagina_chiusa()
    return PlainTextResponse("", status_code=204)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

def current_config() -> Config:
    return config_module.load()


def base_context(config: Config, **extra) -> dict:
    """Ogni pagina riceve le stringhe nella lingua scelta."""

    context = {"config": config, "lang": config.lang, "t": i18n.strings(config.lang)}
    context.update(extra)
    return context


@app.post("/lingua/{lang}")
async def cambia_lingua(lang: str):
    config = current_config()
    config.lang = i18n.normalize(lang)
    config_module.save(config)
    return RedirectResponse("/", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    config = current_config()
    return templates.TemplateResponse(
        request,
        "index.html",
        base_context(
            config,
            sources=sources_registry.executable(),
            copy_only=sources_registry.copy_only(),
            selected=sources_registry.DEFAULT_SELECTED,
            llm_enabled=config.llm_enabled,
        ),
    )


@app.post("/mailto", response_class=HTMLResponse)
async def salva_mailto(request: Request, mailto: str = Form(...)):
    """Scorciatoia dalla pagina iniziale: senza email OpenAlex risponde 429."""

    config = current_config()
    config.mailto = mailto.strip()
    config_module.save(config)
    return templates.TemplateResponse(request, "partials/mailto.html", base_context(config))


@app.post("/suggerimenti", response_class=HTMLResponse)
async def suggerimenti(request: Request, topic: str = Form(...)):
    config = current_config()
    async with cache.client(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as client:
        suggestions = await keywords.gather(topic, client, config)
        strategy = heuristic_strategy(suggestions, config.lang)
        if config.llm_enabled:
            try:
                blocks = await LLMClient(config, client).blocks_for(
                    topic,
                    suggestions.concepts,
                    suggestions.cooccurring,
                    suggestions.mesh,
                    config.lang,
                )
                strategy = Strategy(blocks=blocks, mesh=suggestions.mesh)
                suggestions.llm_used = True
            except (LLMError, httpx.HTTPError, OSError) as exc:
                suggestions.notes.append(
                    i18n.strings(config.lang)["llm_unusable"].format(error=str(exc)[:120])
                )

    return templates.TemplateResponse(
        request,
        "partials/strategia.html",
        base_context(
            config,
            topic=topic,
            suggestions=suggestions,
            strategy=strategy,
            queries=search.queries_for(strategy),
            sources=sources_registry.executable(),
            copy_only=sources_registry.copy_only(),
            selected=sources_registry.DEFAULT_SELECTED,
        ),
    )


@app.post("/query", response_class=HTMLResponse)
async def query(
    request: Request,
    label: list[str] = Form(default=[]),
    terms: list[str] = Form(default=[]),
    mesh: str = Form(default=""),
    anno_da: str = Form(default=""),
    anno_a: str = Form(default=""),
    solo_articoli: bool = Form(default=False),
):
    strategy = strategy_from_form(label, terms, mesh, anno_da, anno_a, solo_articoli)
    return templates.TemplateResponse(
        request,
        "partials/query.html",
        base_context(
            current_config(),
            queries=search.queries_for(strategy),
            sources=sources_registry.executable(),
            copy_only=sources_registry.copy_only(),
        ),
    )


@app.post("/cerca", response_class=HTMLResponse)
async def cerca(
    request: Request,
    label: list[str] = Form(default=[]),
    terms: list[str] = Form(default=[]),
    mesh: str = Form(default=""),
    fonte: list[str] = Form(default=[]),
    limite: int = Form(default=25),
    topic: str = Form(default=""),
    anno_da: str = Form(default=""),
    anno_a: str = Form(default=""),
    solo_articoli: bool = Form(default=False),
):
    config = current_config()
    strategy = strategy_from_form(label, terms, mesh, anno_da, anno_a, solo_articoli)
    results, works = await search.run(strategy, fonte, max(1, min(limite, 100)), config)
    id_ricerca = history.salva(topic, strategy, results, works)

    return templates.TemplateResponse(
        request,
        "partials/risultati.html",
        base_context(
            config,
            results=results,
            works=works,
            id_ricerca=id_ricerca,
            campi=list(CAMPI_PREDEFINITI),
            tutti_i_campi=CAMPI,
            vista="tabella",
            pdf_scaricati=_pdf_presenti(works),
        ),
    )


def _pdf_presenti(works: list[Work]) -> dict[int, bool]:
    return {i: pdf.gia_scaricato(w) is not None for i, w in enumerate(works)}


@app.post("/risultati/{id_ricerca}", response_class=HTMLResponse)
async def risultati(
    request: Request,
    id_ricerca: str,
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
):
    """Ridisegna l'elenco con i campi scelti, come tabella o come lista APA."""

    works = history.record(id_ricerca)
    voce = history.voce(id_ricerca) or {}
    return templates.TemplateResponse(
        request,
        "partials/elenco.html",
        base_context(
            current_config(),
            works=works,
            id_ricerca=id_ricerca,
            campi=normalizza_campi(campo),
            tutti_i_campi=CAMPI,
            vista="apa" if vista == "apa" else "tabella",
            pdf_scaricati=_pdf_presenti(works),
            quando=voce.get("quando", ""),
        ),
    )


def _campi_da_query(campi: str | None) -> list[str]:
    return normalizza_campi([c for c in (campi or "").split(",") if c])


@app.get("/export/{id_ricerca}.bib", response_class=PlainTextResponse)
async def export_bib(id_ricerca: str, campi: str | None = None):
    return PlainTextResponse(
        to_bibtex(history.record(id_ricerca), _campi_da_query(campi)),
        headers={"Content-Disposition": 'attachment; filename="ricerca.bib"'},
    )


@app.get("/export/{id_ricerca}.csv", response_class=PlainTextResponse)
async def export_csv(id_ricerca: str, campi: str | None = None):
    return PlainTextResponse(
        to_csv(history.record(id_ricerca), _campi_da_query(campi)),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ricerca.csv"'},
    )


@app.get("/export/{id_ricerca}.apa.txt", response_class=PlainTextResponse)
async def export_apa(id_ricerca: str):
    return PlainTextResponse(
        to_apa(history.record(id_ricerca)),
        headers={"Content-Disposition": 'attachment; filename="riferimenti-apa.txt"'},
    )


@app.post("/pdf/{id_ricerca}/{indice}", response_class=HTMLResponse)
async def scarica_pdf(request: Request, id_ricerca: str, indice: int):
    """Scarica il PDF aperto di un record e restituisce la cella aggiornata."""

    works = history.record(id_ricerca)
    if indice >= len(works):
        return HTMLResponse("")
    work = works[indice]
    errore = None
    async with httpx.AsyncClient(headers={"User-Agent": search.USER_AGENT}) as client:
        try:
            await pdf.scarica(work, client)
        except (httpx.HTTPError, ValueError, OSError) as exc:
            errore = str(exc)[:120]
    return templates.TemplateResponse(
        request,
        "partials/pdf.html",
        base_context(
            current_config(),
            work=work,
            indice=indice,
            id_ricerca=id_ricerca,
            scaricato=pdf.gia_scaricato(work) is not None,
            errore=errore,
        ),
    )


@app.get("/pdf/{id_ricerca}/{indice}/file")
async def apri_pdf(id_ricerca: str, indice: int):
    works = history.record(id_ricerca)
    if indice >= len(works):
        return PlainTextResponse("record inesistente", status_code=404)
    percorso = pdf.gia_scaricato(works[indice])
    if percorso is None:
        return PlainTextResponse("PDF non ancora scaricato", status_code=404)
    return FileResponse(percorso, media_type="application/pdf", filename=percorso.name)


@app.get("/cronologia", response_class=HTMLResponse)
async def cronologia(request: Request):
    return templates.TemplateResponse(
        request,
        "cronologia.html",
        base_context(current_config(), voci=history.elenco()),
    )


@app.get("/cronologia/{id_ricerca}", response_class=HTMLResponse)
async def cronologia_voce(request: Request, id_ricerca: str):
    voce = history.voce(id_ricerca)
    if voce is None:
        return RedirectResponse("/cronologia", status_code=303)
    works = history.record(id_ricerca)
    return templates.TemplateResponse(
        request,
        "ricerca_salvata.html",
        base_context(
            current_config(),
            voce=voce,
            works=works,
            id_ricerca=id_ricerca,
            campi=list(CAMPI_PREDEFINITI),
            tutti_i_campi=CAMPI,
            vista="tabella",
            pdf_scaricati=_pdf_presenti(works),
            quando=voce.get("quando", ""),
        ),
    )


@app.post("/cronologia/{id_ricerca}/elimina")
async def elimina_voce(id_ricerca: str):
    history.elimina(id_ricerca)
    return RedirectResponse("/cronologia", status_code=303)


@app.post("/cronologia/svuota")
async def svuota_cronologia():
    history.svuota()
    return RedirectResponse("/cronologia", status_code=303)


@app.get("/impostazioni", response_class=HTMLResponse)
async def impostazioni(request: Request, salvato: int = 0):
    return templates.TemplateResponse(
        request,
        "impostazioni.html",
        base_context(
            current_config(),
            presets=PRESETS,
            salvato=bool(salvato),
            percorso=config_module.CONFIG_FILE,
            sources=sources_registry.ALL,
        ),
    )


SECRET_FIELDS = ("llm_api_key", "core_api_key", "s2_api_key", "ncbi_api_key")


@app.post("/impostazioni")
async def salva_impostazioni(
    mailto: str = Form(default=""),
    llm_base_url: str = Form(default=""),
    llm_model: str = Form(default=""),
    llm_api_key: str = Form(default=""),
    core_api_key: str = Form(default=""),
    s2_api_key: str = Form(default=""),
    ncbi_api_key: str = Form(default=""),
    rimuovi: list[str] = Form(default=[]),
):
    """Un campo chiave lasciato vuoto conserva la chiave gia' salvata.

    Le chiavi non vengono mai rimandate al browser, quindi il modulo arriva
    vuoto anche quando sono impostate: per cancellarne una si spunta
    "rimuovi" accanto al campo.
    """

    config = current_config()
    config.mailto = mailto.strip()
    config.llm_base_url = llm_base_url.strip()
    config.llm_model = llm_model.strip()

    nuovi = {
        "llm_api_key": llm_api_key.strip(),
        "core_api_key": core_api_key.strip(),
        "s2_api_key": s2_api_key.strip(),
        "ncbi_api_key": ncbi_api_key.strip(),
    }
    for campo, valore in nuovi.items():
        if campo in rimuovi:
            setattr(config, campo, "")
        elif valore:
            setattr(config, campo, valore)

    config_module.save(config)
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
        request,
        "partials/modelli.html",
        base_context(current_config(), models=models, error=error),
    )
