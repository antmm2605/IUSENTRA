# Regia Operativa Fascicolo / Practice Engine

La Regia Operativa Fascicolo e' il motore deterministico che collega pratica commerciale, apertura fascicolo, checklist, documenti richiesti, predeposito, deposito, ricevute, timeline, evidence pack e audit.

Principio guida:

> Ogni fascicolo deve sapere cosa serve, cosa manca, cosa blocca, cosa e' stato inviato e cosa e' stato realmente acquisito.

Lex AI puo' spiegare o assistere, ma la validita' della pratica e del deposito resta determinata da profili, repository, documenti, ricevute, validatori e fonti ufficiali.

## Fonti operative

- `pct/legal_platform_catalog.py` e `pct/legal_platform_seed.py` generano i profili primari.
- `docs/SIGP_GIUDICE_DI_PACE.md` integra il profilo SIGP/Giudice di Pace quando il seed operativo non espone ancora una procedura dedicata.
- `pct/template_atti.py` e catalogo master template alimentano etichette, atti consigliati e slot collegabili.
- `pct/validazione.py` resta la fonte per controlli PDF/A, cifratura e dimensione.
- I portali sono trattati solo con flussi autorizzati: import file, ZIP, EML, XML o JSON autorizzato. Non e' previsto scraping HTML.

## Storage

Runtime JSON tenant-aware sotto il data root scrivibile dello studio:

- `fascicoli/practice_engine/practice_engine.json`
- `fascicoli/practice_engine/receipts/`
- `fascicoli/practice_engine/evidence_packs/`

Nei runtime Docker/Hetzner e multi-tenant il percorso deve essere risolto tramite `PRACTICE_ENGINE_DB` / `g.data_paths`, mai tramite path relativo al repository come `./fascicoli/...`.

Migrazioni governate:

- `pct/sql/20260504_practice_engine.sql`
- `pct/sql/20260504_practice_engine_postgres.sql`

Tabelle:

- `practice_profiles`
- `practice_requirements`
- `practice_document_slots`
- `practice_checklist_items`
- `practice_validation_results`
- `practice_state_history`
- `deposit_sessions`
- `deposit_receipts`
- `deposit_timeline_events`
- `evidence_packs`

## API React

Le API UI sono sotto `/api/v1/ui` e dichiarano sempre `mock_fallback=false` nei payload Regia:

- `GET /fascicoli/<fascicolo_id>/regia`
- `POST /fascicoli/<fascicolo_id>/regia/applica-profilo`
- `POST /fascicoli/<fascicolo_id>/regia/ricalcola`
- `GET /fascicoli/<fascicolo_id>/checklist`
- `GET /fascicoli/<fascicolo_id>/document-slots`
- `POST /fascicoli/<fascicolo_id>/document-slots/<slot_key>/link`
- `POST /fascicoli/<fascicolo_id>/document-slots/<slot_key>/validate`
- `POST /fascicoli/<fascicolo_id>/predeposito/check`
- `POST /fascicoli/<fascicolo_id>/depositi/prepara`
- `POST /fascicoli/<fascicolo_id>/depositi/invia`
- `GET /fascicoli/<fascicolo_id>/depositi/<deposito_id>/timeline`
- `POST /fascicoli/<fascicolo_id>/depositi/<deposito_id>/importa-ricevuta`
- `GET /fascicoli/<fascicolo_id>/depositi/<deposito_id>/evidence-pack`
- `POST /preventivi/<preventivo_id>/apri-fascicolo`
- `POST /conferimenti/<conferimento_id>/apri-fascicolo`

## Regole di acquisizione deposito

`ACQUISITO` e' ammesso solo con ricevuta o esito finale positivo del canale corretto:

- PCT/PST: esito cancelleria positivo.
- PDP: esito PDP positivo.
- PAT: esito PAT positivo.
- PTT/SIGIT: esito PTT positivo.
- SIGP/Giudice di Pace: esito SIGP o esito portale autorizzato positivo.

Accettazione PEC, consegna PEC e controlli automatici OK non bastano per dichiarare acquisito quando il canale richiede esito finale.

## Predeposito e invio

Il predeposito valuta dati, slot documentali, firme, PDF/A, dimensione, busta e canale. L'invio reale fallisce chiuso se non esiste un adapter autorizzato configurato. Una busta `.enc` prodotta come simulazione tecnica non viene dichiarata busta ministeriale reale.

## UI

La sezione `Regia Operativa` vive nel dettaglio fascicolo React e mostra dati di repository reale:

- header operativo;
- riepilogo economico/amministrativo;
- checklist dinamica;
- slot documentali;
- validazione;
- deposito e timeline ricevute;
- evidence pack quando disponibile.

Nessun dato demo o hardcoded viene usato come sostituto di dati mancanti.
