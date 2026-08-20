"""Registro delle fonti."""

from __future__ import annotations

from .arxiv import Arxiv
from .base import Source
from .copy_only import Scopus, WebOfScience
from .core import Core
from .crossref import Crossref
from .doaj import Doaj
from .europepmc import EuropePMC
from .opac_sbn import OpacSbn
from .openalex import OpenAlex
from .openalex_semantica import OpenAlexSemantica
from .pubmed import PubMed
from .semantic_scholar import SemanticScholar

ALL: list[Source] = [
    OpenAlex(),
    OpenAlexSemantica(),
    Crossref(),
    PubMed(),
    EuropePMC(),
    Arxiv(),
    Doaj(),
    SemanticScholar(),
    Core(),
    OpacSbn(),
    Scopus(),
    WebOfScience(),
]

BY_ID: dict[str, Source] = {source.id: source for source in ALL}

DEFAULT_SELECTED = ["openalex", "crossref", "pubmed", "europepmc", "arxiv", "doaj"]


def executable() -> list[Source]:
    return [s for s in ALL if s.executable]


def copy_only() -> list[Source]:
    return [s for s in ALL if not s.executable]


__all__ = ["ALL", "BY_ID", "DEFAULT_SELECTED", "Source", "executable", "copy_only"]
