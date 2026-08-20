"""L'unico punto da cui l'applicazione parla con OpenAlex.

Chiave, email di cortesia, timeout e contabilità del costo stanno scritti qui
una volta sola: le funzioni che si appoggiano a OpenAlex — la fonte, i
suggerimenti, le citazioni, le faccette — non li riscrivono ognuna a modo suo.
"""

from __future__ import annotations

from contextvars import ContextVar

import httpx

from . import cache, costo
from .config import Config

API = "https://api.openalex.org"
CONTENUTI = "https://content.openalex.org"

# L'interrogazione riscritta da OpenAlex nel suo linguaggio, per il compito in
# corso. Non un attributo della fonte: nel registro le fonti sono istanze
# uniche e due ricerche avviate insieme si sovrascriverebbero il valore.
# `asyncio.gather` dà a ogni compito la sua copia del contesto, quindi qui
# ognuno legge il proprio.
ULTIMA_OQL: ContextVar[str] = ContextVar("ultima_oql", default="")


def parametri(config: Config, **extra) -> dict[str, str]:
    """I parametri della chiamata, senza i vuoti: OpenAlex rifiuta con `400`
    un `search=` senza contenuto e un `mailto` malformato."""

    params = {chiave: str(valore) for chiave, valore in extra.items() if valore not in ("", None)}
    if config.mailto_valido:
        params["mailto"] = config.mailto_valido
    if config.openalex_api_key:
        params["api_key"] = config.openalex_api_key
    return params


async def chiama(
    client: httpx.AsyncClient,
    percorso: str,
    config: Config,
    timeout: float = 25,
    **extra,
) -> dict:
    """Una GET su OpenAlex, con la spesa annotata nel registro del giorno.

    Le risposte che arrivano dalla cache portano il marcatore e non si
    contano: la stessa query ripetuta mentre si affina una strategia si paga
    una volta sola.
    """

    risposta = await client.get(
        f"{API}{percorso}", params=parametri(config, **extra), timeout=timeout
    )
    risposta.raise_for_status()
    corpo = risposta.json()
    if not risposta.headers.get(cache.INTESTAZIONE):
        speso = (corpo.get("meta") or {}).get("cost_usd") or 0.0
        costo.aggiungi(float(speso))
    scritta = oql(corpo)
    if scritta:
        ULTIMA_OQL.set(scritta)
    return corpo


async def contenuto_pdf(work_id: str, config: Config, client: httpx.AsyncClient) -> bytes:
    """Il PDF dall'archivio di OpenAlex: $0.01 a file, chiave obbligatoria.

    Il corpo non dichiara la spesa come fa l'API dei metadati, quindi il
    costo si annota qui a listino.
    """

    if not config.openalex_api_key:
        raise ValueError("l'archivio OpenAlex vuole la chiave")
    risposta = await client.get(
        f"{CONTENUTI}/works/{work_id}.pdf",
        params={"api_key": config.openalex_api_key},
        timeout=120,
        follow_redirects=True,
    )
    risposta.raise_for_status()
    costo.aggiungi(costo.COSTO_PDF)
    return risposta.content


def id_breve(valore: str | None) -> str:
    """`https://openalex.org/W123` → `W123`: il filtro vuole la forma corta."""

    return str(valore or "").rstrip("/").rsplit("/", 1)[-1]


def abstract_da_indice(indice: dict | None) -> str | None:
    """OpenAlex consegna l'abstract smontato in parola → posizioni.

    Rimontarlo non costa una chiamata in più e riempie una scheda che
    altrimenti resta muta.
    """

    if not indice:
        return None
    posizioni: list[tuple[int, str]] = []
    for parola, dove in indice.items():
        posizioni.extend((posto, parola) for posto in dove or [])
    if not posizioni:
        return None
    posizioni.sort()
    return " ".join(parola for _, parola in posizioni) or None


def oql(corpo: dict) -> str:
    """La query riscritta da OpenAlex nel suo linguaggio: la strategia
    riproducibile che una revisione deve poter pubblicare."""

    return str((((corpo.get("meta") or {}).get("x_query")) or {}).get("oql") or "")
