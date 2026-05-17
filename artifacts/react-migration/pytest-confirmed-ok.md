# Pytest shard confermati OK

Aggiornato: 2026-05-17, agenti fonte legale 2.245.0, no backup.

## Regola operativa

Questi comandi o shard sono stati verificati in questa sessione e non vanno rilanciati a vuoto. Si ripetono solo se viene toccato codice collegato al loro perimetro, oppure come ultimo gate aggregato prima di commit/deploy.

## Frontend e gate React

### Agenti fonte legale 2.245.0 - 2026-05-17

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\legal_update_batch_runner.py pct\legal_update_repository.py pct\scheduler_registry.py web\services\legal_update_surface.py` | OK | Sintassi confermata dopo registro `source_agent_runs`, agenti per fonte e colonna Agente nella pagina Fonti. |
| `python -m pytest tests\test_legal_update_batch_runner.py tests\test_scheduler_registry.py tests\test_scheduler_admin.py tests\test_legal_update_surface_jobs.py tests\test_legal_updates_pipeline.py::test_pagina_fonti_mostra_catalogo_professionale_e_ciclo_giornaliero -q --tb=short` | OK | 16/16 passati: runner per fonte, persistenza esiti agente, template fonte allowlist, console pianificazioni e pagina fonti. |
| `python -m ruff check pct\legal_update_batch_runner.py pct\legal_update_repository.py pct\scheduler_registry.py web\services\legal_update_surface.py tests\test_legal_update_batch_runner.py tests\test_scheduler_registry.py tests\test_scheduler_admin.py tests\test_legal_updates_pipeline.py` | OK | Ruff mirato verde sui file toccati dagli agenti fonte. |

### Console pianificazioni superadmin 2.244.0 - 2026-05-17

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\scheduler_registry.py pct\scheduler.py web\services\scheduler_admin_surface.py web\blueprints\scheduler_admin.py web\bootstrap\blueprint_registry.py web\services\auth_runtime.py web\services\tenant_isolation_runtime.py` | OK | Sintassi confermata per registro cronjob, blueprint superadmin, allowlist piattaforma e integrazione scheduler. |
| `python -m pytest tests\test_scheduler_registry.py tests\test_scheduler_worker.py -q --tb=short` | OK | 6/6 passati: creazione agenti da template autorizzato, blocco template non autorizzati, richieste manuali e job `scheduler_registry_reload`. |
| `python -m pytest tests\test_scheduler_admin.py -q --tb=short` | OK | 3/3 passati: `/admin/pianificazioni`, alias `/admin/cronjob`, creazione agente e richiesta esecuzione. |
| `python -m pytest tests\test_operational_surfaces.py::test_superadmin_product_surfaces_renderizzano -q --tb=short` | OK | La superficie superadmin renderizza anche `Pianificazioni` e mostra gli agenti delegati disponibili. |
| `python -m ruff check pct\scheduler_registry.py pct\scheduler.py web\services\scheduler_admin_surface.py web\blueprints\scheduler_admin.py tests\test_scheduler_registry.py tests\test_scheduler_admin.py tests\test_scheduler_worker.py tests\test_operational_surfaces.py` | OK | Ruff mirato verde sui file della console pianificazioni. |
| `python -m pytest tests\test_scheduler_registry.py tests\test_scheduler_admin.py tests\test_scheduler_worker.py tests\test_operational_surfaces.py::test_superadmin_product_surfaces_renderizzano tests\test_legal_updates_pipeline.py::test_pagina_fonti_mostra_catalogo_professionale_e_ciclo_giornaliero tests\test_legal_updates_pipeline.py::test_verifica_web_legge_allegati_della_fonte_ufficiale tests\test_react_legal_intelligence_search.py tests\test_normattiva_client.py -q --tb=short` | OK | 21/21 passati sul perimetro integrato pianificazioni, catalogo fonti, verifica allegati web, Ricerca Legale e Normattiva. |
| `npm --prefix frontend run typecheck -- --pretty false`; `npm --prefix frontend run build` | OK | TypeScript e build Vite verdi; gli asset hashati generati localmente sono stati ripuliti perche' il Dockerfile li rigenera in deploy. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short`; `python scripts\validate_docs_links.py docs\LEX_PUBLIC_SOURCES_AND_STUDIO_DATA_AUDIT.md docs\REACT_MIGRATION_MASTER_PLAN.md docs\DEPLOY_HETZNER_CPX42.md CHANGELOG.md artifacts\react-migration\pytest-confirmed-ok.md`; `python scripts\validate_docs_commands.py`; `git diff --check -- . ':!data/*'` | OK | Packaging sincronizzato, readiness 8/8, documentazione validata e whitespace pulito dopo bump `2.244.0`. |

### Catalogo fonti legali 2.243.9 - 2026-05-17

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\legal_update_repository.py pct\legal_update_pipeline.py pct\scheduler.py lex\research\official_sources.py web\services\legal_update_surface.py web\blueprints\legal_updates_admin.py` | OK | Sintassi confermata dopo catalogo fonti, nuove fonti ufficiali e riepiloghi per fonte. |
| `python -m pytest tests\test_legal_updates_pipeline.py::test_fonti_default_includono_presidi_utili_per_studi_legali tests\test_legal_updates_pipeline.py::test_feed_xml_con_content_type_generico_importa_fonti_ufficiali tests\test_legal_updates_pipeline.py::test_pagina_fonti_mostra_catalogo_professionale_e_ciclo_giornaliero tests\test_legal_updates_pipeline.py::test_admin_surfaces_renderizzano_fonti_staging_analisi_e_archivio -q --tb=short` | OK | 4/4 passati: catalogo professionale, fonti aggiunte da IUSENTRA, RSS Curia con intestazione generica e render admin. |
| `python -m ruff check pct\legal_update_repository.py pct\legal_update_pipeline.py pct\scheduler.py lex\research\official_sources.py web\services\legal_update_surface.py web\blueprints\legal_updates_admin.py tests\test_legal_updates_pipeline.py` | OK | Ruff mirato verde sui file toccati dal catalogo fonti. |

### Archivi ufficiali visibili 2.243.8 - 2026-05-17

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile lex\retrieval\official_sources_retriever.py web\services\react_legal_intelligence_bridge.py web\services\legal_update_surface.py` | OK | Sintassi confermata dopo aggancio Normattiva/Gazzetta alla Ricerca Legale e alla console Aggiornamenti legali. |
| `python -m pytest tests\test_react_legal_intelligence_search.py tests\test_legal_update_surface_jobs.py tests\test_official_sources_registry.py tests\test_normattiva_importer.py -q --tb=short` | OK | 11/11 passati: la Ricerca Legale usa gli archivi ufficiali locali prima della ricerca web e mostra i conteggi reali Normattiva/Gazzetta. |
| `python -m py_compile pct\legal_update_web_verification.py pct\legal_update_pipeline.py` | OK | Sintassi confermata dopo verifica web multi-query, lettura contesto pagina e allegati ufficiali governati. |
| `python -m pytest tests\test_legal_updates_pipeline.py::test_verifica_normativa_usa_archivi_locali_web_e_contesto tests\test_legal_updates_pipeline.py::test_verifica_web_legge_allegati_della_fonte_ufficiale tests\test_legal_updates_pipeline.py::test_legal_update_autopubblica_senza_reinserire_contenuti_gia_presenti tests\test_legal_updates_pipeline.py::test_legal_update_autopubblica_attende_conferme_web tests\test_react_legal_intelligence_search.py tests\test_legal_update_surface_jobs.py tests\test_official_sources_registry.py tests\test_normattiva_importer.py -q --tb=short` | OK | 15/15 passati: verifica con archivi locali, web esterno e allegati ufficiali, piu' regressioni autopubblicazione governata. |
| `python -m pytest tests\test_legal_updates_pipeline.py tests\test_normattiva_client.py tests\test_scheduler_worker.py -q --tb=short` | OK | 37/37 passati: scheduler 23:00/23:10/23:15, OpenGA completo, fonti aggiuntive, skip Normattiva invariata e pipeline Update Intelligence. |
| `python -m ruff check pct\scheduler.py pct\legal_update_pipeline.py pct\legal_update_repository.py pct\legal_update_web_verification.py lex\normativa\normattiva_client.py tools\normattiva_multi_sync.py tools\gazzetta_ufficiale_sync.py tests\test_legal_updates_pipeline.py tests\test_normattiva_client.py tests\test_scheduler_worker.py` | OK | Ruff mirato verde sul ciclo quotidiano fonti ufficiali e downloader Normattiva. |
| Probe OpenGA API `package_search?fq=groups:<categoria>&rows=200` per Calendario Udienze, Decreti, Ordinanze, Pareri, Provvedimenti pubblicati, Ricorsi definiti, Ricorsi pendenti, Ricorsi pervenuti e Sentenze | OK | Tutte le categorie rispondono 200/success; le categorie da 31 dataset espongono 31 risultati con `rows=200` invece dei 10 default di `group_show`. |
| `npm --prefix frontend run typecheck -- --pretty false`; `npm --prefix frontend run build` | OK | TypeScript e build Vite verdi; il Dockerfile rigenera il bundle in deploy, gli asset hashati locali non sono stati committati. |
| `python -m pytest tests\test_react_legal_intelligence_search.py tests\test_legal_update_surface_jobs.py tests\test_official_sources_registry.py tests\test_normattiva_importer.py tests\test_normattiva_client.py tests\test_scheduler_worker.py -q --tb=short` | OK | 16/16 passati su Ricerca Legale, superficie admin, registry fonti, Normattiva e scheduler. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short`; `python scripts\validate_docs_links.py docs\LEX_PUBLIC_SOURCES_AND_STUDIO_DATA_AUDIT.md docs\REACT_MIGRATION_MASTER_PLAN.md docs\DEPLOY_HETZNER_CPX42.md CHANGELOG.md`; `python scripts\validate_docs_commands.py`; `git diff --check -- . ':!data/*'` | OK | Packaging sincronizzato, readiness 8/8, documentazione validata e whitespace check pulito dopo bump `2.243.8`. |

### Update Intelligence staging automatico 2.243.6 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\legal_update_pipeline.py pct\legal_update_repository.py web\blueprints\legal_updates_admin.py` | OK | Sintassi confermata dopo riconciliazione staging, chiusura cataloghi open data e nuove etichette operative. |
| `python -m pytest tests\test_legal_updates_pipeline.py::test_open_data_cataloghi_vengono_archiviati_senza_review_manuale tests\test_legal_updates_pipeline.py::test_autopublish_risolve_needs_review_ufficiale_in_notizia tests\test_legal_updates_pipeline.py::test_admin_review_mostra_etichette_operative_senza_codici_grezzi -q --tb=short` | OK | 3/3 passati sui regressi utente: niente `Da valutare` nello staging, cataloghi open data chiusi, contenuti ufficiali informativi pubblicabili automaticamente. |
| `python -m pytest tests\test_legal_updates_pipeline.py::test_admin_studio_accede_review_aggiornamenti_legali_senza_403 tests\test_legal_updates_pipeline.py::test_admin_review_mostra_etichette_operative_senza_codici_grezzi -q --tb=short` | OK | 2/2 passati dopo il fix 403: un amministratore di studio con permessi admin/AI apre `/admin/aggiornamenti-legali/review` senza blocco, e le etichette operative restano pulite. |
| `python -m pytest tests\test_legal_updates_pipeline.py tests\test_normattiva_client.py tests\test_normattiva_importer.py -q --tb=short` | OK | 31/31 passati: pipeline aggiornamenti legali, client Normattiva e importer confermati dopo la modifica e il fix accesso review. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging e release readiness 8/8 confermati dopo bump `2.243.6`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; rebuild correttivo finale; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx` | OK | Docker locale `2.243.6`: app/scheduler/OCR/Redis/nginx healthy; `/api/pronto` locale 200 con `versione=2.243.6`; container app `pct.__version__ == 2.243.6`. |
| Smoke HTTP autenticato `GET /admin/aggiornamenti-legali/review` e `GET /admin/aggiornamenti-legali/staging` su Docker locale | OK | Review 200 in 0,55 s senza 403; staging 200 in 6,09 s, senza testo `Da valutare`, codici `pending`, `NEW_NORMATIVE` o `NEEDS_REVIEW`; la pagina esegue solo riconciliazione leggera della coda, non import massivo. |
| Normattiva Open Data Hetzner da documentazione ufficiale | OK | Letto il manifest ufficiale da `dati.normattiva.it`: 23 collezioni elencate, 19 ZIP validi nel volume `/data/normativa/raw`, DB attivo 189.851 documenti, 800.757 articoli, 639.273 chunk; quattro collezioni restano a stream vuoto e sono registrate nel manifest tentativi. |

### Update Intelligence verificata 2.243.5 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\legal_update_pipeline.py pct\legal_update_web_verification.py web\blueprints\legal_updates_admin.py lex\retrieval\official_sources_retriever.py` | OK | Sintassi confermata dopo verifica pubblica governata e risoluzione path runtime `/data`. |
| `python -m pytest tests\test_legal_updates_pipeline.py -q --tb=short` | OK | 25/25 passati: autopublish con conferme web, blocco se conferme insufficienti, UI review senza codici grezzi e superfici admin Update Intelligence. |
| `python -m pytest tests\test_legal_updates_pipeline.py::test_admin_review_mostra_etichette_operative_senza_codici_grezzi tests\test_legal_updates_pipeline.py::test_legal_update_autopubblica_attende_conferme_web -q --tb=short` | OK | 2/2 passati sui due regressi principali richiesti: etichette operative e verifica fonti prima della pubblicazione. |
| `python -m pytest tests\test_operational_surfaces.py::test_superadmin_product_surfaces_renderizzano -q --tb=short` | OK | Superfici superadmin con Aggiornamenti legali e Coda revisioni renderizzate. |
| `python -m pytest tests\test_normattiva_client.py tests\test_normattiva_importer.py -q --tb=short` | OK | Percorso client/importer Normattiva confermato dopo skip delle collezioni non servite come ZIP valido. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e readiness 8/8 verdi dopo bump `2.243.5` e nuove dipendenze crawler. |
| Ricostruzione fonti ufficiali Hetzner `/data` | OK | Gazzetta: 28 documenti, 3.911 chunk, DB 32.129.024 byte, JSONL 20.342.735 byte. Normattiva: 18 ZIP, 189.743 documenti univoci, 800.757 articoli, 638.836 chunk, DB 2.866.860.032 byte, JSONL 1.092.175.389 byte. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; readiness locale | OK | Docker locale no-cache `2.243.5`: app/scheduler/OCR/Redis healthy, `/api/pronto` locale 200 con `versione=2.243.5`, `beautifulsoup4` e `feedparser` presenti nel container. |
| HTTP autenticato locale su `/admin/aggiornamenti-legali/analisi` e `/admin/aggiornamenti-legali/review` | OK | Login superadmin con CSRF, H1 `Analisi automatica` e `Coda revisioni aggiornamenti`, pulsante `Pubblica idonei`, assenti stringhe visibili `NEW_NORMATIVE`, `NEW CASE LAW`, `NORMATIVA_AGGIORNAMENTO` e `>pending<`. |

### Registri mediazione interni e Lex 2.243.4 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| Sync live Registro Mediazione dal contesto app Docker | OK | Acquisite 3.035 righe ufficiali: 1.149 organismi, 481 enti e 1.405 formatori; 305 pagine ASP.NET lette dai tre elenchi ministeriali. |
| `python -m py_compile pct\legal_intelligence.py pct\legal_update_pipeline.py pct\legal_update_repository.py web\services\react_legal_intelligence_bridge.py web\services\assistente_studio_context.py lex\retrieval\sources\legal_intelligence.py lex\retrieval\source_router.py web\helpers.py` | OK | Sintassi confermata dopo import registri, bridge Lex e correzione store condiviso per dati pubblici. |
| `python -m pytest -q tests/test_legal_intelligence.py::test_sync_registro_mediazione_elenco_popola_cache tests/test_legal_intelligence.py::test_sync_registro_mediazione_elenco_legge_gridview_ministeriale_paginata tests/test_assistente_studio_context_giurisprudenza.py::test_ricerca_legale_lines_espone_registro_mediazione_a_lex tests/test_legal_updates_pipeline.py::test_normative_slug_duplicate_non_blocca_pubblicazione tests/test_legal_updates_pipeline.py::test_openga_ckan_importa_risorse_json_per_lex --tb=short` | OK | 5/5: import paginato ministeriale, fonte Lex mediazione, slug normativi duplicati e OpenGA CKAN JSON. |
| `python -m pytest -q tests/test_legal_intelligence.py tests/test_react_legal_intelligence_search.py tests/test_assistente_studio_context_giurisprudenza.py --tb=short`; `python -m pytest -q tests/test_legal_updates_pipeline.py --tb=short` | OK | 52 test totali passati sui perimetri Ricerca Legale, Lex e Update Intelligence. |
| `python -m pytest -q tests/test_react_legal_intelligence_search.py::test_mediazione_importata_non_viene_deduplicata_come_solo_link tests/test_react_legal_intelligence_search.py::test_mediazione_espone_accessi_ufficiali_ripristinati --tb=short` | OK | Regressione coperta: i 3.035 record importati non vengono piu' deduplicati come semplici link con lo stesso URL ufficiale. |
| `npm --prefix frontend run typecheck -- --pretty false`; `npm --prefix frontend run build` | OK | TypeScript e build Vite verdi; chunk `LegalIntelligencePage-DUmVLp81.js` 28.44 kB / 8.29 kB gzip, main `index-DfXeVYex.js` 451.74 kB / 133.61 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto` | OK | Docker locale no-cache `2.243.4`: app healthy, scheduler/OCR/Redis healthy, readiness locale 200 con `versione=2.243.4`. |
| API React autenticata `/api/v1/ui/ricerca-legale/mediazione` | OK | 3.038 schede restituite: 3.035 record importati piu' tre accessi ufficiali; primo record importato `ADR Center srl`, sezione `Organismi di mediazione`. |
| Chrome CDP autenticato `artifacts/react-migration/visual-2.243.4-mediazione-registry-final/visual-load-audit.md` | OK | 6/6 su `/ricerca-legale/mediazione` e `/legal-intelligence/mediazione`, desktop/tablet/mobile: 80 righe renderizzate, 5 filtri, zero overflow, zero form POST, zero testo tecnico vietato. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short`; `python scripts\validate_docs_links.py docs\LEGAL_UPDATE_INTELLIGENCE.md docs\LEX_PUBLIC_SOURCES_AND_STUDIO_DATA_AUDIT.md docs\REACT_MIGRATION_MASTER_PLAN.md`; `python scripts\validate_docs_commands.py`; `git diff --check -- . ':!data/*'` | OK | Packaging sincronizzato, readiness release 8/8, documentazione validata e whitespace check pulito sul perimetro non-runtime. |

### Backup preventivo Hetzner 2.243.3 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `bash -n deploy/hetzner/backup.sh deploy/hetzner/deploy.sh`; `python -m pytest tests\test_hetzner_backup_retention.py -q`; `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Script backup sintatticamente valido, test backup 3/3 e packaging/readiness 8/8 verdi dopo il trattamento warning `tar` non fatale e bump `2.243.3`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"`; `git diff --check -- . ':!data/*'` | OK | Docker locale no-cache finale su `2.243.3`: wheel `pct-studio-legale-2.243.3`, app/scheduler/OCR/Redis healthy, readiness locale 200 `versione=2.243.3`, runtime container `2.243.3`, whitespace check pulito. |
| `python scripts\validate_docs_links.py docs\DEPLOY_HETZNER_CPX42.md deploy\hetzner\README.md`; `python scripts\validate_docs_commands.py` | OK | Documentazione Hetzner aggiornata su `npm ci --include=dev` e backup best-effort; link locali e comandi documentati validi. |

### Build Docker frontend Hetzner 2.243.2 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short`; `npm --prefix frontend run build:vite`; `git diff --check -- . ':!data/*'` | OK | Packaging/readiness 8/8, build Vite e whitespace check verdi dopo bump `2.243.2` e hardening del Dockerfile frontend. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Build Docker no-cache riprodotta con `node_modules` esclusi dal contesto: lo stage Vite installa Tailwind/PostCSS con `--include=dev`, wheel `pct-studio-legale-2.243.2`, app/scheduler/OCR/Redis healthy, readiness locale 200 `versione=2.243.2` e runtime container `2.243.2`. |

### Aggiornamenti legali deduplica/autopubblicazione 2.243.1 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall pct\legal_update_repository.py pct\legal_update_pipeline.py pct\legal_update_ai.py web\blueprints\legal_updates_admin.py web\services\legal_update_surface.py pct\scheduler.py pct\cli.py` | OK | Sintassi confermata dopo chiave canonica anti-duplicati, cleanup archivio, filtro utilita' studio legale, autopubblicazione contenuti ufficiali idonei, scheduler notturno e azioni admin/CLI. |
| `python -m pytest tests/test_legal_updates_pipeline.py tests/test_scheduler_worker.py -q` | OK | 23/23 passati: autopubblicazione senza reinserimenti, duplicati giurisprudenziali, cleanup archivio, pagine/API admin Update Intelligence e trigger scheduler 00:00-05:00. |
| `python -m ruff check pct\legal_update_repository.py pct\legal_update_pipeline.py pct\legal_update_ai.py web\blueprints\legal_updates_admin.py web\services\legal_update_surface.py pct\scheduler.py tests\test_legal_updates_pipeline.py tests\test_scheduler_worker.py` | OK | Ruff mirato verde sui file Python modificati, escluso `pct\cli.py` per lint legacy preesistente non collegato alla tranche; `pct\cli.py` e' stato verificato con compileall e help runtime. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging e readiness release 8/8 verdi su versione `2.243.1`; `Dockerfile`, `setup.py`, `railway.toml` e `pct/__init__.py` allineati. |
| `python scripts\validate_docs_links.py docs\LEGAL_UPDATE_INTELLIGENCE.md`; `python scripts\validate_docs_commands.py`; `python -m pct.cli aggiornamenti-legali --help` | OK | Link/comandi documentali validi e nuova opzione CLI `--cleanup-only` esposta correttamente nella console. |
| Cleanup locale archivi `data\intelligence\legal_updates.db`, `data\tenants\antonella-mammola\intelligence\legal_updates.db`, `data\tenants\tenant-8bf98719c459\intelligence\legal_updates.db` | OK | Rimossi 2 doppioni reali: 1 nel tenant `antonella-mammola` e 1 nel tenant `tenant-8bf98719c459`; dopo il riconto tutti e tre gli archivi hanno `groups=0` e `duplicate_items=0`. I database runtime restano non committati. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Build locale no-cache finale completata con wheel `pct-studio-legale-2.243.1`, bundle React ricompilato dal Dockerfile, app/scheduler/OCR/Redis healthy, readiness locale 200 con `versione=2.243.1` e runtime container `2.243.1`. |

### Sito Studio Builder Pro 2.239.1 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run build`; `npm --prefix frontend run test` | OK | TypeScript, build Vite e contratti frontend confermati dopo layout B, pannello ridimensionabile, nuove tab, controlli tipografici, colori, effetti, media e preview live completa. |
| `python -m pytest tests/test_studio_site_builder_api.py tests/test_studio_site_builder_blocks.py tests/test_studio_site_assets.py -q --tb=short` | OK | 7/7 passati: API builder, pagine/blocchi, asset media, persistenza tema/layout/effetti e contratti sito studio restano coerenti. |
| `python -m ruff check pct/studio_site.py pct/studio_site_theme.py web/bootstrap/template_runtime.py web/services/studio_site_builder_runtime.py web/services/react_sito_studio_builder_bridge.py web/blueprints/api_v1_react.py tests/test_studio_site_builder_api.py tests/test_studio_site_builder_blocks.py` | OK | Ruff mirato verde sul perimetro Python modificato, inclusi filtri rich text controllati e salvataggio design settings esteso. |
| `node --check scripts/react-migration/verify-sito-studio-builder-pro.mjs`; `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs` | OK | Script visuale e gate React confermano builder full React, route governata e nessuna regressione nei contratti di routing. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging e readiness release verdi su versione `2.239.1`; Dockerfile, `setup.py`, `railway.toml`, `pct/__init__.py` e pacchetto frontend allineati. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto` | OK | Build locale no-cache completata; app, scheduler, OCR, Redis e nginx avviati; readiness locale 200 con `versione=2.239.1`. |
| `node scripts\react-migration\verify-sito-studio-builder-pro.mjs` | OK | Chrome CDP autenticato su `/sito-studio/builder`: caricamento 1409 ms, pannello 380px, resize 380->480px, preview 1121px, footer live visibile, menu tablet/mobile presente, colori/font/effetti/formattazione/allineamento funzionanti. Report: `artifacts/react-migration/visual-2.239.1-sito-studio-builder/visual-load-audit.md`. |

### Tranche superadmin operativo 2.239.0 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\support_remote.py pct\config_studio.py web\services\runtime_settings.py web\services\support_surface.py web\services\server_maintenance_surface.py`; `python -m ruff check pct\support_remote.py pct\config_studio.py web\services\runtime_settings.py web\services\support_surface.py web\services\server_maintenance_surface.py tests\test_support_remote.py tests\test_server_maintenance_surface.py` | OK | Sintassi e Ruff confermati dopo STUN predefinito, preservazione configurazione pronta, console assistenza pronta all'uso, mappa storage per studio e scansione rapida governata. |
| `python -m pytest tests\test_support_remote.py tests\test_server_maintenance_surface.py -q --tb=short` | OK | 15/15 passati: assistenza remota pronta senza TURN obbligatorio, ICE default disponibile su `/webrtc-config`, salvataggio con STUN vuoto preserva il default, manutenzione server espone categorie, cartelle principali, file pesanti, azioni operative e guardrail anti-scansione lenta. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging e readiness release verdi su versione `2.239.0`; Dockerfile, `setup.py`, `railway.toml` e `pct/__init__.py` allineati. |
| `python scripts\validate_docs_links.py docs\ASSISTENZA_REMOTA.md docs\OBSERVABILITY_AUDIT_PRODUCT.md docs\REACT_MIGRATION_MASTER_PLAN.md`; `python scripts\validate_docs_commands.py` | OK | Link documentali 21/157 e comandi documentali 155/155 confermati dopo aggiornamento assistenza remota, osservabilita' prodotto e master plan. |
| `python -m pytest tests\test_operational_surfaces.py::test_superadmin_product_surfaces_renderizzano -q --tb=short` | OK | Smoke prodotto superadmin confermato dopo le modifiche a `Server e manutenzione` e `Assistenza remota`. |
| `npm --prefix frontend run build` | OK | Build Vite completata in 7.39s; bundle principale invariato `index-Di4ENQKe.js` 451.51 kB / 133.56 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Build no-cache ha creato wheel `pct-studio-legale==2.239.0`; app, scheduler, OCR e Redis healthy; readiness locale 200 con `versione=2.239.0`; runtime container `2.239.0`; `PCT_SUPPORT_STUN_URLS=stun:stun.l.google.com:19302`. |
| Probe autenticato Docker `/admin/supporto-remoto` e `/admin/server-manutenzione`; `build_server_maintenance_surface()` nel container | OK | Login superadmin locale riuscito; assistenza remota 200 in 0.106s con "Pronta per assistenza immediata"; manutenzione server 200 in 2.345s; payload storage 2.339s su due studi, con scansione parziale dichiarata quando scatta il limite operativo. |
| Chromium headless reale su `http://127.0.0.1:8080/admin/supporto-remoto` e `/admin/server-manutenzione`, desktop/tablet/mobile, report `artifacts/react-migration/visual-2.239.0-superadmin-operativo/visual-load-audit.md` | OK | 6/6 viste OK: assistenza 592-673 ms, manutenzione 2812-2854 ms; nessun overflow orizzontale, nessun errore console, nessun testo tecnico vietato (`backend`, `frontend`, `legacy`, `payload`, `runtime`, `json_api`, `provider`, `webhook`, `undefined`, `null`, `demo`, `sample`, `repository`, `endpoint`, `mock_fallback`, `psutil`). |

### Hotfix Copertura AI condivisa 2.238.4 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\legal_coverage_surface.py web\blueprints\legal_coverage_admin.py web\services\core_runtime.py pct\legal_coverage_sqlite_repository.py pct\storage_migration_full.py tests\test_legal_coverage_surface.py tests\test_repository_sql_parity.py tests\test_web_bootstrap.py pct\__init__.py`; `python -m ruff check web\services\legal_coverage_surface.py web\blueprints\legal_coverage_admin.py web\services\core_runtime.py pct\legal_coverage_sqlite_repository.py pct\storage_migration_full.py tests\test_legal_coverage_surface.py tests\test_repository_sql_parity.py tests\test_web_bootstrap.py` | OK | Sintassi e Ruff confermati dopo passaggio di Copertura AI ad archivio condiviso, rimozione selettore studio, blocco dei backend tenant impliciti e allineamento della migrazione storage sul DB coverage di piattaforma. |
| `python -m pytest tests\test_legal_coverage_surface.py tests\test_repository_sql_parity.py::test_coverage_surface_ignora_database_tenant_postgresql_come_fallback tests\test_repository_sql_parity.py::test_coverage_surface_ignora_tenant_unico_con_configurazione_postgres_legacy tests\test_repository_sql_parity.py::test_coverage_surface_usa_postgresql_solo_se_configurato_esplicitamente tests\test_ai_coverage_pipeline.py tests\test_web_bootstrap.py::test_template_principali_usano_copy_italiana_e_date_localizzate -q --tb=short` | OK | 12/12 passati: dashboard/review non espongono piu' selezione studio, `tenant_slug` e `g.tenant` vengono ignorati, `studio.db` e PostgreSQL tenant-aware non sono fallback impliciti, PostgreSQL resta valido se configurato esplicitamente per coverage. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_legal_coverage_surface.py tests\test_repository_sql_parity.py::test_coverage_surface_ignora_database_tenant_postgresql_come_fallback tests\test_repository_sql_parity.py::test_coverage_surface_ignora_tenant_unico_con_configurazione_postgres_legacy tests\test_repository_sql_parity.py::test_coverage_surface_usa_postgresql_solo_se_configurato_esplicitamente tests\test_ai_coverage_pipeline.py tests\test_web_bootstrap.py::test_template_principali_usano_copy_italiana_e_date_localizzate tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_end_to_end_studio.py tests\test_operational_surfaces.py::test_superadmin_product_surfaces_renderizzano -q --tb=short` | OK | Packaging sincronizzato e gate mirato finale 22/22 verde su versione `2.238.4`. |
| `python scripts\validate_docs_links.py README.md docs\LEGAL_COVERAGE_AUTOFILL.md docs\STORAGE_MATRIX.md docs\STORAGE_MIGRATION_PLAN.md docs\REACT_MIGRATION_MASTER_PLAN.md`; `python scripts\validate_docs_commands.py`; `python -m pytest tests\test_end_to_end_studio.py -q --tb=short`; `python -m pytest tests\test_operational_surfaces.py::test_superadmin_product_surfaces_renderizzano -q --tb=short` | OK | Link documentali 21/157 e comandi documentali 155/155 verdi; smoke admin con `/admin/copertura-ai` e review verde; superfici end-to-end admin principali verdi. |

### Hotfix Aggiornamenti legali condivisi 2.238.3 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\legal_update_pipeline.py web\services\legal_update_surface.py web\helpers.py tests\test_legal_updates_pipeline.py`; `python -m py_compile web\blueprints\legal_updates_admin.py pct\__init__.py` | OK | Sintassi confermata dopo passaggio di Update Intelligence ad archivio applicativo condiviso, blocco del DSN tenant implicito e rimozione selezione studio dalla console admin. |
| `python -m pytest tests\test_legal_updates_pipeline.py -q --tb=short` | OK | 18/18 passati: pipeline, admin pages/API, pagina Fonti e regressioni multi-studio confermano che `tenant_slug` viene ignorato e il repository resta quello condiviso. |
| `python -m pytest tests\test_storage_postgres_migration.py::test_copy_legal_updates_to_postgres_migra_news_normativa_e_review -q --tb=short` | OK | Migrazione PostgreSQL esplicita ancora verde: il backend SQL resta disponibile solo quando viene passato un DSN intenzionale, senza ereditarlo dal tenant della request. |
| `python -m py_compile web\services\assistente_studio_context.py tests\test_assistente_studio_context_giurisprudenza.py`; `python -m pytest tests\test_assistente_studio_context_giurisprudenza.py -q --tb=short` | OK | 2/2 passati: il contesto Lex descrive gli aggiornamenti legali come archivio condiviso e non riporta piu' la vecchia dicitura tenant-aware. |
| Controllo template `legal_updates_*.html` su `name="tenant_slug"`, `tenant_slug=`, `Studio attivo`, `tenant selezionato`, `archivi globali impliciti` | OK | Nessuna occorrenza: dashboard, Fonti, Acquisizione, Analisi, Archivio, Review e Dettaglio non espongono piu' selezione studio. |
| `python -m pytest tests\test_react_legal_intelligence_search.py tests\test_assistente_studio_context_giurisprudenza.py -q --tb=short` | OK | 5/5 passati: Ricerca Legale e contesto Lex continuano a leggere `legal_updates.db` dopo il cambio di scope condiviso. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 verde su versione `2.238.3`. |
| `python -m ruff check pct\legal_update_pipeline.py web\services\legal_update_surface.py web\services\assistente_studio_context.py web\blueprints\legal_updates_admin.py web\helpers.py tests\test_legal_updates_pipeline.py tests\test_assistente_studio_context_giurisprudenza.py` | OK | Ruff mirato verde sul perimetro Python modificato. |
| `python scripts\validate_docs_links.py docs\LEGAL_UPDATE_INTELLIGENCE.md docs\STORAGE_MATRIX.md docs\STORAGE_MIGRATION_PLAN.md docs\LEX_PUBLIC_RESEARCH_GATEWAY.md docs\LEX_PUBLIC_LEGAL_SOURCES.md docs\REACT_MIGRATION_MASTER_PLAN.md`; `python scripts\validate_docs_commands.py`; `git diff --check -- <perimetro aggiornamenti legali condivisi>` | OK | Link documentali validi: 21 documenti, 157 link locali; comandi documentali 155/155. Diff check senza errori, con soli warning CRLF informativi su tre documenti. |
| `python -m pytest tests\test_legal_updates_pipeline.py tests\test_assistente_studio_context_giurisprudenza.py tests\test_react_legal_intelligence_search.py tests\test_storage_postgres_migration.py::test_copy_legal_updates_to_postgres_migra_news_normativa_e_review tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short`; `python scripts\validate_docs_commands.py`; `git diff --check -- . ':!data/*'` | OK | Gate finale aggregato 32/32 verde; comandi documentali 155/155; diff check senza errori, con soli warning CRLF informativi sui documenti storage/update intelligence. |

### Hotfix Lex chat sentenze 2.238.2 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile lex\research\source_scope_policy.py lex\retrieval\orchestrator.py lex\retrieval\official_web.py lex\routes.py lex\tests\test_routes.py lex\tests\test_official_web.py lex\tests\unit\test_retrieval_orchestrator.py tests\test_lex_sources_and_studio_data.py tests\test_lex_widget_contract.py` | OK | Sintassi confermata dopo ripristino `SourceScope.reason`, fallback Cassazione esatto, skip della seconda ricerca pubblica, JSON controllato su crash chat e guardia widget anti-HTML. |
| `node --check web\static\js\pct-lex-assistant.js` | OK | Sintassi JS confermata dopo sanitizzazione errori HTTP nel widget Lex. |
| `python -m pytest tests\test_lex_sources_and_studio_data.py::test_source_scope_exact_sentenza tests\test_lex_sources_and_studio_data.py::test_retrieval_exact_sentenza_metadata_non_cade_su_source_scope_reason lex\tests\test_routes.py::test_assistente_chat_failure_returns_json_not_html tests\test_lex_widget_contract.py::test_widget_posts_chat_payload_to_canonical_route lex\tests\test_official_web.py::test_resolve_official_source_ids_prioritizza_cassazione_per_sentenza_esatta lex\tests\test_official_web.py::test_search_recognized_official_web_fallback_cassazione_lista_pubblica lex\tests\unit\test_retrieval_orchestrator.py::test_giurisprudenza_specifica_non_ripete_ricerca_pubblica_se_exact_match_ufficiale -q --tb=short` | OK | 7/7 passati: sentenza 14575 con data deposito, fallback Cassazione, skip della seconda ricerca pubblica, API chat JSON senza HTML e contratto widget. |
| `python -m pytest tests\test_lex_sentenze_clienti_fix.py tests\test_lex_sources_and_studio_data.py lex\tests\test_routes.py tests\test_lex_widget_contract.py lex\tests\test_official_web.py lex\tests\unit\test_retrieval_orchestrator.py -q --tb=short` | OK | Shard aggregato passato sul perimetro sentenze specifiche, fonti pubbliche/dati studio, route Lex, widget, ricerca web ufficiale e retrieval exact-match. |
| Probe bounded Lex locale con query `Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026` | OK | `build_bounded_http_payload` in circa 3031 ms: risposta `Ho individuato la pronuncia richiesta`, link ufficiale `https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP50042`, nessun HTML/doctype, `exact_match_count=1`, `needs_review` per testo integrale/motivazione/dispositivo mancanti. |
| `python -m ruff check lex\research\source_scope_policy.py lex\retrieval\orchestrator.py lex\retrieval\official_web.py lex\routes.py lex\tests\test_routes.py lex\tests\test_official_web.py lex\tests\unit\test_retrieval_orchestrator.py tests\test_lex_sources_and_studio_data.py tests\test_lex_widget_contract.py`; `git diff --check -- . ':!data/*'` | OK | Ruff mirato verde; diff check senza errori, con solo warning CRLF informativo su `web/static/js/pct-lex-assistant.js`. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging/versione `2.238.2` sincronizzati e readiness release 8/8 verde. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | Link e comandi documentali validi dopo aggiornamento changelog, audit Lex e report React. |
| `npm --prefix frontend run build` | OK | TypeScript e build Vite `2.238.2` completati in 7.06s; main `index-Di4ENQKe.js` 451.51 kB / 133.56 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"`; probe bounded Lex nel container | OK | Build no-cache ha creato wheel `pct-studio-legale==2.238.2`; app/scheduler/OCR/Redis healthy. Primo `/api/pronto` durante warm-up post-recreate in timeout, rilancio a caldo 200 con `versione=2.238.2`; runtime container `2.238.2`; probe container Lex in circa 2012 ms con exact match Cassazione `SZP50042`, nessun HTML. |

### Sblocco Lex Operational Knowledge 2.237.9 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests/test_lex_operational_knowledge.py -q --tb=short` | OK | 23/23 passati: Operational Knowledge e' default-on, resta spegnibile con `LEX_OPERATIONAL_KNOWLEDGE_ENABLED=0`, il registry espone workflow/provider stabili, il bridge HTTP gestisce dati studio con contesto permessi e lascia proseguire quando il contesto permessi non e' valutabile. |
| `python -m pytest lex/tests/test_http_bounded_bridge.py lex/tests/test_http_bounded_bridge_governed_only.py tests/test_lex_fascicolo_first_retrieval.py tests/test_lex_giurisprudenza_workflow.py -q --tb=short` | OK | 18/18 passati: il default-on operativo non intercetta i workflow governati generici senza contesto permessi e preserva i flag fascicolo-first/fonti esterne. |
| `python -m pytest tests/test_lex_operational_knowledge.py tests/test_lex_sentenze_clienti_fix.py tests/test_lex_sources_and_studio_data.py tests/test_lex_legal_source_engine.py lex/tests/unit/test_sentenze_clienti_fix.py lex/tests/test_http_bounded_bridge.py lex/tests/test_http_bounded_bridge_governed_only.py tests/test_lex_fascicolo_first_retrieval.py tests/test_lex_giurisprudenza_workflow.py tests/test_lex_professional_upgrade.py tests/test_lex_drafting_intent.py -q --tb=short` | OK | 173/173 passati: dati studio, clienti, agenda, preventivi, sentenze specifiche, fonti pubbliche, legal source engine, bounded bridge e drafting restano coerenti. |
| `python -m py_compile lex/http_bounded_bridge.py lex/formatting/answer_builder.py lex/formatting/professional_answer.py tests/test_lex_professional_upgrade.py tests/test_lex_fascicolo_first_retrieval.py` | OK | Sintassi confermata dopo fallback web automatico per ricerca legale con contesto interno parziale e contesto fonte nelle risposte strict. |
| `python -m pytest tests/test_lex_professional_upgrade.py::test_caso_18_risposta_grounded_con_fonti tests/test_lex_professional_upgrade.py::test_risposta_strict_con_fonte_senza_estratto_resta_da_verificare tests/test_lex_fascicolo_first_retrieval.py::test_payload_http_ricerca_legale_auto_web_anche_con_contesto_interno -q --tb=short` | OK | 3/3 passati: la risposta mostra l'estratto della fonte, degrada a `needs_review` se la fonte non ha contesto testuale e abilita ricerca web ufficiale per `ricerca_legale` anche con fonti interne insufficienti. |
| Probe manuali Python su `AnswerBuilder` e `build_bounded_http_payload` | OK | Risposta normativa verificata con sezione `Contesto fonte - Art. 2043 Codice Civile`; payload ricerca giurisprudenziale con archivio interno insufficiente verificato con `allow_external_research=True`, `require_official_sources=True` e motivo fonti esterne valorizzato. |
| `python -m py_compile lex/operational_knowledge/settings.py lex/operational_knowledge/integration.py lex/operational_knowledge/service.py lex/tools/operational_knowledge_tool.py tests/test_lex_operational_knowledge.py` | OK | Sintassi confermata dopo default-on, defer a ricerca pubblica e fallback tecnico su repository non disponibili. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging/versione sincronizzati su `2.237.9`. |
| `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` | OK | 8/8 passati: packaging e readiness release `2.237.9` confermati. |
| `git diff --check -- . ':!data/*'` | OK | Nessun errore whitespace sul perimetro tracciato, escludendo i file runtime `data/` gia' sporchi prima della tranche. |
| `python scripts/validate_docs_links.py`; `python scripts/validate_docs_commands.py` | OK | Link e comandi documentali validi dopo aggiornamento docs Lex e report. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Docker locale no-cache ha costruito wheel `pct-studio-legale==2.237.9`; app, scheduler, OCR e Redis healthy; readiness locale 200 con `versione=2.237.9`; runtime container `2.237.9`. |
| `ssh iusentra-hetzner "cd /opt/iusentra/repo && IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh"`; `GET https://app.iusentra.it/api/pronto`; `docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml ps`; `docker exec iusentra-app-1 python -c "import pct; print(pct.__version__)"` | OK | Deploy Hetzner senza backup sul commit finale `2.237.9`; cron backup non aggiornato, container app/scheduler/OCR/Redis/audit healthy, readiness pubblica 200 con `versione=2.237.9` e runtime container `2.237.9`. |

### Hotfix Lex risposta e accenti 2.237.8 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npx --yes sass@1.83.0 web/static/scss/app.scss web/static/css/app.css --style=compressed --no-source-map` | OK | Rigenerato CSS statico dopo le regole della bolla risposta Lex, senza cambiare il bundle React. |
| `node --check web/static/js/pct-lex-assistant.js`; `node --check web/static/js/lex-tts/supertonic-engine.js` | OK | Sintassi confermata per renderer risposta Lex e normalizzazione Supertonic NFC. |
| `node tests/js/lex_assistant_render.test.mjs`; `node tests/js/lex_tts_normalizer.test.mjs`; `node tests/js/lex_tts_profiles_quality.test.mjs`; `node tests/js/lex_tts_supertonic_engine.test.mjs`; `node tests/js/lex_tts_voice_contract.test.mjs` | OK | Coperti titoli, paragrafi, elenchi, tabelle, citazioni, link sicuri, codice inline, escaping HTML, pause/profili TTS e accenti italiani `à`, `è`, `é`, `ì`, `ò`, `ù`. |
| `python -m py_compile web/bootstrap/scadenziario_routes.py pct/__init__.py`; `python tools/sync_packaging_files.py --check` | OK | Sintassi e packaging/versione `2.237.8` sincronizzati. |
| `python -m pytest -q tests/test_web_bootstrap.py tests/test_lex_widget_contract.py tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 64/64 passati: bootstrap/widget Lex, nuove classi renderer, packaging e release readiness verdi. |
| `python scripts/validate_docs_links.py`; `python scripts/validate_docs_commands.py` | OK | Link e comandi documentali validi dopo l'aggiornamento delle note Lex. |
| Chrome headless su HTML temporaneo della bolla Lex con `web/static/css/app.css` | OK | DOM renderizzato con heading, elenco, tabella, citazione e accenti italiani; metriche `w=750`, `h=208`, `txt=true`. |
| `npm --prefix frontend run build` | OK | TypeScript e build Vite `2.237.8` completati in 6.38s; main `index-DaU5NV_e.js` 451.50 kB / 133.56 kB gzip. |
| `git diff --check -- <perimetro Lex risposta/TTS/docs/versione>` | OK | Nessun errore whitespace; solo warning CRLF informativo su `web/static/js/pct-lex-assistant.js`. |

### Rientro governance bootstrap 2.237.7 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web/bootstrap/scadenziario_routes.py pct/__init__.py` | OK | Sintassi confermata dopo la riduzione non funzionale delle righe vuote nello scadenziario e bump `2.237.7`. |
| `python -m pytest tests/test_web_bootstrap.py tests/test_react_shell.py::test_react_clienti_cartella_profonda_collegata_route_api_e_card_operative tests/test_react_shell.py::test_react_route_gate_copre_rotte_profonde_e_preserva_contratti_operativi tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` | OK | Gate bootstrap, cartella cliente React, packaging e release readiness verdi; `scadenziario_routes.py` rientra a 699 righe contro limite 700. |
| `node --test tests/js/lex_tts_normalizer.test.mjs tests/js/lex_tts_profiles_quality.test.mjs tests/js/lex_tts_supertonic_engine.test.mjs tests/js/lex_tts_voice_contract.test.mjs` | OK | 4/4 passati sul perimetro Lex TTS ereditato dal commit `2.237.6`. |
| `python tools/sync_packaging_files.py --check`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | Packaging sincronizzato, contratti React/App V2/Legal Skills verdi e build Vite `2.237.7` completata in 6.31s; main `index-DaU5NV_e.js` 451.50 kB / 133.56 kB gzip. |
| `python scripts/validate_docs_links.py`; `python scripts/validate_docs_commands.py` | OK | Link e comandi documentali ancora validi dopo aggiornamento changelog e report. |

### Hotfix Lex TTS prosodia 2.237.6 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `node --check web/static/js/lex-tts/quality-presets.js`; `node --check web/static/js/lex-tts/voice-profiles.js`; `node --check web/static/js/lex-tts/legal-speech-normalizer.js`; `node --check web/static/js/lex-tts/browser-speech-engine.js`; `node --check web/static/js/lex-tts/supertonic-engine.js`; `node --check web/static/js/lex-tts/tts-engine-registry.js`; `node --check web/static/js/pct-lex-assistant-voice.js`; `node --check web/static/js/pct-lex-assistant.js` | OK | Sintassi confermata dopo profili piu' lenti, normalizzazione numerica/punteggiatura, tag lingua Supertonic completo e caricamento TTS nella shell React. |
| `node tests/js/lex_tts_normalizer.test.mjs`; `node tests/js/lex_tts_profiles_quality.test.mjs`; `node tests/js/lex_tts_supertonic_engine.test.mjs`; `node tests/js/lex_tts_voice_contract.test.mjs` | OK | Coperti importi, percentuali, orari, pause per virgola/domanda/esclamazione, profilo `M1.json`, cambio voice style Supertonic e fallback browser. |
| `python -m pytest -q tests/test_web_bootstrap.py::test_lex_assistant_usa_componente_esterno_e_posizione_persistente tests/test_lex_widget_contract.py tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 18/18 passati: template Flask e React caricano la catena `lex-tts`, contratto widget Lex, packaging e readiness release `2.237.6` confermati. |
| `python tools/sync_packaging_files.py --check`; `git diff --check -- <perimetro Lex TTS>` | OK | Packaging sincronizzato; whitespace senza errori sui file TTS, template, test, documenti e file versione toccati. |

### Hotfix cartella cliente React full 2.237.5 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web/bootstrap/clienti_workspace_routes.py web/services/react_clienti_bridge.py` | OK | Sintassi confermata dopo redirect canonico `_legacy` e nuove azioni cartella/faldone nel bridge React. |
| `python -m pytest tests/test_react_shell.py::test_react_clienti_cartella_profonda_collegata_route_api_e_card_operative tests/test_react_shell.py::test_react_route_gate_copre_rotte_profonde_e_preserva_contratti_operativi tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` | OK | 10/10 passati: route profonda cliente, redirect da `_legacy=1`, contratto React, packaging e readiness release `2.237.5`. |
| `node frontend/scripts/check-react-contracts.mjs`; `node scripts/react-migration/check-route-gate.mjs`; `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Contratti React, route gate e anti-mascheramento/no-fake React confermano `/clienti/:id/cartella` come `react_operational_full` e bloccano CTA `?_legacy=1`. |
| `python scripts/react-migration/generate_app_v2_page_registry.py --check`; `python scripts/react-migration/generate_app_v2_area_requirements.py --check`; `python scripts/react-migration/generate_app_v2_test_docs.py --check` | OK | Documentazione generata App V2 allineata dopo l'aggiunta della route cartella cliente al manifest. |
| `python tools/sync_packaging_files.py --check`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | Packaging sincronizzato, TypeScript e gate frontend verdi; build Vite `2.237.5` in 7.24s con main `index-DaU5NV_e.js` 451.50 kB / 133.56 kB gzip e chunk `CartellaClientePage-DIANK4mp.js` 12.82 kB / 4.20 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Docker locale no-cache ha costruito wheel `pct-studio-legale==2.237.5`; dopo warm-up iniziale app/scheduler/OCR/Redis healthy, readiness locale circa 79 ms e runtime container `2.237.5`. |
| Chrome CDP headless autenticato su `/clienti/2B6E3D22/cartella?_legacy=1` desktop e mobile, report `artifacts/react-migration/visual-2.237.5-clienti-cartella/visual-load-audit.md` | OK | Redirect 302 alla URL canonica senza `_legacy`; shell React presente; desktop 1979 ms a contenuto visibile, DOMContentLoaded 1082 ms; mobile 1516 ms, DOMContentLoaded 604 ms; nessun overflow, form POST HTML, console error o testo tecnico vietato. |
| `git diff --check -- . ':!data/*'`; `python scripts/validate_docs_links.py`; `python scripts/validate_docs_commands.py` | OK | Whitespace senza errori, con soli warning CRLF preesistenti su documento generato e test; link e comandi documentali restano validi. |

### Lex TTS Supertonic fase 3 2.237.4 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `node --check web/static/js/lex-tts/quality-presets.js`; `node --check web/static/js/lex-tts/voice-profiles.js`; `node --check web/static/js/lex-tts/legal-speech-normalizer.js`; `node --check web/static/js/lex-tts/browser-speech-engine.js`; `node --check web/static/js/lex-tts/supertonic-engine.js`; `node --check web/static/js/lex-tts/tts-engine-registry.js`; `node --check web/static/js/pct-lex-assistant-voice.js`; `node --check web/static/js/pct-lex-assistant.js` | OK | Sintassi confermata per il layer voce Lex, engine Supertonic/ONNX locale, registry e facciata pubblica `window.PctLexVoice`. |
| `node tests/js/lex_tts_normalizer.test.mjs`; `node tests/js/lex_tts_profiles_quality.test.mjs`; `node tests/js/lex_tts_supertonic_engine.test.mjs`; `node tests/js/lex_tts_voice_contract.test.mjs` | OK | Normalizzazione legale, profili/preset, comportamento Supertonic opzionale senza asset/runtime e fallback browser confermati. |
| `python -m pytest -q tests/test_lex_widget_contract.py tests/test_packaging_consistency.py --tb=short` | OK | 16/16 passati: contratto widget Lex e allineamento packaging/versione `2.237.4` confermati. |
| `python tools/sync_packaging_files.py --check`; `git diff --check -- . ':!data/*'` | OK | Packaging sincronizzato; whitespace senza errori sul perimetro tracciato, con solo warning CRLF su `.gitignore`. |
| `ssh iusentra-hetzner "cd /opt/iusentra/repo && BRANCH=Codex/legal-electronic-filing-kIxcV IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh"`; `GET https://app.iusentra.it/api/pronto`; `docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml ps` | OK | Deploy Hetzner senza backup sul commit finale del branch; app, scheduler, OCR, Redis, audit-postgres, audit-worm, Ollama healthy/up; readiness pubblica 200 con `versione=2.237.4`. |
| Installazione asset Supertonic 3 su Hetzner; `GET https://app.iusentra.it/static/vendor/supertonic/manifest.json`; `HEAD` pubblici su modelli ONNX, voice style e ONNX Runtime Web; `docker exec iusentra-app-1 ... /app/web/static/vendor/supertonic` | OK | Asset reali Supertonic 3 installati come file locali non tracciati da Git: ONNX e voice styles da `Supertone/supertonic-3`, ONNX Runtime Web `1.26.0`, manifest `enabled=true`; asset presenti nell'immagine Docker e serviti same-origin con HTTP 200. |

### Lex Operational Knowledge 2.236.7 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests/test_lex_operational_knowledge.py -q` | OK | 17/17 passati: feature flag off/on, tenant isolation, RBAC, lookup clienti/fascicoli/scadenze/agenda/preventivi/conferimenti/documenti, messaggi PEC/email, template atti, audit, blocco azioni dispositive, no web per dati cliente e tool registry default-off. |
| `python -m py_compile lex/operational_knowledge/service.py lex/operational_knowledge/query_router.py tests/test_lex_operational_knowledge.py`; `python -m compileall -q lex/operational_knowledge lex/tools/operational_knowledge_tool.py tests/test_lex_operational_knowledge.py` | OK | Sintassi confermata dopo router operativo, supporto `cliente_id`, messaggi/notifiche/template e fallback deterministico per termini. |
| `python -m ruff check lex/operational_knowledge lex/http_bounded_bridge.py lex/tools/registry.py lex/tools/operational_knowledge_tool.py tests/test_lex_operational_knowledge.py` | OK | Ruff verde sul nuovo layer, tool registry e integrazione bounded bridge. |
| `python -m pytest tests/test_lex_legal_source_engine.py tests/test_lex_operational_knowledge.py -q` | OK | 30/30 passati: Legal Source Engine locale e Operational Knowledge restano compatibili, senza rete live nei test. |
| `python -m pytest lex/tests/test_http_bounded_bridge.py lex/tests/test_http_bounded_bridge_governed_only.py tests/test_lex_fascicolo_first_retrieval.py -q` | OK | 12/12 passati: il bounded bridge esistente continua a instradare workflow governati e fascicolo-first dopo l'innesto operativo. |
| `python tools/sync_packaging_files.py --check`; `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q`; `git diff --check` | OK | Packaging/versione `2.236.7` sincronizzati, readiness 8/8 passata; `git diff --check` senza errori, solo warning CRLF su file runtime preesistente e documento generato. |
| `python scripts/validate_docs_links.py`; `python scripts/validate_docs_commands.py`; `python scripts/validate_openapi.py docs/openapi.yaml`; `python scripts/verify_openapi_provider.py` | OK | Link e comandi documentali verdi, OpenAPI valida, provider verification OK con auth-error=182, success=27, backend-security=1 su data root temporaneo. |
| `python scripts/react-migration/generate_app_v2_page_registry.py --check`; `python scripts/react-migration/generate_app_v2_area_requirements.py --check`; `python scripts/react-migration/generate_app_v2_test_docs.py --check` | OK | I generatori hanno inizialmente segnalato drift documentale; rigenerati i documenti ufficiali e rilanciati i tre `--check`, tutti verdi. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React/App V2/UI coverage, TypeScript e build Vite `2.236.7` verdi; main asset `index-B5vl-4wv.js` 447.43 kB / 132.37 kB gzip. |
| `node frontend/scripts/check-react-contracts.mjs`; `node scripts/react-migration/check-route-gate.mjs`; `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Contratti React, route gate e anti-mascheramento/no-fake React confermati dopo build e rigenerazione report. |
| `ssh iusentra-hetzner "cd /opt/iusentra/repo && IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh"` | OK | Deploy Hetzner completato sul commit corrente del branch; log `Cron backup: non aggiornato`, app/scheduler/OCR/Redis/audit services healthy, runtime container `2.236.7`. |
| `GET https://app.iusentra.it/api/pronto`; `python scripts/smoke_app_v2_all.py --suite health --read-only --base-url https://app.iusentra.it --timeout 20` | OK | Readiness pubblica 200 `versione=2.236.7`; smoke produzione health PASS=2 FAIL=0 SKIP=0 BLOCKED=0. |

### Legal Source Engine Lex AI 2.236.6 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests\test_lex_legal_source_engine.py -q` | OK | 10/10 passati: registry fonti spento di default, rete vietata nei test, contratto `fetch` fail-closed, answer policy con citazioni/versione/prassi, retriever/tool dry-run, dogfood e report sicuri. |
| `python -m compileall -q lex\legal_sources tests\test_lex_legal_source_engine.py`; `python -m ruff check lex\legal_sources tests\test_lex_legal_source_engine.py` | OK | Sintassi e lint mirati verdi sul nuovo scheletro Legal Source Engine. Nessun backup, nessuna rete, nessun dato cliente e nessun corpus/indice generato. |

### Prova notifica automatica 2.236.2 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m ruff check pct/notifiche_legali.py tests/test_notifiche_legali.py` | OK | Ruff verde dopo calcolo automatico SHA-256 lato browser, validazione hash e date italiane in relata. |
| `python -m pytest tests/test_notifiche_legali.py -q` | OK | 26/26 passati: hash non SHA-256 e riferimenti DatiAtto mancanti bloccano; le date ISO vengono rese in formato italiano nella relata. |
| `npm --prefix frontend run typecheck` | OK | TypeScript verde dopo maschera deposito semplificata con selezione file multipla e riepilogo automatico atto/relata/PEC/RAC/RdAC. |
| `python -m pytest tests/test_notifiche_legali.py tests/test_telematic_registry_fail_closed.py tests/legal_deposit/test_penal_deposit_rules.py -q` | OK | 46/46 passati sul perimetro notifiche legali, registry procedimenti, deposito e fail-closed; nessuna regressione su PCT/SICID/SIECIC/SIGP/UNEP/PAT/PTT/PDP. |
| `python -m compileall -q legal_deposit pct web/blueprints/api_v1_react.py web/services/react_notifiche_legali_bridge.py`; `node scripts/react-migration/check-route-gate.mjs` | OK | Bytecode Python e route gate React coerenti dopo il fix del deposito prova. |
| `python tools/sync_packaging_files.py --check`; `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q`; `node frontend/scripts/check-react-contracts.mjs`; `npm --prefix frontend test`; `npm --prefix frontend run build` | OK | Packaging/readiness 8/8, contratti React, UI coverage e build Vite `2.236.2` verdi; chunk notifiche `NotificheLegaliPage-DKDTCQJS.js` 63.69 kB / 14.89 kB gzip e CSS `NotificheLegaliPage-JwzkYe5n.css` 15.58 kB / 2.91 kB gzip. |
| Browser Chromium headless su runtime isolato `http://127.0.0.1:8093/notifiche-legali` | OK | Login operatore, scheda `Deposito prova notifica`, upload multiplo di `ricorso.pdf`, `relata_notifica.pdf.p7m`, `pec_inviata.eml`, `accettazione.eml`, `consegna.eml`: riepilogo compilato con SHA-256 calcolati, `DatiAtto.xml` precompilato con destinatario/PEC/RAC/RdAC anche scegliendo prima i file e poi inserendo il destinatario, `Controlla prova deposito` superato, console error 0, mobile 390px senza overflow. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; smoke App V2 locale | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.236.2`; app, scheduler, OCR, Redis e Nginx avviati; readiness locale 200 con `versione=2.236.2`; smoke health PASS=2 FAIL=0 e notifications PASS=3 FAIL=0 SKIP=1. Nessun backup eseguito. |
| Deploy Hetzner `IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh`; `GET https://app.iusentra.it/api/pronto`; smoke App V2 produzione | OK | Deploy completato sul commit pushato, log `Cron backup: non aggiornato`; app, scheduler, OCR, Redis, audit-postgres, audit-worm e Caddy healthy; readiness pubblica 200 con `versione=2.236.2`; smoke produzione health PASS=2 FAIL=0 e notifications PASS=3 FAIL=0 SKIP=1. Nessun backup eseguito. |

### Prova notifica multi-documento 2.236.1 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m ruff check pct/notifiche_legali.py web/services/react_notifiche_legali_bridge.py tests/test_notifiche_legali.py` | OK | Ruff verde dopo `atti_notificati`, riferimento portale documento e test prova deposito multi-documento. |
| `python -m pytest tests/test_notifiche_legali.py -q` | OK | 25/25 passati: la prova deposito accetta piu' atti notificati con hash e mantiene RAC/RdAC originali obbligatorie. |
| `npm --prefix frontend run typecheck`; `node frontend/scripts/check-react-contracts.mjs`; `npm --prefix frontend test`; `npm --prefix frontend run build`; `node scripts/react-migration/check-route-gate.mjs` | OK | TypeScript, contratti, UI coverage, build Vite e route gate verdi dopo la selezione documenti della prova deposito; chunk `NotificheLegaliPage-DTWnOHO8.js` 58.16 kB / 13.16 kB gzip. |
| Browser Chrome headless su runtime isolato `http://127.0.0.1:8092/notifiche-legali` | OK | Login operatore, scheda `Deposito prova notifica`, pratica con `pst:JPW_SIGP:2182464` e `procura.pdf`: 2 checkbox, elenco automatico con entrambi i documenti e SHA-256, campo `Atto notificato` compilato come `pst:JPW_SIGP:2182464 - ricorso.pdf; procura.pdf`, zero errori console e nessun testo tecnico vietato. |
| `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q` | OK | 8/8 passati dopo bump versione `2.236.1`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto` | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.236.1`; app, scheduler, OCR, Redis e Nginx avviati; readiness locale 200 con `versione=2.236.1`. Nessun backup eseguito. |
| `python scripts/smoke_app_v2_all.py --suite health --read-only --base-url http://127.0.0.1:8080 --timeout 20`; `python scripts/smoke_app_v2_all.py --suite notifications --read-only --base-url http://127.0.0.1:8080 --timeout 20` | OK | Health locale PASS=2 FAIL=0; notifiche locale PASS=3 FAIL=0 SKIP=1, con invio reale saltato per modalita sola lettura. |
| Deploy Hetzner `IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh`; `GET https://app.iusentra.it/api/pronto`; smoke App V2 produzione | OK | Deploy completato sul commit corrente del branch; log `Cron backup: non aggiornato`; container app, scheduler, OCR, Redis, audit-postgres, audit-worm e Caddy healthy; readiness pubblica 200 con `versione=2.236.1`; smoke produzione health PASS=2 FAIL=0 e notifiche PASS=3 FAIL=0 SKIP=1. Nessun backup eseguito. |

### Modulo notifiche legali e registry telematico 2.236.0 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests/test_notifiche_legali.py tests/test_telematic_registry_fail_closed.py tests/legal_deposit/test_penal_deposit_rules.py -q` | OK | 44/44 passati: notifica PEC L. 53/1994 fail-closed, cliente non-notifica, multi-selezione documenti riportata nella relata, attestazioni, evidence pack, legacy `pct/notifica.py`, registry procedimenti, profili canale, PTT/SIGIT 10MB/50MB/50 file/100 caratteri e PDF/A governato. |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run build`; `node frontend/scripts/check-react-contracts.mjs` | OK | TypeScript, build Vite `2.236.0` e contratti React verdi dopo la UI multi-documento; chunk Notifiche Legali `NotificheLegaliPage-Q_BF-der.js` 56.32 kB / 12.75 kB gzip. |
| `python -m ruff check legal_deposit pct/notifica.py pct/notifiche_legali.py web/blueprints/api_v1_react.py web/services/react_notifiche_legali_bridge.py tests/test_notifiche_legali.py tests/test_telematic_registry_fail_closed.py tests/legal_deposit/test_penal_deposit_rules.py`; `python -m compileall -q legal_deposit pct web/blueprints/api_v1_react.py web/services/react_notifiche_legali_bridge.py`; `python tools/sync_packaging_files.py --check`; `git diff --check` | OK | Ruff, bytecode, packaging e whitespace verdi sul perimetro modificato; i file runtime `data/` restano fuori dallo stage. |
| `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q`; `npm --prefix frontend test`; `node scripts/react-migration/check-route-gate.mjs` | OK | Packaging/readiness 8/8, contratti React/App V2/UI coverage e route gate verdi. |
| `python scripts/validate_docs_links.py docs/LEGAL_NOTIFICATIONS_AND_TELEMATIC_REGISTRY.md docs/DEPOSIT_CHANNEL_PROFILES.md docs/LEGAL_DEPOSIT_ARCHITECTURE.md docs/index.md docs/REACT_MIGRATION_MASTER_PLAN.md` | OK | Link documentali locali verificati: 21 documenti, 150 link. |
| Browser in-app su runtime isolato `http://127.0.0.1:8091/notifiche-legali` | OK | Login admin di test su data root temporaneo, pratica con 2 documenti: selezione multipla presente, 2 checkbox, elenco allegati aggiornato con `atto-principale.pdf` e `allegato-fascicolo.pdf`; `Controlla prova deposito` e `Prepara comunicazione` visibili nei rispettivi percorsi; nessun testo tecnico vietato. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `docker compose ps`; `GET http://127.0.0.1:8080/api/pronto` | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.236.0`; app, scheduler, OCR e Redis healthy; readiness locale 200 `versione=2.236.0`. Nessun backup eseguito. |
| `python scripts/smoke_app_v2_all.py --suite health --read-only --base-url http://127.0.0.1:8080 --timeout 20`; `python scripts/smoke_app_v2_all.py --suite notifications --read-only --base-url http://127.0.0.1:8080 --timeout 20` | OK | Health locale PASS=2 FAIL=0; notifiche locale PASS=3 FAIL=0 SKIP=1, con invio reale saltato per modalita sola lettura. |

### Hotfix PST Step 4 e SIGP/Giudice di Pace 2.235.6 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests\test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests\test_local_signer.py::test_pst_ricerca_snapshot_sigp_include_ricerca_atti_nel_batch_visualizzazione tests\test_local_signer.py::test_pst_documenti_sigp_batcha_documenti_e_ricerca_atti_senza_chiamate_extra tests\test_local_signer.py::test_pst_ricerca_snapshot_batcha_ricerca_e_documenti_senza_preflight --tb=short` | OK | 4/4 passati: Step 4 presidia `Aggiorna pratica esistente` e il mapping iniziale legge `mode=update_existing`; SIGP/Giudice di Pace include `ricercaAtti` nel batch di visualizzazione/catalogo senza chiamate profilo fuori batch. |
| `python -m ruff check web\bootstrap\portali_acquisizione_routes.py tests\test_react_shell.py tools\local_signer.py tests\test_local_signer.py`; `python -m pytest -q tests\test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests\test_react_shell.py::test_portale_acquisizione_accetta_alias_fascicolo_id_per_mapping tests\test_react_shell.py::test_portale_acquisizione_legacy_step4_preseleziona_aggiorna_pratica tests\test_react_shell.py::test_react_telematico_scroll_usa_offset_topbar_non_scroll_into_view tests\test_react_shell.py::test_react_user_facing_links_non_espongono_app_v2_prefix --tb=short`; `python -m pytest -q tests\test_local_signer.py::test_pst_ricerca_snapshot_sigp_include_ricerca_atti_nel_batch_visualizzazione tests\test_local_signer.py::test_pst_documenti_sigp_batcha_documenti_e_ricerca_atti_senza_chiamate_extra tests\test_local_signer.py::test_pst_ricerca_snapshot_batcha_ricerca_e_documenti_senza_preflight --tb=short` | OK | Dopo la verifica browser e la scoperta del template classico, 5/5 React/shell e 3/3 Local Signer passati: anche `web/templates/portale/acquisizione_wizard.html` mostra nello Step 4 `Aggiorna pratica esistente` e `Fascicolo locale da aggiornare` con `mode=update_existing` preselezionato. |
| `python -m pytest -q tests\test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests\test_local_signer.py::test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import tests\test_local_signer.py::test_pst_ricerca_snapshot_batcha_ricerca_e_documenti_senza_preflight tests\test_local_signer.py::test_pst_ricerca_snapshot_sigp_include_ricerca_atti_nel_batch_visualizzazione tests\test_local_signer.py::test_pst_documenti_sigp_batcha_documenti_e_ricerca_atti_senza_chiamate_extra tests\test_local_signer.py::test_download_documenti_batch_sigp_include_dominio_invocazione tests\test_local_signer.py::test_pst_ricerca_esatta_arricchisce_profilo_se_mancano_campi_identita --tb=short` | OK | 7/7 passati sul perimetro Local Signer/PST/SIGP: visualizzazione batch, riuso sessione view e download batch Giudice di Pace preservati. |
| `python -m pytest -q tests\test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests\test_react_shell.py::test_portale_acquisizione_accetta_alias_fascicolo_id_per_mapping tests\test_react_shell.py::test_react_telematico_scroll_usa_offset_topbar_non_scroll_into_view tests\test_react_shell.py::test_react_user_facing_links_non_espongono_app_v2_prefix tests\test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita tests\test_polisweb.py::test_polisweb_classico_non_chiede_preflight_pin_prima_delle_operazioni_reali --tb=short` | OK | 6/6 passati: mapping pratica, link telematici, scroll e blocco preflight PIN restano governati. |
| `python -m ruff check tools\local_signer.py tests\test_local_signer.py tests\test_react_shell.py`; `npm --prefix frontend run typecheck`; `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs` | OK | Ruff Python, TypeScript, contratti React e route gate verdi su `2.235.6`. |
| `npm --prefix frontend run build`; `python tools\build_dist.py`; `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_build_dist.py tests\test_local_signer.py::test_local_signer_dist_allineato_a_sorgente_e_installer_versionati --tb=short` | OK | Build Vite `2.235.6` verde in 6.94s; Local Signer `1.6.35` rigenerato in `tools/dist` con installer Windows/macOS/Linux; packaging/readiness/dist 14/14 verdi. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `docker compose ps`; `GET http://127.0.0.1:8080/api/pronto`; runtime container | OK | Immagini locali ricostruite da zero dopo route/template, wheel `pct-studio-legale==2.235.6`; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.235.6` e runtime container `2.235.6`. |
| `python scripts\smoke_app_v2_all.py --subset contracts --read-only --base-url http://127.0.0.1:8080`; `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url http://127.0.0.1:8080` | OK | Contracts offline PASS=2 FAIL=0 SKIP=1; post-deploy locale PASS=76 FAIL=0 SKIP=1 BLOCKED=6 su `2.235.6`. Blocchi invariati: credenziali smoke dedicate e ID documento sintetico assenti. |
| Browser in-app `http://127.0.0.1:8080/portali/pst/acquisizione?_legacy=1&fascicolo_id=test-fascicolo&mode=update_existing` | OK | Step 4 classico verificato nel browser reale: visibili `Pratica da aggiornare`, radio `Aggiorna pratica esistente` selezionato e `Fascicolo locale da aggiornare`; console error 0. |
| Deploy Hetzner senza backup: `IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh`; `GET https://app.iusentra.it/api/pronto`; compose Hetzner; smoke pubblico read-only | OK | Deploy eseguito senza lanciare `backup.sh` e con log `Cron backup: non aggiornato`; server riallineato al branch pushato, app/scheduler/OCR/Redis/Audit healthy, runtime container `2.235.6`, readiness pubblica 200 `versione=2.235.6`, smoke produzione PASS=76 FAIL=0 SKIP=1 BLOCKED=6 WARNING=0. |

### Hotfix PST, Local Signer e Telematico 2.235.5 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_local_signer.py::test_pick_preferred_windows_cert_filtra_per_codice_fiscale_e_prefere_authentica tests/test_local_signer.py::test_pick_preferred_windows_cert_usa_certificato_unico_filtrato_per_cf tests/test_local_signer.py::test_soap_call_curl_batch_raw_windows_preserva_cert_store_spec tests/test_local_signer.py::test_soap_call_curl_raw_windows_applica_ssl_no_revoke tests/test_local_signer.py::test_pst_preflight_windows_applica_ssl_no_revoke tests/test_local_signer.py::test_errore_certificato_server_pst_non_chiede_di_aggiungere_ssl_no_revoke tests/test_local_signer.py::test_curl_command_windows_preferisce_curl_di_sistema tests/test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests/test_local_signer.py::test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import tests/test_local_signer.py::test_pst_ricerca_snapshot_batcha_ricerca_e_documenti_senza_preflight tests/test_local_signer.py::test_pst_ricerca_esatta_arricchisce_profilo_se_mancano_campi_identita --tb=short` | OK | 11/11 passati: selezione certificato auto con CF unico, curl Windows con `--ssl-no-revoke`, messaggio PST senza istruzioni manuali `--ssl-no-revoke`, ricerca/snapshot senza preflight e download batch sulla sessione `view`. |
| `python -m pytest -q tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests/test_react_shell.py::test_react_user_facing_links_non_espongono_app_v2_prefix tests/test_react_shell.py::test_react_telematico_scroll_usa_offset_topbar_non_scroll_into_view tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_react_shell.py::test_portale_acquisizione_accetta_alias_fascicolo_id_per_mapping tests/test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita --tb=short` | OK | 6/6 passati: link visibili telematici senza `/app-v2`, scroll con offset topbar, wizard PST senza preflight React e con sessione propagata. |
| `python -m pytest -q tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_react_shell.py::test_react_telematico_scroll_usa_offset_topbar_non_scroll_into_view --tb=short` | OK | 2/2 passati dopo il fix TypeScript: la UI non contiene piu' `ensurePstPortalSession` ne' `localSignerJson('/pst/preflight-auth')`, e le superfici telematiche non usano `scrollIntoView`. |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | TypeScript verde; build Vite `iusentra-react-token-ui@2.235.5` verde in 6.12s con asset principali `index-Bd532Fmq.js` 445.23 kB / 131.74 kB gzip, `TelematicoPage-DsmJk5eO.js` 23.65 kB / 7.26 kB gzip e `TelematicoSurfacePage-CuO12ww3.js` 65.31 kB / 19.33 kB gzip. |
| `python -m ruff check tools/local_signer.py tests/test_local_signer.py tests/test_react_shell.py web/services/react_telematico_bridge.py web/services/react_fascicoli_bridge.py web/services/react_messaggi_bridge.py web/services/react_scadenziario_bridge.py web/services/react_studio_module_bridge.py` | OK | Ruff mirato verde sul perimetro PST/telematico. |
| `python tools\build_dist.py`; `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py tests/test_build_dist.py tests/test_local_signer.py::test_local_signer_dist_allineato_a_sorgente_e_installer_versionati --tb=short` | OK | Local Signer `1.6.34` rigenerato (`SetupLocalSigner.exe`, pacchetti Windows/macOS/Linux, note e sorgente dist) e packaging/readiness/dist 14/14 verdi. |
| `rg -n -F "localSignerJson('/pst/preflight-auth'" frontend\src web\static\react tests\test_react_shell.py`; `rg -n -F "Local Signer non pronto sul PC" frontend\src web\static\react tests\test_react_shell.py`; `rg -n -F "/app-v2/polisweb" frontend\src web\services web\static\react tests\test_react_shell.py` | OK | Nessun match applicativo nei sorgenti o asset build; restano solo le asserzioni negative dei test dove previste. |

### Hotfix Email ordinaria e Panoramica 2.235.4 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\email_client.py` | OK | Sintassi confermata dopo il retry IMAP su timeout e la scoperta cartelle piu' conservativa. |
| `python -m pytest -q tests\test_email_client.py::test_cartelle_imap_effettive_non_scopre_archivi_equivalenti tests\test_email_client.py::test_sincronizza_imap_recupera_timeout_socket_durante_fetch tests\test_email_client.py::test_email_ordinaria_deduplica_triplicati_da_cartelle_imap_equivalenti tests\test_email_client.py::test_sincronizza_imap_non_fonde_uid_stabili_con_stesso_message_id --tb=short` | OK | 4/4 passati: niente sync su archivi equivalenti, retry su `cannot read from timed out object`, deduplica ordinaria preservata e UID PEC/Legalmail stabili non fusi. |
| `python -m pytest -q tests\test_email_client.py --tb=short` | OK | 50/50 passati: sync PEC/ordinaria, allegati, cartelle, timeout, deduplica e invii restano verdi. |
| `python -m pytest -q tests\test_dashboard_mailbox_sync.py --tb=short` | OK | 5/5 passati: runtime manuale/automatico conserva lock, cooldown e separazione PEC/ordinaria. |
| `python -m ruff check pct\email_client.py tests\test_email_client.py` | OK | Lint mirato verde per il perimetro email. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React/App V2/UI coverage, TypeScript e build Vite `iusentra-react-token-ui@2.235.4` verdi; build 6.70s, main JS `index-BoNCz9Gi.js` 445.23 kB / 131.75 kB gzip e CSS `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness/packaging 8/8 su versione sorgente `2.235.4`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; runtime container | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.235.4`; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.235.4` e runtime container `2.235.4`. |
| `python scripts\smoke_app_v2_all.py --subset contracts --read-only --base-url http://127.0.0.1:8080`; `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url http://127.0.0.1:8080` | OK | Contracts offline PASS=2 FAIL=0 SKIP=1; post-deploy locale PASS=76 FAIL=0 SKIP=1 BLOCKED=6 su `2.235.4`. I blocchi restano credenziali smoke dedicate e ID documento sintetico assenti, non failure codice. |
| Deploy Hetzner senza backup: `IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh`; `GET https://app.iusentra.it/api/pronto`; compose Hetzner; smoke pubblico read-only | OK | Deploy eseguito senza lanciare `backup.sh` e con log `Cron backup: non aggiornato`; server su release `2.235.4`, app/scheduler/OCR/Redis/Audit healthy, `/api/pronto` pubblico `ok=true`, runtime container `2.235.4`, smoke produzione PASS=76 FAIL=0 SKIP=1 BLOCKED=6. Verificato anche che `/opt/iusentra/repo/email/ordinaria.json` sia assente e che i log app/scheduler non contengano `cannot read from timed out object`. |

### Hotfix Local Signer CI 2.235.3 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests\test_local_signer.py::test_portale_wsdl_diretto_abilitato_default_attivo tests\test_local_signer.py::test_local_signer_dist_allineato_a_sorgente_e_installer_versionati --tb=short` | OK | 2/2 passati: WSDL diretto PDP/PAT/PTT attivo di default e `tools/dist/local_signer.py` allineato alla sorgente. |
| `python scripts\run_pytest_phases.py --suite signer --suite-shard 4 --suite-total-shards 4 --suite-subdivide-items --timeout-minutes 5` | OK | Shard CI esatto che era rosso su GitHub: 39/39 passati dopo Local Signer `1.6.31`. |
| `python scripts\run_pytest_phases.py --suite signer --suite-shard 1..4 --suite-total-shards 4 --suite-subdivide-items --timeout-minutes 5` | OK | Tutti gli shard Local Signer locali passati: shard 1 40/40, shard 2 40/40, shard 3 39/39, shard 4 39/39. |
| `python -m ruff check tools\local_signer.py tests\test_local_signer.py`; `python -m compileall -q tools\local_signer.py pct\__init__.py` | OK | Sintassi e lint mirati verdi per il fix Local Signer e il bump versione applicativa. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness/packaging 8/8 su versione sorgente `2.235.3`. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React, App V2 frontend, UI coverage, TypeScript e build Vite `iusentra-react-token-ui@2.235.3` verdi; build 7.14s, main JS `index-BANtr1vZ.js` 444.72 kB / 131.64 kB gzip e CSS `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `docker compose ps`; `GET http://127.0.0.1:8080/api/pronto`; runtime container | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.235.3`; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.235.3` e runtime container `2.235.3`. |
| `python scripts\smoke_app_v2_all.py --subset contracts --read-only --base-url http://127.0.0.1:8080`; `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url http://127.0.0.1:8080` | OK | Contracts offline PASS=2 FAIL=0 SKIP=1; post-deploy locale PASS=76 FAIL=0 SKIP=1 BLOCKED=6 su `2.235.3`. I blocchi restano credenziali smoke dedicate e ID documento sintetico assenti. |

### Hotfix CI/portali/email 2.235.2 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python scripts\smoke_app_v2_all.py --subset contracts` | OK | PASS=2 FAIL=0 SKIP=1: OpenAPI e provider verification offline verdi; il controllo HTTP live viene dichiarato SKIP e resta nelle suite `api`/`post-deploy`. |
| `python -m pytest -q tests\scripts\test_smoke_app_v2_all.py tests\test_email_client.py::test_email_ordinaria_deduplica_triplicati_da_cartelle_imap_equivalenti tests\test_email_client.py::test_sincronizza_imap_non_fonde_uid_stabili_con_stesso_message_id --tb=short` | OK | 6/6 passati: alias `contracts` offline, repair triplicati ordinari e guardia anti-fusione PEC/Legalmail con UID stabili. |
| `python -m pytest -q tests\test_react_shell.py::test_route_ufficiali_superfici_telematiche_restano_legacy_ma_acquisizioni_assistite_react tests\test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti --tb=short` | OK | 2/2 passati: PDP/PAT/PTT/SIGIT assistiti esatti servono shell React; superfici telematiche non parificate restano legacy-first. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs`; `python -m pytest -q tests\test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests\test_react_shell.py::test_react_wizard_acquisizione_portale_usa_endpoint_operativi_reali tests\test_react_shell.py::test_route_importa_pratica_pst_resta_raggiungibile_dalla_nav --tb=short` | OK | Contratti React e route gate coerenti; API telematiche reali e acquisizione PST legacy ancora raggiungibili. |
| `python -m pytest -q tests\test_email_client.py --tb=short` | OK | 48/48 passati: il client PEC/ordinaria mantiene sync, allegati, stati, deduplica inviati e nuova riparazione triplicati ordinari. |
| `python -m pytest -q tests\test_app_v2_page_registry.py tests\test_app_v2_area_requirements_phase8.py tests\test_app_v2_test_plan_phase10.py --tb=short` | OK | 12/12 passati dopo rigenerazione registry, requisiti area, matrice e piano test con le nuove route assistite. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `python scripts\react-migration\generate_app_v2_area_requirements.py --check`; `python scripts\react-migration\generate_app_v2_test_docs.py --check` | OK | Documenti App V2 generati e deterministici su manifest 2.235.2. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short`; `python -c "import pct; print(pct.__version__)"` | OK | Packaging sincronizzato, readiness/packaging 8/8 e versione source `2.235.2`. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React, App V2 frontend, UI coverage, TypeScript e build Vite `iusentra-react-token-ui@2.235.2` verdi; build 6.54s, main JS `index-BANtr1vZ.js` 444.72 kB / 131.64 kB gzip e CSS `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `python -m compileall -q pct\email_client.py web\bootstrap\react_route_gate.py web\blueprints\react_shell.py scripts\smoke_app_v2_all.py`; `python -m ruff check pct\email_client.py scripts\smoke_app_v2_all.py web\bootstrap\react_route_gate.py web\blueprints\react_shell.py tests\test_email_client.py tests\test_react_shell.py tests\scripts\test_smoke_app_v2_all.py`; `git diff --check` | OK | Sintassi confermata, Ruff mirato verde e diff senza whitespace error; solo warning CRLF su file gia' tracciati. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `docker compose ps`; `GET http://127.0.0.1:8080/api/pronto`; runtime container | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.235.2`; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.235.2` e runtime container `2.235.2`. |
| `python scripts\smoke_app_v2_all.py --subset contracts --read-only --base-url http://127.0.0.1:8080`; `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url http://127.0.0.1:8080` | OK | Contracts offline PASS=2 FAIL=0 SKIP=1; post-deploy locale PASS=76 FAIL=0 SKIP=1 BLOCKED=6. I blocchi restano solo credenziali smoke dedicate e ID documento sintetico assenti. |
| Browser in-app autenticato su `/app-v2/messaggi/nuovo`, `/portali/pdp/acquisizione`, `/portali/pat/acquisizione`, `/portali/ptt/acquisizione`, `/portali/sigit/acquisizione` | OK | `/app-v2/messaggi/nuovo` mostra la pagina React `Nuovo messaggio` e non `Funzione non attiva per questo studio`; le quattro acquisizioni assistite servono la shell React senza vecchi testi `Portale ufficiale assistito` o `Local Connector non raggiungibile`, con zero errori console. |
| `python scripts\react-migration\generate_backend_security_map.py --check`; `python -m pytest -q tests\test_backend_security_phase5.py::test_mappa_sicurezza_backend_generata_e_allineata --tb=short`; `python -m pytest -q tests\test_auth.py tests\test_backend_security_phase5.py tests\test_tenant_isolation_runtime.py tests\test_app_v2_feature_flags.py tests\test_app_v2_routing.py tests\test_openapi_contracts_phase6.py --tb=short` | OK | Mappa sicurezza backend riallineata alle 102 route manifest, incluso il nuovo perimetro portali assistiti; gate RBAC/tenant/App V2/OpenAPI 75/75 verde dopo il rosso CI sul commit iniziale. |
| Deploy Hetzner `deploy/hetzner` su `7f2ff992`; `GET https://app.iusentra.it/api/pronto`; `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url https://app.iusentra.it`; compose Hetzner con `/opt/iusentra/.env.hetzner` | OK | Produzione aggiornata a `versione=2.235.2`; app, scheduler, OCR, Redis, audit-postgres, audit-worm e Ollama healthy; smoke pubblico PASS=76 FAIL=0 SKIP=1 BLOCKED=6. |

### Hotfix App V2 rollout 2.235.1 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_feature_flags.py tests/test_app_v2_feature_flags.py tests/test_app_v2_routing.py tests/test_react_shell.py::test_react_shell_app_v2_route_operativa_e_spegnibile_da_feature_flag --tb=short` | OK | 22/22 passati: le superfici App V2 operative sono attive di default, il rollback esplicito per flag resta 403 e telematico/Web Push restano protetti. |
| `python -m pytest -q tests/test_feature_flags.py tests/test_app_v2_feature_flags.py tests/test_app_v2_routing.py tests/test_react_shell.py::test_react_shell_app_v2_route_operativa_e_spegnibile_da_feature_flag tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 30/30 passati dopo il fix alias esplicito: flag, routing App V2, shell React, packaging e readiness release confermati su `2.235.1`. |
| `python -m pytest -q tests/test_feature_flags.py tests/test_app_v2_feature_flags.py tests/test_app_v2_routing.py tests/test_react_shell.py::test_react_shell_app_v2_route_operativa_e_spegnibile_da_feature_flag tests/test_app_v2_page_registry.py tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 35/35 passati come gate finale locale dopo rigenerazione registro e cleanup runtime. |
| `python -m compileall -q web\services\feature_flags.py scripts\smoke_app_v2_all.py scripts\smoke_app_v2_routing.py scripts\smoke_app_v2_pages.py` | OK | Sintassi confermata per resolver flag e smoke aggiornati. |
| `python tools\sync_packaging_files.py --check`; `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `python scripts\react-migration\generate_app_v2_test_docs.py --check`; `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | Packaging, registro App V2 e documentazione deterministici; link/comandi docs validati dopo l'aggiornamento del rollout e del default flag nel registro. |
| `python -m compileall -q scripts\react-migration\generate_app_v2_page_registry.py`; `python -m pytest -q tests/test_app_v2_page_registry.py --tb=short` | OK | Generatore registro App V2 confermato dopo l'allineamento della colonna `Default flag`; 5/5 passati. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Test frontend, TypeScript e build Vite `iusentra-react-token-ui@2.235.1` verdi; build 5.83s, asset principali invariati `index-CSdjNGxs.js` 444.72 kB / 131.62 kB gzip e `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| Flask test client autenticato su `/app-v2/messaggi/nuovo`, `/app-v2/messaggi`, `/app-v2/documenti`, `/app-v2/telematico` | OK | Le prime tre route rispondono 200 con shell React; `/app-v2/telematico` resta 403 perche' nel perimetro non parificato. La cartella runtime temporanea `tmp_smoke_app_v2_message` e' stata rimossa. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; runtime/label immagine | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.235.1`; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.235.1`, runtime e label immagine `2.235.1`. |
| `python scripts\smoke_app_v2_all.py --subset contracts --read-only --base-url http://127.0.0.1:8080`; `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url http://127.0.0.1:8080` | OK | Contracts PASS=7 FAIL=0; post-deploy PASS=76 FAIL=0 SKIP=1 BLOCKED=6. I blocchi sono solo credenziali smoke dedicate e ID documento test assenti. |
| Browser reale su `http://127.0.0.1:8080/app-v2/messaggi/nuovo` desktop e mobile | OK | La route anonima non mostra piu' `Funzione non attiva per questo studio`, ma il redirect corretto a `/login?next=/app-v2/messaggi/nuovo`; pagina non vuota, nessun overlay framework, nessun errore/warning console, form login interagibile. |

### Fase react 13 - smoke operativi e post-deploy readiness 2.234.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\smoke_lib.py scripts\smoke_app_v2_all.py` | OK | Sintassi confermata per libreria smoke comune e orchestrator fase 13. |
| `python scripts\smoke_app_v2_all.py --help`; `python scripts\smoke_app_v2_all.py --subset inventory` | OK | CLI fase 13 disponibile; alias storico fase 10 preservato e inventario pagine/routing/workflow eseguito senza credenziali. |
| `python -m pytest -q tests\scripts\test_smoke_lib.py tests\scripts\test_smoke_app_v2_all.py --tb=short` | OK | 7/7 passati: redaction segreti, URL safe, JSON report, policy failure, alias `--subset`, inventory JSON e missing env. |
| `python scripts\react-migration\generate_app_v2_test_docs.py --check`; `python -m pytest -q tests\scripts\test_smoke_lib.py tests\scripts\test_smoke_app_v2_all.py tests\test_app_v2_test_plan_phase10.py tests\test_ci_cd_gates_phase11.py --tb=short` | OK | Documenti test App V2 deterministici dopo l'inserimento della fase 13; 15/15 passati su smoke, test-plan e CI/CD. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | Link documentali 148 verificati; 154 comandi/path documentati controllati dopo l'aggiunta di `docs/smoke-tests.md` e release readiness. |
| `python scripts\smoke_app_v2_all.py --suite health --read-only --base-url https://app.iusentra.it --json-output ...` | OK | Readiness pubblica 200 `versione=2.233.0` prima del bump, shell base 302 controllato e report JSON prodotto senza segreti. |
| `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --staging --base-url https://app.iusentra.it --json-output %TEMP%\iusentra-smoke-phase13-postdeploy.json` | OK | Post-deploy produzione read-only: PASS=76, FAIL=0, SKIP=1, BLOCKED=6, WARNING=0. Bloccati solo controlli autenticati/ID test per env mancanti; non dichiarati verdi. |
| `python tools\sync_packaging_files.py --check`; `python -c "import pct; print(pct.__version__)"` | OK | Packaging sincronizzato e versione sorgente `2.234.0` confermata dopo bump fase 13. |
| `python scripts\validate_openapi.py docs\openapi.yaml`; `python scripts\verify_openapi_provider.py`; `python scripts\smoke_app_v2_all.py --suite flags --read-only --base-url https://app.iusentra.it` | OK | OpenAPI valido; provider verification: 182 auth-error, 27 success e 1 backend-security; smoke feature flag produzione 4 PASS, 0 FAIL. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React, gate App V2, UI coverage, TypeScript e build Vite 2.234.0 verdi; build completata in 5.86s con asset principali invariati `index-CSdjNGxs.js` 444.72 kB / 131.62 kB gzip e `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_openapi_contracts_phase6.py --tb=short` | OK | 13/13 passati su packaging, readiness release e contratti OpenAPI dopo il consolidamento smoke fase 13. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; smoke post-deploy locale | OK | Build locale no-cache 2.234.0 completata; app, scheduler, OCR e Redis healthy, nginx running; `/api/pronto` locale 200 `versione=2.234.0`, runtime container e label immagine `2.234.0`; smoke post-deploy locale read-only: PASS=76, FAIL=0, SKIP=1, BLOCKED=6, WARNING=0. |
| Hetzner CPX42 `IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh`; `GET https://app.iusentra.it/api/pronto`; smoke post-deploy produzione | OK | Deploy fase 13 completato senza aggiornare cron backup: server sul commit `85d7617549c0695ffd3f41447d0b2c86524766aa`, container app/scheduler/OCR/Redis/audit-postgres/audit-worm/Ollama healthy e Caddy up; runtime `2.234.0`, readiness pubblica 200 `versione=2.234.0`; smoke post-deploy produzione read-only PASS=76, FAIL=0, SKIP=1, BLOCKED=6, WARNING=0 e `smoke_backend_security.py` verde sugli anonimi. |

### Fase react 12 - documentazione, handover e release playbook 2.233.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\validate_docs_links.py scripts\validate_docs_commands.py scripts\react-migration\generate_api_contracts.py` | OK | Sintassi confermata per i nuovi validator documentali e il generatore API aggiornato. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | 21 documenti e 145 link locali verificati; 131 comandi/path documentati controllati contro script, workflow e npm scripts reali. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `python scripts\react-migration\generate_app_v2_area_requirements.py --check`; `python scripts\react-migration\generate_app_v2_test_docs.py --check` | OK | Registry, requisiti area e documenti test App V2 allineati. |
| `python scripts\react-migration\generate_api_contracts.py`; `python scripts\react-migration\generate_api_contracts.py --check`; `python scripts\validate_openapi.py docs\openapi.yaml`; `python scripts\verify_openapi_provider.py` | OK | OpenAPI/mappa contratti rigenerate con data fase 12 e allineate; OpenAPI valido; provider verification: 182 auth-error, 27 success e 1 backend-security. |
| `python scripts\smoke_app_v2_all.py --subset inventory`; `python scripts\smoke_app_v2_all.py --subset contracts` | OK | Inventario App V2 e contratti/smoke OpenAPI eseguiti senza credenziali, con profili autenticati non dichiarati verdi. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React, App V2 frontend, UI coverage, TypeScript e build Vite 2.233.0 verdi; build 6.73s, main JS `index-CSdjNGxs.js` 444.72 kB / 131.62 kB gzip e CSS `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip invariati. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short`; `python -m pytest -q tests\test_openapi_contracts_phase6.py --tb=short`; `python -m pytest -q tests\test_ci_cd_gates_phase11.py tests\test_app_v2_test_plan_phase10.py --tb=short` | OK | Packaging/readiness 8/8, contratti OpenAPI 5/5 e regressioni CI/test-plan 8/8 passati dopo bump `2.233.0`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; smoke locali security/routing/workflows | OK | Build locale no-cache 2.233.0 completata; app, scheduler, OCR e Redis healthy, nginx running; `/api/pronto` 200 `versione=2.233.0`, runtime container e label immagine `2.233.0`; smoke security/routing/workflows verdi, con profili autenticati saltati per assenza env dedicate. |
| Hetzner CPX42 `IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh`; `GET https://app.iusentra.it/api/pronto`; smoke produzione security/routing/workflows | OK | Deploy fase 12 completato senza aggiornare cron backup: repository server sul commit `a33794605f8fb2e7356981f4907d2e755d8da09a`, runtime container `2.233.0`, app/scheduler/OCR/Redis/audit-postgres/audit-worm/Ollama healthy e Caddy up; readiness pubblica 200 `versione=2.233.0`; smoke sicurezza anonimo, routing e workflow inventory produzione verdi dopo riaggancio proxy post-recreate. |

### Fase react 11 - CI/CD App V2 2.232.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\react-migration\generate_app_v2_test_docs.py tests\test_ci_cd_gates_phase11.py` | OK | Sintassi confermata per generatore test plan aggiornato e regressioni CI/CD fase 11. |
| `python -c "import pathlib, yaml; [yaml.safe_load(...)]"` | OK | Tutti i workflow `.github/workflows/*.yml` parseabili dopo l'aggiunta di `smoke-staging.yml`. |
| `python scripts\react-migration\generate_app_v2_test_docs.py --check`; `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `python scripts\react-migration\generate_app_v2_area_requirements.py --check` | OK | Piano test CI/CD, registry App V2 e requisiti area deterministici. |
| `python scripts\smoke_app_v2_all.py --subset inventory`; `python scripts\smoke_app_v2_all.py --subset contracts` | OK | Inventory senza credenziali e OpenAPI/provider verification verdi; provider: 182 auth-error, 27 success e 1 backend-security. |
| `python -m pytest -q tests\test_ci_cd_gates_phase11.py --tb=short` | OK | 5/5 passati: documentazione CI/CD, workflow main, smoke staging manuale e audit supply-chain verificati. |
| `python -m pytest -q tests\test_openapi_contracts_phase6.py tests\test_ci_cd_gates_phase11.py --tb=short` | OK | 10/10 passati su contratti API e gate CI/CD fase 11. |
| `python -m pytest -q tests\test_app_v2_page_registry.py tests\test_app_v2_test_plan_phase10.py tests\test_ci_cd_gates_phase11.py --tb=short` | OK | 13/13 passati su registry, piano test e CI/CD. |
| `python -m pytest -q tests\test_auth.py tests\test_backend_security_phase5.py tests\test_tenant_isolation_runtime.py tests\test_app_v2_feature_flags.py tests\test_app_v2_routing.py tests\test_openapi_contracts_phase6.py --tb=short` | OK | 75/75 passati sul gate RBAC, tenant isolation, feature flag, routing e contratti. |
| `python -m pip install pip-audit`; `python -m pip_audit -r requirements.txt --format json --output %TEMP%\pip-audit-phase11.json`; `npm --prefix frontend audit --audit-level=critical --omit=dev --json` | OK | Audit dipendenze locali: Python senza vulnerabilita note; npm production critical a zero vulnerabilita. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React, gate App V2, UI coverage, TypeScript e build Vite 2.232.0 verdi; build completata in 6.36s con asset principali invariati. |
| `python scripts\run_pytest_phases.py --suite release-readiness --timeout-minutes 10`; `python scripts\run_pytest_phases.py --suite quality-overlay --timeout-minutes 10`; `python scripts\run_pytest_phases.py --suite e2e-smoke --timeout-minutes 10`; `python scripts\run_pytest_phases.py --suite coverage-critical --timeout-minutes 10` | OK | Suite CI governate verdi: release readiness 1/1, quality overlay 5/5, e2e-smoke 1/1, coverage-critical 313 item. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_ci_cd_gates_phase11.py --tb=short`; `python -c "import pct; print(pct.__version__)"` | OK | Packaging sincronizzato, readiness/packaging/fase 11 13/13 e versione source `2.232.0`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; runtime/label Docker; smoke App V2 local | OK | Build locale no-cache 2.232.0 completata; app, scheduler, OCR, Redis, audit-postgres e audit-worm healthy; readiness locale `versione=2.232.0`, runtime container `2.232.0`, label immagine `2.232.0`; smoke security/pages/routing/workflows completati, con profili autenticati dichiarati mancanti per assenza env. |
| Hetzner CPX42 `IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh`; `GET https://app.iusentra.it/api/pronto`; smoke produzione security/routing/workflows | OK | Deploy fase 11 completato senza aggiornare cron backup: repository server sul commit `023f18ba7b5be9bebdcf57c508e900e7a2f003c7`, runtime container `2.232.0`, app/scheduler/OCR/Redis/audit-postgres/audit-worm/Ollama healthy e Caddy up; readiness pubblica 200 `versione=2.232.0`; smoke sicurezza anonimo, routing e workflow inventory produzione verdi, con smoke autenticati saltati per assenza env dedicate. |

### Fase react 10 - test completi App V2 2.231.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\react-migration\generate_app_v2_test_docs.py scripts\smoke_app_v2_all.py tests\test_app_v2_test_plan_phase10.py` | OK | Sintassi confermata per generatore piano/inventario/matrice, smoke orchestrator e test dedicato fase 10. |
| `python scripts\react-migration\generate_app_v2_test_docs.py --check`; `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `python scripts\react-migration\generate_app_v2_area_requirements.py --check` | OK | Documenti fase 10, registry App V2 e requisiti area deterministici. |
| `python scripts\smoke_app_v2_all.py --subset inventory`; `python scripts\smoke_app_v2_all.py --subset contracts` | OK | Inventory senza credenziali completato; OpenAPI valido e provider verification verde con 182 auth-error, 27 success e 1 backend-security. |
| `python -m pytest -q tests\test_app_v2_test_plan_phase10.py --tb=short` | OK | 3/3 passati: doc deterministici, P0/P1 full marcati `tested`, smoke inventory senza segreti. |
| `python -m pytest -q tests\test_ui_coverage_phase9.py tests\test_app_v2_area_requirements_phase8.py tests\test_app_v2_frontend_phase7.py tests\test_app_v2_page_registry.py --tb=short` | OK | 15/15 passati: guard fasi 7/8/9 e registry preservati dopo collegamento fase 10. |
| `npm --prefix frontend run test`; `npm --prefix frontend run test:app-v2`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Contratti React, gate App V2, UI coverage, TypeScript e build Vite 2.231.0 verdi; build completata in 5.98s con asset principali invariati. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py tests\test_app_v2_test_plan_phase10.py --tb=short` | OK | Packaging sincronizzato, readiness/packaging e test fase 10 verdi dopo bump 2.231.0. |
| `python -m pytest -q tests\test_auth.py tests\test_backend_security_phase5.py tests\test_tenant_isolation_runtime.py tests\test_app_v2_feature_flags.py tests\test_app_v2_routing.py tests\test_openapi_contracts_phase6.py --tb=short` | OK | 75/75 passati sul perimetro auth, security, tenant isolation, feature flag, routing e contratti OpenAPI. |
| `python scripts\run_pytest_phases.py --suite release-readiness`; `python scripts\run_pytest_phases.py --suite quality-overlay`; `python scripts\run_pytest_phases.py --suite coverage-critical --timeout-minutes 10`; `python scripts\run_pytest_phases.py --suite e2e-smoke --timeout-minutes 10` | OK | Suite CI governate verdi: release readiness 1/1, quality overlay 5/5, coverage-critical 313 item, e2e-smoke 1/1. |
| `python -m pytest -q tests\test_auth.py tests\test_storage_strategy.py tests\test_telematico_repository.py --cov=pct.auth --cov=pct.storage --cov=pct.telematico_repository --cov-report=term-missing --tb=short` | OK | Baseline coverage mirata 78% totale; ResourceWarning sqlite gia' osservati come warning, non failure. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; runtime/label Docker; smoke App V2 local | OK | Build locale no-cache 2.231.0 completata; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.231.0`, runtime container `2.231.0`, label immagine `2.231.0`; smoke security/pages/routing/workflows completati, con profili autenticati dichiarati mancanti per assenza env. |

### Fase react 9 - UI regression App V2 2.230.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\validate_ui_coverage.py scripts\react-migration\generate_app_v2_page_registry.py scripts\react-migration\generate_app_v2_area_requirements.py tests\test_ui_coverage_phase9.py` | OK | Sintassi confermata per validatore copertura UI, generatori fase 9 e test dedicato. |
| `python scripts\validate_ui_coverage.py`; generatori App V2 `--check` | OK | Copertura UI fase 9 deterministica: P0/P1=63, P0/P1 full `ui_tested`=34; Storybook non introdotto, VRT non attivo e gap dichiarati. |
| `npm --prefix frontend run test`; `npm --prefix frontend run test:app-v2`; `npm --prefix frontend run typecheck` | OK | Contratti React, gate App V2, validatore UI coverage e TypeScript verdi su `2.230.0`. |
| `python -m pytest -q tests\test_ui_coverage_phase9.py tests\test_app_v2_area_requirements_phase8.py tests\test_app_v2_frontend_phase7.py tests\test_app_v2_page_registry.py --tb=short` | OK | 15/15 passati: fixture sicure, rigenerazione registry/requisiti e guard fase 7/8 preservati. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short`; `python scripts\validate_openapi.py docs\openapi.yaml` | OK | Packaging sincronizzato, readiness release 8/8 e OpenAPI valido dopo bump `2.230.0`. |
| `npm --prefix frontend run build` | OK | Build Vite 2.230.0 completata in 6.51s; bundle principale invariato `index-CSdjNGxs.js` 444.72 kB / 131.62 kB gzip, CSS principale `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; versione runtime/label Docker | OK | Build locale no-cache e riavvio completati; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.230.0`, runtime container e label immagine `2.230.0`. |
| `python scripts\smoke_backend_security.py --base-url http://127.0.0.1:8080`; `python scripts\smoke_app_v2_workflows.py --base-url http://127.0.0.1:8080` | OK | API sensibili anonime 401 controllato; smoke workflow autenticato non eseguito per assenza credenziali ambiente e dichiarato come inventario. |
| Browser in-app su `http://127.0.0.1:8080/app-v2/impostazioni` e `/impostazioni` | OK | App V2 flag-off controllato; pagina Impostazioni React visibile con testi operativi, zero errori console e nessun testo tecnico vietato nel DOM snapshot. |

### Fase react 8 - requisiti area/workflow App V2 2.229.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\react-migration\generate_app_v2_area_requirements.py scripts\smoke_app_v2_workflows.py tests\test_app_v2_area_requirements_phase8.py` | OK | Sintassi confermata per generatore requisiti area, smoke workflow e test fase 8. |
| `python scripts\react-migration\generate_app_v2_area_requirements.py --check`; `python scripts\react-migration\generate_app_v2_page_registry.py --check` | OK | Registro requisiti area e registry App V2 deterministici, con sezione fase 8 nel registro e nel riepilogo frontend. |
| `python scripts\smoke_app_v2_workflows.py --list`; `python scripts\smoke_app_v2_workflows.py --base-url http://127.0.0.1:8080` | OK | Inventario P0/P1 reale elencato; smoke autenticato non eseguito senza env e dichiarato come tale, senza segreti stampati. |
| `python -m pytest -q tests\test_app_v2_area_requirements_phase8.py tests\test_app_v2_frontend_phase7.py tests\test_app_v2_page_registry.py --tb=short` | OK | 12/12 passati: doc fase 8, stati area, smoke workflow, guard fase 7 e registry preservati. |
| `npm --prefix frontend run test:app-v2`; `npm --prefix frontend run test`; `npm --prefix frontend run typecheck` | OK | Gate App V2, contratti React e TypeScript verdi su `2.229.0`; P0/P1=63 e P0/P1 full=34 invariati. |
| `npm --prefix frontend run build` | OK | Build Vite 2.229.0 completata in 6.13s; bundle principale invariato `index-CSdjNGxs.js` 444.72 kB / 131.62 kB gzip, CSS principale `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `python scripts\validate_openapi.py docs\openapi.yaml`; `python scripts\verify_openapi_provider.py`; `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | OpenAPI valido, provider verification 182 auth-error / 27 success / 1 backend-security, packaging sincronizzato e readiness 8/8 per `2.229.0`. |
| `python -m pytest -q tests\test_app_v2_feature_flags.py tests\test_app_v2_routing.py tests\test_react_shell.py::test_react_api_bridge_richiede_autenticazione --tb=short`; `node scripts\react-migration\check-route-gate.mjs`; `git diff --check` | OK | 15/15 passati; route gate OK; `git diff --check` senza errori, solo warning CRLF su file toccati/runtime locali. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Build locale no-cache e riavvio completati; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.229.0`, runtime container e label immagine `2.229.0`. |
| Browser in-app su `http://127.0.0.1:8080/app-v2/impostazioni` | OK | Login locale di verifica, stato flag-off `Funzione non attiva per questo studio.`, zero errori console e nessun testo tecnico vietato nel DOM snapshot. |

### Fase react 7 - frontend App V2 governato 2.228.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\react-migration\generate_app_v2_page_registry.py tests\test_app_v2_frontend_phase7.py web\blueprints\react_shell.py` | OK | Sintassi confermata per generatore registro, test fase 7 e bootstrap React con permessi effettivi. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check` | OK | Registro App V2 e riepilogo frontend deterministici con sezione `Stato frontend fase 7`. |
| `npm --prefix frontend run test:app-v2`; `npm --prefix frontend run test`; `npm --prefix frontend run typecheck` | OK | Gate App V2, contratti React e TypeScript verdi; il gate fase 7 verifica 63 route P0/P1 e 34 route P0/P1 full. |
| `python -m pytest -q tests\test_app_v2_frontend_phase7.py tests\test_app_v2_page_registry.py tests\test_app_v2_feature_flags.py tests\test_app_v2_routing.py tests\test_react_shell.py::test_react_api_bridge_richiede_autenticazione --tb=short` | OK | 23/23 passati: 404 sicura App V2, RBAC bootstrap, registry, feature flag, routing e auth API preservati. |
| `python scripts\validate_openapi.py docs\openapi.yaml`; `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | OpenAPI valido, packaging sincronizzato e readiness release 8/8 per `2.228.0`. |
| `npm --prefix frontend run build` | OK | Build Vite 2.228.0 completata in 6.50s; bundle principale `index-CSdjNGxs.js` 444.72 kB / 131.62 kB gzip, CSS principale invariato `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Build locale no-cache e riavvio completati; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.228.0`, runtime container e label immagine `2.228.0`. |
| `python scripts\smoke_backend_security.py --base-url http://127.0.0.1:8080` | OK | Readiness 200, API sensibili anonime 401 controllato, prova tenant forzato saltata per assenza di API key smoke. |
| Browser in-app + Playwright Chrome su `/app-v2/area-non-censita` desktop/tablet/mobile | OK | Login locale di verifica, 404 sicura visibile, nessun caricamento dashboard, nessuna richiesta `/api/v1/ui/dashboard`, zero errori console, zero overflow. DOMContentLoaded desktop/tablet/mobile 532.7/453.6/532.1 ms. |

### Fase react 4 - routing legacy e fallback App V2 2.225.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\app_v2_routing.py scripts\react-migration\generate_app_v2_page_registry.py scripts\smoke_app_v2_routing.py tests\test_app_v2_routing.py tests\test_app_v2_page_registry.py` | OK | Sintassi confermata per helper routing fail-closed, generatore registro, smoke routing e test dedicati. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check` | OK | Registro e mappa routing App V2 deterministici: 98 route manifest, 13 route App V2 frontend, 31 alias frontend, 69 mapping backend sicuri, 0 redirect live. |
| `python scripts\smoke_app_v2_routing.py --list`; `python scripts\smoke_app_v2_routing.py --base-url http://127.0.0.1:8080` | OK | Smoke senza credenziali: `/api/pronto` 200, endpoint flag 401 controllato, legacy/App V2 anonimi verso login same-origin, nessun redirect esterno. |
| `python -m pytest -q tests\test_app_v2_routing.py tests\test_app_v2_page_registry.py --tb=short` | OK | 15/15 passati: sanificazione query, blocco open redirect, mapping statici/dinamici, fallback case-sensitive, flag off/on e documenti generati. |
| `python -m pytest -q tests\test_app_v2_routing.py tests\test_app_v2_page_registry.py tests\test_feature_flags.py tests\test_app_v2_feature_flags.py tests\test_react_shell.py::test_react_shell_app_v2_route_protette_da_feature_flags --tb=short` | OK | 27/27 passati sul perimetro routing, feature flag, shell App V2 e registro. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs` | OK | Contratti React e route gate confermano strip query/hash lato router, helper Python, query whitelist/blacklist e 0 redirect live. |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | TypeScript, contratti frontend e build Vite 2.225.0 verdi; build 5.49s, bundle principale `index-C-BWXjrL.js` 440.64 kB / 130.82 kB gzip, CSS principale invariato 121.77 kB / 22.33 kB gzip. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging, versione e readiness release confermati dopo bump `2.225.0`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Build locale no-cache e riavvio completati; app, scheduler, OCR, Redis e nginx healthy/running; readiness locale `versione=2.225.0` e runtime container `2.225.0`. |
| Chrome Playwright anonimo su `/app-v2?next=https://evil.example`, `/app-v2/documenti`, `/fascicoli?q=smoke` desktop/mobile | OK | Tutti i percorsi restano same-origin e arrivano al login: desktop 339/27/32 ms, mobile 266/28/26 ms; zero errori console e nessun redirect esterno. |

### Fase react 1 - feature flag App V2 2.222.0

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\feature_flags.py web\services\core_runtime.py web\blueprints\api_v1_react.py web\blueprints\react_shell.py web\blueprints\push_notifications.py tests\test_feature_flags.py tests\test_push_notifications.py` | OK | Sintassi confermata per resolver flag, bootstrap, endpoint JSON, shell e guard Web Push. |
| `python -m pytest -q tests/test_feature_flags.py --tb=short` | OK | 4/4 passati: default-off, toggle auditabile, endpoint `/api/v1/ui/feature-flags`, route `/app-v2/documenti` off/on e blocco Web Push flag-off. |
| `python -m pytest -q tests/test_push_notifications.py --tb=short` | OK | 14/14 passati con `notifications.mobilePush` esplicitamente abilitato nei test esistenti, preservando il comportamento Web Push quando il flag e' attivo. |
| `npm --prefix frontend run typecheck` | OK | TypeScript senza errori dopo helper `featureFlags.ts`, filtro route App V2 e guard client Web Push. |
| `npm --prefix frontend run test` | OK | Contratti React verificati. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 confermata per `2.222.0`. |
| `python -m pytest -q tests/test_web_bootstrap.py::test_docker_compose_hetzner_allinea_email_ordinaria_e_ai_locale --tb=short` | OK | Contratto compose Hetzner/email ordinaria/AI locale confermato dopo aggiornamento env feature flag. |
| `npm --prefix frontend run build` | OK | Build Vite completata in 6.52s; bundle principale `index-ofyf7WIs.js` 431.37 kB / 128.58 kB gzip, CSS principale 121.77 kB / 22.33 kB gzip. |
| `node scripts\react-migration\check-route-gate.mjs`; shard mirati `tests/test_react_shell.py` | OK | Gate route coerente e 3/3 test shell mirati passati dopo bootstrap feature flag. |
| `git diff --check` | OK | Nessun errore whitespace; soli warning CRLF su file gia' toccati/runtime locali. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini locali 2.222.0 ricostruite; app, scheduler, OCR e Redis healthy. `docker compose ps` richiede variabili audit WORM locali temporanee solo per interpolare i servizi non avviati. |
| `Invoke-WebRequest http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Readiness locale HTTP 200 con `versione=2.222.0`; runtime container `2.222.0`. |
| Browser Playwright Chrome autenticato desktop/tablet/mobile su `/app-v2/documenti` e `/notifiche` | OK | `/app-v2/documenti` torna 403 controllato `Funzione non attiva per questo studio.` con flag off; `/notifiche` torna 200 in 1873/2124/1921 ms, zero overflow, zero errori console e zero termini tecnici vietati. |

### Fase react 2 - registro App V2 2.223.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\react-migration\generate_app_v2_page_registry.py scripts\smoke_app_v2_pages.py tests\test_app_v2_page_registry.py` | OK | Sintassi confermata per generatore registro, smoke App V2 e test dedicati. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check` | OK | Registro deterministico aggiornato: `docs/app-v2-page-registry.md` e `docs/frontend-app-v2-pages.md`. |
| `python scripts\smoke_app_v2_pages.py --list` | OK | Inventario smoke senza credenziali: 98 route manifest, 69 full, 3 partial, 26 legacy e target smoke App V2 elencati. |
| `python -m pytest -q tests/test_app_v2_page_registry.py --tb=short` | OK | 4/4 passati: documenti generati, route manifest presenti, priorita su backlog e smoke script eseguibile. |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run test` | OK | TypeScript e contratti React confermati dopo bump `2.223.0` e registro fase 2. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 confermata per `2.223.0`. |
| `npm --prefix frontend run build` | OK | Build Vite completata in 5.35s; asset principali invariati rispetto al baseline 2.222.0. |
| `git diff --check` | OK | Nessun errore whitespace sui file di fase 2; resta solo warning CRLF su dato runtime non committato. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini locali 2.223.0 ricostruite no-cache; app, scheduler, OCR, Redis e servizi audit healthy/running. |
| `docker compose ps`; `Invoke-WebRequest http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Readiness locale HTTP 200 con `versione=2.223.0`; runtime container `2.223.0`. |
| `python scripts\smoke_app_v2_pages.py --base-url http://127.0.0.1:8080` | OK | Senza credenziali lo smoke non chiama endpoint protetti e cade correttamente su inventario `--list` implicito. |

### PST Local Signer sessione view/download 2.221.0

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\bootstrap\portali_acquisizione_routes.py` | OK | Sintassi confermata dopo alias `fascicolo_id` / `target_fascicolo_id` per il wizard di acquisizione portale. |
| `python -m pytest -q tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_react_shell.py::test_portale_acquisizione_accetta_alias_fascicolo_id_per_mapping tests/test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests/test_local_signer.py::test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import tests/test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita --tb=short` | OK | 5/5 passati: React recupera la sessione PST da selezione/anteprima, il download resta batch su `purpose=view`, il vecchio wizard continua a usare snapshot e non reintroduce sessioni import separate. |
| `npm --prefix frontend run typecheck` | OK | TypeScript senza errori dopo helper di recupero sessione PST e mapping fascicolo dal query string. |
| `npm --prefix frontend run test` | OK | Contratti React confermati dopo la correzione del wizard PST. |
| `npm --prefix frontend run build` | OK | Build Vite completata in 5.97s; rigenerato chunk `TelematicoSurfacePage` con riuso sessione Local Signer. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 confermata dopo il fix PST. |
| `Invoke-WebRequest http://127.0.0.1:8080/portali/pst/acquisizione?fascicolo_id=DC5BF1DB`; `Invoke-WebRequest http://127.0.0.1:8080/api/pronto` | OK | Wizard locale raggiungibile HTTP 200 con alias `fascicolo_id`; readiness locale HTTP 200 con `versione=2.221.0`. |
| `python tools\build_dist.py` | OK | Generati `SetupLocalSigner-1.6.30.exe`, alias `SetupLocalSigner.exe`, `InstallaLocalSigner-1.6.30.command`, `InstallaLocalSigner-1.6.30.run`, PS1 interno e note release con richiamo al riuso sessione PST view/download. |
| `python -m py_compile tools\local_signer.py tools\dist\local_signer.py tools\build_dist.py` | OK | Sintassi confermata per sorgente Local Signer, copia distribuita e builder. |
| `python -m pytest -q tests/test_local_signer.py::test_local_signer_dist_allineato_a_sorgente_e_installer_versionati tests/test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests/test_local_signer.py::test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import --tb=short` | OK | 3/3 passati: dist Local Signer `1.6.30` allineata alla sorgente, installer versionati presenti e guardrail sessione PST confermati. |

### Audit probatorio WORM 2.221.0

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests/test_audit_canonical.py tests/test_audit_hashing.py tests/test_audit_signing.py tests/test_audit_worm.py tests/test_audit_emit.py tests/test_audit_chain.py tests/test_audit_merkle.py tests/test_audit_snapshot.py tests/test_audit_proof.py tests/test_audit_bundle.py tests/test_audit_routes.py tests/test_audit_integrations.py -q` | OK | 30/30 passati: JCS, hash file, JWS, adapter CAdES esterno, WORM/Object Lock guard, assenza API delete, emit/idempotenza, failure post-WORM, catena, Merkle, snapshot multi-tenant, proof, bundle offline, route e hook dominio fail-closed sul tenant. |
| `python -m compileall -q audit scripts alembic tests\test_audit_canonical.py tests\test_audit_hashing.py tests\test_audit_signing.py tests\test_audit_worm.py tests\test_audit_emit.py tests\test_audit_chain.py tests\test_audit_merkle.py tests\test_audit_snapshot.py tests\test_audit_proof.py tests\test_audit_bundle.py tests\test_audit_routes.py tests\test_audit_integrations.py` | OK | Sintassi confermata per moduli audit, script forensi, Alembic e test mirati. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump `2.221.0` e nuove dipendenze Alembic/boto3. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: packaging e readiness release confermate per `2.221.0`. |
| `alembic -c alembic.ini upgrade head --sql` con `AUDIT_DATABASE_URL=postgresql://audit:audit@localhost:5432/iusentra` | OK | SQL offline generato: tabelle indice eventi/snapshot/failure/reconciliation e versione `20260513_legal_audit_worm`. |
| `npm run typecheck` in `frontend/` | OK | TypeScript senza errori dopo tab Audit nel dettaglio Fascicoli. |
| `npm run test` in `frontend/` | OK | Contratti React verificati dopo tab Audit e payload Fascicoli aggiornato. |
| `npm run build` in `frontend/` | OK | Build Vite completata; asset React rigenerati in `web/static/react`. |
| `git diff --check` | OK | Nessun errore whitespace; restano solo warning CRLF su file gia' toccati/runtime locali. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini locali ricostruite con package e label `2.221.0`; app, scheduler, OCR e Redis healthy. |
| `Invoke-WebRequest http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Readiness locale `versione=2.221.0`; runtime container `2.221.0`. |

### Audit gate React reale 2.220.0

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web/bootstrap/react_route_gate.py web/blueprints/api_v1_react.py web/blueprints/react_shell.py` | OK | Sintassi confermata dopo allowlist chirurgica per `/scadenziario` e `/sito-studio`. |
| `python -m pytest tests/test_react_shell.py -q --tb=short` | OK | 81/81 passati: shell React, fallback `_legacy=1`, route profonde, manifest/gate e API principali coerenti. |
| `npm --prefix frontend run typecheck` | OK | TypeScript senza errori dopo promozione builder/scadenziario e conversione form Template Atti. |
| `npm --prefix frontend run build` | OK | Build Vite completata per `iusentra-react-token-ui@2.220.0`; asset React rigenerati in `web/static/react`. |
| `npm --prefix frontend run test` | OK | Contratti React verificati con script frontend. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Gate/manifest coerenti: le route sbloccate non restano bloccate da `_excluded()` o legacy-first. |
| `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Audit anti-mascheramento aggiornato a 98 route; nessun full con form HTML o mock. |
| `node scripts/react-migration/check-no-mock-data-full-react.mjs` | OK | Nessun dato mock/demo rilevato sulle superfici full React. |
| Browser Playwright Python con Chrome locale, login reale, desktop `/sito-studio/builder`, `/scadenziario/<id>`, `/scadenziario/<id>/modifica` e mobile `/sito-studio/redazione-ai` | OK | Shell operativa presente, testi attesi visibili, nessun errore console, nessun overflow orizzontale e nessun termine tecnico vietato nel testo visibile. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump `2.220.0`. |
| `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q` | OK | 8/8 passati: packaging e readiness release confermate per `2.220.0`. |

### Email ordinaria accenti e charset 2.218.9

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests\test_email_client.py::test_parse_message_recupera_accenti_con_charset_errato tests\test_email_client.py::test_sincronizza_imap_ripara_testo_salvato_con_accenti_rotti tests\test_email_client.py::test_sincronizza_inviati_rimuove_doppione_con_orario_server_diverso tests\test_email_client.py::test_sincronizza_inviati_non_fonde_due_invii_locali_simili_senza_message_id --tb=short` | OK | 4/4 passati: accenti recuperati da charset errato, record storici con `�` riparati alla sync e guardie deduplica Email ordinaria preservate. |
| `python -m py_compile pct\email_client.py web\services\mailbox_sync_runtime.py web\blueprints\email_ordinaria.py web\services\react_email_bridge.py` | OK | Sintassi confermata per parser email, runtime sync e bridge React. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.218.9. |
| `npm --prefix frontend run typecheck` | OK | TypeScript senza errori dopo bump versione frontend. |
| `node frontend\scripts\check-react-contracts.mjs` | OK | Contratti React confermati; nessun cambio UI richiesto per il fix backend. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: packaging e readiness release confermati per 2.218.9. |
| `npm --prefix frontend run build` | OK | Build Vite 2.218.9 completata in 6.09s; bundle principale invariato `index-Ci4uxUYh.js` 431.15 kB / 128.50 kB gzip; chunk email invariato `EmailPecPage-CAqfMtKE.js` 38.08 kB / 10.69 kB gzip. |
| Docker locale `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini finali 2.218.9 ricostruite; app, scheduler, OCR e Redis healthy, Nginx attivo, `/api/pronto` 200 con versione `2.218.9`; runtime container `pct.__version__=2.218.9`. |
| `git diff --check` | OK | Nessun errore whitespace; solo warning CRLF sul file Python toccato. |

### Email ordinaria deduplica inviati 2.218.8

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests\test_email_client.py::test_sincronizza_inviati_rimuove_doppione_quando_esiste_gia_copia_imap_inviata tests\test_email_client.py::test_sincronizza_inviati_rimuove_doppione_con_orario_server_diverso tests\test_email_client.py::test_sincronizza_inviati_non_fonde_due_invii_locali_simili_senza_message_id tests\test_email_client.py::test_sincronizza_imap_non_fonde_uid_stabili_con_stesso_message_id tests\test_messaggi.py::test_invia_email_imposta_message_id_per_deduplica_inviati --tb=short` | OK | 5/5 passati: deduplica locale/IMAP con stesso `Message-ID`, deduplica con scarto orario provider, nessuna fusione di invii locali simili, guardia Legalmail su UID stabili e generazione `Message-ID` SMTP. |
| `python -m py_compile pct\email_client.py pct\messaggi.py web\services\mailbox_sync_runtime.py web\blueprints\email_ordinaria.py web\services\react_email_bridge.py` | OK | Sintassi confermata per client email ordinaria/PEC, invio SMTP e runtime sync. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.218.8. |
| `node frontend\scripts\check-react-contracts.mjs` | OK | Contratti React confermati; nessun cambio UI richiesto per il fix backend. |
| `npm --prefix frontend run typecheck` | OK | TypeScript senza errori dopo bump versione frontend. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: packaging e readiness release confermati per 2.218.8. |
| `npm --prefix frontend run build` | OK | Build Vite 2.218.8 completata in 6.28s; bundle principale invariato `index-Ci4uxUYh.js` 431.15 kB / 128.50 kB gzip; chunk email invariato `EmailPecPage-CAqfMtKE.js` 38.08 kB / 10.69 kB gzip. |
| Docker locale `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini finali 2.218.8 ricostruite; app, scheduler, OCR e Redis healthy, Nginx attivo, `/api/pronto` 200 con versione `2.218.8`; runtime container `pct.__version__=2.218.8`. |

### Allegati PEC e cartelle Legalmail 2.218.7

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests\test_email_client.py::test_email_dettaglio_visualizza_e_scarica_allegato_salvato tests\test_email_client.py::test_email_dettaglio_non_propone_link_per_allegato_non_recuperato tests\test_email_client.py::test_email_ordinaria_dettaglio_usa_repository_smtp_e_allegati_ordinari tests\test_email_client.py::test_parse_message_salva_allegato_message_rfc822 tests\test_email_client.py::test_sincronizza_imap_ripara_allegati_storici_senza_file tests\test_email_client.py::test_sincronizza_imap_scopre_cartelle_legalmail_e_corregge_spedite tests\test_email_client.py::test_imap_mailbox_list_parser_legge_cartelle_legalmail_non_quotate --tb=short` | OK | 7/7 passati: allegati salvati, allegati metadata-only senza link React, ordinaria separata, parsing `message/rfc822`, riparazione storica PEC e parser cartelle Legalmail non quotate. |
| `python -m py_compile pct\email_client.py web\services\react_email_bridge.py web\blueprints\email_client.py web\blueprints\email_ordinaria.py` | OK | Sintassi confermata per parser, bridge React e route allegati PEC/ordinaria. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo `statusLabel` e azioni allegato condizionali. |
| `node frontend\scripts\check-react-contracts.mjs` | OK | Contratti React confermati per superfici email. |
| `npm --prefix frontend run build` | OK | Build Vite 2.218.7 completata in 5.63s; chunk `EmailPecPage-CAqfMtKE.js` 38.08 kB / 10.69 kB gzip, bundle principale `index-Ci4uxUYh.js` 431.15 kB / 128.50 kB gzip. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.218.7. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate per 2.218.7. |
| `git diff --check` | OK | Nessun errore whitespace; restano solo warning CRLF su file gia' toccati. |
| Docker locale `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini finali 2.218.7 ricostruite; app, scheduler, OCR e Redis healthy, Nginx attivo, `/api/pronto` 200 con versione `2.218.7`; runtime container `pct.__version__=2.218.7`. |
| Browser in-app su `/email/messaggio/ade7f2ddbb0643848eb78a380fb70764` e `/email/messaggio/ade7f2ddbb0643848eb78a380fb70764/allegato/0` | OK | Desktop: dettaglio React con `postacert.eml` e `daticert.xml`, nessuna 404, azioni allegato visibili per file recuperati; URL allegato 0 apre `postacert.eml` in 1911 ms. Tablet 820x1180: 3197 ms, nessun errore console. Mobile 390x844: 3365 ms, nessun errore console. |

### Template Atti Cartabia / prefill / timbro studio 2.218.0

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python scripts\template_atti\apply_cartabia_schema.py` | OK | Catalogo master e split arricchiti con schema Cartabia 1.2.0; report generato in `artifacts/template-atti/cartabia-catalog-coverage.*`. |
| `python scripts\template_atti\validate_cartabia_catalog.py` | OK | Validati 420 template master, split coerenti 122/186/92/20 e totale 420 senza ID duplicati o perdita di link compilatore. |
| `python -m py_compile pct\studio_timbro.py pct\template_atti_prefill.py pct\template_cartabia_rules.py pct\template_atti.py pct\compilatore_atti.py pct\template_atti_master_catalog.py pct\template_catalog_service.py web\blueprints\template_atti.py web\blueprints\api_v1_react.py web\services\react_template_atti_bridge.py` | OK | Sintassi confermata per timbro tenant-aware, prefill resolver, regole Cartabia, catalogo, compilatore, API e bridge React. |
| `python -m pytest tests\test_template_atti_master_catalog.py tests\test_template_atti_cartabia_prefill_timbro.py -q` | OK | 13/13 passati: schema master, split, link compilatore, timbro dinamico, assenza dati Montagnese hardcoded, ordine timbro prima titolo, prefill, filtro testi vietati da dati storici e endpoint timbro/API. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per dati Template Atti, filtri Cartabia/prefill e preview timbro. |
| `npm --prefix frontend run test` | OK | Contratti React confermati dopo spostamento degli stili timbro su CSS governato. |
| `npm --prefix frontend run build:vite` | OK | Build Vite completata in 7.39s; chunk lazy `TemplateAttiPage-DBGLHnhR.js` 16.58 kB / 4.92 kB gzip e CSS `TemplateAttiPage-C0WmBbpQ.css` 8.96 kB / 1.71 kB gzip. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.218.0. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate per 2.218.0. |
| Docker locale `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini finali 2.218.0 ricostruite dopo micro-patch UI; app, scheduler, OCR e Redis healthy, Nginx attivo, `/api/pronto` 200 con versione `2.218.0`. |
| Browser Chrome headless su `/template-atti/catalogo` e `/template-atti/compila/CIV_CIT_001` | OK | Catalogo desktop/tablet/mobile: Cartabia, timbro e prefill visibili, DOMContentLoaded caldo 291/254/287 ms; compilatore desktop 791 ms; nessun errore console, nessun overflow orizzontale e nessun testo tecnico vietato. Primo accesso post-rebuild ha mostrato warm-up tenant gia' registrato. |

### Template Atti STRICT inventario/fonti 2.218.1

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\template_atti_inventory.py pct\template_atti_unified_catalog.py pct\template_atti_prefill.py pct\template_cartabia_rules.py pct\studio_timbro.py web\blueprints\template_atti.py web\blueprints\api_v1_react.py` | OK | Sintassi confermata per inventario, catalogo unificato, prefill STRICT, fonti Cartabia, timbro top-left e nuove API. |
| `python scripts\template_atti\build_template_inventory.py` | OK | Report aggiornato: 1320 template canonici rilevati su 1320 attesi, scostamento 0; 4576 record di fonte ispezionati, 3256 copie eccedenti tracciate e 710 gruppi con copie multiple riconciliati senza promuovere record duplicati. |
| `python -m pytest tests/test_template_atti_master_catalog.py tests/test_template_atti_inventory.py tests/test_template_atti_cartabia_strict.py tests/test_template_atti_prefill_strict.py tests/test_template_atti_timbro.py tests/test_template_atti_unified_catalog.py tests/test_template_atti_sources.py tests/test_template_atti_api_strict.py tests/test_template_atti_cartabia_prefill_timbro.py -q` | OK | 30/30 passati: catalogo master, inventario, copie fonte riconciliate, strict mode, fonti ufficiali, prefill priorita/conflitti, timbro, API e regressioni 2.218.0. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo label UI `Compila con dati IUSENTRA`, metriche inventario e stato Cartabia non assolutistico. |
| `npm --prefix frontend run build` | OK | Build Vite 2.218.1 completata in 6.72s; chunk lazy `TemplateAttiPage-CPfS4W17.js` 16.96 kB / 5.07 kB gzip. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.218.1. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate per 2.218.1. |

### Template Atti STRICT autore/editor professionale 2.218.1

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\template_atti_prefill.py pct\compilatore_atti.py web\blueprints\template_atti.py web\blueprints\api_v1_react.py web\services\react_template_atti_bridge.py` | OK | Sintassi confermata dopo priorita' `Autore` da Dati Studio/Avvocato titolare e import automatico nell'editor professionale. |
| `python -m pytest tests/test_template_atti_prefill_strict.py tests/test_template_atti_api_strict.py tests/test_assistente_redazionale.py -q` | OK | 9/9 passati: `autore` e `author_user_id` risolti da Dati Studio, API prefill allineata e compilazione con pratica importata come documento del fascicolo nell'editor. |
| `python -m pytest tests/test_template_atti_inventory.py tests/test_template_atti_cartabia_strict.py tests/test_template_atti_unified_catalog.py tests/test_template_atti_sources.py -q` | OK | 11/11 passati: inventario, Cartabia STRICT, catalogo unificato e fonti ufficiali confermati dopo l'ultimo cambio. |
| `python -m pytest tests/test_template_atti_prefill_strict.py tests/test_template_atti_api_strict.py tests/test_template_atti_cartabia_prefill_timbro.py -q` | OK | 10/10 passati: prefill, API strict e regressioni Cartabia/prefill/timbro. |
| `python -m pytest tests/test_template_atti_master_catalog.py tests/test_template_atti_timbro.py tests/test_template_atti_workspace.py tests/test_assistente_redazionale.py tests/test_react_document_editor.py -q` | OK | 24/24 passati: catalogo master, timbro, workspace template, assistente redazionale e route/payload editor React. |
| `python -m pytest tests/test_template_atti_master_catalog.py tests/test_template_atti_inventory.py tests/test_template_atti_cartabia_strict.py tests/test_template_atti_prefill_strict.py tests/test_template_atti_timbro.py tests/test_template_atti_unified_catalog.py tests/test_template_atti_sources.py tests/test_template_atti_api_strict.py tests/test_template_atti_cartabia_prefill_timbro.py tests/test_template_atti_workspace.py tests/test_assistente_redazionale.py tests/test_react_document_editor.py -q` | Timeout isolato | Batch unico troppo largo per il budget locale; gli stessi file sono passati nei tre shard sopra. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo il cambio di flusso dal catalogo al compilatore. |

### Notifiche legali sicure / bozze relata / comunicazioni cliente 2.217.1

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct/notifiche_legali.py web/services/react_notifiche_legali_bridge.py web/services/core_runtime.py web/blueprints/api_v1_react.py tests/test_notifiche_legali.py` | OK | Sintassi confermata per hardening template, bridge React, default tenant-aware notifiche, API e test. |
| `python -m pytest -q tests/test_notifiche_legali.py --tb=short` | OK | 22/22 passati: token sicuri, blocco Jinja/accessi riservati, modelli standard, anteprima compilata, bozze tenant-aware, comunicazioni cliente separate e robustezza JSON. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per nuovi tipi `LegalRelataPreviewResult`, `LegalRelataDraftResult`, modelli cliente e funzioni API. |
| `node frontend/scripts/check-react-contracts.mjs` | OK | Contratti React confermati per endpoint anteprima relata, bozze relata, modelli cliente separati e route `/notifiche-legali`. |
| `npm --prefix frontend run build` | OK | Build Vite 2.217.1 completata in 6.89s; chunk lazy `NotificheLegaliPage-ZR7Tq272.js` 50.44 kB / 11.59 kB gzip e CSS 11.43 kB / 2.30 kB gzip. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.217.1. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate per 2.217.1. |
| Docker locale `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini finali 2.217.1 ricostruite senza backup; app, scheduler, OCR e Redis healthy, Nginx attivo, `/api/pronto` 200 con versione `2.217.1`. |
| Browser Chrome headless su `/notifiche-legali` desktop/tablet/mobile | OK | Dopo warm-up tenant gia' documentato: desktop 677.8 ms, tablet 620.0 ms, mobile 634.6 ms a contenuto visibile; nessun errore console, nessun overflow, nessun testo tecnico vietato; tab cliente senza catalogo relata e senza versione `2026.05.12`. |

### Sincronizzazione calendari bidirezionale 2.217.0

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct/calendar_providers/base.py pct/calendar_providers/__init__.py pct/calendar_credentials.py pct/calendar_bindings.py pct/calendar_conflicts.py pct/calendar_providers/demo.py pct/calendar_providers/webcal.py pct/calendar_providers/google.py pct/calendar_providers/microsoft.py pct/calendar_providers/apple_caldav.py pct/calendar_sync_engine.py web/services/react_impostazioni_calendar.py web/blueprints/api_v1_react.py web/blueprints/api_v1.py pct/scheduler.py tools/demo_calendar_sync.py` | OK | Sintassi confermata per provider, repository, motore, API, scheduler e demo. |
| `python -m pytest tests/test_calendar_sync.py` | OK | 2/2 passati: compatibilita' WebCal/ICS esistente preservata. |
| `python -m pytest tests/test_calendar_sync_engine.py` | OK | 6/6 passati: push/pull demo, update, conflitto, scadenza perentoria protetta e privacy export. |
| `python -m pytest tests/test_calendar_credentials.py` | OK | 1/1 passato: token salvato cifrato, valore in chiaro assente dal file. |
| `python -m pytest tests/test_calendar_demo_provider.py` | OK | 1/1 passato: provider locale persistente con cursor, update, delete e reload da disco. |
| `python -m pytest tests/test_calendar_api.py` | OK | 1/1 passato: collegamento ambiente prova locale, sync account e payload senza credenziali esposte. |
| `python tools/demo_calendar_sync.py` | OK | Demo persistente completata: account, calendario, appuntamento, push, binding, pull, conflitto, scadenza perentoria e privacy `busy_only`. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per il pannello Impostazioni Calendari e nuovi client API. |
| `npm --prefix frontend run test` | OK | Contratti React confermati dopo aggiunta account/calendari/conflitti. |
| `npm --prefix frontend run build` | OK | Build Vite 2.217.0 finale completata in 5.95s; asset React rigenerati in `web/static/react` con fix overflow mobile topbar/sidebar. |
| Browser Chrome headless su `Impostazioni -> Calendari` desktop/tablet/mobile | OK | Sezioni `Collega account`, `Calendari collegati` e `Conflitti calendario` visibili; nessun errore console, nessun overflow documentale e nessun testo tecnico vietato. |
| Docker locale `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Immagini finali 2.217.0 ricostruite dopo asset CSS; app, scheduler, OCR e Redis healthy, Nginx attivo, `/api/pronto` 200 con versione `2.217.0`. |

### Notifiche legali parametriche / precompilazione IUSENTRA 2.216.8

| Verifica | Esito | Nota |
| --- | --- | --- |
| Controllo catalogo `pct/data/notifiche_legali_templates.json` | OK | Catalogo versione `2026.05.12` con 39 voci: tutti i modelli 01-34 richiesti piu' varianti operative 01A-01E. |
| `python -m py_compile pct/notifiche_legali.py web/services/react_notifiche_legali_bridge.py web/blueprints/api_v1_react.py` | OK | Sintassi confermata per motore parametrico, bridge precompilazione e API React. |
| `python -m pytest -q tests/test_notifiche_legali.py --tb=short` | OK | 7/7 passati: generazione L. 53, comunicazione cliente, prova deposito, attestazioni automatiche e precompilazione da dati IUSENTRA. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per nuovi tipi pratica/destinatario/documento e UI assistita. |
| `npm --prefix frontend run test` | OK | Contratti React confermati per `/notifiche-legali`, endpoint e workflow separati. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Route gate coerente: `/notifiche-legali` resta `react_operational_full`. |
| `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Contratto full React e no-fake confermati dopo la precompilazione. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.216.8. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate per 2.216.8. |
| `npm --prefix frontend run build` | OK | Build Vite 2.216.8 completata in 5.95s; `NotificheLegaliPage-MxCCwTqZ.js` resta lazy-loaded e il bundle iniziale resta sostanzialmente invariato. |
| `docker compose build app scheduler-worker ocr-worker` | OK | Immagini locali costruite con wheel `pct-studio-legale==2.216.8`, senza creare backup. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` / `docker compose ps` / `GET http://127.0.0.1:8080/api/pronto` | OK | Container locali healthy; readiness `versione=2.216.8`; runtime container `pct.__version__=2.216.8`. |
| Browser reale Docker locale `http://127.0.0.1:8080/notifiche-legali` desktop/mobile | OK | Blocco `Compilazione assistita da IUSENTRA` visibile; desktop 539 ms e mobile 516 ms a contenuto visibile dopo warm-up; nessun overflow orizzontale, nessun errore console e nessun testo tecnico vietato. |
| Deploy Hetzner CPX42 manuale senza backup / `GET https://app.iusentra.it/api/pronto` | OK | Repository server e branch remoti allineati sul commit finale 2.216.8; container `app`, `redis`, `scheduler-worker`, `ocr-worker`, `caddy` e `ollama` healthy/up; readiness pubblica `versione=2.216.8`. |

### Notifiche legali L. 53 / comunicazioni cliente 2.216.7

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall pct/notifiche_legali.py web/services/react_notifiche_legali_bridge.py web/blueprints/api_v1_react.py web/blueprints/email_client.py web/blueprints/email_ordinaria.py tests/test_notifiche_legali.py tests/test_react_shell.py -q` | OK | Sintassi confermata per dominio notifiche, bridge React, blocchi email e test collegati. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo `NotificheLegaliPage`, data client e link dalla pagina PEC. |
| `node frontend/scripts/check-react-contracts.mjs` | OK | Contratti React aggiornati per route `/notifiche-legali`, endpoint dedicati e workflow separati. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Route gate e manifest coerenti: `/notifiche-legali` e' sbloccata come `react_operational_full`. |
| `python -m pytest -q tests/test_notifiche_legali.py` | OK | 5/5 passati: notifica L. 53, cliente senza relata, prova deposito RAC/RdAC e API React. |
| `python -m pytest -q tests/test_react_shell.py::test_react_comunicazioni_email_messaggi_collegate_nav_e_shell tests/test_react_shell.py::test_route_ufficiali_email_messaggi_servono_react_con_vista_classica_tecnica` | OK | 2/2 passati: nav Comunicazioni, route ufficiali React e shell confermate. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.216.7. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate per 2.216.7. |
| `npm --prefix frontend run build` | OK | Build Vite 2.216.7 completata in 6.39s; generati chunk lazy `NotificheLegaliPage-BUG2q9Nt.js` e CSS dedicato. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.216.7`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` / `docker compose ps` / `GET http://127.0.0.1:8080/api/pronto` | OK | Container locali healthy e readiness `versione=2.216.7`. |
| Browser reale `http://127.0.0.1:8080/notifiche-legali` desktop/tablet/mobile | OK | Workflow `Notifica ex L. 53/1994`, `Deposito prova notifica` e `Comunica al cliente` visibili; oggetto obbligatorio, form RAC/RdAC e comunicazione cliente presenti; nessun errore console e nessun testo tecnico vietato rilevato. |
| Deploy Hetzner CPX42 `deploy/hetzner` / `GET https://app.iusentra.it/api/pronto` | OK | Backup preventivo eseguito, repository server sul branch `Codex/legal-electronic-filing-kIxcV`, container `app`, `redis`, `scheduler-worker`, `ocr-worker`, `caddy` e `ollama` healthy/up; readiness pubblica `versione=2.216.7`. |

### Fascicolo Veloce guidato / apertura deposito 2.216.5

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall web\bootstrap\fascicoli_core_routes.py web\services\react_fascicoli_bridge.py web\blueprints\api_v1_react.py tests\test_react_shell.py` | OK | Sintassi confermata dopo selezione uffici/soggetti reali, validazioni chiare e redirect al deposito assistito. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo nuovi tipi `judicialOffices`, `subjects` e selettori React del form. |
| `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_react_fascicoli_api_suite_usa_repository_reali tests/test_react_shell.py::test_react_fascicolo_nuovo_form_collassabile_e_fascicolo_veloce tests/test_react_shell.py::test_post_nuovo_fascicolo_veloce_carica_documenti_ed_email_eml tests/test_react_shell.py::test_post_nuovo_fascicolo_veloce_crea_e_collega_soggetto_controparte tests/test_react_shell.py::test_post_nuovo_fascicolo_veloce_restituisce_errori_chiari_json --tb=short` | OK | 6/6 passati: form React, payload reale, apertura deposito, persistenza controparte/CF, creazione soggetto collegato e messaggi JSON chiari confermati. |
| `npm --prefix frontend run build` | OK | Build Vite 2.216.5 completata in 6.15s; asset React rigenerati in `web/static/react`. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.216.5. |
| `npm --prefix frontend run test` | OK | Contratti React confermati dopo le modifiche a `/fascicoli/nuovo`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate per 2.216.5. |
| `python tools\codex_harness\run_codex_quality_gate.py --mode code` | OK | Gate Codex Harness eseguito sul perimetro applicativo dopo il commit: scope, dipendenze runtime, AGENTS e Open Design support verdi. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.216.5`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` / `docker compose ps` / `GET http://127.0.0.1:8080/api/pronto` | OK | Container locali healthy e readiness `versione=2.216.5`. |
| Browser reale `http://127.0.0.1:8080/fascicoli/nuovo` desktop/tablet/mobile | OK | Selezione cliente arricchita, controparte/soggetto, autorita' giudiziaria reale e Fascicolo Veloce visibili; nessun overflow nelle sezioni verificate e nessun errore console. |

### Local Signer PST ricerca-snapshot 1.6.28 / app 2.216.4

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall tools/local_signer.py` | OK | Sintassi sorgente confermata dopo `auth_ready` prudente e nuovo endpoint `/pst/ricerca-snapshot`. |
| `python -m pytest -q tests/test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests/test_local_signer.py::test_pst_prepare_authenticated_session_esegue_preflight_una_sola_volta tests/test_local_signer.py::test_pst_prepare_authenticated_session_non_marca_cookie_pronto_su_preflight_timeout tests/test_local_signer.py::test_pst_ricerca_snapshot_batcha_ricerca_e_documenti_senza_preflight tests/test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser --tb=short` | OK | 6/6 passati: preflight timeout non abilita cookie-only, ricerca esatta batcha ricerca+documenti e wizard Flask/React conoscono il nuovo endpoint. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo riuso snapshot in `TelematicoSurfacePage`. |
| `python tools\build_dist.py` | OK | Generati `SetupLocalSigner-1.6.28.exe`, alias `SetupLocalSigner.exe`, `InstallaLocalSigner-1.6.28.command`, `InstallaLocalSigner-1.6.28.run`, PS1 interno e note release. |
| `npm --prefix frontend run build` | OK | Build Vite 2.216.4 completata; asset React rigenerati in `web/static/react`. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato per app 2.216.4. |
| `python -m compileall tools\local_signer.py tools\dist\local_signer.py tests\test_local_signer.py tests\test_polisweb.py -q` | OK | Sintassi confermata su sorgente, dist e guardrail PST. |
| `python -m pytest -q tests\test_local_signer.py --tb=short` | OK | 124/124 passati: dist, sessioni PST, preflight prudente, batch e endpoint ricerca-snapshot confermati. |
| `python -m pytest -q tests\test_polisweb.py::test_dettaglio_fascicolo_mostra_download_ufficiale_portale tests\test_polisweb.py::test_acquisizione_wizard_pst_preview_error_usa_fallback_assistito tests\test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita tests\test_polisweb.py::test_portale_acquisizione_wizard_renderizza_javascript_valido tests\test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser --tb=short` | OK | 5/5 passati: wizard PST, fallback assistito, JavaScript e superficie React allineati. |
| `python -m compileall pct\fascicoli.py web\services\telematico_runtime.py tests\test_polisweb.py -q` | OK | Sintassi confermata dopo import PST parziale su pratica esistente e merge metadati portale arricchito. |
| `python -m pytest -q tests\test_polisweb.py::test_api_portale_acquisizione_import_pst_blocca_catalogo_senza_file tests\test_polisweb.py::test_api_portale_acquisizione_import_pst_parziale_aggiorna_pratica_esistente tests\test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita --tb=short` | OK | 3/3 passati: zero file PST resta bloccato, pratica esistente con download parziale viene aggiornata e il documento mancante resta catalogato con identificativi portale. |
| `python -m pytest -q tests\test_polisweb.py::test_api_portale_acquisizione_import_pst_parziale_aggiorna_pratica_esistente tests\test_polisweb.py::test_api_portale_acquisizione_import_pst_arricchisce_file_locali_con_metadati_preview tests\test_polisweb.py::test_dettaglio_fascicolo_mostra_download_ufficiale_portale --tb=short` | OK | 3/3 passati: regressione laterale su metadati portale, dettaglio fascicolo e arricchimento file PST esclusa. |
| `python -m pytest -q tests\test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita --tb=short` | OK | Guardrail statico aggiornato: autocomplete uffici supporta anche risposta `/api/uffici` con chiave `value`. |
| Browser reale `http://127.0.0.1:8080/portali/pst/acquisizione` Palmi RG 274/2026 | OK | Selezionato Tribunale di Palmi, ricerca snapshot con dati completi, Step 5 su `Aggiorna pratica esistente`, import finale su `/fascicoli/B6A03AE6#sezione-documenti-fascicolo`; log Local Signer con `/pst/ricerca-snapshot` e `/pst/download-documenti-batch`, senza `/pst/preflight-auth` intermedio. |
| `python tools\check_local_signer_boundaries.py` | OK | Boundary check Local Signer confermato dopo bump 1.6.28. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: packaging e readiness release confermate per 2.216.4. |
| `rg -n "fetch\([^\r\n]*(pst\.giustizia\|processotelematico\.giustizia\|giustizia\.it)\|XMLHttpRequest\([^\r\n]*(pst\.giustizia\|processotelematico\.giustizia\|giustizia\.it)" frontend\src web\templates integrations -g "*.ts" -g "*.tsx" -g "*.js" -g "*.html"` | OK | Nessuna chiamata diretta ai domini ministeriali nei sorgenti browser; il flusso PST resta sul Local Signer locale. |

### Local Signer PST sessione unica 1.6.27 / app 2.216.3

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python tools\build_dist.py` | OK | Generati `SetupLocalSigner-1.6.27.exe`, alias `SetupLocalSigner.exe`, `InstallaLocalSigner-1.6.27.command`, `InstallaLocalSigner-1.6.27.run`, PS1 interno e note release. |
| `python -m compileall tools\local_signer.py tools\dist\local_signer.py tests\test_local_signer.py tests\test_polisweb.py -q` | OK | Sintassi confermata su sorgente, dist e guardrail PST dopo unificazione sessione. |
| `python tools\sync_packaging_files.py --check` | OK | Versione applicativa 2.216.3 sincronizzata tra sorgente Python, frontend, Docker e Railway. |
| `python tools\check_local_signer_boundaries.py` | OK | Boundary check Local Signer confermato dopo bump 1.6.27. |
| `python -m pytest -q tests\test_local_signer.py --tb=short` | OK | 122/122 passati: session manager, download batch, compatibilita' preflight e dist Local Signer allineati. |
| `python -m pytest -q tests\test_polisweb.py::test_dettaglio_fascicolo_mostra_download_ufficiale_portale tests\test_polisweb.py::test_acquisizione_wizard_pst_preview_error_usa_fallback_assistito tests\test_polisweb.py::test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita tests\test_polisweb.py::test_portale_acquisizione_wizard_renderizza_javascript_valido --tb=short` | OK | 4/4 passati: dettaglio fascicolo e wizard acquisizione usano batch, sessione view e JavaScript valido. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: packaging e readiness release confermate per 2.216.3. |
| `rg -n "fetch\([^\r\n]*(pst\.giustizia\|processotelematico\.giustizia\|giustizia\.it)\|XMLHttpRequest\([^\r\n]*(pst\.giustizia\|processotelematico\.giustizia\|giustizia\.it)" frontend\src web\templates integrations -g "*.ts" -g "*.tsx" -g "*.js" -g "*.html"` | OK | Nessuna chiamata browser diretta ai domini ministeriali nei sorgenti applicativi; il flusso PST resta su `127.0.0.1:27272`. |
| `git diff --check` | OK | Nessun errore whitespace; presenti solo warning CRLF su file runtime/preesistenti e file toccati. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Rebuild locale no-cache completato; wheel `pct-studio-legale==2.216.3` inclusa nell'immagine. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini 2.216.3 senza procedure di backup. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 30` | OK | Readiness locale 200 con `versione=2.216.3`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.216.3`. |
| `docker exec iusentra-app python -c "... SetupLocalSigner-1.6.27.exe ..."` | OK | Nel container locale sono presenti `SetupLocalSigner-1.6.27.exe` e alias `SetupLocalSigner.exe`, alias valido con header `MZ`. |
| Deploy manuale Hetzner senza backup | OK | Deploy eseguito senza `deploy.sh` e senza script backup: server allineato al commit pushato, app/scheduler/OCR/Redis healthy, runtime `2.216.3`, `SetupLocalSigner-1.6.27.exe` presente e alias `SetupLocalSigner.exe` valido con header `MZ`. |
| `curl -fsS https://app.iusentra.it/api/pronto` | OK | Produzione Hetzner pronta con `versione=2.216.3`. |

### Local Signer distribuito 1.6.26 / app 2.216.2

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python tools/build_dist.py` | OK | Generati `SetupLocalSigner-1.6.26.exe`, alias `SetupLocalSigner.exe`, `InstallaLocalSigner-1.6.26.command`, `InstallaLocalSigner-1.6.26.run`, PS1 interno e note release. |
| `python -m compileall tools\local_signer.py tests\test_local_signer.py -q` | OK | Sintassi confermata dopo bump Local Signer e guardrail dist. |
| `python tools\check_local_signer_boundaries.py` | OK | Boundary check Local Signer confermato. |
| `python tools\sync_packaging_files.py --check` | OK | Versione applicativa 2.216.2 sincronizzata tra packaging, Docker e Railway. |
| `python -m pytest -q tests\test_local_signer.py::test_local_signer_dist_allineato_a_sorgente_e_installer_versionati tests\test_local_signer.py::test_installer_local_signer_windows_legacy_restituisce_exe_senza_login tests\test_local_signer.py::test_installer_local_signer_windows_setup_route_e_pubblica tests\test_local_signer.py::test_installer_local_signer_windows_exe_route_se_bundle_presente tests\test_local_signer.py::test_installer_local_signer_macos_e_pubblico tests\test_local_signer.py::test_installer_local_signer_linux_e_pubblico --tb=short` | OK | 6/6 passati: dist allineato alla sorgente, alias EXE valido e download installer pubblici funzionanti. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate dopo 2.216.2. |
| `git diff --check` | OK | Nessun errore whitespace; presenti solo warning CRLF su file runtime/preesistenti e package JSON. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Rebuild locale no-cache completato; wheel `pct-studio-legale==2.216.2` inclusa nell'immagine. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini 2.216.2. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.216.2`. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 30` | OK | Readiness locale 200 con `versione=2.216.2`. |
| `docker exec iusentra-app python -c "... SetupLocalSigner-1.6.26.exe ..."` | OK | Nel container locale e' presente `SetupLocalSigner-1.6.26.exe`, alias `SetupLocalSigner.exe` valido e header Windows `MZ`. |
| Deploy manuale Hetzner senza backup su commit `37dce78f` | OK | Server allineato al commit pushato, container app/scheduler/ocr/redis healthy, runtime `2.216.2`, alias `SetupLocalSigner.exe` con header `MZ`. |
| `curl -fsS https://app.iusentra.it/api/pronto` | OK | Produzione Hetzner pronta con `versione=2.216.2`. |

### Hotfix PST Local Signer batch 2.216.1

| Verifica | Esito | Nota |
| --- | --- | --- |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo sessione PST React con preflight, ricerca, snapshot e download batch via Local Signer browser. |
| `python -m compileall integrations/sigp_sync/local_connector_client.py integrations/sigp_sync/routes.py tests/test_sigp_sync.py tests/test_react_shell.py -q` | OK | Sintassi confermata per client/route SIGP e test mirati. |
| `python -m pytest -q tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_sigp_sync.py::test_sigp_sync_visibile_nel_menu_e_apre_primo_fascicolo_importato tests/test_sigp_sync.py::test_sigp_sync_local_connector_preview_e_download_salva_file tests/test_sigp_sync.py::test_sigp_sync_download_duplicato_passa_original_true_al_local_signer --tb=short` | OK | 4/4 passati: il wizard React usa Local Signer PST e SIGP non torna al download singolo. |
| `npm --prefix frontend run test` | OK | Contratti React confermati dopo l'hotfix PST. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.216.1. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate. |
| `npm --prefix frontend run build` | OK | Build Vite 2.216.1 completata in 5.84s; asset React rigenerati. |
| `python -m pytest -q tests/test_sigp_sync.py --tb=short` | OK | 13/13 passati: SIGP/PST batch, catalogo, import e salvataggio browser confermati. |
| `python -m pytest -q tests/test_local_signer.py::test_wizard_pst_usa_snapshot_unico_e_sessioni_distinte --tb=short` | OK | Wizard classico PST ancora coerente con snapshot unico e sessioni gestite dal Local Signer. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Route gate invariato e coerente. |
| `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Full React contract e no-fake React full verdi. |
| `git diff --check` | OK | Nessun errore whitespace; presenti solo warning CRLF su file gia' gestiti da Git/runtime locale. |

### Fascicolo Veloce e form collassabile 2.216.0

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall web/bootstrap/fascicoli_core_routes.py web/services/react_fascicoli_bridge.py pct/fascicoli.py tests/test_react_shell.py` | OK | Sintassi confermata per backend fascicoli, bridge React e test mirati. |
| `python -m pytest -q tests/test_react_shell.py::test_react_fascicolo_nuovo_form_collassabile_e_fascicolo_veloce tests/test_react_shell.py::test_post_nuovo_fascicolo_veloce_carica_documenti_ed_email_eml --tb=short` | OK | 2/2 passati: sezioni collassabili, `Pratiche collegate` sotto `Personalizzabile`, upload documenti e import `.eml` nel fascicolo. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo pannelli collassabili e stato `Fascicolo Veloce`. |
| `npm --prefix frontend run test` | OK | Contratti React confermati dopo la modifica alla pagina `/fascicoli/nuovo`. |
| `npm --prefix frontend run build` | OK | Build Vite finale completata in 6.02s; asset React rigenerati in `web/static/react`. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Route gate invariato e coerente dopo la modifica a `/fascicoli/nuovo`. |
| `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Contratto full React e audit anti-mascheramento coerenti. |
| `node scripts/react-migration/check-no-fake-react-full.mjs` | OK | Nessuna route full mascherata dopo la tranche Fascicolo Veloce. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging/versione 2.216.0 sincronizzati tra Python, frontend, Docker e Railway. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate dopo bump 2.216.0. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Rebuild finale no-cache completato con wheel `pct-studio-legale==2.216.0` e asset React aggiornati. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini finali 2.216.0. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 30` | OK | Readiness locale 200 con `versione=2.216.0`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.216.0`. |
| Browser Playwright headless su `/fascicoli/nuovo` desktop/tablet/mobile | OK | Sezioni collassabili, `Fascicolo Veloce`, upload documenti/email EML, `Presidio deposito assistito`, nessun overflow, nessun errore console e nessun testo tecnico vietato. Primo accesso post-restart ha riprodotto il warm-up tenant gia' aperto; passaggi caldi desktop 761.3/647.2/538.7 ms a contenuto visibile, tablet 692.5 ms, mobile 646.7 ms. |
| `python tools/codex_harness/run_codex_quality_gate.py --mode code` | OK | Gate di supporto pre-deploy eseguito dopo il commit applicativo: perimetro code, dipendenze runtime, guardrail AGENTS e Open Design support verdi. |

### Hotfix `/documenti` React 2.215.7

| Verifica | Esito | Nota |
| --- | --- | --- |
| `npm run typecheck` | OK | TypeScript confermato dopo aggiunta route/sidebar/workspace Documenti e rimozione falso positivo Tariffario. |
| `npm run test` | OK | Contratti React confermati: `/documenti` e' governata e non torna legacy-first. |
| `python -m compileall web\bootstrap\react_route_gate.py web\blueprints\react_shell.py web\services\react_studio_module_bridge.py -q` | OK | Sintassi backend confermata per gate, shell route e bridge StudioModule. |
| `node scripts\react-migration\check-route-gate.mjs` | OK | Route gate allineato: `/documenti` censita tra le route governate consentite. |
| `node scripts\react-migration\check-full-react-route-contract.mjs` | OK | Full React contract verde dopo filtro record visibili e fix falso positivo Tariffario. |
| `python -m pytest -q tests/test_react_shell.py::test_react_blocco_finale_studio_admin_completo tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short` | OK | 4/4 passati: route, shell, gate e payload operativo Documenti coperti. |
| `python -m pytest -q tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short` | OK | Rilancio mirato dopo filtro record `demo`/`sample`: payload operativo confermato. |
| `npm run build` | OK | Build Vite 2.215.7 completata in 6.15s; asset React rigenerati in `web/static/react`. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.215.7. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate. |
| `python -m json.tool tools\react-migration\route-manifest.json` / `python -m json.tool artifacts\react-migration\legacy-contracts\documenti.json` | OK | Manifest e contratto legacy `/documenti` validi JSON. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Eseguito due volte: rebuild finale dopo il filtro Python del bridge Documenti; package `pct-studio-legale==2.215.7`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini 2.215.7. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 20` | OK | Readiness locale 200 con `versione=2.215.7`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.215.7`. |
| Browser Playwright headless su `/documenti` desktop/tablet/mobile | OK | Desktop 352.9 ms, tablet 210.8 ms, mobile 167.9 ms a contenuto React visibile; nessun overflow, nessun errore console, nessun termine tecnico visibile. |
| Payload JSON `/api/v1/ui/studio-modules/documenti` | OK | Status 200 e nessun `demo`/`sample` nel payload dopo filtro record visibili. |

### Catalogo ufficiale CodiceOggetto PST e ricerca UI 2.215.6

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall pct\pratiche_collegate_catalog.py` | OK | Sintassi confermata dopo separazione catalogo tecnico ufficiale e catalogo UI compatto. |
| `python -m pytest -q tests/test_codici_oggetto_pst_catalog.py --tb=short` | OK | 3/3 passati: 1.018 codici XSD ufficiali, `014001` e `111604` presenti, `014700` escluso perche' non trovato negli XSD attivi. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo introduzione di `CodiceOggettoPstSearch` e catalogo UI compatto. |
| `node frontend\scripts\check-react-contracts.mjs` | OK | Contratti React aggiornati: Preventivi, Wizard e Fascicoli usano ricerca rapida CodiceOggetto e catalogo ufficiale compatto. |
| `python -m pytest -q tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_create_crea_preventivo_reale_con_cliente_potenziale_e_clausola tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_rifiuta_codice_oggetto_non_ufficiale tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_genera_conferimento_solo_dopo_accettazione_cliente --tb=short` | OK | 3/3 passati: wizard, codice ufficiale, rifiuto codice inventato e conferimento restano governati. |
| `python -m pytest -q tests/test_deposito_guidato.py::test_orchestratore_blocca_deposito_pct_senza_codice_oggetto_pst tests/test_deposito_guidato.py::test_api_validazione_deposito_restituisce_semaforo_e_consente_con_warning --tb=short` | OK | 2/2 passati: pre-deposito continua a bloccare fascicoli PCT senza CodiceOggetto ufficiale. |
| `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_api_suite_usa_repository_reali --tb=short` | OK | Form fascicolo e propagazione CodiceOggetto confermati sui repository reali di test. |
| `python -m pytest -q tests/test_practice_engine_validators.py --tb=short` | OK | 3/3 passati: validatori pratica continuano a usare il catalogo ufficiale. |
| `npm --prefix frontend run build` | OK | Build Vite 2.215.6 completata in 7.36s; il chunk `CodiceOggettoPstSearch` resta separato e gzip circa 31 KB. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging/versione 2.215.6 sincronizzati. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate dopo bump 2.215.6. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con package `pct-studio-legale==2.215.6`. |
| `docker compose up -d app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini 2.215.6; app, scheduler, OCR e Redis healthy. |
| `Invoke-RestMethod -Uri http://127.0.0.1:8080/api/pronto` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.215.6"}`. |
| Browser Chrome headless desktop/tablet/mobile su `/fascicoli/nuovo`, `/preventivi/nuovo`, `/preventivi/conferimento/nuovo`, `/preventivi/wizard` | OK | Ricerca CodiceOggetto visibile e usabile: `014001` selezionabile, ricerca `famiglia` con 12 risultati, `111604` presente, `014700` escluso; nessun overflow orizzontale o errore console. |

### Hotfix visualizzazione allegati email 2.215.5

| Verifica | Esito | Nota |
| --- | --- | --- |
| `node frontend\scripts\check-react-contracts.mjs` | OK | Contratti React aggiornati: il dettaglio messaggio espone `Visualizza` per gli allegati email in nuova scheda, distinto da `Scarica`. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo estensione del tipo `EmailAttachment` con `viewHref`. |
| `python -m compileall web\services\react_email_bridge.py web\blueprints\email_client.py web\blueprints\email_ordinaria.py` | OK | Sintassi backend confermata per i moduli email collegati agli allegati. |
| `python -m pytest -q tests/test_email_client.py::test_email_dettaglio_visualizza_e_scarica_allegato_salvato tests/test_email_client.py::test_email_ordinaria_dettaglio_usa_repository_smtp_e_allegati_ordinari --tb=short` | OK | 2/2 passati: link inline e download allegati confermati per PEC ed email ordinaria. |
| `npm --prefix frontend run build` | OK | Build Vite 2.215.5 completata in 5.42s con chunk `EmailPecPage` aggiornato. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging/versione 2.215.5 sincronizzati. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate dopo bump 2.215.5. |
| `python -m pytest -q tests/test_react_shell.py::test_react_comunicazioni_email_messaggi_collegate_nav_e_shell --tb=short` | OK | Shell React comunicazioni confermata dopo l'aggiunta dell'azione `Visualizza` agli allegati email. |
| `git diff --check` | OK | Nessun errore di whitespace; presenti solo warning CRLF su file gia' gestiti da Git/runtime locale. |

### Hotfix Email ordinaria bulk 2.215.2

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall pct/email_client.py web/blueprints/api_v1_react.py tests/test_email_client.py` | OK | Compilazione mirata dei file toccati dal fix bulk email. |
| `python -m pytest -q tests/test_email_client.py -k "email_ordinaria_react_bulk_action or fallback_globale_senza_tenant" --tb=short` | OK | 6 test verdi: cancellazione/spostamento multiplo ordinaria con salvataggio singolo e guardrail no fallback globale. |
| `python -m pytest -q tests/test_email_client.py -k "bulk_action" --tb=short` | OK | 5 test verdi: endpoint bulk PEC e ordinaria confermati dopo il passaggio ai metodi batch. |
| Prova sintetica `elimina_definitivamente_multipla()` con 1986 messaggi su file temporaneo | OK | 1986 eliminati, 0 residui, tempo locale 0.033s; conferma che il collo di bottiglia dei salvataggi ripetuti e' rimosso. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging/versione 2.215.2 sincronizzati. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test verdi su coerenza packaging e readiness release dopo il bump versione. |

### Hotfix Docker email ordinaria 2.215.3

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_web_bootstrap.py::test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina --tb=short` | OK | Contratto CI verde dopo ripristino `PCT_EMAIL_ORDINARIA_DB=/data/email/ordinaria.json` nel Dockerfile. |
| `python scripts/run_pytest_phases.py --core-shard 7 --core-total-shards 10 --core-subshard 3 --core-total-subshards 3 --core-subdivide-items --timeout-minutes 5` | OK | 36 test verdi: riprodotto localmente il sotto-shard `Pytest core fase 7/10 observability parte 3/3` che falliva su GitHub. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging/versione 2.215.3 sincronizzati. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test verdi su coerenza packaging e readiness release dopo il bump versione 2.215.3. |
| `python -m pytest -q tests/test_lex_professional_upgrade.py tests/test_lex_sources_and_studio_data.py --tb=short` | OK | 49 test verdi: test Lex gia' presenti usati per riallineare la coverage critica senza abbassare la soglia. |
| `python scripts/run_pytest_phases.py --suite coverage-critical --timeout-minutes 5 -- --cov=lex --cov=pct.auth --cov=pct.storage --cov=pct.storage_postgres --cov=pct.telematico_repository --cov=pct.telematico_workflow --cov-config=config/coverage-critical.ini --cov-report=term --cov-fail-under=71` | OK | Suite coverage critica verde localmente: 313 test, coverage totale 71.56%, soglia 71 rispettata. |

### Ripristino CI mirato 2026-05-10

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python tools/check_repo_governance.py` | OK | Governance di nuovo verde dopo rientro sotto budget dei bootstrap `dashboard_routes.py` e `scadenziario_routes.py` senza refactor funzionale, con helper richiesta condiviso e pulizia righe vuote superflue. |
| `python -m ruff check web/services/request_mode.py web/bootstrap/dashboard_routes.py web/bootstrap/scadenziario_routes.py` | OK | `Lint + syntax` mirato verde dopo correzione delle tre forme `if ...: return ...` che avevano riaperto il gate `E701` su `dashboard_routes.py`. |
| `python -m flake8 web/services/request_mode.py web/bootstrap/dashboard_routes.py web/bootstrap/scadenziario_routes.py` | OK | Sintassi e stile mirati confermati verdi sugli stessi file toccati dal fix CI. |
| `python -m py_compile web/services/request_mode.py web/bootstrap/dashboard_routes.py web/bootstrap/scadenziario_routes.py` | OK | Compilazione Python mirata verde dopo estrazione di `richiede_vista_classica()` e `richiede_json()` nel servizio condiviso. |
| `node frontend/scripts/check-react-contracts.mjs` | OK | Contratto React riallineato: ripristinato marker sticky del Tariffario e whitelist mirata per i riepiloghi fiscali governati di Fatturazione/Tariffario gia' ammessi dal prodotto. |
| `npm --prefix frontend run test -- --runInBand` | OK | Shard frontend `contratti` verde dopo fix Tariffario + guardrail contratti. |
| `python -m pytest -q tests/test_ci_no_regression_contract.py tests/test_packaging_consistency.py --tb=short` | OK | 12 test verdi sui contratti anti-regressione e packaging collegati ai gate CI. |
| `python -m pytest -q tests/test_web_bootstrap.py::test_i_moduli_bootstrap_restano_governabili --tb=short` | OK | Regressione specifica sul budget dei moduli bootstrap coperta e confermata verde. |
| `python tools/check_local_signer_boundaries.py` | OK | Guardrail Local Signer verde; il riepilogo CI relativo non ha piu' un errore locale riproducibile dopo il ripristino del gate principale. |
| `python -m ruff check --output-format=github --select E9,F63,F7,F82 core pct web lex tests tools/*.py worker.py gunicorn.conf.py vercel_app.py visible_signature.py wsgi.py` | OK | Gate `Lint + syntax` completo verde dopo correzione `F823` in `lex/providers/deterministic_provider.py` sul fallback `studio_data_lookup`. |
| `python -m pytest -q lex/tests/unit/test_router.py tests/test_lex_legal_studio_full.py::TestTC20PipelineCoerenza::test_pipeline_coherence --tb=short` | OK | 10 test Lex mirati verdi dopo il fix del provider deterministico; routing e pipeline professionale restano coerenti. |
| `python -m ruff check --config pyproject.toml packaging_manifest.py docker/entrypoint.py tools/sync_packaging_files.py pct/giurisprudenza_corpus.py lex/http_bounded_bridge.py lex/context/studio_context.py lex/retrieval lex/formatting/answer_builder.py tests/test_packaging_consistency.py tests/test_docker_entrypoint.py` | OK | `Ruff governed modules` verde dopo pulizia variabili inutilizzate e auto-fix sicuro degli import nei moduli Lex governati. |
| `python -m pytest -q lex/tests/unit/test_sentenze_clienti_fix.py::test_deterministic_provider_studio_data_lookup_no_technical_text tests/test_lex_legal_studio_full.py::TestTC20PipelineCoerenza::test_pipeline_coherence --tb=short` | OK | 6 test verdi: il lookup studio dati resta non tecnico e la pipeline professionale continua a chiudere senza regressioni dopo la pulizia Ruff governata. |

### Eliminazione multipla Email PEC e ordinaria 2.214.10

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_email_client.py -k "bulk_action or email_ordinaria_route_react_api_e_repository_separato_da_pec" --tb=short` | OK | 3 test verdi: payload React PEC/ordinaria con `bulkAction` corretto, spostamento multiplo nel cestino per la PEC e cancellazione definitiva multipla dal cestino ordinario. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo aggiunta checkbox, barra azioni multiple e submit JSON dedicato nelle due caselle email. |
| `npm --prefix frontend run build` | OK | Build Vite completata con asset aggiornati della pagina `EmailPecPage`, inclusa la nuova esperienza di selezione multipla. |

### Deduplica Email ordinaria 2.214.9

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_email_client.py -k "sincronizza_inviati_rimuove_doppione or email_ordinaria_route_react_api_e_repository_separato_da_pec" --tb=short` | OK | 2 test verdi: la casella ordinaria continua a restare separata dalla PEC e il sync degli inviati rimuove il doppione quando esiste gia' la copia IMAP stabile. |
| `python -m pytest -q tests/test_email_client.py -k "sincronizza_imap_non_fonde_uid_stabili_con_stesso_message_id or sincronizza_imap_migra_riferimenti_legacy_tramite_message_id" --tb=short` | OK | 2 test verdi: il fix non rompe la migrazione `Message-ID` dei record legacy e non fonde due invii distinti con UID IMAP stabili. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging allineato dopo bump versione `2.214.9`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test verdi: packaging e readiness confermati per la release `2.214.9`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite con package `pct-studio-legale==2.214.9`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` + `docker compose up -d --no-build --force-recreate app scheduler-worker ocr-worker` | OK | Servizi locali riallineati alle immagini `2.214.9`; ricreazione forzata necessaria per portare il runtime sul nuovo tag. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` + `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 20` + health inspect | OK | Runtime locale confermato su `2.214.9`; readiness JSON corretta e container `healthy` dopo i probe iniziali lenti di startup. |

### Isolamento utenti multi-studio 2.214.8

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_auth.py -k "tenant_scoped_auth or backend_auth_sqlite_mantiene_json_allineato or migra_utenti_legacy_json_in_sqlite" --tb=short` | OK | 3 test verdi: riparazione SQLite auth tenant da archivio locale, persistenza JSON sincronizzata e migrazione legacy JSON -> SQLite. |
| `python -m pytest -q tests/test_storage_strategy.py -k "admin_utenti_studio_mostra_utenti_tenant_sqlite or login_route_con_studio_slug_legge_utenti_dal_sqlite_del_tenant or bootstrap_legacy_runtime_data" --tb=short` | OK | 4 test verdi sul pannello utenti studio, login tenant-aware e blocco bootstrap root->tenant in ambiente multi-studio. |
| `python -m pytest -q tests/test_auth.py --tb=short` | OK | 40 test verdi sull'intero modulo auth dopo introduzione del tenant context obbligatorio e della sincronizzazione JSON/SQLite. |
| `python -m pytest -q tests/test_storage_strategy.py --tb=short` | OK | 40 test verdi sull'intero perimetro storage/auth multi-tenant, inclusi bootstrap, caching e route di amministrazione studio. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging confermato allineato alla release `2.214.8`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test verdi sui gate di packaging e readiness per la release multi-studio corretta. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo l'hardening del bridge React `/utenti`. |
| `npm --prefix frontend run build` | OK | Build Vite completata con asset aggiornati della pagina `UtentiPage`. |

### Parcella personalizzata Fatturazione 2.214.6

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_fatturazione.py tests/test_react_fatturazione_bridge.py tests/test_fattura_pa.py` | OK | 11 test verdi inclusi i casi forfettario/minimo senza IVA su calcolo parcella, salvataggio React e XML FatturaPA. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo il blocco UI dell'opzione IVA nei regimi senza imposta. |
| `npm --prefix frontend run build` | OK | Build Vite 2.214.6 completata con chunk aggiornato `FatturazionePage`. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging confermato allineato dopo il bump patch `2.214.6`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test verdi sulla release `2.214.6`. |
| `docker compose build app` | OK | Immagine locale ricostruita con wheel `pct-studio-legale==2.214.6`. |
| `docker compose up -d --force-recreate app` | OK | Recreate necessario per riallineare il container locale al nuovo tag applicativo. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` + `/api/pronto` interno + health inspect | OK | Runtime locale confermato su `2.214.6`; readiness JSON corretta e container `healthy` dopo i probe iniziali. |

### Parcella personalizzata Fatturazione 2.214.5

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_fatturazione.py tests/test_react_fatturazione_bridge.py tests/test_fattura_pa.py` | OK | 8 test verdi su calcoli parcella, bridge React della nuova parcella personalizzata e XML FatturaPA con snapshot documento/destinatario estero. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo l'estensione della pagina `/fatturazione/nuova` con sezioni trasmissione/studio/destinatario/documento/pagamento. |
| `npm --prefix frontend run build` | OK | Build Vite 2.214.5 completata; asset React rigenerati con i nuovi chunk `FatturazionePage`. |
| Browser reale `http://127.0.0.1:8091/fatturazione/nuova` desktop/tablet/mobile | OK | Login tecnico locale con dati reali seedati; presenti `Nuova parcella personalizzata`, sezioni trasmissione/studio/destinatario/documento/pagamento, nessun overflow orizzontale e nessun testo vietato `backend`, `payload`, `legacy`, `runtime`. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging confermato allineato dopo il bump release `2.214.5`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test verdi sulla release finale `2.214.5`. |
| `docker compose build --no-cache app` | OK | Rebuild locale no-cache completato con wheel `pct-studio-legale==2.214.5`. |
| `docker compose up -d --no-build redis app nginx` + `docker compose up -d --no-build --force-recreate app` | OK | Servizi locali rialzati; ricreazione forzata necessaria per allineare il container app al nuovo build. |
| `docker compose ps` + `docker inspect iusentra-app --format "{{json .State.Health}}"` | OK | `iusentra-app` healthy dopo alcuni probe iniziali lenti; Redis/Nginx attivi. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` + `/api/pronto` interno | OK | Verifica finale nel container: versione runtime `2.214.5` e risposta JSON `{\"ok\": true, \"versione\": \"2.214.5\"}`. |

### Hotfix contributo unificato preventivo 2.214.4

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_motore_preventivo.py tests/test_preventivi_wizard.py --tb=short` | OK | 47 test verdi: catalogo preventivi, bridge React wizard e regressione `Atto di citazione` con contributo unificato `EUR 237,00`. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo l'uso del profilo ricalcolato nel wizard per riallineare le spese vive suggerite. |

### Hotfix contributo unificato 2.214.3

| Verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_strumenti_legali.py -k contributo_unificato --tb=short` | OK | 6 test mirati verdi su civile valore non indicato, Cassazione tributaria, amministrativo Cassazione e appalti. |
| `python -m pytest -q tests/test_strumenti_legali.py --tb=short` | OK | 21 test verdi sull'intero modulo Strumenti Legali dopo l'aggiunta del nuovo selettore `Tipo valore` e l'allineamento dei contributi unificati. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging e file versione allineati alla release `2.214.3`. |

### Hotfix eliminazione clienti e soggetti 2.214.2

| Verifica | Esito | Nota |
| --- | --- | --- |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo aggiunta delete singolo/multiplo su Clienti e Soggetti. |
| `npm --prefix frontend run build` | OK | Build Vite 2.214.2 completata; asset React rigenerati in `web/static/react`. |
| `python -m pytest tests/test_react_shell.py -k "clienti_delete or soggetti_delete"` | OK | 2 test mirati verdi: payload React con `deleteHref` e endpoint JSON di eliminazione clienti/soggetti. |

### Hotfix Tariffario e Preventivo guidato 2.214.1

| Verifica | Esito | Nota |
| --- | --- | --- |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo CTA `Preventivo guidato`, payload compatti e ripristino riepilogo sticky. |
| `node frontend/scripts/check-react-contracts.mjs` | OK | Contratti React confermati: riepilogo Tariffario, azioni compatte e link Preventivo guidato restano governati. |
| `python -m pytest -q tests/test_react_tariffario_console.py tests/test_react_preventivo_wizard_console.py --tb=short` | OK | 17 test passati: payload sotto soglia, wizard, archivio preventivi e sticky Tariffario coperti. |
| `npm --prefix frontend run build` | OK | Build Vite 2.214.1 completata; asset React rigenerati in `web/static/react`. |
| Browser `localhost:5003/tariffario` desktop/tablet/mobile | OK | Sessione isolata 2.214.1: desktop dopo scroll mostra ancora riepilogo, `Calcola e aggiorna`, `Crea preventivo` e `Reset`; tablet/mobile senza errori console. |
| Browser `localhost:5003/preventivi/` e `/preventivi/wizard` | OK | `Preventivo guidato` presente in archivio con 3 link a `/preventivi/wizard`; wizard caricato senza errori console. |
| Misura client Flask autenticato | OK | `/api/v1/ui/tariffario` 416585 byte / media 66.4 ms; `/api/v1/ui/preventivi/wizard` 704916 byte / media 46.8 ms; `/preventivi/` 9124 byte / media 5.4 ms. |
| Docker locale `docker compose build --no-cache app scheduler-worker ocr-worker` + `docker compose up -d app scheduler-worker ocr-worker nginx` | OK | Rebuild no-cache finale 2.214.1 verde; app, scheduler, OCR e Redis healthy, Nginx attivo, `/api/pronto` 200 con versione `2.214.1` e runtime container `2.214.1`. |

### Tranche 2.213.0 - pagine operative richieste full React

| Verifica | Esito | Nota |
| --- | --- | --- |
| `node frontend/scripts/check-react-contracts.mjs` | OK | Contratti aggiornati: submit React centralizzato, route richieste governate, niente regressione sui contratti esistenti. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Manifest/gate allineati dopo promozione delle route richieste e alias full React. |
| `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Anti-mascheramento verde: 84 route censite, nessun full React fittizio e nessun form POST HTML nei target full. |
| `npm --prefix frontend run typecheck` | OK | TypeScript senza errori dopo conversione JsonPostForm e pulizia testi UI. |
| `npm --prefix frontend run build` | OK | Build Vite produzione rigenerata con asset React 2.213.0. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato con versione 2.213.0. |

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
| `node frontend/scripts/check-react-contracts.mjs` | OK | Contratti React aggiornati per Impostazioni, Pagamenti, Notifiche, Backup e Calendari. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Gate route allineato: `/backup`, `/impostazioni/calendario` e `/sincronizzazione-calendari` aprono Impostazioni React; sottoroute operative restano protette. |
| `python -m pytest -q tests/test_react_shell.py::test_impostazioni_react_api_redige_segreti_e_salva_configurazioni tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale --tb=short` | OK | 2 test passati dopo fix loader backup: segreti redatti, occhio sui campi riservati, link Google App Password e AI Locale coperti. |
| `python -m pytest -q tests/test_react_shell.py -k "impostazioni or route_gate_non_promuove_moduli_studio_telematico_admin_incompleti or react_blocco_finale_route_reali_e_vista_classica or react_blocco_finale_studio_admin_completo or navigation_sidebar" --tb=short` | OK | 6 test passati su shell, gate, sidebar e Impostazioni full React. |
| `npm test -- --runInBand` | OK | Contratti frontend React verdi. |
| `npm run typecheck` | OK | TypeScript verde dopo integrazione tab Backup/Calendari e testi non tecnici. |
| `npm run build` | OK | Build Vite produzione rigenerata; chunk corrente `ImpostazioniPage-BliipEpP.js`. |
| `python -m pytest -q tests/test_impostazioni_ai_locale_react.py tests/test_impostazioni_pec_local_signer_react.py --tb=short` | OK | 5 test passati: AI Locale e PEC verificano il PC in uso tramite IUSENTRA Local Signer e la shell React carica i guard statici. |
| `python -m pytest -q tests/test_web_bootstrap.py::test_lex_assistant_usa_componente_esterno_e_posizione_persistente --tb=short` | OK | Shell React compatibile con widget Lex e bridge browser dopo aggiunta guard AI Locale. |
| `node scripts/react-migration/check-no-fake-react-full.mjs` | OK | Nessuna route full React fittizia. |
| `node scripts/react-migration/audit-anti-mascheramento.mjs` | OK | Audit aggiornato: 55 route censite, 73 link legacy, nessun `LegacyPostForm` o form POST HTML React. |
| `python -m pytest -q tests/test_backup.py tests/test_calendar_sync.py --tb=short` | OK | 28 test passati su backup e sincronizzazione calendari. |
| `python -m pytest -q tests/test_impostazioni_firma.py tests/test_local_signer.py tests/test_firma_pkcs11.py --tb=short` | OK | Test firma, Local Signer e canale PKCS#11 passati. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_web_bootstrap.py --tb=short` | OK | 54 test passati su packaging, bootstrap e contratti runtime. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato con versione 2.209.0. |
| `python -m pytest -q tests/test_release_readiness.py --tb=short` | OK | Release readiness passata. |
| `python tools/check_repo_governance.py` | OK | Governance verde: `web/app.py` 40 righe e 0 route inline. |
| Verifica browser locale isolata `/backup`, `/impostazioni?tab=backup`, `/impostazioni/calendario`, `/impostazioni?tab=smtp` | OK | Login temporaneo con dati fuori repo; Backup e Calendari nella stessa pagina Impostazioni, link Google App Password presente, nessun testo visibile `frontend`, `backend`, `payload`, `runtime`, `json_api`, `Segreti protetti`, `Password e token`, `Modello conversazione` o `Modello ricerca documenti`. |
| `npm run typecheck` | OK | TypeScript verde dopo pagina Impostazioni full React. |
| `npm test` | OK | Contratti React aggiornati per `/impostazioni` e `/impostazioni-studio`. |
| `npm run build` | OK | Build Vite rigenerata con chunk `ImpostazioniPage`. |
| `node scripts/react-migration/audit-anti-mascheramento.mjs` | OK | Audit aggiornato a 53 route; impostazioni classificate con componente operativo reale. |
| `node scripts/react-migration/check-no-fake-react-full.mjs` | OK | Nessun full React fittizio dopo riallineamento manifest. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Gate route coerente: impostazioni full React, calendario/pagamenti legacy protetti. |
| `python -m pytest -q tests/test_react_shell.py -k "impostazioni or route_gate or blocco_telematico_studio_admin_resta_legacy_first or react_blocco_finale_studio_admin_completo" --tb=short` | OK | 7 test passati su shell, gate, impostazioni e AI Locale. |
| `python -m pytest -q tests/test_impostazioni_firma.py tests/test_web_bootstrap.py::test_impostazioni_pec_espone_controllo_local_signer_e_password_salvata tests/test_local_signer.py::test_tab_firma_mostra_download_local_signer_per_tutte_le_piattaforme --tb=short` | OK | 6 test passati su firma, PEC legacy fallback e Local Signer. |
| `python -m pytest -q tests/test_react_shell.py::test_impostazioni_react_ai_status_e_bootstrap_usano_runtime_locale tests/test_local_ai.py::test_impostazioni_template_contains_ai_locale_tab tests/test_local_ai.py::test_api_local_ai_bootstrap_aggiorna_cache_runtime_chat --tb=short` | OK | 3 test passati su AI Locale e bootstrap runtime. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.209.0. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test release/packaging passati dopo bump 2.209.0. |
| `npm run typecheck` | OK | Verde dopo correzione testi visibili Impostazioni e messaggio AI Locale. |
| `npm run build` | OK | Build Vite rigenerata dopo fix layout/testi Impostazioni; chunk corrente `ImpostazioniPage-C_-flQDe.js` e CSS `ImpostazioniPage-C9le0siY.css`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale --tb=short` | OK | 8 test passati: Docker locale multi-processo, layout tabs compatto, niente `Fonte/config_studio/json_api` nella card riepilogo, segreti tradotti in UI. |
| `npm test` | OK | Contratti React verdi dopo fix Impostazioni e reattivita' Docker locale. |
| `python -m pytest -q tests/test_react_shell.py -k "impostazioni or route_gate or blocco_telematico_studio_admin_resta_legacy_first or react_blocco_finale_studio_admin_completo" --tb=short` | OK | 7 test passati dopo i guardrail contro regressioni visive/testuali su Impostazioni. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8 test passati dopo aggiunta concorrenza Docker locale. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Build no-cache completata per app, scheduler e OCR con wheel `pct-studio-legale==2.209.0`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | App, scheduler, OCR e Redis healthy dopo rebuild; Nginx attivo. |
| `docker compose ps` | OK | Tutti i container runtime locali risultano in esecuzione; app, scheduler, OCR e Redis healthy. |
| `docker exec iusentra-app printenv WEB_CONCURRENCY/GUNICORN_THREADS/GUNICORN_WORKER_CONNECTIONS` | OK | Runtime locale confermato: 2 processi web, 4 thread, 500 connessioni worker. |
| `Invoke-WebRequest http://127.0.0.1:8080/api/pronto` | OK | 5 richieste consecutive: prima 153 ms, successive 13-14 ms, versione `2.209.0`. |
| Verifica browser `/impostazioni` desktop/tablet/mobile | OK | Schermata React renderizzata, sezioni presenti, nessun testo visibile `json_api`, `config_studio`, `Fonte`, `React operativo` o `bridge impostazioni`; tab compatti e form leggibile anche su mobile. |
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

## Tranche testi visibili e dettagli email React 2.214.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npm run typecheck` | OK | TypeScript confermato dopo guardia testi visibili, dettagli email React, Redazione Atti e bump 2.214.0. |
| `npm test` | OK | Contratti React verificati. |
| `npm run build` | OK | Build Vite 2.214.0 completata; asset React rigenerati in `web/static/react`. |
| `python -m py_compile web/blueprints/api_v1_react.py web/blueprints/email_client.py web/blueprints/email_ordinaria.py web/blueprints/react_shell.py web/bootstrap/react_route_gate.py web/services/react_email_bridge.py web/services/react_redazione_atti_bridge.py web/services/react_template_atti_bridge.py web/services/react_legal_intelligence_bridge.py web/services/react_giurisprudenza_bridge.py web/services/react_statistiche_bridge.py web/services/react_studio_module_bridge.py` | OK | Sintassi backend confermata sui bridge/blueprint toccati. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato su 2.214.0. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Route gate coerente. |
| `node scripts/react-migration/check-full-react-route-contract.mjs` | OK | Audit anti-mascheramento aggiornato, no fake full e contratto full React OK. |
| `node scripts/react-migration/check-no-fake-react-full.mjs` | OK | Nessuna route full mascherata. |
| `python -m pytest -q tests/test_email_client.py::test_email_dettaglio_visualizza_e_scarica_allegato_salvato tests/test_email_client.py::test_email_ordinaria_dettaglio_usa_repository_smtp_e_allegati_ordinari tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica tests/test_react_shell.py::test_statistiche_react_full_non_espone_fallback_legacy tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short` | OK | 6/6 passati: dettagli email, route React, statistiche e gate mirati. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati dopo bump versione. |
| Browser desktop full React, 3 blocchi route manifest | OK | Tutte le route `react_operational_full` esatte del manifest, esclusa `/admin/database` verificata separatamente, hanno `#root`, nessun overflow e nessun termine tecnico vietato visibile. |
| Browser Docker 2.214.0 desktop/mobile su pagine richieste | OK | `/redazione-atti`, `/template-atti`, `/statistiche`, `/ricerca-legale`, `/legal-intelligence/news`, `/giurisprudenza`, `/strumenti-legali`, `/strumenti-operativi`, `/deposito/checklist`, `/sito-studio/contatti`, dettagli PEC/email ordinaria e `/admin/database`: nessun overflow e nessun testo tecnico vietato. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con wheel `pct-studio-legale==2.214.0`. |
| `docker compose up -d app scheduler-worker ocr-worker` | OK | Servizi locali riavviati sulle immagini 2.214.0. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest -UseBasicParsing http://localhost:8080/api/pronto` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.214.0"}`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.214.0`. |

## Hotfix Sito Studio Contatti e Nav React 2026-05-09

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web/services/react_sito_studio_bridge.py web/blueprints/api_v1_react.py` | OK | Sintassi backend confermata dopo entrypoint pubblici, testi non tecnici e azioni protette dei contatti sito. |
| `npm run typecheck` | OK | TypeScript confermato dopo `entrypoints`, pagina contatti operativa anche a lista vuota e nuova gestione sidebar. |
| `npm run build` | OK | Build Vite 2.213.0 completata; asset React rigenerati in `web/static/react`. |
| `docker compose build app` | OK | Immagine locale app ricostruita con bridge e asset aggiornati. |
| `docker compose up -d --no-build app nginx` | OK | `iusentra-app` riavviata e healthy; `iusentra-nginx` attivo. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest http://127.0.0.1:8080/api/pronto` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.213.0"}`. |
| Browser reale `http://localhost:8080/sito-studio/contatti` | OK | Pagina React presente con `Contatti Sito Studio`, `Ingressi pubblici`, `Richieste contatto`, `Prenotazioni`, link `Apri modulo contatti` e `Apri prenotazione`; nessun overflow orizzontale e nessun testo tecnico vietato. |
| Browser reale nav `Studio -> Statistiche -> Fascicoli` | OK | Su `Statistiche` resta aperta solo la sezione `STUDIO`; aprendo `FASCICOLI` si chiude `STUDIO`; su `/fascicoli` resta aperta solo `FASCICOLI`. |

## Gate finali tranche Impostazioni React 2.209.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Build locale completa delle immagini 2.209.0 senza cache. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi riavviati sulle immagini appena costruite. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest http://127.0.0.1:8080/api/pronto` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.209.0"}`. |
| `docker exec iusentra-app printenv WEB_CONCURRENCY` | OK | Confermata capacita' locale: `2`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container: `2.209.0`. |

## Hotfix Impostazioni PEC React / Local Signer 2026-05-09

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npm run typecheck` | OK | TypeScript React confermato dopo spostamento `Verifica invio PEC` su Local Signer browser-locale. |
| `npm run test` | OK | Contratti React confermati dopo guardia anti-regressione PEC. |
| `python -m py_compile web/services/react_impostazioni_bridge.py web/blueprints/api_v1_react.py` | OK | Sintassi backend confermata dopo blocco del test SMTP PEC server-side. |
| `python -m pytest -q tests/test_impostazioni_pec_local_signer_react.py tests/test_email_client.py::test_impostazioni_payload_smtp_locale_usa_password_pec_salvata_del_tenant tests/test_local_signer.py::test_ui_pec_locale_auto_avvia_signer_e_mostra_pacchetto --tb=short` | OK | 4/4 passati: React usa Local Signer `/pec/smtp/test`, recupero password salvata tenant-aware e legacy locale confermati. |
| `python -m pytest -q tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale tests/test_react_shell.py::test_impostazioni_react_api_redige_segreti_e_salva_configurazioni --tb=short` | OK | 2/2 passati: pagina Impostazioni React e API configurazioni restano coerenti. |

## Hotfix Impostazioni AI Locale React / Local Signer 2026-05-09

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npm run typecheck` | OK | TypeScript React confermato dopo spostamento delle azioni AI Locale sul Local Signer del PC. |
| `npm run test` | OK | Contratti React confermati dopo guardia AI Locale. |
| `npm run build` | OK | Build Vite 2.211.0 completata; asset React rigenerati con la tab AI Locale aggiornata. |
## Catalogo PST / Preventivo guidato / Predeposito 2.215.4 - 2026-05-11

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall pct\pratiche_collegate_catalog.py pct\preventivi.py pct\fascicoli.py pct\deposito_guidato.py pct\practice_engine\validators.py pct\practice_engine\profiles.py web\services\react_fascicoli_bridge.py web\services\react_preventivi_bridge.py web\services\react_preventivo_wizard_bridge.py web\services\fascicoli_runtime.py web\blueprints\api_v1_react.py` | OK | Sintassi confermata dopo catalogo PST, propagazione wizard/preventivi/conferimenti e blocco predeposito CodiceOggetto. |
| `node frontend\scripts\check-react-contracts.mjs` | OK | Contratti React aggiornati: Preventivi, Preventivo guidato e Fascicoli usano il catalogo PST versionato e non hardcodano la tabella nel componente. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo import JSON catalogo e campi CodiceOggetto nel wizard. |
| `python -m pytest tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_create_crea_preventivo_reale_con_cliente_potenziale_e_clausola tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_rifiuta_codice_oggetto_non_ufficiale tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_genera_conferimento_solo_dopo_accettazione_cliente -q` | OK | 3/3 passati: il wizard salva un codice PST valido, rifiuta codice inventato e lo propaga al conferimento. |
| `python -m pytest tests/test_deposito_guidato.py::test_orchestratore_blocca_comparsa_senza_procura tests/test_deposito_guidato.py::test_api_validazione_deposito_restituisce_semaforo_e_consente_con_warning tests/test_deposito_guidato.py::test_orchestratore_blocca_deposito_pct_senza_codice_oggetto_pst -q` | OK | 3/3 passati: il predeposito usa il CodiceOggetto PST e blocca la busta se manca. |
| `python -m pytest tests/test_practice_engine_validators.py -q` | OK | 3/3 passati: validatori Regia/Practice Engine coerenti dopo il nuovo controllo `codice_oggetto_pst_valido`. |
| `npm --prefix frontend run build` | OK | Build Vite produzione completata con asset React aggiornati per Preventivi, Preventivo guidato, Fascicoli e catalogo PST versionato. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging/versione 2.215.4 sincronizzati. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness release confermate dopo bump 2.215.4. |
| `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_api_suite_usa_repository_reali --tb=short` | OK | Ponte Fascicoli confermato: il source preventivo propaga solo CodiceOggetto PST valido all'apertura fascicolo. |
| `git diff --check` | OK | Nessun errore di whitespace; presenti solo warning CRLF su file gia' gestiti da Git/runtime locale. |

| `node --check web/static/js/react-ai-local-guard.js` | OK | Sintassi della guardia browser-locale AI Locale confermata. |
| `python -m pytest -q tests/test_impostazioni_ai_locale_react.py tests/test_local_signer.py::test_local_ai_bridge_snapshot_windows_propone_installer_e_download_modello_automatico tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale --tb=short` | OK | 5/5 passati: AI Locale React passa dal Local Signer, gestisce Ollama/modelli mancanti, conferma il rilevamento prestazioni PC e conserva il contratto Impostazioni. |
| `python tools/sync_packaging_files.py --check` | OK | Versione 2.211.0 allineata tra sorgente Python, frontend, Docker e Railway. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py tests/test_web_bootstrap.py::test_lex_assistant_usa_componente_esterno_e_posizione_persistente --tb=short` | OK | 9/9 passati: packaging, readiness e shell React/Lex confermati dopo guard AI Locale. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con package `pct-studio-legale==2.211.0`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali avviati sulle immagini 2.211.0; app, scheduler, OCR e Redis healthy. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo durante la verifica. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 20` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.211.0"}`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.211.0`. |

## Hotfix Hetzner Backup / Esclusione Ollama 2026-05-09

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `ssh iusentra-hetzner "tar --use-compress-program=unzstd -tf /opt/iusentra/backups/iusentra-data-20260509_153532.tar.zst | grep -E '(^|/)ollama(/|$)' | head -20 || true"` | KO diagnosticato | Verifica reale: il backup vecchio conteneva ancora `intelligence/downloads/ollama` e path tenant, quindi non bastava escludere solo `./ollama`. |
| `bash -n deploy/hetzner/backup.sh` | OK | Sintassi script backup confermata dopo esclusioni obbligatorie e verifica anti-Ollama nell'archivio. |
| `python -m pytest -q tests/test_hetzner_backup_retention.py --tb=short` | OK | 3/3 passati: contratto retention, env esempio e test runtime con backup reale temporaneo senza percorsi Ollama. |
| `python tools/sync_packaging_files.py --check` | OK | Versione 2.212.0 allineata tra sorgente Python, frontend, Docker e Railway. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: packaging e readiness confermati dopo bump 2.212.0. |

## Gate finali tranche Controlli Atti e Strumenti React 2.210.0

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `node frontend/scripts/check-react-contracts.mjs` / `npm test` | OK | Contratti React aggiornati: `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` sono governati e non tornano legacy. |
| `node scripts/react-migration/check-route-gate.mjs` | OK | Route gate allineato: exact `/deposito/checklist` React, subpath checklist profondi ancora protetti. |
| `node scripts/react-migration/audit-anti-mascheramento.mjs` | OK | Audit aggiornato: 57 route censite, bridge legacy azzerati, 0 form POST HTML React. |
| `node scripts/react-migration/check-no-fake-react-full.mjs` | OK | Nessuna route full mascherata; rimosso form POST HTML dalla superficie `StudioModulePage`. |
| `node scripts/react-migration/run-legal-ui-checks.mjs` | OK | Check UI legale/responsive/anti-Bootstrap confermati dopo promozione route. |
| `npm run typecheck` | OK | TypeScript confermato dopo titolo `Controlli Atti` e pulizia testi telematici. |
| `npm run build` | OK | Build Vite 2.210.0 completata; asset rigenerati in `web/static/react`. |
| `node scripts/react-migration/run-full-react-migration.mjs` | OK | Audit, anti-mascheramento, route contract, no fake full e responsive workspace OK. |
| Visual smoke Chrome desktop/tablet/mobile | OK | `/deposito/checklist`, `/strumenti-legali`, `/strumenti-operativi` verificati a 1440x900, 834x1112 e 390x844: shell React, titoli, card e azioni visibili, nessun overflow e nessun testo tecnico vietato. |
| `python -m pytest -q tests/test_react_shell.py::test_react_blocco_finale_studio_admin_completo tests/test_react_shell.py::test_blocco_telematico_studio_admin_resta_legacy_first tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica tests/test_react_shell.py::test_route_ufficiali_superfici_telematiche_restano_moduli_operativi_legacy_e_checklist_react tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short` | OK | 7/7 passati dopo lo sblocco iniziale delle route. |
| `python -m pytest -q tests/test_react_shell.py::test_route_ufficiali_superfici_telematiche_restano_moduli_operativi_legacy_e_checklist_react tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short` | OK | 4/4 ripetuti solo per file toccati dopo la pulizia titolo/testi: route/API/gate/matrice confermati. |
| `python tools/sync_packaging_files.py --check` | OK | Coerenza packaging verificata dopo bump 2.210.0. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | Packaging e release readiness confermati per versione 2.210.0. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con package `pct-studio-legale==2.210.0`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini appena costruite. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 20` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.210.0"}`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.210.0`. |

## Hotfix isolamento tenant multi-studio 2026-05-10

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_storage_strategy.py -k "legacy_global_admin or context_invalid or carica_tenant or request_storage_runtime" --tb=short` | OK | 10/10 passati: guardie tenant, bootstrap request e profilo storage tenant-aware confermati dopo il blocco fail-closed. |
| `python -m pytest -q tests/test_storage_strategy.py -k "bootstrap_legacy_runtime_data or login_route_bootstraps_legacy_root_data_for_single_tenant_install" --tb=short` | OK | 3/3 passati: il bootstrap legacy resta attivo solo in mono-studio e viene bloccato quando sono presenti due tenant attivi. |
| `python -m pytest -q tests/test_storage_strategy.py --tb=short` | OK | 40/40 passati: login multi-studio, sessioni legacy, bootstrap tenant e runtime storage senza regressioni. |
| `python -m pytest -q tests/test_auth.py --tb=short` | OK | 38/38 passati: autenticazione, ruoli, superadmin e persistenza utenti confermati dopo il rafforzamento del contesto tenant. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging e metadati versione allineati dopo bump 2.214.8. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness confermate per 2.214.8. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con package `pct-studio-legale==2.214.8`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini 2.214.8. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 20` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.214.8"}`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.214.8`. |

## Hardening tenant-aware repository paths 2026-05-10

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall web/services/core_runtime.py web/services/react_impostazioni_calendar.py web/bootstrap/search_routes.py web/bootstrap/fascicoli_editor_routes.py web/template_atti.py web/services/pdp_penale_runtime.py tests/test_storage_strategy.py` | OK | Sintassi confermata dopo il passaggio dei loader e helper sensibili ai path tenant-aware/fail-closed. |
| `python -m pytest -q tests/test_storage_strategy.py -k "sensitive_repositories or tenant_context_is_missing or practice_engine_path or config_studio_e_smtp_dal_tenant_attivo or token_dir_uses_tenant_agenda_path or tenant_preventivi_repository"` | OK | 6/6 passati: backup, soggetti, indice ricerca, privacy, condivisioni, calendario impostazioni e preventivi usano i path del tenant attivo; se il contesto studio manca, i loader critici si bloccano per evitare letture cross-studio. |
| `python -m compileall web/bootstrap/admin_database_routes.py web/blueprints/api_v1_react.py web/services/admin_surfaces_shared.py web/services/system_health_surface.py tests/test_storage_strategy.py` | OK | Sintassi confermata dopo l'allineamento tenant-aware delle superfici admin database/salute sistema. |
| `python -m pytest -q tests/test_storage_strategy.py -k "admin_database_react_payload_uses_tenant_backup_dir or admin_shared_helpers_use_tenant_paths or sensitive_repositories or tenant_context_is_missing or token_dir_uses_tenant_agenda_path or tenant_preventivi_repository"` | OK | 6/6 passati: il bridge React `admin/database` usa il `BACKUP_DIR` del tenant attivo e gli helper admin condivisi (configurazione studio, backup, clienti) non leggono piu' la root globale quando esiste `g.data_paths`. |
| `python -m compileall web/services/topbar_operational.py web/blueprints/template_atti.py web/services/applicazioni_runtime.py web/blueprints/legal_intelligence.py tests/test_storage_strategy.py` | OK | Sintassi confermata dopo il passaggio tenant-aware anche su topbar, template atti, applicazioni e legal intelligence. |
| `python -m pytest -q tests/test_storage_strategy.py -k "topbar_cfg_value_blocks_when_tenant_context_is_missing or template_blueprint_uses_tenant_template_paths or applicazioni_runtime_uses_tenant_template_and_portale_paths or legal_intelligence_uses_tenant_daily_and_portale_paths or admin_database_react_payload_uses_tenant_backup_dir or admin_shared_helpers_use_tenant_paths or sensitive_repositories or tenant_context_is_missing or token_dir_uses_tenant_agenda_path or tenant_preventivi_repository"` | OK | 10/10 passati: anche topbar, blueprint template atti, runtime applicazioni e legal intelligence usano i path del tenant attivo o si bloccano se il contesto studio manca. |

## Hotfix email tenant fail-closed 2026-05-11

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_email_client.py -k "email_ordinaria_react_api_non_legge_fallback_globale_senza_tenant or email_ordinaria_bulk_action_non_cancella_fallback_globale_senza_tenant or email_ordinaria_route_react_api_e_repository_separato_da_pec or email_ordinaria_react_bulk_action_elimina_selezione_da_cestino"` | OK | 4/4 passati: riprodotto il rischio su API React ordinaria senza tenant, verificato blocco `tenant_context_required` e confermata la separazione ordinaria/PEC gia' esistente. |
| `python -m pytest -q tests/test_email_client.py -k "fallback_globale_senza_tenant or email_ordinaria_route_react_api_e_repository_separato_da_pec or email_ordinaria_react_bulk_action_elimina_selezione_da_cestino"` | OK | 5/5 passati: PEC ed email ordinaria non leggono piu' fallback globale in multi-studio senza tenant e la bulk delete non cancella dal repository globale. |
| `python -m compileall web/services/tenant_paths.py web/blueprints/email_client.py web/blueprints/email_ordinaria.py web/blueprints/api_v1_react.py web/services/mailbox_sync_runtime.py tests/test_email_client.py` | OK | Sintassi confermata dopo guardrail condiviso `TenantDataPathError` e chiusura fail-closed dei path mail tenant. |
| `python -m pytest -q tests/test_dashboard_mailbox_sync.py tests/test_email_client.py::test_email_ordinaria_sincronizza_usa_imap_smtp_dalle_impostazioni tests/test_email_client.py::test_email_blueprint_usa_storage_tenant_per_sincronizzazione --tb=short` | OK | 7/7 passati: sync PEC/ordinaria resta tenant-aware con contesto valido e non regredisce il bridge dashboard mailbox. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.215.1. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness confermate per 2.215.1. |
## PST Palmi RG 274/2026 / Local Signer 1.6.28 - 2026-05-11

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests\test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests\test_local_signer.py::test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import tests\test_local_signer.py::test_pst_ricerca_snapshot_batcha_ricerca_e_documenti_senza_preflight --tb=short` | OK | 3/3 passati: snapshot PST accorpa ricerca/profilo/catalogo, conserva `data_iscrizione`, e il download batch con `preflight_auth:false` non chiama il preflight preparatorio. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo il riuso sessione senza preflight nel download batch React. |
| `python -m compileall tools\local_signer.py tests\test_local_signer.py -q` | OK | Sintassi confermata per Local Signer 1.6.28 e test PST mirati. |
| `python tools\build_dist.py` | OK | Rigenerati `SetupLocalSigner-1.6.28.exe`, alias `SetupLocalSigner.exe` e installer macOS/Linux dopo i fix PST. |
| `npm --prefix frontend run build` | OK | Build Vite completata e asset React rigenerati. |
| Browser reale `http://127.0.0.1:8080/portali/pst/acquisizione`, Tribunale di Palmi RG 274/2026 | OK con issue funzionale catalogo | Una sola `/pst/ricerca-snapshot` per consultazione; metadati completi recuperati (`Oggetto: Usucapione`, procedimento, stato, iscrizione 07/03/2026); tab documenti con 6 elementi; download eseguito con sola `/pst/download-documenti-batch` senza `/pst/preflight-auth`. Traccia locale ignorata dal git in `artifacts/pst-import-traces/palmi-274-2026-20260511-165722.local.*`. |
| Docker locale `docker compose build app`, `docker compose up -d --no-build app`, `GET /api/pronto` | OK | Runtime locale aggiornato a `2.216.4`; app pronta e Local Signer `1.6.28` attivo su `127.0.0.1:27272`. |

## Hotfix CodiceOggettoPst apertura fascicolo / preventivi 2026-05-11

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m compileall pct/pratiche_collegate_catalog.py web/bootstrap/fascicoli_core_routes.py web/services/react_preventivi_bridge.py web/blueprints/api_v1_react.py tests/test_react_shell.py tests/test_react_preventivo_wizard_console.py -q` | OK | Sintassi confermata dopo risoluzione centralizzata del codice PST digitato e fallback da preventivo/conferimento. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo auto-selezione React del codice esatto nel catalogo PST. |
| `python -m pytest -q tests/test_react_shell.py::test_react_fascicolo_nuovo_form_collassabile_e_fascicolo_veloce tests/test_react_shell.py::test_post_nuovo_fascicolo_veloce_risolve_codice_oggetto_pst_digitato tests/test_react_shell.py::test_post_nuovo_fascicolo_da_preventivo_preserva_codice_oggetto_fino_a_deposito tests/test_react_preventivo_wizard_console.py::test_preventivo_react_nuovo_risolve_codice_digitato_nell_oggetto tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_codice_digitato_arriva_a_fascicolo_e_deposito tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_rifiuta_codice_oggetto_non_ufficiale --tb=short` | OK | 6/6 passati: `014001` digitato viene salvato su fascicolo veloce, preventivo normale, wizard, conferimento e fascicolo guidato con redirect al deposito assistito. |
| `npm --prefix frontend run build` | OK | Build Vite completata; rigenerati asset React con `CodiceOggettoPstSearch-Bpr8uDqj.js`. |
| `python -m pytest -q tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_create_crea_preventivo_reale_con_cliente_potenziale_e_clausola tests/test_react_preventivo_wizard_console.py::test_preventivo_wizard_react_genera_conferimento_solo_dopo_accettazione_cliente --tb=short` | OK | 2/2 passati: i casi storici con codice PST selezionato esplicitamente restano invariati. |
| `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_api_suite_usa_repository_reali --tb=short` | OK | Prefill da preventivo verso nuovo fascicolo mantiene `codiceOggettoPst=014001`. |
| `python -m pytest -q tests/test_react_preventivo_wizard_console.py --tb=short` | OK | 14/14 passati: console wizard preventivi completa confermata dopo il fix. |
| Browser reale `http://127.0.0.1:8080/fascicoli/nuovo` | OK | Dopo rebuild Docker locale, digitando `014001` in `Pratiche collegate` compare la selezione `014001 - Istanza sospensione dell'esecuzione ex art. 373 c.p.c.` e l'input nascosto `codice_oggetto_pst` vale `014001`. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump 2.216.6. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness confermate per 2.216.6. |
| `docker compose up -d --build app`; `curl.exe -sS --max-time 45 http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | App Docker locale ricostruita e healthy su `127.0.0.1:8080`; readiness OK con versione `2.216.6`. |

## Notifiche legali - modelli relata visibili/personalizzabili 2.216.9

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\notifiche_legali.py web\services\react_notifiche_legali_bridge.py web\blueprints\api_v1_react.py tests\test_notifiche_legali.py` | OK | Sintassi confermata dopo rendering modelli personalizzati, campi automatici e storage tenant-aware dei modelli relata. |
| `python -m pytest -q tests\test_notifiche_legali.py --tb=short` | OK | 9/9 passati: modelli standard, modello personalizzato Jinja, integrazione avvocato, API React e salvataggio modello personalizzato confermati. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo anteprima modello, editor personalizzato, palette campi e precompilazione deposito/cliente. |
| `node frontend\scripts\check-react-contracts.mjs` | OK | Contratti statici aggiornati per anteprima relata, nuovo modello su misura, campi automatici, endpoint salvataggio e percorsi deposito/cliente. |
| `npm --prefix frontend run test` | OK | Suite frontend confermata dopo aggiornamento contratti React. |
| `node scripts\react-migration\check-route-gate.mjs` | OK | Route gate invariato: `/notifiche-legali` resta governata come superficie React full. |
| `node scripts\react-migration\check-full-react-route-contract.mjs` | OK | Contratto full React confermato; audit anti-mascheramento aggiornato senza nuove violazioni. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump versione `2.216.9`. |
| `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 8/8 passati: coerenza packaging e readiness confermate per `2.216.9`. |
| `npm --prefix frontend run build` | OK | Build Vite completata in 6.27s; chunk lazy `NotificheLegaliPage-CONMJjZ1.js` 42.04 kB / 10.01 kB gzip, CSS 9.46 kB / 2.07 kB gzip. |
| `docker compose build app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite senza backup con package `pct-studio-legale==2.216.9`. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati sulle immagini appena costruite. |
| `docker compose ps` | OK | `iusentra-app`, `iusentra-scheduler`, `iusentra-ocr` e `iusentra-redis` healthy; `iusentra-nginx` attivo. |
| `Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8080/api/pronto -TimeoutSec 30` | OK | Readiness locale: `{"ok":true,"stato":"pronto","versione":"2.216.9"}`. |
| `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Versione runtime container locale: `2.216.9`. |
| Browser Chrome reale su `http://127.0.0.1:8080/notifiche-legali`, desktop 1440x1000 e mobile 390x844 | OK | Anteprima modello, nuovo modello su misura, inserimento campo `Avvocato notificante`, `Deposito prova notifica` e `Comunica al cliente` verificati; nessun overflow, nessun errore console e nessun testo tecnico vietato visibile. |

## PWA/Web Push notifiche dispositivo 2.217.2 - 2026-05-12

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\notifications\models.py pct\notifications\repository.py pct\notifications\service.py pct\notifications\web_push.py web\services\notifications_runtime.py web\blueprints\push_notifications.py web\services\topbar_operational.py` | OK | Sintassi confermata per dominio notifiche, runtime Flask, API push e integrazione topbar persistente. |
## Portali non-PST assistiti fail-closed 2.219.0 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\portal_integration_policy.py pct\portal_direct_guard.py pct\sigit.py pct\pat.py pct\pdp.py web\services\telematico_runtime.py web\services\pdp_penale_runtime.py web\bootstrap\portali_acquisizione_routes.py web\bootstrap\telematico_surface_wiring.py tools\local_signer.py tests\test_portali_payload_import_ui.py` | OK | Sintassi confermata per policy, guard, client produttivi, runtime assistito, route Flask, Local Signer e test. |
| `python -m pytest tests/test_portali_payload_import_ui.py -q` | OK | 27/27 passati: payload autorizzati PDP/PAT/PTT, policy fail-closed, manifest direct verified, guard client diretti, sessione assistita, deposito senza evidenza, import ricevute in Comunicazioni/Cancelleria, timeline/evidence pack e wizard PST/non-PST. |
| `python -m pytest tests/test_pdp_penale_web.py tests/test_deposito_guidato.py -q` | OK | 14/14 passati: workflow PDP esistente preservato, deposito guidato e parser PEC PDP riallineato alla finestra 60 giorni per test con data 2026-05-13. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump `2.219.0`. |
| `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q` | OK | 8/8 passati: packaging e readiness release confermate per `2.219.0`. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per frontend `2.219.0`. |
| `npm --prefix frontend run build` | OK | Build Vite completata per `iusentra-react-token-ui@2.219.0`; asset React rigenerati in `web/static/react`. |

| `python -m pytest -q tests/test_push_notifications.py tests/test_web_bootstrap.py::test_pwa_routes_and_error_handlers_restano_registrati --tb=short` | OK | 9/9 passati: repository, dedupe, subscription, revoca, public key senza config, subscribe valido/invalido, push mockato, endpoint scaduto e Service Worker/manifest root. |
| `python -m pytest -q tests/test_topbar_operational_api.py --tb=short` | OK | 2/2 passati: top bar e shape notifiche operative compatibili dopo persistenza. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per utility PWA/Web Push e UI `Impostazioni > Notifiche`. |
| `npm --prefix frontend run build` | OK | Build Vite completata e asset React rigenerati con pannello dispositivo e manifest PWA. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo aggiunta `pywebpush` e bump `2.217.2`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py tests/test_web_bootstrap.py::test_docker_compose_hetzner_allinea_email_ordinaria_e_ai_locale --tb=short` | OK | 9/9 passati: requisiti, versione, readiness e compose Hetzner restano coerenti. |
| `docker compose build --no-cache app scheduler-worker ocr-worker` | OK | Immagini locali ricostruite da zero con package `pct-studio-legale==2.217.2` e `pywebpush==2.3.0` installato. |
| `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx` | OK | Servizi locali riavviati senza backup; app, scheduler, OCR e Redis healthy, Nginx attivo. |
| `docker compose ps`; `Invoke-WebRequest http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Docker locale healthy; readiness `versione=2.217.2` e runtime container `2.217.2`. |
| Browser Playwright headless autenticato/impersonato su `http://127.0.0.1:8080/notifiche`, desktop/tablet/mobile | OK | Pannello `Notifiche su questo dispositivo`, nota iPhone/iPad e pulsanti attiva/disattiva/test visibili; `ServiceWorker`, `PushManager` e `Notification` presenti; nessun overflow e nessun termine tecnico vietato visibile. |

## Template Atti STRICT Cartabia/prefill/timbro 2.218.1 - 2026-05-12

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\template_atti_inventory.py pct\template_atti_unified_catalog.py pct\template_atti_prefill.py pct\template_cartabia_rules.py pct\studio_timbro.py web\blueprints\template_atti.py web\blueprints\api_v1_react.py` | OK | Sintassi confermata per inventario, catalogo unificato, prefill STRICT, fonti Cartabia, timbro top-left e nuove API. |
| `python scripts\template_atti\build_template_inventory.py` | OK | Report aggiornato: 1320 template canonici rilevati su 1320 attesi, scostamento 0; 4576 record di fonte ispezionati, 3256 copie eccedenti tracciate e conflitti fonte bloccati in revisione. |
| `python -m pytest tests/test_template_atti_inventory.py tests/test_template_atti_unified_catalog.py tests/test_template_atti_cartabia_strict.py tests/test_template_atti_prefill_strict.py tests/test_template_atti_timbro.py tests/test_template_atti_sources.py tests/test_template_atti_api_strict.py tests/test_template_atti_cartabia_prefill_timbro.py -q` | OK | 20/20 passati: inventario, strict mode, fonti ufficiali, prefill priorita/conflitti, timbro, API e regressioni 2.218.0. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo label UI `Compila con dati IUSENTRA`, metriche inventario e stato Cartabia non assolutistico. |

## Fascicolo Documenti e Cancelleria preview 2026-05-12

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\bootstrap\fascicoli_document_routes.py` | OK | Sintassi confermata dopo upload multiplo documenti e classificazione automatica/manuale. |
| `npm --prefix frontend run build` | OK | TypeScript e build Vite completati; rigenerati asset React per `FascicoliPage`. |
| `python -m pytest tests/test_react_shell.py -q -k "fascicoli_suite"` | OK | Suite mirata Fascicoli aggiornata: azioni documenti dentro Quadro intelligente AI, editor separato rimosso dalla UI, Comunicazioni / Cancelleria presenti. |
| `docker compose build app`; `docker compose up -d --no-build app`; `GET http://127.0.0.1:8080/api/pronto` | OK | Immagine locale ricostruita senza backup; container `iusentra-app` healthy e readiness 200. |
| Chrome headless autenticato su `http://127.0.0.1:8080/fascicoli/B6A03AE6`, desktop 1440x1100 e mobile 390x1000 | OK | Screenshot preview in `artifacts/react-migration/previews/*v3.png`; `Documenti e atti`, `Compilatore atti`, `Indice Lex`, `Elimina fascicolo` dentro Quadro intelligente AI; `Comunicazioni / Cancelleria` a due colonne; assenti `Catalogo portale`, `Depositi` e titolo separato editor; nessun overflow orizzontale e nessun errore console. |

## Template Atti compilatore React STRICT 2.218.2 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\template_atti_prefill.py pct\template_cartabia_rules.py pct\assistente_redazionale.py web\blueprints\template_atti.py web\blueprints\api_v1_react.py web\blueprints\react_shell.py web\bootstrap\react_route_gate.py` | OK | Sintassi confermata dopo compilatore React, label italiane, resolver prefill e route gate aggiornato. |
| `python -m pytest tests/test_template_atti_api_strict.py tests/test_template_atti_prefill_strict.py tests/test_assistente_redazionale.py -q` | OK | 9/9 passati: API catalogo/compilatore, prefill strict, redirect React sugli errori e label redazionali italiane. |
| `python -m pytest tests/test_template_atti_cartabia_strict.py tests/test_template_atti_cartabia_prefill_timbro.py tests/test_template_atti_unified_catalog.py tests/test_template_atti_sources.py -q` | OK | 16/16 passati: Cartabia strict, fonti ufficiali, timbro, catalogo unificato e regressioni sui 1320 template. |
| `python -m pytest tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica -q` | OK | La route `/template-atti/compila/<codice>` resta governata dalla shell React; la vista Jinja e' solo fallback `_legacy=1`. |
| `python scripts\template_atti\build_template_inventory.py` | OK | Inventario confermato: 1320 template canonici su 1320 attesi, scostamento 0; 4576 record fonte ispezionati e 3256 copie eccedenti tracciate. |
| `python tools\sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump `2.218.2`. |
| `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short -q` | OK | 8/8 passati: coerenza packaging e readiness release confermate per `2.218.2`. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo tipi e normalizzazione dati del compilatore Template Atti. |
| `npm --prefix frontend run build` | OK | Build Vite completata per `iusentra-react-token-ui@2.218.2`; asset React rigenerati in `web/static/react`. |
| Browser Playwright su `http://127.0.0.1:8099/template-atti/compila/AMM_RIC_001?id_cliente=0AD3517D&id_fascicolo=68756850` | OK | UI React visibile, vecchio compilatore assente, note mancanti in italiano, colore giallo leggibile (`rgb(74, 58, 0)` su `rgb(255, 248, 214)`), pannello Cartabia senza oggetti tecnici, CTA `Crea bozza e apri editor`, nessun errore console. Screenshot: `artifacts/react-migration/template-atti-compila-react.png`. |
| Hetzner `iusentra-hetzner`, branch `Codex/legal-electronic-filing-kIxcV` | OK | Deploy completato e riverificato sul branch finale: app, scheduler, OCR, Redis e Ollama healthy; `https://app.iusentra.it/api/pronto` risponde `versione=2.218.2`. Il primo backup e' stato rilanciato per file email cambiato durante `tar`; il secondo backup si e' completato prima del deploy. |

## PWA/Web Push configurazione operativa 2.218.4 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\notifications\web_push.py pct\notifications\generate_vapid.py pct\notifications\web_push_diagnostics.py web\blueprints\push_notifications.py tests\test_push_notifications.py tools\generate_vapid_keys.py` | OK | Sintassi confermata per diagnostica, generatore VAPID, endpoint push, test e CLI. |
| `bash -n deploy/hetzner/configure_web_push.sh`; `bash -n deploy/hetzner/verify_web_push.sh`; `bash -n deploy/hetzner/deploy.sh` | OK | Sintassi shell confermata, incluso opt-out `IUSENTRA_SKIP_BACKUP_CRON=1` per non aggiornare la pianificazione backup. |
| `python tools/generate_vapid_keys.py --subject mailto:admin@example.com`; `python tools/generate_vapid_keys.py --json` | OK | Generatore VAPID EC P-256 verificato: stampa solo stdout e non scrive file nel repository. Le chiavi generate durante il test non sono state salvate o committate. |
| `python -m pct.notifications.web_push_diagnostics` | OK diagnostico | Con ambiente non configurato esce con codice 1 e segnala variabili mancanti senza stampare private key; con variabili fittizie segnala `configured=true`. |
| `bash deploy/hetzner/configure_web_push.sh --env-file <temp>`; `bash deploy/hetzner/verify_web_push.sh --env-file <temp>` | OK | Smoke su file temporaneo fuori repository: abilita Web Push, non stampa private key, non crea backup e verifica host. File temporaneo rimosso. |
| `python -m pytest -q tests/test_push_notifications.py --tb=short` | OK | 14/14 passati: generazione chiavi, config/diagnostica, endpoint autenticato/non configurato/configurato, privacy private key, subscribe/test/revoca e script statici. |
| `npm --prefix frontend run test` | OK | Contratti React verificati dopo microcopy Notifiche. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per `pushNotifications.ts` e pannello Notifiche. |
| `npm --prefix frontend run build` | OK | Build Vite 2.218.4 completata e asset React rigenerati. |
| `python tools/sync_packaging_files.py --check` | OK | Packaging sincronizzato dopo bump `2.218.4`. |
| `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py tests/test_web_bootstrap.py::test_docker_compose_hetzner_allinea_email_ordinaria_e_ai_locale --tb=short` | OK | 9/9 passati: packaging, readiness release e compose Hetzner confermati. |
| `docker compose up -d --build --remove-orphans redis app scheduler-worker ocr-worker nginx`; `curl.exe -fsS http://127.0.0.1:8080/api/pronto` | OK | Docker locale ricostruito senza backup; app, scheduler, OCR, Redis e nginx attivi; `/api/pronto` risponde `versione=2.218.4`. |
| Chrome CDP headless su `http://127.0.0.1:8080/notifiche` con sessione tenant | OK | Desktop 2113 ms e mobile 2801 ms: shell React `Impostazioni` visibile, nessuna failure, nessun overflow e pannello Notifiche raggiungibile. |
| Hetzner CPX42: `bash deploy/hetzner/configure_web_push.sh`; `IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh`; `bash deploy/hetzner/verify_web_push.sh`; `curl -fsS https://app.iusentra.it/api/pronto` | OK | Deploy produzione completato senza eseguire backup e senza aggiornare cron backup; container app, Caddy, worker, Redis e Ollama healthy; `/api/pronto` 200 `versione=2.218.4`; Web Push `backend configured=true`. |
| Hetzner `/api/push/public-key` autenticato con sessione tenant | OK | Risposta `ok=true`, `configured=true`, `enabled=true`, public key presente; nessun campo `privateKey` e nessuna assegnazione `IUSENTRA_VAPID_PRIVATE_KEY=` nella risposta. |
| `git diff --check` | OK | Nessun errore whitespace. |

## Fase react 14 - release finale 2.235.0 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python tools\sync_packaging_files.py --check`; `python -c "import pct; print(pct.__version__)"` | OK | Packaging sincronizzato e runtime locale `2.235.0`. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | Link docs e comandi/path documentati validati. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `generate_app_v2_area_requirements.py --check`; `generate_app_v2_test_docs.py --check` | OK | Registry, requisiti area e test docs allineati. |
| `python scripts\validate_ui_coverage.py`; `node scripts\react-migration\check-route-gate.mjs`; `node frontend\scripts\check-app-v2-frontend.mjs`; `node frontend\scripts\check-react-contracts.mjs` | OK | Gate App V2/React: P0/P1=63, full UI tested=34, contratti verdi. |
| `python scripts\react-migration\generate_api_contracts.py --check`; `python scripts\validate_openapi.py docs\openapi.yaml`; `python scripts\verify_openapi_provider.py` | OK | OpenAPI valido; provider verification 182 auth-error, 27 success sample, 1 guardrail. |
| `python -m pytest -q tests\scripts\test_smoke_lib.py tests\scripts\test_smoke_app_v2_all.py tests\test_app_v2_test_plan_phase10.py tests\test_ci_cd_gates_phase11.py tests\test_openapi_contracts_phase6.py tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | 28/28 passati. |
| `python -m pytest -q tests\test_auth.py tests\test_backend_security_phase5.py tests\test_tenant_isolation_runtime.py tests\test_app_v2_feature_flags.py tests\test_app_v2_routing.py --tb=short` | OK | 70/70 passati su auth, backend security, tenant, feature flag e routing. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Test frontend, TypeScript e build Vite verdi; bundle principale invariato. |
| `python scripts\run_pytest_phases.py --suite release-readiness --timeout-minutes 10`; `--suite quality-overlay`; `--suite e2e-smoke`; `--suite coverage-critical` | OK | Shard CI locali verdi; coverage-critical pytest 313 test. |
| `python scripts\run_pytest_phases.py --suite coverage-critical --timeout-minutes 20 -- --cov=lex --cov=pct.auth --cov=pct.storage --cov=pct.storage_postgres --cov=pct.telematico_repository --cov=pct.telematico_workflow --cov-config=config/coverage-critical.ini --cov-report=term-missing --cov-fail-under=71` | OK | Coverage critica 71.61%, soglia 71 raggiunta; ResourceWarning SQLite non bloccanti. |
| `python -m pip_audit -r requirements.txt --format json --output %TEMP%\pip-audit-phase14.json`; `npm --prefix frontend audit --audit-level=critical --omit=dev --json` | OK | Nessuna vulnerabilita nota. |
| Secret scan high-confidence | OK | 5213 file esaminati, 0 finding. |
| `python tools\check_python_baseline.py`; `python tools\check_repo_governance.py`; Ruff; Ruff governed; mypy governed; flake8 | OK | Governance verde dopo estrazione moduli Fascicoli/Documenti e pattern mojibake Unicode-escaped. |
| `python -m pytest -q tests\test_web_bootstrap.py::test_file_critici_non_contengono_marker_di_mojibake ... tests\test_fascicolo_detail_ux.py --tb=short`; `python -m pytest -q tests\test_polisweb.py::test_route_importa_documenti_portale_salva_documenti_e_deposito ... --tb=short` | OK | 12/12 e 6/6 passati sul refactor finale. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `/api/pronto`; runtime/label immagine | OK | Docker locale finale post-refactor healthy; readiness `2.235.0`, container runtime e label `2.235.0`. |
| `python scripts\smoke_app_v2_all.py --subset contracts --read-only --base-url http://127.0.0.1:8080`; `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url http://127.0.0.1:8080` | OK | Contracts PASS=7 FAIL=0; post-deploy PASS=76 FAIL=0 SKIP=1 BLOCKED=6. |

## Audit probatorio WORM 2.221.0 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests/test_audit_canonical.py tests/test_audit_hashing.py tests/test_audit_signing.py tests/test_audit_worm.py tests/test_audit_emit.py tests/test_audit_chain.py tests/test_audit_merkle.py tests/test_audit_snapshot.py tests/test_audit_proof.py tests/test_audit_bundle.py tests/test_audit_routes.py tests/test_audit_integrations.py -q` | OK | 31/31 passati: canonicalizzazione JCS, hash, firma JWS/CAdES adapter, WORM/Object Lock double, emit WORM-before-index, catena, Merkle, snapshot, proof, bundle, route `/audit` e alias `/registro`, integrazioni atti/PEC/depositi/ricevute. |
| `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_bridge_usa_repository_reali tests/test_react_shell.py::test_react_fascicoli_detail_nav_lessico_e_referente_studio_presidiati tests/test_react_shell.py::test_react_fascicoli_api_suite_usa_repository_reali tests/test_react_shell.py::test_react_fascicoli_bridge_formatta_date_e_referenti_visibili` | OK | 4/4 passati: bridge Fascicoli e dettaglio React restano su dati reali dopo tab Audit e link `/registro/bundle/fascicolo/<id>`. |
| `python -m compileall -q audit web\services\react_fascicoli_bridge.py` | OK | Sintassi confermata dopo alias Registro e fail-closed tenant nel bridge Fascicoli. |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | TypeScript, contratti React e build Vite confermati dopo tab Audit nel fascicolo e guardia testo aggiornata. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | Packaging, requisiti e readiness release confermati dopo bump `2.221.0` e dipendenze Alembic/boto3. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `/api/pronto` locale | OK | Immagini locali ricostruite da zero con `pct-studio-legale==2.221.0`; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.221.0`. |

## Fase react 6 - OpenAPI e provider verification 2.227.0 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile scripts\react-migration\generate_api_contracts.py scripts\validate_openapi.py scripts\verify_openapi_provider.py tests\test_openapi_contracts_phase6.py web\blueprints\api_v1_react.py` | OK | Sintassi confermata per generatore contratti, validatore OpenAPI, provider verification, test fase 6 e risposta 401 normalizzata. |
| `python scripts\react-migration\generate_api_contracts.py --check` | OK | `docs/openapi.yaml`, `docs/api-endpoint-contract-map.md` e `docs/api-contracts.md` allineati e deterministici. |
| `python scripts\validate_openapi.py docs\openapi.yaml` | OK | OpenAPI 3.0.3 valido: componenti, response/error schema, path param, RBAC, tenant scope e status P0/P1 verificati. |
| `python scripts\verify_openapi_provider.py` | OK | Provider verification con Flask test client: 182 endpoint auth-error 401 reali, 27 endpoint P0/P1 con 200 autenticato, guardrail `tenant_id` 400 `backend_security_control_param`. |
| `python -m pytest -q tests\test_openapi_contracts_phase6.py --tb=short` | OK | 5/5 passati: generazione, validazione OpenAPI, copertura P0/P1, provider verification e error schema reale/normalizzato. |
| `python -m pytest -q tests\test_backend_security_phase5.py tests\test_feature_flags.py tests\test_app_v2_routing.py --tb=short` | OK | 24/24 passati: guardrail fase 5, feature flag e routing App V2 restano compatibili dopo normalizzazione 401 e contratti fase 6. |
| `python -m pytest -q tests\test_react_shell.py::test_react_api_bridge_richiede_autenticazione tests\test_react_shell.py::test_react_api_utenti_nuovo_crea_utente_json_senza_password tests\test_react_shell.py::test_react_api_utenti_nuovo_valida_campi_e_permesso --tb=short` | OK | 3/3 passati: auth API React e flusso Utenti restano compatibili con il nuovo formato 401. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging, versione e readiness release confermati dopo bump `2.227.0`; 8/8 passati. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | Contratti React, route gate, TypeScript, test frontend e build Vite 2.227.0 verdi; build 5.57s, bundle principale invariato `index-C-BWXjrL.js` 440.64 kB / 130.82 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `/api/pronto` locale | OK | Build locale no-cache e riavvio completati; wheel `pct-studio-legale==2.227.0`, app/scheduler/OCR/Redis healthy, readiness locale `versione=2.227.0` e runtime container `2.227.0`. |
| `python scripts\smoke_backend_security.py --base-url http://127.0.0.1:8080` | OK | Smoke post-Docker locale: readiness 2.227.0, API sensibili anonime 401 controllato; verifica autenticata `tenant_id` saltata senza `IUSENTRA_SMOKE_API_KEY`. |

## Fase react 5 - Sicurezza backend endpoint 2.226.0 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\backend_security.py web\blueprints\api_v1_react.py scripts\react-migration\generate_backend_security_map.py scripts\smoke_backend_security.py tests\test_backend_security_phase5.py` | OK | Sintassi confermata per guardrail backend, blueprint API React, generatore mappa, smoke e test fase 5. |
| `python scripts\react-migration\generate_backend_security_map.py --check` | OK | `docs/backend-endpoint-security-map.md` allineato e deterministico. |
| `python -m pytest -q tests\test_backend_security_phase5.py tests\test_tenant_isolation_runtime.py tests\test_feature_flags.py tests\test_app_v2_routing.py --tb=short` | OK | 33/33 passati: 401 anonimo, 400 parametri tenant/studio forzati, filtri leciti, auth decorator, isolamento tenant, feature flag e routing fase 4. |
| `python -m pytest -q tests\test_react_shell.py::test_react_api_bridge_richiede_autenticazione tests\test_react_shell.py::test_react_api_utenti_nuovo_crea_utente_json_senza_password tests\test_react_shell.py::test_react_api_utenti_nuovo_valida_campi_e_permesso tests\test_react_shell.py::test_impostazioni_react_api_redige_segreti_e_salva_configurazioni tests\test_react_shell.py::test_impostazioni_react_ai_status_e_bootstrap_usano_runtime_locale tests\test_react_shell.py::test_react_fascicoli_api_suite_richiede_auth tests\test_react_shell.py::test_react_fascicoli_api_suite_usa_repository_reali tests\test_fascicoli_pagination.py tests\test_email_client.py::test_email_route_ufficiale_serve_react_e_api_distingue_inviati_cestino tests\test_email_client.py::test_email_ordinaria_route_react_api_e_repository_separato_da_pec --tb=short` | OK | 15/15 passati: regressione su Impostazioni, Utenti, Fascicoli, paginazione ed Email PEC/ordinaria dopo il guardrail centrale. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging, versione e readiness release confermati dopo bump `2.226.0`. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | Contratti React, route gate, TypeScript, test frontend e build Vite 2.226.0 verdi; build 6.32s, bundle principale invariato `index-C-BWXjrL.js` 440.64 kB / 130.82 kB gzip, CSS principale invariato 121.77 kB / 22.33 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `/api/pronto` locale | OK | Build locale no-cache e riavvio completati; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.226.0` e runtime container `2.226.0`. |
| `python scripts\smoke_backend_security.py --base-url http://127.0.0.1:8080` | OK | `/api/pronto` 200 `versione=2.226.0`; le API sensibili anonime rispondono 401 controllato. La prova autenticata di blocco `tenant_id` resta saltata senza `IUSENTRA_SMOKE_API_KEY`, come documentato negli open issues. |

## Portali assistiti PDP/PAT/PTT dentro IUSENTRA - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web/bootstrap/portali_acquisizione_routes.py web/bootstrap/telematico_surface_wiring.py web/services/telematico_runtime.py web/services/react_telematico_bridge.py` | OK | Sintassi confermata dopo nuovo endpoint `importa-file` per i canali assistiti e bridge React senza link esterno primario. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo il wizard React PDP/PAT/PTT avviato da Step 1 e import assistito senza anteprima fittizia. |
| `python -m pytest -q tests/test_portali_payload_import_ui.py --tb=short` | OK | 30/30 passati: payload autorizzati invariati, sessioni assistite e nuovo import file/ricevute nel fascicolo interno per PDP, PAT e PTT. |
| `python -m pytest -q tests/test_react_shell.py::test_route_ufficiali_superfici_telematiche_esatte_servono_react_con_vista_classica_tecnica tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale --tb=short` | OK | 2/2 passati: route ufficiali React e payload API reale restano coerenti; `officialHref` non viene esposto come link esterno per PDP/PAT/PTT. |
| `npm --prefix frontend run build` | OK | Build Vite completata; rigenerati asset React, incluso `TelematicoSurfacePage-D7MePmJF.js` e `TelematicoSurfacePage-fOf1Ew_N.css`. |
| Browser reale su server test autenticato `127.0.0.1:8093` per `/portali/pdp/acquisizione`, `/portali/pat/acquisizione`, `/portali/ptt/acquisizione` | OK | PDP/PAT/PTT partono da `Step 1/7`, mostrano `Sessione IUSENTRA`, `Apri sessione IUSENTRA` e `Raccogli file nel software`; non mostrano `Portale ufficiale` come CTA primaria ne' `Endpoint browser`. |

## Percorso PST unico e ingressi SIGP storici - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo rimozione degli ingressi separati SIGP e testi visibili riallineati al percorso PST unico. |
| `python -m pytest -q tests/test_polisweb.py::test_acquisizione_wizard_pst_preview_error_usa_fallback_assistito tests/test_sigp_integration.py --tb=short` | OK | 8/8 passati: wizard PST classico senza ritorno a `PST/SIGP` e contratto modulo storico SIGP aggiornato a `Percorso PST unico`. |
| `npm --prefix frontend run build` | OK | Build Vite completata con manifest e asset React coerenti dopo l'ultima rigenerazione. |

## Notifiche legali L53 e registry procedimenti 2.236.0 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m ruff check legal_deposit pct/notifica.py pct/notifiche_legali.py web/blueprints/api_v1_react.py web/services/react_notifiche_legali_bridge.py tests/test_notifiche_legali.py tests/test_telematic_registry_fail_closed.py tests/legal_deposit/test_penal_deposit_rules.py` | OK | Ruff verde sui moduli modificati per notifiche PEC L53, registry procedimenti, policy deposito e test. |
| `python -m compileall -q legal_deposit pct web/blueprints/api_v1_react.py web/services/react_notifiche_legali_bridge.py` | OK | Sintassi Python confermata dopo fail-closed canali/procedimenti, modulo legacy `pct/notifica.py` disattivato e workflow PST area web. |
| `python -m pytest tests/test_notifiche_legali.py tests/test_telematic_registry_fail_closed.py tests/legal_deposit/test_penal_deposit_rules.py -q` | OK | 44/44 passati: oggetto L53, ricevuta completa, attestazioni, cliente non-notifica, PTT 10MB/50MB/50 file/100 caratteri, SICID/SIECIC/SIGP/UNEP/PAT/PTT/PDP e evidence pack. |
| `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q` | OK | 8/8 passati dopo bump versione `2.236.0`. |
| `npm --prefix frontend run typecheck`; `node frontend/scripts/check-react-contracts.mjs`; `npm --prefix frontend test`; `npm --prefix frontend run build`; `node scripts/react-migration/check-route-gate.mjs` | OK | TypeScript, contratti React, test frontend, build Vite e route gate verdi; `NotificheLegaliPage` ora seleziona piu' documenti e li riporta automaticamente nell'elenco. |
| Browser reale su runtime Flask isolato `127.0.0.1:8091/notifiche-legali` | OK | Pratica con due documenti: multi-selezione visibile, entrambi i documenti selezionati appaiono nell'elenco allegati, nessun testo tecnico vietato. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto` | OK | Docker locale no-cache healthy; readiness locale `versione=2.236.0`. |
| `python scripts/smoke_app_v2_all.py --suite health --read-only --base-url http://127.0.0.1:8080 --timeout 20`; `python scripts/smoke_app_v2_all.py --suite notifications --read-only --base-url http://127.0.0.1:8080 --timeout 20` | OK | Smoke locale read-only: health PASS=2; notifications PASS=3 SKIP=1 per invio reale escluso. |
| `ssh iusentra-hetzner "cd /opt/iusentra/repo && IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh"` | OK | Deploy Hetzner sul commit corrente del branch `Codex/legal-electronic-filing-kIxcV`; backup non eseguito e cron backup non aggiornato per richiesta utente `no backup`. |
| `GET https://app.iusentra.it/api/pronto`; `python scripts/smoke_app_v2_all.py --suite health --read-only --base-url https://app.iusentra.it --timeout 20`; `python scripts/smoke_app_v2_all.py --suite notifications --read-only --base-url https://app.iusentra.it --timeout 20` | OK | Produzione healthy: `/api/pronto` 200 `versione=2.236.0`; smoke health PASS=2; smoke notifications PASS=3 SKIP=1. |

## Profilo, agenda, email, portali e scadenziario 2.236.3 - 2026-05-14

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\bootstrap\auth_management_routes.py web\bootstrap\clienti_routes.py web\blueprints\api_v1_react.py web\blueprints\email_client.py web\blueprints\email_ordinaria.py web\bootstrap\scadenziario_routes.py web\services\react_scadenziario_bridge.py web\services\react_telematico_bridge.py tests\test_react_shell.py` | OK | Sintassi confermata per profilo React, autocomplete agenda, compose email, scadenziario e bridge telematico. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run test` | OK | Contratti React, route gate, TypeScript e coverage UI fase 9 verdi dopo nuove route `/profilo` e `/agenda/importa`, autofill agenda, email allegati e azioni scadenziario. |
| `python -m pytest -q tests\test_react_shell.py::test_profilo_e_import_agenda_sono_route_react_operativa tests\test_react_shell.py::test_react_autocomplete_clienti_usa_payload_minimale_sicuro --tb=short` | OK | 2/2 passati: `/profilo` e `/agenda/importa` sono route React e l'autocomplete clienti mantiene payload sicuro arricchito. |
| `python -m pytest -q tests\test_email_client.py::test_email_ordinaria_scrivi_restera_separata_da_email_pec --tb=short`; `python -m pytest -q tests\test_react_scadenziario_additions.py --tb=short`; `python -m pytest -q tests\test_react_shell.py::test_react_superfici_telematiche_api_payload_reale --tb=short` | OK | Email ordinaria/PEC restano separate, scadenziario React 3/3 verde e payload telematico reale confermato. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.236.3`. |
| `npm --prefix frontend run build` | OK | Build Vite 2.236.3 completata in 6.85s; main JS `index-De_Z6EEb.js` 445.63 kB / 131.89 kB gzip, CSS `index-Bafxecf8.css` 121.77 kB / 22.33 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Docker locale no-cache healthy; readiness locale `versione=2.236.3` e runtime container `2.236.3`. |
| Playwright/CDP locale autenticato su `/profilo`, `/agenda/importa`, `/agenda/nuovo`, `/clienti`, `/soggetti`, `/fascicoli`, `/portali/pdp/acquisizione`, `/pat`, `/sigit`, `/email-ordinaria/scrivi`, `/email/scrivi`, `/scadenziario`, `/impostazioni?tab=ai` | OK | Profilo React visibile; Agenda importa operativa; ricerca cliente Marco senza error boundary e prefill `MSCMRC75E26L063G`, `RG 12/2026`, `palmi`, `Antonella Mammola`; scrollbar superiori presenti; link `Portale ufficiale` visibile; allegati multipli e cliente email visibili; scadenziario senza `repository_reali` e dettaglio attivo; AI locale non resta su `Stato: non verificato`. |
| Playwright/CDP viewport 834x1112 e 390x844 su `/agenda/nuovo` | OK | Nessun overflow orizzontale, contenuto `Nuovo appuntamento` presente e form responsive dopo le modifiche autocomplete/autofill. |
| `ssh iusentra-hetzner "cd /opt/iusentra/repo && BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh"`; `GET https://app.iusentra.it/api/pronto`; `docker compose ... ps`; `docker compose ... exec -T app python -c "import pct; print(pct.__version__)"` | OK | Deploy Hetzner CPX42 completato per `2.236.3`; branch server `Codex/legal-electronic-filing-kIxcV`, container app/scheduler/OCR/Redis/Caddy/Ollama healthy o running, `/api/pronto` pubblico 200 `versione=2.236.3`, runtime container `2.236.3`. |

## Audit UI/UX severo 2.236.4 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\blueprints\admin.py pct\tenant.py web\blueprints\api_v1_react.py` | OK | Sintassi confermata dopo lazy storage admin, manifest storage opzionale senza reconcile e API JSON `/agenda/importa`. |
| `node --check web\static\js\impostazioni-ai.js`; `node --check web\static\js\pct-lex-assistant.js`; `node --check scripts\react-migration\visual-load-audit.mjs` | OK | Testi visibili AI/Lex ripuliti da termini tecnici e audit visuale parametrico per label versione. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo dialog focus trap, bottoni icona accessibili, tabella mobile e submit React agenda import. |
| `npm --prefix frontend run test` | OK | Contratti React, App V2 frontend e UI coverage fase 9 confermati dopo la patch UI. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs`; `node scripts\react-migration\check-full-react-route-contract.mjs` | OK | Contratti React, route gate, anti-mascheramento e full React contract verdi. |
| `npm --prefix frontend run build` | OK | Build Vite 2.236.4 completata in 6.52s; main JS `index-o-tks_dT.js` 445.70 kB / 131.88 kB gzip, CSS `index-BMXxk8lG.css` 123.50 kB / 22.64 kB gzip. |
| `python -m pytest -q tests\test_react_shell.py::test_profilo_e_import_agenda_sono_route_react_operativa tests\test_tenant_admin_legacy.py::test_superadmin_ha_superficie_piattaforma_separata_dagli_utenti_studio tests\test_tenant_admin_legacy.py::test_admin_dettaglio_studio_mostra_storage_root_canonico_e_non_slug_legacy tests\test_storage_strategy.py::test_gestione_tenant_provision_storage_backend_creates_sqlite_and_manifest tests\test_storage_strategy.py::test_storage_manifest_mostra_postgresql_attivo_per_domini_core --tb=short` | OK | 5/5 passati: route profilo/import agenda, superfici admin tenant e manifest storage restano compatibili. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.236.4`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Docker locale no-cache healthy; app, scheduler, OCR e Redis healthy; readiness locale 47 ms circa con `versione=2.236.4`; runtime container `2.236.4`. |
| HTTP autenticato admin locale su `/admin/studi/antonella-mammola`, `/admin/api/studi/antonella-mammola/storage`, `/admin/studi/antonella-mammola/database` | OK | Dettaglio studio 48 ms circa, configurazione archivio 30 ms circa, conteggio spazio entro budget parziale di 2s; il timeout worker precedente e' risolto. |
| Chrome CDP autenticato `artifacts/react-migration/visual-2.236.4/visual-load-audit.md` | OK | 46 route verificate in desktop e mobile, 92/92 controlli OK: zero login redirect, zero loading bloccati, zero form POST HTML nel perimetro React, zero testo tecnico vietato, zero overflow orizzontale. Picco caldo osservato: `/statistiche` mobile 4421 ms. |

## Rifinitura audit UI/UX 2.236.5 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo rifinitura testi Ricerca Studio, Controlli Atti e CSS ricerca. |
| `node --check scripts\react-migration\visual-load-audit.mjs`; `npm --prefix frontend run test` | OK | Script audit valido; contratti React, App V2 frontend e UI coverage fase 9 verdi dopo la correzione degli avvisi azioni/collegamenti. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs`; `node scripts\react-migration\check-full-react-route-contract.mjs` | OK | Contratti React, route gate, anti-mascheramento e no-fake React confermati dopo la patch. |
| `python tools\sync_packaging_files.py --check`; `python -m py_compile pct\__init__.py`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging/versione `2.236.5` sincronizzati; readiness release 8/8 passata. |
| `npm --prefix frontend run build` | OK | Build Vite 2.236.5 completata in 6.79s; main JS `index-PRcu5jld.js` 445.70 kB / 131.89 kB gzip, CSS `index-vkwJu0dF.css` 123.48 kB / 22.60 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Docker locale no-cache ricostruito e riavviato; app/scheduler/OCR/Redis healthy; readiness locale 200 `versione=2.236.5`; runtime container `2.236.5`. |
| Chrome CDP autenticato `artifacts/react-migration/visual-2.236.5/visual-load-audit.md`; retry mirato `artifacts/react-migration/visual-2.236.5-soggetti-nuovo/visual-load-audit.md` | OK | Audit completo: 91/92 controlli OK, zero avvisi, zero overflow e zero testo tecnico vietato; unico timeout CDP isolato su `/soggetti/nuovo` mobile. Retry mirato della stessa route: OK in 761 ms con H1 `Nuovo Soggetto`. |
| `ssh iusentra-hetzner "cd /opt/iusentra/repo && IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh"` | OK | Deploy Hetzner CPX42 eseguito su richiesta `no backup`: `backup.sh` non eseguito e cron backup non aggiornato. |
| `GET https://app.iusentra.it/api/pronto`; `docker compose ... ps`; `docker compose ... exec -T app python -c 'import pct; print(pct.__version__)'`; manifest React pubblico | OK | Produzione healthy: `/api/pronto` 200 `versione=2.236.5`, app/scheduler/OCR/Redis healthy, runtime container `2.236.5`, manifest pubblico con asset `index-PRcu5jld.js`, `RicercaStudioPage-Co-rTlBG.js` e `TelematicoSurfacePage-DtdIUca0.js`. |

## Strumenti Forensi operativi 2.236.6 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\react_studio_module_bridge.py web\blueprints\api_v1_react.py` | OK | Sintassi backend confermata dopo ripristino catalogo strumenti, form dinamici e endpoint JSON `/api/v1/ui/strumenti-legali/<tool_id>`. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo estensione runtime campi, multiselect, submit JSON e risultati in pagina. |
| `python -m pytest -q tests\test_react_shell.py::test_react_strumenti_legali_catalogo_form_e_calcolo_json tests\test_react_shell.py::test_react_studio_module_frontend_supporta_rotte_profonde_e_form_reali --tb=short` | OK | 2/2 passati: catalogo con oltre 30 funzioni, preset mora commerciale, form reale e risposta JSON con metriche/tabelle. |
| `python -m pytest -q tests\test_strumenti_legali.py --tb=short` | OK | 21/21 passati: dominio storico degli strumenti legali preservato. |
| `python -m py_compile web\blueprints\sigp_redirects.py`; `python -m pytest -q tests\test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative tests\test_react_shell.py::test_react_studio_module_card_e_runtime_non_sono_decorativi tests\test_react_shell.py::test_react_studio_module_card_href_interni_raggiungibili --tb=short` | OK | 3/3 passati dopo correzione redirect `/sigp/` senza 308 canonico. |
| `python -m pytest -q tests\test_react_shell.py::test_react_strumenti_legali_catalogo_form_e_calcolo_json tests\test_sigp_sync.py::test_sigp_sync_non_esposto_in_menu_e_download_senza_preflight_pin --tb=short` | OK | 2/2 passati: regressione strumenti e presidio SIGP confermati insieme. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs`; `node scripts\react-migration\check-full-react-route-contract.mjs` | OK | Contratti React, route gate, anti-mascheramento e no-fake React verdi dopo promozione funzionale di `/strumenti-legali`. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.236.6`. |
| `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | Test frontend e build Vite verdi; asset React rigenerati con `StudioModulePage` aggiornato. |
| Browser in-app autenticato Docker locale su `/strumenti-legali/?tool=interessi&app=calcolo_interessi_di_mora` | OK | Catalogo `Strumenti Forensi` visibile, comando `Calcola interessi` esegue il submit e mostra risultato con `Interessi maturati` e `Segmenti di calcolo`; desktop/tablet/mobile confermati, nessun testo tecnico vietato. |
| Browser in-app baseline caricamento Docker locale su `/strumenti-legali/?tool=interessi&app=calcolo_interessi_di_mora` | OK | 3 run desktop: DOMContentLoaded 1441/1119/1089 ms, form visibile 1720/1394/1401 ms, comando visibile 2681/1662/2748 ms. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto` | OK | Docker locale no-cache 2.236.6 healthy; app/scheduler/OCR healthy e readiness locale 200 `versione=2.236.6`. |
| `python -m pytest tests\test_lex_legal_source_engine.py -q` | OK | 13/13 passati dopo attivazione operativa locale del Legal Source Engine: registry, policy, auto-populate, retriever JSONL, tool interni e dogfood senza rete. |
| `python -m compileall -q lex\legal_sources tests\test_lex_legal_source_engine.py`; `python -m ruff check lex\legal_sources tests\test_lex_legal_source_engine.py` | OK | Sintassi e lint verdi per il modulo Legal Source Engine operativo. |
| `python -m lex.legal_sources.populate --activate --populate --force --json` | OK | Motore attivato localmente senza backup e senza rete: runtime config ignorata, 15 source-card citabili scritte in `indexes/legal_sources/`, report in `artifacts/legal_sources/reports/`. |
| `python -m pytest tests\test_lex_legal_source_engine.py -q`; `python -m compileall -q lex\legal_sources tests\test_lex_legal_source_engine.py`; `python -m ruff check lex\legal_sources tests\test_lex_legal_source_engine.py` | OK | Verifiche ripetute dopo risoluzione dei default runtime sotto `PCT_DATA_ROOT` per server/container. |

## Legal Skills Engine 2.237.0 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile lex\legal_skills\models.py lex\legal_skills\parser.py lex\legal_skills\__init__.py tests\test_legal_skills_engine.py` | OK | Sintassi confermata per modelli, parser e test Legal Skills. |
| `python -m pytest tests\test_legal_skills_engine.py -q` | OK | 8/8 passati: registry seed pack, frontmatter, profilo tenant-aware, esecuzione workflow, trust layer, export/review, API e route React `/legal-skills`. |
| `node frontend\scripts\check-legal-skills.mjs` | OK | Gate statico frontend Legal Skills verde: route, feature flag, pagine e componenti obbligatori presenti. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato per la nuova superficie React Legal Skills e gli hook API. |
| `npm --prefix frontend run test` | OK | Contratti React, App V2 frontend, check Legal Skills e UI coverage verdi; P0/P1 68, full 47. |
| `python scripts\validate_openapi.py docs\openapi.yaml` | OK | OpenAPI valido dopo l'aggiunta degli endpoint `/api/v1/legal-skills/*`. |
| `python scripts\verify_openapi_provider.py` | OK | Provider verification: `auth-error=195`, `success=27`, `backend-security=1`. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | Documentazione aggiornata: 21 documenti e 157 link verificati; 155 comandi/percorsi validati. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.237.0`. |
| `npm --prefix frontend run build` | OK | Build Vite finale completata in 6.47s; main JS `index-D8oQCFWT.js` 450.88 kB / 133.35 kB gzip, CSS `index-U797z5OV.css` 124.48 kB / 22.85 kB gzip; chunk Legal Skills lazy separati. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate app scheduler-worker ocr-worker nginx`; readiness locale | OK | Docker locale no-cache su `2.237.0`; app/scheduler/OCR/Redis healthy, nginx running, container app `pct.__version__ == 2.237.0`. `/api/pronto` hot 18 ms circa dopo warm-up iniziale. |
| Chrome CDP autenticato `artifacts/react-migration/visual-2.237.0-legal-skills/visual-load-audit.md` | OK | `/legal-skills` desktop 1736 ms e mobile 2728 ms a contenuto React visibile; zero failure, zero warning, nessun overflow, console error o testo tecnico vietato. |

## AI Legal fase 2 finale 2.237.1 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\__init__.py tests\test_legal_skills_engine.py`; `python -m pytest tests\test_legal_skills_engine.py -q` | OK | Versione `2.237.1` e test Legal Skills confermati: 8/8 passati. |
| `node frontend\scripts\check-legal-skills.mjs` | OK | Gate esteso per le pagine richieste da fase 2: `PracticeProfilePage`, `ColdStartInterviewPage`, `LegalSkillRunPage`, `SkillRunDetailPage`, `ReviewerQueuePage`. |
| `python scripts\validate_openapi.py docs\openapi.yaml`; `python scripts\verify_openapi_provider.py` | OK | OpenAPI valido e provider verification verde: `auth-error=195`, `success=27`, `backend-security=1`. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | Documentazione ancora coerente: 21 documenti, 157 link, 155 comandi/percorsi. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests\test_packaging_consistency.py tests\test_release_readiness.py --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.237.1`. |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | TypeScript, contratti React/App V2/Legal Skills e build Vite 2.237.1 verdi; build 6.61s, main JS `index-D8dK_xzI.js` 451.50 kB / 133.57 kB gzip. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate app scheduler-worker ocr-worker nginx` | OK | Docker locale no-cache `2.237.1`; app/scheduler/OCR/Redis healthy, nginx running, container app `pct.__version__ == 2.237.1`. |
| `curl` locale su `/legal-skills/profile/cold-start`, `/legal-skills/review-queue`, `/legal-skills/run`; `GET http://127.0.0.1:8080/api/pronto` | OK | Le route Legal Skills fase 2 non producono 404 e reindirizzano a login da anonime; readiness locale 200 `versione=2.237.1`, controlli caldi 21.6/19.5 ms. |

## Fase react 3 - App V2 feature flag per pagina 2.224.0 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest -q tests/test_feature_flags.py tests/test_app_v2_feature_flags.py tests/test_app_v2_page_registry.py tests/test_react_shell.py::test_react_shell_app_v2_route_protette_da_feature_flags --tb=short` | OK | 16/16 passati: flag canonici default-off, alias storici, mapping route statiche/dinamiche e protezione shell App V2. |
| `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs` | OK | Contratti React e route gate confermano che solo `/app-v2` e `/app/*` sono protetti dai flag sperimentali; la navigazione operativa normale resta disponibile. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `python scripts\smoke_app_v2_pages.py --base-url http://127.0.0.1:8080` | OK | Registro pagine App V2 allineato; smoke senza credenziali eseguito in modalita inventario con target flag-off attesi. |
| `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` | OK | TypeScript, contratti frontend e build Vite 2.224.0 verdi; asset React rigenerati in `web/static/react`. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | Packaging, versione e readiness release confermati dopo bump `2.224.0`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx`; `GET http://127.0.0.1:8080/api/pronto`; `docker exec iusentra-app python -c "import pct; print(pct.__version__)"` | OK | Build locale no-cache e riavvio completati; app, scheduler, OCR e Redis healthy; readiness locale `versione=2.224.0` e runtime container `2.224.0`. |
| Chrome CDP su `http://127.0.0.1:8080/` e `/fascicoli` con sessione tenant | OK | Desktop/mobile: Panoramica 471/1451 ms, Fascicoli 3500/4445 ms a contenuto React visibile; nessun overflow orizzontale o errore console nel report pulito. |
| Chrome CDP su `/app-v2` e `/app-v2/documenti` con flag spenti | OK | Entrambe le route rispondono fail-closed mostrando solo `Funzione non attiva per questo studio.`; nessun dato operativo viene caricato. |

## Ricerca Legale reale e fonte PST 2.238.0 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web/services/react_legal_intelligence_bridge.py tests/test_react_legal_intelligence_search.py` | OK | Sintassi backend e regressioni dedicate confermate dopo l'innesto ricerca reale `/ricerca-legale`. |
| `python -m pytest tests/test_react_legal_intelligence_search.py -q --tb=short` | OK | 3/3 passati: ricerca su `legal_updates.db`, fallback ufficiale governato e news PST `NWS4865` in News/Ricerca Legale. |
| `npm --prefix frontend run typecheck` | OK | TypeScript confermato dopo il form React che invia la query al backend. |
| `npm --prefix frontend run test` | OK | Contratti React, App V2 frontend, Legal Skills e UI coverage verdi dopo la modifica a `LegalIntelligencePage`. |
| `npm --prefix frontend run build` | OK | Build Vite `2.238.0` completata; asset React rigenerati con chunk `LegalIntelligencePage-CtbkdlI-.js` e CSS `LegalIntelligencePage-Ccs-Dp3-.css`. |
| `python tools/sync_packaging_files.py --check`; `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.238.0`. |
| `python -m pytest tests/test_react_legal_intelligence_search.py tests/test_legal_updates_pipeline.py::test_legal_update_repository_espone_evidenze_lex_da_sql -q --tb=short` | OK | 4/4 passati: bridge React ricerca legale e repository SQL Lex confermati insieme. |
| `python -m pytest tests/test_react_shell.py::test_react_blocco_finale_studio_admin_completo tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative -q --tb=short` | OK | 2/2 passati: matrice route/API/card operative e blocco finale studio/admin ancora coerenti. |
| `python -m pytest tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative tests/test_react_shell.py::test_react_route_gate_copre_rotte_profonde_e_preserva_contratti_operativi -q --tb=short` | OK | 2/2 passati: gate route React e contratti profondi confermati con `/ricerca-legale` full React. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate app scheduler-worker ocr-worker nginx`; readiness locale | OK | Docker locale no-cache `2.238.0`: app, scheduler, OCR, Redis e nginx avviati; `/api/pronto` 200 con `versione=2.238.0`; container app `pct.__version__ == 2.238.0`. |
| Playwright autenticato tramite impersonazione tenant su `/ricerca-legale?q=mediazione` desktop/mobile, report `artifacts/react-migration/visual-2.238.0-ricerca-legale/visual-load-audit.md` | OK | Form ricerca backend visibile, fonte PST `NWS4865` visibile con contesto `22/04/2026`, nessun testo tecnico vietato e nessun overflow orizzontale. |
| `git restore -- data/auth/audit.json data/auth/utenti.json data/tenant_user_directory.json` | OK | Ripuliti solo artefatti runtime prodotti da login/impersonazione e Docker locale; lasciati intatti i file `data/` gia' sporchi prima della tranche. |
| Deploy Hetzner CPX42 con `IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh`; verifiche post-deploy | OK | Server sul branch pushato, `/api/pronto` pubblico 200 con `versione=2.238.0`, container app/scheduler/OCR/Redis/Ollama healthy e cron backup non aggiornato. |

## Registri Mediazione ufficiali 2.239.2 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests/test_react_legal_intelligence_search.py -q --tb=short` | OK | 4/4 passati: ricerca reale, fallback ufficiale governato, news PST `NWS4865` e tre accessi ufficiali Mediazione esposti in `/legal-intelligence/mediazione` e `/ricerca-legale`. |
| `python -m compileall pct web -q` | OK | Sintassi Python confermata dopo aggiornamento bridge Legal Intelligence e bump `2.239.2`. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests/test_packaging_consistency.py tests/test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.239.2`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; verifiche locali | OK | Docker locale no-cache `2.239.2`: app, scheduler, OCR e Redis healthy; `/api/pronto` locale 200 con `versione=2.239.2`; container app `pct.__version__ == 2.239.2`. |
| Deploy Hetzner CPX42 con `IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh`; verifiche post-deploy | OK | Server portato su commit `dbb5d43a`; cron backup non aggiornato; app/scheduler/OCR/Redis/Ollama healthy; `/api/pronto` pubblico 200 con `versione=2.239.2`; pacchetto container `pct-studio-legale 2.239.2`. |

## Ricerca Legale con contesto fonte 2.239.3 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `npm --prefix frontend run typecheck`; `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-tranche-10a-open-design.mjs` | OK | TypeScript, contratti React e Open Design verdi dopo trasformazione di `/legal-intelligence/` in `Osservatorio Legale` e schede fonte con contesto interno. |
| `npm --prefix frontend run test` | OK | Contratti React, App V2 frontend, Legal Skills e UI coverage verdi. |
| `python -m pytest tests\test_react_legal_intelligence_search.py -q --tb=short` | OK | 4/4 passati: ogni fonte di ricerca espone estratto, contesto, uso pratico e attendibilita'; i registri mediazione restano distinti e ufficiali. |
| `python -m compileall pct web -q` | OK | Sintassi Python confermata dopo arricchimento del bridge Legal Intelligence. |
| `npm --prefix frontend run build` | OK | Build Vite `2.239.3` completata; chunk `LegalIntelligencePage-BY7S6cFD.js` 20.37 kB / 6.43 kB gzip e CSS `LegalIntelligencePage-CcxQe1xY.css` 10.20 kB / 1.90 kB gzip. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.239.3`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; verifiche locali | OK | Docker locale no-cache `2.239.3`: app, scheduler, OCR e Redis healthy; `/api/pronto` locale 200 con `versione=2.239.3`; container app e pacchetto `pct-studio-legale` su `2.239.3`. |
| Chrome CDP autenticato, report `artifacts/react-migration/visual-2.239.3-legal-intelligence-context/visual-load-audit.md` | OK | 8/8 controlli desktop/mobile su `/legal-intelligence`, `/legal-intelligence/mediazione`, `/ricerca-legale` e `/ricerca-legale?q=mediazione`: nessun overflow, testo tecnico, form POST HTML, console error o redirect login. |
| Deploy Hetzner CPX42 con `IUSENTRA_SKIP_BACKUP_CRON=1 BRANCH=Codex/legal-electronic-filing-kIxcV bash deploy/hetzner/deploy.sh`; verifiche post-deploy | OK | Server sul commit pushato, cron backup non aggiornato; app, scheduler, OCR, Redis e Ollama healthy; `/api/pronto` pubblico 200 con `versione=2.239.3`; pacchetto container `pct-studio-legale 2.239.3`. |

## Sblocco Legal Skills default-on 2.238.1 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\feature_flags.py web\blueprints\api_v1_legal_skills.py tests\test_feature_flags.py tests\test_app_v2_feature_flags.py tests\test_legal_skills_engine.py` | OK | Sintassi confermata dopo promozione default-on del motore base Legal Skills e dei flag route React. |
| `python -m pytest tests\test_feature_flags.py tests\test_app_v2_feature_flags.py tests\test_legal_skills_engine.py -q --tb=short` | OK | 20/20 passati: Legal Skills base e route catalogo/profilo/esecuzione/revisione sono default-on; trust layer e agenti schedulati restano default-off e rispondono `feature_disabled`. |
| `node frontend\scripts\check-legal-skills.mjs`; `node frontend\scripts\check-react-contracts.mjs`; `node scripts\react-migration\check-route-gate.mjs` | OK | Gate statici Legal Skills, contratti React e route gate coerenti con lo sblocco della pagina. |
| `python scripts\react-migration\generate_app_v2_page_registry.py --check`; `python scripts\react-migration\generate_app_v2_area_requirements.py --check`; `python scripts\react-migration\generate_app_v2_test_docs.py --check` | OK | Registri e documenti App V2 allineati ai nuovi default flag Legal Skills. |
| `npm --prefix frontend run test`; `npm --prefix frontend run typecheck`; `npm --prefix frontend run build` | OK | Test frontend, TypeScript e build Vite `2.238.1` verdi dopo fix console: main `index-Di4ENQKe.js` 451.51 kB / 133.56 kB gzip, chunk `LegalSkillsCatalogPage-DWJDhbO1.js` 3.65 kB / 1.55 kB gzip. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e readiness release 8/8 dopo bump `2.238.1`. |
| `python scripts\validate_docs_links.py`; `python scripts\validate_docs_commands.py` | OK | Link e comandi documentali validi dopo aggiornamento dei default Legal Skills. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; readiness locale | OK | Docker locale no-cache `2.238.1`: app, scheduler, OCR, Redis healthy e nginx running; `/api/pronto` 200 con `versione=2.238.1`; container app `pct.__version__ == 2.238.1`. |
| Chrome CDP autenticato `artifacts/react-migration/visual-2.238.1-legal-skills/visual-load-audit.md` | OK | `/legal-skills` desktop 2787 ms e mobile 1497 ms a contenuto React visibile; zero failure, zero warning, nessun redirect login, console error, overflow, form POST HTML o testo tecnico vietato. |
| `git restore -- data/auth/audit.json data/auth/utenti.json data/tenant_user_directory.json` | OK | Ripuliti solo artefatti runtime prodotti da login/impersonazione e Docker locale; lasciati intatti i file `data/` gia' sporchi prima della tranche. |

## Multi-studio hardening tenant/API 2.218.3 - 2026-05-13

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m pytest tests/test_tenant_isolation_runtime.py -q` | OK | 9/9 passati: compatibilita single-tenant `PCT_API_KEY`, blocco API key globale in multi-tenant, chiave studio coerente, mismatch cross-studio, sessioni incoerenti e path fuori root tenant. |
| `python -m pytest tests/test_storage_strategy.py::test_login_route_assigns_single_active_tenant_to_legacy_global_admin tests/test_storage_strategy.py::test_login_route_bootstraps_legacy_root_data_for_single_tenant_install tests/test_tenant_admin_legacy.py::test_superadmin_globale_ignora_ruolo_stale_nel_sql_locale -q` | OK | Regressioni auth legacy/multi-tenant corrette: fallback single-tenant esplicito preservato e riallineamento SUPERADMIN mantenuto solo per multi-tenant auto-rilevato. |
| `python -m pytest tests/test_fascicoli_pagination.py::test_fascicoli_frontend_contratto_query_params_e_lazy_tab -q` | OK | Contratto statico Fascicoli lazy confermato dopo rimozione preload `regia` dal dettaglio iniziale. |
| `python -m pytest tests -q -k "auth or tenant or api_v1 or security or clienti or fascicoli or scadenziario or messaggi or email"` | OK | Shard ampio sicurezza/API/domini sensibili completato verde dopo correzione dei tre regressi emersi al primo giro. |
| `python -m compileall web pct tests` | OK | Sintassi Python confermata su web, pct e tests. |
| `python -m ruff check web/services/tenant_api_auth.py web/services/tenant_isolation_runtime.py web/blueprints/api_v1.py web/blueprints/api_v1_react.py tests/test_tenant_isolation_runtime.py` | OK | Ruff verde dopo rimozione import inutilizzato in `api_v1_react.py`. |
| `npm run test --prefix frontend` | OK | Contratti React verificati per versione frontend `2.218.3`. |
| `npm run typecheck --prefix frontend` | OK | TypeScript confermato. |
| `npm run build --prefix frontend` | OK | Build Vite completata; asset React rigenerati in `web/static/react`, con dettaglio Fascicoli piu' leggero per caricamento lazy. |

## Superadmin storage e assistenza remota pronta 2.239.0 - 2026-05-15

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\support_remote.py pct\config_studio.py web\services\runtime_settings.py web\services\support_surface.py web\services\server_maintenance_surface.py` | OK | Sintassi confermata dopo default STUN, separazione consumi tenant/globali e scansione storage per categorie. |
| `python -m pytest tests\test_support_remote.py tests\test_server_maintenance_surface.py -q --tb=short` | OK | 14/14 passati: console assistenza pronta, ICE server predefinito, salvataggio config senza perdere il default, inventario storage tenant, categorie/cartelle/file e render server maintenance. |

## Server storage Hetzner e posta scaricata 2.243.7 - 2026-05-16

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile web\services\server_maintenance_surface.py web\blueprints\server_maintenance_admin.py web\services\mailbox_sync_runtime.py web\bootstrap\sync_runtime_routes.py web\services\pdp_penale_runtime.py web\blueprints\api_v1_react.py pct\scheduler.py pct\tenant.py web\services\tenant_legacy_bootstrap.py tests\test_server_maintenance_surface.py tests\test_hetzner_backup_retention.py tests\test_dashboard_mailbox_sync.py tests\test_storage_strategy.py scripts\purge_downloaded_mailboxes.py` | OK | Sintassi confermata dopo console Hetzner, retention rigida, ottimizzazione massima, script cancellazione posta scaricata e blocco fail-closed della posta multi-studio. |
| `python -m pytest tests\test_server_maintenance_surface.py tests\test_hetzner_backup_retention.py -q --tb=short` | OK | 14/14 passati: console spazio fuori studi, cache servizi, massimo 3 backup, deduplica/compattazione archivi studi e purge PEC/ordinaria senza toccare configurazioni. |
| `python -m pytest tests\test_server_maintenance_surface.py tests\test_hetzner_backup_retention.py tests\test_dashboard_mailbox_sync.py -q --tb=short`; `python -m pytest tests\test_storage_strategy.py::test_legacy_bootstrap_non_importa_email_root_automaticamente -q --tb=short` | OK | 21 test mirati passati: lo scheduler email multi-studio e le route operative non cadono piu' su `/data/email`; il bootstrap legacy automatico non importa piu' gli archivi email root nei tenant. |
| `python -m pytest tests\test_email_client.py::test_email_blueprint_usa_storage_tenant_per_sincronizzazione tests\test_email_client.py::test_email_sync_route_espone_warning_e_sync_errore tests\test_email_client.py::test_api_pec_poll_cancelleria_espone_duplicati_e_warning_sync -q --tb=short`; `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | 3/3 test email tenant-aware verdi, packaging sincronizzato e readiness/packaging 8/8 verdi. |
| `python -m py_compile pct\email_client.py web\blueprints\email_client.py web\blueprints\email_ordinaria.py web\services\react_email_bridge.py web\services\server_maintenance_surface.py pct\scheduler.py pct\cli.py pct\legal_update_job.py pct\legal_update_batch_runner.py web\services\legal_update_surface.py tests\test_email_client.py tests\test_email_attachment_dedup.py tests\test_legal_update_batch_runner.py tests\test_legal_update_surface_jobs.py` | OK | Sintassi confermata dopo lettore allegati ZIP e job aggiornamenti legali per elemento. |
| `python -m pytest tests\test_email_attachment_dedup.py tests\test_email_client.py::test_email_dettaglio_scarica_allegato_da_archivio_zip tests\test_email_client.py::test_email_dettaglio_visualizza_e_scarica_allegato_salvato tests\test_email_client.py::test_email_ordinaria_dettaglio_usa_repository_smtp_e_allegati_ordinari -q --tb=short` | OK | 9/9 passati: allegati sciolti e archiviati restano leggibili; download e anteprime PEC/ordinaria non dipendono dal formato fisico. |
| `python -m pytest tests\test_legal_update_batch_runner.py tests\test_legal_update_surface_jobs.py tests\test_scheduler_worker.py -q --tb=short` | OK | 8/8 passati: scheduler, admin e runner usano job per fonte/pubblicazione con timeout per elemento. |
| `python -m pytest tests\test_server_maintenance_surface.py tests\test_hetzner_backup_retention.py tests\test_dashboard_mailbox_sync.py -q --tb=short` | OK | 20/20 passati dopo l'integrazione della compressione allegati nel pannello di ottimizzazione massima. |
| `python -m pytest tests\test_storage_strategy.py::test_legacy_bootstrap_non_importa_email_root_automaticamente tests\test_email_client.py::test_email_blueprint_usa_storage_tenant_per_sincronizzazione tests\test_email_client.py::test_email_sync_route_espone_warning_e_sync_errore tests\test_email_client.py::test_api_pec_poll_cancelleria_espone_duplicati_e_warning_sync -q --tb=short` | OK | 4/4 passati: blocco email tenant-aware e no bootstrap root email confermati dopo il lettore compresso. |
| `python tools\sync_packaging_files.py --check`; `python -m pytest tests\test_packaging_consistency.py tests\test_release_readiness.py -q --tb=short` | OK | Packaging sincronizzato e readiness 8/8 verdi per `2.243.7`. |
| `docker compose build --no-cache app scheduler-worker ocr-worker`; `docker compose up -d --no-build --force-recreate redis app scheduler-worker ocr-worker nginx`; `Invoke-WebRequest http://localhost:8080/api/pronto`; env check container; `python -m pct.legal_update_job --publish-only --publish-limit 1`; `docker builder prune --all --force`; `docker system df` | OK | Docker locale no-cache `2.243.7`: app/scheduler/OCR/Redis healthy, `/api/pronto` 200, `IUSENTRA_EMAIL_ATTACHMENT_STORAGE=archive`, timeout aggiornamenti legali `180`, publish max `80`, CLI job operativo e Build Cache locale `0B` dopo prune. |
| Hetzner `docker builder prune --all --force`; `docker system df`; `df -h /`; pulizia `/opt/iusentra/tmp-backup-snapshot` e backup/quarantene legacy | OK | Cache build Docker azzerata (`Build Cache 0B`); disco produzione sceso da circa 233 GiB iniziali a circa 41 GiB usati su 301 GiB dopo pulizia cache, posta scaricata, snapshot temporaneo e backup legacy. |
| `python3 /tmp/purge_downloaded_mailboxes.py --data-root /opt/iusentra/data --apply` su Hetzner | OK | Recuperati 36.7 GiB cancellando solo PEC/email ordinaria scaricate, allegati e stati di risincronizzazione; configurazioni casella preservate. |
| `python scripts\purge_downloaded_mailboxes.py --data-root data --apply` locale | OK | Recuperati 30.1 GiB localmente con la stessa procedura governata; non sono stati toccati i file configurazione studio. |
