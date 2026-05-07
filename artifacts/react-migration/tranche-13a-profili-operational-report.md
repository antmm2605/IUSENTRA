# Tranche 13A - Profili React operativo

## Route convertita

- Route pubblica: `/profili`
- Shell React: `frontend/src/App.tsx` serve `ProfiliPage`
- Stato prima: `react_bridge`
- Stato dopo: `react_operational_full`

## Flusso legacy

- `LegacyPostForm` rimosso dal flusso principale di `ProfiliPage`.
- Il link `?_legacy=1` resta disponibile solo nel pannello "Rollback tecnico".
- Nessuna CTA primaria punta al fallback legacy.

## Endpoint JSON

- `GET /api/v1/ui/profili`
  - legge ruoli, permessi, matrice e override reali dal manager legacy;
  - applica autenticazione e permesso `utenti.leggi`;
  - non espone password, hash, token, session token o API key.
- `POST /api/v1/ui/profili`
  - salva override permessi via JSON;
  - applica autenticazione, CSRF/sessione e permesso `utenti.scrivi`;
  - valida payload e campi ammessi;
  - impedisce escalation non autorizzata;
  - riusa il manager legacy senza duplicare RBAC.

## Permessi e audit

- Lettura: `utenti.leggi`.
- Scrittura: `utenti.scrivi` piu controllo dei permessi assegnati come extra.
- Audit preservato: evento `utenti.aggiorna_permessi` registrato dal manager legacy.

## UI implementata

- Stati coperti: loading, saving, success, error, validation, permission denied, empty state.
- Dati reali: ruoli, utenti associati ai ruoli, permessi, matrice ruolo/permesso e override utente.
- Salvataggio: `saveProfiliPermissions()` via `apiPostJson`.
- Contratti dichiarati dal bridge:
  - `mock_fallback: false`
  - `writes: "json_api"`
  - `route_owner: "react_shell"`
  - `operational: true`

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs` - OK
- `node scripts/react-migration/check-no-fake-react-full.mjs` - OK
- `node scripts/react-migration/check-tranche-13a-profili-operational.mjs` - OK
- `python scripts/react-migration/check-tranche-13a-profili-api.py` - OK
- `cd frontend && npm run test` - OK
- `cd frontend && npm run typecheck` - OK
- `cd frontend && npm run build` - OK

## Rischi residui

- Il rollback legacy resta disponibile per intervento tecnico esplicito su `/profili?_legacy=1`.
- La modifica non migra altre route e non elimina il template legacy.

## Rollback

- Ripristinare lo stato manifest di `/profili` a `react_bridge`.
- Usare `/profili?_legacy=1` per accedere al template legacy durante il rollback tecnico.
- Revertire bridge, endpoint POST JSON e bundle React della tranche se serve annullare la promozione.
