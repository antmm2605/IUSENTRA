# Tranche 25A - Audit e registro attivita React operativo reale

## Route convertite

- `/audit`
- `/registro-attivita`

## Stato prima

- `react_operational_partial`

## Stato dopo

- `/audit`: `react_operational_full`
- `/registro-attivita`: `react_operational_full`

## Endpoint JSON creati

- `GET /api/v1/ui/audit`
- `GET /api/v1/ui/registro-attivita`
- `GET /api/v1/ui/audit/<id_evento>`

## LegacyPostForm rimossi

- Nessun `LegacyPostForm` nel flusso principale.

## Link legacy rimasti e perche

- `?_legacy=1` resta solo rollback tecnico.

## Payload sensibili redatti

- Il bridge sanifica payload, dettagli e metadati prima di restituirli a React.
- Password, hash, token, API key, secret e stack trace sono redatti.

## Export backend preservato

- Export resta link backend sicuro quando presente.

## Permessi controllati

- `_richiedi_auth` e permesso lettura audit sui GET.
- Azioni mutative restano disabilitate se il backend legacy non le supporta.

## UI state implementati

- Loading, saving, success, error, empty state e dettaglio evento JSON.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-tranche-25a-audit-operational.mjs`
- `node scripts/react-migration/check-tranche-25a-no-sensitive-audit-leak.mjs`
- `python scripts/react-migration/check-tranche-25a-audit-api.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Rischi residui

- Harness Flask autenticato non disponibile negli script statici.

## Rollback

- `GET /audit?_legacy=1` e `GET /registro-attivita?_legacy=1` restano disponibili come rollback tecnico.
