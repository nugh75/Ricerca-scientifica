# OpenAlex esteso — specifica

**Data:** 2026-08-20
**Stato:** implementata in 1.0.0b2, estesa in 1.0.0b5 e 1.0.0b6

## Perché

Ricerca usa OpenAlex per una cosa sola: una `search` su `title_and_abstract`
con tre filtri. L'API ne offre molte altre che servono esattamente al lavoro
che l'applicazione fa — costruire, documentare e schermare una revisione della
letteratura. Questa specifica raccoglie quelle che valgono il codice che
costano, verificate sull'API reale il 2026-08-20.

## Che cosa si aggiunge

### 1. Fondamenta condivise
Un solo punto di contatto con OpenAlex (`ricerca/openalex_api.py`): chiave,
email di cortesia, timeout e contabilità del costo scritte una volta sola.
Oggi `sources/openalex.py` e `keywords.py` ripetono lo stesso preambolo, e le
funzioni nuove lo ripeterebbero altre sei volte.

### 2. Contabilità del credito
Ogni risposta porta `meta.cost_usd`. Il budget quotidiano è $1.00 con la
chiave gratuita, $0.10 senza. Oggi l'app avvisa a indovinare (`avviso()` in
`sources/openalex.py`); con il dato vero può dire quanto resta e fermarsi
prima del `429`. Le risposte servite dalla cache non si contano.

Listino verificato: entità singola gratis, lista/filtro $0.0001,
ricerca e ricerca semantica $0.001, PDF dall'archivio $0.01, autocomplete $0.

### 3. Record più ricco
Nella stessa chiamata, senza costo aggiuntivo:
- `abstract_inverted_index` → l'abstract, che oggi da OpenAlex resta vuoto;
- `is_retracted` → un articolo ritirato non deve entrare in una revisione
  senza che si veda;
- `cited_by_count` e `citation_normalized_percentile.is_in_top_10_percent` →
  ordine di lettura per lo screening;
- `has_content.pdf` e `content_urls.pdf` → la copia nell'archivio OpenAlex;
- `id` → l'identificativo che serve a tutto il resto.

### 4. Filtri nuovi
`language`, `is_retracted:false`, `is_oa:true`, `has_content.pdf:true`, più i
filtri per entità (rivista, ateneo, finanziatore) risolti da autocomplete.
Valgono per OpenAlex soltanto: l'interfaccia deve dirlo, perché un filtro che
una fonte ignora in silenzio falsa una revisione.

### 5. PDF dall'archivio OpenAlex
`content.openalex.org/works/{id}.pdf` — 50M+ file, $0.01 l'uno, richiede la
chiave (senza, risponde `401 API key required`). Ultimo tentativo dopo i
collegamenti aperti e dopo Unpaywall, e solo se chi usa l'app lo accende:
è l'unica funzione a pagamento reale del programma.

I PDF restano sotto il copyright originale, OpenAlex non concede diritti in
più: la licenza del singolo lavoro è in `best_oa_location.license`.

### 6. Snowballing
Tre direzioni da un record già trovato:
- **indietro**: `referenced_works` della scheda (chiamata singola, gratis) e
  poi i record a blocchi di cento (`filter=openalex:W1|W2|…`, $0.0001);
- **avanti**: `filter=cites:W123`;
- **di lato**: `related_works`, dieci vicini già calcolati.

I record scelti si aggiungono alla ricerca in cronologia, in coda, con la
provenienza segnata: le decisioni di screening sono indicizzate per posizione
e non devono spostarsi.

### 7. Profilo del campo (faccette)
`group_by` su anno, tipo, accesso aperto, topic e paese: cinque chiamate da
$0.0001 che dicono com'è fatta la letteratura prima di leggerne un rigo, e
danno i numeri per il diagramma PRISMA.

### 8. Ricerca semantica
`search.semantic=` trova per significato invece che per parole. Nuova fonte
interrogabile accanto alle altre, spenta di suo: massimo 50 risultati, una
richiesta al secondo, $0.001 a chiamata.

### 9. Autocomplete
`/autocomplete/{entità}?q=` risponde in ~200 ms e non costa nulla. Serve a due
cose: suggerire termini mentre si scrivono i blocchi, e risolvere un nome in
un identificativo (regola dei documenti: mai filtrare per nome).

### 10. OQL nel protocollo
Ogni risposta contiene `meta.x_query.oql`, la stessa query scritta nel
linguaggio di OpenAlex. Va salvata nella cronologia ed esportata nel
protocollo: è la strategia riproducibile che una revisione deve pubblicare.

### 11. Campione riproducibile e paginazione a cursore
`sample=N&seed=S` per il pilota di screening; il cursore per superare i 100
record per chiamata fino a un tetto di 200, che tiene il costo prevedibile.

### 12. Identità, citazioni e profili bibliometrici
I record conservano gli identificativi OpenAlex degli autori e della rivista,
se la fonte li dichiara con certezza. Il conteggio `cited_by_count` compare nei
risultati e negli export distinguendo lo zero dal dato assente; proviene da
OpenAlex e non è una misura assoluta.

La sezione **Esplora** cerca autori e riviste e mostra identità, produzione,
citazioni, indice h, indice i10, andamento annuale e lavori più citati. I
conteggi aggregati sono presentati come una fotografia OpenAlex, con la data di
consultazione: possono aggiornarsi con tempi diversi e non costituiscono da
soli un giudizio di qualità. Le cronologie precedenti, prive di identificativi,
restano leggibili e aprono una ricerca per nome senza associare omonimi in modo
automatico.

Dalla versione 1.0.0b6, ogni lavoro più citato può caricare su richiesta un
elenco breve degli articoli che lo citano. Il caricamento resta differito per
non moltiplicare le chiamate OpenAlex quando si apre il profilo.

## Che cosa resta fuori

- Snapshot, CLI e sincronizzazione S3 di OpenAlex: sono per corpora interi.
- `corpus=expansion|all`: raddoppia il rumore, serve a casi che l'app non ha.
- `grobid_xml`: il testo pieno strutturato è interessante per l'estrazione
  dati, ma senza un uso già definito è codice speculativo.
- Pagine di navigazione per atenei: l'app conserva questo filtro ma non espone
  ancora un profilo istituzionale.
- OQL come linguaggio di input: si esporta, non si fa scrivere.

## Vincoli

- Nessuna dipendenza nuova.
- Python ≥ 3.11, httpx asincrono, test con pytest e respx.
- Ogni stringa a schermo in italiano e inglese (`i18n.STRINGS`, chiavi in
  parità: `tests/test_i18n.py` lo verifica).
- Nomi e commenti in italiano, come il resto del programma.
- Niente chiamate a pagamento senza che chi usa l'app lo sappia prima.
- Le funzioni nuove non devono rallentare la ricerca normale: chi non le usa
  non paga né aspetta.
