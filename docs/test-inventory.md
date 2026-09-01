# Inventario test IUSENTRA

Aggiornato: 2026-05-14, fase 14 `fasereact`.

Inventario generato da `scripts/react-migration/generate_app_v2_test_docs.py`. Non sostituisce l'esecuzione dei test: classifica i file presenti e rende visibili gap, aree e stato.

## Sintesi

- File pytest censiti: 601.
- Smoke/script censiti: 6.
- Runner frontend component/VRT rilevati: nessuno; copertura UI tramite gate statici fase 9.

| Tipo test | Conteggio |
| --- | --- |
| API contract | 92 |
| Backend | 72 |
| E2E | 9 |
| Frontend static gate | 1 |
| Frontend/UI | 187 |
| RBAC | 60 |
| Security | 37 |
| Smoke CLI | 6 |
| Tenant isolation | 144 |

## Fasi pytest governate

| Fase | Descrizione | File censiti |
| --- | --- | --- |
| 00-ci-contracts | Contratti CI, packaging, sicurezza minima e guardrail tecnici rapidi. | 20 |
| 01-flask-core | Bootstrap Flask, autenticazione, sicurezza web, osservabilita' e superfici operative. | 19 |
| 02-react-ui | Contratti React, regia, topbar, layout mobile e coerenza design system. | 34 |
| 03-core-business | Domini gestionali: clienti, fascicoli, agenda, preventivi, tariffario e workflow economico. | 49 |
| 04-storage | Persistenza, migrazioni, tenant, repository SQL e parita' storage. | 14 |
| 05-documents | Documenti, template atti, editor, firma visibile e intelligenza documentale. | 42 |
| 06-telematico | PCT, PEC, portali telematici, SIGP, buste, Local Signer e deposito. | 63 |
| 07-lex-ai | Lex, assistenti, fonti ufficiali, legal intelligence, coverage AI e ricerca. | 170 |
| 08-e2e | Flussi end-to-end e golden path ufficiali. | 6 |
| 09-misc | Test non classificati dalle fasi principali | 184 |

## Suite CI aggiuntive

| Suite | Target | Esempi |
| --- | --- | --- |
| coverage-critical | 64 | lex/tests, tests/test_lex_agenda_scadenze_knowledge_matrix.py, tests/test_lex_ai_quality_framework.py, tests/test_lex_assistente_context_real_requests.py, tests/test_lex_atti_redazione_knowledge_matrix.py ... |
| e2e-nightly | 4 | tests/e2e/test_studio_reale_flow.py, tests/e2e/test_ai_pipeline_full.py, tests/e2e/test_tenant_migration_full.py, tests/e2e/test_operational_crash_day.py |
| e2e-smoke | 1 | tests/e2e/test_studio_reale_flow.py |
| quality-overlay | 3 | tests/test_lex_quality_gates.py, tests/test_performance_budget.py, tests/test_local_signer_ai_cache.py |
| release-readiness | 1 | tests/test_release_readiness.py |
| signer | 3 | tests/test_local_signer.py, tests/test_build_dist.py, tests/test_visible_signature.py |

## Inventario completo

| Area | Tipo test | File | Copre | Gap | Stato |
| --- | --- | --- | --- | --- | --- |
| API contracts | API contract | tests/test_ci_no_regression_contract.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| API contracts | API contract | tests/test_data_flow_contract.py | 403/RBAC, tenant, contratto, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| API contracts | API contract | tests/test_fascicolo_document_catalog_schema_contract.py | tenant, contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| API contracts | API contract | tests/test_lex_widget_contract.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| API contracts | API contract | tests/test_openapi_contracts_phase6.py | tenant, contratto, file | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| API contracts | API contract | tests/test_template_atti_frontend_contract.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Agenda | API contract | tests/test_agenda.py | tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Agenda | API contract | tests/test_calendar_credentials.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Agenda | API contract | tests/test_calendar_demo_provider.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Agenda | API contract | tests/test_calendar_sync.py | audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Agenda | API contract | tests/test_calendar_sync_engine.py | tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Agenda | API contract | tests/test_lex_agenda_scadenze_knowledge_matrix.py | 403/RBAC, tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Agenda | Backend | tests/test_scadenza_proposta_agenda.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Agenda | Frontend/UI | tests/test_calendar_api.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| App V2 | API contract | tests/scripts/test_smoke_app_v2_all.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| App V2 | API contract | tests/test_app_v2_frontend_phase7.py | 403/RBAC, tenant, feature flag, contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| App V2 | API contract | tests/test_app_v2_test_plan_phase10.py | tenant, feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| App V2 | Frontend/UI | tests/test_app_v2_page_registry.py | feature flag | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| App V2 | Security | tests/test_app_v2_feature_flags.py | feature flag, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| App V2 | Tenant isolation | tests/test_app_v2_area_requirements_phase8.py | 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| App V2 | Tenant isolation | tests/test_app_v2_routing.py | tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | API contract | tests/test_audit_integrations.py | tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Audit | Backend | tests/test_audit_canonical.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Backend | tests/test_audit_hashing.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Frontend/UI | tests/test_audit_merkle.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Audit | Frontend/UI | tests/test_audit_signing.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Audit | Frontend/UI | tests/test_functional_parity_audit.py | contratto, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Audit | Frontend/UI | tests/test_sentenza_economic_audit.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Audit | Security | tests/test_audit_hmac.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Security | tests/test_audit_worm.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_audit_bundle.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_audit_chain.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_audit_emit.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_audit_legal_source_delivery.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_audit_proof.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_audit_routes.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_audit_snapshot.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Audit | Tenant isolation | tests/test_pec_audit_pipeline.py | 401 anonimo, 403/RBAC, tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Auth/RBAC | RBAC | tests/test_auth.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Auth/RBAC | RBAC | tests/test_auth_management_routes.py | 403/RBAC | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Auth/RBAC | RBAC | tests/test_profili.py | 403/RBAC, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | API contract | tests/test_advanced_ai_runtime.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_assistente_followup.py | file, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_capability_truth_registry.py | tenant, feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_ci_cd_gates_phase11.py | 401 anonimo, tenant, feature flag, contratto, file, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_client_signature_providers.py | tenant, file | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_daily_plan_service.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_firma_remota.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_golden_journeys.py | 403/RBAC, tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_legal_skills_engine.py | 401 anonimo, 403/RBAC, tenant, feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_legal_updates_pipeline.py | 403/RBAC, tenant, contratto, file, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_local_ai.py | tenant, contratto, file, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_local_pec_runtime.py | audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_observability_runtime.py | tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_packaging_consistency.py | tenant, contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_performance_budget.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | API contract | tests/test_transactional_outbox.py | tenant, contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Backend domain | Backend | tests/test_antiriciclaggio.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_applicazioni_catalogo_lotto1.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_brocardi_adapter.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_cache.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_compensi_a_tempo.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_crm_intake.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_daily_plan_assignment.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_daily_plan_serializers.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_database_migration.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_design_tokens.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_formatting.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_jobs.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_kpi_engine.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_legal_regex_pack.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_legal_update_source_parsers.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_local_signer_ai_cache.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_local_signer_installer_atomic.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_mediazione_dm150.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_metrics_endpoint.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_normattiva_importer.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_notizie_utili.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_ocr_pipeline_adapter.py | feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_pdf_style.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_pec.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_pec_legal_workflow.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_polisweb_diff.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_portali_certificati.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_prima_nota.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_procedure_xsd_mapper.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_prompt_library.py | 401 anonimo, 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_regia_apertura_fascicolo.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_regia_channels.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_runtime_service_checks.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_scheduler_registry.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_structured_logging.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_strumenti_lotto2a.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_time_tracking_passivo.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Backend | tests/test_uffici_competenti.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | E2E | tests/e2e/test_ai_pipeline_full.py | audit | richiede ambiente/credenziali quando esce dal test client | censito |
| Backend domain | E2E | tests/e2e/test_operational_crash_day.py | tenant, audit | richiede ambiente/credenziali quando esce dal test client | censito |
| Backend domain | E2E | tests/e2e/test_studio_reale_flow.py | happy/edge path dominio | richiede ambiente/credenziali quando esce dal test client | censito |
| Backend domain | E2E | tests/test_end_to_end_studio.py | tenant | richiede ambiente/credenziali quando esce dal test client | censito |
| Backend domain | E2E | tests/test_golden_paths.py | tenant | richiede ambiente/credenziali quando esce dal test client | censito |
| Backend domain | E2E | tests/test_pec_ocr_pipeline.py | tenant | richiede ambiente/credenziali quando esce dal test client | censito |
| Backend domain | E2E | tests/test_portali_telematici_matrix.py | 401 anonimo | richiede ambiente/credenziali quando esce dal test client | censito |
| Backend domain | Frontend/UI | tests/legal_deposit/test_payment_policies.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_ai_coverage_pipeline.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_aml_screening.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_applicazioni_repository.py | feature flag | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_assistente_competencies.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_assistente_context_cache.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_busta.py | contratto, file, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_cades_signed_attrs.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_compilatore_atti.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_dashboard_panoramica.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_economic_dashboard.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_economico_context.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_evidence_vault.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_fascicolo_operational_presidio.py | 403/RBAC, file | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_fascicolo_sentenza_economica.py | tenant, contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_feature_flags.py | 403/RBAC, feature flag, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_firma_pkcs11.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_firme_cades.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_fonti_ufficiali_registry.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_coverage_ai_resilience.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_coverage_pipeline.py | contratto, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_intelligence.py | 401 anonimo, file, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_intelligence_daily_engine.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_notification_rulepack.py | contratto, file, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_official_context.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_platform_catalog.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_source_expansion.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_sources_registry.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_update_autofetch.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_update_batch_runner.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_update_job_queue.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_update_publish_context.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_update_surface_jobs.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_update_surface_truth.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_legal_updates_backfill_official_context.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_local_pec_bridge.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_login_brute_force_guard.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_motore_preventivo.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_normative_tables.py | feature flag, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_notification_relata_fascicolo.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_notification_workflow.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_ocr_worker.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_official_sources_registry.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_official_web_gazzetta.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_pagamenti_giustizia.py | contratto, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_pdf_deadline_import.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_pec_hearing_understanding.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_pec_legal_deadline_proposer.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_pec_legal_event_understanding.py | tenant, contratto, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_pec_legal_families.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_polisweb_eventi.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_polisweb_sync_job.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_post_acceptance_obligations.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_practice_engine_profiles.py | file | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_practice_engine_state_machine.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_practice_engine_structure.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_practice_engine_validators.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_presidio_health.py | tenant, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_procedure_completion_api.py | 401 anonimo | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_procedure_completion_fusion.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_procedure_completion_models.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_procedure_completion_source_plan.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_procedure_completion_validator.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_procedure_inventory_importer.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_procedure_lifecycle_edges.py | tenant, contratto, file, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_regia_api_payloads.py | feature flag, file | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_regia_controllo_studio.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_regia_no_shortcuts.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_regia_scoped_loading.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_regia_worklist.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_reginde.py | 401 anonimo | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_registro_ppaa_harvest_public.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_reports.py | feature flag | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_riconciliazione_bancaria.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_runtime_resilience.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_scheduler_worker.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_sentenza_economic_dashboard.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_signed_attachment_preview.py | file | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_strumenti_lotto2b.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_strumenti_lotto2b2.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_studio_demo.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_studio_voice_assistant.py | 403/RBAC, feature flag | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_sync.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_sync_uffici.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_template_normative_compliance.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_termini_processuali.py | tenant, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_terminology_aliases.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_territorio_italia.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_timesheet.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_topbar_hooks.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_uffici_giudiziari_comuni_db.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_visible_signature.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_workflow_commerciale.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_workflow_onboarding.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | Frontend/UI | tests/test_workflow_pipeline.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Backend domain | RBAC | tests/legal_deposit/test_penal_deposit_rules.py | tenant, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_applicazioni.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_assistente_execution_policy.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_assistente_focus.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_assistente_redazionale.py | contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_compliance_cockpit.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_condivisione.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_ctu.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_database.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_digital_signature_workflow.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_legal_ocr_structured.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_local_signer.py | 401 anonimo, 403/RBAC, tenant, feature flag, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_mobile_layout.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_pec_economia_contributo_unificato.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_polisweb_cerca_rg.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_polisweb_fascicolo_sync.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_portale_economici.py | 403/RBAC, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_presidio_processuale_ruleset.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_procedure_lifecycle.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_reginde_sync_cache.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_registro_ppaa_sync_cache.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_responsabile_conformita.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_sentenza_a_verbale_catena_economica.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_telematic_deposit_workflow.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_telematic_registry_fail_closed.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_topbar_operational_api.py | 401 anonimo, 403/RBAC, tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | RBAC | tests/test_unlimited_ocr_integration.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_assistente_legal_reference_guard.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_assistente_social.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_assistente_social_intent.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_gazzetta_connector.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_healthcheck.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_legal_intelligence_repository.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_legal_update_safe_diagnostics.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_legal_update_source_capabilities.py | contratto, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_legal_update_web_verification_attachments.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_normattiva_client.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_official_sources_retriever.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_pec_pagopa_rt.py | contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_procedure_coverage_ext.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_procedure_knowledge_pipeline.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_rate_limit.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_scheduler_admin.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Security | tests/test_secrets_manager.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/scripts/test_smoke_lib.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_checklist_atti.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_codeql_public_surface_regressions.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_crm_routes.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_api.py | 401 anonimo, 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_collectors.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_deduplication.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_models.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_perf.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_priority.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_repository.py | tenant, contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_scheduler.py | tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_daily_plan_scheduling.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_dashboard_mailbox_sync.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_docker_entrypoint.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_fascicolo_detail_ux.py | tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_import_center.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_installation_packs.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_legal_coverage_surface.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_legal_ocr_pipeline.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_migration_assistant.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_notification_presidia_payloads.py | 401 anonimo, tenant, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_notification_presidia_rollout_api.py | tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_notification_relata_materializer.py | 403/RBAC, tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_operational_resilience.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_operational_surfaces.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_pec_control_tower.py | 403/RBAC, tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_pec_deadline_legacy_repair.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_pec_economic_auto_trigger.py | tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_pec_legal_deadline_cablaggio.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_pec_notification_presidio.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_pec_operational_chain.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_polisweb.py | 401 anonimo, tenant, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_practice_engine_sql_source.py | tenant, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_procedure_completion_repository.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_procedure_completion_service.py | 403/RBAC, tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_procedure_lifecycle_repository.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_product_governance_surface.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_push_notifications.py | 401 anonimo, 403/RBAC, tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_release_readiness.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_repository_sql_parity.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_scheduler.py | tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_sentenza_economic_repository.py | tenant, feature flag, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_sentenza_economic_runtime.py | 401 anonimo, 403/RBAC, tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_sentenza_economic_workflow.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_server_maintenance_surface.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_strumenti_legali.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_studio_site.py | tenant, feature flag, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_studio_site_assets.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_studio_site_public_blocks.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_support_remote.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_utf8_integrity.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_web_bootstrap.py | 401 anonimo, tenant, feature flag, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Backend domain | Tenant isolation | tests/test_workspace_intelligente.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Clienti/anagrafiche | API contract | lex/tests/unit/test_sentenze_clienti_fix.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Clienti/anagrafiche | API contract | tests/test_lex_sentenze_clienti_fix.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Clienti/anagrafiche | Backend | tests/test_clienti_workflow.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Clienti/anagrafiche | Frontend/UI | tests/test_clienti.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Clienti/anagrafiche | Frontend/UI | tests/test_clienti_route_filters.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Clienti/anagrafiche | Tenant isolation | tests/test_import_center_clienti_sink.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Comunicazioni | RBAC | tests/test_notifiche_legali.py | 403/RBAC, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Comunicazioni | Security | tests/test_messaggi.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Comunicazioni | Tenant isolation | tests/test_email_attachment_dedup.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Comunicazioni | Tenant isolation | tests/test_email_client.py | 403/RBAC, tenant, feature flag, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Comunicazioni | Tenant isolation | tests/test_lex_email_knowledge_matrix.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | API contract | lex/tests/unit/test_template_atti_source.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Documenti | Backend | tests/test_editor_ai_italian_validator.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Backend | tests/test_editor_pdf_cid.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Backend | tests/test_template_atti_sources.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Frontend/UI | tests/test_editor_ai_edit_proposals.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_editor_ai_renderer.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_editor_ai_template_resolver.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_template_atti_cartabia_strict.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_template_atti_generation_gate.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_template_atti_inventory.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_template_atti_prefill_strict.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_template_atti_timbro.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | Frontend/UI | tests/test_template_atti_unified_catalog.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Documenti | RBAC | tests/test_template_atti_api_strict.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | RBAC | tests/test_template_atti_cartabia_prefill_timbro.py | contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | RBAC | tests/test_template_atti_legal_sources_registry.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | RBAC | tests/test_template_atti_master_catalog.py | contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | RBAC | tests/test_template_atti_repository.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | RBAC | tests/test_template_atti_workspace.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Tenant isolation | tests/test_editor_ai_api.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Tenant isolation | tests/test_editor_ai_draft_generation.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Tenant isolation | tests/test_editor_ai_repository.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Tenant isolation | tests/test_lex_editor_ai_tools.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Documenti | Tenant isolation | tests/test_template_atti_editor.py | tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Fascicoli | API contract | tests/test_fascicoli_pagination.py | tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Fascicoli | Backend | tests/test_fascicoli_clienti_links_audit.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Fascicoli | Frontend/UI | tests/test_fascicoli_signature_options.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Fascicoli | Frontend/UI | tests/test_fascicoli_stato_e_filtri_economici.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Fascicoli | Tenant isolation | tests/test_fascicoli.py | tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Backend | tests/test_document_intelligence_extraction.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Backend | tests/test_document_intelligence_pdf_quality.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Backend | tests/test_fascicoli_document_resilience.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Backend | tests/test_fascicolo_document_autonomy_audit.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Frontend/UI | tests/test_document_management.py | feature flag | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| File/document security | Frontend/UI | tests/test_fascicolo_document_presidio.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| File/document security | Frontend/UI | tests/test_lex_document_context.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| File/document security | RBAC | tests/test_document_intelligence_catalog_api.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | RBAC | tests/test_fascicolo_document_catalog.py | tenant, contratto, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | RBAC | tests/test_fascicolo_registry_document.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Security | tests/test_client_document_reader.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Security | tests/test_document_intelligence_api.py | 403/RBAC, tenant, feature flag, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Security | tests/test_document_intelligence_frontend.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Security | tests/test_document_tools.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_document_intelligence_auto_indexing.py | 403/RBAC, tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_document_intelligence_catalog_governance.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_document_intelligence_repository.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_document_intelligence_repository_sql.py | tenant, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_document_intelligence_service.py | 403/RBAC, tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_document_intelligence_versioning.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_fascicolo_document_catalog_pipeline.py | tenant, contratto, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_legal_document_ingestion.py | tenant, feature flag, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_lex_document_tools_auto_index.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_lex_fascicolo_documents_tools.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_run_fascicolo_document_presidio.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| File/document security | Tenant isolation | tests/test_signed_document_name_audit.py | tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | API contract | lex/tests/unit/test_guida_pratica_source.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_data_consistency_react_api.py | 401 anonimo, 403/RBAC, tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_guida_pratica_set33_import.py | tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_impostazioni_pec_local_signer_react.py | feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_product_readiness_react_api.py | 401 anonimo, 403/RBAC | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_react_condivisioni.py | 403/RBAC | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_react_crm_bridge.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_react_preventivo_wizard_console.py | 401 anonimo, feature flag, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_react_privacy_registry_sources.py | feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_react_tariffario_console.py | audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | API contract | tests/test_react_timesheet.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Frontend React | Frontend static gate | frontend/package.json | contratti React, App V2 frontend, UI coverage fase 9, typecheck e build | nessun Vitest/Jest/RTL coverage; nessun VRT attivo | censito |
| Frontend React | Frontend/UI | lex/tests/unit/test_autonomy_query_builder.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_assistente_language_guidance.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_circuit_breaker.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_curate_codex_guida_pratica_completion.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_guida_pratica_api.py | file | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_guida_pratica_set34_41_import.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_guida_pratica_set42_49_import.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_guida_pratica_shared_service.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_guida_pratica_user_kb_import.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_import_guida_pratica_termini_processuali.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_impostazioni_ai_locale_react.py | feature flag, file | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_lex_tokenjuice.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_notifiche_legali_preview_ui.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_asset_retention.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_dashboard_cache.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_document_editor.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_email_datetime.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_fascicoli_sentenze_economiche.py | tenant, feature flag, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_lex_learning_bridge.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_payload_cache.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_react_wizard_pro.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_redazione_guidata.py | 401 anonimo, 403/RBAC | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | Frontend/UI | tests/test_regia_ui_react.py | 403/RBAC, feature flag, contratto, file, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Frontend React | RBAC | tests/test_deposito_guidato.py | feature flag, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | RBAC | tests/test_quickorganizer_import.py | tenant, feature flag, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | RBAC | tests/test_react_fatturazione_bridge.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | RBAC | tests/test_react_shell.py | 401 anonimo, 403/RBAC, tenant, feature flag, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Security | tests/test_build_dist.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Security | tests/test_document_intelligence_hidden_ui.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Security | tests/test_guida_pratica_service.py | 401 anonimo, feature flag, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Security | tests/test_impostazioni_firma_local_signer_versione_react.py | feature flag, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_notiziario_react.py | tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_pec_auto_acquire.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_portali_payload_import_ui.py | tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_react_document_archive.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_react_legal_intelligence_search.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_react_scadenziario_additions.py | 401 anonimo, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_studio_site_builder_api.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_studio_site_builder_blocks.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_ui_api_security_matrix.py | 401 anonimo, 403/RBAC, tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Frontend React | Tenant isolation | tests/test_ui_coverage_phase9.py | 403/RBAC, tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Impostazioni | API contract | tests/test_ci_coverage_config.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Impostazioni | Backend | tests/test_config_studio.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Impostazioni | Backend | tests/test_config_studio_smtp.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Impostazioni | Frontend/UI | tests/test_backup.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Impostazioni | Security | tests/test_impostazioni_sdi_config.py | feature flag, contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Impostazioni | Tenant isolation | tests/test_hetzner_backup_retention.py | tenant, feature flag, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Impostazioni | Tenant isolation | tests/test_impostazioni_firma.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | API contract | lex/tests/test_citation_guard_strict.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_evaluation_metrics.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_gateway_router.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_gateway_status.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_hallucination_guard.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_http_bounded_bridge.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_http_bounded_bridge_governed_only.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_legal_reference_guard_strict.py | tenant, file | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_official_web.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_ollama_provider_strict_no_evidence.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_orchestrator_http_raw_chat_blocked.py | feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_professional_answer_needs_review.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_provider_health_and_citations.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/test_service.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_autonomy_local_archive_provider.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_autonomy_local_corpus_provider.py | contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_bundle_scenarios.py | 403/RBAC, tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_deterministic_provider.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_guard_orchestrator.py | 403/RBAC, tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_memory_service.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_ollama_provider.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_professional_answer.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_registry.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_retrieval_orchestrator.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_router.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_source_policy_invariants.py | 403/RBAC, tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | lex/tests/unit/test_template_act_workflow.py | 403/RBAC, tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_ai_quality_framework.py | tenant, contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_autonomous_cli.py | feature flag, contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_autonomous_discovery_web.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_autonomous_learning.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_autonomous_nightly.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_citazioni_cliccabili.py | happy/edge path dominio | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_docling_parser.py | feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_fascicolo_first_retrieval.py | tenant, feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_giurisprudenza_workflow.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_italian_response_guard.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_legal_source_engine.py | feature flag | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_model_routing_governance.py | contratto | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_module.py | tenant, file, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_professional_upgrade.py | tenant, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | API contract | tests/test_lex_studio_database_source.py | tenant | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Lex/Ricerca | Backend | lex/tests/test_gateway_privacy_guard.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/test_grounding.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/unit/test_autonomy_detail_links.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/unit/test_autonomy_gap_detector.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/unit/test_concept_graph.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/unit/test_evaluation_learning_metrics.py | feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/unit/test_knowledge_base.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/unit/test_learning_citation_extractor.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | lex/tests/unit/test_sources_polite_fetcher.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | tests/test_assistente_studio_context_giurisprudenza.py | tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | tests/test_giurisprudenza_corpus.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | tests/test_lex_autonomy_detail_links.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | tests/test_lex_quality_gates.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | tests/test_lex_source_corpus_generator.py | tenant, contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Backend | tests/test_lex_tools_copertura.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/test_dependencies.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/test_orchestrator.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/test_runtime_dependencies.py | 401 anonimo | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_autonomy_improvement_proposer.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_autonomy_memory_inspection.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_autonomy_research_planner.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_autonomy_safety.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_learning_language_analyzer.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_learning_models.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_retrieval_learning_memory.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_source_policy.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_source_registry.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | lex/tests/unit/test_sources_trust.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_calcolatori_lexday.py | contratto, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_giurisprudenza_repository.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_legal_practice_research_matrix.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_lex_dataset_training_status.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_lex_drafting_intent.py | feature flag | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_lex_eval_scorecard_surface.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_lex_memory_answers.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_lex_sources_and_studio_data.py | tenant | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_lex_workflow_agents_planner.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_procedure_source_research.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | Frontend/UI | tests/test_search_index.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Lex/Ricerca | RBAC | lex/tests/unit/test_social_intent_routing.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | RBAC | tests/test_giurisprudenza.py | tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | RBAC | tests/test_lex_daily_plan_tool.py | 403/RBAC, tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | RBAC | tests/test_lex_tool_registry_governance.py | 403/RBAC, contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | RBAC | tests/test_reginde_cache_search.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Security | lex/tests/test_routes.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | lex/tests/unit/test_studio_context.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_backfill_sentenza_lex_economics.py | tenant, contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_global_search.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_global_search_api.py | tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_global_search_indexer.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_global_search_stats.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_assistente_context_real_requests.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_atti_redazione_knowledge_matrix.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_dataset_nightly.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_dataset_review_queue.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_economic_context_tools.py | tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_economic_knowledge_matrix.py | 403/RBAC, tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_legal_studio_full.py | tenant, feature flag, contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_legal_studio_tools_normativa.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_memory_tree.py | tenant, contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_operational_knowledge.py | 403/RBAC, tenant, feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_privacy_admin_knowledge_matrix.py | 403/RBAC, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_procedure_completion_tools.py | 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_sito_studio_knowledge_matrix.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_software_domain_dataset_matrix.py | 403/RBAC, tenant, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_studio_dataset_pipeline.py | tenant, feature flag, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_workflow_agents_api.py | 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_workflow_agents_executor.py | 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_workflow_agents_metrics.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_workflow_agents_models.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_lex_workflow_agents_policies.py | 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Lex/Ricerca | Tenant isolation | tests/test_local_deep_research_integration.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Mandato/economico | Backend | tests/test_fattura_pa.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Mandato/economico | Backend | tests/test_tariffario_fascia_alta.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Mandato/economico | Backend | tests/test_tassonomia_preventivi.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Mandato/economico | Frontend/UI | tests/test_fatturazione.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Mandato/economico | Frontend/UI | tests/test_preventivi_conferimento_route.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Mandato/economico | Frontend/UI | tests/test_preventivi_repository.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Mandato/economico | Frontend/UI | tests/test_preventivi_wizard_tariffario_audit.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Mandato/economico | Frontend/UI | tests/test_tariffario.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Mandato/economico | Frontend/UI | tests/test_tariffario_catalogo_coverage.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Mandato/economico | RBAC | tests/test_preventivi_wizard.py | feature flag, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Mandato/economico | RBAC | tests/test_tariffario_routes.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Portale Cliente | Tenant isolation | tests/test_client_portal_access.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Portale Cliente | Tenant isolation | tests/test_client_portal_api.py | 401 anonimo, 403/RBAC, tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Portale Cliente | Tenant isolation | tests/test_client_portal_repository.py | tenant, feature flag, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Scadenze | Frontend/UI | tests/test_guardiano_scadenze.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Scadenze | Frontend/UI | tests/test_scadenze_proposte_pec.py | tenant, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Scadenze | RBAC | tests/test_polisweb_scadenze_registri.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Scadenze | Tenant isolation | tests/test_scadenziario.py | 401 anonimo, tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | API contract | tests/test_backend_security_phase5.py | 401 anonimo, tenant, file, audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Security | API contract | tests/test_cache_security.py | audit | provider verification copre campione; estendere schema response P0/P1 puntuali | censito |
| Security | Security | tests/test_security_headers.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Security | tests/test_uffici_giudiziari_security.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Security | tests/test_upload_security.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Security | tests/test_web_security.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Tenant isolation | tests/test_daily_plan_security.py | 403/RBAC, tenant, feature flag | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Tenant isolation | tests/test_document_intelligence_security.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Tenant isolation | tests/test_lex_workflow_agents_security.py | 403/RBAC, tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Tenant isolation | tests/test_procedure_completion_security.py | 403/RBAC, tenant, feature flag, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Security | Tenant isolation | tests/test_security_redaction.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Smoke | Smoke CLI | scripts/smoke_app_v2_all.py | readiness, route, workflow o sicurezza runtime | autenticazione completa solo con env smoke dedicate | censito |
| Smoke | Smoke CLI | scripts/smoke_app_v2_pages.py | readiness, route, workflow o sicurezza runtime | autenticazione completa solo con env smoke dedicate | censito |
| Smoke | Smoke CLI | scripts/smoke_app_v2_routing.py | readiness, route, workflow o sicurezza runtime | autenticazione completa solo con env smoke dedicate | censito |
| Smoke | Smoke CLI | scripts/smoke_app_v2_workflows.py | readiness, route, workflow o sicurezza runtime | autenticazione completa solo con env smoke dedicate | censito |
| Smoke | Smoke CLI | scripts/smoke_backend_security.py | readiness, route, workflow o sicurezza runtime | autenticazione completa solo con env smoke dedicate | censito |
| Smoke | Smoke CLI | scripts/smoke_lib.py | readiness, route, workflow o sicurezza runtime | autenticazione completa solo con env smoke dedicate | censito |
| Telematico | Backend | tests/test_import_pst_xsd_codici_oggetto.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | Backend | tests/test_pst_services.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | E2E | tests/test_deposito_telematico_catalogo.py | tenant, feature flag, contratto, audit | richiede ambiente/credenziali quando esce dal test client | censito |
| Telematico | Frontend/UI | tests/test_codici_oggetto_pst_catalog.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_conformita_pst.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_deposito_compatibilita.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_deposito_route_helpers.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_deposito_server_dry_run_audit.py | audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_profilo_deposito.py | 401 anonimo | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_pst_xsd_catalog_importer.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_regia_deposito_receipts.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_simulazione_deposito.py | contratto | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_telematico_repository.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_telematico_resilience.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_telematico_source_recovery.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | Frontend/UI | tests/test_telematico_truth_registry.py | happy/edge path dominio | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Telematico | RBAC | tests/test_deposito.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | RBAC | tests/test_deposito_anagrafica_ministeriale.py | happy/edge path dominio | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | RBAC | tests/test_deposito_destination_tables.py | audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | RBAC | tests/test_pdp_penale_web.py | file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | RBAC | tests/test_pdp_penale_workflow.py | tenant, contratto, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | RBAC | tests/test_sigp_integration.py | contratto | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | RBAC | tests/test_sigp_sync.py | 401 anonimo, contratto, file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | RBAC | tests/test_telematico_workflow.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | Security | tests/test_canali_telematici_deposito.py | 401 anonimo, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | Security | tests/test_pst_catalog.py | file | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | Tenant isolation | tests/test_pst_original_presidio_runtime.py | 401 anonimo, tenant, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Telematico | Tenant isolation | tests/test_telematico_dashboard.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | E2E | tests/e2e/test_tenant_migration_full.py | tenant | richiede ambiente/credenziali quando esce dal test client | censito |
| Tenant isolation | Frontend/UI | tests/test_storage_governance.py | contratto, audit | nessun runner component/VRT dedicato; copertura via gate statici e browser smoke | censito |
| Tenant isolation | Tenant isolation | tests/test_audit_lex_tenant_sources.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | Tenant isolation | tests/test_pec_pipeline_tenant_isolation.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | Tenant isolation | tests/test_storage_compaction_script.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | Tenant isolation | tests/test_storage_postgres_migration.py | tenant, contratto, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | Tenant isolation | tests/test_storage_strategy.py | 403/RBAC, tenant, contratto, file, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | Tenant isolation | tests/test_tenant_admin_legacy.py | tenant, audit | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | Tenant isolation | tests/test_tenant_isolation_runtime.py | 401 anonimo, 403/RBAC, tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
| Tenant isolation | Tenant isolation | tests/test_tenant_migration_full.py | tenant | estendere solo se emerge una route/area non coperta dalla matrice | censito |
