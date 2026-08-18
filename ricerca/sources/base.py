"""Interfaccia comune a tutte le fonti."""

from __future__ import annotations

import httpx

from ..config import Config
from ..models import Strategy, Work
from ..strategy import render


class Source:
    id: str = ""
    label: str = ""
    homepage: str = ""
    # Le fonti non eseguibili producono solo la stringa da incollare altrove.
    executable: bool = True
    key_field: str = ""
    key_hint: str = ""

    def render_query(self, strategy: Strategy) -> str:
        return render(strategy)

    def unavailable_reason(self, config: Config) -> str | None:
        if self.key_field and not getattr(config, self.key_field, ""):
            return self.key_hint or "richiede una chiave API"
        return None

    async def search(
        self, client: httpx.AsyncClient, query: str, limit: int, config: Config
    ) -> list[Work]:
        raise NotImplementedError


def clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
