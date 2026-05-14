# Full React final report

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-14T23:10:00+02:00: modulo notifiche legali 2.236.0.
La pagina `/notifiche-legali` mantiene la shell React operativa e rende esplicita
la fase successiva ai tre pulsanti segnalati: controllo relata, controllo prova
deposito e preparazione comunicazione cliente producono esito visibile, file
previsti, testo generato e pacchetto prova quando disponibile. Il backend ora
blocca notifiche L. 53/1994 incomplete, canali/procedimenti sconosciuti,
oggetti PEC errati, ricevute non complete, attestazioni mancanti e PDF/A non
ammesso. La selezione documenti consente uno o piu' documenti della pratica e
li riporta automaticamente nell'elenco allegati alla relata. Gate mirato verde:
44/44; Docker locale `2.236.0`, smoke read-only e browser isolato verificati
senza eseguire backup.

Aggiornamento 2026-05-14T19:05:00+02:00: hotfix 2.235.3. Il rosso remoto
`CI / Local Signer e PKCS#11` e' stato riprodotto localmente e corretto:
PDP/PAT/PTT restano WSDL diretti di default nel Local Signer, mentre la
modalita browser-assistita entra solo con flag espliciti di forzatura o
disabilitazione. Rigenerato Local Signer `1.6.31` e i pacchetti `tools/dist`,
incluso `SetupLocalSigner.exe`, per allineare anche il download pubblico.

Verifica locale 2.235.3: lo shard CI esatto `signer` 4/4 e' verde 39/39 e
tutti gli shard Local Signer locali sono verdi: 40/40, 40/40, 39/39 e 39/39.
Dist allineato alla sorgente, ruff, packaging/readiness 8/8, `npm test`,
typecheck e build Vite verdi. Docker locale no-cache ricostruito con wheel
`pct-studio-legale==2.235.3`, servizi app/scheduler/OCR/Redis healthy,
readiness locale 200 `versione=2.235.3`, smoke contracts PASS=2 FAIL=0 SKIP=1
e post-deploy locale PASS=76 FAIL=0 SKIP=1 BLOCKED=6. La regola PST resta
vincolante: un PIN per visualizzare e un PIN per scaricare, salvo scadenza
reale della sessione lato portale o token.

Aggiornamento 2026-05-14T18:20:00+02:00: hotfix 2.235.2. Le route
assistite non-PST `/portali/pdp/acquisizione`, `/portali/pat/acquisizione`,
`/portali/ptt/acquisizione` e `/portali/sigit/acquisizione` sono promosse come
React operative esatte con `TelematicoSurfacePage`, manifest sbloccato,
route-gate e shell React allineati. Restano legacy-first i moduli telematici
piu' ampi non parificati e l'acquisizione PST storica, per non confondere
integrazione diretta PST e portali assistiti.

Lo smoke CI `contracts` e' ora offline: OpenAPI e provider verification girano
senza server locale, mentre i controlli HTTP live restano nelle suite `api` e
`post-deploy`. Email ordinaria ripara i triplicati IMAP equivalenti in lettura
e durante la sync, mantenendo separati messaggi PEC/Legalmail diversi anche se
il provider ricicla lo stesso `Message-ID`. Il piano React full aggiorna le
fasi residue e conserva la regola operativa PST: un PIN per visualizzare e un
PIN per scaricare, salvo scadenza reale della sessione.

Verifica locale 2.235.2: test mirati email/route/CI, contratti React,
route-gate, registry App V2, packaging/readiness, `npm test`, typecheck e build
Vite verdi. Docker locale no-cache healthy con readiness `versione=2.235.2`;
smoke `contracts` PASS=2 FAIL=0 SKIP=1 e `post-deploy` PASS=76 FAIL=0
SKIP=1 BLOCKED=6. Browser in-app autenticato: `/app-v2/messaggi/nuovo` attivo
in React senza `Funzione non attiva per questo studio`; PDP/PAT/PTT/SIGIT
assistiti senza vecchia card `Portale ufficiale assistito` o `Local Connector
non raggiungibile` e senza errori console.

CI remota: il primo push ha intercettato correttamente la mappa sicurezza
backend non rigenerata dopo l'aumento del manifest da 98 a 102 route. La mappa
e' stata riallineata e il gate locale RBAC/tenant/App V2/OpenAPI e' tornato
verde 75/75. Produzione Hetzner aggiornata a 2.235.2 sul commit del hotfix:
container app, scheduler, OCR, Redis, audit-postgres, audit-worm e Ollama
healthy; `/api/pronto` pubblico 200 e smoke post-deploy pubblico PASS=76
FAIL=0 SKIP=1 BLOCKED=6.

Aggiornamento 2026-05-14T10:05:00+02:00: fase react 13 `fasereact`
2.234.0. Gli smoke operativi App V2 sono stati consolidati in
`scripts/smoke_app_v2_all.py` con suite `health`, `auth`, `flags`, `rbac`,
`tenant`, `routing`, `api`, `pages`, `workflows`, `documents`, `admin`,
`search`, `notifications` e `post-deploy`. La nuova libreria
`scripts/smoke_lib.py` governa redaction, HTTP, result model, summary, JSON
report, severity ed exit code. `BLOCKED`/`SKIP` restano espliciti per env o ID
test mancanti e non vengono dichiarati verdi.

Verifica fase 13: py_compile, help, inventory compatibile fase 10, test unitari
7/7, gate documentali, OpenAPI/provider, npm test/typecheck/build, packaging,
readiness e Docker locale no-cache verdi. Il run post-deploy locale su
`http://127.0.0.1:8080` ha prodotto PASS=76, FAIL=0, SKIP=1, BLOCKED=6,
WARNING=0 con runtime e label immagine `2.234.0`; il run pubblico post-deploy su
`https://app.iusentra.it` al commit
`85d7617549c0695ffd3f41447d0b2c86524766aa` ha prodotto lo stesso esito, con
`/api/pronto` 200 `versione=2.234.0` e container Hetzner healthy/up. I blocchi
riguardano solo profili smoke/ID documento non configurati.

Aggiornamento 2026-05-14T09:30:00+02:00: fase react 12 `fasereact`
2.233.0. La documentazione finale App V2 e' ora indicizzata in
`docs/index.md` e copre architettura, App V2, feature flag, routing,
sicurezza/RBAC/tenant, API contracts, test, CI/CD, rollout, rollback,
troubleshooting, osservabilita, database/migrazioni, risk register, release
notes e handover prossime PR. `README.md`, `SECURITY.md` e `CONTRIBUTING.md`
sono stati riallineati ai comandi, branch, gate e limiti reali.

Audit documentale: Storybook/VRT e smoke autenticati restano gap espliciti,
non stati verdi; i documenti generati restano governati dai generatori. Aggiunti
`scripts/validate_docs_links.py` e `scripts/validate_docs_commands.py`.
Verifica locale: link docs 145/145, comandi/path 131/131, generatori App V2,
OpenAPI/provider verification, smoke inventory/contracts, npm
test/typecheck/build, packaging/readiness e pytest mirati verdi.

Aggiornamento 2026-05-14T07:10:00+02:00: fase react 11 `fasereact`
2.232.0. La CI/CD App V2 ora ha gate bloccanti espliciti nel workflow
principale: provider verification/OpenAPI, smoke contratti, registro e piano
test App V2, smoke inventory, RBAC/tenant isolation, feature flag, routing,
frontend test/typecheck/build, coverage critica ed E2E smoke. Aggiunto
`docs/ci-cd-gates.md` come inventario operativo e `.github/workflows/smoke-staging.yml`
come smoke manuale ambiente/post-deploy con secrets solo da GitHub.

La security supply chain produce report `pip-audit` e `npm audit` senza
segreti hardcoded; i required checks consigliati e il rollout 1/10/50/100 sono
documentati. Verifica locale: YAML workflow, generatori `--check`, pytest fase
11 5/5, contratti/fase 11 10/10, registry/test-plan/fase 11 13/13, backend
security/tenant/flag/routing/OpenAPI 75/75, npm audit critical zero, pip-audit
senza vulnerabilita note, npm test/typecheck/build, coverage-critical,
release-readiness, quality-overlay, e2e-smoke, Docker no-cache 2.232.0 healthy
e smoke App V2 locale.

Aggiornamento 2026-05-14T02:35:00+02:00: fase react 10 `fasereact`
2.231.0. Aggiunti piano test, inventario e matrice App V2:
`docs/test-plan-app-v2.md`, `docs/test-inventory.md` e
`docs/test-matrix-app-v2.md`, generati in modo deterministico da
`scripts/react-migration/generate_app_v2_test_docs.py`. Il nuovo orchestratore
`scripts/smoke_app_v2_all.py` coordina inventory, security, pagine, routing,
workflow e contratti senza segreti hardcoded.

La fase non dichiara copertura frontend o VRT che il repo non possiede:
Vitest/Jest/RTL, Playwright/Cypress e Storybook restano gap documentati. Gli
smoke autenticati richiedono env espliciti e, in loro assenza, restano
inventario o controlli anonimi.

Verifica locale: py_compile, generatori `--check`, smoke inventory/contracts,
pytest fase 10 3/3, gate fasi 7/8/9/registry 15/15, backend security/tenant/
flag/routing/OpenAPI 75/75, npm test/typecheck/build, suite CI
coverage-critical, release-readiness, quality-overlay, e2e-smoke, coverage
mirata auth/storage/telematico al 78%, Docker no-cache 2.231.0 healthy e smoke
App V2 locale security/pages/routing/workflows.

Aggiornamento 2026-05-14T00:15:00+02:00: fase react 9 `fasereact`
2.230.0. Aggiunta la disciplina UI regression App V2 senza mascherare
Storybook o VRT come presenti: `docs/ui-regression-and-storybook.md` documenta
scelta, gap, fixture, stati UI, RBAC, feature flag, accessibilita e responsive;
`frontend/src/test/fixtures/app-v2-ui-fixtures.json` contiene dati sintetici
sicuri; `scripts/validate_ui_coverage.py` blocca P0/P1 full privi di riga
`ui_tested` e stati minimi.

Il registro pagine e il riepilogo frontend generati hanno ora la sezione
`Copertura UI fase 9`. Le route P0/P1 full React sono marcate `ui_tested`; le
route parziali, legacy o telematiche non parificate restano `partial`,
`pending` o `blocked`, cosi' la fase non dichiara completate superfici che non
hanno ancora parita reale.

Verifica locale finale: py_compile, generatori `--check`, validatore UI
coverage, npm test/typecheck/build, pytest fase 9/fase 8/fase 7/registry
15/15, OpenAPI, packaging/readiness, Docker no-cache 2.230.0 healthy, smoke
security, smoke workflow in modalita inventario e browser in-app su App V2
flag-off piu' pagina Impostazioni React senza errori console o testi tecnici
vietati.

Aggiornamento 2026-05-13T23:59:00+02:00: fase react 8 `fasereact`
2.229.0. Aggiunto il registro generato dei requisiti specifici per area in
`docs/app-v2-area-requirements.md`: ogni area ora dichiara pagine, URL App V2,
feature flag, endpoint API, RBAC, PII, workflow principali, test richiesti,
test presenti e stato finale. Le aree con route legacy/parziali restano
`partial` o `blocked` e non vengono mascherate come complete.

La fase introduce `scripts/smoke_app_v2_workflows.py` per inventario e smoke
autenticati dei workflow P0/P1 reali. Senza credenziali ambiente lo script non
dichiara eseguiti i profili admin/tenant/readonly; con `--require-credentials`
fallisce in modo esplicito.

Verifica locale finale: py_compile, generatori `--check`, smoke workflow
inventario, pytest fase 8/fase 7/registry 12/12, feature/routing/shell 15/15,
npm test/typecheck/build, OpenAPI, provider verification, packaging/readiness,
Docker no-cache 2.229.0 healthy e browser in-app su `/app-v2/impostazioni`
flag-off con zero errori console e nessun testo tecnico vietato.

Aggiornamento 2026-05-13T23:55:00+02:00: fase react 7 `fasereact`
2.228.0. Rafforzato il livello frontend comune App V2: il bootstrap React
espone i permessi effettivi dell'utente, la navigazione sperimentale filtra
pagine con feature flag spento o permesso mancante, e le route App V2 non
censite mostrano una 404 sicura senza caricare la dashboard.

Il registro pagine e il riepilogo frontend ora riportano lo stato fase 7
(`complete_tested`, `partial`, `pending`) su ogni route. Le route P0/P1 gia'
full React sono coperte dal gate comune; le superfici legacy o parziali restano
pendenti e non vengono dichiarate completate.

Verifica locale finale: py_compile, generatore registry `--check`, npm
test/typecheck/build, pytest fase 7/registry/flag/routing 23/23, OpenAPI,
packaging/readiness, Docker no-cache 2.228.0 healthy e browser
desktop/tablet/mobile su `/app-v2/area-non-censita` con zero errori console,
zero overflow e nessuna richiesta dashboard.

Aggiornamento 2026-05-13T23:05:00+02:00: fase react 5 `fasereact`
2.226.0. Le API React `/api/v1/ui` hanno un guardrail backend centrale che
blocca parametri client riservati al server (`tenant_id`, `studio_id`, user,
API key, token generici e redirect liberi) dopo autenticazione, senza eco dei
valori ricevuti. La mappa `docs/backend-endpoint-security-map.md` censisce 182
endpoint con auth, priorita, permessi attesi e dati sensibili.

Verifica locale: py_compile, generatore mappa `--check`, pytest fase
5/tenant/feature/routing 33/33, regressioni API Impostazioni/Utenti/Fascicoli
ed Email 15/15, packaging/readiness 8/8, typecheck, contratti React, route gate
e build Vite 2.226.0. Nessuna nuova dipendenza frontend e bundle principale
invariato.

Aggiornamento 2026-05-13T22:05:00+02:00: fase react 4 `fasereact`
2.225.0. Aggiunto il perimetro di routing sicuro legacy -> App V2:
`web/services/app_v2_routing.py` censisce 69 mapping backend espliciti e
parametri dinamici ammessi, conserva query innocue, scarta query rischiose e
fallisce chiuso se il target non e' interno, non e' sotto `/app-v2` o non ha un
feature flag App V2 noto.

La fase mantiene 0 redirect live: le route legacy restano fallback sicuro finche'
non viene attivato rollout esplicito per pagina. Il router frontend ora rimuove
query e hash prima del matching, preservando deep link come
`/app/fascicoli?drawer=nuovo`. Aggiunti
`docs/legacy-to-app-v2-routing-map.md`, colonne fase 4 nel registro,
smoke `scripts/smoke_app_v2_routing.py` e test dedicati contro open redirect,
query unsafe, mapping statici/dinamici e feature flag spenti/accesi.

Verifica locale finale: test routing/registro 15/15, gate routing+feature flag
27/27, typecheck, contratti React, build Vite, packaging/readiness, Docker
no-cache 2.225.0 healthy e smoke Chrome desktop/mobile su percorsi App V2 e
legacy anonimi, tutti same-origin verso login e senza errori console.

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

## Aggiornamento fase react 5 Backend Security 2.226.0

Le API React `/api/v1/ui` hanno ora un guardrail centrale sui parametri di
controllo server. Tenant, studio, user, API key, token generici e redirect
liberi vengono rifiutati con `backend_security_control_param` dopo
autenticazione, senza eco dei valori ricevuti. I campi legittimi dei flussi
Utenti/Profili/Impostazioni restano validati dagli endpoint di dominio.

Mappa aggiornata: `docs/backend-endpoint-security-map.md`. Verifiche mirate:
py_compile, generatore mappa `--check`, pytest fase 5/tenant/feature/routing
33/33 e regressioni API Impostazioni, Utenti, Fascicoli, Email 15/15.

## Aggiornamento fase react 6 OpenAPI/provider 2.227.0

La fase 6 introduce `docs/openapi.yaml` come contratto OpenAPI 3.0.3 generato
dagli endpoint reali `/api/v1/ui`, piu' `docs/api-endpoint-contract-map.md` per
collegare endpoint, pagina, priorita, RBAC, feature flag, tenant scope e stato
provider verification.

Gate introdotti: `generate_api_contracts.py --check`, `validate_openapi.py`,
`verify_openapi_provider.py` e `tests/test_openapi_contracts_phase6.py`. La
provider verification copre 182 endpoint con 401 reale, 27 endpoint P0/P1 con
200 autenticato e il 400 `backend_security_control_param` sui parametri tenant
forzati.

## Aggiornamento fase react 14 release finale 2.235.0

La chiusura fase 14 non introduce nuove migrazioni React. Conferma lo stato
full/partial/legacy del manifest, aggiorna `docs/final-release-report.md` e
riesegue i gate finali su documentazione, registry, feature flag, routing,
OpenAPI/provider verification, backend, frontend, security, coverage-critical e
Docker locale.

Fix finale applicato e ritestato: estrazione di `fascicoli_create_routes.py` e
`fascicoli_document_helpers.py` per riportare i moduli bootstrap nei budget
governance, senza cambiare URL legacy o shell React. Smoke Docker locale finale:
contracts PASS=7 FAIL=0; post-deploy PASS=76 FAIL=0 SKIP=1 BLOCKED=6.

## Hotfix App V2 rollout 2.235.1

Corretto il blocco per cui le pagine operative sotto `/app-v2` restavano spente
quando lo studio non aveva flag manuali configurati. Le superfici gia'
promosse operative sono ora attive di default e spegnibili per rollback
esplicito; `routes.appV2.telematico.center`,
`routes.appV2.telematico.surface` e `routes.appV2.notifications.mobilePush`
restano default-off e fail-closed.

Verifiche mirate: `/app-v2/messaggi/nuovo`, `/app-v2/messaggi` e
`/app-v2/documenti` rispondono 200 con shell React autenticata; `/app-v2/telematico`
resta 403. Test feature flag/routing/shell/packaging/readiness 30/30 passati.
Build Vite 2.235.1 verde in 5.83s senza aumento degli asset principali.
Docker locale no-cache healthy con readiness `2.235.1`; smoke contracts
PASS=7 FAIL=0 e post-deploy PASS=76 FAIL=0 SKIP=1 BLOCKED=6. Browser reale
desktop/mobile su `/app-v2/messaggi/nuovo`: nessun messaggio "Funzione non
attiva", redirect login corretto per utente anonimo e zero errori console.
