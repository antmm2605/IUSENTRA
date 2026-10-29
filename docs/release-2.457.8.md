# Etichette certe del catalogo documentale (passo 1 dell'addestramento)

Primo passo del piano `docs/PIANO_CATENA_DOCUMENTALE_2026-10-29.md` (Fase 1) per addestrare un classificatore dei documenti misurabile. Autorizzato dall'utente il 29/10/2026.

- **Registro delle etichette certe** (`pct/document_intelligence/verita/`). Per ogni documento del fascicolo raccoglie le etichette che il software conosce con certezza:
  - livello A: tipo atto dichiarato nel deposito telematico e letto dal Portale dei Servizi Telematici, solo per atti principali e provvedimenti. Gli allegati non ricevono etichetta;
  - livello B: correzioni e conferme singole dell'avvocato.

  Esclusioni e controlli:
  - le conferme massive sono escluse: attestano che una prova esiste, non che il documento sia stato letto;
  - gli XML con struttura ministeriale o FatturaPA sono contati a parte, perché il catalogo li riconosce già con certezza;
  - un conflitto fra deposito e avvocato viene segnalato e prevale la decisione dell'avvocato;
  - un tipo atto del portale non presente nella tabella di corrispondenza non diventa un'etichetta: viene contato, per completare la tabella con riscontri.
- **Audit delle decisioni.**
  - La conferma dichiara se è singola o massiva.
  - La correzione registra la voce di prima e quella nuova.
  - L'identificativo dell'evento è univoco anche quando lo stesso documento viene rivisto più volte: prima la seconda revisione falliva sulla chiave duplicata.
- **Censimento in sola lettura sul server.** Azione manuale «Censimento etichette certe del catalogo», nel container scheduler-worker. Restituisce solo conteggi per voce, concordanza del catalogo attuale con il deposito e tipi atto del portale non ancora in tabella. Nessun nome di file, testo o dato del cliente; gli studi sono numerati.

Non modificati: classificazione in uso, seconda lettura di Lex, flusso deposito/firma/PEC congelato.

Test: `tests/test_verita_catalogo.py`, più gli adeguamenti di `tests/test_document_catalog_conferma.py` e `tests/test_document_intelligence_catalog_governance.py`.
