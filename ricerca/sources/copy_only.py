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
        return f"TITLE-ABS-KEY({inner})" if inner else ""


class WebOfScience(Source):
    id = "wos"
    label = "Web of Science"
    homepage = "https://www.webofscience.com"
    executable = False

    def render_query(self, strategy: Strategy) -> str:
        inner = render(strategy)
        return f"TS=({inner})" if inner else ""
