# Template Atti - Cartabia STRICT

Aggiornato: 2026-05-12.

## Regola

Un template non diventa `cartabia_ready` per la sola presenza di un campo. Deve avere profilo Cartabia, area processuale, regole applicabili, dati obbligatori mappati, prefill per i dati ricavabili da IUSENTRA, controlli deposito se depositabile, fonti ufficiali e nessun issue bloccante.

## Fonti

Le evidenze sono in `docs/legal_sources/cartabia_sources.jsonl`; l'audit e' in `docs/reports/cartabia_web_source_audit.md`.

Fonti ufficiali usate: Normattiva, Gazzetta Ufficiale, PST/DGSIA, PDP, Giustizia Amministrativa, Giustizia Tributaria, Garante Privacy.

## Stato attuale

- `cartabia_ready`: 1320 template canonici.
- `cartabia_review_required`: 0 template canonici.
- `draft_professionale`: 0 template canonici.
- `needs_review`: 0.
- Totale governato: 1320 template canonici.
- Record di fonte ispezionati senza gonfiare il totale: 4576.
- Template con conflitto non riconciliato tra copie fonte: 0.
- Template con copie fonte riconciliate automaticamente: 1156.

`cartabia_ready` qui significa pronto come modello governato: norme, fonti, controlli, prefill binding, timbro, renderer e deposito sono presenti. Non richiede che esista gia una pratica. I dati concreti (`Cliente / Mittente`, `Pratica Collegata`, `Destinatario / Ufficio Giudiziario`, `Autore`) vengono risolti quando l'avvocato seleziona il template e avvia la compilazione.

Se una fonte ufficiale o una capability di modello manca davvero, il template resta `cartabia_review_required`. Le copie JSON/SQLite/tenant con metadati diversi ma risolvibili vengono riconciliate usando la fonte canonica e restano tracciate nei report.

`richiede_verifica_avvocato` non e' una bandiera generale dei modelli pronti. Rimane `false` sui template `cartabia_ready` e passa a `true` solo quando manca una fonte/regola ufficiale oppure quando una verifica concreta di compilazione trova dati realmente bloccanti.

## Aree coperte

- Civile ordinario e semplificato.
- Famiglia, minori e persone.
- ADR, mediazione, negoziazione, arbitrato.
- Penale e PDP.
- Tributario e PTT.
- Amministrativo e PAT.
- Esecuzioni.
- Monitorio.
- Cautelari.
- Studio interno, privacy e incarichi.

## Aggiornamento regole

Ogni nuova regola deve aggiungere un `evidence_id` ufficiale. Se la fonte non e' reperita, il template resta `cartabia_review_required` con `fonte_normativa_mancante`.
