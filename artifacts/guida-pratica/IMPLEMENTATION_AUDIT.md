# Audit implementazione Guida Pratica - 2026-05-22

## Esito

- Catalogo ufficiale PST/XSD mantenuto come fonte di deposito: 1.018 record.
- Guide ufficiali curate: 1.018 su 1.018.
- Codici ufficiali senza guida curata: 0.
- Incoerenze tra catalogo ufficiale e stato depositabile: 0.
- Alias/schede interne non depositabili: 49, mantenute come guida interna e bloccate per la generazione deposito.
- Guida Pratica disponibile anche a Lex come fonte interna conversazionale tramite `GuidaPraticaSource`, senza rendere la guida un requisito bloccante del fascicolo.
- Vecchio blocco UI sperimentale rimosso dal servizio e dal componente React: non rientrano più le frasi `Scheda pratica suggerita...` / `Scheda pratica individuata...`, la progressione `0/16 requisiti` e il profilo immobiliare `Vendita di cose immobili / Scheda 140011` come pannello operativo.

## File audit

- `artifacts/guida-pratica/guida-pratica-audit.json`
- `artifacts/guida-pratica/codici-ufficiali-senza-guida-curata.csv`
- `artifacts/guida-pratica/guida-pratica-coverage.csv`
- `artifacts/guida-pratica/browser-guida-pratica-report.json`
- `artifacts/guida-pratica/browser-guida-pratica-ui-removal-report.json`
- `artifacts/guida-pratica/utf8-integrity-report.json`
- `artifacts/guida-pratica/utf8-integrity-large-report.json`
- `artifacts/guida-pratica/kb-set4-parte2-import-report.json`
- `artifacts/guida-pratica/termini-processuali-set4-parte2-import-report.json`
- `artifacts/guida-pratica/termini-processuali-set4-parte2-kb-audit.csv`

## Verifiche eseguite

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python scripts\validate_codici_oggetto_pst.py --min-records 1000` | OK | 1.018 record, duplicati 0, invalidi 0, descrizioni mancanti 0. |
| `python scripts\verify_pst_xsd_catalog.py` | OK | Catalogo PST/XSD ufficiale integro: 1.018 record validi. |
| `python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated ...` | OK | 1.018 codici ufficiali curati, 0 senza guida, coerenza deposito OK, 49 alias interni non depositabili. |
| `python scripts\import_guida_pratica_termini_processuali.py --report artifacts\guida-pratica\termini-processuali-set4-parte2-import-report.json --csv artifacts\guida-pratica\termini-processuali-set4-parte2-kb-audit.csv` | OK | 2.895 termini importati, 832 template calcolabili e audit termini aggiornato. |
| `python scripts\audit_guida_pratica_user_material_fields.py --fail-on-loss --report ...latest.json --csv ...latest.csv` | OK | 7 file utente, 36 schede, 724 righe, 0 voci perse tra file ricevuti, KB, servizio/API, UI e Lex. |
| `python -m pytest tests\test_guida_pratica_api.py::test_template_filtrato_da_guida_pratica_espone_anteprima_operativa tests\test_guida_pratica_api.py::test_guida_pratica_api_agganciata_al_fascicolo tests\test_react_shell.py::test_post_nuovo_fascicolo_con_cliente_apre_il_fascicolo -q --tb=short` | OK | Template filtrato dalla Guida Pratica, import documento, anteprima PDF, salvataggio nel fascicolo e redirect nuovo fascicolo verso fascicolo reale governati da test. |
| `python -m pytest tests\test_template_atti_master_catalog.py tests\test_guida_pratica_api.py::test_template_filtrato_da_guida_pratica_espone_anteprima_operativa -q --tb=short` | OK | Il catalogo resta a 192 modelli operativi storici e gli alias core come `GDP_001` aprono il compilatore reale solo quando richiesti. |
| Browser su `http://127.0.0.1:8080/fascicoli/nuovo` | OK | Pagina reale caricata, nessuna occorrenza del vecchio blocco `Vendita di cose immobili / Scheda 140011`, nessuna frase `Scheda pratica suggerita...` o `Scheda pratica individuata...`, zero errori console. |
| `python -m pytest -q tests\test_guida_pratica_api.py lex\tests\unit\test_guida_pratica_source.py tests\test_react_document_editor.py tests\test_import_guida_pratica_termini_processuali.py tests\test_curate_codex_guida_pratica_completion.py tests\test_guida_pratica_service.py tests\test_pst_xsd_catalog_importer.py ...` | OK | 42 test passati sul perimetro Guida Pratica, Lex, import termini, editor documento, catalogo PST/XSD e Impostazioni. |
| `npm run build` da `frontend` | OK | TypeScript e build Vite completati dopo la rimozione del vecchio contesto UI e l'aggiornamento dei bundle React. |
| `python -m pct.cli utf8-integrity --check-only --root ... --report artifacts\guida-pratica\utf8-integrity-guida-pratica-latest.json --json` | OK | 4 file testuali controllati, 0 artefatti di encoding, 0 riparazioni necessarie. |
| `python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py tests\test_import_pst_xsd_codici_oggetto.py tests\test_pst_xsd_catalog_importer.py tests\test_codici_oggetto_pst_catalog.py tests\test_react_shell.py::test_react_blueprints_registered -q --tb=short` | OK | 23 test passati. |
| `python -m pytest lex\tests\unit\test_guida_pratica_source.py lex\tests\unit\test_retrieval_orchestrator.py lex\tests\unit\test_deterministic_provider.py lex\tests\unit\test_router.py tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py -q --tb=short` | OK | 46 test passati: Lex recupera la guida completa, risponde in modo conversazionale e non confonde alias interni con codici ufficiali di deposito. |
| `python -m ruff check ...` | OK | Ruff verde sul perimetro guida, catalogo, API e test. |
| `pnpm --filter @iusentra/studio typecheck` | OK | TypeScript senza errori. |
| `pnpm --filter @iusentra/studio build` | OK | Build Vite completata su versione 2.248.11. |
| `python -m pytest tests\test_guida_pratica_api.py::test_guida_pratica_api_fascicolo_react_legge_stesso_fascicolo_json_legacy -q --tb=short` | OK | Il dettaglio React e la Guida Pratica leggono lo stesso fascicolo JSON legacy anche con SQLite operativo non popolato. |
| Browser desktop/tablet/mobile su fascicolo con codice `220101` | OK | Guida visibile, badge `Uso facoltativo`, badge `Scheda collegata`, badge `Guida curata`, nessun `Codice PST verificato`, nessun overflow orizzontale, nessun errore console, nessun testo tecnico vietato. |
| `python -m pct.cli utf8-integrity ...` | OK | UTF-8 valido sui file guida e UI; i due JSON grandi verificati con soglia 12 MB. |
| `python scripts\react-migration\generate_api_contracts.py --check`; `python scripts\validate_openapi.py docs\openapi.yaml`; `python scripts\verify_openapi_provider.py`; `python -m pytest tests\test_openapi_contracts_phase6.py -q --tb=short` | OK | Contratti API riallineati, OpenAPI valido, provider verification OK e test OpenAPI 5/5. |
| `python -m pytest tests\test_procedure_inventory_importer.py tests\test_procedure_xsd_mapper.py tests\test_procedure_source_research.py tests\test_procedure_knowledge_pipeline.py tests\test_procedure_lifecycle.py tests\test_digital_signature_workflow.py tests\test_telematic_deposit_workflow.py tests\test_post_acceptance_obligations.py tests\test_notification_workflow.py tests\test_evidence_vault.py tests\test_procedure_coverage_ext.py tests\test_procedure_lifecycle_repository.py tests\test_procedure_lifecycle_edges.py -q --tb=short` | OK | 33/33 passati sul perimetro deposito, XSD, firma, notifiche e lifecycle procedura. |
| Docker locale no-cache + container audit | OK | Primo tentativo intercettato con download Dart Sass troncato; Dockerfile reso robusto con retry e archivio temporaneo. Rilancio `docker compose build --no-cache app scheduler-worker ocr-worker` completato; container app/OCR/scheduler/redis healthy; `/api/pronto` espone `2.248.11`; validatore Guida Pratica nel container OK con 1.018/1.018 ufficiali curati. |
| `python scripts\smoke_app_v2_all.py --subset contracts`; `python scripts\smoke_app_v2_all.py --subset inventory` | OK | Smoke contratti offline PASS=2/SKIP live runtime previsto; inventory PASS=3. |
| `python tools\check_repo_governance.py`; `python scripts\validate_docs_links.py ...`; `python scripts\validate_docs_commands.py`; packaging/readiness/UTF-8 | OK | Governance repo OK, link e comandi documentali validi, packaging sincronizzato, 13 test readiness/UTF-8 passati e scan UTF-8 mirato OK. |

## Lista codici ufficiali senza guida curata

Nessuno. Il CSV `artifacts/guida-pratica/codici-ufficiali-senza-guida-curata.csv` contiene solo l'intestazione.

## Nota operativa su audit voce per voce

L'audit voce per voce aggiornato è disponibile in `artifacts/guida-pratica/guida-pratica-user-material-field-audit-latest.json` e `artifacts/guida-pratica/guida-pratica-user-material-field-audit-latest.csv`. Il CSV canonico `artifacts/guida-pratica/guida-pratica-user-material-field-audit.csv` risulta temporaneamente aperto da un altro processo Windows; il JSON canonico è aggiornato, mentre il CSV canonico va riallineato appena il file non è più bloccato.

## Nota operativa su anteprima, template filtrato e import

La pagina reale `/template-atti/compila/<codice>` deve riprodurre il mockup approvato quando arriva dalla Guida Pratica con `id_fascicolo`, `guida_pratica` e `origine=guida_pratica`: template già filtrato, caricamento automatico del modello suggerito, import PDF/DOC/DOCX, anteprima PDF e salvataggio nel fascicolo senza chiudere il fascicolo. Il confronto visivo deve usare gli screenshot canonici in `artifacts/guida-pratica/mockups/pacchetto-completo-v2/`.
