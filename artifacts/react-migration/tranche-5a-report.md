# Tranche 5A - Report finale

Data/ora: 2026-05-06 15:55 Europe/Rome
Branch base: claude/legal-electronic-filing-kIxcV

## Route migrate

- `/studio` React full exact.
- `/amministrazione` React full exact.

## Route preparate ma lasciate legacy

- `/impostazioni`
- `/impostazioni-studio`
- `/impostazioni/calendario`
- `/impostazioni/pagamenti`
- `/sincronizzazione-calendari`

## File creati

- `web/services/react_studio_bridge.py`
- `web/services/react_amministrazione_bridge.py`
- `frontend/src/studioData.ts`
- `frontend/src/amministrazioneData.ts`
- `frontend/src/components/StudioPage.tsx`
- `frontend/src/components/StudioPage.css`
- `frontend/src/components/AmministrazionePage.tsx`
- `frontend/src/components/AmministrazionePage.css`
- `scripts/react-migration/check-tranche-5a-gate.py`
- `scripts/react-migration/check-tranche-5a-secrets.mjs`
- `artifacts/react-migration/tranche-5a-route-map.md`
- `artifacts/react-migration/tranche-5a-report.md`

## File modificati

- `web/blueprints/api_v1_react.py`
- `web/bootstrap/react_route_gate.py`
- `web/blueprints/react_shell.py`
- `frontend/src/App.tsx`
- `frontend/scripts/check-react-contracts.mjs`
- `scripts/react-migration/check-route-gate.mjs`
- `scripts/react-migration/run-safe-react-migration.mjs`
- `tools/react-migration/route-manifest.json`
- `CHANGELOG.md`
- `README.md`
- `docs/REACT_MIGRATION_MASTER_PLAN.md`
- `pct/__init__.py`
- `setup.py`
- `Dockerfile`
- `railway.toml`
- `frontend/package.json`
- `frontend/package-lock.json`

## Endpoint aggiunti

- `GET /api/v1/ui/studio`
- `GET /api/v1/ui/amministrazione`

## Gate modificato

- Sbloccati solo `/studio` exact e `/amministrazione` exact.
- Protetti `/studio/*` e `/amministrazione/*`.
- Confermati legacy `/impostazioni`, `/impostazioni-studio`, `/impostazioni/calendario`, `/impostazioni/pagamenti`, `/impostazioni?tab=firma`, `/sincronizzazione-calendari`.

## Route ancora bloccate

- Impostazioni e sottoroute sensibili.
- Calendari e sincronizzazione calendari.
- Pagamenti e provider.
- Economico, mandato, documentale e telematico non toccati da questa tranche.

## Contratti legacy catturati

- `artifacts/react-migration/legacy-contracts/studio.json`
- `artifacts/react-migration/legacy-contracts/amministrazione.json`
- `artifacts/react-migration/legacy-contracts/impostazioni.json`
- `artifacts/react-migration/legacy-contracts/impostazioni-studio.json`
- `artifacts/react-migration/legacy-contracts/impostazioni__calendario.json`
- `artifacts/react-migration/legacy-contracts/impostazioni__pagamenti.json`
- `artifacts/react-migration/legacy-contracts/sincronizzazione-calendari.json`

## Permessi verificati

- `/studio`: stesso perimetro dell'alias legacy, sessione Flask richiesta.
- `/amministrazione`: vincolo legacy `utenti.leggi`, senza bypass amministrativo via API key.

## POST legacy preservati

- Nessun POST legacy modificato.
- Nessun nuovo endpoint POST creato.
- Nessun fetch POST introdotto.

## Impostazioni, calendari e pagamenti

- Impostazioni lasciate legacy.
- Calendari lasciati legacy.
- Pagamenti lasciati legacy.
- Nessun bridge operativo impostazioni creato.
- Nessuna configurazione riservata serializzata nel payload React.

## Controlli

- Anti-segreti: OK (`node scripts/react-migration/check-tranche-5a-secrets.mjs`).
- UI consistency: OK (`node scripts/react-migration/check-ui-consistency.mjs`).
- Route gate: OK (`node scripts/react-migration/check-route-gate.mjs`).
- Gate Flask 5A: OK (`python scripts/react-migration/check-tranche-5a-gate.py`).
- Contratti React: OK (`node frontend/scripts/check-react-contracts.mjs`).
- Runner 5A: OK (`ALLOW_DIRTY=1 node scripts/react-migration/run-safe-react-migration.mjs --tranche=5a`, usato per non toccare modifiche runtime non pertinenti gia' presenti nel worktree).

## Test frontend

- `npm run test`: OK.
- `npm run typecheck`: OK.
- `npm run build`: OK.

## Limiti test Flask

- Il test harness ha consentito autenticazione con tenant admin seeded.
- Verificati shell React, bypass `?_legacy=1`, subpath legacy, impostazioni legacy, endpoint JSON e POST non intercettati.

## Rischi residui

- Le route impostazioni restano volutamente legacy per preservare configurazioni riservate e flussi locali.
- Il worktree locale contiene modifiche dati/runtime non pertinenti alla tranche, non incluse nelle patch 5A.

## Patch generate

- `artifacts/react-migration/patches/tranche-5a.backend.patch`
- `artifacts/react-migration/patches/tranche-5a.frontend.patch`
- `artifacts/react-migration/patches/tranche-5a.gate.patch`
- `artifacts/react-migration/patches/tranche-5a.tests.patch`
- `artifacts/react-migration/patches/tranche-5a.reports.patch`

## Rollback

```bash
git apply -R artifacts/react-migration/patches/tranche-5a.backend.patch
git apply -R artifacts/react-migration/patches/tranche-5a.frontend.patch
git apply -R artifacts/react-migration/patches/tranche-5a.gate.patch
git apply -R artifacts/react-migration/patches/tranche-5a.tests.patch
```
