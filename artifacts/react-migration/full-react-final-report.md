# Full React final report

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-13T21:20:00+02:00: fase react 2 `fasereact`
2.223.0. Aggiunto registro ufficiale pagine App V2/React generato da script,
con 98 route manifest, 13 route shell App V2, 31 alias legacy, feature flag,
RBAC, rischio tenant/PII, test presenti/mancanti e priorita P0/P1/P2/P3.

La fase 2 non promuove route a full senza parita reale: le route legacy e
partial restano backlog esplicito in `docs/frontend-app-v2-pages.md`. Aggiunto
smoke parametrico `scripts/smoke_app_v2_pages.py`, senza credenziali hardcoded,
e test deterministici `tests/test_app_v2_page_registry.py`.

Aggiornamento 2026-05-13T20:45:00+02:00: fase react 1 `fasereact`
2.222.0. Introdotta governance default-off per capability App V2 e Web Push:
route sperimentali `/app-v2/*` protette da feature flag, endpoint autenticato
`/api/v1/ui/feature-flags`, bootstrap React con stato flag e guard client/server
per notifiche push su dispositivo.

La fase non modifica il comportamento delle route operative gia' promosse:
`/documenti`, `/fascicoli`, `/agenda`, `/comunicazioni` e le superfici React
ufficiali restano servite dalla shell corrente. I flag agiscono solo sul
perimetro sperimentale App V2 e sulle azioni Web Push finche' non vengono
abilitate esplicitamente per lo studio.

Verifica locale finale: Docker no-cache 2.222.0 healthy, `/api/pronto` 200,
browser Chrome autenticato desktop/tablet/mobile con `/app-v2/documenti` 403
controllato flag-off e `/notifiche` 200 senza overflow, errori console o testi
tecnici vietati.

Aggiornamento 2026-05-13T13:32:00+02:00: tranche 2.220.0 audit gate React
reale. Promosse a full reale `/scadenziario/:id` e `/sito-studio/builder`;
promosse a partial governato `/scadenziario/:id/modifica` e
`/sito-studio/redazione-ai`. I sottopercorsi ad alto rischio restano
legacy-first con contratti espliciti: telematico, servizi telematici, SIGP
sync, tribunali, guida firma digitale, osservabilita, alias database e
applicazioni.

La verifica ha corretto anche falsi full preesistenti: il componente
`Template Atti` non usa piu' form HTML e il fallback dashboard non contiene piu'
marcatori mock. Gate registrati verdi in `pytest-confirmed-ok.md`: py_compile,
`tests/test_react_shell.py`, typecheck, build, test frontend e i tre script
React di route-gate/full/no-mock.

Verifica browser reale 2026-05-13: Chrome headless via Playwright Python,
login autenticato, desktop su builder e scadenziario dettaglio/modifica,
mobile su redazione assistita Sito Studio. Esito: shell operativa presente,
testi attesi visibili, zero errori console, zero overflow orizzontale e nessun
termine tecnico vietato nel testo visibile.

Aggiornamento 2026-05-13T18:20:00+02:00: tranche 2.218.4 PWA/Web Push.
`Impostazioni > Notifiche` mantiene l'esperienza React e sostituisce lo stato
generico `Da configurare` con messaggi operativi: server da configurare,
browser/dispositivo non supportato, permesso bloccato, dispositivo pronto o
notifiche attive. Gli amministratori vedono il comando server
`bash deploy/hetzner/configure_web_push.sh`; gli utenti ordinari vedono che
l'amministratore deve abilitare il canale. Il consenso browser resta solo su
click esplicito.

Backend e deploy ora includono diagnostica sicura di `/api/push/public-key`,
generatore VAPID, verifica CLI e script Hetzner di configurazione/verifica senza
stampa della chiave privata. Nessuna chiave reale e' stata salvata nel
repository.

Aggiornamento 2026-05-12T19:50:00+02:00: tranche 2.218.0 su
`/template-atti`, `/template-atti/catalogo` e compilatore atti. Il catalogo
mantiene 420 template master e 192 modelli operativi collegati, con schema
Cartabia 1.2.0, prefill bindings e link compilatore su tutte le voci. La UI
React mostra filtri per stato Cartabia, area processuale e precompilazione,
chip `Precompilabile`, `Richiede verifica avvocato`, dati mancanti, controlli
bloccanti/consigliati e preview del timbro studio. Nessuna voce viene
dichiarata automaticamente `100% conforme`: gli stati restano governati da
regole, metadati e revisione professionale dove necessaria.

Il timbro studio e' ora servizio tenant-aware e viene iniettato centralmente
nei render degli atti prima del titolo; il resolver prefill espone provenienza,
attendibilita', avvisi, alternative e motivi dei dati mancanti senza inventare
dati. Gate mirati registrati in `pytest-confirmed-ok.md`: script catalogo,
pytest master/prefill/timbro, typecheck, contratti React, build Vite,
packaging, readiness release, Docker locale 2.218.0 e smoke browser verdi.
Chrome headless su Docker locale ha confermato catalogo desktop/tablet/mobile
e compilatore desktop senza overflow, errori console o termini tecnici vietati.

Aggiornamento 2026-05-12T18:05:00+02:00: tranche 2.217.2 PWA/Web Push.
`Impostazioni > Notifiche` aggiunge il pannello dispositivo con consenso
esplicito, attivazione/disattivazione subscription e test. Il centro notifiche
topbar resta compatibile ma ora persiste notifiche e letture in `NOTIFICATIONS_DB`.
Service Worker e manifest sono serviti da root; senza VAPID configurato la UI
mostra stato chiaro e il gestionale continua a usare le notifiche interne.

Aggiornamento 2026-05-12T17:50:00+02:00: tranche 2.217.1 su
`/notifiche-legali`. I modelli relata personalizzati sono ora renderizzati con
motore ristretto: solo token whitelistati, niente blocchi Jinja, filtri,
chiamate o accessi riservati. La pagina mostra testo modello e anteprima
compilata con dati correnti e placeholder espliciti; l'avvocato puo' modificare
la relata compilata e salvarla come bozza della notifica corrente, tenant-aware
e separata dal catalogo dei modelli riutilizzabili. Il tab `Comunica al
cliente` usa un catalogo proprio `comunicazioni-cliente-1.0`, non espone il
catalogo relata 2026.05.12 e genera solo oggetto/corpo email ordinaria.
Smoke Chrome headless desktop/tablet/mobile confermato su Docker locale
2.217.1: nessun errore console, overflow o testo tecnico vietato; tab cliente
senza catalogo relata e senza versione `2026.05.12`.

Aggiornamento 2026-05-12T22:05:00+02:00: tranche 2.217.0 su
`Impostazioni -> Sincronizzazione Calendari`. La tab Calendari espone ora
account collegabili, calendari con direzione bidirezionale/in sola entrata/in
sola uscita, riservatezza export, ultimo allineamento, azione `Allinea ora`,
pausa/disconnessione e conflitti risolvibili. Il frontend resta senza logica
provider e senza segreti: Google, Microsoft, Apple/iCloud, WebCal/ICS e il
provider locale persistente passano da API Flask e dal nuovo
`CalendarSyncEngine`. La demo locale ha verificato push, pull, update,
conflitto e protezione scadenza perentoria.
Smoke Chrome headless desktop/tablet/mobile confermato sul pannello: account,
calendari collegati e conflitti sono visibili, senza errori console, overflow
documentale o testi tecnici vietati.

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

## Aggiornamento Template Atti compilatore React 2.218.2

`GET /template-atti/compila/<codice>` e' ora una superficie React operativa. La route carica la shell React, legge il contesto da `GET /api/v1/ui/template-atti/compila/<codice>`, mostra cliente e pratica collegata come selettori reali e invia la generazione al POST Flask gia' auditato. La vista classica resta disponibile solo con `_legacy=1`.

La pagina espone il presidio normativo Cartabia/deposito senza badge assoluti: quando mancano dati concreti dell'atto, il modello resta compilabile solo dopo completamento dei campi obbligatori. Le note mancanti sono in italiano e con contrasto verificato; non vengono mostrati nomi tecnici di campo o messaggi inglesi.

Browser Playwright 2026-05-13 su `AMM_RIC_001` con cliente e pratica selezionati: compilatore React visibile, vecchio compilatore assente, nessun errore console, pannello normativo senza oggetti tecnici e CTA finale `Crea bozza e apri editor`.

## Aggiornamento fase react 3 App V2 2.224.0

La shell sperimentale App V2 ha ora feature flag canonici per pagina/route, tutti default-off, con alias storici preservati. I flag proteggono solo `/app-v2` e `/app/*`: le route operative gia' in uso nella sidebar ordinaria non vengono filtrate o bloccate.

Verifiche 2026-05-13: pytest mirati feature flag/App V2/registro/shell 16/16, contratti React, route gate, registry `--check`, typecheck, test frontend, build Vite, packaging/readiness e Docker locale 2.224.0 healthy. Browser Chrome CDP su `/` e `/fascicoli` desktop/mobile verde nel passaggio caldo; `/app-v2` e `/app-v2/documenti` restano fail-closed con messaggio operativo quando i flag sono spenti.
