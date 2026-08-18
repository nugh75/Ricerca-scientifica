"""Tipi di dato condivisi da tutta l'applicazione."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """Un blocco concettuale: i termini sono in OR fra loro."""

    label: str
    terms: list[str]

    def clean_terms(self) -> list[str]:
        return [t.strip() for t in self.terms if t and t.strip()]


@dataclass
class Strategy:
    """Blocchi in AND fra loro; `mesh` sono i termini controllati PubMed."""

    blocks: list[Block] = field(default_factory=list)
    mesh: list[str] = field(default_factory=list)

    def non_empty_blocks(self) -> list[Block]:
        return [b for b in self.blocks if b.clean_terms()]

    def is_empty(self) -> bool:
        return not self.non_empty_blocks()


@dataclass
class Work:
    """Un risultato bibliografico, normalizzato fra le fonti."""

    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    venue: str | None = None
    url: str | None = None
    abstract: str | None = None
    oa_url: str | None = None
    sources: list[str] = field(default_factory=list)

    @property
    def authors_short(self) -> str:
        if not self.authors:
            return ""
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."


@dataclass
class SourceResult:
    """Esito dell'interrogazione di una singola fonte."""

    source_id: str
    label: str
    query: str
    works: list[Work] = field(default_factory=list)
    error: str | None = None


@dataclass
class Suggestions:
    """Materiale grezzo raccolto per un topic, prima della strategia."""

    topic: str
    concepts: list[tuple[str, float]] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    mesh: list[str] = field(default_factory=list)
    cooccurring: list[tuple[str, int]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    llm_used: bool = False
