"""Costruzione della strategia e resa nella sintassi dei motori."""

from __future__ import annotations

from .i18n import strings
from .keywords import words_of
from .models import Block, Filtri, Strategy, Suggestions


def or_group(terms: list[str], term_fmt: str = '"{term}"') -> str:
    return " OR ".join(term_fmt.format(term=t) for t in terms)


def render(strategy: Strategy, term_fmt: str = '"{term}"') -> str:
    """Blocchi in AND, termini in OR dentro ciascun blocco."""

    groups = [or_group(b.clean_terms(), term_fmt) for b in strategy.non_empty_blocks()]
    if not groups:
        return ""
    if len(groups) == 1:
        return f"({groups[0]})"
    return " AND ".join(f"({g})" for g in groups)


def flat_terms(strategy: Strategy, limit: int = 8) -> str:
    """Per i motori senza operatori booleani: i termini piu' rilevanti."""

    terms: list[str] = []
    for block in strategy.non_empty_blocks():
        for term in block.clean_terms():
            if term not in terms:
                terms.append(term)
    return " ".join(terms[:limit])


def heuristic_strategy(suggestions: Suggestions, lang: str | None = None) -> Strategy:
    """Strategia costruita senza LLM, solo dai dati raccolti."""

    topic = suggestions.topic.strip()
    primary = topic_seed(topic)
    for name, score in suggestions.concepts:
        if score >= 0.35 and name.lower() != topic.lower() and len(primary) < 6:
            primary.append(name)

    topic_words = set(words_of(topic))
    used = {t.lower() for t in primary} | topic_words
    related = []
    for term, _count in suggestions.cooccurring:
        words = set(words_of(term))
        # un termine fatto solo di parole del topic non aggiunge nulla
        if term.lower() in used or (words and words <= topic_words):
            continue
        related.append(term)
        used.add(term.lower())
        if len(related) == 6:
            break

    t = strings(lang)
    blocks = [Block(t["block_main"], primary)]
    if related:
        blocks.append(Block(t["block_related"], related))
    return Strategy(blocks=blocks, mesh=list(suggestions.mesh))


def topic_seed(topic: str, max_words: int = 3) -> list[str]:
    """Il topic diventa termini di ricerca.

    Una frase lunga cercata alla lettera non trova nulla: oltre le tre
    parole significative il topic si scompone nelle sue parole.
    """

    topic = topic.strip()
    if not topic:
        return []
    words = words_of(topic)
    if len(words) <= max_words:
        return [topic]
    return words[:5]


def strategy_from_form(
    labels: list[str],
    term_lines: list[str],
    mesh: str = "",
    anno_da: str = "",
    anno_a: str = "",
    solo_articoli: bool = False,
) -> Strategy:
    """Ricostruisce la strategia dai campi di testo della pagina."""

    blocks = []
    for label, line in zip(labels, term_lines):
        terms = [t.strip() for t in line.replace("\n", ",").split(",") if t.strip()]
        if terms:
            blocks.append(Block(label.strip() or "Blocco", terms))
    mesh_terms = [t.strip() for t in mesh.replace("\n", ",").split(",") if t.strip()]
    return Strategy(
        blocks=blocks,
        mesh=mesh_terms,
        filtri=Filtri(
            anno_da=_anno(anno_da),
            anno_a=_anno(anno_a),
            solo_articoli=bool(solo_articoli),
        ),
    )


def _anno(valore: str) -> int | None:
    valore = str(valore).strip()
    return int(valore) if valore.isdigit() and 1000 <= int(valore) <= 2999 else None
