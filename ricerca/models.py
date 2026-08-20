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
class Filtri:
    """Vincoli che valgono per tutte le fonti, ognuna con la sua sintassi.

    Gli ultimi quattro li applica solo OpenAlex: le altre banche dati non
    espongono gli stessi campi, e l'interfaccia deve dirlo — un filtro
    ignorato in silenzio falsa il conteggio di una revisione.
    """

    anno_da: int | None = None
    anno_a: int | None = None
    solo_articoli: bool = False
    lingua: str = ""
    escludi_ritirati: bool = False
    solo_oa: bool = False
    con_pdf: bool = False
    rivista_id: str = ""
    ateneo_id: str = ""
    finanziatore_id: str = ""
    # Pilota di screening riproducibile: stesso seme, stesso campione.
    campione: int | None = None
    seme: int | None = None

    def attivi(self) -> bool:
        return bool(
            self.anno_da or self.anno_a or self.solo_articoli
            or self.lingua or self.escludi_ritirati or self.solo_oa or self.con_pdf
            or self.rivista_id or self.ateneo_id or self.finanziatore_id
        )


@dataclass
class Strategy:
    """Blocchi in AND fra loro; `mesh` sono i termini controllati PubMed."""

    blocks: list[Block] = field(default_factory=list)
    mesh: list[str] = field(default_factory=list)
    filtri: Filtri = field(default_factory=Filtri)

    def non_empty_blocks(self) -> list[Block]:
        return [b for b in self.blocks if b.clean_terms()]

    def is_empty(self) -> bool:
        return not self.non_empty_blocks()


@dataclass
class Work:
    """Un risultato bibliografico, normalizzato fra le fonti."""

    title: str
    authors: list[str] = field(default_factory=list)
    # Identificativi paralleli ai nomi: restano separati per non rompere le
    # cronologie vecchie, che conservano soltanto una lista di stringhe.
    author_ids: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    venue: str | None = None
    venue_id: str = ""
    url: str | None = None
    abstract: str | None = None
    oa_url: str | None = None
    # Altre strade verso lo stesso PDF: le fonti ne dichiarano più d'una e
    # spesso la prima è una pagina di destinazione, non il file.
    oa_urls: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    # Quel che sa OpenAlex e le altre fonti non dicono: serve alle citazioni,
    # allo screening e all'ultimo tentativo di scaricare il PDF.
    openalex_id: str = ""
    ritirato: bool = False
    citazioni: int | None = None
    molto_citato: bool = False      # primo dieci per cento del suo campo e anno
    pdf_archivio: str = ""          # copia nell'archivio OpenAlex, a pagamento
    # Pertinenza: somma dei contributi delle fonti in cui il record compare
    # in alto (reciprocal rank fusion). Non viene mostrata, ordina l'elenco.
    punteggio: float = 0.0
    # Screening: riempiti al momento della lettura dalla cronologia.
    decisione: str = ""
    motivo: str = ""
    # Campi corretti a mano: gli originali restano nella cronologia.
    corretto: list[str] = field(default_factory=list)
    # Campi completati da Unpaywall: mancavano, non erano sbagliati.
    completato: list[str] = field(default_factory=list)

    def candidati_pdf(self) -> list[str]:
        """Tutti i collegamenti da provare, in ordine, senza ripetizioni."""

        visti, ordinati = set(), []
        for indirizzo in [self.oa_url, *self.oa_urls]:
            if indirizzo and indirizzo not in visti:
                visti.add(indirizzo)
                ordinati.append(indirizzo)
        return ordinati

    @property
    def authors_short(self) -> str:
        if not self.authors:
            return ""
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    @property
    def authors_identified(self) -> list[tuple[str, str]]:
        """Nomi e ID allineati, con ID vuoto quando una fonte non lo sa."""

        ids = [*self.author_ids, *([""] * max(0, len(self.authors) - len(self.author_ids)))]
        return list(zip(self.authors, ids))


@dataclass
class SourceResult:
    """Esito dell'interrogazione di una singola fonte."""

    source_id: str
    label: str
    query: str
    works: list[Work] = field(default_factory=list)
    error: str | None = None
    secondi: float = 0.0
    # La stessa interrogazione riscritta da OpenAlex nel suo linguaggio: è la
    # strategia riproducibile da allegare a una revisione.
    oql: str = ""


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
    tradotto: str = ""
