# Full React final report

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-31T13:30:00+02:00: supporto remoto avviabile dallo
studio 2.248.93.
La shell React espone ora un comando `Assistenza` visibile nella topbar dello
studio e non nascosto nei breakpoint tablet/mobile; i template legacy principali
di dashboard, dettaglio cliente e dettaglio fascicolo usano lo stesso flusso
studio. Il click crea una sessione cliente tramite `/support/studio/sessione`,
apre la stanza cliente firmata e registra audit/eventi senza richiedere accesso
superadmin all'utente dello studio.

Verifica reale su server isolato `127.0.0.1:18654`: pulsante studio visibile,
modal launcher funzionante anche senza Bootstrap JS nella shell React, stanza
cliente con consensi, cabina superadmin con sessione `studio-admin`, stanza
operatore e WebSocket cliente/operatore con chat e ping bidirezionali. Console
browser senza errori.

Aggiornamento 2026-05-29T21:05:00+02:00: hotfix regressioni PST e Studio Telematico
2.248.89.
Verifica browser in-app su server locale `127.0.0.1:8080`: `/portali/pst/acquisizione`
carica il percorso guidato PST senza messaggio obsoleto `Timeout del Local Signer locale`;
`/importa-pratiche-studio-telematico` carica il percorso guidato e non mostra
`Pacchetto non leggibile` nello stato iniziale. Desktop, tablet e mobile non hanno
overflow orizzontale e la console non registra errori.

Verifica file reali utente: `QuickOrganizer.zip` in `C:\Users\antmm\Downloads\ATTI`
viene riconosciuto come ZIP con `QuickOrganizer.mdb` non leggibile in questo ambiente
e 9575 file `ATTI`/`EMAILS`; l'anteprima ora produce un avviso operativo e non un
errore generico. Il falso `Citazione_28139218.pdf` da PST viene bloccato perché non
contiene un PDF reale.

Aggiornamento 2026-05-29T18:10:00+02:00: hotfix regressioni PST e Studio Telematico
2.248.88.
Le superfici React coinvolte restano operative: `/portali/pst/acquisizione`
carica la ricerca per anno e il percorso PST senza console error e senza
messaggio generico di timeout Local Signer; `/importa-pratiche-studio-telematico`
espone il preparatore Windows `.exe`, non mostra più `.ps1` come azione primaria
e mantiene feedback visibile durante controllo/import.

Verifica locale isolata: server Flask temporaneo su `127.0.0.1:18080`, login
operatore test, browser in-app con screenshot desktop non vuoti, console senza
errori. Verifica API reale: upload ZIP con sole cartelle `ATTI`/`EMAILS`
restituisce anteprima controllata (`sourceKind=zip-files`, `availableFiles=2`,
warning `pratiche_assenti`) invece di `Pacchetto non leggibile`.

Aggiornamento 2026-05-26T09:15:00+02:00: uffici competenti inline nel fascicolo
2.248.62.
Il dettaglio fascicolo React contiene ora una sezione `Uffici giudiziari per
Comune` con ricerca interna: l'avvocato inserisce uno o più Comuni e il risultato
viene renderizzato nella stessa finestra della pratica, con uffici, recapiti,
assistenza pubblicata e copia rapida dei contatti. La funzione riusa l'endpoint
read-only già governato per Strumenti Forensi e non modifica procedure
telematiche, depositi, Local Signer o dati runtime.

Gate locali confermati: typecheck React, pytest mirati fascicoli/uffici, build
Vite e browser in-app su fascicolo campione con ricerca `Taurianova`, risultato
Palmi visibile e zero overflow desktop/tablet/mobile.

Aggiornamento 2026-05-25T19:20:00+02:00: EML fascicolo, cancellazione
documenti e Local Signer EXE 2.248.52.
L'editor React dei documenti riconosce gli `.eml` caricati nel fascicolo e li
presenta come email originale read-only: intestazioni, corpo, allegati e link
di download restano consultabili senza alterare la prova PEC. Le route di
visualizzazione/download usano un resolver di lettura che recupera anche copie
storiche con suffisso quando un vecchio metadato punta a un file base non più
presente.

La cancellazione documenti salva prima l'archivio del fascicolo e rimuove il
file solo dopo, così un lock SQLite non può più lasciare una riga fantasma con
file già cancellato. Lo storage tenant-aware usa `busy_timeout` e retry brevi
su `database is locked`; upload e delete restituiscono un messaggio operativo
controllato invece di errore 500 se l'archivio è occupato.

Local Signer è allineato a `1.6.45`: il download Windows pubblico è
`SetupLocalSigner-1.6.45.exe` e anche la vecchia route `windows-ps1` restituisce
l'EXE, senza proporre PowerShell come installazione utente. Gate locali
confermati: pytest fascicoli/editor/storage/Local Signer, compileall, typecheck
React, build Vite, packaging, readiness, UTF-8, OpenAPI e governance repo.

Aggiornamento 2026-05-25T18:35:00+02:00: Componi PEC via Local Signer
2.248.51.
`/email/scrivi` resta esperienza React, ma il submit PEC non usa più la sola
risposta Flask come prova di invio. La pagina invia dal browser a Local Signer
`127.0.0.1:27272/pec/send`, passa allegati in base64 e registra l'inviato nello
studio con `/email/scrivi/conferma-locale` solo dopo `Message-ID` positivo. Il
fallback server risponde con errore operativo quando l'invio server non è
esplicitamente abilitato o quando lo storico messaggi torna `FALLITO`.
Gate locali confermati: pytest PEC/email/Local Signer 78/78, typecheck React,
build Vite e compileall Python.

Aggiornamento 2026-05-25T12:30:00+02:00: evoluzione grafica professionale e
Lex 2.248.40.
Il preset IUSENTRA è stato stabilizzato anche durante navigazioni consecutive
nello stesso tab: l'audit aspetta che la sequenza pagina venga rimarcata prima
di giudicare la route. Il controllo finale ha verificato 168 combinazioni
desktop, tablet e mobile con scroll fino al fondo: Panoramica, Regia Operativa,
Ricerca Studio, Agenda, Fascicoli, Clienti/Soggetti, Comunicazioni, Scadenze,
Studio, Sito Studio, Amministrazione e Impostazioni restano React/preset dove
previsto, senza overflow, senza testi tecnici visibili e con bottoni contenenti
testo e icone.

Lex è stato rifinito come pannello operativo professionale: toolbar laterale su
desktop/tablet, toolbar verticale compatta su mobile, microfono, caricamento
documenti e web libero sempre presenti. Il gate dedicato è verde 9/9 su PEC,
Notifiche legali e Fascicoli; la textarea mobile ha dimensione touch corretta
anche sulla pagina più compressa.

Aggiornamento 2026-05-25T12:00:00+02:00: Design system unico governato 2.248.39.
La Fase 4 rende bloccante il preset grafico IUSENTRA: `pnpm --filter @iusentra/studio test`
esegue `check-design-system-governance.mjs`, che produce il report automatico
`artifacts/react-migration/design-system-governance-report.md` e impedisce nuovi CSS
locali o inline style non motivati. Il wizard preventivi è stato riallineato al preset
senza accenti laterali pagina-specifici.
Le sole pagine che possono restare come superfici speciali fuori preset sono
`/sito-studio/builder` e le visualizzazioni dettaglio fascicolo `/fascicoli/<id>`;
tutte le altre, incluse PEC, email, lista fascicoli, nuovo fascicolo e archivio,
passano dal frame IUSENTRA.

Verifica aggiunta: `/email/`, `/email-ordinaria/` e `/notifiche-legali` restano
React con preset attivo su desktop, tablet e mobile. Gli asset statici React/PWA
sono esclusi dal rate limit, così i cambi pagina ravvicinati non servono JS/CSS
come 429 e non lasciano la shell vuota.

Aggiornamento 2026-05-24T23:55:00+02:00: Sito Studio modifica articolo
2.248.37.
`/sito-studio/articoli/:id/modifica` è ora una pagina React operativa completa:
la route Flask serve la shell React, il payload arriva da
`/api/v1/ui/sito-studio/articoli/<id>/modifica`, il form salva sul backend
reale via JSON, blocca i campi di contesto forzato e registra audit
tenant-aware. La pagina mostra caricamento, assenza articolo, errori campo,
successo di salvataggio, anteprima pubblica e azioni editoriali senza mock o
dati demo.

Il gate React ammette solo la rotta esatta di modifica articolo e mantiene
protetti i percorsi tecnici non ricostruiti. Manifest, contratti legacy,
route-gate, full-react-route-contract, no-fake React full, test frontend e
pytest mirati impediscono il ritorno a fallback classici. La verifica browser
desktop/tablet/mobile ha confermato titolo e corpo editabili preservati,
nessun overflow orizzontale, nessun errore console e nessun testo tecnico
vietato visibile.

Aggiornamento 2026-05-24T22:20:00+02:00: React full senza pagine finte
2.248.36.
`/giurisprudenza/nuova` è stata ricostruita come superficie React completa:
carica dati JSON reali, propone default e opzioni dal backend, valida i campi,
salva la scheda tramite POST JSON e mostra esito operativo senza mock o dati
demo. La rotta classica resta disponibile solo dietro `?_legacy=1` per
compatibilità tecnica, non come percorso principale.

Il manifest e i gate promuovono a `react_operational_full` anche
`/preventivi/wizard`, `/scadenziario/:id/modifica` e
`/sito-studio/redazione-ai`. Il wizard preventivi non pubblica più l'azione
primaria `?_legacy=1`; contratti React, route gate, full-react-route-contract,
no-fake React full e audit anti-mascheramento sono stati rilanciati sul
perimetro modificato.

Verifica browser reale locale: login operatore, apertura
`/giurisprudenza/nuova`, compilazione della scheda, salvataggio confermato e
controllo responsive desktop/tablet/mobile senza overflow orizzontale.

Aggiornamento 2026-05-24T18:00:00+02:00: chiusura Relata notifica PEC-first
2.248.28.
`/notifiche-legali`, top bar, dettaglio fascicolo e Portale Servizi ora seguono
la regola corretta: il provvedimento notificabile nasce dalla PEC dell'ufficio
giudiziario. I documenti già presenti in `Documenti e atti` e i soli metadati
del portale non generano più duplicati né pendenze di relata. Il link di
acquisizione viene compilato con fascicolo, numero R.G., anno, ufficio, PEC e
documento, con acquisizione mirata al singolo provvedimento e flag
`non_duplicare_documenti=1`.

La UI espone anche la matrice casi/destinatari governata dal backend, la lista
Fascicoli mostra pagine ulteriori con controlli espliciti e Lex indicizza i
`.pdf.p7m` come PDF leggibili salvando l'indice una sola volta. La chiusura
richiede demo script, screenshot reali e guida PDF:
`artifacts/notifiche-legali/notifiche-legali-demo-e2e.pdf` e
`artifacts/notifiche-legali/notifiche-legali-guida-avvocato-screenshot.pdf`.
La guida screenshot è stata rigenerata con font Unicode e viewport leggibili:
8 pagine renderizzate, zero caratteri sostitutivi e 14/14 verifiche UI
superate. Sono stati salvati anche gli XSD SICI PST del 12 maggio 2026 in
`docs/specs/ministero/xsd/2026-05-12-sici/`, così il deposito prova resta
ancorato agli schemi tecnici più recenti disponibili nel repository.

Aggiornamento 2026-05-23T20:00:00+02:00: notifiche legali guidate
2.248.21.
`/notifiche-legali` mantiene la superficie React operativa e ora espone un
percorso più guidato: scelta pratica con selezione automatica di tutti i
documenti, upload multiplo degli allegati esterni, aggiunta manuale progressiva,
attestazioni automatiche per ogni allegato che le richiede e risultato con
passaggi, verifiche e audit.

Gate verdi: `tests/test_notifiche_legali.py`, demo audit L. 53/1994 e
typecheck React. Il report demo è registrato in
`artifacts/notifiche-legali/notifica-l53-demo-audit.md`.

Aggiornamento 2026-05-22T12:05:00+02:00: Preset grafico globale IUSENTRA
2.248.12.
Il preset grafico globale è ora centralizzato in `IusentraPreset.tsx` e
documentato in `docs/UI_PRESET_IUSENTRA.md`: PageShell, MainArea, MainSurface,
SupportRail, PanelCard, DataSurface, FiltersBar, ContextFilters, PaginationBar,
ActionCard, EmptyState, token grafici e mappa icone sono il riferimento unico
per le pagine operative. La pagina Fascicoli usa il preset come caso pilota e
mantiene la DataSurface allineata alla SupportRail desktop; `/sito-studio/builder`
resta esclusa dal preset come richiesto.

Gate verdi: contratti React, App V2 frontend, legal skills, typecheck, build
Vite, test shell Fascicoli/preset e browser locale desktop/tablet/mobile sul
caso pilota dopo build.

Aggiornamento 2026-05-18T17:20:00+02:00: Update Intelligence fonti/PDF/OCR/Lex
2.245.40.
La console `/admin/aggiornamenti-legali/` espone ora contatori su evidenze web,
PDF/allegati e documenti collegati; Ricerca Legale riceve dai risultati
`legal_updates.db` riferimenti normativi, R.G., domande contestuali e stato
PDF/OCR senza duplicare il contesto. Lex e il corpus riusano lo stesso
arricchimento deterministico; il Web libero resta separato da fonti ufficiali,
studio, fascicoli e promozione DB/corpus.

Gate verdi: py_compile mirato, shard Update Intelligence, job/autofetch/batch,
verifica web/allegati/document intelligence, Lex/corpus/Ricerca
Legale/Giurisprudenza, typecheck, build Vite, governance, UTF-8 e diff check.

Aggiornamento 2026-05-17T14:05:00+02:00: AI Locale mobile e
EmbeddingGemma 2.245.7.
La tab `/impostazioni?tab=ai` non tratta piu' telefono e tablet come se fossero
PC: rileva dispositivo, touch, dimensione schermo, RAM dichiarata, core e spazio
stimato, poi mostra il percorso sicuro. Su mobile apre Lex AI usando il motore
autorizzato dello studio; sul PC resta disponibile la preparazione locale con
Local Signer e Ollama. Il modello di ricerca documenti viene presentato come
`EmbeddingGemma 300M`, senza esporre il codice `embeddinggemma:300m` nella UI.

Verifica reale con dati temporanei isolati: Playwright desktop 1440x1000 e
mobile 390x844 su `/impostazioni?tab=ai`, login tenant, Local Signer intercettato
nel browser, pannello `AI su telefono e tablet`, `EmbeddingGemma 300M` e `Apri
Lex AI` visibili, nessun overflow orizzontale e zero errori console. Gate verdi:
typecheck, pytest mirato Impostazioni AI, contratti React e build Vite.
Produzione Hetzner aggiornata sul commit `0b54b53d0b057b5e122eea8935075b717948fdc7`
con readiness pubblica `2.245.7`, container app/scheduler/OCR/Redis/Ollama
healthy, marker UI presenti nel bundle e cache build Docker finale a `0B`.

Aggiornamento 2026-05-17T13:35:00+02:00: Lex AI mobile e Qwen 3.5 2.245.6.
La shell React espone Lex AI anche su telefono e tablet: nella barra mobile
inferiore compare il pulsante operativo `Lex AI`, che apre il widget contestuale
globale senza portare dati legali o modelli sul dispositivo. La scelta di
prodotto dopo la valutazione del video su Qwen 3.5 e' mantenere il telefono come
client sicuro verso il runtime autorizzato dello studio, mentre i modelli
`qwen3.5:2b` e `qwen3.5:9b` entrano solo come opzioni volontarie in AI Locale
per prove misurate su desktop/edge.

Verifica reale mobile 390x844 su `/` autenticata: `Lex AI` visibile, click con
apertura del widget globale, pannello non nascosto, nessun overflow orizzontale
e zero errori console. Gate verdi: typecheck, py_compile AI locale, contratti
React, pytest shell mirato, build Vite e validazione link documentali.
Valutazione documentata in `docs/LEX_MOBILE_AI_QWEN35_EVALUATION.md`.

Aggiornamento 2026-05-16T17:40:00+02:00: registri mediazione interni 2.243.4.
La pagina `/ricerca-legale/mediazione` non e' piu' una raccolta di collegamenti:
porta dentro IUSENTRA Registro Organismi di Mediazione, Elenco Enti per la
Mediazione ed Elenco Formatori per la Mediazione, con 3.035 righe acquisite dal
portale ministeriale e classificate per sezione, stato, natura, territorio,
codice fiscale, partita IVA, email e sito. L'alias
`/legal-intelligence/mediazione` resta governato e canonizza sulla stessa
esperienza.

Lex legge gli stessi dati come fonte ufficiale di classe A tramite il repository
interno condiviso. Il bridge React usa identita' per-riga, cosi' i record
importati non vengono piu' deduplicati come semplici link ministeriali. Gate
verdi: py_compile mirato, pytest Legal Intelligence/Lex/Update Intelligence,
typecheck, build Vite, Docker locale no-cache, sync live 3.035 record, API
React autenticata con 3.038 schede e Chrome CDP desktop/tablet/mobile 6/6 in
`artifacts/react-migration/visual-2.243.4-mediazione-registry-final/visual-load-audit.md`.
Nessun backup eseguito.

Aggiornamento 2026-05-15T18:20:00+02:00: hotfix Lex chat 2.238.2.
Il widget Lex nella shell non riversa piu' HTML di errore nella conversazione:
le risposte non JSON/HTML vengono sostituite da un messaggio operativo breve e
`/api/assistente/chat` restituisce JSON controllato se fallisce prima dello
stream. Il crash su sentenze specifiche (`SourceScope.reason` mancante) e'
coperto da test con `Sentenza n. 14575 ud. 15/04/2026 - deposito del
21/04/2026`.
La stessa query trova la scheda ufficiale Cassazione
`penale_dettaglio.page?contentId=SZP50042` tramite fallback governato sulla
pagina pubblica Giurisprudenza Penale; dopo l'exact match ufficiale il retrieval
non rilancia la ricerca pubblica generica lenta. Gate verdi: py_compile,
node --check, Ruff, test Lex mirati e diff check sul perimetro.

Aggiornamento 2026-05-15T14:30:00+02:00: hotfix cartella cliente 2.237.5.
La route `/clienti/<id>/cartella` e' censita come `react_operational_full` e i
richiami con `?_legacy=1` vengono normalizzati con redirect 302 verso la URL
canonica prima di servire la shell React. `CartellaClientePage` usa solo azioni
canoniche di cartella/faldone e non mostra piu' collegamenti `?_legacy=1`.
Gate verdi: py_compile mirato, pytest React shell mirati, packaging/readiness
8/8, generatori App V2 `--check`, `npm test`, typecheck, build Vite `2.237.5`,
`check-full-react-route-contract`, Docker locale no-cache e browser Chrome CDP
desktop/mobile su URL legacy. Browser locale: desktop contenuto React visibile
in 1979 ms, mobile in 1516 ms, entrambi senza overflow, console error o testo
tecnico vietato.

Aggiornamento 2026-05-14T23:55:00+02:00: prova notifica automatica 2.236.2.
La scheda `Deposito prova notifica` e' stata semplificata: l'utente sceglie
insieme atto, relata firmata, PEC inviata, RAC e RdAC; IUSENTRA riconosce i
file dal nome, calcola automaticamente gli SHA-256 nel browser e compila il
riepilogo prova con riferimenti DatiAtto.xml. I campi manuali restano in un
pannello secondario di correzione. Le date delle relate vengono rese in formato
italiano, ad esempio `TAURIANOVA RC, 14/05/2026`. Gate mirati verdi:
notifiche/registry/deposito 46/46, typecheck, contratti React, UI coverage,
packaging/readiness 8/8 e build Vite `2.236.2`. Verifica browser: i riferimenti
`DatiAtto.xml` si aggiornano anche se l'utente sceglie prima i file e inserisce
dopo il destinatario. Deploy Hetzner completato senza backup con readiness
pubblica `2.236.2` e smoke produzione health/notifiche verdi.

Aggiornamento 2026-05-14T23:35:00+02:00: hotfix prova notifica 2.236.1.
La scheda `Deposito prova notifica` permette ora di selezionare uno o piu'
documenti dalla pratica anche per il deposito della prova, non solo per la
relata. I riferimenti portale, ad esempio `pst:JPW_SIGP:2182464`, entrano nel
campo `Atto notificato` e nell'elenco automatico insieme al nome file e allo
SHA-256 disponibile. Il payload inviato al backend contiene `atti_notificati`
separati, cosi' l'evidence pack distingue atto principale e allegati notificati.
Gate mirati verdi: ruff, pytest notifiche 25/25, typecheck, contratti React,
test frontend, build Vite, route gate, packaging/readiness 8/8 e browser Chrome
headless su runtime isolato.
Docker locale e deploy Hetzner verificati sul commit corrente del branch con
`IUSENTRA_SKIP_BACKUP_CRON=1`: app `2.236.1`, container healthy, readiness
pubblica e smoke `health`/`notifications` verdi senza eseguire backup.

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

## Aggiornamento notifiche legali e telematico 2.236.0

Completato il perimetro operativo per notifiche PEC L. 53/1994, relazioni
parametriche, prova deposito, registry procedimenti telematici e workflow PST
area web. La UI `Notifiche Legali` permette ora di selezionare uno o piu'
documenti dalla pratica e li riporta automaticamente nell'elenco allegati prima
di `Controlla relata`, `Controlla prova deposito` e `Prepara comunicazione`.

Il backend fallisce chiuso su canali o procedimenti ignoti, disattiva il modulo
legacy `pct/notifica.py`, impone oggetto L53 esatto, relata separata e firmata,
ricevuta completa, fonte/verifica PEC, attestazioni quando richieste, PDF/A
bloccante/manual review e limiti PTT/SIGIT 10MB/50MB/50 file/100 caratteri.

Verifiche: ruff, compileall, pytest mirati 44/44, packaging/readiness 8/8,
typecheck, contratti React, test frontend, build Vite, route gate, browser reale
su runtime isolato con due documenti, Docker locale no-cache, smoke locale e
smoke produzione. Deploy Hetzner completato sul commit corrente del branch
`Codex/legal-electronic-filing-kIxcV` con `IUSENTRA_SKIP_BACKUP_CRON=1`:
nessun backup eseguito e cron backup non aggiornato.

## Hotfix operativo UI 2.236.3

Il perimetro segnalato dall'utente e' stato chiuso senza nuove dipendenze
frontend: `/profilo` e `/agenda/importa` passano alla shell React; `/agenda/nuovo`
precompila avvocato, codice fiscale, procedimento e ufficio dalla selezione
cliente; clienti, soggetti e fascicoli hanno la scrollbar superiore; PDP, PAT e
SIGIT mostrano `Portale ufficiale` come link secondario; PEC e SMTP ordinario
supportano cliente e allegati multipli; lo scadenziario non espone piu' la fonte
tecnica e apre il dettaglio operativo; Impostazioni AI locale rilancia la
verifica stato all'apertura del tab.

Gate finali locali: py_compile, contratti React, route gate, typecheck, test
frontend leggero, build Vite, pytest mirati, packaging/readiness, Docker locale
no-cache 2.236.3 e Playwright/CDP autenticato sulle route richieste. Restano
aperti solo limiti strumentali documentati in `pytest-open-issues.md`:
contratto storico `/sigp/` 308 e falsi rossi da script/browser in-app.

Deploy Hetzner CPX42 eseguito sul branch `Codex/legal-electronic-filing-kIxcV`
con runtime `2.236.3`: repository server aggiornato, app/scheduler/OCR/Redis,
Caddy e Ollama healthy/running, `/api/pronto` pubblico 200 e container app con
`pct.__version__ == 2.236.3`.

## Audit UI/UX severo 2.236.4

Completato hardening visivo e di usabilita' su superfici React e pannelli
admin collegati: testi italiani professionali, date admin in formato italiano,
bottoni icona etichettati, focus trap per drawer/modali, tabelle mobile a card,
wrapping per testi lunghi e correzioni su stati loading/error/success.

Il blocco piu' severo era prestazionale: il dettaglio admin studio poteva
mandare in timeout il worker per riconciliazione archivio durante una lettura.
Ora il rendering usa percorsi canonici senza reconcile, il conteggio spazio e'
lazy/time-boxed e la configurazione database resta consultabile senza scansioni
pesanti.

Gate locali: py_compile, node --check, typecheck, contratti React, route gate,
full React contract, build Vite, pytest mirati admin/storage/agenda, packaging,
Docker locale no-cache e Chrome CDP autenticato. Report visuale:
`artifacts/react-migration/visual-2.236.4/visual-load-audit.md`, 46 route,
92 controlli desktop/mobile, 0 failure.

## Rifinitura audit UI/UX 2.236.5

Seconda passata correttiva dopo il report severo: Ricerca Studio usa solo
linguaggio operativo per lo studio legale, senza sigle tecniche, tempi in
millisecondi o scorciatoie esposte come testo primario. Controlli Atti sostituisce
i riferimenti al browser con postazione/PC. Il CSS della barra ricerca usa una
dimensione testo stabile e l'audit visuale conta correttamente anche pulsanti e
controlli interni, non solo link.

Gate locali: typecheck, test frontend, contratti React, route gate, full React
contract, packaging/readiness, build Vite, Docker locale no-cache e Chrome CDP
autenticato. Audit completo `visual-2.236.5`: 91/92 OK con un timeout CDP
isolato su `/soggetti/nuovo` mobile; retry mirato `visual-2.236.5-soggetti-nuovo`
OK in 761 ms. Nessun avviso, overflow orizzontale o testo tecnico vietato nelle
rotte passate.

Deploy Hetzner CPX42 eseguito senza backup su richiesta esplicita `no backup`:
non e' stato eseguito `backup.sh` e il cron backup non e' stato aggiornato
(`IUSENTRA_SKIP_BACKUP_CRON=1`). Produzione verificata: branch
`Codex/legal-electronic-filing-kIxcV`, container app/scheduler/OCR/Redis healthy,
`/api/pronto` pubblico 200 `versione=2.236.5`, runtime container
`pct.__version__ == 2.236.5` e manifest React pubblico con gli asset aggiornati.

## Strumenti Forensi operativi 2.236.6

Ripristinata la parita' funzionale della pagina `/strumenti-legali`: la shell
React non si limita piu' a mostrare schede informative, ma espone il catalogo
completo delle funzioni forensi e invia i form agli endpoint JSON collegati ai
metodi reali di `GestioneStrumentiLegali`.

Il bridge `Strumenti Forensi` ora pubblica 70 funzioni di catalogo e 20
calcolatori eseguibili, con campi dinamici, preset applicativi, fascicoli reali
quando disponibili e risultati in pagina con metriche, tabelle, note, avvisi e
fonti. Il submit resta nella pagina React, senza form POST HTML nel flusso
principale e senza dati dimostrativi.

Gate locali: py_compile backend, typecheck, test frontend, build Vite, contratti
React, route gate, full React contract, pytest mirati Strumenti Legali/SIGP,
dominio storico `tests/test_strumenti_legali.py`, browser reale
desktop/tablet/mobile e Docker locale no-cache 2.236.6. La verifica browser
autenticata su `/strumenti-legali/?tool=interessi&app=calcolo_interessi_di_mora`
conferma catalogo, comando `Calcola interessi`, risultato `Interessi maturati`,
tabella `Segmenti di calcolo` e assenza di testi tecnici vietati.

## Legal Skills Engine 2.237.0

Completata la prima consegna AI Legal con nuova esperienza React `/legal-skills`:
catalogo pack, profilo studio, esecuzione guidata e revisione risultati restano
coerenti con il design system IUSENTRA, senza dati dimostrativi e con linguaggio
operativo per lo studio legale.

Il backend espone `/api/v1/legal-skills/*` con feature flag spenti di default,
RBAC, audit, tenant isolation, blocco parametri riservati e storage runtime sotto
il tenant attivo. I seed pack sono read-only e originali IUSENTRA: contratti,
privacy, contenzioso e regolatorio.

Gate locali: py_compile, `tests/test_legal_skills_engine.py`, check statico
frontend Legal Skills, typecheck, test frontend, OpenAPI/provider verification,
documentazione, packaging/readiness, build Vite e Docker locale no-cache 2.237.0.
Browser Chrome CDP autenticato su `/legal-skills`: desktop 1736 ms, mobile
2728 ms, zero failure/warning, nessun overflow, console error o testo tecnico
vietato. Il 404 iniziale della route e' stato corretto aggiornando route gate e
shell React Flask.

## AI Legal fase 2 finale 2.237.1

La seconda fase ha chiuso il contratto frontend richiesto dal file `ai legal 2`:
le pagine nominali `PracticeProfilePage`, `ColdStartInterviewPage`,
`LegalSkillRunPage`, `SkillRunDetailPage` e `ReviewerQueuePage` esistono come
wrapper agganciati alla shell React, riusano le pagine operative gia' verificate e
non introducono dati mock o workflow paralleli.

Il check Legal Skills ora blocca regressioni sui file pagina e sulle route
`/legal-skills/profile/cold-start` e `/legal-skills/review-queue`. Gate finali
locali: pytest Legal Skills 8/8, OpenAPI/provider, docs, packaging/readiness,
typecheck, test frontend, build Vite 2.237.1, Docker no-cache e smoke HTTP
locale sulle route fase 2.

## Sblocco Legal Skills 2.238.1

Il catalogo `/legal-skills` e le route collegate non richiedono piu' un override
manuale dei flag per gli studi ordinari: `lex.legalSkills.enabled` e i flag
catalogo/profilo/esecuzione/revisione sono attivi di default, con rollback
esplicito ancora disponibile.

Restano spenti di default trust layer, custom skill e agenti schedulati. Il
gate mirato conferma quindi il comportamento desiderato: catalogo e profilo sono
raggiungibili, mentre le superfici sensibili rispondono ancora fail-closed senza
opt-in.

Verifica finale locale: Docker no-cache 2.238.1 healthy, `/api/pronto` 200
`versione=2.238.1` e Chrome CDP autenticato su `/legal-skills` verde in
desktop/mobile (2787/1497 ms), senza redirect login, errori console, overflow,
form POST HTML o testo tecnico vietato.

## Sito Studio Builder Pro 2.239.1

`/sito-studio/builder` e' ora una superficie React full dedicata, senza shell
ordinaria visibile: topbar scura, pannello verticale stretto e anteprima live
grande. La struttura segue la Versione B richiesta e mantiene operative le 10 tab
definitive con dati studio, pagine/menu, blocchi, contenuti, aspetto, media,
SEO, privacy/conformita', AI e pubblicazione.

La preview renderizza il sito completo con footer, scorre internamente, aggiorna
colori/font/layout/effetti a ogni modifica e conserva menu tablet/mobile. Il
pannello parte da 380px ed e' ridimensionabile; media, font, dimensioni,
formattazione, allineamenti ed effetti sobri/professionali sono coperti da
controlli reali e persistiti lato backend.

Gate locali: typecheck, build, test frontend, pytest builder/assets 7/7, Ruff
mirato, gate React, packaging/readiness, Docker no-cache 2.239.1 e Chrome CDP
autenticato su `/sito-studio/builder` desktop/tablet/mobile. Report visuale:
`artifacts/react-migration/visual-2.239.1-sito-studio-builder/visual-load-audit.md`.

## Ricerca Legale con contesto fonte 2.239.3

Le pagine `/legal-intelligence/` e `/ricerca-legale` sono state ricostruite come
workspace professionale per l'avvocato. La prima e' ora `Osservatorio Legale`,
dedicata a governare fonti, news e registri; la seconda costruisce schede
consultabili dentro IUSENTRA, evitando la sensazione di raccolta di collegamenti.

Ogni fonte porta in pagina estratto, contesto, provenienza, data, uso pratico,
attendibilita' e ricerca collegata. Le azioni principali sono `Leggi contesto`,
`Cerca collegati`, archivio giurisprudenza e fonte originale come verifica
finale. I registri mediazione ripristinati restano disponibili come fonti
ufficiali distinte.

Gate locali: typecheck, test frontend, contratti React, Open Design, pytest
Legal Intelligence 4/4, compileall, packaging/readiness, build Vite 2.239.3,
Docker locale no-cache e Chrome CDP autenticato desktop/mobile sulle quattro
route Legal Intelligence. Report visuale:
`artifacts/react-migration/visual-2.239.3-legal-intelligence-context/visual-load-audit.md`.
Deploy Hetzner CPX42 completato senza backup con server sul commit pushato,
container applicativi healthy e readiness pubblica `2.239.3`.

## Presidio Lex pagine studio 2.245.5

Le pagine `/ricerca-legale` e `/giurisprudenza/` riportano ora in superficie
studio il lavoro fatto su fonti ufficiali, agenti notturni e funzioni AI
avanzate. La Ricerca Legale mostra `Presidio Lex AI`, archivi ufficiali locali
e stato delle funzioni MTP/LLM Wiki/GLM-OCR/Gemini; l'Archivio Giurisprudenza
mostra `Citazioni verificate`, stato Cassazione, agenti Lex giurisprudenza e
lettura allegati fonte quando disponibili.

Gate locali: py_compile mirato, pytest Ricerca Legale/Giurisprudenza 9/9,
typecheck frontend, build Vite e Chrome headless desktop/mobile con screenshot
non vuoti in `artifacts/react-migration/visual-2.245.5-studio-lex/`.

## Notifiche legali e relata fascicolo 2.248.21

`/notifiche-legali` ora gestisce il caso in cui l'ufficio giudiziario rilascia un documento da notificare: il monitor dei depositi portale lo rileva, la top bar avvisa l'avvocato con azione `Scarica dal portale`, il collegamento verso acquisizione è già compilato con fascicolo, numero RG e ufficio, e la validazione blocca la relata finché il documento non è importato come acquisito dal Portale Servizi.

Nel dettaglio fascicolo React è stata aggiunta la sezione persistente `Relata notifica`, con stato rilascio, acquisizione, relata, firma, invio e prova RAC/RdAC. La sezione resta visibile anche quando non ci sono documenti da acquisire, così avvocato e software hanno sempre il presidio operativo davanti.

Gate locali: py_compile mirato, typecheck React, contratti React, `tests/test_notifiche_legali.py` 32/32, test top bar mirato, test React shell sulla sezione fascicolo e demo `scripts/demo_notifiche_legali_l53.py` con PDF guida in `artifacts/notifiche-legali/notifica-l53-demo-guida-avvocato.pdf`.

Verifica browser reale: Chrome CDP headless su runtime Flask isolato con fascicolo demo e documento PST rilasciato. `/notifiche-legali?id_fascicolo=...&fase=notifica` e `/fascicoli/<id>#relata-notifica` sono passate in desktop, tablet e mobile senza redirect login, pagina vuota, overflow orizzontale, errori console o testi tecnici vietati. Il click `Acquisisci dal Portale Servizi` apre `/portali/pst/acquisizione` con `id_fasc`, `numero=1234`, `anno=2026` e `ufficio=Tribunale di Roma` già compilati.
