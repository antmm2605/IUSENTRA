# Tranche 9A - Report finale

- Data/ora: 2026-05-06 19:07:11 +02:00
- Branch base dichiarato: `claude/legal-electronic-filing-kIxcV`
- Branch di lavoro: `Codex/legal-electronic-filing-kIxcV`
- Versione applicativa: `2.198.96`

## 1. Route migrate

- `/template-atti`: React full come dashboard/catalogo documentale.
- `/template-atti/catalogo`: React full come catalogo template con soli metadati.
- `/redazione-atti`: React full come superficie operativa controllata.

## 2. Route preparate ma lasciate legacy

- `/template-atti/nuovo`: legacy operational, editor/POST legacy preservati.
- `/template-atti/*`: legacy operational salvo `/template-atti/catalogo`.
- `/redazione-atti/*`: legacy operational.
- `/checklist`: legacy operational.
- `/deposito/checklist`: legacy operational.
- `/giurisprudenza`: legacy operational.
- `/legal-intelligence`: legacy operational.
- `/ricerca-legale`, route telematiche, impostazioni e famiglie gia' bloccate: nessuno sblocco aggiuntivo.

## 3. File creati

- `web/services/react_template_atti_bridge.py`
- `web/services/react_redazione_atti_bridge.py`
- `frontend/src/templateAttiData.ts`
- `frontend/src/redazioneAttiData.ts`
- `frontend/src/components/TemplateAttiPage.tsx`
- `frontend/src/components/TemplateAttiPage.css`
- `frontend/src/components/RedazioneAttiPage.tsx`
- `frontend/src/components/RedazioneAttiPage.css`
- `scripts/react-migration/check-tranche-9a-gate.py`
- `scripts/react-migration/check-tranche-9a-secrets.mjs`
- `scripts/react-migration/check-tranche-9a-no-document-raw.mjs`
- `scripts/react-migration/check-tranche-9a-no-legal-generation.mjs`
- `scripts/react-migration/check-tranche-9a-no-document-generation.mjs`
- `scripts/react-migration/check-tranche-9a-open-design.mjs`
- `artifacts/react-migration/tranche-9a-route-map.md`
- `artifacts/react-migration/tranche-9a-open-design.md`
- `artifacts/react-migration/tranche-9a-report.md`

## 4. File modificati

- `web/blueprints/api_v1_react.py`
- `web/bootstrap/react_route_gate.py`
- `web/blueprints/react_shell.py`
- `tools/react-migration/route-manifest.json`
- `frontend/src/App.tsx`
- `frontend/scripts/check-react-contracts.mjs`
- `frontend/src/theme/impeccable-open-design.css`
- `frontend/src/ui/openDesign.ts`
- `scripts/react-migration/check-route-gate.mjs`
- `scripts/react-migration/run-safe-react-migration.mjs`
- `frontend/package.json`
- `frontend/package-lock.json`
- `web/static/react/**`
- `README.md`
- `CHANGELOG.md`
- `docs/REACT_MIGRATION_MASTER_PLAN.md`
- `pct/__init__.py`
- `setup.py`
- `Dockerfile`
- `railway.toml`

## 5. Endpoint aggiunti

- `GET /api/v1/ui/template-atti`
- `GET /api/v1/ui/template-atti/catalogo`
- `GET /api/v1/ui/redazione-atti`

Tutti gli endpoint usano `_richiedi_auth`, richiedono sessione utente (`g.utente_corrente`) e riusano bridge read-only. Non sono stati creati POST, upload, export, PDF, DOCX, editor o endpoint AI.

## 6. Gate modificato

- `/template-atti` exact e `/template-atti/catalogo` servono shell React.
- `/template-atti/nuovo` e ogni altro `/template-atti/*` restano legacy.
- `/redazione-atti` exact serve shell React.
- Ogni `/redazione-atti/*` resta legacy.
- `/checklist`, `/deposito/checklist`, `/giurisprudenza`, `/legal-intelligence`, `/ricerca-legale` restano legacy.
- `_EXCLUDED_PREFIXES`, `_EXCLUDED_SUFFIXES`, `_EXCLUDED_SEGMENTS`, `_legacy_requested()`, `_accepts_html()` e supporto `?_legacy=1` non sono stati cambiati.

## 7. Contratti legacy catturati

- `artifacts/react-migration/legacy-contracts/template-atti.json`
- `artifacts/react-migration/legacy-contracts/template-atti__catalogo.json`
- `artifacts/react-migration/legacy-contracts/template-atti__nuovo.json`
- `artifacts/react-migration/legacy-contracts/redazione-atti.json`
- `artifacts/react-migration/legacy-contracts/checklist.json`
- `artifacts/react-migration/legacy-contracts/deposito__checklist.json`
- `artifacts/react-migration/legacy-contracts/giurisprudenza.json`
- `artifacts/react-migration/legacy-contracts/legal-intelligence.json`

## 8. Permessi e POST legacy

- Permessi legacy verificati nella route map: le superfici legacy richiedono login; gli endpoint React aggiunti non consentono bypass con API key perche' richiedono utente in sessione.
- POST legacy preservati: `/template-atti/nuovo`, `/template-atti/*`, `/redazione-atti/*`, `/deposito/checklist` e route operative collegate non sono stati modificati.
- I form legacy, token CSRF, upload, download/export e workflow editor restano sui percorsi legacy.

## 9. Legacy preservato

- Editor template: lasciato legacy.
- Redazione guidata completa: lasciata legacy.
- Checklist deposito: lasciata legacy.
- Giurisprudenza e legal-intelligence: lasciate legacy.
- PDF/DOCX/export/download: lasciati legacy.
- Generazione testo legale e prompt AI: lasciati legacy; nessun nuovo prompt o output AI e' stato introdotto.

## 10. Impeccable / Open Design

- Impeccable in questa PR significa gerarchia compatta, spacing coerente, azioni distinguibili, stati vuoti leggibili, warning chiari e densita' adatta a cataloghi/documenti.
- Open Design in questa PR significa token CSS interni, classi `iu-*`, componenti riusabili, nessun CDN, nessun lock-in grafico e nessuna dipendenza esterna.
- Token creati/rafforzati: `--iu-od-doc-gap`, `--iu-od-doc-card-radius`, `--iu-od-doc-section-gap`, `--iu-od-doc-meta-size`, `--iu-od-doc-focus-ring`.
- Utility create/rafforzate: `.iu-od-surface`, `.iu-od-grid`, `.iu-od-card`, `.iu-od-meta`, `.iu-od-warning`, `.iu-od-action-row`.
- Componenti interessati: `TemplateAttiPage`, `RedazioneAttiPage`, data client e bridge documentali.

## 11. Esito controlli

- `node scripts/react-migration/run-safe-react-migration.mjs --tranche=9a`: OK con `ALLOW_DIRTY=1` per file runtime locali preesistenti.
- `npm run test`: OK.
- `npm run typecheck`: OK.
- `npm run build`: OK.
- `node scripts/react-migration/check-route-gate.mjs`: OK.
- `node scripts/react-migration/check-ui-consistency.mjs`: OK.
- `node scripts/react-migration/check-tranche-9a-secrets.mjs`: OK.
- `node scripts/react-migration/check-tranche-9a-no-document-raw.mjs`: OK.
- `node scripts/react-migration/check-tranche-9a-no-legal-generation.mjs`: OK.
- `node scripts/react-migration/check-tranche-9a-no-document-generation.mjs`: OK.
- `node scripts/react-migration/check-tranche-9a-open-design.mjs`: OK.
- `python scripts/react-migration/check-tranche-9a-gate.py`: OK.

## 12. Limiti test Flask

- Il test harness Flask ha consentito autenticazione di test controllata; nessun bypass e nessun limite residuo di autenticazione da dichiarare.

## 13. Rischi residui

- I dati reali esposti dipendono dai repository JSON/tenant gia' disponibili: quando mancano dati reali, la UI mostra stati vuoti e warning invece di mock.
- Il working tree locale contiene file runtime/data non correlati alla tranche e non inclusi nelle patch 9A ne' nel commit.

## 14. Patch generate

- `artifacts/react-migration/patches/tranche-9a.backend.patch`
- `artifacts/react-migration/patches/tranche-9a.frontend.patch`
- `artifacts/react-migration/patches/tranche-9a.gate.patch`
- `artifacts/react-migration/patches/tranche-9a.design.patch`
- `artifacts/react-migration/patches/tranche-9a.tests.patch`
- `artifacts/react-migration/patches/tranche-9a.reports.patch`

## 15. Rollback

```bash
git apply -R artifacts/react-migration/patches/tranche-9a.backend.patch
git apply -R artifacts/react-migration/patches/tranche-9a.frontend.patch
git apply -R artifacts/react-migration/patches/tranche-9a.gate.patch
git apply -R artifacts/react-migration/patches/tranche-9a.design.patch
git apply -R artifacts/react-migration/patches/tranche-9a.tests.patch
```
