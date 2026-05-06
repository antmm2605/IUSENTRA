# Tranche React 2A - report finale

Data/ora: 2026-05-06 13:15 Europe/Rome

Branch base richiesto: `claude/legal-electronic-filing-kIxcV`

## Route migrate

- `/statistiche` -> React full
- `/audit` -> React full
- `/registro-attivita` -> React full

## Route solo fotografate

- `/utenti` -> resta `legacy_operational`
- `/profili` -> resta `legacy_operational`
- `/backup` -> resta `legacy_operational`

## File creati

- `web/services/react_statistiche_bridge.py`
- `web/services/react_audit_bridge.py`
- `frontend/src/lib/apiClient.ts`
- `frontend/src/statisticheData.ts`
- `frontend/src/auditData.ts`
- `frontend/src/components/StatistichePage.tsx`
- `frontend/src/components/StatistichePage.css`
- `frontend/src/components/AuditPage.tsx`
- `frontend/src/components/AuditPage.css`
- `scripts/react-migration/check-tranche-2a-gate.py`
- `artifacts/react-migration/tranche-2a-preflight.md`
- `artifacts/react-migration/tranche-2a-route-map.md`
- `artifacts/react-migration/tranche-2a-gate.md`
- `artifacts/react-migration/tranche-2a-report.md`

## File modificati

- `web/blueprints/api_v1_react.py`
- `web/bootstrap/react_route_gate.py`
- `web/blueprints/react_shell.py`
- `frontend/src/App.tsx`
- `frontend/scripts/check-react-contracts.mjs`
- `scripts/react-migration/check-route-gate.mjs`
- `scripts/react-migration/run-safe-react-migration.mjs`
- `tools/react-migration/route-manifest.json`
- `README.md`
- `CHANGELOG.md`
- `docs/REACT_MIGRATION_MASTER_PLAN.md`
- `pct/__init__.py`
- `setup.py`
- `Dockerfile`
- `railway.toml`
- `frontend/package.json`
- `frontend/package-lock.json`
- `web/static/react/*`

## Endpoint aggiunti

- `GET /api/v1/ui/statistiche`
- `GET /api/v1/ui/audit`
- `GET /api/v1/ui/registro-attivita`

## Gate modificato

- Rimossi da `_LEGACY_OPERATIONAL_PREFIXES` solo `/statistiche`, `/audit`, `/registro-attivita`.
- Rimossi da `_LEGACY_FIRST_PREFIXES` solo `/statistiche`, `/audit`, `/registro-attivita`.
- `?_legacy=1` resta invariato.

## Route ancora bloccate

- `/utenti`
- `/profili`
- `/backup`
- `/fatturazione`
- `/preventivi`
- `/compensi-forensi`
- `/tariffario`
- `/deposito/checklist`
- `/polisWeb`, `/pdp`, `/pat`, `/sigit`, `/sigp`, `/portali/*`
- `/impostazioni?tab=firma`

## Contratti legacy catturati

- `artifacts/react-migration/legacy-contracts/statistiche.json`
- `artifacts/react-migration/legacy-contracts/audit.json`
- `artifacts/react-migration/legacy-contracts/registro-attivita.json`
- `artifacts/react-migration/legacy-contracts/utenti.json`
- `artifacts/react-migration/legacy-contracts/profili.json`
- `artifacts/react-migration/legacy-contracts/backup.json`

## Test eseguiti

- `node scripts/react-migration/check-route-gate.mjs` -> PASS
- `node scripts/react-migration/check-ui-consistency.mjs` -> PASS
- `python scripts/react-migration/check-tranche-2a-gate.py` -> PASS
- `cd frontend && npm run test` -> PASS
- `cd frontend && npm run typecheck` -> PASS
- `cd frontend && npm run build` -> PASS

## Esiti richiesti

- `npm run test`: PASS
- `npm run typecheck`: PASS
- `npm run build`: PASS
- `check-ui-consistency`: PASS
- `check-route-gate`: PASS

## Limiti test Flask

Il test Flask usa un tenant temporaneo autenticato tramite harness esistente e verifica shell React, fallback `?_legacy=1`, blocco legacy di `/utenti`, `/profili`, `/backup` e JSON degli endpoint. Su Windows il cleanup della directory temporanea puo' lasciare handle SQLite aperti: lo script usa `ignore_cleanup_errors=True` solo per non trasformare quel cleanup in falso negativo.

## Rischi residui

- `/statistiche` non introduce una chart library: la parita' read-only viene resa con KPI, distribuzioni e record tabellari.
- Gli export restano link GET legacy e non sono duplicati nel bridge React.
- `/utenti`, `/profili` e `/backup` restano esclusi perche' collegati a POST, permessi o restore/download tecnici.

## Rollback

```bash
git apply -R artifacts/react-migration/patches/tranche-2a.backend.patch
git apply -R artifacts/react-migration/patches/tranche-2a.frontend.patch
git apply -R artifacts/react-migration/patches/tranche-2a.gate.patch
git apply -R artifacts/react-migration/patches/tranche-2a.tests.patch
```
