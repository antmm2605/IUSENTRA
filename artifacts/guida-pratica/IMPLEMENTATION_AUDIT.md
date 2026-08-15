# Audit implementazione Guida Pratica - 2026-05-23

## Aggiornamento set42–49 — 15 agosto 2026

- Materiale esaminato: 80 JSON giuridici negli archivi `files (31).zip`–`files (38).zip`, per 400 schede e 400 termini; 11 DOCX nell'archivio `files (30).zip`, esclusi perché temi scolastici di attualità estranei alla guida professionale.
- Import eseguito: 399 schede distribuite in 80 moduli `kb_98_set42_*`–`kb_98_set49_*`; 399 termini aggiunti al repository runtime, che passa a 4.307 record e 1.263 template calcolabili.
- Deduplicazione: la sorgente `415120` è stata esclusa perché già coperta dalla guida canonica `GUIDA_ESECUTORE_TESTAMENTARIO_NOMINA_POTERI_E_RESPONSABILIT_ARTT_700_712_C_C_415055`; la divergenza contenutistica è registrata nel report di import, senza creare una seconda guida concorrente.
- Sicurezza deposito: 399/399 schede importate sono alias interni non depositabili; catalogo PST/XSD invariato a 1.018 codici ufficiali, con zero contaminazioni di deposito.
- Audit dati: 1.145 record utente controllati, zero perdite tra modulo, KB completo, servizio/API, UI e Lex; validazione catalogo 2.154/2.154 schede curate, 1.018/1.018 codici ufficiali coperti, zero mancanti e zero incoerenze.
- UTF-8: 80 moduli controllati, zero artefatti, zero errori e zero riparazioni necessarie (`utf8-integrity-set42-49-2026-08-15.json`).
- Prova visiva reale: eseguita sulla copia Docker `http://127.0.0.1:8080`, release `2.278.57`, fascicolo `DD242366`. Il pannello Guida Pratica ha caricato la scheda collegata; click reale sulla tab Normativa, hover e focus del controllo verificati; nessun errore console. Il refresh a cache calda ha completato in circa 1,6 secondi. Desktop, tablet 768×1024 e mobile 390×844 sono stati controllati con scorrimento fino al fondo: nessun overflow orizzontale e nessun contenuto tagliato nel pannello guida.

## Esito

- Catalogo ufficiale PST/XSD mantenuto come fonte di deposito: 1.018 record.
- Guide ufficiali curate: 1.018 su 1.018.
- Schede complessive nel KB completo: 1.080.
- Codici ufficiali senza guida curata: 0.
- Incoerenze tra catalogo ufficiale e stato depositabile: 0.
- Alias/schede interne non depositabili: 62, mantenute come guida interna e bloccate per la generazione deposito.
- TOP9 set6 integrato: otto nuovi alias interni conservano il codice ricevuto senza sovrascrivere il catalogo ministeriale; `111003` resta codice ufficiale depositabile.
- Guida Pratica disponibile anche a Lex come fonte interna conversazionale tramite `GuidaPraticaSource`, con ragionamento operativo e voci specialistiche della scheda, senza rendere la guida un requisito bloccante del fascicolo.
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
- `artifacts/guida-pratica/kb-set5-parte1-import-report.json`
- `artifacts/guida-pratica/kb-set5-parte2-import-report.json`
- `artifacts/guida-pratica/kb-set5-structural-validation-report.json`
- `artifacts/guida-pratica/kb-set6-parte1-import-report.json`
- `artifacts/guida-pratica/kb-set6-parte2-import-report.json`
- `artifacts/guida-pratica/kb-set6-structural-validation-report.json`
- `artifacts/guida-pratica/guida-pratica-user-material-field-audit-latest.json`
- `artifacts/guida-pratica/guida-pratica-user-material-field-audit-latest.csv`
- `artifacts/guida-pratica/termini-processuali-set5-dry-run-report.json`
- `artifacts/guida-pratica/termini-processuali-set5-dry-run-audit.csv`
- `artifacts/guida-pratica/termini-processuali-set6-dry-run-report.json`
- `artifacts/guida-pratica/termini-processuali-set6-dry-run-audit.csv`
- `artifacts/guida-pratica/utf8-integrity-set5-report.json`
- `artifacts/guida-pratica/termini-processuali-set4-parte2-import-report.json`
- `artifacts/guida-pratica/termini-processuali-set4-parte2-kb-audit.csv`

## Verifiche eseguite

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| Validazione `scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated ...` | OK | JSON leggibile, 1.080 schede curate, 1.018/1.018 codici ufficiali coperti, 0 mancanti, 0 incoerenze deposito, 62 alias interni non depositabili. |
| Controllo PowerShell UTF-8/BOM sui moduli e report set5 | OK | File scritti in UTF-8 senza BOM; nessun byte sostitutivo rilevato nei moduli `kb_98_top9_set5_parte1.json`, `kb_98_top9_set5_parte2.json` e nei due report di import. |
| Runtime Python/Node locale | OK | Installati Python 3.12 e Node LTS in scope utente, creata `.venv` locale e sbloccati i gate mirati. Docker locale resta non disponibile su questa macchina Windows senza WSL/daemon, da coprire con deploy remoto e check GitHub. |
| `python -m py_compile ...`; `python -m ruff check ...` | OK | Sintassi e Ruff verdi su merge KB, audit materiale utente, validatore e test servizio. |
| `python scripts\audit_guida_pratica_user_material_fields.py --fail-on-loss ...` | OK | 11 moduli utente, 54 schede, 1.095 righe, 918 voci presenti, 0 perdite tra KB, servizio/API, UI e Lex, 0 valori scalar sostituiti nel servizio. |
| `python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py lex\tests\unit\test_guida_pratica_source.py tests\test_import_guida_pratica_termini_processuali.py -q --tb=short` | OK | 40 test mirati passati sul perimetro Guida Pratica, API, Lex e import termini. |
| `python scripts\import_guida_pratica_termini_processuali.py --dry-run ...set6...` | OK | 2.987 termini letti dalla KB, 894 template calcolabili; nessuna scrittura runtime in `data/scadenziario`. |
| Flask `test_client` su catalogo e codici set6 rappresentativi | OK | API UI collegata al KB completo: catalogo 1.080/1.080 curato, `111003` depositabile, alias interni set6 visibili ma non depositabili. |
| `python -m pct.cli utf8-integrity --check-only ...`; controlli React equivalenti a `pnpm test`; `tsc --noEmit`; `vite build` con `node.exe` esplicito | OK | UTF-8 mirato verde; contratti React, audit preset, UI coverage, TypeScript e build Vite completati. Gli aggregati `pnpm` sono stati scomposti perché la policy PowerShell locale blocca gli shim del PATH. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_utf8_integrity.py -q --tb=short`; `python scripts\react-migration\generate_api_contracts.py --check`; `python scripts\validate_openapi.py docs\openapi.yaml`; `python scripts\verify_openapi_provider.py` | OK | Packaging/readiness/UTF-8, contratti API, OpenAPI e provider verification riallineati alla versione `2.248.19`. |
| `python scripts\validate_codici_oggetto_pst.py --min-records 1000` | OK | 1.018 record, duplicati 0, invalidi 0, descrizioni mancanti 0. |
| `python scripts\verify_pst_xsd_catalog.py` | OK | Catalogo PST/XSD ufficiale integro: 1.018 record validi. |
| `python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated ...` | OK storico 2.248.11 | 1.018 codici ufficiali curati, 0 senza guida, coerenza deposito OK, 49 alias interni non depositabili prima dell'import set5; la verifica strutturale corrente sopra registra 54 alias. |
| `python scripts\import_guida_pratica_termini_processuali.py --report artifacts\guida-pratica\termini-processuali-set4-parte2-import-report.json --csv artifacts\guida-pratica\termini-processuali-set4-parte2-kb-audit.csv` | OK | 2.895 termini importati, 832 template calcolabili e audit termini aggiornato. |
| `python scripts\audit_guida_pratica_user_material_fields.py --fail-on-loss --report ...latest.json --csv ...latest.csv` | OK storico 2.248.11 | 7 file utente, 36 schede, 724 righe, 0 voci perse fino al set4; il set5 è registrato nei report di import e va incluso nel prossimo audit Python completo. |
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
