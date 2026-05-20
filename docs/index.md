# Indice documentazione IUSENTRA

Aggiornato: 2026-05-21, pipeline lifecycle procedurale.

Questo indice e' il punto di ingresso operativo per sviluppatori, maintainer e release manager. I documenti generati devono essere aggiornati tramite gli script indicati, non a mano, salvo correzioni esplicitamente documentate.

## Avvio e contesto

| Area | Documento | Quando usarlo |
| --- | --- | --- |
| Overview progetto | [README](../README.md) | Setup rapido, struttura repository, comandi principali e link di handover. |
| Contribuzione | [CONTRIBUTING](../CONTRIBUTING.md) | Checklist PR, regole App V2, sicurezza, PII, feature flag e test. |
| Sicurezza | [SECURITY](../SECURITY.md) | Modello sicurezza, disclosure, RBAC, tenant isolation, segreti e file security. |
| Architettura | [architecture](architecture.md) | Mappa tecnica corrente Flask, React/App V2, repository, API, CI e deploy. |
| Architettura storica | [ARCHITETTURA](ARCHITETTURA.md) | Dettaglio preesistente dei moduli applicativi. |

## App V2 e migrazione React

| Area | Documento | Fonte di verita |
| --- | --- | --- |
| App V2 handover | [app-v2](app-v2.md) | Regole operative, checklist nuova pagina/rotta/componente. |
| Piano migrazione | [REACT_MIGRATION_MASTER_PLAN](REACT_MIGRATION_MASTER_PLAN.md) | Stato storico e avanzamento fasi React. |
| Registro pagine | [app-v2-page-registry](app-v2-page-registry.md) | Generato da `scripts/react-migration/generate_app_v2_page_registry.py`. |
| Frontend pages | [frontend-app-v2-pages](frontend-app-v2-pages.md) | Riepilogo operativo pagine, componenti e stato UI. |
| Requisiti area | [app-v2-area-requirements](app-v2-area-requirements.md) | Workflow, RBAC, tenant, PII e stato per area. |
| Feature flag | [feature-flags](feature-flags.md) | Flag default-off, env, fallback, rollout e rollback. |
| Routing legacy/App V2 | [legacy-to-app-v2-routing-map](legacy-to-app-v2-routing-map.md) | Mapping redirect, query policy e fallback. |
| UI regression | [ui-regression-and-storybook](ui-regression-and-storybook.md) | Copertura UI reale, Storybook/VRT non presenti e gap. |

## API, sicurezza e dati

| Area | Documento | Quando usarlo |
| --- | --- | --- |
| API contracts | [api-contracts](api-contracts.md) | OpenAPI, provider verification, error schema e checklist endpoint. |
| API map | [api-endpoint-contract-map](api-endpoint-contract-map.md) | Endpoint/pagina/RBAC/tenant/provider verification. |
| OpenAPI | [openapi.yaml](openapi.yaml) | Specifica verificata da `scripts/validate_openapi.py`. |
| Backend security map | [backend-endpoint-security-map](backend-endpoint-security-map.md) | Stato auth/RBAC/tenant/PII per endpoint. |
| RBAC e tenant | [security-rbac-tenant-isolation](security-rbac-tenant-isolation.md) | Enforcement backend, denial policy e test. |
| Multi-studio | [MULTI_STUDIO_SECURITY](MULTI_STUDIO_SECURITY.md) | Regole multi-studio e fail-closed. |
| Storage | [STORAGE_MATRIX](STORAGE_MATRIX.md) | Matrice repository/path/tenant. |
| Database e migrazioni | [database-and-migrations](database-and-migrations.md) | Stato SQLite/PostgreSQL, migrazioni e rollback dati. |
| Notifiche e procedimenti telematici | [LEGAL_NOTIFICATIONS_AND_TELEMATIC_REGISTRY](LEGAL_NOTIFICATIONS_AND_TELEMATIC_REGISTRY.md) | L. 53/1994, relata, prova notifica, fail-closed e registry PCT/SIGP/UNEP/PAT/PTT/PDP. |
| Procedure lifecycle knowledge pipeline | [procedure_lifecycle_knowledge_pipeline](procedure_lifecycle_knowledge_pipeline.md) | Inventario PST/XSD, mapping procedure, fonti, schede, lifecycle, firma, deposito, ricevute, notifica, prova, audit e gap queue. |
| Audit repo lifecycle procedure | [procedure_lifecycle_repo_audit](procedure_lifecycle_repo_audit.md) | Inventario iniziale, moduli riusati, conflitti evitati, gap reali e piano definitivo della tranche. |

## Lex AI e fonti

| Area | Documento | Quando usarlo |
| --- | --- | --- |
| Lex Operational Knowledge | [lex-operational-knowledge-map](lex-operational-knowledge-map.md) | Mappa sorgenti operative reali, tenant key, permessi, rischi e stato integrazione Lex. |
| Variabili Lex | [LEX_ENV_VARS](LEX_ENV_VARS.md) | Feature flag Lex, AI locale, fonti ufficiali e Operational Knowledge. |
| Legal Source Engine | [lex_ai_legal_source_engine](lex_ai_legal_source_engine.md) | Architettura nativa per fonti giuridiche ufficiali e citazioni. |
| Workflow fonti | [lex_ai_legal_source_engine_printing_press_logic](lex_ai_legal_source_engine_printing_press_logic.md) | Pattern di scoperta fonte, manoscritti, scorecard e dogfood senza dipendenza runtime da Printing Press. |
| Registro tool Lex | [LEX_TOOL_REGISTRY](LEX_TOOL_REGISTRY.md) | Tool Lex disponibili e regole operative per dati strutturati e fonti. |
| Policy sorgenti Lex | [LEX_SOURCE_POLICY_SYSTEM](LEX_SOURCE_POLICY_SYSTEM.md) | Ranking sorgenti, modalita' strict/balanced/broad e grounding. |
| Legal Skills Engine | [LEGAL_SKILLS_ENGINE](LEGAL_SKILLS_ENGINE.md) | Skill pack legali read-only, profilo studio, guardrail, API e UI React. |

## Test, CI e release

| Area | Documento | Quando usarlo |
| --- | --- | --- |
| Test plan App V2 | [test-plan-app-v2](test-plan-app-v2.md) | Test pyramid, smoke, coverage e comandi principali. |
| Test inventory | [test-inventory](test-inventory.md) | Inventario generato dei file test/smoke. |
| Test matrix | [test-matrix-app-v2](test-matrix-app-v2.md) | Stato pagina/ruolo/tenant/flag/test. |
| Smoke test | [smoke-tests](smoke-tests.md) | Orchestrator fase 13, suite, env, JSON report, exit code e post-deploy. |
| CI/CD gates | [ci-cd-gates](ci-cd-gates.md) | Workflow reali, required checks, artifact e secrets. |
| Release readiness | [release-readiness-checklist](release-readiness-checklist.md) | Checklist operativa pre-release, rollout progressivo e rollback. |
| Final release report | [final-release-report](final-release-report.md) | Report tecnico conclusivo fase 14, GO/NO-GO, comandi eseguiti e rischi residui. |
| Release rollout | [release-rollout](release-rollout.md) | Pre-release, rollout, smoke, rollback e monitoraggio. |
| Release notes App V2 | [release-notes-app-v2](release-notes-app-v2.md) | Sintesi tecnica, known issues e pending items. |
| Troubleshooting | [troubleshooting](troubleshooting.md) | Diagnosi rapida per test, build, API, flag, smoke e CI. |

## Operativita, osservabilita e handover

| Area | Documento | Quando usarlo |
| --- | --- | --- |
| Observability e log | [observability-and-logs](observability-and-logs.md) | Eventi audit/denial, metriche e cosa non loggare. |
| Risk register | [risk-register](risk-register.md) | Rischi concreti, mitigazioni e owner. |
| Handover e prossime PR | [handover-next-prs](handover-next-prs.md) | Stato finale, pending, blocked e PR consigliate. |
| Audit documentazione | [documentation-audit](documentation-audit.md) | Contraddizioni trovate/risolte e stato docs fase 12. |
| Osservabilita prodotto | [OBSERVABILITY_AUDIT_PRODUCT](OBSERVABILITY_AUDIT_PRODUCT.md) | Audit prodotto gia' esistente. |
| Deploy Hetzner | [DEPLOY_HETZNER_CPX42](DEPLOY_HETZNER_CPX42.md) | Procedura server CPX42 e profilo Docker. |
| Deploy profile | [deploy/hetzner README](../deploy/hetzner/README.md) | Runbook tecnico del profilo `deploy/hetzner`. |

## Validazioni documentali

| Comando | Scopo |
| --- | --- |
| `python scripts/validate_docs_links.py` | Verifica link locali dei documenti handover. |
| `python scripts/validate_docs_commands.py` | Verifica che script, workflow e npm scripts citati esistano. |
| `python scripts/react-migration/generate_app_v2_page_registry.py --check` | Verifica registry, frontend pages e routing map generati. |
| `python scripts/react-migration/generate_app_v2_area_requirements.py --check` | Verifica requisiti area App V2. |
| `python scripts/react-migration/generate_app_v2_test_docs.py --check` | Verifica test plan, inventory e matrix generati. |

## Regole di lettura

- Non dichiarare completa una pagina se `docs/app-v2-area-requirements.md` o `docs/frontend-app-v2-pages.md` la marcano `partial`, `pending`, `blocked` o `complete_unverified`.
- Non dichiarare Storybook, VRT o Playwright/Cypress se il comando non esiste nel repository.
- Non mettere segreti, password, token, PEC reali o dati cliente nei documenti.
- Per rollout App V2 usare sempre feature flag default-off, smoke e rollback documentati.
