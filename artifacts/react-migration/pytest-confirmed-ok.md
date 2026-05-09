# Pytest shard confermati OK

Aggiornato: 2026-05-09, sessione React Full / shard backend.

## Regola operativa

Questi comandi o shard sono stati verificati in questa sessione e non vanno rilanciati a vuoto. Si ripetono solo se viene toccato codice collegato al loro perimetro, oppure come ultimo gate aggregato prima di commit/deploy.

## Frontend e gate React

| Verifica | Esito | Nota |
| --- | --- | --- |
| `npm test` | OK | Contratti React verificati. |
| `npm run typecheck` | OK | TypeScript senza errori. |
| `npm run build` | OK | Build Vite completata. |
| `node scripts/react-migration/run-full-react-migration.mjs` | OK | Anti-mascheramento passato; audit aggiornato su 53 route e 80 link legacy totali non primari. |
| `node scripts/react-migration/run-legal-ui-checks.mjs` | OK | Legal UI, responsive workspace e no-bootstrap-primary React passati. |
| `python scripts/run_pytest_phases.py --list --json --report artifacts/react-migration/pytest-phases-20260509-list.json` | OK | Inventario corrente: 269 file test. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py` | OK | 8 test passati dopo le correzioni Lex/Local AI. |

## Gate finali sessione 2026-05-09

| Verifica | Esito | Nota |
| --- | --- | --- |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Manifest e gate route allineati dopo promozione `/statistiche` a `react_operational_full`. |
| `python -m pytest -q tests/test_react_shell.py::test_statistiche_react_full_non_espone_fallback_legacy --tb=short` | OK | Regressione mirata: payload `/api/v1/ui/statistiche` senza fallback `_legacy=1`, manifest full, `writes=none`. |
| `npm test` | OK | Verde dopo correzioni Lex/Local AI. |
| `npm run typecheck` | OK | Verde dopo correzioni Lex/Local AI. |
| `npm run build` | OK | Build Vite verde; asset React rigenerati. |
| `node scripts/react-migration/run-full-react-migration.mjs` | OK | Audit, anti-mascheramento, route contract, responsive e no-bootstrap-primary OK. |
| `node scripts/react-migration/run-legal-ui-checks.mjs` | OK | Legal UI checks OK. |
| `python tools/check_repo_governance.py` | OK | Governance verde; `web/app.py` resta bootstrap con 40 righe e 0 route inline. |
| `python -m pytest -q lex/tests/unit/test_router.py lex/tests/test_gateway_router.py tests/test_lex_sentenze_clienti_fix.py --tb=short` | OK | 32 test Lex passati dopo ripristino regex accentate cliente. |
| `docker compose build --no-cache app` | OK | Immagine locale ricostruita da zero con package `pct-studio-legale==2.208.0`. |
| `docker compose up -d --no-build redis app nginx` | OK | Dopo rebuild: `iusentra-app` healthy, `nginx` avviato, `/api/pronto` risponde 200. |
| `python -m pytest -q tests/test_database.py::test_create_app_bootstrap_moduli_monitorati tests/test_web_bootstrap.py::test_create_app_email_ordinaria_deriva_da_email_db_runtime tests/test_web_bootstrap.py::test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina --tb=short` | OK | 3 test passati sul fallback email ordinaria runtime e bootstrap dati. |
| `python -m pytest -q tests/test_storage_strategy.py::test_sync_user_directory_indicizza_utenti_tenant_sqlite tests/test_storage_strategy.py::test_sync_user_directory_puo_saltare_reconcile_pesante tests/test_web_bootstrap.py::test_runtime_bundle_startup_sync_directory_non_rilancia_reconcile_pesante --tb=short` | OK | 3 test passati: directory utenti tenant invariata e startup web senza reconcile storage pesante. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 20` | OK | Risposta 200 con versione `2.208.0` dal container locale. |

## Verifiche eseguite riportate dall'utente

Queste verifiche sono state riportate dall'utente e vengono conservate qui per evitare rilanci inutili. Si ripetono solo se viene toccato codice collegato al loro perimetro oppure come gate finale prima di commit/deploy.

| Verifica | Esito | Nota |
| --- | --- | --- |
| `npm test` | OK | Verde. |
| `npm run typecheck` | OK | Verde. |
| `npm run build` | OK | Verde. |
| `node scripts/react-migration/run-full-react-migration.mjs` | OK | Verde. |
| `node scripts/react-migration/run-legal-ui-checks.mjs` | OK | Verde. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py` | OK | Verde. |

Formula operativa da mantenere nei report: `pytest completo monolitico non è verde perché va in timeout; il gate è stato verificato con shard/sotto-shard, con timeout per job, e i timeout larghi sono stati isolati.`

## Test mirati corretti e confermati

| Test | Esito | Nota |
| --- | --- | --- |
| `tests/test_ci_no_regression_contract.py::test_pytest_core_uses_ten_parallel_shards_without_removing_tests` | OK | Confermato dopo correzione shard `observability` / `ocr_worker`. |
| `tests/test_lex_widget_contract.py::test_base_template_no_longer_contains_disabled_legacy_lex_chat` | OK | Confermato dopo rimozione marker legacy dal base template. |
| `tests/test_migration_assistant.py::test_build_migration_assistant_rileva_postgres_anche_se_storage_corrente_e_json` | OK | Confermato dopo stub PostgreSQL completo per `database_config_to_dsn`. |
| `tests/test_migration_assistant.py::test_admin_assistente_migrazione_renderizza_errori_e_rimedi` | OK | Confermato dopo stub PostgreSQL completo per `database_config_to_dsn`. |
| `tests/test_ci_no_regression_contract.py tests/test_lex_widget_contract.py tests/test_migration_assistant.py` | OK | Gruppo mirato passato: 21 test. |
| `tests/test_email_client.py::test_base_template_non_renderizza_vecchio_lex_duplicato` | OK | Confermato dopo aggiornamento del contratto: niente marker legacy, un solo include `pct_ai_widget`. |
| `tests/test_document_intelligence_repository_sql.py::test_document_ai_repository_sqlite_persistente_filtra_e_ricarica` | OK | Confermato dopo hardening di `_detect_backend` quando lo stub PostgreSQL non espone una classe reale. |
| `tests/test_web_bootstrap.py::test_docker_compose_hetzner_allinea_email_ordinaria_e_ai_locale` | OK | Confermato dopo allineamento default Hetzner `PCT_LOCAL_AI_BASE_URL` su `/api/version`. |
| `tests/test_repository_sql_parity.py::test_coverage_surface_usa_database_tenant_postgresql_come_fallback` | OK | Confermato dopo allineamento stub `resolve_runtime_postgres_dsn` al fallback tenant PostgreSQL reale. |
| `tests/test_repository_sql_parity.py::test_coverage_surface_usa_tenant_unico_con_configurazione_postgres_legacy` | OK | Confermato insieme al fallback PostgreSQL legacy tenant. |
| `tests/test_react_document_editor.py::test_editor_documento_payload_pdf_usa_anteprima_nativa` | OK | Confermato nel sotto-shard React UI preventivi/editor isolato. |
| `tests/test_react_document_editor.py::test_editor_documento_react_contract_statico` | OK | Confermato nel sotto-shard React UI preventivi/editor isolato. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_bootstrap_console_operativa` | OK | Confermato singolarmente: il timeout era da batch troppo largo. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_e_fallback_legacy_smoke` | OK | Confermato singolarmente: il timeout era da batch troppo largo. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_calcola_ads_con_voci_manuali_e_accessori` | OK | Confermato singolarmente: il timeout era da batch troppo largo. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_calcola_ads_per_fasi_senza_compenso_unico` | OK | Confermato singolarmente: il timeout era da batch troppo largo. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_calcola_ads_compenso_unico_solo_se_flag_attivo` | OK | Confermato singolarmente: il timeout era da batch troppo largo. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_calcola_tutte_le_voci_area_pratica_aggiunte` | OK | Confermato singolarmente: il timeout era da batch troppo largo. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_create_crea_preventivo_reale_con_cliente_potenziale_e_clausola` | OK | Confermato singolarmente: test lento ma sotto timeout job. |
| `tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_non_genera_conferimento_senza_accettazione_cliente` | OK | Confermato singolarmente: test lento ma sotto timeout job. |
| `tests/test_react_shell.py::test_blocco_telematico_studio_admin_resta_legacy_first` | OK | Confermato dopo riallineamento `_LEGACY_FIRST_PREFIXES` della shell React con `/strumenti-operativi`. |
| `tests/test_react_shell.py::test_nav_legacy_allineata_react_senza_nascondere_sidebar` | OK | Confermato insieme al batch React shell legacy-first. |
| `tests/test_react_shell.py::test_react_blocco_finale_studio_admin_completo` | OK | Confermato insieme al batch React shell legacy-first. |
| `tests/test_react_shell.py::test_react_firma_documento_profonda_non_degrada_a_dettaglio_generico` | OK | Confermato insieme al batch React shell legacy-first. |
| `tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica` | OK | Confermato insieme al batch React shell legacy-first. |
| `tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti` | OK | Confermato dopo allineamento `_LEGACY_OPERATIONAL_PREFIXES` con `/strumenti-operativi`. |
| `tests/test_web_bootstrap.py::test_runtime_cloud_hosted_ignora_percorsi_ai_del_tenant` | OK | Confermato dopo adeguamento dello stub `LocalAIService` ai path reali. |
| `tests/test_editor_ai_repository.py::test_repository_sqlite_filtra_tenant_fascicolo_e_versiona` | OK | Confermato dopo hardening `EditorAIRepository` sul backend PostgreSQL opzionale. |
| `tests/test_editor_ai_repository.py::test_repository_sqlite_modifiche_e_audit` | OK | Confermato dopo hardening `EditorAIRepository` sul backend PostgreSQL opzionale. |
| `tests/test_web_bootstrap.py::test_contesto_lex_compatta_le_sezioni_e_limita_le_fonti` | OK | Confermato dopo reinserimento del guardrail prompt esatto per richieste operative/ricerca senza saluti. |
| `tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative` | OK | Confermato dopo sblocco React per `/sito-studio/` mantenendo legacy-first sui percorsi profondi/builder. |
| `tests/test_studio_site.py::test_sito_studio_inizializza_seed_e_consente_preview_bozza` | OK | Confermato dopo bootstrap side-effect Sito Studio nel gate React. |
| `tests/test_studio_site.py::test_sito_studio_flag_opzionali_controllano_le_route_pubbliche` | OK | Confermato dopo bootstrap side-effect Sito Studio nel gate React. |
| `tests/test_studio_site.py::test_sito_studio_contatti_pubblici_persistono` | OK | Confermato dopo bootstrap side-effect Sito Studio nel gate React. |
| `tests/test_studio_site.py::test_sito_studio_prenotazione_approvata_si_sincronizza_in_agenda` | OK | Confermato dopo bootstrap side-effect Sito Studio nel gate React. |
| `tests/test_studio_site.py::test_console_superadmin_siti_studio_espone_il_catalogo` | OK | Confermato dopo bootstrap side-effect Sito Studio nel gate React. |
| `tests/test_workflow_commerciale.py::test_apri_fascicolo_automatico_comparsa_risposta_genera_attivita_specifiche` | OK | Confermato singolarmente: timeout da batch workflow troppo largo. |
| `tests/test_workflow_commerciale.py::test_apri_fascicolo_automatico_propaga_procedura_operativa_tributaria` | OK | Confermato singolarmente: timeout da batch workflow troppo largo. |
| `tests/test_workflow_onboarding.py::test_build_fascicolo_onboarding_precompila_fascicolo_da_workflow` | OK | Confermato singolarmente. |
| `tests/test_workflow_onboarding.py::test_build_fascicolo_onboarding_comparsa_risposta_usa_controlli_normativi_specifici` | OK | Confermato singolarmente. |
| `tests/test_workflow_onboarding.py::test_collega_fascicolo_aggiorna_preventivo_e_conferimento` | OK | Confermato singolarmente: test lento, sotto timeout job. |
| `lex/tests/unit/test_bundle_scenarios.py::test_lookup_sentenza_con_numero_pdf_degrada_senza_riferimenti_verificati` | OK | Confermato dopo normalizzazione metadata pubblico `workflow=giurisprudenza`, `workflow_detail=giurisprudenza_specifica`, coverage gap e risposta prudenziale. |
| `tests/test_regia_apertura_fascicolo.py::test_apertura_fascicolo_da_pratica_commerciale_genera_regia` | OK | Confermato singolarmente: test lento, il timeout era da batch troppo largo. |
| `tests/test_regia_apertura_fascicolo.py::test_override_economico_deve_essere_auditato` | OK | Confermato singolarmente: test lento, il timeout era da batch troppo largo. |
| `tests/test_regia_api_payloads.py::test_api_regia_payload_completo_e_mock_false` | OK | Confermato singolarmente. |
| `tests/test_regia_api_payloads.py::test_api_slot_predeposito_deposito_ricevuta_evidence_pack` | OK | Confermato singolarmente: test lento, il timeout era da batch troppo largo. |
| `tests/test_regia_channels.py::test_canali_telematici_hanno_regole_distinte` | OK | Confermato singolarmente. |
| `lex/tests/unit/test_bundle_scenarios.py::test_errore_telematico_restituisce_risposta_deterministica_con_metadati` | OK | Confermato dopo allineamento `deposito_telematico` al percorso deterministico e metadata pubblico `telematico_status`. |
| `lex/tests/unit/test_professional_answer.py::test_risposta_fascicolo_viene_strutturata_con_qualita_e_azioni` | OK | Confermato dopo ripristino headings professionali `Quadro verificato`, `Qualita della risposta` e dicitura fascicolo considerato. |
| `lex/tests/unit/test_professional_answer.py::test_risposta_normativa_incompleta_richiede_revisione_professionale` | OK | Confermato dopo ripristino heading strict `Risposta professionale` e sezione `Limiti e verifiche`. |
| `lex/tests/unit/test_router.py::test_router_resolves_telematico_workflow` | OK | Confermato dopo separazione tra intent `explain_telematico_error` (`telematico_status`) e flusso completo `deposito_telematico`. |
| `lex/tests/unit/test_bundle_scenarios.py::test_errore_telematico_restituisce_risposta_deterministica_con_metadati` + `tests/test_lex_legal_studio_full.py::TestTC03DepositoTelematico::*` + `tests/test_lex_legal_studio_full.py::TestTC20PipelineCoerenza::test_pipeline_coherence` | OK | Verifica incrociata: status errore telematico e deposito telematico restano distinti e coerenti. |
| `lex/tests/unit/test_router.py` + `tests/test_lex_legal_studio_full.py::TestTC03DepositoTelematico` + `tests/test_lex_legal_studio_full.py::TestTC20PipelineCoerenza::test_pipeline_coherence` | OK | Confermato dopo priorita' corretta: domanda sulla normativa del deposito -> `normativa`; checklist/errore deposito operativo -> `deposito_telematico`. |
| `tests/test_assistente_followup.py::test_resolve_followup_query_aggancia_richiesta_pdf_al_tema_precedente` | OK | Sotto-shard batch timeout Lex #14: passato singolarmente. |
| `tests/test_assistente_followup.py::test_should_trigger_web_search_esclude_le_richieste_solo_interne` | OK | Sotto-shard batch timeout Lex #14: passato singolarmente. |
| `tests/test_assistente_followup.py::test_assistente_context_espone_followup_resolution_quando_eredita_il_tema` | OK | Sotto-shard batch timeout Lex #14: passato singolarmente; test lento circa 2 minuti. |
| `tests/test_assistente_followup.py::test_assistente_context_guida_l_apertura_su_ricerca_web_sentenze_civili` | OK | Sotto-shard batch timeout Lex #14: passato singolarmente; test lento circa 2 minuti. |
| `tests/test_assistente_followup.py::test_assistente_context_copre_l_area_economica_di_studio` | OK | Sotto-shard batch timeout Lex #14: passato singolarmente; test lento oltre 2 minuti. |
| `tests/test_local_ai.py::test_local_ai_bootstrap_disabled_is_non_blocking` | OK | Confermato dopo correzione stub `pct.local_ai`: il modulo reale viene usato quando disponibile. |
| `tests/test_local_ai.py::test_assistente_prompt_separa_voce_e_regole_tecniche` | OK | Confermato insieme al batch Local AI. |
| `tests/test_local_ai.py::test_api_local_ai_context_endpoints_prepare_payloads` | OK | Sotto-shard batch timeout Lex/Local AI: passato singolarmente. |
| `tests/test_local_ai.py::test_api_assistente_context_prepara_prompt_per_companion_locale` | OK | Sotto-shard batch timeout Lex/Local AI: passato singolarmente; test lento. |
| `tests/test_local_ai.py::test_api_assistente_context_integra_fonti_ufficiali_web_live` | OK | Sotto-shard batch timeout Lex/Local AI: passato singolarmente; test lento. |
| `tests/test_local_ai.py::test_api_assistente_context_espone_profilo_richiesta_e_policy_fonti` | OK | Sotto-shard batch timeout Lex/Local AI: passato singolarmente; test lento. |
| `tests/test_local_ai.py::test_api_assistente_context_eredita_tema_precedente_per_verifica_web` | OK | Sotto-shard batch timeout Lex/Local AI: passato singolarmente; test lento. |
| `tests/test_local_ai.py::test_api_assistente_context_integra_documenti_caricati` | OK | Confermato dopo propagazione degli allegati governati nelle `citations` del payload Lex. |
| `07-lex-ai` tail da item 555 a fine | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-555.json` | 47/47 item passati con batch da 5 e timeout 5 minuti per job. |

## Shard backend confermati

| Fase / shard | Esito | Report | Nota |
| --- | --- | --- | --- |
| `06-telematico` con `--item-batch-size 5 --timeout-minutes 5` | OK | `artifacts/react-migration/pytest-20260509-06-telematico.json` | 82 batch item passati. Non ripetere salvo modifiche a telematico/PST/PDP/PAT/PTT/SIGP/Local Signer. |
| `08-e2e` con `--batch-size 1 --timeout-minutes 5` | OK | `artifacts/react-migration/pytest-20260509-08-e2e.json` | 5/5 file passati. |
| `00-ci-contracts` con `--item-batch-size 5 --timeout-minutes 5` | OK | `artifacts/react-migration/pytest-20260509-00-ci-contracts.json` | 17/17 batch item passati. |
| `02-react-ui` item 1-84 | OK | `artifacts/react-migration/pytest-20260509-02-react-ui-tail.json` + test singoli | Batch fino a item 84 confermati; item 84 passato dopo fix `_LEGACY_OPERATIONAL_PREFIXES`. Riprendere da item 85. |
| `01-flask-core` item 1-119 | OK | `artifacts/react-migration/pytest-20260509-01-flask-core-tail-110.json` + test mirato | Item 116 confermato dopo fix stub `LocalAIService`. Riprendere da item 120. |
| `01-flask-core` tail da item 130 | OK | `artifacts/react-migration/pytest-20260509-01-flask-core-tail-130.json` | 2/2 batch item passati. Fase 01 confermata completa. |
| `02-react-ui` item 1-140 | OK | `artifacts/react-migration/pytest-20260509-02-react-ui-tail-125.json` + test singoli | Tail finale 125-139 passato. Fase 02 confermata completa. |
| `05-documents` item 1-84 | OK | `artifacts/react-migration/pytest-20260509-05-documents-tail-30.json` + test mirati | Item 81-82 confermati dopo hardening `EditorAIRepository`. Riprendere da item 85. |
| `05-documents` tail da item 85 | OK | `artifacts/react-migration/pytest-20260509-05-documents-tail-85.json` | 12/12 batch item passati. Fase 05 confermata completa. |
| `03-core-business` completa | OK | `artifacts/react-migration/pytest-20260509-03-core-business-tail-230.json`, `artifacts/react-migration/pytest-20260509-03-core-business-tail-375.json`, `artifacts/react-migration/pytest-20260509-03-core-business-tail-445.json` + test singoli | Fase 03 confermata completa con shard/sotto-shard. Resta documentato il batch 4 timeout come timeout largo isolato, non come verde monolitico. |
| `07-lex-ai` item 1-74 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai.json` + test mirato | Item 74 confermato dopo fix giurisprudenza specifica. Riprendere da item 75. |
| `07-lex-ai` item 75-94 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-75.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-80.json` + test mirati | Item 76 e 93-94 corretti e confermati miratamente; riprendere da item 95. |
| `07-lex-ai` item 95-104 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-95.json` + test mirati | Item 104 corretto e confermato; riprendere da item 105. |
| `07-lex-ai` item 105-109 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-105.json` + test mirati | Item 107 corretto e confermato con l'intero file router; riprendere da item 110. |
| `07-lex-ai` item 110-179 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-110.json` + sotto-shard singoli | Batch 1-13 OK; batch 14 timeout largo isolato, cinque item confermati singolarmente. Riprendere da item 180. |
| `07-lex-ai` item 180-529 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-180.json` + test mirati | Batch 1-69 OK; batch 70 aveva una failure Local AI corretta e verificata. Riprendere da item 530. |
| `07-lex-ai` item 530-549 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-530.json` + sotto-shard singoli | Batch 1-3 OK; batch 4 timeout largo isolato, cinque item confermati singolarmente. Riprendere da item 550. |
| `07-lex-ai` item 550-554 | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-550.json` + test mirato | Item 552 corretto e confermato; riprendere da item 555. |
| `07-lex-ai` completa | OK | `artifacts/react-migration/pytest-20260509-07-lex-ai.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-75.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-80.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-95.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-105.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-110.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-180.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-530.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-550.json`, `artifacts/react-migration/pytest-20260509-07-lex-ai-tail-555.json` + sotto-shard singoli | Fase 07 confermata completa con shard/sotto-shard. Timeout larghi isolati: follow-up lenti e Local AI API context; nessun timeout dichiarato verde monolitico. |
| `04-storage` item batch 1-14 | OK | `artifacts/react-migration/pytest-20260509-04-storage.json` | Passati fino al batch precedente al fallback PostgreSQL coverage. |
| `04-storage` tail da item 70 | OK | `artifacts/react-migration/pytest-20260509-04-storage-tail-70.json` | 22/22 batch item passati dopo fix fallback PostgreSQL coverage. Fase 04 confermata completa. |
| `09-misc` tail da item 15 | OK | `artifacts/react-migration/pytest-20260509-09-misc-tail-15.json` | 14/14 batch item passati. Fase 09 confermata completa. |
| `03-core-business` item batch 1-22 | OK | `artifacts/react-migration/pytest-20260509-03-core-business-items.json` | Passati fino al blocco precedente ai test preventivi lenti. |
| `03-core-business` blocco preventivi/conferimento lento | OK a test singoli | Output sessione 2026-05-09 | I 10 test del batch lento sono passati singolarmente; il timeout era da raggruppamento, non da failure funzionale. |
| `01-flask-core` item batch 1-22 | OK | `artifacts/react-migration/pytest-20260509-01-flask-core-items.json` | Passati fino al batch precedente al controllo Docker Hetzner. |
| `05-documents` item batch 1-3 | OK | `artifacts/react-migration/pytest-20260509-05-documents.json` | Passati fino al batch precedente a `DocumentAIRepository.from_sqlite_db`. |
| `09-misc` item batch 1-3 | OK | `artifacts/react-migration/pytest-20260509-09-misc.json` | Passati fino al batch precedente al test email/base template. |

## Nota pytest monolitico

`python -m pytest -q` monolitico non viene usato come dichiarazione di verde totale in locale perche' va in timeout. Il gate viene verificato tramite shard/sotto-shard con timeout per job, isolando i test lenti e correggendo le failure reali.
