# Tranche 14A - Utenti React operativo reale

## Route convertita

- `/utenti`

## Stato prima

- `/utenti`: `react_operational_partial`
- `/utenti/nuovo`: `react_operational_full`
- Le route annidate `/utenti/*` diverse da `/utenti/nuovo` restavano protette dal gate.

## Stato dopo

- `/utenti`: `react_operational_full`
- `/utenti/nuovo`: `react_operational_full`
- Nessun altro subpath `/utenti/*` e' stato sbloccato.

## LegacyPostForm rimossi

- `frontend/src/components/UtentiPage.tsx` non usa `LegacyPostForm`.
- Le azioni principali non puntano a `?_legacy=1`.
- Il fallback legacy resta solo nel pannello "Rollback tecnico".

## Endpoint JSON creati

- `GET /api/v1/ui/utenti`
- `POST /api/v1/ui/utenti/<id_utente>/stato`
- `POST /api/v1/ui/utenti/<id_utente>/ruolo`
- `POST /api/v1/ui/utenti/<id_utente>/reset-password`
- `POST /api/v1/ui/utenti/<id_utente>/profilo`

## Permessi controllati

- Lettura: `utenti.leggi`.
- Scritture: `utenti.scrivi`.
- I permessi operativi sono dichiarati nel payload React con `canCreate`, `canUpdate`, `canDisable`, `canResetPassword`, `canChangeRole`.
- Le API impediscono modifica non autorizzata, auto-disabilitazione e rimozione/disabilitazione dell'ultimo amministratore attivo.

## Audit preservato

- Creazione: `utenti.crea`.
- Stato account: `utenti.modifica_stato`.
- Ruolo: `utenti.modifica_ruolo`.
- Reset credenziale: `utenti.reset_password`.
- Profilo minimo: `utenti.modifica_profilo`.

## UI state implementati

- Loading.
- Saving.
- Success.
- Errori di validazione.
- Permesso negato.
- Errore server/rete.
- Empty state.
- Dirty state su profilo e ruolo.
- Conferma esplicita per disabilitazione account e reset credenziale.

## Azioni utente convertite

- Cambio ruolo: API JSON `POST /api/v1/ui/utenti/<id_utente>/ruolo`.
- Stato account: API JSON `POST /api/v1/ui/utenti/<id_utente>/stato`.
- Reset credenziale: API JSON `POST /api/v1/ui/utenti/<id_utente>/reset-password`; la credenziale temporanea non viene restituita.
- Profilo minimo: API JSON `POST /api/v1/ui/utenti/<id_utente>/profilo`.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs` - OK.
- `node scripts/react-migration/check-no-fake-react-full.mjs` - OK.
- `node scripts/react-migration/check-tranche-14a-utenti-operational.mjs` - OK.
- `python scripts/react-migration/check-tranche-14a-utenti-api.py` - OK.
- `cd frontend && npm run test` - OK.
- `cd frontend && npm run typecheck` - OK.
- `cd frontend && npm run build` - OK.

## Rischi residui

- Il rollback legacy `/utenti?_legacy=1` resta disponibile per confronto e recupero tecnico.
- Le route annidate legacy `/utenti/<id>/...` non sono state convertite in questa tranche e restano protette dal gate.

## Rollback

- Ripristinare lo status manifest di `/utenti` a `react_operational_partial`.
- Ripristinare `UtentiPage` e `utentiData` alla vista descrittiva precedente.
- Mantenere `/utenti?_legacy=1` come percorso Flask operativo durante il rollback.
