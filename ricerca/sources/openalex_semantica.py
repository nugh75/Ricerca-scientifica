"""OpenAlex che cerca per significato invece che per parole.

`search.semantic` confronta il testo della domanda con l'abstract dei lavori
in uno spazio vettoriale: trova chi dice la stessa cosa con altre parole, che
è esattamente quello che una strategia booleana si lascia sfuggire. In cambio
restituisce al massimo cinquanta record e costa dieci volte un filtro, quindi
sta accanto alle altre fonti ma spenta finché non la si accende.
"""

from __future__ import annotations

import httpx

from .. import openalex_api
from ..config import Config
from ..i18n import strings
from ..models import Strategy
from ..strategy import flat_terms
from .base import Source
from .openalex import SELECT, filtro_vincoli, work_da

MASSIMO = 50          # il tetto dell'endpoint, non una scelta nostra


class OpenAlexSemantica(Source):
    id = "openalex_semantica"
    label = "OpenAlex · significato"
    homepage = "https://openalex.org"

    def render_query(self, strategy: Strategy) -> str:
        """Qui i booleani non servono: conta il testo, più lungo è meglio è."""

        return flat_terms(strategy, limit=40)

    def avviso(self, config: Config, lang: str | None = None) -> str | None:
        return strings(lang)["semantica_avviso"]

    async def search(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        config: Config,
        filtri=None,
    ):
        corpo = await openalex_api.chiama(
            client,
            "/works",
            config,
            **{"search.semantic": query},
            filter=",".join(filtro_vincoli(filtri)),
            per_page=str(min(limit, MASSIMO)),
            select=SELECT,
        )
        works = [work_da(item) for item in corpo.get("results", [])]
        for work in works:
            work.sources = [self.id]
        return works
