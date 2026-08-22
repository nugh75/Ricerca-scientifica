"""Rotte dell'applicazione: HTML reso dal server, aggiornato con htmx."""

from __future__ import annotations

import asyncio
import json
import traceback
import unicodedata
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

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
from . import biblioteca, cache, citazioni, costo, diagnostica, faccette, history, i18n, keywords, lavori, macchina, openalex_api, pdf, profili, registro, revisioni, search, unpaywall, watchdog, wiki
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
from .models import Strategy, Suggestions, Work
from .strategy import LINGUE, heuristic_strategy, strategy_from_form

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["apa_list"] = lambda works: [apa(w) for w in sorted(works, key=lambda w: apa(w).lower())]
templates.env.filters["numero"] = lambda valore: f"{int(valore or 0):,}"

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
        "lingue": LINGUE,
    }
    context.update(extra)
    return context


def _contesto_revisione(
    id_progetto: str,
    revisore: str = "",
    pagina_abstract: int = 1,
    pagina_fulltext: int = 1,
) -> dict:
    """Dati derivati del workspace, raccolti una volta per tutte le sezioni."""

    progetto = revisioni.progetto(id_progetto) or {}
    revisori = progetto.get("revisori", [])
    revisore_attivo = revisore if revisore in revisori else (revisori[0] if revisori else "")
    record = []
    conflitti_abstract = set(revisioni.conflitti(id_progetto, "abstract"))
    conflitti_fulltext = set(revisioni.conflitti(id_progetto, "fulltext"))
    titoli = {
        item.get("id", ""): item.get("record", {}).get("title", "")
        for item in progetto.get("record", [])
    }
    for item in revisioni.lavori(progetto):
        id_item = item.get("id", "")
        work = item["work"]
        doi = (work.doi or "").strip()
        url_articolo = (
            doi if doi.startswith(("http://", "https://"))
            else f"https://doi.org/{doi}" if doi
            else next(
                (
                    url for url in (work.url, work.oa_url)
                    if url and url.startswith(("http://", "https://"))
                ),
                "",
            )
        )
        record.append({
            **item,
            "url_articolo": url_articolo,
            "pdf_scaricato": pdf.gia_scaricato(work) is not None,
            "decisioni_abstract": revisioni.decisioni_item(progetto, id_item, "abstract"),
            "decisioni_fulltext": revisioni.decisioni_item(progetto, id_item, "fulltext"),
            "stato_abstract": revisioni.stato_finale(progetto, id_item, "abstract"),
            "stato_fulltext": revisioni.stato_finale(progetto, id_item, "fulltext"),
            "conflitto_abstract": id_item in conflitti_abstract,
            "conflitto_fulltext": id_item in conflitti_fulltext,
            "conflitto_estrazione": revisioni.conflitto_estrazione(progetto, id_item),
            "testo_completo": progetto.get("testi_completi", {}).get(id_item, {}),
            "studio_principale": titoli.get(
                progetto.get("gruppi_studio", {}).get(id_item, ""), ""
            ),
            "variazioni": progetto.get("versioni_record", {}).get(id_item, []),
        })
    per_pagina = 25

    def pagina_screening(
        candidati: list[dict], pagina: int, fase: str
    ) -> tuple[list[dict], int, int]:
        candidati = sorted(
            candidati,
            key=lambda voce: (
                not voce.get(f"conflitto_{fase}"),
                bool(voce.get(f"stato_{fase}")),
            ),
        )
        pagine = max(1, -(-len(candidati) // per_pagina))
        pagina = min(max(1, pagina), pagine)
        inizio = (pagina - 1) * per_pagina
        return candidati[inizio : inizio + per_pagina], pagina, pagine

    record_abstract, pagina_abstract, pagine_abstract = pagina_screening(
        record, pagina_abstract, "abstract"
    )
    candidati_fulltext = [voce for voce in record if voce.get("stato_abstract") == "incluso"]
    record_fulltext, pagina_fulltext, pagine_fulltext = pagina_screening(
        candidati_fulltext, pagina_fulltext, "fulltext"
    )
    collegate = {r.get("id") for r in progetto.get("ricerche", [])}
    riepilogo = revisioni.riepilogo(progetto)
    # Le fasi finali lavorano sugli inclusi: finché il testo completo non ha
    # deciso nulla valgono gli inclusi dell'abstract.
    inclusi = [
        voce for voce in record
        if voce.get("stato_fulltext") == "incluso"
        or (not riepilogo["fulltext"]["incluso"] and voce.get("stato_abstract") == "incluso")
    ]
    return {
        "progetto": progetto,
        "record_inclusi": inclusi,
        "record_revisione": record,
        "riepilogo_revisione": riepilogo,
        "checklist_prisma_s": revisioni.checklist_prisma_s(progetto),
        "articoli_sentinella": revisioni.controlla_sentinelle(progetto),
        "protocollo_mancanti": revisioni.campi_protocollo_mancanti(progetto),
        "ricerche_disponibili": [r for r in history.elenco() if r.get("id") not in collegate],
        "priorita_assistita": revisioni.priorita_assistita(progetto),
        "aggiornamento_dovuto": revisioni.aggiornamento_dovuto(progetto),
        "wiki_statistiche": wiki.statistiche(progetto.get("wiki", {})),
        "wiki_obsoleta": wiki.obsoleta(progetto),
        "revisore_attivo": revisore_attivo,
        "record_screening_abstract": record_abstract,
        "record_screening_fulltext": record_fulltext,
        "pagina_abstract": pagina_abstract,
        "pagine_abstract": pagine_abstract,
        "pagina_fulltext": pagina_fulltext,
        "pagine_fulltext": pagine_fulltext,
    }


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
            ultime=history.elenco()[:5],
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
    lingua: str = Form(default=""),
    escludi_ritirati: bool = Form(default=False),
    solo_oa: bool = Form(default=False),
    con_pdf: bool = Form(default=False),
    rivista: str = Form(default=""),
    ateneo: str = Form(default=""),
    finanziatore: str = Form(default=""),
    campione: str = Form(default=""),
    seme: str = Form(default=""),
):
    strategy = strategy_from_form(
        label, terms, mesh, anno_da, anno_a, solo_articoli,
        lingua=lingua,
        escludi_ritirati=escludi_ritirati,
        solo_oa=solo_oa,
        con_pdf=con_pdf,
        rivista=rivista,
        ateneo=ateneo,
        finanziatore=finanziatore,
        campione=campione,
        seme=seme,
    )
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


@app.get("/autocompleta", response_class=HTMLResponse)
async def autocompleta(
    request: Request,
    entita: str = "keywords",
    q: str = "",
    modo: str = "opzioni",
    bersaglio: str = "",
):
    """Le opzioni di un `datalist`; un guasto non ferma la scrittura."""

    config = current_config()
    try:
        async with cache.client(headers={"User-Agent": search.USER_AGENT}) as http:
            voci = await openalex_api.autocompleta(entita, q, config, http)
    except (httpx.HTTPError, OSError):
        voci = []
    return templates.TemplateResponse(
        request,
        "partials/suggerimenti_parole.html" if modo == "pulsanti" else "partials/opzioni.html",
        {
            "request": request,
            "voci": voci,
            "valore_nome": entita in ("keywords", "topics"),
            "bersaglio": bersaglio,
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
    topic: str = Form(default=""),
    anno_da: str = Form(default=""),
    anno_a: str = Form(default=""),
    solo_articoli: bool = Form(default=False),
    lingua: str = Form(default=""),
    escludi_ritirati: bool = Form(default=False),
    solo_oa: bool = Form(default=False),
    con_pdf: bool = Form(default=False),
    rivista: str = Form(default=""),
    ateneo: str = Form(default=""),
    finanziatore: str = Form(default=""),
    campione: str = Form(default=""),
    seme: str = Form(default=""),
):
    config = current_config()
    strategy = strategy_from_form(
        label, terms, mesh, anno_da, anno_a, solo_articoli,
        lingua=lingua,
        escludi_ritirati=escludi_ritirati,
        solo_oa=solo_oa,
        con_pdf=con_pdf,
        rivista=rivista,
        ateneo=ateneo,
        finanziatore=finanziatore,
        campione=campione,
        seme=seme,
    )
    limite = max(1, min(limite, 200))

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

    risposta = templates.TemplateResponse(
        request,
        "partials/risultati.html",
        base_context(
            config,
            results=[],
            voce=history.voce(lavoro.risultato) or {},
            **contesto_elenco(lavoro.risultato, [], "tabella"),
        ),
    )
    # I risultati arrivano dentro la pagina della strategia, che non ha un
    # indirizzo suo: un aggiornamento del browser li faceva sparire. Da qui in
    # poi la barra indica la ricerca salvata, che si ricarica e si condivide.
    risposta.headers["HX-Push-Url"] = f"/cronologia/{lavoro.risultato}"
    return risposta


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


STATI_FILTRO = {"incluso", "forse", "escluso", "da_valutare"}


def _normalizza_testo_filtro(testo: str) -> str:
    decomposto = unicodedata.normalize("NFKD", testo.casefold())
    senza_accenti = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in senza_accenti).split())


def _filtra_risultati(
    works: list[Work],
    testo: str = "",
    anno_da: int | None = None,
    anno_a: int | None = None,
    fonte: str = "",
    stato: str = "",
) -> list[tuple[int, Work]]:
    """Filtra l'intero record conservando gli indici della cronologia."""

    parole = _normalizza_testo_filtro(testo).split()
    fonte = fonte.strip().casefold()
    stato = stato if stato in STATI_FILTRO else ""
    trovati = []
    for indice, work in enumerate(works):
        cercabile = _normalizza_testo_filtro(" ".join([
            work.title,
            *work.authors,
            work.venue or "",
            work.doi or "",
        ]))
        if parole and not all(parola in cercabile for parola in parole):
            continue
        if anno_da is not None and (work.year is None or work.year < anno_da):
            continue
        if anno_a is not None and (work.year is None or work.year > anno_a):
            continue
        if fonte and fonte not in {valore.casefold() for valore in work.sources}:
            continue
        if stato == "da_valutare" and work.decisione:
            continue
        if stato and stato != "da_valutare" and work.decisione != stato:
            continue
        trovati.append((indice, work))
    return trovati


def contesto_elenco(
    id_ricerca: str,
    campo,
    vista: str,
    pagina: int = 1,
    filtro_testo: str = "",
    filtro_anno_da: int | None = None,
    filtro_anno_a: int | None = None,
    filtro_fonte: str = "",
    filtro_stato: str = "",
) -> dict:
    """Tutto ciò che serve a disegnare un elenco di risultati, in un posto solo.

    Ci si arriva da tre strade — ricerca appena conclusa, cambio dei campi,
    ricerca riaperta dalla cronologia — e devono mostrare le stesse cose.
    """

    tutti = history.record(id_ricerca)
    voce = history.voce(id_ricerca) or {}
    filtro_testo = filtro_testo.strip()
    filtro_fonte = filtro_fonte.strip()
    filtro_stato = filtro_stato if filtro_stato in STATI_FILTRO else ""
    filtrati = _filtra_risultati(
        tutti,
        filtro_testo,
        filtro_anno_da,
        filtro_anno_a,
        filtro_fonte,
        filtro_stato,
    )
    pagine = max(1, -(-len(filtrati) // PER_PAGINA))
    pagina = min(max(1, pagina), pagine)
    inizio = (pagina - 1) * PER_PAGINA
    righe = filtrati[inizio : inizio + PER_PAGINA]
    return {
        "works": [work for _, work in righe],
        "righe": righe,
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
        "totale": len(filtrati),
        "totale_tutti": len(tutti),
        "fonti_filtro": sorted(
            {fonte for work in tutti for fonte in work.sources}, key=str.casefold
        ),
        "filtro_testo": filtro_testo,
        "filtro_anno_da": filtro_anno_da,
        "filtro_anno_a": filtro_anno_a,
        "filtro_fonte": filtro_fonte,
        "filtro_stato": filtro_stato,
        "filtri_attivi": bool(
            filtro_testo or filtro_anno_da is not None or filtro_anno_a is not None
            or filtro_fonte or filtro_stato
        ),
    }


def _elenco(
    request: Request,
    id_ricerca: str,
    campo: list[str],
    vista: str,
    pagina: int = 1,
    filtro_testo: str = "",
    filtro_anno_da: int | None = None,
    filtro_anno_a: int | None = None,
    filtro_fonte: str = "",
    filtro_stato: str = "",
):
    return templates.TemplateResponse(
        request,
        "partials/elenco.html",
        base_context(current_config(), **contesto_elenco(
            id_ricerca,
            campo,
            vista,
            pagina,
            filtro_testo,
            filtro_anno_da,
            filtro_anno_a,
            filtro_fonte,
            filtro_stato,
        )),
    )


def _indici_massa(works: list[Work], selezione: list[int], tutti: bool) -> list[int]:
    """Ambito esplicito e sicuro per ogni comando potenzialmente massivo."""

    if tutti:
        return list(range(len(works)))
    return list(dict.fromkeys(i for i in selezione if 0 <= i < len(works)))


def _avviso_ambito_massa(
    request: Request,
    id_ricerca: str,
    campo: list[str],
    vista: str,
    filtro_testo: str,
    filtro_anno_da: int | None,
    filtro_anno_a: int | None,
    filtro_fonte: str,
    filtro_stato: str,
):
    risposta = _elenco(
        request, id_ricerca, campo, vista,
        filtro_testo=filtro_testo,
        filtro_anno_da=filtro_anno_da,
        filtro_anno_a=filtro_anno_a,
        filtro_fonte=filtro_fonte,
        filtro_stato=filtro_stato,
    )
    return avvisa(
        risposta, i18n.strings(current_config().lang)["bulk_scope_required"]
    )


@app.post("/risultati/{id_ricerca}", response_class=HTMLResponse)
async def risultati(
    request: Request,
    id_ricerca: str,
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
    pagina: int = Form(default=1),
    filtro_testo: str = Form(default=""),
    filtro_anno_da: int | None = Form(default=None),
    filtro_anno_a: int | None = Form(default=None),
    filtro_fonte: str = Form(default=""),
    filtro_stato: str = Form(default=""),
    azzera_filtri: bool = Form(default=False),
):
    """Ridisegna l'elenco con i campi scelti, come tabella o come lista APA."""

    if azzera_filtri:
        filtro_testo = filtro_fonte = filtro_stato = ""
        filtro_anno_da = filtro_anno_a = None
    return _elenco(
        request,
        id_ricerca,
        campo,
        vista,
        pagina=pagina,
        filtro_testo=filtro_testo,
        filtro_anno_da=filtro_anno_da,
        filtro_anno_a=filtro_anno_a,
        filtro_fonte=filtro_fonte,
        filtro_stato=filtro_stato,
    )


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
    config = current_config()
    errore = None
    async with httpx.AsyncClient(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as client:
        if not await _scarica_con_ripiego(id_ricerca, indice, work, config, client):
            errore = i18n.strings(config.lang)["pdf_not_found"]
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


@app.get("/faccette/{id_ricerca}", response_class=HTMLResponse)
async def faccette_profilo(request: Request, id_ricerca: str):
    """Il profilo del campo per la strategia di questa ricerca."""

    config = current_config()
    voce = history.voce(id_ricerca) or {}
    query = next(
        (f.get("query", "") for f in voce.get("fonti", []) if f.get("id") == "openalex"),
        "",
    )
    if not query:
        return HTMLResponse("")
    async with cache.client(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as http:
        profilo = await faccette.profilo(
            query, history.filtri(id_ricerca), config, http
        )
    return templates.TemplateResponse(
        request, "partials/faccette.html", base_context(config, profilo=profilo)
    )


@app.get("/citazioni/{id_ricerca}/{indice}/{verso}", response_class=HTMLResponse)
async def citazioni_elenco(request: Request, id_ricerca: str, indice: int, verso: str):
    """I lavori intorno a questo: chi lo cita, chi cita lui, chi gli somiglia."""

    config = current_config()
    works = history.record(id_ricerca)
    if not works or indice >= len(works):
        return HTMLResponse("")
    t = i18n.strings(config.lang)
    trovati, problema = [], ""
    async with cache.client(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as http:
        try:
            trovati = await citazioni.cerca(works[indice], verso, config, http)
        except ValueError:
            problema = t["citazioni_senza_id"]
        except (httpx.HTTPError, OSError) as exc:
            problema = keywords.messaggio_api(exc.response) if isinstance(
                exc, httpx.HTTPStatusError
            ) else t["err_rete_fonte"]

    presenti = {(w.openalex_id or w.doi or w.title) for w in works}
    return templates.TemplateResponse(
        request,
        "partials/citazioni.html",
        base_context(
            config,
            id_ricerca=id_ricerca,
            indice=indice,
            verso=verso,
            trovati=[
                w for w in trovati
                if (w.openalex_id or w.doi or w.title) not in presenti
            ],
            problema=problema,
        ),
    )


@app.post("/citazioni/{id_ricerca}/{indice}/{verso}", response_class=HTMLResponse)
async def citazioni_aggiungi(
    request: Request,
    id_ricerca: str,
    indice: int,
    verso: str,
    scelti: list[str] = Form(default=[]),
):
    """Porta nella ricerca i record spuntati, in coda e con la provenienza."""

    config = current_config()
    if not scelti:
        return HTMLResponse("")
    async with cache.client(
        headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
    ) as http:
        nuovi = await citazioni.per_id(scelti, config, http)
    entrati = history.aggiungi(id_ricerca, nuovi, "citazioni")
    registro.annota(
        i18n.strings(config.lang)["log_citazioni_aggiunte"].format(quanti=entrati),
        f"{id_ricerca} · {verso}",
    )
    return _scheda(request, id_ricerca, indice)


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
            progetti_revisione=revisioni.elenco(),
        ),
    )


@app.post("/scheda/{id_ricerca}/{indice}/nota", response_class=HTMLResponse)
async def salva_nota_scheda(
    request: Request, id_ricerca: str, indice: int, nota: str = Form(default="")
):
    """L'appunto di chi legge, salvato accanto al record."""

    works = history.record(id_ricerca)
    if not 0 <= indice < len(works):
        return HTMLResponse("")
    testo = history.salva_nota(id_ricerca, indice, nota)
    work = history.record(id_ricerca)[indice]
    testi = i18n.strings(current_config().lang)
    risposta = templates.TemplateResponse(
        request,
        "partials/nota.html",
        base_context(
            current_config(), work=work, indice=indice, id_ricerca=id_ricerca
        ),
    )
    return avvisa(risposta, testi["note_saved"] if testo else testi["note_cleared"], "buono")


@app.post("/scheda/{id_ricerca}/{indice}/revisione", response_class=HTMLResponse)
async def aggiungi_scheda_a_revisione(
    request: Request,
    id_ricerca: str,
    indice: int,
    id_progetto: str = Form(...),
):
    """Porta questo record nel corpus di una review, senza collegare tutto."""

    testi = i18n.strings(current_config().lang)
    if revisioni.progetto(id_progetto) is None:
        return avvisa(_scheda(request, id_ricerca, indice), testi["review_add_record_missing"])
    aggiunto = revisioni.aggiungi_record(id_progetto, id_ricerca, indice)
    return avvisa(
        _scheda(request, id_ricerca, indice),
        testi["review_add_record_done"] if aggiunto else testi["review_add_record_already"],
        "buono" if aggiunto else "errore",
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
    aggiorna_elenco: bool = Form(default=False),
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
    filtro_testo: str = Form(default=""),
    filtro_anno_da: int | None = Form(default=None),
    filtro_anno_a: int | None = Form(default=None),
    filtro_fonte: str = Form(default=""),
    filtro_stato: str = Form(default=""),
):
    """Segna un record come incluso, forse o escluso. Ripetere annulla."""

    history.decide(id_ricerca, indice, stato, motivo)
    works = history.record(id_ricerca)
    if indice >= len(works):
        return HTMLResponse("")
    # L'elenco intero si ridisegna solo se la decisione cambia ciò che si vede:
    # un filtro per stato fa uscire il record, le colonne decisione e motivo lo
    # raccontano. Negli altri casi si scambia la sola cella, così il fuoco resta
    # sulla riga e le scorciatoie continuano a funzionare.
    if aggiorna_elenco and (filtro_stato or {"decisione", "motivo"} & set(campo)):
        risposta = _elenco(
            request, id_ricerca, campo, vista,
            filtro_testo=filtro_testo,
            filtro_anno_da=filtro_anno_da,
            filtro_anno_a=filtro_anno_a,
            filtro_fonte=filtro_fonte,
            filtro_stato=filtro_stato,
        )
        risposta.headers["HX-Retarget"] = f"#blocco-{id_ricerca}"
        risposta.headers["HX-Reswap"] = "outerHTML"
        return risposta
    return templates.TemplateResponse(
        request,
        "partials/screening.html",
        base_context(
            current_config(),
            work=works[indice],
            indice=indice,
            id_ricerca=id_ricerca,
            conteggi=history.conteggi(id_ricerca),
            aggiorna_elenco=aggiorna_elenco,
            vista=vista,
            filtro_stato=filtro_stato,
            fuori_banda=True,
        ),
    )


@app.post("/screening-massa/{id_ricerca}", response_class=HTMLResponse)
async def screening_massa(
    request: Request,
    id_ricerca: str,
    stato: str = Form(...),
    selezione: list[int] = Form(default=[]),
    tutti: bool = Form(default=False),
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
    filtro_testo: str = Form(default=""),
    filtro_anno_da: int | None = Form(default=None),
    filtro_anno_a: int | None = Form(default=None),
    filtro_fonte: str = Form(default=""),
    filtro_stato: str = Form(default=""),
):
    """Applica la stessa decisione a tutti i record spuntati."""

    works = history.record(id_ricerca)
    indici = _indici_massa(works, selezione, tutti)
    if not indici:
        return _avviso_ambito_massa(
            request, id_ricerca, campo, vista, filtro_testo, filtro_anno_da,
            filtro_anno_a, filtro_fonte, filtro_stato,
        )
    for indice in indici:
        decisione = history.decisioni(id_ricerca).get(str(indice), {})
        gia_deciso = decisione.get("stato", "")
        if stato == "annulla":
            if gia_deciso:
                history.decide(id_ricerca, indice, gia_deciso, decisione.get("motivo", ""))
        elif gia_deciso != stato:
            history.decide(id_ricerca, indice, stato, decisione.get("motivo", ""))
    return _elenco(
        request, id_ricerca, campo, vista,
        filtro_testo=filtro_testo,
        filtro_anno_da=filtro_anno_da,
        filtro_anno_a=filtro_anno_a,
        filtro_fonte=filtro_fonte,
        filtro_stato=filtro_stato,
    )


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
    tutti: bool = Form(default=False),
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
    filtro_testo: str = Form(default=""),
    filtro_anno_da: int | None = Form(default=None),
    filtro_anno_a: int | None = Form(default=None),
    filtro_fonte: str = Form(default=""),
    filtro_stato: str = Form(default=""),
):
    """Manda a Zotero i record spuntati, o tutti quando richiesto."""

    config = current_config()
    works = history.record(id_ricerca)
    indici = _indici_massa(works, selezione, tutti)
    if not indici:
        return _avviso_ambito_massa(
            request, id_ricerca, campo, vista, filtro_testo, filtro_anno_da,
            filtro_anno_a, filtro_fonte, filtro_stato,
        )
    da_inviare = [works[i] for i in indici]

    try:
        async with httpx.AsyncClient(headers={"User-Agent": search.USER_AGENT}) as client:
            esito = await zotero_client.invia(da_inviare, config, client)
        messaggio = i18n.strings(config.lang)["zotero_done"].format(**esito)
        registro.annota("Zotero", messaggio)
    except (zotero_client.ZoteroError, httpx.HTTPError, OSError) as exc:
        messaggio = i18n.strings(config.lang)["zotero_error"].format(errore=str(exc)[:160])
        registro.errore("Zotero", str(exc)[:200])
        return avvisa(_elenco(
            request, id_ricerca, campo, vista,
            filtro_testo=filtro_testo,
            filtro_anno_da=filtro_anno_da,
            filtro_anno_a=filtro_anno_a,
            filtro_fonte=filtro_fonte,
            filtro_stato=filtro_stato,
        ), messaggio)

    return avvisa(_elenco(
        request, id_ricerca, campo, vista,
        filtro_testo=filtro_testo,
        filtro_anno_da=filtro_anno_da,
        filtro_anno_a=filtro_anno_a,
        filtro_fonte=filtro_fonte,
        filtro_stato=filtro_stato,
    ), messaggio, "buono")


async def _scarica_con_ripiego(
    id_ricerca: str, indice: int, work: Work, config: Config, client: httpx.AsyncClient
) -> bool:
    """Scarica il PDF; se i collegamenti che abbiamo falliscono, ne chiede
    altri a Unpaywall e lascia l'archivio OpenAlex come ultima strada."""

    try:
        await pdf.scarica(work, client, prova_archivio=False)
        return True
    except (httpx.HTTPError, ValueError, OSError):
        pass

    nuove = []
    if config.mailto_valido and work.doi:
        altre = await unpaywall.altre_copie(work.doi, config, client)
        nuove = [u for u in altre if u not in work.candidati_pdf()]
        if nuove:
            work.oa_urls = work.oa_urls + nuove
            history.completa(id_ricerca, indice, {"oa_urls": work.oa_urls})
    try:
        await pdf.scarica(work, client)
        if nuove:
            registro.annota(
                i18n.strings(config.lang)["log_pdf_rescued"],
                f"{work.title[:60]} · {len(nuove)}",
            )
        return True
    except (httpx.HTTPError, ValueError, OSError) as exc:
        registro.errore(f"PDF non scaricato: {work.title[:60]}", str(exc)[:120])
        return False


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
    tutti: bool = Form(default=False),
    campo: list[str] = Form(default=[]),
    vista: str = Form(default="tabella"),
    filtro_testo: str = Form(default=""),
    filtro_anno_da: int | None = Form(default=None),
    filtro_anno_a: int | None = Form(default=None),
    filtro_fonte: str = Form(default=""),
    filtro_stato: str = Form(default=""),
):
    """Completa i record spuntati, o tutti quando richiesto, con Unpaywall."""

    config = current_config()
    etichette = i18n.strings(config.lang)
    works = history.record(id_ricerca)
    indici = _indici_massa(works, selezione, tutti)
    if not indici:
        return _avviso_ambito_massa(
            request, id_ricerca, campo, vista, filtro_testo, filtro_anno_da,
            filtro_anno_a, filtro_fonte, filtro_stato,
        )
    if not config.mailto_valido:
        return avvisa(_elenco(
            request, id_ricerca, campo, vista,
            filtro_testo=filtro_testo,
            filtro_anno_da=filtro_anno_da,
            filtro_anno_a=filtro_anno_a,
            filtro_fonte=filtro_fonte,
            filtro_stato=filtro_stato,
        ), etichette["unpaywall_no_email"])

    esito = await _completa_da_unpaywall(id_ricerca, indici, config)
    messaggio = etichette["unpaywall_done"].format(**esito)
    registro.annota("Unpaywall", messaggio)
    return avvisa(
        _elenco(
            request, id_ricerca, campo, vista,
            filtro_testo=filtro_testo,
            filtro_anno_da=filtro_anno_da,
            filtro_anno_a=filtro_anno_a,
            filtro_fonte=filtro_fonte,
            filtro_stato=filtro_stato,
        ),
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
    tutti: bool = Form(default=False),
    filtro_testo: str = Form(default=""),
    filtro_anno_da: int | None = Form(default=None),
    filtro_anno_a: int | None = Form(default=None),
    filtro_fonte: str = Form(default=""),
    filtro_stato: str = Form(default=""),
):
    """Scarica i PDF dei record spuntati, o di tutti quando richiesto."""

    works = history.record(id_ricerca)
    indici = _indici_massa(works, selezione, tutti)
    if not indici:
        return _avviso_ambito_massa(
            request, id_ricerca, campo, vista, filtro_testo, filtro_anno_da,
            filtro_anno_a, filtro_fonte, filtro_stato,
        )
    da_prendere = [(i, works[i]) for i in indici if works[i].oa_url and not pdf.gia_scaricato(works[i])]

    presi = falliti = 0
    if da_prendere:
        # Tre alla volta: piu' veloce di uno per uno, senza sembrare un raschiatore.
        cancello = asyncio.Semaphore(3)

        config = current_config()

        async def prendi(indice, work, client):
            async with cancello:
                return await _scarica_con_ripiego(id_ricerca, indice, work, config, client)

        async with httpx.AsyncClient(
            headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
        ) as client:
            esiti = await asyncio.gather(*(prendi(i, w, client) for i, w in da_prendere))
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
        _elenco(
            request, id_ricerca, campo, vista,
            filtro_testo=filtro_testo,
            filtro_anno_da=filtro_anno_da,
            filtro_anno_a=filtro_anno_a,
            filtro_fonte=filtro_fonte,
            filtro_stato=filtro_stato,
        ),
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


@app.get("/biblioteca/{nome}/file")
async def biblioteca_file(nome: str):
    """Il PDF trovato dalla ricerca a testo pieno, aperto nel lettore interno.

    Senza questa rotta la biblioteca sapeva dire in quale file stava la frase
    ma non sapeva mostrarlo.
    """

    percorso = biblioteca.percorso_pdf(nome)
    if percorso is None:
        return PlainTextResponse("PDF non trovato", status_code=404)
    return FileResponse(
        percorso,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{percorso.name}"'},
    )


@app.get("/esplora", response_class=HTMLResponse)
async def esplora(request: Request, tipo: str = "autori", q: str = ""):
    """Cerca autori o riviste OpenAlex senza avviare una revisione."""

    config = current_config()
    tipo = tipo if tipo in profili.TIPI else "autori"
    trovati, errore = [], ""
    if q.strip():
        try:
            async with cache.client(
                headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
            ) as client:
                trovati = await profili.cerca(tipo, q, config, client)
        except (httpx.HTTPError, OSError) as exc:
            errore = str(exc)[:160]
    return templates.TemplateResponse(
        request,
        "esplora.html",
        base_context(config, tipo=tipo, query=q, trovati=trovati, errore=errore),
    )


async def _pagina_profilo(request: Request, tipo: str, id_entita: str):
    config = current_config()
    try:
        async with cache.client(
            headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
        ) as client:
            profilo, opere = await profili.leggi(tipo, id_entita, config, client)
    except (ValueError, httpx.HTTPError, OSError):
        return RedirectResponse(f"/esplora?tipo={tipo}", status_code=303)
    return templates.TemplateResponse(
        request,
        "profilo.html",
        base_context(
            config,
            tipo=tipo,
            profilo=profilo,
            opere=opere,
            consultato=datetime.now().strftime("%Y-%m-%d"),
        ),
    )


@app.get("/autori/{id_entita}", response_class=HTMLResponse)
async def autore_pagina(request: Request, id_entita: str):
    return await _pagina_profilo(request, "autori", id_entita)


@app.get("/riviste/{id_entita}", response_class=HTMLResponse)
async def rivista_pagina(request: Request, id_entita: str):
    return await _pagina_profilo(request, "riviste", id_entita)


@app.get("/esplora/citanti/{id_lavoro}", response_class=HTMLResponse)
async def citanti_profilo(request: Request, id_lavoro: str):
    """Carica su richiesta gli articoli che citano un lavoro del profilo."""

    config = current_config()
    identificativo = citazioni.identificativo_lavoro(id_lavoro)
    if not identificativo:
        return HTMLResponse("", status_code=404)
    trovati, problema = [], ""
    try:
        async with cache.client(
            headers={"User-Agent": search.USER_AGENT}, follow_redirects=True
        ) as client:
            trovati = await citazioni.cerca(
                Work(title="", openalex_id=identificativo), "avanti", config, client, limite=8
            )
    except (ValueError, httpx.HTTPError, OSError):
        problema = i18n.strings(config.lang)["explore_error"]
    return templates.TemplateResponse(
        request,
        "partials/citanti_profilo.html",
        base_context(config, trovati=trovati, problema=problema),
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


@app.get("/revisioni", response_class=HTMLResponse)
async def revisioni_pagina(request: Request):
    return templates.TemplateResponse(
        request,
        "revisioni.html",
        base_context(current_config(), progetti=revisioni.elenco(), tipi=revisioni.TIPI),
    )


@app.post("/revisioni")
async def crea_revisione(
    titolo: str = Form(...),
    tipo: str = Form(default="sistematica"),
    revisori: str = Form(default=""),
):
    id_progetto = revisioni.crea(
        titolo,
        tipo,
        [nome.strip() for nome in revisori.split(",") if nome.strip()],
    )
    return RedirectResponse(f"/revisioni/{id_progetto}", status_code=303)


@app.get("/revisioni/{id_progetto}.md", response_class=PlainTextResponse)
async def esporta_revisione_markdown(id_progetto: str):
    progetto = revisioni.progetto(id_progetto)
    if progetto is None:
        return PlainTextResponse("", status_code=404)
    return PlainTextResponse(
        revisioni.esporta_markdown(progetto),
        headers={"Content-Disposition": 'attachment; filename="review-workspace.md"'},
    )


@app.get("/revisioni/{id_progetto}.json")
async def esporta_revisione_json(id_progetto: str):
    progetto = revisioni.progetto(id_progetto)
    if progetto is None:
        return Response(status_code=404)
    return Response(
        json.dumps(progetto, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="review-workspace.json"'},
    )


@app.get("/revisioni/{id_progetto}", response_class=HTMLResponse)
async def revisione_pagina(
    request: Request,
    id_progetto: str,
    revisore: str = "",
    pagina_abstract: int = 1,
    pagina_fulltext: int = 1,
):
    if revisioni.progetto(id_progetto) is None:
        return RedirectResponse("/revisioni", status_code=303)
    revisioni.allinea(id_progetto)
    return templates.TemplateResponse(
        request,
        "revisione.html",
        base_context(
            current_config(),
            **_contesto_revisione(
                id_progetto, revisore, pagina_abstract, pagina_fulltext
            ),
        ),
    )


FASI_DIFFERITE = ("estrazione", "qualita", "sintesi", "wiki", "aggiornamenti")


PER_PAGINA_FASE = 20


@app.get("/revisioni/{id_progetto}/fase/{nome}", response_class=HTMLResponse)
async def revisione_fase(
    request: Request, id_progetto: str, nome: str, revisore: str = "", pagina: int = 1
):
    """Una fase sola, chiesta quando arriva sullo schermo.

    Le fasi finali disegnano un modulo per ogni record incluso: tenerle tutte
    nella pagina significa costruire migliaia di campi che nessuno guarderà,
    e anche una sola fase va divisa in pagine quando gli inclusi sono molti.
    """

    if nome not in FASI_DIFFERITE or revisioni.progetto(id_progetto) is None:
        return Response(status_code=404)
    revisioni.allinea(id_progetto)
    contesto = _contesto_revisione(id_progetto, revisore)
    inclusi = contesto["record_inclusi"]
    pagine = max(1, -(-len(inclusi) // PER_PAGINA_FASE))
    pagina = min(max(1, pagina), pagine)
    inizio = (pagina - 1) * PER_PAGINA_FASE
    return templates.TemplateResponse(
        request,
        f"partials/revisione_{nome}.html",
        base_context(
            current_config(),
            nome_fase=nome,
            record_operativi=inclusi[inizio : inizio + PER_PAGINA_FASE],
            pagina_operativa=pagina,
            pagine_operative=pagine,
            **contesto,
        ),
    )


@app.post("/revisioni/{id_progetto}/rinomina")
async def rinomina_revisione(
    id_progetto: str, titolo: str = Form(...), revisore: str = Form(default="")
):
    """Il titolo del progetto, cambiato senza toccare il resto."""

    revisioni.rinomina(id_progetto, titolo)
    return RedirectResponse(
        f"/revisioni/{id_progetto}?revisore={quote(revisore)}", status_code=303
    )


@app.post("/revisioni/{id_progetto}/protocollo")
async def salva_protocollo_revisione(request: Request, id_progetto: str):
    modulo = await request.form()
    revisioni.salva_protocollo(
        id_progetto,
        {campo: modulo.get(campo, "") for campo in revisioni.CAMPI_PROTOCOLLO},
        str(modulo.get("motivo_emendamento", "")),
    )
    return RedirectResponse(f"/revisioni/{id_progetto}#protocollo", status_code=303)


@app.post("/revisioni/{id_progetto}/ricerche")
async def collega_ricerca_revisione(
    id_progetto: str,
    id_ricerca: str = Form(...),
):
    revisioni.collega_ricerca(id_progetto, id_ricerca)
    return RedirectResponse(f"/revisioni/{id_progetto}#ricerche", status_code=303)


@app.post("/revisioni/{id_progetto}/ricerche/{id_ricerca}/rimuovi")
async def scollega_ricerca_revisione(id_progetto: str, id_ricerca: str):
    revisioni.scollega_ricerca(id_progetto, id_ricerca)
    return RedirectResponse(f"/revisioni/{id_progetto}#ricerche", status_code=303)


@app.get("/revisioni/{id_progetto}/pdf/{id_item}")
async def apri_pdf_revisione(id_progetto: str, id_item: str):
    progetto = revisioni.progetto(id_progetto)
    if progetto is None:
        return PlainTextResponse("progetto inesistente", status_code=404)
    voce = next(
        (item for item in revisioni.lavori(progetto) if item.get("id") == id_item),
        None,
    )
    if voce is None:
        return PlainTextResponse("record inesistente", status_code=404)
    percorso = pdf.gia_scaricato(voce["work"])
    if percorso is None:
        return PlainTextResponse("PDF non ancora scaricato", status_code=404)
    return FileResponse(
        percorso,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{percorso.name}"'},
    )


def _esito_decisione_revisione(
    request: Request,
    id_progetto: str,
    id_item: str,
    fase: str,
    revisore: str,
    pagina_abstract: int,
    pagina_fulltext: int,
    avviso: str,
):
    """Il record appena giudicato, e nient'altro.

    Senza htmx si torna alla pagina intera, che resta la strada di riserva:
    con htmx si sostituisce la sola scheda toccata, perché ricostruire il
    workspace a ogni giudizio significa rifare protocollo, ricerche e liste
    per un dato che cambia in una riga.
    """

    ancora = "screening-abstract" if fase == "abstract" else "fulltext"
    if not request.headers.get("hx-request"):
        return RedirectResponse(
            f"/revisioni/{id_progetto}?revisore={quote(revisore)}"
            f"&pagina_abstract={pagina_abstract}&pagina_fulltext={pagina_fulltext}#{ancora}",
            status_code=303,
        )
    contesto = _contesto_revisione(
        id_progetto, revisore, pagina_abstract, pagina_fulltext
    )
    voce = next(
        (r for r in contesto["record_revisione"] if r.get("id") == id_item), None
    )
    if voce is None:
        return Response(status_code=404)
    risposta = templates.TemplateResponse(
        request,
        "partials/revisione_decisione.html",
        base_context(
            current_config(), item=voce, fase=fase, ancora=ancora, **contesto
        ),
    )
    return avvisa(risposta, avviso, "buono")


@app.post("/revisioni/{id_progetto}/nota/{id_item}", response_class=HTMLResponse)
async def nota_revisione(
    request: Request,
    id_progetto: str,
    id_item: str,
    nota: str = Form(default=""),
    fase: str = Form(default="abstract"),
):
    """L'appunto scritto dallo screening: finisce nella ricerca d'origine."""

    testi = i18n.strings(current_config().lang)
    scritto = revisioni.salva_nota(id_progetto, id_item, nota)
    contesto = _contesto_revisione(id_progetto)
    voce = next((r for r in contesto["record_revisione"] if r.get("id") == id_item), None)
    if voce is None:
        return Response(status_code=404)
    risposta = templates.TemplateResponse(
        request,
        "partials/revisione_nota.html",
        base_context(current_config(), item=voce, fase=fase, **contesto),
    )
    if not scritto:
        return avvisa(risposta, testi["note_no_source"])
    return avvisa(
        risposta, testi["note_saved"] if nota.strip() else testi["note_cleared"], "buono"
    )


@app.post("/revisioni/{id_progetto}/screening/{id_item}")
async def screening_revisione(
    request: Request,
    id_progetto: str,
    id_item: str,
    fase: str = Form(...),
    revisore: str = Form(...),
    stato: str = Form(...),
    motivo: str = Form(default=""),
    pagina_abstract: int = Form(default=1),
    pagina_fulltext: int = Form(default=1),
):
    revisioni.decidi(id_progetto, id_item, fase, revisore, stato, motivo)
    return _esito_decisione_revisione(
        request, id_progetto, id_item, fase, revisore,
        pagina_abstract, pagina_fulltext,
        i18n.strings(current_config().lang)["review_decision_saved"],
    )


@app.post("/revisioni/{id_progetto}/consenso/{id_item}")
async def consenso_revisione(
    request: Request,
    id_progetto: str,
    id_item: str,
    fase: str = Form(...),
    stato: str = Form(...),
    motivo: str = Form(default=""),
    revisore: str = Form(default=""),
    pagina_abstract: int = Form(default=1),
    pagina_fulltext: int = Form(default=1),
):
    revisioni.risolvi(id_progetto, id_item, fase, stato, motivo)
    return _esito_decisione_revisione(
        request, id_progetto, id_item, fase, revisore,
        pagina_abstract, pagina_fulltext,
        i18n.strings(current_config().lang)["review_consensus_saved"],
    )


@app.post("/revisioni/{id_progetto}/testo-completo/{id_item}")
async def testo_completo_revisione(
    request: Request,
    id_progetto: str,
    id_item: str,
    stato: str = Form(...),
    nota: str = Form(default=""),
    revisore: str = Form(default=""),
    pagina_abstract: int = Form(default=1),
    pagina_fulltext: int = Form(default=1),
):
    revisioni.salva_testo_completo(id_progetto, id_item, stato, nota)
    return _esito_decisione_revisione(
        request, id_progetto, id_item, "fulltext", revisore,
        pagina_abstract, pagina_fulltext,
        i18n.strings(current_config().lang)["review_fulltext_saved"],
    )


@app.post("/revisioni/{id_progetto}/report/{id_item}")
async def collega_report_revisione(
    id_progetto: str,
    id_item: str,
    id_studio: str = Form(...),
):
    revisioni.collega_report(id_progetto, id_item, id_studio)
    return RedirectResponse(f"/revisioni/{id_progetto}#estrazione", status_code=303)


@app.post("/revisioni/{id_progetto}/estrazione/{id_item}")
async def estrazione_revisione(request: Request, id_progetto: str, id_item: str):
    modulo = await request.form()
    revisore = str(modulo.get("revisore", ""))
    revisioni.salva_estrazione(
        id_progetto,
        id_item,
        revisore,
        {campo: modulo.get(campo, "") for campo in revisioni.CAMPI_ESTRAZIONE},
    )
    return RedirectResponse(
        f"/revisioni/{id_progetto}?revisore={quote(revisore)}#estrazione",
        status_code=303,
    )


@app.post("/revisioni/{id_progetto}/estrazione/{id_item}/consenso")
async def consenso_estrazione_revisione(request: Request, id_progetto: str, id_item: str):
    modulo = await request.form()
    revisioni.salva_consenso_estrazione(
        id_progetto,
        id_item,
        {campo: modulo.get(campo, "") for campo in revisioni.CAMPI_ESTRAZIONE},
    )
    return RedirectResponse(f"/revisioni/{id_progetto}#estrazione", status_code=303)


@app.post("/revisioni/{id_progetto}/bias/{id_item}")
async def bias_revisione(request: Request, id_progetto: str, id_item: str):
    modulo = await request.form()
    revisioni.salva_bias(
        id_progetto,
        id_item,
        {campo: modulo.get(campo, "") for campo in revisioni.CAMPI_BIAS},
    )
    return RedirectResponse(f"/revisioni/{id_progetto}#qualita", status_code=303)


@app.post("/revisioni/{id_progetto}/evidenze")
async def evidenza_revisione(request: Request, id_progetto: str):
    modulo = await request.form()
    revisioni.salva_evidenza(
        id_progetto,
        {campo: modulo.get(campo, "") for campo in revisioni.CAMPI_EVIDENZA},
    )
    return RedirectResponse(f"/revisioni/{id_progetto}#sintesi", status_code=303)


@app.post("/revisioni/{id_progetto}/evidenze/{id_evidenza}/elimina")
async def elimina_evidenza_revisione(id_progetto: str, id_evidenza: str):
    revisioni.elimina_evidenza(id_progetto, id_evidenza)
    return RedirectResponse(f"/revisioni/{id_progetto}#sintesi", status_code=303)


@app.post("/revisioni/{id_progetto}/aggiornamenti")
async def registra_aggiornamento_revisione(
    id_progetto: str,
    nuovi: int = Form(default=0),
    modificati: int = Form(default=0),
    ritirati: int = Form(default=0),
    nota: str = Form(default=""),
):
    revisioni.registra_aggiornamento(id_progetto, nuovi, modificati, ritirati, nota)
    return RedirectResponse(f"/revisioni/{id_progetto}#aggiornamenti", status_code=303)


async def _genera_wiki_revisione(id_progetto: str) -> dict:
    """Compila la base certa e, se configurato, la arricchisce lotto per lotto."""

    progetto = revisioni.progetto(id_progetto) or {}
    base = wiki.crea_base(progetto)
    documenti = wiki.documenti_per_llm(progetto)
    config = current_config()
    risultati, errori = [], []
    if config.llm_enabled:
        for inizio in range(0, len(documenti), 12):
            try:
                risultati.append(
                    await LLMClient(config).wiki_graph(
                        documenti[inizio : inizio + 12], config.lang
                    )
                )
            except (LLMError, httpx.HTTPError, OSError) as exc:
                errori.append(str(exc)[:180])
        if risultati:
            base = wiki.arricchisci(base, risultati, documenti, config.llm_model)
    if errori:
        base["errore_llm"] = errori[0]
    revisioni.salva_wiki(id_progetto, base)
    return {
        **wiki.statistiche(base),
        "llm_usato": base.get("llm_usato", False),
        "errore_llm": bool(errori),
    }


@app.post("/revisioni/{id_progetto}/wiki/genera", response_class=HTMLResponse)
async def avvia_wiki_revisione(request: Request, id_progetto: str):
    descrizione = f"review-wiki:{id_progetto}"
    lavoro = lavori.per_descrizione(descrizione) or lavori.avvia(
        _genera_wiki_revisione(id_progetto), descrizione
    )
    return templates.TemplateResponse(
        request,
        "partials/revisione_wiki_lavoro.html",
        base_context(current_config(), lavoro=lavoro, id_progetto=id_progetto),
    )


@app.get("/revisioni-wiki-lavoro/{id_lavoro}", response_class=HTMLResponse)
async def stato_wiki_revisione(request: Request, id_lavoro: str):
    lavoro = lavori.prendi(id_lavoro)
    if lavoro is None:
        return HTMLResponse("")
    id_progetto = lavoro.descrizione.removeprefix("review-wiki:")
    return templates.TemplateResponse(
        request,
        "partials/revisione_wiki_lavoro.html",
        base_context(current_config(), lavoro=lavoro, id_progetto=id_progetto),
    )


@app.get("/revisioni/{id_progetto}/wiki", response_class=HTMLResponse)
async def wiki_revisione_pagina(request: Request, id_progetto: str):
    progetto = revisioni.progetto(id_progetto)
    if progetto is None:
        return RedirectResponse("/revisioni", status_code=303)
    artefatto = progetto.get("wiki", {})
    return templates.TemplateResponse(
        request,
        "revisione_wiki.html",
        base_context(
            current_config(), progetto=progetto, wiki=artefatto,
            wiki_statistiche=wiki.statistiche(artefatto),
            wiki_obsoleta=wiki.obsoleta(progetto),
            titoli_fonti={
                voce.get("id", ""): voce.get("record", {}).get("title", "")
                for voce in progetto.get("record", [])
            },
        ),
    )


async def _aggiorna_revisione(id_progetto: str) -> dict:
    """Riesegue le ricerche originarie e integra soltanto le differenze."""

    progetto = revisioni.progetto(id_progetto) or {}
    originali, visti = [], set()
    for collegata in progetto.get("ricerche", []):
        id_ricerca = collegata.get("id", "")
        if collegata.get("aggiornamento") or not id_ricerca or id_ricerca in visti:
            continue
        visti.add(id_ricerca)
        originali.append(id_ricerca)

    totale = {"nuovi": 0, "modificati": 0, "ritirati": 0, "esecuzioni": 0}
    config = current_config()
    for id_ricerca in originali:
        voce = history.voce(id_ricerca)
        if not voce:
            continue
        strategia = history.strategia(id_ricerca)
        strategia.filtri = history.filtri(id_ricerca)
        fonti = [
            fonte.get("id", "") for fonte in voce.get("fonti", [])
            if fonte.get("id") in sources_registry.BY_ID
            and sources_registry.BY_ID[fonte.get("id")].executable
        ]
        limite = max(
            [min(200, max(25, int(fonte.get("trovati", 0) or 0))) for fonte in voce.get("fonti", [])]
            or [50]
        )
        risultati, nuovi_lavori = await search.run(strategia, fonti, limite, config)
        id_esecuzione = history.salva(
            f"{voce.get('topic', '')} — aggiornamento",
            strategia,
            risultati,
            nuovi_lavori,
        )
        esito = revisioni.integra_aggiornamento(id_progetto, id_esecuzione, nuovi_lavori)
        for campo in ("nuovi", "modificati", "ritirati"):
            totale[campo] += esito[campo]
        totale["esecuzioni"] += 1
    if not originali:
        revisioni.registra_aggiornamento(
            id_progetto, 0, nota="Nessuna ricerca collegata da rieseguire"
        )
    return totale


@app.post("/revisioni/{id_progetto}/aggiorna", response_class=HTMLResponse)
async def avvia_aggiornamento_revisione(request: Request, id_progetto: str):
    descrizione = f"living-review:{id_progetto}"
    lavoro = lavori.per_descrizione(descrizione) or lavori.avvia(
        _aggiorna_revisione(id_progetto), descrizione
    )
    return templates.TemplateResponse(
        request,
        "partials/revisione_aggiornamento_lavoro.html",
        base_context(current_config(), lavoro=lavoro, id_progetto=id_progetto),
    )


@app.get("/revisioni-lavoro/{id_lavoro}", response_class=HTMLResponse)
async def stato_aggiornamento_revisione(request: Request, id_lavoro: str):
    lavoro = lavori.prendi(id_lavoro)
    if lavoro is None:
        return HTMLResponse("")
    id_progetto = lavoro.descrizione.removeprefix("living-review:")
    return templates.TemplateResponse(
        request,
        "partials/revisione_aggiornamento_lavoro.html",
        base_context(current_config(), lavoro=lavoro, id_progetto=id_progetto),
    )


@app.post("/revisioni/{id_progetto}/elimina")
async def elimina_revisione(id_progetto: str):
    revisioni.elimina(id_progetto)
    return RedirectResponse("/revisioni", status_code=303)


PER_PAGINA_CRONOLOGIA = 25


@app.get("/cronologia", response_class=HTMLResponse)
async def cronologia(request: Request, q: str = "", pagina: int = 1):
    """Le ricerche salvate, cercabili per argomento e divise in pagine.

    Dopo qualche mese l'elenco intero non si legge più: il filtro corre
    sull'argomento con le stesse regole dei record — maiuscole e accenti non
    contano — e le pagine tengono corta la tabella.
    """

    tutte = history.elenco()
    q = q.strip()
    parole = _normalizza_testo_filtro(q).split()
    voci = [
        voce for voce in tutte
        if all(
            parola in _normalizza_testo_filtro(voce.get("topic") or "")
            for parola in parole
        )
    ]
    pagine = max(1, -(-len(voci) // PER_PAGINA_CRONOLOGIA))
    pagina = min(max(1, pagina), pagine)
    inizio = (pagina - 1) * PER_PAGINA_CRONOLOGIA
    return templates.TemplateResponse(
        request,
        "cronologia.html",
        base_context(
            current_config(),
            voci=voci[inizio : inizio + PER_PAGINA_CRONOLOGIA],
            query=q,
            totale=len(voci),
            totale_tutte=len(tutte),
            pagina=pagina,
            pagine=pagine,
        ),
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


@app.get("/cronologia/{id_ricerca}/riesegui", response_class=HTMLResponse)
async def riesegui_ricerca(request: Request, id_ricerca: str):
    """Riapre la strategia di una ricerca salvata, pronta da rilanciare.

    La strategia è già negli archivi: senza questa strada andava riscritta a
    mano, argomento e blocchi compresi, per rifare la stessa interrogazione
    qualche mese dopo.
    """

    voce = history.voce(id_ricerca)
    if voce is None:
        return RedirectResponse("/cronologia", status_code=303)
    config = current_config()
    strategy = history.strategia(id_ricerca)
    strategy.filtri = history.filtri(id_ricerca)
    topic = voce.get("topic", "")
    fonti_salvate = [f.get("id") for f in voce.get("fonti", []) if f.get("id")]
    return templates.TemplateResponse(
        request,
        "index.html",
        base_context(
            config,
            sources=sources_registry.executable(),
            copy_only=sources_registry.copy_only(),
            selected=fonti_salvate or sources_registry.DEFAULT_SELECTED,
            llm_enabled=config.llm_enabled,
            ultime=history.elenco()[:5],
            topic=topic,
            strategy=strategy,
            queries=search.queries_for(strategy),
            limite_predefinito=macchina.limite_consigliato(),
            suggestions=Suggestions(
                topic=topic,
                mesh=list(strategy.mesh),
                notes=[
                    i18n.strings(config.lang)["rerun_note"].format(
                        quando=voce.get("quando", "").replace("T", " ")
                    )
                ],
            ),
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
    config = current_config()
    return templates.TemplateResponse(
        request,
        "impostazioni.html",
        base_context(
            config,
            presets=PRESETS,
            salvato=bool(salvato),
            diagnosi=diagnostica.dati(),
            percorso=config_module.CONFIG_FILE,
            sources=sources_registry.ALL,
            credito_speso=costo.speso(),
            credito_resta=costo.resta(config),
            credito_budget=costo.budget(config),
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
    openalex_contenuti: str = Form(default=""),
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
    config.openalex_contenuti = openalex_contenuti.strip()

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
