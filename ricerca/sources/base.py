"""Interfaccia comune a tutte le fonti."""

from __future__ import annotations

import httpx

from ..config import Config
from ..i18n import strings
from ..models import Filtri, Strategy, Work
from ..strategy import render


class Source:
    id: str = ""
    label: str = ""
    homepage: str = ""
    # Le fonti non eseguibili producono solo la stringa da incollare altrove.
    executable: bool = True
    key_field: str = ""
    key_hint_key: str = "needs_key"

    def render_query(self, strategy: Strategy) -> str:
        return render(strategy) + self.render_filtri(strategy)

    def render_filtri(self, strategy: Strategy) -> str:
        """Coda da aggiungere alla query: ogni fonte ha la sua sintassi."""

        return ""

    def unavailable_reason(self, config: Config, lang: str | None = None) -> str | None:
        if self.key_field and not getattr(config, self.key_field, ""):
            return strings(lang)[self.key_hint_key]
        return None

    def avviso(self, config: Config, lang: str | None = None) -> str | None:
        """Limite noto di una fonte che funziona lo stesso."""

        return None

    async def search(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        config: Config,
        filtri: Filtri | None = None,
    ) -> list[Work]:
        raise NotImplementedError


def clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
