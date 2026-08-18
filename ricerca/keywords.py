"""Estrazione dei termini per un topic dalle banche dati.

Tre fonti indipendenti: i concetti di OpenAlex, i termini controllati MeSH
ricavati dalla traduzione automatica di PubMed, e i termini che ricorrono
nei titoli dei primi risultati. Il fallimento di una non blocca le altre.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter

import httpx

from .config import Config
from .i18n import strings
from .models import Suggestions

OPENALEX = "https://api.openalex.org"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

STOPWORDS = {
    # inglese
    "the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "with", "from",
    "by", "at", "as", "is", "are", "was", "were", "be", "been", "this", "that",
    "these", "those", "its", "it", "their", "we", "our", "study", "review",
    "analysis", "using", "based", "case", "new", "among", "into", "between",
    "effect", "effects", "role", "toward", "towards", "use", "used", "research",
    "paper", "article", "approach", "results", "evidence", "systematic",
    # italiano
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "del", "della",
    "dei", "delle", "degli", "e", "ed", "o", "in", "nel", "nella", "nei", "negli",
    "nelle", "per", "con", "su", "sul", "sulla", "sui", "sugli", "sulle", "da",
    "dal", "dalla", "dai", "dagli", "dalle", "al", "alla", "agli", "alle",
    # "ai" resta fuori dalle stopword: e' l'acronimo di artificial intelligence
    "che", "come", "non", "piu", "tra", "fra", "anche", "ogni", "loro", "suo",
    "uno", "studio", "analisi", "ricerca", "questo", "questa", "sono", "essere",
    # frammenti che restano dopo l'elisione (dell', nell', un', quest')
    "dell", "nell", "sull", "all", "dal", "dall", "quell", "quest", "coll",
}

_WORD = re.compile(r"[a-zà-ÿ][a-zà-ÿ\-]{1,}")
_APOSTROPHE = re.compile(r"['\u2019]")
_MESH = re.compile(r'"([^"]+)"\[MeSH Terms\]')


async def gather(topic: str, client: httpx.AsyncClient, config: Config) -> Suggestions:
    """Raccoglie concetti, MeSH e co-occorrenze in parallelo."""

    suggestions = Suggestions(topic=topic.strip())
    concepts, topics, mesh, cooccurring = await asyncio.gather(
        _retry(_openalex_concepts, topic, client, config),
        _retry(_openalex_topics, topic, client, config),
        _retry(_pubmed_mesh, topic, client, config),
        _retry(_cooccurring_terms, topic, client, config),
        return_exceptions=True,
    )
    t = strings(config.lang)
    mesh_failed = False
    for key, value, target in (
        ("label_concepts", concepts, "concepts"),
        ("label_topics", topics, "topics"),
        ("label_mesh", mesh, "mesh"),
        ("label_cooccurring", cooccurring, "cooccurring"),
    ):
        if isinstance(value, Exception):
            mesh_failed = mesh_failed or target == "mesh"
            suggestions.notes.append(
                t["note_unavailable"].format(label=t[key], error=_short(value, t))
            )
        else:
            setattr(suggestions, target, value)
    if not suggestions.mesh and not mesh_failed:
        suggestions.notes.append(t["mesh_missing"])
    return suggestions


async def _retry(fetch, topic: str, client: httpx.AsyncClient, config: Config, attempts: int = 3):
    """Un secondo tentativo dopo una pausa: 429 e cadute di rete sono frequenti."""

    for attempt in range(1, attempts + 1):
        try:
            return await fetch(topic, client, config)
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            recuperabile = isinstance(exc, httpx.TransportError) or exc.response.status_code in (
                429, 500, 502, 503, 504,
            )
            if attempt == attempts or not recuperabile:
                raise
            await asyncio.sleep(attempt)


async def _openalex_concepts(
    topic: str, client: httpx.AsyncClient, config: Config
) -> list[tuple[str, float]]:
    params = {"title": topic}
    if config.mailto:
        params["mailto"] = config.mailto
    response = await client.get(f"{OPENALEX}/text/concepts", params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    return [
        (c["display_name"], float(c.get("score", 0)))
        for c in data.get("concepts", [])
        if c.get("display_name")
    ]


async def _openalex_topics(topic: str, client: httpx.AsyncClient, config: Config) -> list[str]:
    params = {"title": topic}
    if config.mailto:
        params["mailto"] = config.mailto
    response = await client.get(f"{OPENALEX}/text/topics", params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    return [t["display_name"] for t in data.get("topics", []) if t.get("display_name")][:5]


async def _pubmed_mesh(topic: str, client: httpx.AsyncClient, config: Config) -> list[str]:
    """I termini MeSH escono dalla traduzione automatica di PubMed."""

    params = {"db": "pubmed", "term": topic, "retmode": "json", "retmax": "0"}
    if config.ncbi_api_key:
        params["api_key"] = config.ncbi_api_key
    response = await client.get(f"{EUTILS}/esearch.fcgi", params=params, timeout=20)
    response.raise_for_status()
    result = response.json().get("esearchresult", {})
    terms: list[str] = []
    for item in result.get("translationset", []):
        for match in _MESH.findall(item.get("to", "")):
            if match not in terms:
                terms.append(match)
    for match in _MESH.findall(result.get("querytranslation", "")):
        if match not in terms:
            terms.append(match)
    return terms[:12]


async def _cooccurring_terms(
    topic: str, client: httpx.AsyncClient, config: Config
) -> list[tuple[str, int]]:
    """Unigrammi e bigrammi ricorrenti nei titoli dei primi risultati."""

    params = {"search": topic, "per_page": "50", "select": "title"}
    if config.mailto:
        params["mailto"] = config.mailto
    response = await client.get(f"{OPENALEX}/works", params=params, timeout=25)
    response.raise_for_status()
    titles = [w.get("title") or "" for w in response.json().get("results", [])]
    return count_terms(titles, exclude=topic)


def words_of(text: str) -> list[str]:
    """Parole significative: l'apostrofo separa (dell'IA -> ia)."""

    return [w for w in _WORD.findall(_APOSTROPHE.sub(" ", text.lower())) if w not in STOPWORDS]


def count_terms(titles: list[str], exclude: str = "", min_count: int = 2) -> list[tuple[str, int]]:
    topic_words = set(words_of(exclude))
    counter: Counter[str] = Counter()
    for title in titles:
        words = words_of(title)
        counter.update(w for w in words if w not in topic_words and len(w) > 2)
        counter.update(
            f"{a} {b}"
            for a, b in zip(words, words[1:])
            if not (a in topic_words and b in topic_words)
        )
    ranked = [(term, n) for term, n in counter.most_common(40) if n >= min_count]
    # I bigrammi sono piu' informativi degli unigrammi: prima loro.
    ranked.sort(key=lambda item: (" " not in item[0], -item[1]))
    return ranked[:20]


def _short(exc: Exception, t: dict[str, str]) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return t["err_429"]
        return f"HTTP {code}"
    if isinstance(exc, httpx.TimeoutException):
        return t["err_timeout"]
    text = str(exc) or exc.__class__.__name__
    return text[:120]
