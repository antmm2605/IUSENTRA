# Full React final report

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-12T20:30:00+02:00: tranche 2.216.9 su
`/notifiche-legali`. Il modello relata selezionato e' ora visibile in anteprima
prima della verifica, il catalogo laterale permette scelta rapida e l'avvocato
puo' duplicare o creare modelli personalizzati con campi automatici IUSENTRA.
I modelli su misura vengono salvati nel perimetro tenant e renderizzati dal
motore L. 53/1994 con gli stessi controlli dei modelli standard. I percorsi
`Deposito prova notifica` e `Comunica al cliente` usano la stessa selezione
pratica per proporre atto, destinatario, cliente, procedimento e documento
informativo, riducendo la compilazione manuale senza inventare dati mancanti.

Aggiornamento 2026-05-12T18:40:00+02:00: tranche 2.216.8 su
`/notifiche-legali`. Il percorso e' ora un motore di modelli parametrico:
catalogo JSON versionato con 39 voci complessive, tutti i modelli 01-34
richiesti e varianti 01A-01E per procedimento, attestazioni e destinatari
impresa/societa'. Il bridge React compila automaticamente pratica, assistito,
procedimento, destinatari, PEC, fonte pubblica suggerita, documenti, origine e
hash dai repository reali IUSENTRA. La pagina espone selezione assistita di
pratica, destinatario e documento, senza creare dati fittizi e mantenendo
verifica PEC, firma e invio come conferme esplicite dell'avvocato.

Aggiornamento 2026-05-12T11:25:00+02:00: tranche 2.216.7 su
`/notifiche-legali`. La shell React espone tre percorsi separati: notifica ex
L. 53/1994 con relata e blocchi, deposito prova notifica con RAC/RdAC originali
e comunicazione al cliente senza relata. Le API `/api/v1/ui/notifiche-legali/*`
validano oggetto obbligatorio, fonte PEC, attestazione, ricevuta completa,
firma e approvazione avvocato; i canali PEC/email ordinari bloccano l'uso
diretto dell'oggetto L. 53 e rimandano alla procedura guidata.

Aggiornamento 2026-05-11T17:30:00+02:00: tranche 2.216.5 su
`/fascicoli/nuovo`. Il Fascicolo Veloce ora carica autorita' giudiziarie dal
registro uffici IUSENTRA, mostra clienti e soggetti reali in selettori guidati,
richiede controparte e identificativo quando la creazione veloce deve aprire il
deposito, e restituisce errori JSON espliciti invece del generico `Operazione
non riuscita`. Dopo la creazione veloce il salvataggio porta direttamente a
`/fascicoli/<id>/deposito/prepara`, lasciando busta, firma e invio nel flusso
di deposito assistito governato dagli schemi e dai controlli telematici.
Browser reale Docker desktop/tablet/mobile verificato senza errori console.

Aggiornamento 2026-05-11T14:25:00+02:00: hotfix 2.216.1 sul flusso
PST via Local Signer. Il wizard React dei portali telematici apre il preflight
PST dal browser, conserva la sessione locale e la riusa per ricerca,
snapshot fascicolo e download batch. SIGP/PST e il dettaglio fascicolo usano
sempre il batch documenti, evitando il ritorno al download singolo.

Aggiornamento 2026-05-11T12:40:00+02:00: tranche 2.216.0 su
`/fascicoli/nuovo`. Il form React di apertura fascicolo usa sezioni
collassabili, sposta `Pratiche collegate` nel blocco iniziale sotto
`Personalizzabile` e introduce `Fascicolo Veloce` con multicaricamento separato
di documenti iniziali ed email `.eml`. Il backend salva i file nel repository
documenti del fascicolo, conserva conteggi dedicati e scarta i file non `.eml`
nell'area email senza interrompere la creazione. Il flusso PCT resta impostato
come deposito assistito: preparazione e controlli automatici, conferma utente
prima di firma, busta e invio.

Aggiornamento 2026-05-11T11:00:00+02:00: hotfix 2.215.7 su `/documenti`.
La route non restituisce piu' 404: e' censita nel manifest come
`react_operational_full`, sbloccata dal route gate e servita dalla shell React
con `StudioModulePage` e API `/api/v1/ui/studio-modules/documenti`. Il workspace
collega fascicoli/documenti, catalogo atti, Redazione Atti e ricerca documentale;
il payload filtra record locali con diciture `demo`/`sample` per non esporli in
UI.

Aggiornamento 2026-05-11T02:35:00+02:00: hotfix 2.215.5 sui dettagli
email React. Gli allegati PEC e Email ordinaria mostrano l'azione `Visualizza`
separata da `Apri` e `Scarica`; `Visualizza` usa il link inline in nuova scheda
senza parametro di download forzato.

Aggiornamento 2026-05-11T02:05:00+02:00: tranche 2.215.4 sul flusso
Preventivi/Incarichi/Fascicoli. Il catalogo `Pratiche collegate` e' ora dato
versionato `PST_XSD`; il Preventivo guidato non deduce piu' il CodiceOggetto
dalla tipologia tariffaria e il predeposito PCT blocca la busta se il fascicolo
non contiene un CodiceOggetto ufficiale. `DatiAtto.xml` usa il codice PST nel
nodo `Oggetto`.

Aggiornamento 2026-05-10T00:15:00+02:00: tranche 2.214.0 completata sul
perimetro testi visibili e dettagli email React. Le route
`/email/messaggio/<id>` e `/email-ordinaria/messaggio/<id>` sono nella shell
React con endpoint JSON dedicati. La guardia testi visibili protegge React e
template Flask da diciture tecniche rivolte allo studio. Smoke browser Docker
2.214.0 desktop/mobile su Redazione Atti, Template, Statistiche, Ricerca Legale,
News, Giurisprudenza, Strumenti, Controlli Atti, Sito Studio Contatti, dettagli
email e Database: `#root` presente, nessun overflow orizzontale e nessun termine
vietato visibile.

Tranche architetturale aggiornata: `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` promosse a `react_operational_full`, audit anti-mascheramento senza bridge residui, manifest a 37 full / 1 partial / 19 legacy. `Controlli Atti` usa titolo e payload React reali, mentre le route strumenti usano `StudioModulePage` con payload di modulo studio. Non dichiarare completata la migrazione totale per route legacy ancora giustificate da segreti, export/documenti, sottopercorsi tecnici o portali telematici non ricostruiti.

## Test

- python -m pytest -q: timeout - Interrotto dal timeout locale dopo circa 45 minuti; nessun verde completo dichiarabile.
- npm test: passed - Contratti React verificati.
- npm run typecheck: passed - tsc --noEmit completato.
- npm run build: passed - Vite build completata; asset generati in web/static/react.
- node scripts/react-migration/run-full-react-migration.mjs: passed - Audit, anti-mascheramento e check Full React passati.
- node scripts/react-migration/run-legal-ui-checks.mjs: passed - Check UI legale, responsive e anti-Bootstrap passati.
- node scripts/react-migration/check-route-gate.mjs: passed - Manifest e gate route allineati allo stato corrente.
- python -m pytest -q tests/test_react_shell.py::test_statistiche_react_full_non_espone_fallback_legacy: passed - Regressione mirata su `/statistiche` full senza fallback legacy.
- python tools/check_repo_governance.py: passed - Governance repo verde; `web/app.py` 40 righe e 0 route inline.
- python -m pytest -q lex/tests/unit/test_router.py lex/tests/test_gateway_router.py tests/test_lex_sentenze_clienti_fix.py --tb=short: passed - 32 test Lex passati dopo ripristino regex accentate cliente.
- docker compose build --no-cache app: passed - Immagine locale 2.208.0 ricostruita da zero.
- python -m pytest -q tests/test_database.py::test_create_app_bootstrap_moduli_monitorati tests/test_web_bootstrap.py::test_create_app_email_ordinaria_deriva_da_email_db_runtime tests/test_web_bootstrap.py::test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina --tb=short: passed - 3 test sul fallback email ordinaria runtime e bootstrap dati.
- python -m pytest -q tests/test_storage_strategy.py::test_sync_user_directory_indicizza_utenti_tenant_sqlite tests/test_storage_strategy.py::test_sync_user_directory_puo_saltare_reconcile_pesante tests/test_web_bootstrap.py::test_runtime_bundle_startup_sync_directory_non_rilancia_reconcile_pesante --tb=short: passed - 3 test su directory utenti tenant e startup web senza reconcile pesante.
- docker compose up -d --no-build redis app nginx: passed - Dopo rebuild: `iusentra-app` healthy, `nginx` avviato, `/api/pronto` 200 con versione `2.208.0`.
- npm test: passed - Contratti React 2.210.0 verificati dopo lo sblocco delle tre route.
- npm run typecheck: passed - TypeScript confermato dopo `TelematicoSurfacePage` e `StudioModulePage`.
- npm run build: passed - Vite build completata; asset React 2.210.0 generati in `web/static/react`.
- node scripts/react-migration/run-full-react-migration.mjs: passed - Audit, anti-mascheramento, no fake full, route contract e responsive workspace OK.
- Visual smoke Chrome desktop/tablet/mobile: passed - `/deposito/checklist`, `/strumenti-legali`, `/strumenti-operativi` con shell React, titoli visibili, nessun overflow orizzontale e nessun testo tecnico vietato.
- python -m pytest -q tests/test_react_shell.py::test_route_ufficiali_superfici_telematiche_restano_moduli_operativi_legacy_e_checklist_react tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short: passed - 4/4 test mirati sulle route/API/gate React.
- npm run typecheck: passed - TypeScript confermato per 2.214.0.
- npm test: passed - Contratti React confermati per 2.214.0.
- npm run build: passed - Build Vite 2.214.0 completata; asset React rigenerati.
- node scripts/react-migration/check-route-gate.mjs: passed - Route gate coerente.
- node scripts/react-migration/check-full-react-route-contract.mjs: passed - Contratto full React coerente; audit anti-mascheramento aggiornato.
- node scripts/react-migration/check-no-fake-react-full.mjs: passed - Nessuna route full mascherata.
- python -m pytest -q tests/test_email_client.py::test_email_dettaglio_visualizza_e_scarica_allegato_salvato tests/test_email_client.py::test_email_ordinaria_dettaglio_usa_repository_smtp_e_allegati_ordinari tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica tests/test_react_shell.py::test_statistiche_react_full_non_espone_fallback_legacy tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short: passed - 6/6 mirati email e React.
- python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short: passed - 8/8 dopo bump 2.214.0.
- docker compose build --no-cache app scheduler-worker ocr-worker: passed - immagini locali ricostruite da zero con package 2.214.0.
- docker compose up -d app scheduler-worker ocr-worker: passed - app, scheduler, OCR e Redis healthy.
- Invoke-WebRequest http://localhost:8080/api/pronto: passed - readiness locale `versione=2.214.0`.
- npm run typecheck: passed - TypeScript confermato per route/sidebar/workspace `/documenti`.
- npm test: passed - Contratti React confermati dopo aggiunta `/documenti`.
- npm run build: passed - Build Vite 2.215.7 completata in 6.15s; asset React rigenerati.
- node scripts/react-migration/check-route-gate.mjs: passed - `/documenti` inclusa nelle route governate consentite.
- node scripts/react-migration/check-full-react-route-contract.mjs: passed - Contratto full React e audit anti-mascheramento aggiornati.
- python -m pytest -q tests/test_react_shell.py::test_react_blocco_finale_studio_admin_completo tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short: passed - 4/4 mirati route, shell, gate e payload.
- docker compose build --no-cache app scheduler-worker ocr-worker: passed - immagini locali 2.215.7 ricostruite dopo il filtro Documenti.
- docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx: passed - app, scheduler, OCR e Redis healthy.
- Browser Playwright headless `/documenti`: passed - desktop 352.9 ms, tablet 210.8 ms, mobile 167.9 ms a contenuto visibile, nessun overflow e nessun testo tecnico visibile.
- python -m compileall web/bootstrap/fascicoli_core_routes.py web/services/react_fascicoli_bridge.py pct/fascicoli.py tests/test_react_shell.py: passed - sintassi confermata dopo Fascicolo Veloce.
- python -m pytest -q tests/test_react_shell.py::test_react_fascicolo_nuovo_form_collassabile_e_fascicolo_veloce tests/test_react_shell.py::test_post_nuovo_fascicolo_veloce_carica_documenti_ed_email_eml --tb=short: passed - 2/2 su pannelli collassabili, spostamento pratiche collegate e upload iniziali.
- npm --prefix frontend run typecheck: passed - TypeScript confermato per la UI `/fascicoli/nuovo` 2.216.0.
- npm --prefix frontend run test: passed - Contratti React confermati dopo la modifica alla pagina fascicolo.
- npm --prefix frontend run build: passed - Build Vite finale 2.216.0 completata in 6.02s; asset React rigenerati in `web/static/react`.
- node scripts/react-migration/check-route-gate.mjs / check-full-react-route-contract.mjs / check-no-fake-react-full.mjs: passed - route gate, contratto full React e no-fake coerenti.
- python tools/sync_packaging_files.py --check: passed - packaging/versione 2.216.0 sincronizzati.
- python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short: passed - 8/8 packaging e readiness release.
- docker compose build --no-cache app scheduler-worker ocr-worker: passed - immagini locali finali ricostruite da zero con wheel 2.216.0.
- docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx / docker compose ps / /api/pronto: passed - container locali healthy, readiness `versione=2.216.0`.
- Browser Playwright headless `/fascicoli/nuovo`: passed - desktop/tablet/mobile con upload iniziali, ordine corretto, nessun overflow, nessun errore console e nessun testo tecnico vietato; warm-up tenant iniziale registrato in `pytest-open-issues.md`, passaggi caldi desktop sotto 800 ms.
- npm --prefix frontend run typecheck: passed - TypeScript confermato dopo sessione PST React/Local Signer 2.216.1.
- python -m pytest -q tests/test_react_shell.py::test_react_wizard_pst_verifica_local_signer_dal_browser tests/test_sigp_sync.py::test_sigp_sync_visibile_nel_menu_e_apre_primo_fascicolo_importato tests/test_sigp_sync.py::test_sigp_sync_local_connector_preview_e_download_salva_file tests/test_sigp_sync.py::test_sigp_sync_download_duplicato_passa_original_true_al_local_signer --tb=short: passed - 4/4 mirati su Local Signer PST e SIGP batch.
- npm --prefix frontend run test: passed - Contratti React confermati dopo hotfix PST.
- npm --prefix frontend run build: passed - Build Vite 2.216.1 completata in 5.84s; asset React rigenerati.
- python -m pytest -q tests/test_sigp_sync.py --tb=short: passed - 13/13 sul perimetro SIGP/PST.
- node scripts/react-migration/check-route-gate.mjs / check-full-react-route-contract.mjs: passed - gate e contratto full React coerenti.
