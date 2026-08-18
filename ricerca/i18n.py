"""Stringhe dell'interfaccia in italiano e inglese.

Una sola tabella: le chiavi valgono sia per i template sia per i messaggi
generati dal codice (note, errori delle fonti).
"""

from __future__ import annotations

LANGS = ("it", "en")
DEFAULT = "it"

STRINGS: dict[str, dict[str, str]] = {
    "it": {
        "lang_name": "Italiano",
        "brand_sub": "strategia bibliografica",
        "nav_strategy": "Strategia",
        "nav_settings": "Impostazioni",
        "footer": "Tutto in locale. Chiavi e preferenze restano in ~/.ricerca/config.toml",
        "step1_eyebrow": "Passo uno",
        "step1_title": "Descrivi l'argomento",
        "step1_intro": (
            "Scrivilo in italiano o in inglese. Ricerca interroga OpenAlex per i concetti, "
            "PubMed per i termini controllati MeSH e legge i titoli dei primi risultati per "
            "trovare i termini che ricorrono davvero nella letteratura."
        ),
        "topic_placeholder": "es. competenze di intelligenza artificiale negli insegnanti",
        "topic_aria": "argomento della ricerca",
        "btn_suggest": "Suggerisci le parole chiave",
        "waiting_sources": "lettura delle banche dati…",
        "llm_missing": (
            "Nessun LLM configurato: i blocchi vengono costruiti dai soli dati. "
            "Per farli riorganizzare da un modello, imposta un endpoint in"
        ),
        "llm_missing_tail": "— Ollama, llama-swap, DeepSeek o OpenAI.",
        "mailto_active": "Email di cortesia attiva:",
        "mailto_active_tail": "— OpenAlex applica i limiti più larghi.",
        "mailto_placeholder": "nome@esempio.it",
        "mailto_prompt": "Senza email di cortesia OpenAlex risponde spesso <b>429</b>. Inseriscila una volta sola:",
        "btn_save": "Salva",
        "step2_eyebrow": "Passo due · nessuna ricerca è ancora partita",
        "step2_title": "Ricerche suggerite per",
        "badge_llm": "blocchi riorganizzati dall'LLM",
        "badge_data": "blocchi costruiti dai soli dati",
        "card_terms": "Termini trovati",
        "group_concepts": "Concetti OpenAlex",
        "group_mesh": "Termini controllati MeSH",
        "group_cooccurring": "Ricorrono nei titoli",
        "group_topics": "Aree tematiche",
        "empty_terms": (
            "Nessun termine dalle banche dati questa volta: i blocchi qui sotto partono "
            "dalle parole del topic. Puoi scriverli a mano e aggiornare le stringhe."
        ),
        "card_blocks": "Blocchi della ricerca",
        "blocks_help": (
            "Termini separati da virgola: dentro un blocco vanno in OR, i blocchi fra loro "
            "in AND. Modificali e aggiorna le stringhe."
        ),
        "block": "Blocco",
        "block_optional": "facoltativo",
        "block_name_aria": "nome del blocco",
        "block_terms_aria": "termini del blocco",
        "block_extra_name": "Blocco aggiuntivo",
        "block_extra_placeholder": "es. scuola secondaria, secondary school",
        "mesh_label": "Termini MeSH usati solo da PubMed, in AND con gli altri blocchi",
        "btn_update_queries": "Aggiorna le stringhe",
        "legend_sources": "Dove cercare",
        "limit_label": "Massimo per fonte",
        "btn_search": "Avvia la ricerca",
        "waiting_search": "interrogazione delle fonti…",
        "card_queries": "Stringhe pronte per ogni banca dati",
        "paste_suffix": "da incollare",
        "btn_copy": "copia",
        "copied": "copiata",
        "step3_eyebrow": "Passo tre",
        "step3_title": "Risultati",
        "summary_tail": "record dopo la deduplica",
        "download_bib": "scarica .bib",
        "download_csv": "scarica .csv",
        "th_year": "Anno",
        "th_title": "Titolo",
        "th_authors": "Autori",
        "th_venue": "Sede",
        "th_sources": "Fonti",
        "empty_results": "Nessun record. Allarga i blocchi, togli un vincolo o aggiungi una fonte.",
        "settings_eyebrow": "Configurazione",
        "settings_title": "Impostazioni",
        "settings_saved": "salvato in {path}, permessi 600",
        "settings_llm": "LLM · facoltativo",
        "settings_llm_help": "Qualsiasi endpoint compatibile con l'API OpenAI. Preset:",
        "settings_url": "URL di base",
        "settings_model": "Modello",
        "settings_llm_key": "Chiave API — vuota per i modelli locali",
        "btn_list_models": "Elenca i modelli",
        "settings_sources": "Fonti",
        "settings_mailto": "Email di cortesia — OpenAlex alza i limiti di richiesta",
        "settings_s2": "Chiave Semantic Scholar — senza, il servizio risponde spesso 429",
        "settings_core": "Chiave CORE — gratuita su core.ac.uk",
        "settings_ncbi": "Chiave NCBI per PubMed — facoltativa",
        "key_set": "chiave impostata — lascia vuoto per non cambiarla",
        "key_empty": "nessuna chiave",
        "key_remove": "rimuovi",
        "key_help": (
            "Le chiavi restano sul tuo computer e non vengono mai rimandate al browser: "
            "un campo vuoto lascia invariata la chiave già salvata."
        ),
        "settings_status": "Stato delle fonti",
        "status_ready": "pronta",
        "status_string_only": "solo stringa",
        "endpoint_unreachable": "Endpoint non raggiungibile:",
        "no_models": "L'endpoint non elenca modelli.",
        "note_unavailable": "{label}: non disponibili ({error})",
        "label_concepts": "concetti OpenAlex",
        "label_topics": "topic OpenAlex",
        "label_mesh": "termini MeSH",
        "label_cooccurring": "termini co-occorrenti",
        "mesh_missing": (
            "nessun termine MeSH: PubMed non traduce i topic in italiano, "
            "prova a riscrivere il topic in inglese"
        ),
        "err_429": "HTTP 429, troppe richieste: aggiungi l'email di cortesia in Impostazioni",
        "err_timeout": "tempo scaduto",
        "err_empty_strategy": "strategia vuota",
        "llm_unusable": "LLM non utilizzabile ({error}) — blocchi dai soli dati",
        "need_core_key": "richiede una chiave gratuita da core.ac.uk/services/api",
        "s2_hint": "senza chiave il servizio risponde spesso 429",
        "need_opac_cli": "richiede la CLI {binary} nel PATH",
        "needs_key": "richiede una chiave API",
    },
    "en": {
        "lang_name": "English",
        "brand_sub": "search strategy",
        "nav_strategy": "Strategy",
        "nav_settings": "Settings",
        "footer": "Everything runs locally. Keys and preferences stay in ~/.ricerca/config.toml",
        "step1_eyebrow": "Step one",
        "step1_title": "Describe the topic",
        "step1_intro": (
            "Write it in English or Italian. Ricerca asks OpenAlex for concepts, PubMed for "
            "MeSH controlled terms, and reads the titles of the first results to find the "
            "terms the literature actually uses."
        ),
        "topic_placeholder": "e.g. AI literacy in teacher education",
        "topic_aria": "search topic",
        "btn_suggest": "Suggest keywords",
        "waiting_sources": "reading the databases…",
        "llm_missing": (
            "No LLM configured: blocks are built from the data alone. To have a model "
            "reorganise them, set an endpoint in"
        ),
        "llm_missing_tail": "— Ollama, llama-swap, DeepSeek or OpenAI.",
        "mailto_active": "Courtesy email set:",
        "mailto_active_tail": "— OpenAlex grants the higher rate limits.",
        "mailto_placeholder": "name@example.org",
        "mailto_prompt": "Without a courtesy email OpenAlex often answers <b>429</b>. Enter it once:",
        "btn_save": "Save",
        "step2_eyebrow": "Step two · no search has run yet",
        "step2_title": "Suggested searches for",
        "badge_llm": "blocks reorganised by the LLM",
        "badge_data": "blocks built from the data alone",
        "card_terms": "Terms found",
        "group_concepts": "OpenAlex concepts",
        "group_mesh": "MeSH controlled terms",
        "group_cooccurring": "Recurring in titles",
        "group_topics": "Topic areas",
        "empty_terms": (
            "No terms from the databases this time: the blocks below start from the words "
            "of your topic. Edit them by hand and update the strings."
        ),
        "card_blocks": "Search blocks",
        "blocks_help": (
            "Comma-separated terms: inside a block they are OR-ed, blocks are AND-ed "
            "together. Edit them and update the strings."
        ),
        "block": "Block",
        "block_optional": "optional",
        "block_name_aria": "block name",
        "block_terms_aria": "block terms",
        "block_extra_name": "Extra block",
        "block_extra_placeholder": "e.g. secondary school, scuola secondaria",
        "mesh_label": "MeSH terms, used by PubMed only, AND-ed with the other blocks",
        "btn_update_queries": "Update the strings",
        "legend_sources": "Where to search",
        "limit_label": "Max per source",
        "btn_search": "Run the search",
        "waiting_search": "querying the sources…",
        "card_queries": "Strings ready for each database",
        "paste_suffix": "paste it there",
        "btn_copy": "copy",
        "copied": "copied",
        "step3_eyebrow": "Step three",
        "step3_title": "Results",
        "summary_tail": "records after deduplication",
        "download_bib": "download .bib",
        "download_csv": "download .csv",
        "th_year": "Year",
        "th_title": "Title",
        "th_authors": "Authors",
        "th_venue": "Venue",
        "th_sources": "Sources",
        "empty_results": "No records. Widen the blocks, drop a constraint or add a source.",
        "settings_eyebrow": "Configuration",
        "settings_title": "Settings",
        "settings_saved": "saved to {path}, permissions 600",
        "settings_llm": "LLM · optional",
        "settings_llm_help": "Any endpoint compatible with the OpenAI API. Presets:",
        "settings_url": "Base URL",
        "settings_model": "Model",
        "settings_llm_key": "API key — leave empty for local models",
        "btn_list_models": "List the models",
        "settings_sources": "Sources",
        "settings_mailto": "Courtesy email — OpenAlex raises the rate limits",
        "settings_s2": "Semantic Scholar key — without it the service often answers 429",
        "settings_core": "CORE key — free at core.ac.uk",
        "settings_ncbi": "NCBI key for PubMed — optional",
        "key_set": "key set — leave empty to keep it",
        "key_empty": "no key",
        "key_remove": "remove",
        "key_help": (
            "Keys stay on your computer and are never sent back to the browser: "
            "an empty field leaves the stored key untouched."
        ),
        "settings_status": "Source status",
        "status_ready": "ready",
        "status_string_only": "string only",
        "endpoint_unreachable": "Endpoint unreachable:",
        "no_models": "The endpoint lists no models.",
        "note_unavailable": "{label}: unavailable ({error})",
        "label_concepts": "OpenAlex concepts",
        "label_topics": "OpenAlex topics",
        "label_mesh": "MeSH terms",
        "label_cooccurring": "co-occurring terms",
        "mesh_missing": (
            "no MeSH terms: PubMed does not translate Italian topics, "
            "try writing the topic in English"
        ),
        "err_429": "HTTP 429, too many requests: add the courtesy email in Settings",
        "err_timeout": "timed out",
        "err_empty_strategy": "empty strategy",
        "llm_unusable": "LLM unusable ({error}) — blocks from the data alone",
        "need_core_key": "needs a free key from core.ac.uk/services/api",
        "s2_hint": "without a key the service often answers 429",
        "need_opac_cli": "needs the {binary} CLI on the PATH",
        "needs_key": "needs an API key",
    },
}


def normalize(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT


def strings(lang: str | None = None) -> dict[str, str]:
    return STRINGS[normalize(lang)]
