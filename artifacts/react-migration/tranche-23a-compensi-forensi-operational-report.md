# Tranche 23A - Compensi forensi React operativo reale

## Route convertita

- `/compensi-forensi`

## Stato prima

- `react_bridge`
- `/compensi-forensi/*` legacy/protetto

## Stato dopo

- `/compensi-forensi`: `react_operational_full`
- `/compensi-forensi/*`: legacy/protetto

## LegacyPostForm rimossi

- Nessun `LegacyPostForm` nel flusso principale.
- Il calcolo usa `calculateCompensiForensi()` e `apiPostJson`.

## Link legacy rimasti e perche

- `?_legacy=1` resta solo rollback tecnico.

## Endpoint JSON creati

- `GET /api/v1/ui/compensi-forensi`
- `POST /api/v1/ui/compensi-forensi/calcola`

## Permessi controllati

- `_richiedi_auth` su GET e POST.
- Permesso lettura/calcolo fatturazione-compensi prima di esporre dati o calcolare.

## Audit preservato

- Il calcolo registra audit `compensi_forensi.calcola` quando disponibile.

## UI state implementati

- Loading, calculating, saving, success, error, validation, permission denied e empty state.

## Calcolo backend preservato

- React invia solo input.
- Risultato e importi mostrati arrivano dalla risposta backend.

## DM55 backend preservato

- Nessuna tabella, scaglione, coefficiente o formula DM55 in React.

## Risultato backend mostrato

- Il pannello risultato mostra metadati, note, warning e valori gia calcolati dal backend.

## Salva log / crea preventivo

- Le azioni restano disabilitate/non supportate quando il legacy non fornisce un servizio canonico JSON.

## PDF/DOCX non introdotti

- Nessuna generazione o download documento in React.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-tranche-23a-compensi-forensi-operational.mjs`
- `node scripts/react-migration/check-tranche-23a-no-compensi-frontend-calculation.mjs`
- `python scripts/react-migration/check-tranche-23a-compensi-forensi-api.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Rischi residui

- Harness Flask autenticato non disponibile negli script statici.

## Rollback

- `GET /compensi-forensi?_legacy=1` resta disponibile come rollback tecnico.
