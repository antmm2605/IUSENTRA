# Tranche 22A - Incassi e pagamenti React operativo reale

## Route convertita

- `/incassi-pagamenti`

## Stato prima

- `react_bridge`
- `/impostazioni/pagamenti` legacy operativo/protetto

## Stato dopo

- `/incassi-pagamenti`: `react_operational_full`
- `/incassi-pagamenti/*`: legacy/protetto
- `/impostazioni/pagamenti`: legacy/protetto

## LegacyPostForm rimossi

- Nessun `LegacyPostForm` nel flusso principale React.
- Le azioni principali passano da `frontend/src/incassiPagamentiData.ts` e `apiPostJson`.

## Link legacy rimasti e perche

- `/impostazioni/pagamenti?_legacy=1` resta solo come "Impostazioni provider legacy" / rollback tecnico.
- Non e una CTA primaria operativa.

## Endpoint JSON creati

- `GET /api/v1/ui/incassi-pagamenti`
- `POST /api/v1/ui/incassi-pagamenti/incasso`
- `POST /api/v1/ui/incassi-pagamenti/<id_pagamento>/stato`
- `POST /api/v1/ui/incassi-pagamenti/<id_pagamento>/collega`
- `POST /api/v1/ui/incassi-pagamenti/<id_pagamento>/link-pagamento`

## Permessi controllati

- Lettura con `_richiedi_auth` e permesso fatturazione/incassi.
- Azioni mutative con sessione, CSRF e permesso scrittura.

## Audit preservato

- Registrazione incasso, cambio stato e link pagamento producono audit applicativo quando il manager/backend lo supporta.

## UI state implementati

- Loading, saving, success, error, validation, empty state e warning provider.

## Azioni pagamento JSON supportate

- Registrazione incasso manuale.
- Cambio stato pagamento.
- Recupero/generazione link pagamento via backend.
- Collegamento fattura esposto come non supportato quando il legacy non fornisce azione canonica.

## Provider config lasciata legacy

- React espone solo stato provider sicuro.
- Configurazioni provider restano in `/impostazioni/pagamenti?_legacy=1`.

## Webhook lasciati legacy

- Webhook e segreti restano backend/legacy.

## Segreti non esposti

- Nessun provider secret, webhook secret, API key, token provider o dato carta nel payload React.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-tranche-22a-incassi-pagamenti-operational.mjs`
- `node scripts/react-migration/check-tranche-22a-no-provider-secrets.mjs`
- `python scripts/react-migration/check-tranche-22a-incassi-pagamenti-api.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Rischi residui

- Harness Flask autenticato non disponibile negli script statici: le verifiche runtime restano coperte dai controlli statici e dal deploy.

## Rollback

- `GET /incassi-pagamenti?_legacy=1` resta disponibile come rollback tecnico.
