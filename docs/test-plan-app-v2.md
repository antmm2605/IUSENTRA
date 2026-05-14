# Piano test App V2

Aggiornato: 2026-05-14, fase 10 `fasereact`.

## Strategia

La fase 10 consolida i test esistenti senza dichiarare passati comandi non eseguiti. Il piano usa una piramide con unit/domain test Python, test Flask/API, gate statici React, contratti OpenAPI, smoke HTTP e E2E solo dove esistono file reali. Il monolitico `python -m pytest -q` resta disponibile ma non va usato come unico segnale locale perche' storicamente puo' superare i budget; il runner governato `scripts/run_pytest_phases.py` consente shard documentati.

## Test pyramid

- Base: unit/domain pytest per auth, storage, tenant, documenti, comunicazioni, telematico, Lex e workflow.
- Middle: Flask test client, API JSON, RBAC, feature flag, tenant isolation, file security e provider verification.
- UI: `npm --prefix frontend run test`, `typecheck`, build Vite e `scripts/validate_ui_coverage.py`; nessun runner component/VRT dedicato e quindi nessuna copertura frontend percentuale dichiarata.
- Top: smoke CLI e test E2E Python esistenti; smoke autenticati richiedono env e non sono verdi se le env mancano.

## Copertura fase 10

- Route manifest: 98.
- Route P0/P1: 63.
- Route P0/P1 con stato `tested`: 34.
- File test/smoke censiti: 317.
- Stati matrice: blocked=11, partial=38, pending=15, tested=34.

## Comandi principali

| Area | Comando | Copertura |
| --- | --- | --- |
| Backend rapido | python -m pytest -q tests/test_auth.py tests/test_backend_security_phase5.py tests/test_tenant_isolation_runtime.py --tb=short | auth, security e tenant isolation mirati |
| Backend sharded | python scripts\run_pytest_phases.py --phase 00-ci-contracts,01-flask-core,04-storage --timeout-minutes 15 --batch-size 8 | core backend senza monolitico opaco |
| Frontend statico | npm --prefix frontend run test | contratti React, App V2 e UI coverage |
| Frontend build | npm --prefix frontend run typecheck && npm --prefix frontend run build | typecheck e build Vite |
| Contratti API | python scripts\validate_openapi.py docs\openapi.yaml && python scripts\verify_openapi_provider.py | OpenAPI + provider verification |
| Smoke unico | python scripts\smoke_app_v2_all.py --base-url http://127.0.0.1:8080 | orchestratore smoke fase 10 |
| Coverage backend | python -m pytest -q tests/test_auth.py tests/test_storage_strategy.py tests/test_telematico_repository.py --cov=pct.auth --cov=pct.storage --cov=pct.telematico_repository --cov-report=term-missing | baseline coverage mirata, senza cambiare soglie CI |

## Backend coverage

Coverage Python disponibile tramite `pytest-cov` gia' presente in `requirements/dev.txt`. La CI mantiene il gate critico su Lex/auth/storage/telematico con `config/coverage-critical.ini` e soglia 71; questa fase non abbassa soglie. Il comando locale di baseline mirato e' documentato nella tabella comandi e va registrato in `artifacts/react-migration/pytest-confirmed-ok.md` dopo l'esecuzione.

## Frontend coverage

Non esistono Vitest/Jest/React Testing Library coverage o Playwright/Cypress component test. La copertura frontend reale in questa fase e' statica/contrattuale: `check-react-contracts.mjs`, `check-app-v2-frontend.mjs`, `validate_ui_coverage.py`, typecheck e build. Percentuali frontend non disponibili e non dichiarate.

## Security, RBAC e tenant isolation

Copertura presente tramite `tests/test_auth.py`, `tests/test_auth_management_routes.py`, `tests/test_backend_security_phase5.py`, `tests/test_tenant_isolation_runtime.py`, `tests/test_storage_strategy.py`, `tests/test_upload_security.py`, `tests/test_web_security.py`, `tests/test_security_headers.py` e test document/security specifici. La matrice marca `partial` quando manca prova pagina/workflow puntuale.

## Feature flag e routing

Copertura presente tramite `tests/test_feature_flags.py`, `tests/test_app_v2_feature_flags.py`, `tests/test_app_v2_routing.py`, `scripts/smoke_app_v2_routing.py`, registry e gate frontend. Tutte le route App V2 sperimentali restano default-off finche' non abilitate.

## API contract coverage

Contratti verificati con `docs/openapi.yaml`, `scripts/validate_openapi.py`, `scripts/verify_openapi_provider.py` e `tests/test_openapi_contracts_phase6.py`. Il provider sample non sostituisce test di dominio: gli endpoint sensibili restano coperti anche da security/RBAC/tenant tests.

## E2E e smoke

E2E Python presenti in `tests/e2e/` e golden path. Non esiste Playwright/Cypress dedicato. Lo smoke unificato fase 10 e' `scripts/smoke_app_v2_all.py`; se mancano credenziali, esegue readiness/inventari e dichiara i profili autenticati mancanti senza marcarli passati.

## Flaky tests

Rischio noto: primo accesso tenant autenticato dopo restart puo' essere lento per warm-up gia' registrato in `pytest-open-issues.md`. Nessun nuovo flaky introdotto dalla fase 10; eventuali timeout vanno sotto-shardati e documentati.

## Tests non eseguiti o bloccati

- Smoke autenticati tenant A/B/readonly: richiedono env `IUSENTRA_*_USER/PASSWORD`.
- Frontend component coverage e VRT: tool non presenti nel repo.
- E2E browser Playwright/Cypress: tool non presenti; presenti E2E Python/test client.

## Commands recommended for CI

La fase 11 dovra' decidere dove inserirli. Comandi candidati:

| Priorita | Comando | Motivo |
| --- | --- | --- |
| P0 | python scripts\react-migration\generate_app_v2_test_docs.py --check | inventario/matrice/piano test deterministici |
| P0 | python scripts\smoke_app_v2_all.py --subset inventory | smoke discovery senza credenziali |
| P0 | python scripts\validate_openapi.py docs\openapi.yaml && python scripts\verify_openapi_provider.py | contratti API |
| P0 | npm --prefix frontend run test && npm --prefix frontend run typecheck && npm --prefix frontend run build | frontend App V2 |
| P1 | python scripts\run_pytest_phases.py --phase 00-ci-contracts,01-flask-core,04-storage,06-telematico --timeout-minutes 15 --batch-size 8 | backend/security/tenant sharded |
| P1 | python scripts\run_pytest_phases.py --suite coverage-critical --suite-shard <n> --suite-total-shards 12 | coverage critica esistente |

## Criteri di accettazione fase 10

- Inventario, matrice e piano test generati e verificati.
- Smoke orchestrator presente e senza segreti hardcoded.
- Test phase 10 dedicato verde.
- Backend/frontend/contracts/smoke/coverage mirati eseguiti e registrati nei report.
- Nessun runner o coverage non presente dichiarato come completo.
