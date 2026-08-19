"""Rotte dell'applicazione: HTML reso dal server, aggiornato con htmx."""

from __future__ import annotations

import asyncio
import json
import traceback
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config as config_module
from . import __version__
from . import biblioteca, cache, diagnostica, history, i18n, keywords, lavori, macchina, pdf, registro, search, unpaywall, watchdog
from . import zotero as zotero_client
from . import sources as sources_registry
from .config import PRESETS, Config
from .export import (
    CAMPI,
    CAMPI_PREDEFINITI,
    apa,
    normalizza_campi,
    protocollo,
    protocollo_testo,
    to_apa,
    to_bibtex,
    to_csv,
)
from .llm import LLMClient, LLMError
from .models import Strategy, Work
from .strategy import heuristic_strategy, strategy_from_form

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["apa_list"] = lambda works: [apa(w) for w in sorted(works, key=lambda w: apa(w).lower())]

@asynccontextmanager
async def ciclo_di_vita(_: FastAPI):
    watchdog.stato.lavori_in_corso = lambda: len(lavori.in_corso())
    sorveglianza = asyncio.create_task(watchdog.sorveglia()) if watchdog.attiva() else None
    yield
    if sorveglianza is not None:
        sorveglianza.cancel()


app = FastAPI(title="Ricerca", lifespan=ciclo_di_vita)


def avvisa(risposta, testo: str, livello: str = "errore"):
    """Manda un avviso alla pagina senza toccarne il contenuto.

    Scrivere l'errore dentro la risposta significa sostituire la zona
    colpita: l'elenco dei risultati sparirebbe per far posto a una riga
    rossa. Con questa intestazione la pagina resta dov'è e l'avviso compare
    in un angolo.
    """

    # Le intestazioni HTTP non portano UTF-8: accenti e punti mediani vanno
    # scritti come sequenze di scampo, che JSON.parse ricompone nel browser.
    risposta.headers["HX-Trigger"] = json.dumps(
        {"avviso": {"testo": testo, "livello": livello}}, ensure_ascii=True
    )
    return risposta


@app.middleware("http")
async def conta_le_richieste(request: Request, chiama):
    """Finché una richiesta è in volo, l'app non si spegne da sola."""

    watchdog.stato.apre_una_richiesta()
    try:
        return await chiama(request)
    finally:
        watchdog.stato.chiude_una_richiesta()


@app.exception_handler(Exception)
async def guasto(request: Request, eccezione: Exception):
    """Un errore imprevisto deve lasciare una traccia leggibile, non una
    pagina bianca: finisce nel registro e viene mostrato all'utente."""

    registro.errore(
        f"guasto su {request.url.path}",
        f"{type(eccezione).__name__}: {eccezione}",
    )
    traceback.print_exception(type(eccezione), eccezione, eccezione.__traceback__)
    testo = i18n.strings(current_config().lang)["guasto"]

    if request.headers.get("hx-request"):
        # 204: htmx non sostituisce nulla, la pagina resta intera.
        return avvisa(Response(status_code=204), testo)
    return HTMLResponse(f'<p class="nota errore">{testo}</p>', status_code=500)


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

    context = {
        "config": config,
        "lang": config.lang,
        "tema": config.tema if config.tema in ("chiaro", "scuro") else "auto",
        "densita": config.densita if config.densita == "compatta" else "comoda",
        "t": i18n.strings(config.lang),
        "versione": __version__,
        "config_percorso": str(config_module.CONFIG_FILE),
        "errori_registro": registro.quanti_errori(),
        "voci": registro.ultime(),
        "errori": registro.quanti_errori(),
    }
    context.update(extra)
    return context


@app.post("/tema/{tema}")
async def cambia_tema(request: Request, tema: str):
    """Chiaro, scuro o come il sistema. La scelta resta."""

    config = current_config()
    config.tema = tema if tema in ("chiaro", "scuro", "auto") else "auto"
    config_module.save(config)
    return templates.TemplateResponse(request, "partials/tema.html", base_context(config))


@app.post("/densita/{densita}", response_class=HTMLResponse)
async def cambia_densita(request: Request, densita: str):
    """Righe comode o compatte: dipende da quanto schermo si ha."""

    config = current_config()
    config.densita = "compatta" if densita == "compatta" else "comoda"
    config_module.save(config)
    return templates.TemplateResponse(request, "partials/densita.html", base_context(config))


@app.post("/lingua/{lang}")
async def cambia_lingua(lang: str):
    config = current_config()
    config.lang = i18n.normalize(lang)
    config_module.save(config)
    return RedirectResponse("/", status_code=303)


@app.get("/benvenuto", response_class=HTMLResponse)
async def benvenuto(request: Request, salvato: int = 0):
    """La configurazione guidata: ogni voce spiega che cosa cambia."""

    config = current_config()
    return templates.TemplateResponse(
        request,
        "benvenuto.html",
        base_context(
            config,
            presets=PRESETS,
            macchina=macchina.descrizione(),
            modelli=macchina.consiglio(),
            sources=sources_registry.ALL,
            salvato=bool(salvato),
        ),
    )


@app.post("/benvenuto")
async def salva_benvenuto(
    mailto: str = Form(default=""),
    llm_base_url: str = Form(default=""),
    llm_model: str = Form(default=""),
    llm_api_key: str = Form(default=""),
    core_api_key: str = Form(default=""),
    s2_api_key: str = Form(default=""),
    ncbi_api_key: str = Form(default=""),
    openalex_api_key: str = Form(default=""),
    zotero_api_key: str = Form(default=""),
    zotero_library_id: str = Form(default=""),
    lingua: str = Form(default="en"),
    tema: str = Form(default="auto"),
    azione: str = Form(default="fine"),
):
    config = current_config()
    config.mailto = mailto.strip()
    config.llm_base_url = llm_base_url.strip()
    config.llm_model = llm_model.strip()
    config.zotero_library_id = zotero_library_id.strip()
    config.lang = i18n.normalize(lingua)
    config.tema = tema if tema in ("chiaro", "scuro", "auto") else "auto"
    for campo, valore in (
        ("llm_api_key", llm_api_key),
        ("core_api_key", core_api_key),
        ("s2_api_key", s2_api_key),
        ("ncbi_api_key", ncbi_api_key),
        ("openalex_api_key", openalex_api_key),
        ("zotero_api_key", zotero_api_key),
    ):
        if valore.strip():
            setattr(config, campo, valore.strip())
    if azione == "continua":
        # Salva e resta sulla guida: chi inserisce le chiavi deve vedere
        # che sono state prese, senza uscire dalla pagina.
        config_module.save(config)
        return RedirectResponse("/benvenuto?salvato=1", status_code=303)

    config.configurato = "1"
    config_module.save(config)
    return RedirectResponse("/", status_code=303)


@app.post("/salta-benvenuto")
async def salta_benvenuto():
    """Chi vuole partire subito non deve compilare nulla."""

    config = current_config()
    config.configurato = "1"
    config_module.save(config)
    return RedirectResponse("/", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    config = current_config()
    if not config.configurato:
        return RedirectResponse("/benvenuto", status_code=303)
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
        tradotto = ""
        if config.llm_enabled and _sembra_italiano(topic):
            try:
                tradotto = await LLMClient(config, client).traduci(topic)
            except (LLMError, httpx.HTTPError, OSError):
                tradotto = ""
        suggestions = await keywords.gather(topic, client, config, tradotto)
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
            limite_predefinito=macchina.limite_consigliato(),
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
    limite = max(1, min(limite, 100))

    async def esegui():
        results, works = await search.run(strategy, fonte, limite, config)
        return history.salva(topic, strategy, results, works)

    lavoro = lavori.avvia(esegui(), f"ricerca: {topic[:60] or '—'}")
    return templates.TemplateResponse(
        request,
        "partials/in-corso.html",
        base_context(config, lavoro=lavoro),
    )


@app.get("/lavoro/{id_lavoro}", response_class=HTMLResponse)
async def stato_lavoro(request: Request, id_lavoro: str):
    """La pagina chiede come va: finché dura mostra l'attesa, poi il risultato.

    Il lavoro va avanti sul server: cambiare pagina non lo ferma, e tornando
    qui lo si ritrova concluso.
    """

    config = current_config()
    lavoro = lavori.prendi(id_lavoro)
    if lavoro is None:
        return templates.TemplateResponse(
            request, "partials/lavoro-perso.html", base_context(config)
        )
    if not lavoro.finito:
        return templates.TemplateResponse(
            request,
            "partials/in-corso.html",
            base_context(config, lavoro=lavoro),
        )
    if lavoro.stato == "fallito":
        return templates.TemplateResponse(
            request,
            "partials/lavoro-fallito.html",
            base_context(config, lavoro=lavoro),
        )

    return templates.TemplateResponse(
        request,
        "partials/risultati.html",
        base_context(config, results=[], **contesto_elenco(lavoro.risultato, [], "tabella")),
    )


# Parole che in inglese non esistono: bastano a capire che il topic è italiano.
_SPIE_ITALIANE = {
    "di", "del", "della", "dei", "degli", "delle", "gli", "che", "con", "per",
    "nella", "negli", "sulla", "come", "una", "uno", "sono", "anche", "più",
}


def _sembra_italiano(topic: str) -> bool:
    parole = {p.strip(".,;:()").lower() for p in topic.split()}
    return bool(parole & _SPIE_ITALIANE)


def _pdf_presenti(works: list[Work]) -> dict[int, bool]:
    return {i: pdf.gia_scaricato(w) is not None for i, w in enumerate(works)}


# Cinquanta record per pagina: oltre, la pagina si appesantisce e sulle
# macchine modeste lo scorrimento si sente.
PER_PAGINA = 50


def contesto_elenco(id_ricerca: str, campo, vista: str, pagina: int = 1) -> dict:
    """Tutto ciò che serve a disegnare un elenco di risultati, in un posto solo.

    Ci si arriva da tre strade — ricerca appena conclusa, cambio dei campi,
    ricerca riaperta dalla cronologia — e devono mostrare le stesse cose.
    """

    tutti = history.record(id_ricerca)
    voce = history.voce(id_ricerca) or {}
    pagine = max(1, -(-len(tutti) // PER_PAGINA))
    pagina = min(max(1, pagina), pagine)
    inizio = (pagina - 1) * PER_PAGINA
    return {
        "works": tutti[inizio : inizio + PER_PAGINA],
        "id_ricerca": id_ricerca,
        "campi": normalizza_campi(campo),
        "tutti_i_campi": CAMPI,
        "vista": "apa" if vista == "apa" else "tabella",
        "pdf_scaricati": _pdf_presenti(tutti),
        "quando": voce.get("quando", ""),
        "conteggi": history.conteggi(id_ricerca),
        "fonti": voce.get("fonti", []),
        "pdf_su_disco": pdf.quanti_scaricati(tutti),
        "pagina": pagina,
        "pagine": pagine,
        "inizio": inizio,
        "totale": len(tutti),
    }


def _elenco(
    request: Request,
    id_ricerca: str,
    campo: list[str],
    vista: str,
    pagina: int = 1,
):
    return templates.TemplateResponse(
        request,
        "partials/elenco.html",
        base_context(current_config(), **contesto_elenco(id_ricerca, campo, vista, pagina)),
    )


@app.post("/risultati/{id_ricerca}", response_class=HTMLResponse)
async def risultati(
    request: Request,
    id_ricerca: str,
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
    pagina: int = Form(default=1),
):
    """Ridisegna l'elenco con i campi scelti, come tabella o come lista APA."""

    return _elenco(request, id_ricerca, campo, vista, pagina=pagina)


def _campi_da_query(campi: str | None) -> list[str]:
    return normalizza_campi([c for c in (campi or "").split(",") if c])


@app.get("/export/{id_ricerca}.bib", response_class=PlainTextResponse)
async def export_bib(id_ricerca: str, campi: str | None = None):
    return PlainTextResponse(
        to_bibtex(history.record(id_ricerca), _campi_da_query(campi)),
        headers={"Content-Disposition": 'attachment; filename="references.bib"'},
    )


@app.get("/export/{id_ricerca}.csv", response_class=PlainTextResponse)
async def export_csv(id_ricerca: str, campi: str | None = None):
    return PlainTextResponse(
        to_csv(history.record(id_ricerca), _campi_da_query(campi)),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="records.csv"'},
    )


@app.get("/export/{id_ricerca}.apa.txt", response_class=PlainTextResponse)
async def export_apa(id_ricerca: str):
    return PlainTextResponse(
        to_apa(history.record(id_ricerca)),
        headers={"Content-Disposition": 'attachment; filename="apa-references.txt"'},
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
            registro.errore(f"PDF non scaricato: {work.title[:60]}", errore)
    risposta = templates.TemplateResponse(
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
    if errore:
        etichette = i18n.strings(current_config().lang)
        return avvisa(risposta, f"{etichette['pdf_error']}: {errore} — {etichette['pdf_upload_hint']}")
    return risposta


@app.post("/pdf/{id_ricerca}/{indice}/carica", response_class=HTMLResponse)
async def carica_pdf(request: Request, id_ricerca: str, indice: int, file: UploadFile = File(...)):
    """Riceve un PDF scaricato a mano e lo mette dove stanno gli altri."""

    works = history.record(id_ricerca)
    if indice >= len(works):
        return HTMLResponse("")
    problema = ""
    try:
        pdf.salva_caricato(works[indice], await file.read())
    except (ValueError, OSError) as exc:
        problema = i18n.strings(current_config().lang)["pdf_upload_failed"]
        registro.errore("PDF caricato", str(exc)[:160])

    risposta = _scheda(request, id_ricerca, indice)
    return avvisa(risposta, problema) if problema else risposta


@app.get("/pdf/{id_ricerca}.zip")
async def scarica_archivio_pdf(id_ricerca: str):
    """I PDF già scaricati, in un solo file da salvare sul proprio computer."""

    contenuto, quanti = pdf.archivio(history.record(id_ricerca))
    if not quanti:
        return PlainTextResponse(
            i18n.strings(current_config().lang)["zip_empty"], status_code=404
        )
    return Response(
        contenuto,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="article-pdfs.zip"'},
    )


@app.get("/pdf/{id_ricerca}/{indice}/file")
async def apri_pdf(id_ricerca: str, indice: int):
    works = history.record(id_ricerca)
    if indice >= len(works):
        return PlainTextResponse("record inesistente", status_code=404)
    percorso = pdf.gia_scaricato(works[indice])
    if percorso is None:
        return PlainTextResponse("PDF non ancora scaricato", status_code=404)
    # `inline`: il file si apre dentro il lettore dell'app, non parte un
    # altro scaricamento né si apre una finestra del browser di sistema.
    return FileResponse(
        percorso,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{percorso.name}"'},
    )


def _posizioni_per_fonte(voce: dict, work: Work) -> list[dict]:
    """In che posizione ogni banca dati ha restituito questo record."""

    righe = []
    for fonte in voce.get("fonti", []):
        if fonte.get("id") in work.sources:
            righe.append({"etichetta": fonte.get("etichetta", ""), "trovati": fonte.get("trovati", 0)})
    return righe


@app.get("/scheda/{id_ricerca}/{indice}", response_class=HTMLResponse)
async def scheda(request: Request, id_ricerca: str):
    """La scheda intera di un record, dentro la finestra dell'app."""

    return _scheda(request, id_ricerca, int(request.path_params["indice"]))


def _scheda(request: Request, id_ricerca: str, indice: int, salvato: bool = False, problema_pdf: str = ""):
    config = current_config()
    works = history.record(id_ricerca)
    if not works:
        return HTMLResponse("")
    indice = min(max(0, indice), len(works) - 1)
    work = works[indice]
    voce = history.voce(id_ricerca) or {}
    return templates.TemplateResponse(
        request,
        "partials/scheda.html",
        base_context(
            config,
            work=work,
            originale=history.originale(id_ricerca, indice),
            indice=indice,
            totale=len(works),
            id_ricerca=id_ricerca,
            posizioni=_posizioni_per_fonte(voce, work),
            riferimento=apa(work),
            bibtex=to_bibtex([work]).strip(),
            scaricato=pdf.gia_scaricato(work) is not None,
            nome_pdf=(pdf.gia_scaricato(work).name if pdf.gia_scaricato(work) else ""),
            cartella_pdf=str(config_module.CONFIG_DIR / "pdf"),
            salvato=salvato,
            problema_pdf=problema_pdf,
            sintesi=history.sintesi(id_ricerca, indice),
            sintesi_in_corso=lavori.per_descrizione(f"sintesi:{id_ricerca}:{indice}") is not None,
            ha_testo=bool(_testo_da_riassumere(work).strip()),
        ),
    )


@app.post("/scheda/{id_ricerca}/{indice}", response_class=HTMLResponse)
async def salva_scheda(
    request: Request,
    id_ricerca: str,
    indice: int,
    title: str = Form(default=""),
    authors: str = Form(default=""),
    year: str = Form(default=""),
    venue: str = Form(default=""),
    doi: str = Form(default=""),
):
    """Correzioni a mano ai metadati: gli originali restano nella cronologia."""

    history.correggi(
        id_ricerca,
        indice,
        {
            "title": title.strip(),
            "authors": [a.strip() for a in authors.split(";") if a.strip()],
            "year": int(year) if year.strip().isdigit() else None,
            "venue": venue.strip(),
            "doi": doi.strip(),
        },
    )
    registro.annota(
        i18n.strings(current_config().lang)["log_record_fixed"],
        f"{id_ricerca} · {indice}",
    )
    return _scheda(request, id_ricerca, indice, salvato=True)


@app.post("/screening/{id_ricerca}/{indice}", response_class=HTMLResponse)
async def screening(
    request: Request,
    id_ricerca: str,
    indice: int,
    stato: str = Form(...),
    motivo: str = Form(default=""),
):
    """Segna un record come incluso, forse o escluso. Ripetere annulla."""

    history.decide(id_ricerca, indice, stato, motivo)
    works = history.record(id_ricerca)
    if indice >= len(works):
        return HTMLResponse("")
    return templates.TemplateResponse(
        request,
        "partials/screening.html",
        base_context(
            current_config(),
            work=works[indice],
            indice=indice,
            id_ricerca=id_ricerca,
            conteggi=history.conteggi(id_ricerca),
            fuori_banda=True,
        ),
    )


@app.post("/screening-massa/{id_ricerca}", response_class=HTMLResponse)
async def screening_massa(
    request: Request,
    id_ricerca: str,
    stato: str = Form(...),
    selezione: list[int] = Form(default=[]),
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
):
    """Applica la stessa decisione a tutti i record spuntati."""

    for indice in selezione:
        decisione = history.decisioni(id_ricerca).get(str(indice), {})
        gia_deciso = decisione.get("stato", "")
        if stato == "annulla":
            if gia_deciso:
                history.decide(id_ricerca, indice, gia_deciso, decisione.get("motivo", ""))
        elif gia_deciso != stato:
            history.decide(id_ricerca, indice, stato, decisione.get("motivo", ""))
    return _elenco(request, id_ricerca, campo, vista)


@app.get("/export/{id_ricerca}.protocollo.txt", response_class=PlainTextResponse)
async def export_protocollo_testo(id_ricerca: str):
    voce = history.voce(id_ricerca) or {}
    return PlainTextResponse(
        protocollo_testo(voce, history.conteggi(id_ricerca)),
        headers={"Content-Disposition": 'attachment; filename="search-protocol.txt"'},
    )


@app.post("/zotero-massa/{id_ricerca}", response_class=HTMLResponse)
async def zotero_massa(
    request: Request,
    id_ricerca: str,
    selezione: list[int] = Form(default=[]),
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
):
    """Manda a Zotero i record spuntati; senza spunte, quelli inclusi."""

    config = current_config()
    works = history.record(id_ricerca)
    scelti = [works[i] for i in selezione if i < len(works)]
    da_inviare = scelti or [w for w in works if w.decisione == "incluso"] or works

    try:
        async with httpx.AsyncClient(headers={"User-Agent": search.USER_AGENT}) as client:
            esito = await zotero_client.invia(da_inviare, config, client)
        messaggio = i18n.strings(config.lang)["zotero_done"].format(**esito)
        registro.annota("Zotero", messaggio)
    except (zotero_client.ZoteroError, httpx.HTTPError, OSError) as exc:
        messaggio = i18n.strings(config.lang)["zotero_error"].format(errore=str(exc)[:160])
        registro.errore("Zotero", str(exc)[:200])
        return avvisa(_elenco(request, id_ricerca, campo, vista), messaggio)

    return avvisa(_elenco(request, id_ricerca, campo, vista), messaggio, "buono")


async def _completa_da_unpaywall(id_ricerca: str, indici: list[int], config: Config) -> dict:
    """Chiede a Unpaywall i campi mancanti dei record indicati."""

    works = history.record(id_ricerca)
    etichette = i18n.strings(config.lang)
    completati = falliti = 0
    cancello = asyncio.Semaphore(4)

    async def uno(indice: int, work: Work, client: httpx.AsyncClient):
        nonlocal completati, falliti
        if not work.doi or not unpaywall.da_completare(work):
            return
        async with cancello:
            try:
                conosciuto = await unpaywall.dati(work.doi, config, client)
            except (httpx.HTTPError, ValueError) as exc:
                falliti += 1
                registro.errore("Unpaywall", f"{work.doi}: {str(exc)[:120]}")
                return
        aggiunte = unpaywall.completamento(work, conosciuto)
        if aggiunte:
            history.completa(id_ricerca, indice, aggiunte)
            completati += 1
            registro.annota(
                etichette["log_unpaywall_record"].format(campi=", ".join(aggiunte)),
                work.title[:70],
            )

    async with cache.client(headers={"User-Agent": search.USER_AGENT}) as client:
        await asyncio.gather(*(uno(i, works[i], client) for i in indici if i < len(works)))

    return {"completati": completati, "falliti": falliti}


@app.post("/unpaywall/{id_ricerca}", response_class=HTMLResponse)
async def completa_da_unpaywall(
    request: Request,
    id_ricerca: str,
    selezione: list[int] = Form(default=[]),
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
):
    """Completa i record spuntati — o tutti — con quel che sa Unpaywall."""

    config = current_config()
    etichette = i18n.strings(config.lang)
    if not config.mailto_valido:
        return avvisa(_elenco(request, id_ricerca, campo, vista), etichette["unpaywall_no_email"])

    works = history.record(id_ricerca)
    indici = [i for i in selezione if i < len(works)] or list(range(len(works)))
    esito = await _completa_da_unpaywall(id_ricerca, indici, config)
    messaggio = etichette["unpaywall_done"].format(**esito)
    registro.annota("Unpaywall", messaggio)
    return avvisa(
        _elenco(request, id_ricerca, campo, vista),
        messaggio,
        "errore" if esito["falliti"] else "buono",
    )


def _testo_da_riassumere(work: Work) -> str:
    """Il testo pieno del PDF se c'è, altrimenti l'abstract.

    Riassumere un abstract dà poco, ma è meglio di niente; con il PDF
    scaricato il riassunto diventa davvero informativo.
    """

    percorso = pdf.gia_scaricato(work)
    if percorso is not None:
        testo = biblioteca.percorso_testo(percorso)
        if testo.exists():
            return testo.read_text(encoding="utf-8", errors="replace")
    return work.abstract or ""


@app.post("/scheda/{id_ricerca}/{indice}/sintesi", response_class=HTMLResponse)
async def chiedi_sintesi(
    request: Request,
    id_ricerca: str,
    indice: int,
    lingua: str = Form(default=""),
    rifai: str = Form(default=""),
):
    """Avvia il riassunto e torna subito: un modello locale può metterci un minuto."""

    config = current_config()
    works = history.record(id_ricerca)
    if indice >= len(works) or not config.llm_enabled:
        return _scheda(request, id_ricerca, indice)

    work = works[indice]
    testo = _testo_da_riassumere(work)
    if not testo.strip():
        return _scheda(request, id_ricerca, indice)

    # Un riassunto già scritto non si rifà da solo: solo se lo si chiede.
    if history.sintesi(id_ricerca, indice) and not rifai:
        return _scheda(request, id_ricerca, indice)

    scelta = "it" if lingua == "it" else "en"
    descrizione = f"sintesi:{id_ricerca}:{indice}"
    if lavori.per_descrizione(descrizione) is None:

        async def esegui():
            async with httpx.AsyncClient() as client:
                parti = await LLMClient(config, client).sintesi(work.title, testo, scelta)
            parti.update(
                {
                    "lingua": scelta,
                    "modello": config.llm_model,
                    "quando": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "fonte": "pdf" if len(testo) > 4000 else "abstract",
                }
            )
            history.salva_sintesi(id_ricerca, indice, parti)
            return parti

        lavori.avvia(esegui(), descrizione)

    return _scheda(request, id_ricerca, indice)


@app.post("/scheda/{id_ricerca}/{indice}/unpaywall", response_class=HTMLResponse)
async def completa_scheda(request: Request, id_ricerca: str, indice: int):
    """Lo stesso, per il record aperto nella scheda."""

    config = current_config()
    if config.mailto_valido:
        await _completa_da_unpaywall(id_ricerca, [indice], config)
    return _scheda(request, id_ricerca, indice)


@app.post("/pdf-massa/{id_ricerca}", response_class=HTMLResponse)
async def pdf_massa(
    request: Request,
    id_ricerca: str,
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
    selezione: list[int] = Form(default=[]),
):
    """Scarica in un colpo i PDF aperti: quelli spuntati, o tutti."""

    works = history.record(id_ricerca)
    indici = [i for i in selezione if i < len(works)] or list(range(len(works)))
    da_prendere = [(i, works[i]) for i in indici if works[i].oa_url and not pdf.gia_scaricato(works[i])]

    presi = falliti = 0
    if da_prendere:
        # Tre alla volta: piu' veloce di uno per uno, senza sembrare un raschiatore.
        cancello = asyncio.Semaphore(3)

        async def prendi(work, client):
            async with cancello:
                try:
                    await pdf.scarica(work, client)
                    return True
                except (httpx.HTTPError, ValueError, OSError):
                    return False

        async with httpx.AsyncClient(headers={"User-Agent": search.USER_AGENT}) as client:
            esiti = await asyncio.gather(*(prendi(w, client) for _i, w in da_prendere))
        presi = sum(1 for e in esiti if e)
        falliti = len(esiti) - presi

    esito = i18n.strings(current_config().lang)["pdf_bulk_done"].format(
        presi=presi, falliti=falliti
    )
    if falliti:
        registro.errore("PDF in blocco", esito)
    else:
        registro.annota("PDF in blocco", esito)
    return avvisa(
        _elenco(request, id_ricerca, campo, vista),
        esito,
        "errore" if falliti else "buono",
    )


@app.get("/export/{id_ricerca}.protocollo.md", response_class=PlainTextResponse)
async def export_protocollo(id_ricerca: str):
    voce = history.voce(id_ricerca) or {}
    return PlainTextResponse(
        protocollo(voce, history.conteggi(id_ricerca)),
        headers={"Content-Disposition": 'attachment; filename="search-protocol.md"'},
    )


@app.post("/affina/{id_ricerca}", response_class=HTMLResponse)
async def affina(request: Request, id_ricerca: str):
    """Termini nuovi ricavati dai record trovati: la strategia si allarga."""

    works = history.record(id_ricerca)
    strategia = history.strategia(id_ricerca)
    testi = [w.title for w in works] + [w.abstract for w in works if w.abstract]
    gia_presenti = " ".join(
        [(history.voce(id_ricerca) or {}).get("topic", "")]
        + [t for blocco in strategia.blocks for t in blocco.terms]
        + list(strategia.mesh)
    )
    nuovi = keywords.count_terms(testi, exclude=gia_presenti, min_count=3)
    return templates.TemplateResponse(
        request,
        "partials/affina.html",
        base_context(current_config(), termini=nuovi[:15], id_ricerca=id_ricerca),
    )


@app.post("/zotero/{id_ricerca}", response_class=HTMLResponse)
async def invia_a_zotero(request: Request, id_ricerca: str):
    """Manda a Zotero i record inclusi; se non ce ne sono, manda tutti."""

    config = current_config()
    works = history.record(id_ricerca)
    inclusi = [w for w in works if w.decisione == "incluso"]
    da_inviare = inclusi or works

    esito, errore = None, None
    try:
        async with httpx.AsyncClient(headers={"User-Agent": search.USER_AGENT}) as client:
            esito = await zotero_client.invia(da_inviare, config, client)
    except (zotero_client.ZoteroError, httpx.HTTPError, OSError) as exc:
        errore = str(exc)[:160]

    return templates.TemplateResponse(
        request,
        "partials/zotero.html",
        base_context(config, esito=esito, errore=errore, soltanto_inclusi=bool(inclusi)),
    )


@app.get("/biblioteca", response_class=HTMLResponse)
async def biblioteca_pagina(request: Request, q: str = ""):
    return templates.TemplateResponse(
        request,
        "biblioteca.html",
        base_context(
            current_config(),
            query=q,
            trovati=biblioteca.cerca(q) if q else [],
            documenti=len(biblioteca.documenti()),
        ),
    )


@app.get("/registro", response_class=HTMLResponse)
async def registro_pagina(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/registro.html",
        base_context(current_config(), voci=registro.ultime(), errori=registro.quanti_errori()),
    )


@app.post("/registro/svuota", response_class=HTMLResponse)
async def svuota_registro(request: Request):
    registro.svuota()
    return templates.TemplateResponse(
        request,
        "partials/registro.html",
        base_context(current_config(), voci=[], errori=0),
    )


@app.get("/registro.txt", response_class=PlainTextResponse)
async def registro_testo():
    return PlainTextResponse(
        registro.come_testo(),
        headers={"Content-Disposition": 'attachment; filename="activity.log"'},
    )


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
    return templates.TemplateResponse(
        request,
        "ricerca_salvata.html",
        base_context(current_config(), voce=voce, **contesto_elenco(id_ricerca, [], "tabella")),
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
            diagnosi=diagnostica.dati(),
            percorso=config_module.CONFIG_FILE,
            sources=sources_registry.ALL,
        ),
    )


SECRET_FIELDS = (
    "llm_api_key", "core_api_key", "s2_api_key", "ncbi_api_key",
    "zotero_api_key", "openalex_api_key",
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
    openalex_api_key: str = Form(default=""),
    zotero_api_key: str = Form(default=""),
    zotero_library_id: str = Form(default=""),
    zotero_library_type: str = Form(default="users"),
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
    config.zotero_library_id = zotero_library_id.strip()
    config.zotero_library_type = zotero_library_type.strip() or "users"

    nuovi = {
        "llm_api_key": llm_api_key.strip(),
        "core_api_key": core_api_key.strip(),
        "s2_api_key": s2_api_key.strip(),
        "ncbi_api_key": ncbi_api_key.strip(),
        "openalex_api_key": openalex_api_key.strip(),
        "zotero_api_key": zotero_api_key.strip(),
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
