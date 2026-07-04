# Piano test App V2

Aggiornato: 2026-05-14, fase 13 `fasereact`.

## Strategia

La fase 10 consolida i test esistenti senza dichiarare passati comandi non eseguiti. La fase 11 collega quei comandi ai workflow CI/CD reali: i gate critici restano bloccanti su pull request e push, mentre smoke autenticati e controlli ambiente restano manuali o nightly quando richiedono credenziali. Il monolitico `python -m pytest -q` resta disponibile ma non va usato come unico segnale locale perche' storicamente puo' superare i budget; il runner governato `scripts/run_pytest_phases.py` consente shard documentati.

## Test pyramid

- Base: unit/domain pytest per auth, storage, tenant, documenti, comunicazioni, telematico, Lex e workflow.
- Middle: Flask test client, API JSON, RBAC, feature flag, tenant isolation, file security e provider verification.
- UI: `pnpm --filter @iusentra/studio test`, `typecheck`, build Vite e `scripts/validate_ui_coverage.py`; nessun runner component/VRT dedicato e quindi nessuna copertura frontend percentuale dichiarata.
- Top: smoke CLI e test E2E Python esistenti; smoke autenticati richiedono env e non sono verdi se le env mancano.

## Copertura fase 10

- Route manifest: 117.
- Route P0/P1: 77.
- Route P0/P1 con stato `tested`: 60.
- File test/smoke censiti: 505.
- Stati matrice: blocked=3, partial=40, pending=14, tested=60.

## Comandi principali

| Area | Comando | Copertura |
| --- | --- | --- |
| Backend rapido | python -m pytest -q tests/test_auth.py tests/test_backend_security_phase5.py tests/test_tenant_isolation_runtime.py --tb=short | auth, security e tenant isolation mirati |
| Backend sharded | python scripts\run_pytest_phases.py --phase 00-ci-contracts,01-flask-core,04-storage --timeout-minutes 15 --batch-size 8 | core backend senza monolitico opaco |
| Frontend statico | pnpm --filter @iusentra/studio test | contratti React, App V2 e UI coverage |
| Frontend build | pnpm --filter @iusentra/studio typecheck && pnpm --filter @iusentra/studio build | typecheck e build Vite |
| Contratti API | python scripts\validate_openapi.py docs\openapi.yaml && python scripts\verify_openapi_provider.py | OpenAPI + provider verification |
| Smoke unico | python scripts\smoke_app_v2_all.py --base-url http://127.0.0.1:8080 | orchestratore smoke fase 10 |
| Coverage backend | python -m pytest -q tests/test_auth.py tests/test_storage_strategy.py tests/test_telematico_repository.py --cov=pct.auth --cov=pct.storage --cov=pct.telematico_repository --cov-report=term-missing | baseline coverage mirata, senza cambiare soglie CI |

## Backend coverage

Coverage Python disponibile tramite `pytest-cov` gia' presente in `requirements/dev.txt`. La CI mantiene il gate critico su Lex/auth/storage/telematico con `config/coverage-critical.ini` e soglia 71; questa fase non abbassa soglie. Il comando locale di baseline mirato e' documentato nella tabella comandi e va registrato in `artifacts/react-migration/pytest-confirmed-ok.md` dopo l'esecuzione.

### Coverage fase 14

Eseguito il gate critico reale:

```powershell
python scripts\run_pytest_phases.py --suite coverage-critical --timeout-minutes 20 -- --cov=lex --cov=pct.auth --cov=pct.storage --cov=pct.storage_postgres --cov=pct.telematico_repository --cov=pct.telematico_workflow --cov-config=config/coverage-critical.ini --cov-report=term-missing --cov-fail-under=71
```

Esito: PASS, 313 test, coverage totale 71.61%, soglia 71 raggiunta. Sono comparsi `ResourceWarning` su connessioni SQLite nei test, senza fallimento del gate.

## Frontend coverage

Non esistono Vitest/Jest/React Testing Library coverage o Playwright/Cypress component test. La copertura frontend reale in questa fase e' statica/contrattuale: `check-react-contracts.mjs`, `check-app-v2-frontend.mjs`, `validate_ui_coverage.py`, typecheck e build. Percentuali frontend non disponibili e non dichiarate.

## Security, RBAC e tenant isolation

Copertura presente tramite `tests/test_auth.py`, `tests/test_auth_management_routes.py`, `tests/test_backend_security_phase5.py`, `tests/test_tenant_isolation_runtime.py`, `tests/test_storage_strategy.py`, `tests/test_upload_security.py`, `tests/test_web_security.py`, `tests/test_security_headers.py` e test document/security specifici. La matrice marca `partial` quando manca prova pagina/workflow puntuale.

## Feature flag e routing

Copertura presente tramite `tests/test_feature_flags.py`, `tests/test_app_v2_feature_flags.py`, `tests/test_app_v2_routing.py`, `scripts/smoke_app_v2_routing.py`, registry e gate frontend. Le route App V2 operative sono attive di default e spegnibili per rollback; le capability non parificate restano default-off.

## API contract coverage

Contratti verificati con `docs/openapi.yaml`, `scripts/validate_openapi.py`, `scripts/verify_openapi_provider.py` e `tests/test_openapi_contracts_phase6.py`. Il provider sample non sostituisce test di dominio: gli endpoint sensibili restano coperti anche da security/RBAC/tenant tests.

## E2E e smoke

E2E Python presenti in `tests/e2e/` e golden path. Non esiste Playwright/Cypress dedicato. Lo smoke unificato fase 10 e' `scripts/smoke_app_v2_all.py`; se mancano credenziali, esegue readiness/inventari e dichiara i profili autenticati mancanti senza marcarli passati.

## Smoke operativi fase 13

La fase 13 promuove `scripts/smoke_app_v2_all.py` a orchestrator operativo. Suite disponibili: `health`, `auth`, `flags`, `rbac`, `tenant`, `routing`, `api`, `pages`, `workflows`, `documents`, `admin`, `search`, `notifications` e `post-deploy`. Il runner supporta `--read-only`, `--json-output`, `--fail-on-warning`, `--require-credentials` e mantiene gli alias storici `--subset inventory|contracts|routing|workflows`.

Comandi:

```powershell
python scripts\smoke_app_v2_all.py --suite all --read-only
python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url https://app.iusentra.it
python scripts\smoke_app_v2_all.py --suite health --read-only --json-output smoke-report.json
```

`BLOCKED` indica env o ID test mancanti; non e' un verde. Con `--require-credentials`, profili smoke mancanti fanno fallire il comando.

## Flaky tests

Rischio noto: primo accesso tenant autenticato dopo restart puo' essere lento per warm-up gia' registrato in `pytest-open-issues.md`. Nessun nuovo flaky introdotto dalla fase 10; eventuali timeout vanno sotto-shardati e documentati.

## Tests non eseguiti o bloccati

- Smoke autenticati tenant A/B/readonly: richiedono env `IUSENTRA_*_USER/PASSWORD`, `IUSENTRA_SMOKE_API_KEY` e ID documento sintetico.
- Storybook: presente come infrastruttura frontend, non ancora gate visuale completo; VRT e test browser component dedicati restano non attivi.
- E2E browser Playwright/Cypress: tool non presenti; presenti E2E Python/test client.

## Commands recommended for CI

La fase 11 ha inserito i comandi candidati nei workflow reali, mantenendo bloccanti build, contratti, RBAC, tenant isolation, feature flag, registry e frontend App V2:

| Priorita | Comando | Motivo |
| --- | --- | --- |
| P0 | python scripts\react-migration\generate_app_v2_test_docs.py --check | inventario/matrice/piano test deterministici |
| P0 | python scripts\smoke_app_v2_all.py --subset inventory | smoke discovery senza credenziali |
| P0 | python scripts\validate_openapi.py docs\openapi.yaml && python scripts\verify_openapi_provider.py | contratti API |
| P0 | pnpm --filter @iusentra/studio test && pnpm --filter @iusentra/studio typecheck && pnpm --filter @iusentra/studio build | frontend App V2 |
| P1 | python scripts\run_pytest_phases.py --phase 00-ci-contracts,01-flask-core,04-storage,06-telematico --timeout-minutes 15 --batch-size 8 | backend/security/tenant sharded |
| P1 | python scripts\run_pytest_phases.py --suite coverage-critical --suite-shard <n> --suite-total-shards 12 | coverage critica esistente |

## CI/CD fase 11

`docs/ci-cd-gates.md` e' il registro operativo dei workflow. Il workflow principale `.github/workflows/ci.yml` esegue i gate App V2 bloccanti su push, pull request e manuale: API contract/provider verification, registry e piano test generati, smoke inventory senza credenziali, test RBAC/tenant/feature flag/routing, frontend test/typecheck/build, shard pytest, coverage critica ed E2E smoke Python.

Le esecuzioni GitHub Actions restano da verificare dopo ogni push: localmente si validano i comandi equivalenti, mentre GitHub conferma runner, cache, artifact e protezioni branch. `.github/workflows/ci-required-gates.yml` attende i required checks dello SHA corrente e produce un report automatico. `.github/workflows/security-supply-chain.yml` mantiene CodeQL/dependency review separati e aggiunge audit dipendenze Python/frontend con artifact. `.github/workflows/smoke-staging.yml` resta manuale, usa environment `staging`, non gira su pull request e richiede secrets solo quando viene selezionato `require_credentials`.

| Workflow | Gate | Bloccante | Nota |
| --- | --- | --- | --- |
| .github/workflows/ci.yml | backend, frontend, contracts, registry, coverage-critical, e2e-smoke | si | Gate PR/push principali |
| .github/workflows/frontend-ci.yml | frontend test/typecheck/build sempre eseguiti | si | Shard rapido dedicato al frontend |
| .github/workflows/security-supply-chain.yml | pip-audit, pnpm audit critical, SBOM | si per audit; artifact sempre | Nessun segreto richiesto |
| .github/workflows/ci-required-gates.yml | required checks sullo SHA corrente | si | Report automatico Markdown/JSON |
| .github/workflows/codeql.yml | CodeQL Python | si | Code scanning GitHub |
| .github/workflows/e2e-nightly.yml | E2E full suite | nightly/manual | Non sostituisce i gate PR |
| .github/workflows/smoke-staging.yml | smoke ambiente e autenticati da secrets | manuale/post-deploy | Usare prima di rollout oltre pilota |

## Criteri di accettazione fase 10

- Inventario, matrice e piano test generati e verificati.
- Smoke orchestrator presente e senza segreti hardcoded.
- Test phase 10 dedicato verde.
- Backend/frontend/contracts/smoke/coverage mirati eseguiti e registrati nei report.
- Nessun runner o coverage non presente dichiarato come completo.
