# Tranche 17A - Fatturazione nuova operational

Generato: 2026-05-07

## Route convertita

- Route: `/fatturazione/nuova`
- Stato prima: `react_bridge`
- Stato dopo: `react_operational_full`
- Manifest: `tools/react-migration/route-manifest.json`

## Endpoint JSON creati

- `GET /api/v1/ui/fatturazione/nuova`
- `POST /api/v1/ui/fatturazione/nuova`

Il GET espone `ok`, `source`, `generated_at`, `contracts`, `form`, `clients`,
`matters`, `defaults`, `fiscal_options`, `actions` e `warnings`.

Il POST accetta solo JSON, richiede sessione/CSRF, verifica
`fatturazione.scrivi`, valida campi consentiti, rifiuta campi ignoti e non
accetta importi canonici dal frontend.

## LegacyPostForm rimossi

`frontend/src/components/FatturazionePage.tsx` non usa piu'
`LegacyPostForm` nel flusso principale della nuova parcella. Il salvataggio
passa da `createFattura()` in `frontend/src/fatturazioneData.ts`, che usa
`apiPostJson`.

## Link legacy rimasti

- `/fatturazione/nuova?_legacy=1` resta solo nella sezione `Rollback tecnico`
  per assistenza o confronto con il template storico.
- I link dettaglio/PDF/XML dell'archivio `/fatturazione` restano backend/legacy
  perche' `/fatturazione` non viene completata in questa tranche e
  `/fatturazione/*` resta `legacy_operational`.

## Audit preservato

Il POST JSON registra `fatturazione.crea` tramite `get_utenti().registra_evento`
con risorsa `parcella`, identificativo parcella e origine
`react_operational_full`.

## Permessi controllati

- Lettura GET: `fatturazione.leggi`
- Creazione POST: `fatturazione.scrivi`
- CSRF: endpoint `api_v1_react.fatturazione_nuova_crea` inserito nei controlli
  browser.

## Calcolo fiscale backend

React invia solo cliente, fascicolo, date, voci, note e opzioni fiscali. Il
calcolo canonico resta in `GestioneFatturazione.crea()` e nelle proprieta'
backend di `Parcella`. Il bridge non implementa un nuovo motore contabile.

## PDF/XML/export

PDF, XML FatturaPA, export CSV, modifica, dettaglio operativo e altri
sottopercorsi `/fatturazione/*` restano sulle route legacy/backend protette.
React non genera documenti, blob o object URL.

## UI state implementati

- Loading iniziale
- Empty state senza clienti
- Saving
- Success con CTA archivio e dettaglio backend se restituito
- Validation errors
- Permission denied
- Server error
- Sezione `Rollback tecnico`

## Test eseguiti

- `python -m py_compile web/services/react_fatturazione_bridge.py web/blueprints/api_v1_react.py web/services/security_runtime.py pct/auth.py`
- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-tranche-17a-fatturazione-nuova-operational.mjs`
- `node scripts/react-migration/check-tranche-17a-no-fiscal-logic.mjs`
- `python scripts/react-migration/check-tranche-17a-fatturazione-nuova-api.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Rischi residui

- `/fatturazione` resta `react_bridge`: archivio, PDF, XML, export, dettaglio e
  modifica non sono stati migrati e devono restare protetti.
- Le parcelle derivate da preventivo mantengono il contesto economico backend
  disponibile, ma la rifinitura UX completa del prefill avanzato resta separata
  dalla promozione operativa minima di questa route.

## Rollback

Rollback tecnico immediato: aprire `/fatturazione/nuova?_legacy=1`.

Rollback codice: ripristinare lo stato manifest a `react_bridge`, rimuovere il
POST JSON `/api/v1/ui/fatturazione/nuova` e tornare al form storico solo se i
guardrail React e il gate vengono aggiornati nella stessa tranche.
