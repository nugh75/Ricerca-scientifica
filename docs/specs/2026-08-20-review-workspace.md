# Workspace per review della letteratura — specifica

**Data:** 2026-08-20
**Stato:** implementata per la versione 1.0.0b7

## Obiettivo

Portare Ricerca oltre la singola interrogazione senza duplicare le funzioni
già presenti. Le ricerche salvate restano istantanee autonome; un progetto di
review ne raccoglie più d'una in un corpus stabile, deduplicato e verificabile.

## Modello di lavoro

Il workspace segue nove fasi navigabili:

1. **Protocollo** — tipo di review, PICO/PICOS/PCC, criteri, outcome, fonti,
   piano di sintesi, registrazione, frequenza di aggiornamento, peer review
   PRESS e articoli sentinella. Ogni modifica successiva conserva motivo,
   data, valore precedente e valore nuovo.
2. **Ricerche** — più istantanee confluiscono nello stesso corpus; query,
   OQL, filtri, data, conteggi e provenienze restano associati ai record.
3. **Titolo e abstract** — decisioni indipendenti e cieche per profilo di
   revisore; lo stato finale esiste soltanto dopo tutte le decisioni o dopo un
   consenso esplicito.
4. **Testo completo** — disponibilità, richieste e motivi sono separati dalla
   decisione di eleggibilità. Le esclusioni conservano sempre la motivazione.
5. **Estrazione** — campi uniformi, prova testuale e pagina; estrazioni
   indipendenti, confronto delle divergenze e scheda concordata. Più report
   possono essere collegati allo stesso studio.
6. **Qualità** — RoB 2, ROBINS-I, JBI, CASP o schema personalizzato con domini,
   giudizio, motivazione, evidenza e pagina.
7. **Sintesi** — mappa delle caratteristiche estratte e Summary of findings
   per outcome con numerosità, effetto, certezza e motivazione.
8. **Wiki e grafo** — ogni record diventa una pagina-fonte; metadati certi
   collegano articoli, autori e sedi. Se è configurato, l'LLM compila dagli
   abstract pagine concettuali e relazioni, conservando gli ID fonte e
   accettando come citazioni soltanto sequenze realmente presenti nel corpus.
9. **Aggiornamenti** — scadenza calcolata dal protocollo, riesecuzione
   esplicita delle strategie, nuove istantanee, differenze dei metadati e
   avvisi sui ritiri.

## Assistenza allo screening

Il primo modello non introduce dipendenze né decisioni automatiche. Conta i
termini che distinguono record inclusi ed esclusi, ordina soltanto i record non
valutati e mostra termini e punteggio. Il corpus originale non viene riordinato
e nessun record viene escluso dal programma.

## Persistenza e compatibilità

- `~/.ricerca/reviews.json` contiene i progetti con permessi `0600`.
- `history.json` non cambia formato e resta la fonte delle istantanee.
- I record sono copiati nel progetto: eliminare una ricerca dalla cronologia
  non cancella decisioni o dati già entrati nella review.
- Il JSON completo è l'export di conservazione; il Markdown è un rapporto
  leggibile con protocollo, query, PRISMA-S, selezione, estrazione, qualità,
  sintesi, aggiornamenti ed emendamenti.

## Scelte UX

La barra delle nove fasi è la sola firma visiva nuova: rappresenta la sequenza
metodologica e porta direttamente alla sezione pertinente. Form e azioni sono
collocati dentro la fase a cui appartengono; non ci sono menu paralleli o
righe di icone ripetute. Gli stati usano testo e numeri, non il solo colore.
Su schermi stretti la traccia scorre orizzontalmente e tutti i moduli diventano
monocolonna. Focus da tastiera e riduzione del movimento seguono le regole già
presenti nell'app.

La wiki si apre in una pagina dedicata: la review principale mostra soltanto
stato, dimensioni e azioni. Nel grafo sono attivi inizialmente articoli e
concetti; autori e sedi sono filtri opzionali per evitare rumore. La ricerca
testuale filtra le pagine e la selezione di un nodo isola il suo vicinato.

## Provenienza della Wiki LLM Graph

- Le pagine-fonte e gli archi `scritto_da` e `pubblicato_in` sono sempre
  ricostruiti localmente dai metadati dell'intero corpus.
- L'analisi semantica usa gli inclusi al testo completo, se presenti; altrimenti
  gli inclusi a titolo/abstract, oppure il corpus intero prima dello screening.
- Gli abstract sono inviati al modello in lotti da dodici, soltanto dopo un
  comando esplicito. L'interfaccia avvisa che il provider può consumare credito.
- Concetti senza una fonte valida vengono eliminati. Una citazione LLM resta
  visibile soltanto se il testo coincide con una sequenza dell'abstract citato.
- Se il modello non è configurato o un lotto fallisce, resta disponibile il
  grafo bibliografico; un'impronta segnala quando il corpus rende la wiki obsoleta.

## Vincoli di sicurezza

La frequenza del protocollo produce una scadenza, non chiamate silenziose. La
riesecuzione parte soltanto da un comando esplicito perché può usare servizi in
rete e credito OpenAlex. Le decisioni assistite rimangono umane e l'audit log
registra ogni cambiamento significativo.
