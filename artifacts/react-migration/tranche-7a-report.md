# Tranche 7A - Preventivi React full

Data/ora: 2026-05-06 17:46:23 +02:00

Branch base: `claude/legal-electronic-filing-kIxcV`

## Route migrate

- `/preventivi`
- `/preventivi/nuovo`
- `/preventivi/conferimento/nuovo`

## Route preparate ma lasciate legacy

- `/preventivi/wizard`
- `/preventivi/*`
- `/preventivi/p/*`
- `/preventivi/conferimento/*` diverso da `/preventivi/conferimento/nuovo`
- `/compensi-forensi`
- `/tariffario`

## File creati

- `web/services/react_preventivi_bridge.py`
- `frontend/src/preventiviData.ts`
- `frontend/src/components/PreventiviPage.tsx`
- `frontend/src/components/PreventiviPage.css`
- `scripts/react-migration/check-tranche-7a-gate.py`
- `scripts/react-migration/check-tranche-7a-secrets.mjs`
- `scripts/react-migration/check-tranche-7a-no-compensi-logic.mjs`
- `scripts/react-migration/check-tranche-7a-no-document-generation.mjs`
- `artifacts/react-migration/tranche-7a-route-map.md`
- `artifacts/react-migration/tranche-7a-report.md`

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
- `docs/REACT_MIGRATION_MASTER_PLAN.md`
- `CHANGELOG.md`
- `pct/__init__.py`
- `setup.py`
- `Dockerfile`
- `railway.toml`
- `frontend/package.json`
- `frontend/package-lock.json`
- `web/static/react/.vite/manifest.json`
- `web/static/react/index.html`
- `web/static/react/assets/*`

## Endpoint aggiunti

- `GET /api/v1/ui/preventivi`
- `GET /api/v1/ui/preventivi/nuovo`
- `GET /api/v1/ui/preventivi/conferimento/nuovo`

## Gate modificato

- `/preventivi` exact ora puo servire la shell React.
- `/preventivi/nuovo` ora puo servire la shell React.
- `/preventivi/conferimento/nuovo` ora puo servire la shell React.
- `?_legacy=1` resta supportato.
- I POST restano fuori dal gate React.

## Route ancora bloccate

- `/preventivi/wizard`
- `/preventivi/p/*`
- `/preventivi/conferimento/*` diverso da `/preventivi/conferimento/nuovo`
- ogni altro `/preventivi/*`
- `/compensi-forensi`
- `/tariffario`
- route documentali, telematiche, impostazioni e fatturazione wildcard gia bloccate.

## Contratti legacy catturati

- `artifacts/react-migration/legacy-contracts/preventivi.json`
- `artifacts/react-migration/legacy-contracts/preventivi__nuovo.json`
- `artifacts/react-migration/legacy-contracts/preventivi__conferimento__nuovo.json`
- `artifacts/react-migration/legacy-contracts/preventivi__wizard.json`
- `artifacts/react-migration/legacy-contracts/preventivi__detail.json`
- `artifacts/react-migration/legacy-contracts/compensi-forensi.json`
- `artifacts/react-migration/legacy-contracts/tariffario.json`

## Permessi verificati

- I route handler legacy usano `_richiedi_login`.
- Gli endpoint React usano `_richiedi_auth` e richiedono un utente Flask in sessione.
- Non e stato rilevato un permesso granulare aggiuntivo nei tre handler GET/POST migrati.
- API key senza sessione non sblocca i dati mandato.

## Preservazioni legacy

- POST `/preventivi/nuovo` preservato sul legacy.
- POST `/preventivi/conferimento/nuovo` preservato sul legacy.
- POST `/preventivi` non intercettato dal gate React.
- Wizard compensi lasciato legacy.
- Compensi forensi lasciato legacy.
- Tariffario lasciato legacy.
- PDF/DOCX lasciati legacy.
- Conversione parcella lasciata legacy.
- Apertura fascicolo da incarico lasciata legacy.

## Controlli

- Anti-segreti: OK (`artifacts/react-migration/tranche-7a-secrets.md`).
- Anti-calcolo compensi frontend: OK (`artifacts/react-migration/tranche-7a-no-compensi-logic.md`).
- Anti-generazione documenti: OK (`artifacts/react-migration/tranche-7a-no-document-generation.md`).
- `check-ui-consistency`: OK (`artifacts/react-migration/ui-consistency.md`).
- `check-route-gate`: OK (`artifacts/react-migration/route-gate.md`).
- `check-tranche-7a-gate`: OK (`artifacts/react-migration/tranche-7a-gate.md`).

## Test eseguiti

- `node scripts/react-migration/run-safe-react-migration.mjs --tranche=7a` con `ALLOW_DIRTY=1`: OK. Il working tree era gia sporco prima della tranche.
- `cd frontend && npm run test`: OK.
- `cd frontend && npm run typecheck`: OK.
- `cd frontend && npm run build`: OK.
- `node scripts/react-migration/check-ui-consistency.mjs`: OK.
- `node scripts/react-migration/check-tranche-7a-secrets.mjs`: OK.
- `node scripts/react-migration/check-tranche-7a-no-compensi-logic.mjs`: OK.
- `node scripts/react-migration/check-tranche-7a-no-document-generation.mjs`: OK.
- `python scripts/react-migration/check-tranche-7a-gate.py`: OK.

## Limiti dei test Flask

- Il test harness ha verificato il gate con sessione autenticata sintetica.
- La cattura dei contratti legacy non autentica l'utente e quindi registra redirect/login quando il legacy lo richiede.
- Non sono stati inventati bypass di autenticazione.

## Rischi residui

- Il working tree conteneva modifiche non correlate prima della tranche; non sono state revertite.
- La build React aggiorna gli asset hashati in `web/static/react/assets`.
- `rg.exe` non era eseguibile nell'ambiente locale per `Accesso negato`; l'analisi route e stata completata con `Select-String`.

## Patch generate

- `artifacts/react-migration/patches/tranche-7a.backend.patch`
- `artifacts/react-migration/patches/tranche-7a.frontend.patch`
- `artifacts/react-migration/patches/tranche-7a.gate.patch`
- `artifacts/react-migration/patches/tranche-7a.tests.patch`
- `artifacts/react-migration/patches/tranche-7a.reports.patch`

## Rollback

```bash
git apply -R artifacts/react-migration/patches/tranche-7a.backend.patch
git apply -R artifacts/react-migration/patches/tranche-7a.frontend.patch
git apply -R artifacts/react-migration/patches/tranche-7a.gate.patch
git apply -R artifacts/react-migration/patches/tranche-7a.tests.patch
```
