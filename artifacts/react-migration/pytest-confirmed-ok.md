# Pytest shard confermati OK

Aggiornato: 2026-05-11, sessione React Full / shard backend.

## Regola operativa

Questi comandi o shard sono stati verificati in questa sessione e non vanno rilanciati a vuoto. Si ripetono solo se viene toccato codice collegato al loro perimetro, oppure come ultimo gate aggregato prima di commit/deploy.

## Frontend e gate React

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
