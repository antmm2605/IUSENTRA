# Tranche 6A - Report finale

Data/ora: 2026-05-06 16:30:14 +02:00

Branch base richiesto: `claude/legal-electronic-filing-kIxcV`

Branch locale: `Codex/legal-electronic-filing-kIxcV`

## Route migrate

- `/fatturazione` React full.
- `/fatturazione/nuova` React full su GET, submit HTML verso POST legacy.
- `/incassi-pagamenti` React full.

## Route preparate ma lasciate legacy

- `/fatturazione/*`
- `/fatturazione/*/modifica`
- `/fatturazione/*/pdf`
- `/fatturazione/*/xml`
- `/export/fatturazione.csv`
- `/impostazioni/pagamenti`
- `/preventivi`
- `/compensi-forensi`
- `/tariffario`

## File creati

- `web/services/react_fatturazione_bridge.py`
- `web/services/react_incassi_pagamenti_bridge.py`
- `frontend/src/fatturazioneData.ts`
- `frontend/src/incassiPagamentiData.ts`
- `frontend/src/components/FatturazionePage.tsx`
- `frontend/src/components/FatturazionePage.css`
- `frontend/src/components/IncassiPagamentiPage.tsx`
- `frontend/src/components/IncassiPagamentiPage.css`
- `scripts/react-migration/check-tranche-6a-gate.py`
- `scripts/react-migration/check-tranche-6a-secrets.mjs`
- `scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs`
- `artifacts/react-migration/tranche-6a-route-map.md`
- `artifacts/react-migration/tranche-6a-gate.md`
- `artifacts/react-migration/tranche-6a-secrets.md`
- `artifacts/react-migration/tranche-6a-no-fiscal-logic.md`
- `artifacts/react-migration/legacy-contracts/fatturazione__detail.json`
- `artifacts/react-migration/legacy-contracts/fatturazione__nuova.json`

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
- `web/static/react/*`

## Endpoint aggiunti

- `GET /api/v1/ui/fatturazione`
- `GET /api/v1/ui/fatturazione/nuova`
- `GET /api/v1/ui/incassi-pagamenti`

## Gate modificato

- Sbloccate solo le exact React `/fatturazione`, `/fatturazione/nuova` e `/incassi-pagamenti`.
- Aggiunte protezioni per `/fatturazione/*` diverso da `/fatturazione/nuova`.
- Aggiunte protezioni per `/incassi-pagamenti/*`.
- Confermate legacy `/impostazioni/pagamenti`, `/preventivi`, `/compensi-forensi` e `/tariffario`.
- Conservato supporto `?_legacy=1`.

## Route ancora bloccate

- Dettagli, modifica, PDF, XML ed export di fatturazione.
- Configurazione provider pagamenti.
- Preventivi, compensi forensi e tariffario.
- Route documentali, impostazioni e telematiche non appartenenti alla tranche.

## Contratti legacy catturati

- `artifacts/react-migration/legacy-contracts/fatturazione.json`
- `artifacts/react-migration/legacy-contracts/fatturazione__nuova.json`
- `artifacts/react-migration/legacy-contracts/fatturazione__detail.json`
- `artifacts/react-migration/legacy-contracts/incassi-pagamenti.json`
- `artifacts/react-migration/legacy-contracts/impostazioni__pagamenti.json`
- `artifacts/react-migration/legacy-contracts/preventivi.json`
- `artifacts/react-migration/legacy-contracts/compensi-forensi.json`
- `artifacts/react-migration/legacy-contracts/tariffario.json`

## Permessi verificati

- Le route legacy economiche risultano protette da sessione Flask.
- Gli endpoint React richiedono `_richiedi_auth` e sessione utente corrente, senza accesso economico via API key.
- Non sono stati modificati RBAC, permessi o helper legacy.

## POST legacy preservati

- `POST /fatturazione/nuova` resta nel blueprint Flask legacy.
- I form React usano submit HTML verso route legacy, non fetch POST.
- Nessun endpoint POST, delete o update nuovo e' stato creato.

## PDF/XML/export lasciati legacy

- Generazione e download PDF restano legacy.
- Generazione e download XML restano legacy.
- Export CSV resta legacy.
- La UI React mostra solo link legacy se esposti dal bridge.

## Provider pagamento lasciati legacy

- La configurazione provider resta su `/impostazioni/pagamenti?_legacy=1`.
- Lo stato provider e' esposto solo come label sicura.
- Nessun dato riservato provider viene serializzato nel payload React.

## Preventivi/compensi/tariffario lasciati legacy

- `/preventivi` resta `legacy_operational`.
- `/compensi-forensi` resta `legacy_operational`.
- `/tariffario` resta `legacy_operational`.

## Esito controllo anti-segreti

- `node scripts/react-migration/check-tranche-6a-secrets.mjs`: PASS.
- Report: `artifacts/react-migration/tranche-6a-secrets.md`.

## Esito controllo anti-calcolo frontend

- `node scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs`: PASS.
- Report: `artifacts/react-migration/tranche-6a-no-fiscal-logic.md`.

## Test eseguiti

- `node scripts/react-migration/check-route-gate.mjs`: PASS.
- `node scripts/react-migration/check-ui-consistency.mjs`: PASS.
- `node scripts/react-migration/check-tranche-6a-secrets.mjs`: PASS.
- `node scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs`: PASS.
- `python scripts/react-migration/check-tranche-6a-gate.py`: PASS.
- `cd frontend && npm run test`: PASS.
- `cd frontend && npm run typecheck`: PASS.
- `cd frontend && npm run build`: PASS.

## Esiti richiesti

- `npm run test`: PASS.
- `npm run typecheck`: PASS.
- `npm run build`: PASS.
- `check-ui-consistency`: PASS.
- `check-route-gate`: PASS.
- `check-tranche-6a-gate`: PASS.

## Limiti test Flask

- Il test harness ha consentito autenticazione con `test_client`, quindi non sono stati applicati bypass o skip.

## Rischi residui

- La lista React non invoca la scrittura legacy `aggiorna_scadute()` eseguita dal GET storico di `/fatturazione`; gli stati mostrati sono quelli gia' persistiti dal repository.
- Le operazioni avanzate economiche restano volutamente in legacy fino a parita' funzionale completa.
- Il runner finale viene eseguito con `ALLOW_DIRTY=1` per la presenza di modifiche runtime preesistenti fuori perimetro nei JSON di `data/`, non incluse nella tranche.

## Rollback

```bash
git apply -R artifacts/react-migration/patches/tranche-6a.backend.patch
git apply -R artifacts/react-migration/patches/tranche-6a.frontend.patch
git apply -R artifacts/react-migration/patches/tranche-6a.gate.patch
git apply -R artifacts/react-migration/patches/tranche-6a.tests.patch
```
