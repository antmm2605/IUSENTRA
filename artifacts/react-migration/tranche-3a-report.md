# Report Tranche 3A migrazione React

Data/ora: 2026-05-06T13:55:00+02:00
Branch base: claude/legal-electronic-filing-kIxcV
Branch locale: Codex/legal-electronic-filing-kIxcV

## Route migrate

- `/utenti`: React full sul GET ufficiale.
- `/utenti/nuovo`: React sul GET ufficiale; il submit resta `POST /utenti/nuovo` legacy.
- `/profili`: React full sul GET ufficiale.

## Route preparate ma lasciate legacy

- `/backup`: bridge/API/pagina React read-only preparatoria, ma gate ancora legacy per `/backup` e sottoroute.

## File creati

- `web/services/react_utenti_bridge.py`
- `web/services/react_profili_bridge.py`
- `web/services/react_backup_bridge.py`
- `frontend/src/utentiData.ts`
- `frontend/src/profiliData.ts`
- `frontend/src/backupData.ts`
- `frontend/src/components/UtentiPage.tsx`
- `frontend/src/components/UtentiPage.css`
- `frontend/src/components/ProfiliPage.tsx`
- `frontend/src/components/ProfiliPage.css`
- `frontend/src/components/BackupPage.tsx`
- `frontend/src/components/BackupPage.css`
- `frontend/src/ui/LegacyPostForm.tsx`
- `scripts/react-migration/check-tranche-3a-gate.py`
- `artifacts/react-migration/legacy-contracts/utenti__nuovo.json`
- `artifacts/react-migration/tranche-3a-route-map.md`
- `artifacts/react-migration/tranche-3a-gate.md`

## File modificati

- `web/blueprints/api_v1_react.py`
- `web/bootstrap/react_route_gate.py`
- `web/blueprints/react_shell.py`
- `frontend/src/App.tsx`
- `frontend/src/ui/ui.css`
- `frontend/scripts/check-react-contracts.mjs`
- `scripts/react-migration/check-route-gate.mjs`
- `scripts/react-migration/run-safe-react-migration.mjs`
- `tools/react-migration/route-manifest.json`
- `frontend/package.json`
- `frontend/package-lock.json`
- `pct/__init__.py`
- `setup.py`
- `Dockerfile`
- `railway.toml`
- `README.md`
- `CHANGELOG.md`
- `docs/REACT_MIGRATION_MASTER_PLAN.md`
- `web/static/react/*`

## Endpoint aggiunti

- `GET /api/v1/ui/utenti`
- `GET /api/v1/ui/profili`
- `GET /api/v1/ui/backup`

## Gate modificato

- Rimossi solo `/utenti` e `/profili` dai blocchi legacy operativi.
- Aggiunta protezione nested per `/utenti/*` eccetto `/utenti/nuovo`.
- Aggiunta protezione nested per `/profili/*`.
- Confermata protezione legacy per `/backup` e `/backup/*`.
- `?_legacy=1` resta invariato.

## Route ancora bloccate

- `/backup`
- `/fatturazione`
- `/incassi-pagamenti`
- `/preventivi`
- `/compensi-forensi`
- `/tariffario`
- `/deposito/checklist`
- `/impostazioni`
- route telematiche e portali.

## Contratti legacy catturati

- `artifacts/react-migration/legacy-contracts/utenti.json`
- `artifacts/react-migration/legacy-contracts/utenti__nuovo.json`
- `artifacts/react-migration/legacy-contracts/profili.json`
- `artifacts/react-migration/legacy-contracts/backup.json`

## Permessi verificati

- `/utenti` e `/profili`: permesso legacy `utenti.leggi`.
- `/utenti/nuovo`: permesso legacy di scrittura preservato sul POST Flask.
- `/backup`: endpoint React read-only protetto con `backup.leggi`; operazioni tecniche restano legacy.

## POST legacy preservati

- `POST /utenti/nuovo` resta form HTML verso legacy, senza fetch POST.
- POST annidati utenti/profili restano legacy.
- POST backup restano legacy e non vengono intercettati dal gate React.

## Azioni backup lasciate legacy

- Esecuzione backup.
- Verifica integrita.
- Download.
- Eliminazione.
- Ripristino.

## Test eseguiti

- `node scripts/react-migration/run-safe-react-migration.mjs --tranche=3a` con `ALLOW_DIRTY=1` per baseline runtime sporca preesistente.
- `node scripts/react-migration/check-route-gate.mjs`
- `node scripts/react-migration/check-ui-consistency.mjs`
- `python scripts/react-migration/check-tranche-3a-gate.py`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Esiti

- `npm run test`: OK.
- `npm run typecheck`: OK.
- `npm run build`: OK.
- `check-ui-consistency`: OK, 0 violazioni.
- `check-route-gate`: OK, 0 violazioni.
- `check-tranche-3a-gate`: OK.

## Limiti test Flask

- Il test harness consente autenticazione tramite tenant admin simulato; non sono stati necessari bypass inventati.
- I POST sono verificati come non intercettati dal gate React; la validazione business resta dei route handler legacy esistenti.

## Rischi residui

- `/backup` e tutte le azioni tecniche restano volutamente legacy fino a una tranche dedicata.
- Le route annidate utenti/profili restano legacy per evitare di duplicare scritture RBAC.
- La working tree contiene file runtime/data sporchi preesistenti non correlati, non inclusi nelle patch di tranche.

## Rollback

```bash
git apply -R artifacts/react-migration/patches/tranche-3a.backend.patch
git apply -R artifacts/react-migration/patches/tranche-3a.frontend.patch
git apply -R artifacts/react-migration/patches/tranche-3a.gate.patch
git apply -R artifacts/react-migration/patches/tranche-3a.tests.patch
```
