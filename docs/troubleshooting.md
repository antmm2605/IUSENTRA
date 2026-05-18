# Troubleshooting IUSENTRA

Aggiornato: 2026-05-14, fase 13 `fasereact`.

Usare questo documento per diagnosi rapida. Non dichiarare verde un comando non eseguito.

| Problema | Sintomo | Diagnosi | Fix | Link |
| --- | --- | --- | --- | --- |
| Test backend falliscono | `pytest` rosso o timeout | Leggere `artifacts/react-migration/pytest-open-issues.md`; evitare monolitico se supera budget. | Rilanciare shard mirato con `scripts/run_pytest_phases.py` o test file specifico; documentare esito. | [test plan](test-plan-app-v2.md) |
| Frontend build fallisce | `npm --prefix frontend run build` rosso | `npm --prefix frontend run typecheck`; controllare componente toccato. | Correggere TypeScript/contratti React; poi build. | [ui regression](ui-regression-and-storybook.md) |
| OpenAPI validation fallisce | `validate_openapi.py` rosso | Controllare endpoint aggiunto o schema incompleto. | Rigenerare con `generate_api_contracts.py`, correggere descrizioni/RBAC/tenant. | [api contracts](api-contracts.md) |
| Provider verification fallisce | 401/200/400 non attesi | Eseguire `python scripts\verify_openapi_provider.py` e leggere endpoint fallito. | Allineare auth, fixture provider o documentare limite per endpoint parametrico. | [api map](api-endpoint-contract-map.md) |
| Feature flag non funziona | Pagina appare/spunta in modo inatteso | Verificare `/api/v1/ui/feature-flags` e `IUSENTRA_FEATURE_FLAGS`. | Spegnere/accendere flag canonico, non alias casuali; riavviare app/worker. | [feature flags](feature-flags.md) |
| Pagina App V2 non appare | 403 "Funzione non attiva" | Flag spento esplicitamente, capability non parificata o permesso mancante. | Verificare `/api/v1/ui/feature-flags`, RBAC utente e che la pagina sia tra le superfici operative attive di default. | [app-v2](app-v2.md) |
| Pagina legacy non redirecta | Resta su template storico | Mapping assente o flag spento. | Verificare `legacy-to-app-v2-routing-map.md`; non forzare redirect da query utente. | [routing map](legacy-to-app-v2-routing-map.md) |
| Utente riceve 403 | Accesso negato | Permesso mancante, flag spento o tenant non valido. | Controllare ruolo/profilo, log `policy_denied`, tenant sessione. | [security RBAC](security-rbac-tenant-isolation.md) |
| Tenant isolation test fallisce | Dati tenant B visibili o 400/403 mancato | Guardrail o path tenant non usato. | Usare `web/services/tenant_paths.py` e fail-closed; aggiungere test mirato. | [database](database-and-migrations.md) |
| Download documento fallisce | 404/403 su allegato | File non presente, permesso mancante, tenant mismatch o path traversal bloccato. | Verificare repository tenant, non esporre path reali; usare route backend sicura. | [SECURITY](../SECURITY.md) |
| Storybook build fallisce | Configurazione o storie non allineate | Storybook è presente come infrastruttura, ma non è gate visuale obbligatorio. | Correggere solo se il perimetro toccato usa Storybook; per il gate minimo usare `validate_ui_coverage.py`. | [ui regression](ui-regression-and-storybook.md) |
| VRT fallisce | Nessun baseline/runner | VRT non presente. | Documentare gap o introdurre Playwright screenshot in PR dedicata. | [risk register](risk-register.md) |
| Smoke test fallisce | `smoke_app_v2_all.py` rosso | Guardare subset, base URL, credenziali env. | Senza env usare inventory/anonimo; con `--require-credentials` fornire secrets smoke. | [release rollout](release-rollout.md) |
| CI fallisce | Workflow GitHub rosso | Aprire job fallito e comando. | Riprodurre comando locale se non richiede secrets; non disattivare gate senza incident review. | [ci-cd gates](ci-cd-gates.md) |
| Env mancanti | Smoke autenticato saltato o fallito | Variabili `IUSENTRA_*_USER/PASSWORD` assenti. | Configurare environment protetto; non committare credenziali. | [ci-cd gates](ci-cd-gates.md) |
| Database test non inizializzato | Errori file/SQLite/PostgreSQL | Data root o DSN mancante. | Usare data root temporaneo nei test; non scrivere runtime in repo. | [database](database-and-migrations.md) |
| Docker readiness lenta | Primo `/api/pronto` fallisce mentre health e' starting | Container in warm-up. | Attendere health e rilanciare readiness; non diagnosticare `email/ordinaria.json` senza verificare env. | [release rollout](release-rollout.md) |

## Smoke tests

| Sintomo | Causa probabile | Comando diagnostico | Fix | Rollback |
| --- | --- | --- | --- | --- |
| `BASE_URL` non raggiungibile | DNS/proxy/container non pronto | `python scripts\smoke_app_v2_all.py --suite health --base-url <url>` | Verificare `/api/pronto`, `docker compose ps`, Caddy/Nginx e certificati. | Stop rollout se readiness resta KO. |
| Login smoke fallisce | Account smoke assente, CSRF/form cambiato o password errata | `python scripts\smoke_app_v2_all.py --suite auth --require-credentials` | Rigenerare account smoke dedicati e controllare form login senza stampare password. | Stop rollout se login utenti reali e smoke falliscono. |
| 403 inatteso | Flag spento, permesso mancante o tenant errato | `python scripts\smoke_app_v2_all.py --suite flags --read-only` | Verificare flag canonico, ruolo e tenant sessione. | Spegnere flag pagina se 403 colpisce ruoli ammessi. |
| Tenant isolation smoke fallisce | Parametro client accettato o repository non tenant-aware | `python scripts\smoke_app_v2_all.py --suite tenant --require-credentials` | Bloccare `tenant_id` client-side/server-side, usare tenant corrente e aggiungere test. | Rollback immediato. |
| Feature Flag smoke fallisce | Flag documentato ma non registrato o default non off | `python scripts\smoke_app_v2_all.py --suite flags` | Allineare `web/services/feature_flags.py`, frontend route e docs. | Spegnere flag o revertire mapping. |
| Open redirect smoke fallisce | Query `next/redirect/return_url` non sanificata | `python scripts\smoke_app_v2_all.py --suite routing` | Usare whitelist query e bloccare host esterni. | Rollback immediato se redirect esterno e' possibile. |
| Documento test mancante | ID sintetico non configurato | `python scripts\smoke_app_v2_all.py --suite documents --read-only` | Impostare `IUSENTRA_TEST_DOCUMENT_ID` o ID tenant A/B non sensibili. | Nessun rollback se solo BLOCKED; rollback se download cross-tenant passa. |
| Env mancanti | `BLOCKED` su auth/RBAC/tenant/workflow | `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only` | Configurare secrets environment protetto, non nel repository. | Non promuovere rollout completo finche' gli smoke autenticati restano blocked. |
| Mutating smoke bloccato | `IUSENTRA_ENABLE_MUTATING_SMOKE` spento | `python scripts\smoke_app_v2_all.py --suite rbac --read-only` | Abilitarlo solo in ambiente test con cleanup. | Nessun rollback: blocco intenzionale. |
| JSON report non scritto | Directory assente o permessi | `python scripts\smoke_app_v2_all.py --suite health --json-output artifacts\smoke\health.json` | Creare directory scrivibile o usare `%TEMP%`. | Non blocca se stdout e exit code sono raccolti. |
| Timeout | Warm-up tenant o endpoint lento | `python scripts\smoke_app_v2_all.py --suite post-deploy --timeout 480` | Raccogliere endpoint lento e confrontare baseline performance. | Stop rollout se p95 o P0 peggiora oltre soglia. |
| TLS locale | Certificato locale non fidato | `python scripts\smoke_app_v2_all.py --suite health --base-url http://127.0.0.1:8080` | Usare HTTP locale o certificato fidato; non disabilitare TLS in staging/prod. | Nessuno se solo locale. |
| Staging secrets mancanti | Workflow `smoke-staging` con credenziali richieste fallisce | Controllare environment `staging` e secrets GitHub | Configurare `IUSENTRA_ADMIN_*`, tenant A/B, readonly e API key smoke. | Non promuovere rollout autenticato. |
| API 500 | Regressione backend o bootstrap dati | `python scripts\smoke_app_v2_all.py --suite api --read-only` | Leggere log redatti, test endpoint e rollback se P0. | Rollback immediato su P0. |
| Frontend shell non raggiungibile | routing/proxy/static asset rotto | `python scripts\smoke_app_v2_all.py --suite pages --read-only` | Verificare build Vite, shell React, Caddy/Nginx e login redirect. | Spegnere flag/redirect o revertire. |

## Comandi diagnostici rapidi

```powershell
python scripts\validate_docs_links.py
python scripts\validate_docs_commands.py
python scripts\smoke_app_v2_all.py --suite post-deploy --read-only
python scripts\react-migration\generate_app_v2_page_registry.py --check
python scripts\react-migration\generate_app_v2_area_requirements.py --check
python scripts\react-migration\generate_app_v2_test_docs.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
npm --prefix frontend run test
npm --prefix frontend run typecheck
```
