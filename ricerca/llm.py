"""Client per qualsiasi endpoint compatibile con l'API OpenAI.

Copre Ollama (`/v1`), DeepSeek, OpenAI e OpenRouter senza
codice dedicato: cambia solo la configurazione.
"""

from __future__ import annotations

import json
import re

import httpx

from .config import Config
from .i18n import strings
from .models import Block

_PROMPT = """Sei un bibliotecario esperto di ricerca bibliografica.
Topic della ricerca: "{topic}"

Termini raccolti dalle banche dati:
- concetti OpenAlex: {concepts}
- termini co-occorrenti nei titoli: {cooccurring}
- termini controllati MeSH: {mesh}

Organizza la ricerca in 2-4 blocchi concettuali. Scrivi le etichette dei
blocchi {lingua}. Ogni blocco raccoglie
sinonimi e varianti (inglese e italiano) di UNO stesso concetto: i termini
dentro un blocco andranno in OR, i blocchi fra loro in AND.
Usa termini realmente usati nella letteratura scientifica, preferendo
l'inglese. Niente spiegazioni.

Rispondi SOLO con JSON in questa forma:
{{"blocks": [{{"label": "nome del concetto", "terms": ["termine 1", "termine 2"]}}]}}
"""


class LLMError(Exception):
    pass


_TRADUZIONE = """Traduci in inglese accademico questo argomento di ricerca.
Rispondi con la sola traduzione, senza virgolette e senza spiegazioni.

Argomento: {topic}"""


_SINTESI = """Sei un ricercatore che legge un articolo scientifico per un collega.
Riassumilo {lingua}, in modo asciutto e verificabile: nessun aggettivo di
lode, nessuna frase di circostanza, nessuna informazione che non sia nel testo.
Se il testo non dice qualcosa, scrivi che non è riportato.

Quattro parti, ognuna di due o tre frasi:
- metodo: come è stato condotto lo studio, su chi o su che cosa, con quali strumenti;
- risultati: che cosa è stato trovato, con i numeri quando ci sono;
- discussione: come gli autori leggono quei risultati, e quali limiti dichiarano;
- conclusione: che cosa se ne ricava, in una frase.

Rispondi SOLO con JSON in questa forma:
{{"metodo": "…", "risultati": "…", "discussione": "…", "conclusione": "…"}}

Titolo: {titolo}

Testo:
{testo}"""


class LLMClient:
    def __init__(self, config: Config, client: httpx.AsyncClient | None = None):
        self.base_url = config.llm_base_url.rstrip("/")
        self.model = config.llm_model
        self.api_key = config.llm_api_key
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def list_models(self) -> list[str]:
        async with self._session() as client:
            response = await client.get(
                f"{self.base_url}/models", headers=self._headers(), timeout=15
            )
            response.raise_for_status()
            data = response.json()
        return sorted(item.get("id", "") for item in data.get("data", []) if item.get("id"))

    async def blocks_for(self, topic: str, concepts, cooccurring, mesh, lang=None) -> list[Block]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": _PROMPT.format(
                        topic=topic,
                        concepts=", ".join(name for name, _ in concepts[:12]) or "-",
                        cooccurring=", ".join(term for term, _ in cooccurring[:12]) or "-",
                        mesh=", ".join(mesh[:8]) or "-",
                        lingua=strings(lang)["llm_labels_language"],
                    ),
                }
            ],
            "temperature": 0.2,
            "stream": False,
        }
        async with self._session() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"risposta inattesa dall'LLM: {data}") from exc
        return _parse_blocks(content)

    async def traduci(self, topic: str) -> str:
        """Il topic in inglese: PubMed e MeSH non capiscono l'italiano."""

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": _TRADUZIONE.format(topic=topic)}],
            "temperature": 0,
            "stream": False,
        }
        async with self._session() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
        try:
            testo = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"risposta inattesa dall'LLM: {data}") from exc
        return " ".join(testo.strip().strip('"').split())[:200]

    async def sintesi(self, titolo: str, testo: str, lingua: str = "it") -> dict:
        """Riassunto in quattro parti. Solleva se il modello non collabora."""

        in_lingua = "in italiano" if lingua == "it" else "in inglese"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": _SINTESI.format(
                        lingua=in_lingua, titolo=titolo[:300], testo=testo[:12000]
                    ),
                }
            ],
            "temperature": 0.1,
            "stream": False,
        }
        async with self._session() as client:
            risposta = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=300,
            )
            risposta.raise_for_status()
            dati = risposta.json()
        try:
            contenuto = dati["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"risposta inattesa dall'LLM: {dati}") from exc
        return _parse_sintesi(contenuto)

    def _session(self):
        if self._client is not None:
            return _Borrowed(self._client)
        return httpx.AsyncClient()


class _Borrowed:
    """Usa un client esistente senza chiuderlo all'uscita dal `with`."""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *exc_info) -> bool:
        return False


def _parse_sintesi(contenuto: str) -> dict:
    """Le quattro parti del riassunto, da una risposta che può essere sporca."""

    testo = re.sub(r"^```(?:json)?|```$", "", contenuto.strip(), flags=re.MULTILINE).strip()
    trovato = re.search(r"\{.*\}", testo, re.DOTALL)
    if not trovato:
        raise LLMError("il modello non ha restituito JSON")
    try:
        dati = json.loads(trovato.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"JSON non valido dal modello: {exc}") from exc

    parti = {}
    for chiave in ("metodo", "risultati", "discussione", "conclusione"):
        valore = dati.get(chiave)
        parti[chiave] = " ".join(str(valore).split()) if valore else ""
    if not any(parti.values()):
        raise LLMError("il modello non ha prodotto un riassunto utilizzabile")
    return parti


def _parse_blocks(content: str) -> list[Block]:
    text = content.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMError("l'LLM non ha restituito JSON")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"JSON non valido dall'LLM: {exc}") from exc
    blocks = []
    for raw in data.get("blocks", []):
        terms = [str(t).strip() for t in raw.get("terms", []) if str(t).strip()]
        if terms:
            blocks.append(Block(str(raw.get("label", "Blocco")).strip() or "Blocco", terms))
    if not blocks:
        raise LLMError("l'LLM non ha prodotto blocchi utilizzabili")
    return blocks
