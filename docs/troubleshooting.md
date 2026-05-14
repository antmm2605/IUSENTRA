# Troubleshooting IUSENTRA

Aggiornato: 2026-05-14, fase 12 `fasereact`.

Usare questo documento per diagnosi rapida. Non dichiarare verde un comando non eseguito.

| Problema | Sintomo | Diagnosi | Fix | Link |
| --- | --- | --- | --- | --- |
| Test backend falliscono | `pytest` rosso o timeout | Leggere `artifacts/react-migration/pytest-open-issues.md`; evitare monolitico se supera budget. | Rilanciare shard mirato con `scripts/run_pytest_phases.py` o test file specifico; documentare esito. | [test plan](test-plan-app-v2.md) |
| Frontend build fallisce | `npm --prefix frontend run build` rosso | `npm --prefix frontend run typecheck`; controllare componente toccato. | Correggere TypeScript/contratti React; poi build. | [ui regression](ui-regression-and-storybook.md) |
| OpenAPI validation fallisce | `validate_openapi.py` rosso | Controllare endpoint aggiunto o schema incompleto. | Rigenerare con `generate_api_contracts.py`, correggere descrizioni/RBAC/tenant. | [api contracts](api-contracts.md) |
| Provider verification fallisce | 401/200/400 non attesi | Eseguire `python scripts\verify_openapi_provider.py` e leggere endpoint fallito. | Allineare auth, fixture provider o documentare limite per endpoint parametrico. | [api map](api-endpoint-contract-map.md) |
| Feature flag non funziona | Pagina appare/spunta in modo inatteso | Verificare `/api/v1/ui/feature-flags` e `IUSENTRA_FEATURE_FLAGS`. | Spegnere/accendere flag canonico, non alias casuali; riavviare app/worker. | [feature flags](feature-flags.md) |
| Pagina App V2 non appare | 403 "Funzione non attiva" | Flag spento o permesso mancante. | Abilitare flag solo in ambiente controllato e verificare RBAC utente. | [app-v2](app-v2.md) |
| Pagina legacy non redirecta | Resta su template storico | Mapping assente o flag spento. | Verificare `legacy-to-app-v2-routing-map.md`; non forzare redirect da query utente. | [routing map](legacy-to-app-v2-routing-map.md) |
| Utente riceve 403 | Accesso negato | Permesso mancante, flag spento o tenant non valido. | Controllare ruolo/profilo, log `policy_denied`, tenant sessione. | [security RBAC](security-rbac-tenant-isolation.md) |
| Tenant isolation test fallisce | Dati tenant B visibili o 400/403 mancato | Guardrail o path tenant non usato. | Usare `web/services/tenant_paths.py` e fail-closed; aggiungere test mirato. | [database](database-and-migrations.md) |
| Download documento fallisce | 404/403 su allegato | File non presente, permesso mancante, tenant mismatch o path traversal bloccato. | Verificare repository tenant, non esporre path reali; usare route backend sicura. | [SECURITY](../SECURITY.md) |
| Storybook build fallisce | Comando non trovato | Storybook non esiste nel repo. | Non dichiararlo gate; usare `validate_ui_coverage.py` finche' non viene introdotto. | [ui regression](ui-regression-and-storybook.md) |
| VRT fallisce | Nessun baseline/runner | VRT non presente. | Documentare gap o introdurre Playwright screenshot in PR dedicata. | [risk register](risk-register.md) |
| Smoke test fallisce | `smoke_app_v2_all.py` rosso | Guardare subset, base URL, credenziali env. | Senza env usare inventory/anonimo; con `--require-credentials` fornire secrets smoke. | [release rollout](release-rollout.md) |
| CI fallisce | Workflow GitHub rosso | Aprire job fallito e comando. | Riprodurre comando locale se non richiede secrets; non disattivare gate senza incident review. | [ci-cd gates](ci-cd-gates.md) |
| Env mancanti | Smoke autenticato saltato o fallito | Variabili `IUSENTRA_*_USER/PASSWORD` assenti. | Configurare environment protetto; non committare credenziali. | [ci-cd gates](ci-cd-gates.md) |
| Database test non inizializzato | Errori file/SQLite/PostgreSQL | Data root o DSN mancante. | Usare data root temporaneo nei test; non scrivere runtime in repo. | [database](database-and-migrations.md) |
| Docker readiness lenta | Primo `/api/pronto` fallisce mentre health e' starting | Container in warm-up. | Attendere health e rilanciare readiness; non diagnosticare `email/ordinaria.json` senza verificare env. | [release rollout](release-rollout.md) |

## Comandi diagnostici rapidi

```powershell
python scripts\validate_docs_links.py
python scripts\validate_docs_commands.py
python scripts\react-migration\generate_app_v2_page_registry.py --check
python scripts\react-migration\generate_app_v2_area_requirements.py --check
python scripts\react-migration\generate_app_v2_test_docs.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
npm --prefix frontend run test
npm --prefix frontend run typecheck
```
