"""Motori senza API aperta: l'app produce solo la stringa da incollare."""

from __future__ import annotations

from ..models import Strategy
from ..strategy import render
from .base import Source


class Scopus(Source):
    id = "scopus"
    label = "Scopus"
    homepage = "https://www.scopus.com"
    executable = False

    def render_query(self, strategy: Strategy) -> str:
        inner = render(strategy)
        if not inner:
            return ""
        query = f"TITLE-ABS-KEY({inner})"
        filtri = strategy.filtri
        if filtri.anno_da:
            query += f" AND PUBYEAR > {filtri.anno_da - 1}"
        if filtri.anno_a:
            query += f" AND PUBYEAR < {filtri.anno_a + 1}"
        if filtri.solo_articoli:
            query += " AND DOCTYPE(ar)"
        return query


class WebOfScience(Source):
    id = "wos"
    label = "Web of Science"
    homepage = "https://www.webofscience.com"
    executable = False

    def render_query(self, strategy: Strategy) -> str:
        inner = render(strategy)
        if not inner:
            return ""
        query = f"TS=({inner})"
        filtri = strategy.filtri
        if filtri.anno_da or filtri.anno_a:
            query += f" AND PY=({filtri.anno_da or 1800}-{filtri.anno_a or 3000})"
        if filtri.solo_articoli:
            query += " AND DT=(Article)"
        return query
