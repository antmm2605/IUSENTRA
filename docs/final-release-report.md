# Final release report App V2

Data esecuzione: 2026-05-14
Branch: `claude/legal-electronic-filing-kIxcV`
Baseline commit prima della fase 14: `30cfd01c326a7ce65318f77039e1a0ea3bf60229`
Versione finale: `2.235.1`
Decisione: GO WITH WARNINGS

## 1. Executive summary tecnico

La fase 14 chiude il percorso `fasereact` con verifica finale di repository, documentazione, registry, feature flag, OpenAPI, provider verification, backend, frontend, sicurezza, coverage critica, Docker locale e smoke App V2. Il successivo hotfix 2.235.1 corregge il rollout App V2: le superfici operative gia' promosse sono attive di default anche sotto `/app-v2`, con rollback esplicito via flag e telematico non parificato ancora fail-closed.

Non risultano failure critiche aperte. Restano warning/gap non bloccanti: smoke autenticati senza credenziali dedicate, VRT/Storybook non presenti nel repo, `gitleaks` non installato in locale, GitHub Actions remote da confermare dopo push.

## 2. Scope verificato

- App V2 e React migration: registry, routing, flag, UI coverage leggera.
- API React `/api/v1/ui/*`: OpenAPI, provider verification, security guard.
- Backend: auth, RBAC, tenant isolation, routing, feature flag, smoke.
- Frontend: test, typecheck, build Vite.
- CI/CD local equivalent: workflow YAML, lint/static checks, coverage-critical, governance.
- Deploy readiness: Docker locale no-cache e smoke post-deploy locale.

## 3. File modificati

- Versione e release: `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml`, `frontend/package.json`, `frontend/package-lock.json`, `CHANGELOG.md`.
- Governance/fix finale: `web/services/feature_flags.py`, `scripts/smoke_app_v2_all.py`, `scripts/smoke_app_v2_routing.py`, `scripts/smoke_app_v2_pages.py`, `web/bootstrap/fascicoli_core_routes.py`, `web/bootstrap/fascicoli_create_routes.py`, `web/bootstrap/fascicoli_document_routes.py`, `web/bootstrap/fascicoli_document_helpers.py`, `pct/email_client.py`.
- Documentazione finale: `docs/final-release-report.md`, `docs/release-readiness-checklist.md`, `docs/handover-next-prs.md`, `docs/test-plan-app-v2.md`, `docs/release-notes-app-v2.md`, `docs/REACT_MIGRATION_MASTER_PLAN.md`, report in `artifacts/react-migration/*`.

## 4. Stato pagine App V2

Registro generato/validato: 98 route manifest; 69 `react_operational_full`, 3 partial, 26 legacy operative/protette. P0/P1 monitorate dal gate UI: 63; P0/P1 full con copertura UI leggera: 34.

## 5. Stato Feature Flag

PASS. I flag App V2 hanno default di rollout coerenti: superfici operative attive, telematico non parificato e Web Push fail-closed, rollback esplicito verificato. Verificati con `validate_ui_coverage.py`, `check-app-v2-frontend.mjs`, `check-route-gate.mjs`, `check-react-contracts.mjs`, smoke post-deploy e test App V2.

## 6. Stato routing/fallback legacy

PASS. Routing legacy -> App V2 validato in inventario e smoke. Query pericolose come `next`, `redirect`, `tenant_id`, `token` restano governate. Il fallback legacy tecnico resta disponibile dove previsto; nessun redirect esterno aperto rilevato negli smoke.

## 7. Stato sicurezza backend

PASS. Test backend security, auth, tenant isolation e routing completati. API protette anonime rispondono 401 coerente; parametri server-controlled restano bloccati dal guardrail.

## 8. Stato RBAC

PASS per test automatici locali e blocco anonimo. BLOCKED per smoke readonly/admin autenticato per assenza credenziali dedicate `IUSENTRA_READONLY_USER/PASSWORD`.

## 9. Stato tenant isolation

PASS per test automatici locali e smoke anonimi tenant-safe. BLOCKED per prova cross-tenant autenticata in smoke per assenza `IUSENTRA_SMOKE_API_KEY` e profili tenant A/B.

## 10. Stato PII/secret handling

PASS. `pip-audit` e `npm audit` puliti; secret scan ad alta confidenza su 5213 file senza finding. I marker PEM trovati in una scansione grezza erano placeholder UI, non segreti. `gitleaks` non installato localmente: controllo marcato NOT EXECUTED e demandato al workflow remoto.

## 11. Stato API contracts/OpenAPI

PASS. `docs/openapi.yaml` valido, mappe API allineate e endpoint P0/P1 documentati con RBAC/tenant scope/error schema.

## 12. Stato provider verification

PASS. Provider verification locale: 182 endpoint con auth-error coerente, 27 sample P0/P1 con successo autenticato e 1 guardrail backend security. Smoke contratti locale post-refactor: PASS=7, FAIL=0.

## 13. Stato frontend/build/UI

PASS. `npm --prefix frontend run test`, `typecheck` e `build` passati. Build Vite hotfix 2.235.1: 5.83s; asset principali invariati `index-CSdjNGxs.js` 444.72 kB / 131.62 kB gzip e `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. Nessuna nuova dipendenza frontend.

## 14. Stato Storybook/VRT/accessibilita

GO WITH WARNINGS. Storybook, VRT e Playwright/Cypress dedicati non sono presenti nel repo e non vengono dichiarati passati. La copertura UI disponibile resta statica/contrattuale con `validate_ui_coverage.py`, `check-app-v2-frontend.mjs`, test frontend e browser/smoke storici.

## 15. Stato test backend

PASS. Suite mirate eseguite:

- release-readiness: 1/1 pass.
- quality-overlay: 5/5 pass.
- e2e-smoke: 1/1 pass.
- backend security/auth/tenant/flags/routing: 70/70 pass.
- smoke script tests/release/openapi/packaging/readiness: 28/28 pass.
- fix governance Fascicoli/Documenti: 12/12 + 6/6 pass.

## 16. Stato test frontend

PASS. `npm --prefix frontend run test`, `typecheck`, `build` passati.

## 17. Stato E2E/smoke

PASS con blocchi non critici documentati. Docker locale no-cache finale: app, scheduler, OCR, Redis e nginx healthy; `/api/pronto` 200 `versione=2.235.1`; container runtime e label immagine `2.235.1`.

Smoke post-deploy locale finale: PASS=76, FAIL=0, SKIP=1, BLOCKED=6, WARNING=0. I BLOCKED dipendono da credenziali smoke dedicate e ID documento test non configurati.

## 18. Stato CI/CD

PASS locale equivalente sui comandi eseguibili. Workflow YAML parse OK. `python tools/check_python_baseline.py`, `tools/check_repo_governance.py`, Ruff, Ruff governed modules, mypy governed e flake8 sono verdi. GitHub Actions remote restano da verificare dopo push.

## 19. Stato documentazione

PASS. Link e comandi docs validati. Creato questo report e aggiornate checklist/handover/test plan/release notes/report React.

## 20. Coverage

Backend critical coverage PASS: `coverage-critical` con `pytest-cov` su Lex/auth/storage/telematico, soglia 71, risultato 71.61%. Frontend coverage percentuale non disponibile per assenza Vitest/Jest/RTL coverage; gap documentato.

## 21. Comandi eseguiti

| Comando | Directory | Esito | Output sintetico |
| --- | --- | --- | --- |
| `git status --short`; `git diff --stat`; `git diff --name-only`; `git log --oneline -n 3` | `D:\legale\IUSENTRA` | PASS | Worktree analizzata, runtime puliti, ultimi commit fase 13 confermati. |
| Workflow YAML parse `.github/workflows/*.yml` | repo | PASS | Tutti i workflow YAML parsati. |
| Secret scan ad alta confidenza | repo | PASS | 5213 file, 0 finding. |
| `python tools\sync_packaging_files.py --check` | repo | PASS | Packaging sincronizzato; versione `2.235.1`. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | repo | PASS | 21 documenti/149 link; 155 comandi/path. |
| Registry/test docs generated checks | repo | PASS | Registry, requisiti area e test docs allineati. |
| `python scripts\validate_ui_coverage.py`; route/frontend/react contracts | repo | PASS | P0/P1=63, full ui_tested=34, contratti React verdi. |
| `python scripts\react-migration\generate_api_contracts.py --check`; `validate_openapi.py`; `verify_openapi_provider.py` | repo | PASS | OpenAPI valido; provider 182/27/1. |
| Pytest smoke/release/OpenAPI/packaging | repo | PASS | 28/28. |
| Pytest auth/security/tenant/flags/routing | repo | PASS | 70/70. |
| `run_pytest_phases.py --suite release-readiness` | repo | PASS | 1/1. |
| `run_pytest_phases.py --suite quality-overlay` | repo | PASS | 5/5. |
| `run_pytest_phases.py --suite e2e-smoke` | repo | PASS | 1/1. |
| `run_pytest_phases.py --suite coverage-critical` | repo | PASS | 313 test, 100%. |
| `coverage-critical` con `pytest-cov --cov-fail-under=71` | repo | PASS | 71.61%. |
| `python -m pip_audit -r requirements.txt` | repo | PASS | Nessuna vulnerabilita nota. |
| `npm --prefix frontend audit --audit-level=critical --omit=dev --json` | repo | PASS | 0 vulnerabilita. |
| Smoke help/py_compile | repo | PASS | Smoke CLI compilata e help disponibile. |
| `python tools\check_python_baseline.py` | repo | PASS | Python baseline 3.12 allineato. |
| `python tools\check_repo_governance.py` | repo | PASS dopo fix | Bootstrap nei budget, mojibake assente. |
| Ruff/Ruff governed/mypy/flake8 | repo | PASS | Static checks verdi. |
| Pytest mirati Fascicoli/Documenti/PolisWeb | repo | PASS | 12/12 e 6/6 dopo refactor. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | repo | PASS | Immagini finali 2.235.1 costruite. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | repo | PASS | Stack locale healthy. |
| `python scripts\smoke_app_v2_all.py --subset contracts --read-only --base-url http://127.0.0.1:8080` | repo | PASS | PASS=7, FAIL=0. |
| `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url http://127.0.0.1:8080` | repo | PASS | PASS=76, FAIL=0, SKIP=1, BLOCKED=6. |
| Browser reale su `/app-v2/messaggi/nuovo` desktop/mobile | repo | PASS | Nessun messaggio `Funzione non attiva`; redirect login corretto per utente anonimo; zero errori console. |

## 22. Comandi non eseguiti

| Comando | Stato | Motivo | Impatto |
| --- | --- | --- | --- |
| `gitleaks` locale | NOT EXECUTED | Binario non installato. | Non blocca GO WITH WARNINGS: coperto da secret scan locale e workflow remoto. |
| Storybook/VRT/test-storybook | NOT APPLICABLE | Tool non presenti nel repo. | Gap non critico gia documentato. |
| Smoke autenticati con `--require-credentials` | BLOCKED | Mancano profili smoke tenant A/B/readonly, API key e ID documento sintetico. | Non sostituisce i test automatici; richiede prossima PR. |
| GitHub Actions remote | NOT EXECUTED localmente | Runner GitHub non disponibile in ambiente locale. | Da verificare dopo push. |

## 23. Failure corrette

| Problema | Causa | Fix | Ritest |
| --- | --- | --- | --- |
| Smoke `--subset contracts` fallito | Stack locale spento dopo verifica Docker. | Rilanciato con stack acceso sul build finale. | PASS=7, FAIL=0. |
| Governance bootstrap fallita | `fascicoli_core_routes.py` e `fascicoli_document_routes.py` oltre budget. | Estratte creazione fascicolo e helper documenti in moduli dedicati. | `check_repo_governance.py` PASS; test mirati 18/18. |
| Governance mojibake fallita | Pattern anti-mojibake in `pct/email_client.py` conteneva marker letterali. | Sostituito con escape Unicode equivalenti. | `test_file_critici_non_contengono_marker_di_mojibake` PASS. |
| Runtime JSON sporchi | Docker/test locali hanno aggiornato file sotto `data/` e `email/ordinaria.json`. | File runtime ripristinati/rimossi, non committati. | `git status --short` controllato. |

## 24. Failure residue

Nessuna failure critica residua. Restano solo BLOCKED/NOT EXECUTED da ambiente o tool mancanti, indicati sopra.

## 25. Rischi residui

1. Smoke autenticati non eseguiti senza secrets dedicate. Mitigazione: prossima PR P0 per profili smoke.
2. VRT/Storybook assenti. Mitigazione: introdurre runner leggero solo dopo profili smoke.
3. GitHub Actions remote non ancora osservate sul commit fase 14. Mitigazione: controllare dopo push.
4. Provider success-body full limitato su endpoint parametrici/upload/mutazioni. Mitigazione: fixture dedicate per endpoint P0/P1 sensibili.
5. Primo warm-up tenant post-restart resta rischio prestazionale noto. Mitigazione: profilazione separata bootstrap tenant.

## 26. Rollback

1. Spegnere i feature flag App V2 interessati e verificare `/api/v1/ui/feature-flags`.
2. Disabilitare redirect App V2 se attivati e usare fallback legacy tecnico.
3. Revert tecnico del commit fase 14 solo se il refactor bootstrap produce regressioni; ripristinare versione precedente e ridistribuire.
4. Smoke post-rollback: `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url <base-url>`.
5. Monitorare error rate, 401/403/404, `policy_denied`, `cross_tenant_denied`, log frontend e `/api/pronto`.
6. Tempo obiettivo rollback: entro 2 ore.

## 27. GO / NO-GO

Decisione: GO WITH WARNINGS.

Motivazione: tutti i gate critici locali sono passati, non ci sono failure di build/test/OpenAPI/provider/RBAC/tenant/secret/security. I warning residui dipendono da credenziali smoke dedicate, tool VRT/Storybook/gitleaks assenti e conferma GitHub Actions post-push.

## 28. Prossima PR consigliata

Titolo: Credenziali smoke staging App V2.

Obiettivo: configurare profili smoke admin, tenant A, tenant B, readonly, API key e ID documento sintetico in environment protetto, senza segreti nel repository.

Criteri accettazione: workflow `smoke-staging.yml` verde con `--require-credentials`; cross-tenant denial e readonly admin denial verificati; download documento sintetico tenant-safe; artifact JSON redatto.

Test richiesti: `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --require-credentials --base-url <staging>` e workflow manuale GitHub.

Rollback: rimuovere secrets/profili smoke dall'environment e tornare agli smoke read-only anonimi.
