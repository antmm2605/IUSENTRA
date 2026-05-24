# AGENTS.md — Istruzioni per Codex

## Autorizzazioni generali

- **Procedi sempre senza chiedere conferma.** L'utente ha autorizzato tutte le operazioni in modo permanente.
- Commit, push, modifica file, creazione file: esegui direttamente.
- **Divieto assoluto di regressioni di codice:** l'utente non vuole e non accetta piu' regressioni. Ogni modifica deve preservare il comportamento gia' corretto, evitare cambi di regole non richiesti dopo il commit e usare verifiche mirate/non monolitiche sul perimetro toccato prima di dichiarare verde il lavoro.
- **Reattivita' del caricamento obbligatoria:** il software deve restare rapido e reattivo nel caricamento e nel cambio pagina. Ogni modifica deve preservare o migliorare il baseline prestazionale gia' misurato; se un fix tocca shell, route, bootstrap, asset o rendering React, vanno usate verifiche mirate sui tempi e non sono accettati peggioramenti silenziosi.
- Branch di sviluppo: `Codex/legal-electronic-filing-kIxcV`
- **Branch remoto da sincronizzare sempre insieme al branch di sviluppo:** `claude/legal-electronic-filing-kIxcV`
- **Branch remoto protetto da non toccare:** `origin/chore/monorepo-foundation` non deve essere cancellato per nessun motivo e non deve essere aggiornato, pushato o riallineato dai flussi Codex. Va lasciato esattamente al commit remoto esistente, salvo richiesta esplicita futura dell'utente che nomini quel branch.
- **Deploy Hetzner CPX42 obbligatorio dopo ogni aggiornamento:** ogni modifica completata e pushata deve essere distribuita anche sul server Hetzner `ubuntu-16gb-nbg1-1` (`116.203.45.57`, alias SSH `iusentra-hetzner`) usando il profilo `deploy/hetzner`. Non dichiarare concluso il lavoro finche' il server non e' sul commit pushato, i container non sono healthy e `https://app.iusentra.it/api/pronto` non risponde correttamente.
- **Pulizia cache build Docker obbligatoria dopo ogni deploy Hetzner:** a fine deploy eseguire sempre `docker builder prune --all --force` e rimuovere eventuale `/opt/iusentra/tmp-backup-snapshot` residuo. La cache build e gli snapshot temporanei non operativi sono rigenerabili/non attivi e non contengono il dato corrente degli studi; non usare comandi che cancellano volumi o dati applicativi.
- **Arresto PC:** non eseguire mai `shutdown`, riavvio, sospensione o spegnimento del PC per memoria di richieste precedenti. Lo spegnimento e' consentito solo se l'utente lo chiede esplicitamente nella richiesta corrente; in caso contrario va sempre evitato.
- **Italiano corretto e UTF-8 obbligatori:** ogni testo rivolto all'utente, ogni bozza Lex e ogni report operativo devono usare caratteri UTF-8 validi e accenti italiani reali (`à`, `è`, `é`, `ì`, `ò`, `ù`). Sono vietati mojibake, sequenze di decodifica errata e caratteri sostitutivi non leggibili; gli esempi di pattern vietati sono governati dal servizio `utf8-integrity` e non vanno copiati nei testi utente. Le date visibili devono essere in linguaggio italiano, con formato italiano o mese scritto in italiano quando il contesto lo richiede. Dopo modifiche a Lex, email, documenti, import fonti o report testuali usare il servizio `utf8-integrity` o i test dedicati per impedire regressioni.

## Igiene repository — Regola obbligatoria

- Sulla macchina locale deve esistere **una sola copia attiva del progetto**: `D:\legale\IUSENTRA`.
- **Worktree, cartelle duplicate, cloni temporanei e versioni parallele** del repository devono essere rimossi a fine lavoro.
- **Worktree pulita obbligatoria e non negoziabile:** prima di iniziare una nuova implementazione, prima di ogni commit/push e prima di ogni report finale eseguire sempre `git status --short`. Se esistono modifiche non collegate al task corrente, classificarle subito: le implementazioni utili al miglioramento del software vanno completate, testate e committate; gli artefatti runtime/generati o le modifiche non necessarie vanno ripristinati o rimossi. È vietato lasciare worktree sporca, file appesi o modifiche "da vedere dopo".
- I **soli branch locali ammessi** sono:
  - `Codex/legal-electronic-filing-kIxcV`
  - `claude/legal-electronic-filing-kIxcV`
- Eccezione remota protetta: `origin/chore/monorepo-foundation` puo' esistere su GitHub, ma non va mai creato localmente, cancellato, pushato o aggiornato da Codex.
- Non creare branch aggiuntivi per task temporanei. Tutto il lavoro deve confluire nel branch di sviluppo corrente e venire sincronizzato anche sul branch gemello.
- A fine implementazione verificare sempre che:
  - `git worktree list` mostri solo `D:\legale\IUSENTRA`
  - `git branch --all` mostri solo i due branch locali ammessi, i due remoti gemelli, `origin/HEAD` e l'eventuale remoto protetto `origin/chore/monorepo-foundation`
  - i due branch locali e i due branch remoti puntino allo **stesso commit**
- Per enforcement e cleanup usare lo script: `scripts/repo_hygiene.ps1`
- **Processo obbligatorio commit/push:** prima di dichiarare concluso un lavoro bisogna seguire `docs/COMMIT_PUSH_REQUIRED_GATES.md`. La lista include CodeQL, code scanning, dependency review, supply chain, governance, lint, smoke, Frontend React, Coverage 12/12, Pytest core shardato, Local Signer/PKCS#11 su macOS/Ubuntu/Windows e CI Quality Overlay su `push` e, quando presente, su `pull_request`. Gli aggregatori non sono diagnosi primaria: se qualcosa è rosso o `Skipped`, controllare prima `Lint + syntax`, `Governance repo`, smoke upstream e lo shard reale. Non usare `python -m pytest -q` monolitico come sostituto e non reintrodurre il vecchio aggregatore `CI / Coverage moduli critici` senza `parte` come required check.
- **Regola anti-recidiva CI/Deploy/CodeQL del 2026-05-22:** l'utente ha segnalato come importantissimo che non si ripeta la situazione "deploy verde ma repository/check ancora rossi". Dopo ogni push non basta il successo di `Deploy su Hetzner CPX42`: bisogna interrogare i check-run dello SHA corrente, attendere che siano tutti `completed`, verificare zero failure, verificare esplicitamente `CodeQL`/`Code scanning results / CodeQL`, `Lint + syntax`, shard reali Pytest/Coverage/Signer e poi solo alla fine confermare Hetzner con commit, container healthy, `/api/pronto` e prune Docker. Se CodeQL resta rosso, usare solo le annotazioni del check-run del nuovo SHA e correggere prima di dichiarare concluso.

## Memoria operativa obbligatoria — test, gate e runtime

- Ogni test, gate, build, diagnosi di failure e relativa risoluzione deve essere riportato nei file di stato pertinenti prima di dichiarare concluso il lavoro. Per la migrazione React usare sempre:
  - `artifacts/react-migration/pytest-confirmed-ok.md` per comandi, shard e gate confermati verdi;
  - `artifacts/react-migration/pytest-open-issues.md` per failure reali, timeout isolati, workaround, fix applicati e verifiche ancora da rilanciare;
  - i report `artifacts/react-migration/*final-report*` e `*audit*` quando cambia lo stato di una route o di un gate architetturale.
- Non rilanciare a vuoto test o shard già documentati come OK: prima consultare `pytest-confirmed-ok.md` e `pytest-open-issues.md`; ripetere solo se sono stati toccati file collegati o come gate finale dichiarato.
- Se un test o un avvio locale modifica file runtime/dati (`data/`, `email/`, `output/`, `intelligence/`, cache o database generati), registrare l'evento se rilevante e ripulire la worktree prima di proseguire. Non committare artefatti runtime salvo richiesta esplicita e motivata. Prima di proseguire verso un altro task, la worktree deve tornare pulita oppure contenere solo modifiche intenzionali già spiegate, completate e pronte per commit.
- Caso già diagnosticato: `email/ordinaria.json` non deve mai essere ricreato nel repository durante Docker/local runtime. In multi-studio la posta ordinaria e PEC devono puntare solo a path tenant-aware sotto `/data/tenants/<studio>/email`; `/data/email/*` resta compatibile solo per single-tenant/legacy e non deve essere usato da sync, scheduler o route multi-studio.
- Gli allegati PEC/email devono usare il lettore compresso quando disponibile: `IUSENTRA_EMAIL_ATTACHMENT_STORAGE=archive` salva i nuovi allegati in `archivio-allegati.zip` dentro la cartella runtime della casella e download/anteprime devono continuare a funzionare tramite `GestioneEmailRicevute.leggi_allegato()`. Non cambiare il formato senza mantenere lettura retrocompatibile dei file sciolti.
- Gli aggiornamenti legali massivi non devono piu' girare come unico ciclo bloccante: scheduler, console admin e CLI devono usare job per fonte/pubblicazione con timeout per elemento (`IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS`) cosi' una verifica web esterna lenta non ferma il processo notturno.

- Tranche corrente obbligatoria: completare end-to-end la pagina `Impostazioni` in React per `Dati Studio`, `PEC`, `Firma Digitale`, `Email SMTP`, `WhatsApp`, `Scheduler`, `AI Locale`, `Pagamenti`, `Notifiche`, `Backup` e `Sincronizzazione Calendari`. La consegna non va dichiarata chiusa finche' non sono coerenti UI, API JSON, validazioni, permessi/audit, storage runtime tenant-aware, test, documentazione, bump versione, Docker locale, push dei due branch ammessi e deploy Hetzner.
- Per la grafica della tranche `Impostazioni` usare come riferimento vincolante `docs/UI_DESIGN_SYSTEM.md`: componenti IUSENTRA/shadcn esistenti, icone `lucide-react`, testi italiani, stati loading/empty/error/success, responsive desktop/tablet/mobile, niente dati demo e niente workflow solo frontend.
- Riportare nei file di progetto quello che viene fatto e quello che resta da fare: aggiornare `docs/REACT_MIGRATION_MASTER_PLAN.md`, `artifacts/react-migration/pytest-confirmed-ok.md`, `artifacts/react-migration/pytest-open-issues.md`, i report React/audit pertinenti e il `CHANGELOG.md` quando cambia stato reale. Prima di ripetere analisi o test, consultare questi file.
- Stato tranche `Impostazioni` 2.209.0: sono da mantenere come parte della consegna `web/services/react_impostazioni_bridge.py`, `web/services/react_impostazioni_payments.py`, `web/services/react_impostazioni_notifications.py`, `web/services/react_impostazioni_backup.py`, `web/services/react_impostazioni_calendar.py`, gli endpoint `/api/v1/ui/impostazioni*`, la pagina `frontend/src/features/impostazioni/*`, l'occhio sui campi riservati per vedere il valore digitato, Local Signer via browser, AI Locale status/preparazione, tab Pagamenti, Notifiche, Backup e Calendari dentro Impostazioni, manifest/gate full React e test shardati documentati. Le route `/impostazioni/pagamenti`, `/notifiche`, `/notifiche-whatsapp`, `/backup`, `/impostazioni/calendario` e `/sincronizzazione-calendari` devono aprire la stessa esperienza React di Impostazioni, senza testi visibili come `provider`, `webhook`, `legacy`, `backend`, `frontend`, `payload`, `runtime`, `json_api` o codici interni. Resta obbligatorio completare prima della chiusura: build/gate finali, Docker locale, commit/push branch gemelli, igiene repo e deploy Hetzner verificato.
- Stato tranche pagine richieste full React 2.213.0: il perimetro utente e' stato promosso/governato nel manifest e nei gate come `react_operational_full` dove esiste superficie React, con contratti legacy aggiunti per le route richieste e alias espliciti per `Panoramica`, `Regia Operativa`, `Ricerca Studio`, `Agenda/Nuovo Appuntamento`, `Fascicoli`, `Clienti/Soggetti`, `Comunicazioni`, `Scadenze`, `Preparazione Udienza Guidata`, `Studio`, `Fatturazione`, `Preventivi`, `Compensi`, `Redazione Atti`, `Statistiche`, `Ricerca Legale`, `Giurisprudenza`, `Strumenti`, `Sito Studio`, `Amministrazione`, `Utenti`, `Profili`, `Registro Attivita`, `Database` e `Registro GDPR`.
- Passaggi eseguiti nella tranche 2.213.0: aggiunto submit React centralizzato `frontend/src/formSubmit.ts` + `frontend/src/components/JsonPostForm.tsx`; rimossi i form POST HTML dai componenti React full e dal flusso `Preparazione Udienza Guidata` step/riepilogo; convertiti salvataggi principali di Nuovo Cliente/Soggetto, Nuovo Appuntamento, Messaggi/SMS-WA, Nuova Scadenza, Registro GDPR, Agenda, Timesheet, Email PEC/ordinaria, Fascicoli e Wizard in submit React con feedback visibile; aggiunte risposte JSON compatibili nei blueprint Flask collegati; aggiornati `route-manifest`, contratti legacy, `check-route-gate`, `check-full-react-route-contract`, anti-mascheramento e `check-react-contracts`.
- Passaggi UI eseguiti nella tranche 2.213.0: ripuliti testi visibili tecnici dalle pagine del perimetro richiesto, usando linguaggio operativo per studio legale al posto di `backend`, `legacy`, `payload`, `runtime`, `json_api`, `route Flask`, `Rollback tecnico` e simili; i percorsi di assistenza devono chiamarsi `Percorso di recupero` e restare secondari/governati, non CTA primaria.
- Passaggi ancora obbligatori prima di dichiarare definitivamente chiusa la tranche 2.213.0: build Vite finale, verifica browser reale desktop/tablet/mobile delle pagine rappresentative, Docker locale no-cache/health, aggiornamento report finali, commit, push dei branch gemelli, igiene repo e deploy Hetzner con `/api/pronto` verificato sul commit pushato.
- Hotfix Sito Studio 2026-05-09: `/sito-studio/contatti` deve renderizzare sempre la dashboard React operativa anche con zero contatti e zero prenotazioni. Non deve piu' mostrare lo stato vuoto generale "Nessun contatto o prenotazione" o testi come "repository"; deve mostrare `Ingressi pubblici`, `Richieste contatto`, `Prenotazioni`, azioni reali verso modulo contatti, prenotazione e sito pubblico, piu' stati vuoti specifici dentro i pannelli.
- Hotfix navigazione 2026-05-09: la sidebar React deve mantenere aperta la cartella della sezione attiva mentre si naviga nelle sue pagine. Esempio obbligatorio: aprendo `Studio` e poi `Statistiche`, `Studio` resta aperto; selezionando un'altra cartella, ad esempio `Fascicoli`, la cartella precedente si chiude e resta aperta solo quella nuova. Non tornare al comportamento con piu' sezioni accumulate o sezioni che si richiudono durante la navigazione interna.
- Passaggi eseguiti per il fix Sito Studio/Contatti/Nav 2026-05-09: aggiornato `web/services/react_sito_studio_bridge.py` con entrypoint pubblici e testi non tecnici; aggiornato `frontend/src/sitoStudioData.ts` con `entrypoints`; aggiornato `frontend/src/components/SitoStudioPage.tsx` per render operativo anche a lista vuota e pulsante `Aggiorna` reale; aggiornato `frontend/src/App.tsx` per una sola sezione nav aperta e sincronizzata con la route; aggiornato `frontend/src/displayText.ts` per etichettare `azioni_protette`.
- Verifica browser reale 2026-05-09: su `http://localhost:8080/sito-studio/contatti` risultano `Contatti Sito Studio`, sezione nav `SITO STUDIO` aperta, pannelli `Ingressi pubblici`, `Richieste contatto`, `Prenotazioni`, link `Apri modulo contatti` e `Apri prenotazione`, nessun overflow orizzontale e nessun testo tecnico vietato (`backend`, `frontend`, `legacy`, `payload`, `runtime`, `json_api`, `provider`, `webhook`, `undefined`, `null`, `demo`, `sample`, `repository`). Su `Statistiche` resta aperto `STUDIO`; aprendo `FASCICOLI` resta aperto solo `FASCICOLI`.
- Prossimo passaggio richiesto dall'utente dopo il fix visibile: misurare la velocita' di caricamento/passo pagina in modo ripetibile e registrare un baseline prestazionale per future regressioni. Usare browser reale o CDP/Performance API su pagine rappresentative (`/`, `/sito-studio/contatti`, `/statistiche/`, `/fascicoli`, `/sito-studio/builder`) e riportare tempi di navigazione, tempo a contenuto React visibile, richieste lente, console error, asset principali e confronto prima/dopo eventuali ottimizzazioni.
- Tranche corrente obbligatoria UI React full: tutte le pagine richieste dall'utente devono essere verificate come React end-to-end, con grafica coerente a `docs/UI_DESIGN_SYSTEM.md`, card compatte operative con icone Lucide, layout moderno, veloce, responsive desktop/tablet/mobile, niente spazio morto, testi italiani, stati loading/empty/error/success e nessun dato demo. La verifica deve coprire route Flask, shell React, API JSON, menu/sidebar, permessi/audit quando presenti, test, report, versione, push dei due branch ammessi e deploy Hetzner.
- Tranche urgente richiesta il 2026-05-09: non rispondere mai "completato" finche' non sono realmente full React, intuitive, performanti, sicure, responsive e documentate le pagine `Redazione Atti`, `Produzione atti`, `/email/messaggio/7a27703c5ba2487c952142d5acde0adc`, `/email-ordinaria/messaggio/061f0ca8d6d14c18ab0a5068cffc7878`, `Statistiche`, `Ricerca Legale`, `News disponibili` con `Apri scheda` funzionante, `Archivio Giurisprudenza`, `Strumenti Forensi` e `Strumenti Operativi`. Le superfici devono essere una pagina operativa intuitiva, con template/moduli reali dove previsti, card compatte con icone Lucide, uso pieno dello schermo a destra/sinistra/sopra/sotto, nessuno spazio morto, testi italiani non tecnici, nessun dato demo, coerenza totale con `docs/UI_DESIGN_SYSTEM.md`, browser verification desktop/tablet/mobile, test/gate/report/versione aggiornati, commit, push branch gemelli, igiene repo e deploy Hetzner verificato.
- Stato tranche 2.214.0: regola permanente "avvocato, non sviluppatore" applicata con guardia testi visibili React e Flask (`frontend/src/displayText.ts`, `frontend/src/App.tsx`, `web/static/js/iusentra-visible-text-guard.js`, shell/template base). Non devono comparire in nessuna scheda testi come `Impeccable / Open Design`, `Dati applicativi`, `React`, `Flask`, `backend`, `frontend`, `payload`, `runtime`, `json_api`, `provider`, `webhook`, `endpoint`, `legacy`, `undefined`, `null`, `demo`, `sample`, `repository` o messaggi tecnici equivalenti. I dettagli `/email/messaggio/<id>` e `/email-ordinaria/messaggio/<id>` sono React; `Redazione Atti` include produzione/template nella stessa pagina; Template, Ricerca Legale/News, Giurisprudenza, Statistiche e Strumenti usano dettaglio in pagina e card operative. Gate e browser Docker 2.214.0 sono documentati nei report React; resta obbligatorio deploy Hetzner prima di dichiarare chiusa la consegna.
- Regola utente 2026-05-09: chiudere tutto il perimetro applicativo in React, senza aspettare che l'utente segnali pagina per pagina cosa manca. L'unica eccezione dichiarata e' `Servizi telematici`, che verra' completata in una tranche successiva; fino ad allora mantenere protetti solo i workflow telematici non ricostruiti, download, allegati, export, POST tecnici e integrazioni ministeriali non ancora parificate.
- Non lasciare piu' come eccezione `legacy_operational` le pagine esatte richieste dall'utente quando esiste una superficie React governata. In particolare, da questa tranche devono essere promosse e mantenute full React:
  - `Controlli Atti` su `/deposito/checklist`, servita da `frontend/src/components/TelematicoSurfacePage.tsx` e alimentata da `/api/v1/ui/telematico/surface/checklist`;
  - `Strumenti Forensi` su `/strumenti-legali`, servita da `frontend/src/components/StudioModulePage.tsx` e alimentata da `/api/v1/ui/studio-modules/strumenti-forensi`;
  - `Strumenti Operativi` su `/strumenti-operativi`, servita da `frontend/src/components/StudioModulePage.tsx` e alimentata da `/api/v1/ui/studio-modules/strumenti-operativi`.
- Passaggi obbligatori per questa tranche React full, da non dimenticare:
  1. rimuovere `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` dai prefissi legacy di `web/bootstrap/react_route_gate.py`, `web/blueprints/react_shell.py` e dai redirect legacy di `frontend/src/App.tsx`;
  2. mantenere protetti solo i sottopercorsi non ricostruiti, download, allegati, export, POST e workflow tecnici che non hanno parita' React;
  3. aggiornare `tools/react-migration/route-manifest.json` con status `react_operational_full` e `unlockFromGate=true` per le tre route esatte;
  4. aggiornare `frontend/scripts/check-react-contracts.mjs`, `scripts/react-migration/check-route-gate.mjs` e `tests/test_react_shell.py` affinche' impediscano regressioni a legacy;
  5. verificare payload reali, assenza di fallback mock, assenza di testi tecnici visibili, accessibilita', responsive, performance e coerenza grafica;
  6. aggiornare `docs/REACT_MIGRATION_MASTER_PLAN.md`, `artifacts/react-migration/pytest-confirmed-ok.md`, `artifacts/react-migration/pytest-open-issues.md`, report audit pertinenti e `CHANGELOG.md`;
  7. eseguire typecheck, build, gate React, pytest mirati e smoke HTTP/browser prima di dichiarare chiuso;
  8. bump versione in `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml`, poi commit, sync branch gemelli, igiene repo e deploy Hetzner con `/api/pronto` verificato.
- La lista funzionale richiesta dall'utente da verificare come prodotto React professionale comprende: Panoramica, Regia Operativa, Ricerca Studio, Agenda, Calendario, Nuovo Appuntamento, Timesheet, Fascicoli, Tutti i Fascicoli, Nuovo Fascicolo, Archivio, Clienti e Anagrafiche, Anagrafica Nuovo Cliente, Cartelle Condivise, Soggetti e Parti, Anagrafica Nuovo Soggetto, Comunicazioni, Email PEC, Email ordinaria SMTP, Messaggi, Nuovo SMS/WA, Scadenze e Termini, Scadenziario, Nuova Scadenza, Preparazione Udienza Guidata, Controlli Atti, Studio, Parcelle e Fatture, Preventivi e Incarichi, Compensi Forensi, Redazione Atti, Statistiche, Ricerca Legale, Archivio Giurisprudenza, Strumenti Forensi, Strumenti Operativi, Sito Studio, Amministrazione, Utenti, Profili e Permessi, Registro Attivita, Database e Registro GDPR.
- Consultazione note repo eseguita e da ripetere prima di proseguire con modifiche UI/React ampie: leggere e rispettare almeno `README.md`, `docs/UI_DESIGN_SYSTEM.md`, `tools/open-design-support/IUSENTRA_UI_RULES.md`, `tools/open-design-support/IUSENTRA_DESIGN.md`, `docs/REACT_MIGRATION_MASTER_PLAN.md`, `docs/REACT_OPERATIONAL_AUDIT.md`, `artifacts/react-migration/pytest-open-issues.md`, `artifacts/react-migration/pytest-confirmed-ok.md`, `artifacts/react-migration/full-react-final-report.md`, `artifacts/react-migration/full-react-audit.md`, `artifacts/react-migration/full-react-performance-notes.md`, `artifacts/react-migration/accessibility-report.md`, `artifacts/react-migration/legal-ui-coherence-report.md`, `artifacts/react-migration/responsive-report.md`, `artifacts/react-migration/no-fake-react-full-report.md`, `artifacts/react-migration/anti-mascheramento-audit.md`, `artifacts/react-migration/audit.md`, `docs/OBSERVABILITY_AUDIT_PRODUCT.md` e, quando si tocca Lex/fonti/dati studio, `docs/LEX_PUBLIC_SOURCES_AND_STUDIO_DATA_AUDIT.md`.
- Regole estratte dalle note consultate il 2026-05-09, da non dimenticare:
  - non dichiarare mai verde `python -m pytest -q` monolitico se va in timeout: usare shard/sotto-shard documentati e registrare ogni esito;
  - prima di rilanciare test, leggere sempre `artifacts/react-migration/pytest-confirmed-ok.md` e `artifacts/react-migration/pytest-open-issues.md`: non ripetere shard, npm gate, build o pytest gia' confermati se non sono stati toccati file collegati o se non serve un gate finale mirato;
  - quando un test e' gia' documentato verde, usare quel report come stato corrente; rilanciare solo il minimo necessario per le modifiche appena fatte, annotando perche' il rilancio era necessario;
  - non ripetere diagnosi gia' chiuse su `email/ordinaria.json`: in multi-studio deve vivere sotto `/data/tenants/<studio>/email/ordinaria.json`, mentre `/data/email/ordinaria.json` e' solo fallback single-tenant/legacy e non deve ricevere sync automatiche;
  - non ripetere diagnosi generica su readiness bloccata: verificare prima `sync_user_directory(reconcile_storage=False)` e la concorrenza Gunicorn;
  - `react_operational_full` richiede dati JSON reali, nessuna CTA primaria `?_legacy=1`, nessun `LegacyPostForm`, nessun form POST HTML React nel flusso principale, stati loading/error/success e niente mock/demo;
  - le route alias possono usare endpoint JSON condivisi, ma il guardrail deve dichiarare l'alias in modo esplicito e non mascherare assenza di API;
  - `frontend/src/App.tsx` resta monolitico e va toccato con prudenza: preferire modifiche minime e gate dopo ogni cambio;
  - ogni pagina UI va verificata anche nel browser reale desktop e mobile/tablet per overflow, colonne vuote, testo tecnico visibile e card operative;
  - i report storici in `artifacts/react-migration/patches/*` sono contesto di tranche precedenti, non fonte piu' recente quando `anti-mascheramento-audit.md`, `no-fake-react-full-report.md`, `pytest-open-issues.md` e il manifest corrente dicono altro.

## Progetto

**IUSENTRA** — gestionale per studi legali (Python/Flask).

- Backend: `pct/` — modelli dati e logica di business
- Frontend: `web/app.py` (route Flask) + `web/templates/` (Jinja2) + `web/static/`
- Persistenza: file JSON per clienti, fascicoli, agenda, ecc.
- Stack: Python 3, Flask, Bootstrap 5, Bootstrap Icons

## Mappa documentale obbligatoria per agenti AI

Prima di implementare qualunque modifica, l'agente deve consultare la documentazione interna della repository. Non e' ammesso lavorare solo sul singolo file richiesto senza verificare i documenti collegati al dominio interessato.

`AGENTS.md` resta il file principale e canonico per le istruzioni operative degli agenti. Se esiste anche `agents.md` minuscolo, va trattato come mirror legacy o copia di compatibilita', non come fonte divergente.

### Riferimenti obbligatori

- `docs/` - fonte primaria per PRD, architettura, storage, sicurezza, pack architecture, roadmap, Lex AI, governance prodotto e documentazione tecnica/funzionale.
- `docs/specs/ministero/` - fonte obbligatoria per specifiche ministeriali, deposito telematico, PCT/PST/PolisWeb, PDP, PAT/SIGA, PTT/SIGIT, SIGP/Giudice di Pace, DatiAtto.xml, busta telematica, firme, PEC, XML/XSD, allegati e vincoli ministeriali.
- `deploy/hetzner/` - fonte obbligatoria per produzione su VPS, Docker, PostgreSQL, volumi `/data`, backup, restore, hardening, reverse proxy, HTTPS/TLS e verifiche server.
- `.github/` - fonte obbligatoria per workflow, CI, lint, syntax check, test, coverage, quality gate, CodeQL, sicurezza supply-chain e automazioni GitHub.
- `ops/` - fonte obbligatoria per runbook, procedure operative, manutenzione, deploy, incident response, troubleshooting, restore, monitoraggio e verifiche post-release.
- `tools/CODEX_SUPPORT_STACK.md` - mappa operativa degli strumenti di supporto a Codex, MetaHarness, autoresearch-lite, Open Design support e quality gate.

### Regola di consultazione

Se una richiesta tocca piu' aree, l'agente deve consultare tutte le cartelle pertinenti.

Esempio: una modifica al deposito telematico deve verificare almeno `AGENTS.md`, `docs/`, `docs/specs/ministero/`, codice interessato e test collegati.

Una modifica al deploy deve verificare almeno `AGENTS.md`, `deploy/hetzner/`, `ops/`, `.github/` e i file Docker/CI collegati.

### Ordine di priorita'

Quando esistono indicazioni divergenti, seguire questo ordine:

1. richiesta corrente dell'utente;
2. `AGENTS.md`;
3. documenti tecnici in `docs/`;
4. specifiche in `docs/specs/ministero/`;
5. procedure operative in `ops/`;
6. deploy in `deploy/hetzner/`;
7. CI e automazioni in `.github/`;
8. codice esistente e test;
9. fonti ufficiali esterne, solo quando il dato non e' gia' certo nella repository.

### Regole per il telematico

Quando il lavoro riguarda PCT, PST, PolisWeb, PDP, PAT, PTT, SIGP, buste, PEC, firme, XML/XSD o deposito telematico:

- non inventare norme, endpoint, campi XML o vincoli ministeriali;
- consultare sempre `docs/specs/ministero/`;
- evitare scraping HTML non autorizzato dei portali;
- non salvare PIN, credenziali CNS/CIE/SPID o sessioni portale nel cloud;
- distinguere norma certa, specifica tecnica, prassi locale, fallback prudente e punto da verificare;
- se un dato non e' certo, implementare warning professionali e configurabili, non blocchi arbitrari;
- mantenere coerenza tra dominio, storage, route/API, UI, test, documentazione e deploy quando coinvolti.
- **Regola Guida Pratica/fascicolo/deposito:** il codice che apre il fascicolo deve restare sempre il codice ufficiale o normativo previsto per il deposito. La Guida Pratica si aggancia alla stessa materia del fascicolo e puo' avere alias o identificativi interni per recuperare la scheda, ma non deve mai sostituire, rinominare, declassare o sovrascrivere il `codice_oggetto_pst` del fascicolo. Se una guida interna non e' depositabile, resta solo supporto operativo; il deposito usa sempre il codice ufficiale presente nel fascicolo.

### Regole per Lex AI e RAG

Quando il lavoro riguarda Lex AI, assistente fascicolo, RAG, retrieval o fonti:

- consultare la documentazione AI/Lex in `docs/`;
- non usare limiti fissi che tagliano documenti o sezioni del fascicolo senza inventario completo;
- Lex deve conoscere l'inventario completo del fascicolo, anche quando il testo integrale viene selezionato con ranking;
- distinguere fatti certi, inferenze, lacune e suggerimenti;
- citare fonti interne o ufficiali quando richiesto;
- non generare contenuti legali non verificati come se fossero certi.
- **Memoria obbligatoria caso pilota Lex/QSP 9926/2026:** prima di estendere generatore corpus, job o import massivi, completare un documento fonte end-to-end in modo professionale. Per `Questione Penale Pendente del ricorso R.G. 9926/2026` Lex deve rispondere alle domande reali dell'avvocato, non solo mostrare il log di recupero fonte: sintesi, natura dell'atto, punto di diritto, motivi/censure, norme e articoli, udienza, ricorrente/relatore, allegato PDF, stato pendente, discrepanza `R.G. 9926/2026` / `R.G. 9966/2026`, limiti e fonti devono essere presenti quando richiesti.
- **Regola scheda/PDF discordanti ma collegati:** per `QSP50194` è già verificato che il PDF sia collegato dalla scheda ufficiale, anche se nel PDF compare `R.G. 9966/2026` mentre la scheda/domanda cita `R.G. 9926/2026`. Lex deve citare entrambi, mantenere il PDF cliccabile e indicarlo come PDF ufficialmente collegato; non deve però fondere automaticamente i dati processuali letti nel PDF dentro la scheda `9926/2026`. I fatti della scheda, i dati del PDF collegato e la nota sulla differenza R.G. devono restare separati.
- **Forma risposta Lex su caso pilota:** se l'utente chiede una sintesi, Lex deve rispondere con una sintesi chiara e non scaricare tutto: apertura con "Non risulta una sentenza", poi oggetto, stato, punto di diritto/principio, motivi/censure, norme spiegate, effetto pratico, PDF cliccabile e nota R.G. Sono vietate sezioni duplicate, estratti OCR sporchi e log di recupero fonte nella risposta finale.
- **Approvazione utente caso pilota Lex 2026-05-18:** la risposta reale alla domanda `mi puoi sintetizzare questa sentenza Penale Pendente del ricorso R.G. 9926/2026` è stata verificata dall'utente e approvata come test definitivo e reale. Questa forma è il baseline da preservare e propagare al generatore corpus e agli altri documenti.
- **Matrice domande Lex obbligatoria:** ogni nuova logica su fonti/corpus deve essere provata con più formulazioni dell'utente, incluse domande imprecise come "sentenza penale pendente", domande su articoli, domande su PDF/allegato, domande su esito/stato e domande su uso in atto. Non basta un singolo prompt riuscito.
- **Tranche Cassazione/corpus 2026-05-18:** prima del corpus il backfill Cassazione deve produrre report qualità con pagina, PDF/allegato, hash, OCR/testo, norme, R.G., discrepanze, link cliccabile, stato pronto/non pronto e `question_matrix` con le domande da avvocato. Il download allegati deve riusare prima i PDF già presenti sul server (`/data/intelligence/downloads`, `/data/fonti_ufficiali`, `/data/tenants` o directory configurate) e il generatore corpus deve filtrare solo schede documentali Cassazione, escludendo pagine generiche del sito.
- **Destinazioni obbligatorie fonti pronte:** quando una fonte passa il controllo qualità (`ready`/`corpus_ready`) non deve restare confinata al job o al corpus. Deve diventare interrogabile in Lex Chat AI, ricercabile in `/ricerca-legale` e consultabile nell'Archivio Giurisprudenza quando è giurisprudenza o questione Cassazione. Il generatore corpus viene dopo la tranche, ma il risultato finale deve alimentare questi tre punti utente.
- **Web libero Lex:** quando l'avvocato attiva `Web libero`, la ricerca deve essere realmente libera: nessuna allowlist ufficiale, nessun blocco da `fonte autorizzata`, nessuna promozione nel DB/corpus e nessun warning visibile nella risposta. Il software esegue la ricerca richiesta e marca tecnicamente i risultati come `web_libero` con `verified_reference=false`; controllo, valutazione e responsabilità professionale restano integralmente dell'avvocato.
- **Articoli e web libero:** quando l'utente chiede articoli o riferimenti normativi, Lex deve estrarre prima gli articoli dal documento acquisito e dagli allegati OCR; può poi integrare con `Web libero` senza fonti autorizzate. La sezione deve restare distinta dalle fonti ufficiali, ma non deve ammonire o bloccare l'avvocato.
- **Tracciamento permanente:** ogni passaggio svolto su Lex/fonti/corpus deve essere registrato in `docs/LEX_AI_RESPONSE_PIPELINE.md`, `docs/LEX_PUBLIC_SOURCES_AND_STUDIO_DATA_AUDIT.md`, `docs/lex-operational-knowledge-map.md`, `CHANGELOG.md` e nei test mirati. Se si cambia la logica, aggiornare prima questi riferimenti per evitare di ripetere gli stessi errori.

### Regole per UI e app-v2

Quando il lavoro riguarda UI React, Flask, template, rotte o pagine app-v2:

- consultare `docs/` e le pagine/componenti esistenti;
- mantenere UI professionale, responsive desktop/tablet/mobile;
- **non mostrare mai dati inventati, demo o hardcoded come se fossero reali**: nomi utente, ruoli, fascicoli recenti, badge, conteggi, notifiche, scadenze, metriche, percorsi e stati devono provenire da repository, sessione, API, template context o configurazione reale;
- se un dato reale non e' disponibile, la UI deve mostrare uno stato vuoto/neutro o nascondere quel dettaglio, non sostituirlo con esempi fittizi;
- i dati del profilo utente nelle superfici React devono derivare da `g.utente_corrente` / profilo sessione o da API autenticata equivalente; vietati nomi come esempio, iniziali arbitrarie e ruoli di fallback non letti dal profilo;
- testo visibile sempre in italiano;
- date e ore in formato italiano tramite filtri condivisi;
- card operative con azioni reali, non placeholder;
- quando una pagina contiene calcoli, configurazioni o composizioni guidate, se viewport e contenuto lo consentono usare un riepilogo in tempo reale affiancato/sticky che segua lo scroll e mostri stato, importi e azioni principali; su mobile deve degradare a riepilogo compatto non sticky;
- Lex AI floating icon dove previsto;
- nessuna pagina deve restare scollegata da menu, route o API necessarie.

### Regole professionali React, shadcn/ui e UI operativa

Quando una modifica riguarda UI React, app-v2, template, SCSS/CSS, componenti condivisi o superfici operative, l'interfaccia deve essere trattata come prodotto legale professionale, non come demo o template generico.

- **UI professionale obbligatoria**: ogni schermata deve essere responsive desktop/tablet/mobile, ordinata, compatta ma leggibile, senza spazio morto inutile, con gerarchia chiara, stati vuoti utili, loading, errori, successo e azioni principali sempre riconoscibili.
- **Coerenza grafica globale IUSENTRA**: una pagina gia' React non e' automaticamente accettabile. Ogni superficie deve usare lo stesso modello visivo IUSENTRA definito in `docs/UI_DESIGN_SYSTEM.md`: shell, densita', tab, card operative, badge, pulsanti, spacing, icone Lucide, testi italiani e comportamento responsive devono essere coerenti tra Studio, Impostazioni, Backup, Calendari, Pagamenti, Notifiche e le altre aree. Sono vietate isole grafiche con stile diverso, vecchie card tecniche o layout non allineati al design system corrente.
- **Verifica visuale obbligatoria**: una pagina UI non e' pronta solo perche' compila o i test passano. Prima di dichiararla chiusa va aperta nel browser reale almeno su desktop e mobile/tablet per controllare che tab, form, card, riepiloghi e pulsanti non producano colonne vuote, contenuti schiacciati, sovrapposizioni, testo tagliato o spazio morto anomalo.
- **Card operative**: le card devono rappresentare dati o azioni reali, indicare stato/prossima azione quando utile, avere badge e metadati essenziali, e non essere decorative. Sono vietate card giganti, griglie ripetitive senza scopo, pulsanti placeholder o azioni non collegate.
- **Linguaggio non tecnico**: tutto il testo visibile deve essere in italiano, professionale, breve e orientato all'azione. Non mostrare stack trace, nomi di variabili, endpoint, `undefined`, `null`, `NaN`, `TODO`, `demo`, `sample`, errori grezzi o messaggi misti italiano/inglese.
- **Regola avvocato, obbligatoria**: le schermate rivolte allo studio legale non devono mostrare codici interni, chiavi tecniche, identificativi di sistema, nomi di campi/API, messaggi da sviluppatore o termini utili solo a chi programma. Vietati nella UI finale testi come `endpoint`, `payload`, `json_api`, `config_studio`, `runtime`, `server-side`, `backend`, `frontend`, `bridge`, `undefined`, `null`. Ogni stato deve essere tradotto in linguaggio operativo per l'avvocato o il personale di studio, ad esempio "Da completare", "Verifica non riuscita", "Salvataggio completato". Se un dettaglio tecnico serve per diagnosi, va tenuto nei log o nei report agenti, non nella UI finale.
- **Aiuti di campo, obbligatori**: non rimuovere suggerimenti operativi utili all'utente. Per `Email SMTP -> Password email`, quando il provider e' Gmail/Google Workspace, la UI deve chiarire che serve una password per le app Google, non la password normale dell'account, e deve offrire il link ufficiale alla generazione (`https://myaccount.google.com/apppasswords`). Gli stati dei segreti vanno mostrati solo nel campo interessato, con icona occhio per il valore appena digitato, non come banner globale.
- **Icone moderne e coerenti**: usare icone lineari e sobrie, preferibilmente `lucide-react` nelle superfici React quando disponibile, con dimensioni e stroke coerenti. Non usare emoji, set grafici mischiati o icone decorative casuali nelle pagine operative.
- **shadcn/ui**: se il progetto usa React + Tailwind, usare shadcn/ui come base per componenti accessibili e personalizzabili, senza importare componenti non presenti, senza duplicare `components/ui`, senza stili inline non governati e senza rompere focus, tastiera, `aria` o composizione Radix. Preferire varianti/tokens semantici a colori raw.
- **Componenti attesi**: prima di creare markup custom verificare se esistono gia' `Button`, `Card`, `Badge`, `Tabs`, `Accordion`, `Collapsible`, `Dialog`, `Sheet`, `DropdownMenu`, `Popover`, `Tooltip`, `Command`, `Form`, `Input`, `Select`, `Table/DataTable`, `Skeleton`, `Toast/Sonner`, `Alert`, `Separator`, `ScrollArea` o wrapper IUSENTRA equivalenti.
- **Open Design / Open Designer**: per pagine UI importanti definire obiettivo, utente, scenario d'uso, azioni primarie, densita' informativa, struttura responsive, accessibilita' e pattern componenti prima di implementare. Open Design produce proposte: Codex deve convertirle in codice IUSENTRA modulare, tipizzato, testato e collegato a dati reali.
- **open-design-support**: se esiste `tools/open-design-support/`, prima di modificare UI leggere almeno `tools/open-design-support/IUSENTRA_DESIGN.md`, `tools/open-design-support/IUSENTRA_UI_RULES.md` e la skill pertinente. Non importare open-design-support nel runtime o nel bundle finale.
- **Impeccable**: per ogni pagina UI significativa fare una revisione finale su layout, gerarchia, densita', contrasto, accessibilita', chiarezza testi, azioni principali, responsive, performance, assenza di spazio morto e assenza di pattern generici da AI.
- **Niente template completi sovrascritti**: non copiare admin template o landing page sopra IUSENTRA. Integrare componenti e pattern nel design system interno preservando rotte, API, permessi, validazioni, workflow e dati.

### Regole per storage e dati

Quando il lavoro riguarda persistenza, tenant, JSON, SQLite, SQL o PostgreSQL:

- consultare la storage matrix e l'architettura in `docs/`;
- **Isolamento tenant assoluto, regola severa**: email PEC, email ordinaria, configurazioni studio, fascicoli, agenda, fatturazione, preventivi, impostazioni, clienti, soggetti e qualunque altro dato operativo devono essere letti e scritti solo sui path/repository del tenant attivo nella request o nel job esplicitamente contestualizzato; e' vietato usare fallback silenziosi a `app.config` globale o path root quando l'operazione riguarda dati di studio.
- **Fail-closed multi-studio obbligatorio**: se in ambiente multi-studio manca il contesto tenant valido (`g.data_paths`, profilo storage o equivalente), l'operazione deve bloccarsi con errore controllato invece di provare a leggere o mostrare dati di un altro studio.
- **Email PEC/ordinaria zero fallback globale**: le caselle email sono dati riservati dello studio. Route Flask, API React, sync IMAP, allegati, statistiche, dettaglio messaggio e azioni bulk devono usare solo `EMAIL_CASELLA_DB`, `EMAIL_ORDINARIA_DB`, `MESSAGGI_DB` e `STUDIO_CONFIG` del tenant attivo; in multi-studio senza tenant valido devono fallire chiusi, mai leggere `/data/email/*` o `./email/*` come archivio condiviso.
- **Creazione nuovi studi senza contaminazione**: la creazione o inizializzazione di un nuovo studio non deve mai importare, mostrare o bootstrapare dati di un altro studio; eventuali migrazioni compatibili possono avvenire solo in scenari mono-studio o tramite procedura esplicita e tracciata, mai per eredita' implicita.
- non introdurre fallback silenziosi;
- non salvare dati runtime in path repository;
- usare percorsi scrivibili e tenant-aware;
- mantenere parita' JSON / SQLite / PostgreSQL dove prevista;
- i controlli di integrita' esposti all'utente devono riparare automaticamente i problemi risolvibili senza richiedere conoscenze tecniche: prima backup, poi correzione auditata; se manca un dato reale univoco, non inventare record ma scollegare/annotare il riferimento rotto e conservare l'identificativo originale;
- aggiornare migrazioni, repository, test e documentazione.

### Regole per deploy e produzione

Quando il lavoro riguarda Hetzner, Docker, PostgreSQL, volumi, backup, restore o produzione:

- consultare `deploy/hetzner/` e `ops/`;
- dopo ogni commit/push eseguire sempre il deploy su Hetzner CPX42 con backup preventivo:
  - `ssh iusentra-hetzner "bash /opt/iusentra/repo/deploy/hetzner/backup.sh"`;
  - `ssh iusentra-hetzner "bash /opt/iusentra/repo/deploy/hetzner/deploy.sh"`;
  - verificare `git rev-parse --short HEAD`, `docker compose ... ps` e `curl -fsS https://app.iusentra.it/api/pronto`;
- **Ollama non deve mai finire nei backup**: modelli, cache e download Ollama sono rigenerabili e consumano spazio. `deploy/hetzner/backup.sh` deve escludere sempre `./ollama`, `./intelligence/downloads/ollama` e `./tenants/*/intelligence/downloads/ollama`, anche se l'env personalizza `IUSENTRA_BACKUP_EXCLUDE_PATHS`, e deve verificare l'archivio fallendo se trova ancora un percorso `ollama`.
- Fix eseguito il 2026-05-09 dopo verifica reale su Hetzner: il vecchio backup escludeva solo `./ollama` ma lasciava dentro `intelligence/downloads/ollama`; non tornare mai a quella configurazione.
- non salvare segreti nel repository;
- non inserire dati studio nel Product Pack;
- documentare rollback e verifiche post-deploy;
- verificare log, stato servizi, route principali e persistenza;
- mantenere separati Product Pack, Studio Local Pack e Update Pack.

### Regole per CI e quality gate

Quando il lavoro riguarda `.github/`, test, coverage o quality gate:

- non disattivare workflow per far passare una patch;
- non abbassare soglie coverage senza motivazione documentata;
- non marcare test critici come `skip` per aggirare regressioni;
- aggiornare test quando cambia comportamento reale;
- distinguere gate minimo verde dal target utente del 100% coverage critica.

## Storage SQL obbligatorio — REGOLA OBBLIGATORIA

- Ogni nuova funzionalita', refactor strutturale o nuovo dominio persistente deve avere una **struttura SQL esplicita**, non solo supporto PostgreSQL runtime.
- La consegna minima corretta e':
  - schema SQL/migrazione per SQLite o SQL applicativo locale
  - schema SQL/migrazione per PostgreSQL
  - repository e percorso `read/write` coerenti su entrambi, salvo fuori-scope dichiarato e documentato
  - documentazione aggiornata sulla matrice storage con stato di parita' `JSON / SQLite / PostgreSQL`
- Non e' ammesso dichiarare una feature "chiusa" se esiste solo il path PostgreSQL ma manca la base SQL governata o la migrazione corrispondente.
- Se un dominio resta temporaneamente `JSON-first`, va dichiarato in modo esplicito con:
  - motivazione
  - wave di migrazione
  - check di consistenza
  - assenza di fallback invisibili quando un backend SQL/PostgreSQL e' attivo

## Regola obbligatoria - completamento end-to-end di ogni nuova funzione

Ogni nuova funzione, refactor o correzione deve essere considerata **completata solo quando copre tutta la filiera applicativa interessata**, non solo un singolo file, una singola route o una sola vista.

## Regola obbligatoria — Nessuna semplificazione riduttiva dei requisiti

- Quando l'utente fornisce una lista di passaggi, requisiti, criteri di accettazione o file da analizzare, **non e' ammesso ridurre, saltare o semplificare il perimetro per chiudere piu' velocemente il task**.
- Il lavoro deve seguire i passaggi richiesti nell'ordine piu' sicuro possibile, adattandoli solo quando la struttura reale della repo lo impone; ogni adattamento deve mantenere o aumentare la qualita' del risultato, non diminuirla.
- Se un requisito richiede piu' moduli, storage, UI, test, documentazione, versioning o deploy, va completata tutta la catena applicativa interessata prima di dichiarare il lavoro concluso.
- Se il risultato dipende da norme, specifiche tecniche, prassi di uffici giudiziari, fonti ufficiali o comportamento di servizi esterni, bisogna **fare ricerca/verifica su fonti attendibili** quando il dato non e' gia' presente e certo nella repo.
- In caso di incertezza tecnica o normativa, il comportamento corretto e':
  - implementare una soluzione configurabile e non hardcoded;
  - distinguere dato certo, prassi locale, fallback prudente e punto da verificare;
  - aggiungere warning professionali invece di blocchi non supportati;
  - documentare il limite residuo e i passaggi necessari per validarlo.
- La consegna deve puntare a un risultato **almeno pari e preferibilmente piu' professionale** di quanto richiesto, senza scorciatoie, placeholder invisibili o funzioni scollegate dalla UI reale.
- I test non devono coprire solo il caso felice: ogni requisito critico deve avere almeno un test o una verifica di regressione coerente con il rischio.
- Quando l'utente consegna materiale professionale gia' strutturato, l'agente deve seguirne la stessa logica, profondita' e granularita': non trasformare schede curate in riassunti generici, non perdere fasi operative, termini processuali, allegati, presupposti, fonti, varianti, esiti e controlli. Ogni riduzione deve essere considerata regressione.
- Per Guida Pratica, template atti, termini processuali, Lex e fascicolo, il risultato deve essere super professionale, intuitivo e distintivo: non basta importare testo; bisogna collegarlo a DB, UI, Lex, scadenziario, template, audit, permessi, test e report. I termini processuali devono diventare operativi in tutto e per tutto, con evento generatore, decorrenza, natura, fase, calcolo quando possibile, revisione professionale quando necessaria e tracciamento.
- Se l'utente allega piu' file o pacchetti con nomi simili, l'agente deve rileggerli tutti, confrontare hash e contenuto, distinguere nuovi moduli da duplicati gia' integrati e registrare la deduplicazione in un report. Non saltare file perche' sembrano simili e non duplicare file identici con nomi diversi.

Checklist minima obbligatoria per dichiarare conclusa una feature:

- **Dominio e persistenza**
  - aggiornare modelli, repository, servizi, seed, migrazioni e logica di business coinvolti;
  - completare la persistenza su `JSON`, `SQLite`, `SQL` e `PostgreSQL` quando il dominio lo richiede;
  - evitare source of truth parziali o fallback silenziosi non governati;
  - aggiungere o aggiornare report di consistenza e parita' read/write dove previsti.
- **Superfici applicative complete**
  - completare route Flask, blueprint, servizi, template, API, menu e punti di accesso UI;
  - una funzione nuova non puo' restare nascosta dietro URL non navigabili o accessibile solo da percorso manuale se deve essere usata in prodotto;
  - se la funzione e' amministrativa, deve risultare chiaramente raggiungibile nella superficie admin corretta.
- **UX e grafica professionale**
  - completare layout, stati vuoti, feedback, messaggi, pulsanti, badge, filtri e navigazione;
  - garantire grafica responsive coerente per **desktop, tablet e mobile**;
  - usare SCSS governabile nei bundle ufficiali, senza lasciare stili sparsi o patch visive isolate;
  - evitare regressioni di coerenza grafica tra pagine correlate.
- **Lingua e localizzazione**
  - tutto il testo visibile deve essere in **italiano**;
  - tutte le date e ore esposte in UI devono usare **formati italiani** tramite i filtri condivisi;
  - nessuna etichetta tecnica, placeholder demo o messaggio misto it/en deve restare in UI finale.
- **Permessi, audit, eventi e tenant**
  - verificare impatti su ruoli, RBAC, tenant, audit log, eventi applicativi, notifiche e automazioni;
  - ogni nuova azione sensibile deve essere tracciabile e coerente con i permessi esistenti;
  - considerare isolamento dati, backup per tenant, policy di studio, import/export e configurazioni collegate.
- **AI e contenuti assistiti**
  - se una funzione usa AI, deve essere completata anche su retrieval, guardrail, fonti, confidence, revisione umana e output verificato;
  - vietato consegnare funzioni AI che generano testo non verificato o che mescolano fatti certi, inferenze e demo placeholder senza distinzione.
- **Testing obbligatorio**
  - eseguire test unitari, di integrazione, di route, di UI e di regressione pertinenti alla feature;
  - aggiungere nuovi test quando la feature introduce nuovo comportamento o nuova UI visibile;
  - verificare che non esistano regressioni su percorsi correlati;
  - per release UI o route, verificare anche risposta HTTP reale e, quando serve, flusso autenticato.
- **Versioning e verifica reale della release**
  - eseguire sempre bump versione su `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml`;
  - verificare che la versione dichiarata sia davvero quella servita da app, container, asset compilati e build finale;
  - non basta aggiornare i file: la versione deve risultare coerente anche nei controlli runtime.
- **Documentazione obbligatoria**
  - aggiornare `README`, `docs/`, `CHANGELOG` e documentazione tecnica/prodotto su GitHub quando la feature lo richiede;
  - documentare sempre comandi, URL, superfici, limiti, policy, dipendenze operative e flusso d'uso;
  - se cambia il comportamento reale del prodotto, la documentazione deve rifletterlo nella stessa tranche.
- **Deploy e verifica finale**
  - ricostruire Docker locale con `--no-cache`, riavviare i servizi e verificare stato `healthy`;
  - controllare log applicativi, route principali, pagine toccate, asset compilati e scheduler/worker correlati;
  - eseguire sempre backup, deploy e verifica su Hetzner CPX42 (`iusentra-hetzner`) dopo il push dei branch gemelli;
  - se il caso riguarda differenze tra locale e produzione, includere anche controllo Railway.

Regola finale: **non dichiarare mai conclusa una funzione se e' stata completata solo nel backend, solo nel database, solo nel template o solo nel prompt AI**. Una feature e' chiusa solo quando dominio, storage, route, UI, permessi, test, versione, documentazione e deploy risultano coerenti tra loro.

## Modularizzazione governabile — Regola obbligatoria

- Ogni nuovo modulo o refactor deve produrre **codice governabile**, quindi con responsabilità piccole e confini chiari.
- È vietato spostare logica da `web/app.py` o da un monolite esistente dentro un nuovo file unico altrettanto grande.
- Quando una feature nuova ha più responsabilità, va divisa **subito** in più moduli gestibili, ad esempio:
  - `bootstrap/` per wiring Flask, registrazioni e setup
  - `services/` per orchestrazione applicativa
  - `pct/` per logica di dominio
- Ogni estrazione deve preferire moduli focalizzati e testabili, invece di helper generici pieni di funzioni eterogenee.
- Se un modulo cresce troppo o mescola routing, configurazione, template context e logica business, va ulteriormente spezzato prima di considerare il lavoro concluso.

## Budget di governabilità per `web/app.py` e moduli — REGOLA FONDAMENTALE

- `web/app.py` deve rimanere un file di **bootstrap governabile**: crea l'app, applica configurazione, inizializza hook/filtri e registra moduli. Non deve tornare a contenere route inline o logica business.
- **Limiti hard di `web/app.py`:**
  - massimo **7000 righe**
  - **0** occorrenze di `@app.route`
  - ogni nuova area va registrata tramite moduli dedicati in `web/bootstrap/`
- **Limiti hard per i nuovi moduli `web/bootstrap/`:**
  - target consigliato: **<= 400 righe**
  - soglia massima ordinaria: **<= 650 righe**
  - se una feature supera questa soglia, va spezzata **prima del merge** in sottosezioni omogenee (`core`, `documenti`, `editor`, `signature`, `pdp`, `lookup`, ecc.)
- **Limiti hard per i nuovi moduli `web/services/`:**
  - target consigliato: **<= 500 righe**
  - soglia massima ordinaria: **<= 800 righe**
  - se un servizio mescola orchestrazione, I/O, template context e policy, va diviso subito in componenti più piccoli
- Le eccezioni legacy esistenti sono **debito tecnico da ridurre**, non nuovo standard da imitare.
- Ogni refactor ampio va consegnato in **tranche sicure e reviewabili**, non in patch uniche gigantesche:
  - un gruppo omogeneo di route o responsabilità per volta
  - evitare patch monolitiche che su Windows rischiano limiti pratici di shell, diff o applicazione patch
- Ogni nuovo modulo deve avere una responsabilità leggibile già dal nome del file. Se nel nome o nel contenuto convivono più domini distinti, il modulo va spezzato.
- Ogni estrazione o nuovo modulo deve aggiornare anche i **guardrail automatici** in `tests/test_web_bootstrap.py`, così i limiti restano vivi e verificabili nel tempo.

## Budget anti-monolite UI/backend/CSS - REGOLA OBBLIGATORIA

Ogni nuovo file o refactor deve rispettare il limite piu' severo applicabile tra questa sezione e i budget legacy gia' presenti. Le eccezioni legacy sono debito tecnico da ridurre, non precedenti da copiare.

### Limiti per nuovo codice

- componente React: massimo **250 righe**;
- pagina React: massimo **450 righe**;
- hook React: massimo **180 righe**;
- servizio frontend o API client: massimo **250 righe**;
- modulo backend di servizio: target **<= 500 righe**;
- blueprint o file route: target **<= 500 righe** e nessuna logica business pesante inline;
- file CSS/SCSS singolo: massimo **400 righe**, salvo bundle legacy gia' governati;
- file utility: massimo **250 righe**.

Se una funzione supera o rischia di superare questi limiti, va divisa prima del merge in componenti, hook, servizi, tipi, schema, costanti, repository o moduli omogenei. E' vietato spostare un monolite in un altro file grande equivalente.

### Struttura minima per pagine React complesse

Una pagina React complessa deve separare almeno:

```text
src/pages/<Area>/<Page>.tsx
src/pages/<Area>/components/
src/pages/<Area>/hooks/
src/pages/<Area>/lib/
src/pages/<Area>/types.ts
src/pages/<Area>/schema.ts
src/pages/<Area>/constants.ts
```

I componenti condivisi devono vivere in strutture riusabili (`src/components/ui/`, `src/components/layout/`, `src/components/app/`, `src/components/iusentra/`, `src/hooks/`, `src/services/`, `src/lib/`) oppure nelle cartelle equivalenti gia' presenti nella repo. Non duplicare card, badge, toolbar, empty state, dialog, form field, data table o layout shell.

## Performance, accessibilita, sicurezza e quality gate - REGOLA OBBLIGATORIA

Ogni modifica deve mantenere o migliorare velocita', sicurezza, accessibilita' e verificabilita'. Non basta che il codice compili.

- **Performance frontend**: evitare render inutili, fetch ripetuti, stato globale non necessario, import icone/librerie in blocco e liste lunghe non paginate o non virtualizzate. Usare lazy loading per aree pesanti, skeleton coerenti, abort/cancel delle richieste e feedback immediato sulle azioni.
- **Performance backend**: evitare query ripetute, letture/scritture integrali di file grandi quando basta un delta, operazioni pesanti dentro request web e caricamento completo del fascicolo quando serve solo un riepilogo. Usare job/queue, paginazione, indici e cache tenant-aware dove appropriato.
- **Sicurezza**: non salvare segreti, PIN, token, cookie o sessioni; non loggare dati sensibili; non bypassare auth/RBAC/tenant; validare input lato server; proteggere upload, path traversal, CSRF, XSS e endpoint admin; non scrivere dati runtime nel repository.
- **Accessibilita**: garantire contrasto adeguato, focus visibile, navigazione tastiera, label nei form, heading coerenti, errori associati ai campi, target touch adeguati e stati non basati solo sul colore.
- **Test e quality gate**: ogni nuova verifica deve rispettare la regola dei 5 minuti per comando pytest/job operativo. Eseguire lint, typecheck, test, build, smoke route e gate Codex pertinenti al perimetro. Non disattivare test, non abbassare coverage, non usare `skip` per aggirare regressioni.
- **Report finale**: riportare file modificati, cosa e' stato fatto, verifiche eseguite, verifiche non eseguite con motivo, rischi residui, stato CI e stato deploy quando richiesto dalle regole di release.

## Regola obbligatoria — Portale Servizi Telematici

**Qualsiasi implementazione che coinvolga i portali telematici (PST/polisWeb, PDP, PAT) deve sempre rispettare le regole impartite dal Portale Servizi Telematici del Ministero della Giustizia.**

Regole chiave:
- **Artefatti runtime dei portali solo su storage scrivibile**: upload, staging, import log e cache operative dei portali devono vivere sempre nel data root scrivibile dello studio (`./data/...`, `/data/...` o percorso tenant equivalente), mai in path repository/code-only come `./portale/` quando l'app gira in Docker, Railway o altro runtime hosted.
- **Vista documenti a buste (accordion)**: i documenti vanno sempre raggruppati per `id_deposito` — stessa UX per PST/polisWeb, PDP e PAT. Ogni busta è un accordion collassabile con i file della busta dentro.
- **Download non autonomo**: il gestionale mostra l'elenco degli atti ma non può scaricare documenti in autonomia — il download richiede sessione autenticata via browser sul portale ufficiale.
  - PST → `pst.giustizia.it` (autenticazione: CNS/CIE/SPID)
  - PDP → `appweb.giustizia.it` (autenticazione: CNS/CIE)
  - PAT → `giustizia-amministrativa.it/pac` (autenticazione: CNS/CIE/SPID)
- **Divieto assoluto di scraping HTML dei portali**: PST/polisWeb, SIGP/GDP, PDP, PAT e PTT non devono essere interrogati leggendo pagine HTML come `sigp_infofascicolo.wp` o sessioni browser "nascoste". Le pagine ufficiali possono essere aperte all'utente per consultazione assistita, ma i dati importati nel gestionale devono arrivare da servizi autorizzati PST/PdA/Model Office, da Local Connector sul PC dello studio o da file reali scaricati/importati dall'utente.
- **Sincronizzazione fascicolo telematico autorizzata**: per SIGP/Giudice di Pace il modulo corretto e' `Sincronizzazione fascicolo telematico`, non una scorciatoia HTML. Il flusso deve essere `IUSENTRA -> Local Connector/Signer -> CNS/smart card -> PST o Punto di Accesso autorizzato -> servizi consultazione fascicolo -> normalizzazione -> UI`, senza salvare PIN, username/password portale o credenziali nel cloud.
- **Campi obbligatori nei modelli documento**: ogni `DocumentoXxx` (PST, PDP, PAT) deve avere `id_deposito` e `tipo_atto` per supportare la vista a buste.
- **Logica di raggruppamento nelle route**: le route `*/documenti` devono sempre costruire la lista `depositi` (dict con `id_deposito`, `tipo_atto`, `data_deposito`, `mittente`, `documenti[]`) ordinata per data decrescente, e passare sia `documenti` (lista flat) sia `depositi` (lista raggruppata) al template.
- **Fallback chiave raggruppamento**: se `id_deposito` è vuoto, usare `f"__{data_deposito}__{mittente}"` come chiave di raggruppamento.
- **PST consultazione copia come default**: nei flussi PST/polisWeb il download predefinito deve usare la copia di consultazione del portale con annotazioni ministeriali visibili; l'originale firmato del repository resta opzionale e non può tornare default né nel wizard né nei modali `Naviga PST` né nei fallback server-side.
- **Payload PST coerente su tutti i canali**: `scarica_originale_portale` deve restare `false` di default in wizard, modali dettaglio fascicolo, batch download, API e fallback server-side. Se il payload non contiene il flag, il server deve interpretarlo come copia di consultazione, non come originale firmato.
- **Matching import PST senza dipendere da un solo id**: l'acquisizione file PST deve riconciliare sempre i documenti usando `id_documento`, `id_cat`, `id_repeatto`, `msg_id`, candidati equivalenti e fallback nome normalizzato + deposito, così anche upload manuali, ZIP e download browser vengono riallineati al catalogo ufficiale.
- **Metadati automatici obbligatori dopo import PST**: ogni documento importato dal portale deve compilare automaticamente `data_documento`, `data_deposito_portale`, classificazione ufficiale, tipo atto, sezione di appartenenza e `tags`, e questi valori devono risultare subito visibili nella UI del fascicolo senza data/tag vuoti.
- **Anti-regressione PST/Local Signer 2026-05-11**: il flusso verificato sul fascicolo `Tribunale di Palmi RG 274/2026` non deve essere modificato in modo da reintrodurre richieste PIN ripetute o perdita dei metadati. Le ricerche PST esatte non-GDP devono usare `/pst/ricerca-snapshot`, conservare e riusare la stessa `pst_session_id`, non chiamare `/pst/preflight-auth` prima di ogni passaggio, e il download fascicolo deve usare solo `/pst/download-documenti-batch` con `preflight_auth:false` quando la sessione e' gia' stata preparata dalla ricerca snapshot.
- **Anti-regressione import PST su fascicolo esistente**: se il fascicolo e' gia' presente e l'utente seleziona `Collega` o `Aggiorna pratica esistente`, l'import PST deve proseguire anche con download parziale del portale quando almeno un file reale e' stato acquisito; deve restare bloccato solo il caso zero-file. Non ripristinare il vecchio blocco che fermava l'import parziale prima del merge sulla pratica locale.
- **Anti-regressione metadati profilo PST**: il wizard e la UI fascicolo devono preservare oggetto, procedimento/ruolo, stato, iscrizione, prossima udienza, parti, `id_cat` e tipo atto ufficiale restituiti dal portale. Valori come `Oggetto non disponibile`, `Procedimento non indicato`, `Stato non disponibile` o `Iscrizione: n.d.` sono ammessi solo se il portale non fornisce davvero il dato nella risposta normalizzata, non come effetto collaterale del merge o della deduplica locale.
- **Flusso documenti PST da mantenere per la UI fascicolo**: `/pst/ricerca-snapshot` restituisce l'inventario ufficiale prima dei file (`fascicolo_snapshot` + `documenti_catalogo`); `/pst/download-documenti-batch` restituisce poi lo stato dei contenuti scaricati. La UI e il merge devono considerare il catalogo come fonte primaria per suddivisione e metadati, usando almeno `id_cat`, `id_documento`, `id_reperto`/`id_repeatto`, `msg_id`, `nome`, `tipo`/`tipo_atto_portale`, `data`, `mittente`, `id_deposito`, eventuali ripetizioni e `sezione_suggerita`; il risultato download serve solo a marcare ogni documento come acquisito, catalogato/non acquisito o da recuperare.
- **Suddivisione documenti nella UI fascicolo**: non classificare mai i documenti PST solo dal nome file. Usare prima `tipo_atto_portale`/`tipo`, `id_deposito`, data deposito, mittente e catalogo portale. Mappatura minima da preservare: `Citazione` -> atti introduttivi/atti di parte; `AttoNonCodificato` -> atti di parte o da classificare, senza perdere il tipo ufficiale; `Decreto`, `Ordinanza`, `Sentenza` -> provvedimenti; comunicazioni, biglietti o eventi di cancelleria -> cancelleria/comunicazioni; documenti senza file ma presenti nel catalogo -> sezione dedicata `Catalogati dal portale, non ancora acquisiti` con azione di recupero. Ordinare le sezioni per `data_deposito_portale`/`data_documento` e raggruppare per busta/deposito quando `id_deposito` e' disponibile.
- **Gate obbligatori dopo ogni modifica PST/Local Signer**: prima di dichiarare chiuso un intervento su `tools/local_signer.py`, `web/templates/portale/acquisizione_wizard.html`, `frontend/src/components/TelematicoSurfacePage.tsx`, `web/services/telematico_runtime.py` o `pct/fascicoli.py`, rilanciare almeno i test mirati PST/Local Signer documentati in `tests/test_local_signer.py` e `tests/test_polisweb.py`, verificare `npm --prefix frontend run typecheck` se si tocca React, controllare il log Local Signer per assenza di `/pst/preflight-auth` ripetuti tra ricerca snapshot e batch download, e aggiornare i report `artifacts/react-migration/pytest-*.md`.
- **Divieto di match lasco sui documenti portale**: un documento non può mai essere riallineato a un deposito solo perché `fonte_documento == PORTALE_TELEMATICO`; il match deve richiedere identificativi portale coerenti o nome originario normalizzato compatibile con la singola busta.
- **Factory fascicoli obbligatoria nei runtime**: route, blueprint, worker, scheduler e job asincroni non devono istanziare `GestioneFascicoli` con il solo `db_path`; bisogna usare `get_fascicoli()` oppure passare sempre insieme `db_path`, `documents_dir` e `archive_dir` tenant-aware/runtime-aware, altrimenti si riaprono regressioni `Permission denied` sui path repo-relative `fascicoli/`.

## Regola obbligatoria — Lex AI e RAG fascicolo completo

- **Nessun collo di bottiglia sul fascicolo**: Lex AI, Assistente locale fascicolo e `reindicizza documenti` devono indicizzare e leggere tutti i documenti, attività, udienze/scadenze, comunicazioni di cancelleria, istanze, agenda e scadenziario già presenti o scaricati nel fascicolo.
- **Divieto di limiti fissi sulle sezioni fascicolo**: nei percorsi RAG/AI del fascicolo non sono ammessi tagli tipo `limit=8`, `[:3]`, `[:1]`, `results[:12]` o equivalenti sulle sezioni documentali/processuali. Se serve proteggere il prompt, usare budget dinamici e inventari completi con conteggi, titoli, date, sezione e identificativi.
- **Reindicizzazione fino a coda vuota**: i job OCR/RAG devono processare i chunk pendenti fino a `pending_remaining == 0` per il fascicolo interessato, non un solo batch fisso. Ogni risposta o stato UI deve distinguere chiaramente tra indicizzazione completata, runtime AI assente e documenti non processabili.
- **Inventario sempre presente nel contesto**: quando Lex AI risponde su un fascicolo deve ricevere almeno l'inventario completo di documenti e sezioni, anche se il testo integrale viene poi selezionato con ranking. In questo modo Lex sa che esistono 50, 60 o 70 documenti e non ragiona solo sui primi risultati.
- **Test anti-regressione obbligatori**: ogni modifica a RAG, OCR, assistente fascicolo o reindicizzazione deve includere test con più di 8 documenti e più di 3 elementi per sezione, verificando che nessun elemento venga eliminato dal contesto per limiti hard-coded.

## Regola obbligatoria — CI, coverage e anti-regressione definitiva

- Nessun commit, push o merge deve disattivare, indebolire o aggirare i job `Lint + syntax`, `Governance repo`, `Pytest core`, le 12 parti `Coverage moduli critici parte */12`, `CI Quality Overlay / quality-gates`, `Performance Nightly`, `CodeQL` e i workflow di sicurezza supply-chain.
- Prima di considerare conclusa una tranche, il blocco CI equivalente locale deve passare almeno su: packaging sync, baseline Python, lint/syntax, smoke Flask, `Pytest core`, coverage critica shardata in 12 parti e quality gates pertinenti.
- **Regola permanente nuovi test**: qualsiasi nuovo test, file di test o suite CI creato da ora in poi deve essere progettato e registrato in modo shardabile tramite `scripts/run_pytest_phases.py` o matrice equivalente, con tempo massimo di 5 minuti per singolo comando pytest/job operativo. Se un test supera o rischia di superare 5 minuti, va diviso subito in piu' test item, shard, fixture piu' leggere o suite parallele; non e' ammesso introdurre nuovi blocchi monolitici.
- La coverage critica non puo' essere abbassata senza motivazione tecnica documentata in `CHANGELOG.md`, aggiornamento dei test e approvazione esplicita dell'utente. Ogni nuovo modulo critico deve portare test dedicati o essere escluso solo con motivazione scritta e temporanea.
- Il target richiesto dall'utente per chiudere definitivamente la coverage critica e' **100%**. Finche' il report combinato delle 12 parti `Coverage moduli critici parte */12` non produce 100,00%, e' consentito dire soltanto che il **gate minimo CI corrente** e' verde, ma e' vietato dichiarare che il problema coverage sia chiuso, risolto definitivamente o tornato al 100%. Il vecchio job aggregato `CI / Coverage moduli critici` senza `parte` e' stato eliminato e non deve essere usato come riferimento o required check.
- Ogni volta che un valore numerico di qualita' cambia (coverage totale, coverage critica, gate 100%, performance budget, conteggio test, soglie CI), bisogna:
  - distinguere chiaramente quale gate si sta leggendo, senza confondere il gate anti-regressione al 100% con la coverage critica aggregata;
  - confrontare il valore con l'ultima baseline certa disponibile e riportare sia il valore precedente sia quello nuovo;
  - se il valore scende, trattarlo come regressione release-blocking finche' non viene recuperato con test reali oppure documentato in `CHANGELOG.md` con causa tecnica, impatto e approvazione esplicita dell'utente;
  - se l'ambiente locale differisce dalla CI (es. Python 3.14 locale contro Python 3.12 GitHub Actions), dichiararlo e, quando possibile, rieseguire il controllo con l'interprete/allineamento CI prima di trarre conclusioni;
  - non dichiarare mai "passa" un valore solo perche' supera la soglia minima: se e' inferiore alla baseline precedente, va spiegato e gestito.
- Baseline operative attuali da non peggiorare senza la procedura sopra: Gate anti-regressione contratti CI `tests/test_ci_no_regression_contract.py` = 100%; coverage critica combinata localmente dalle 12 parti `Coverage moduli critici parte */12` >= 71,49%. Questa baseline non sostituisce il target utente del 100% e non puo' essere comunicata come completamento definitivo della coverage.
- Il Gate anti-regressione al 100% sui contratti CI deve restare attivo: se vengono modificati workflow, bounded context Lex, coverage, quality overlay, performance nightly o regole operative, i test anti-regressione devono fallire in assenza dei controlli richiesti.
- E' vietato correggere un problema CI eliminando il test che lo intercetta, marcandolo `skip`, riducendo soglie o spostando codice fuori dal perimetro di controllo senza sostituire il presidio con uno equivalente o piu' forte.
- Le regressioni gia' chiuse su payload bounded Lex, orchestrazione RAG, quality overlay, performance nightly, mojibake/terminologia, packaging sync, coverage critica e `Pytest core` sono release-blocking: se ricompaiono, il lavoro non puo' essere pushato come completato.
- Dopo ogni push, i branch gemelli `claude/legal-electronic-filing-kIxcV` e `Codex/legal-electronic-filing-kIxcV` devono risultare sullo stesso commit e con gli stessi job obbligatori verdi su GitHub Actions.

## Script di simulazione e test — Riferimento rapido

Tutti gli script sono nella directory `tests/` ed eseguibili con `python -m pytest tests/<file> -v`.

### `tests/test_simulazione_deposito.py` — Simulazione deposito telematico (39 test)
**Riusabile per**: verificare che invio, accettazione e controllo siano conformi al PST dopo ogni modifica ai portali.

| Classe | Cosa testa |
|--------|------------|
| `TestPCTBusta` | Creazione busta `.enc`, struttura `DatiAtto.xml`, hash SHA-256, tag `Attoprincipale` |
| `TestPCTStateMachine` | Tutti i 7 stati (`INVIATO → ACCETTATO_PEC → CONSEGNATO → WARN_CONTROLLI → ERRORE_CONTROLLI → ACCETTATO_CANCELLERIA → RIFIUTATO_CANCELLERIA`) |
| `TestPCTInvioPEC` | Invio PEC mockato con struttura risposta conforme |
| `TestPDPDeposito` | Ciclo completo deposito penale: invio → accettazione PEC → controlli automatici → esito procura |
| `TestPATDeposito` | Ciclo completo deposito amministrativo: invio → accettazione PEC → controlli SIGA → esito segreteria TAR |
| `TestCoerenzaPortali` | Uniformità struttura risposta PDP/PAT, parità campi DocumentoPDP/PAT con DocumentoPolisWeb |

**Per rilanciare la simulazione completa:**
```bash
python -m pytest tests/test_simulazione_deposito.py -v
```

**Per simulare solo un portale:**
```bash
python -m pytest tests/test_simulazione_deposito.py::TestPDPDeposito -v
python -m pytest tests/test_simulazione_deposito.py::TestPATDeposito -v
python -m pytest tests/test_simulazione_deposito.py::TestPCTBusta -v
```

### Altri test utili per il deposito

| File | Cosa testa |
|------|------------|
| `tests/test_busta.py` | Busta telematica: creazione, verifica, allegati, hash |
| `tests/test_pec.py` | Client PEC: invio, ricevute, validazione |
| `tests/test_fascicoli.py` | Modello fascicolo: EsitoDepositoPCT, stati, serializzazione |
| `tests/test_reginde.py` | ReGINde: ricerca uffici, PEC tribunali |

**Esegui tutti i test del progetto:**
```bash
python -m pytest tests/ -v
```

---

## Conformità Portale Servizi Telematici — Stato attuale

**Versione 2.5.2 — Conformità: ~98%** (idonea per produzione)

### Conforme ✅
| Componente | Norma | Dettaglio |
|-----------|-------|-----------|
| `DatiAtto.xml` struttura | D.M. 44/2011 Allegato 2 | Namespace, tag `Attoprincipale` (corretto), hash SHA-256, IdBusta, DataDeposito ISO8601 |
| Busta `.enc` (ZIP) | D.M. 44/2011 art. 14 | ZIP contenente DatiAtto.xml + atti firmati; il `.enc` è il formato "busta" (envelope), non richiede cifratura separata — il canale PEC garantisce integrità |
| Oggetto PEC | D.M. 44/2011 art. 14 c.3 | `"DEPOSITO TELEMATICO - {TipoAtto} - RG {n}/{anno}"` — riconosciuto automaticamente dal sistema PST |
| Firma CAdES-BES | D.M. 44/2011 art. 12 | PKCS#7, hash SHA-256, detached, estensione `.p7m`, chain certificati inclusa |
| Verifica scadenza certificato | D.M. 44/2011 art. 12 | Pre-deposito: blocca se certificato scaduto, avviso a 30 giorni |
| PDP REST API | D.Lgs. 150/2022 + D.M. 217/2023 | Endpoint `/depositi`, multipart/form-data, mTLS (P12/PEM), risposta JSON |
| PAT SOAP SIGA | D.P.C.M. 16/02/2016 + D.P.C.S.G.A. 28/07/2021 | WSDL `depositoAtto`, atto in base64, autenticazione mTLS |
| Stato machine PCT | D.M. 44/2011 flusso 4 fasi | 7 stati, serializzazione JSON, `from_dict` per ripristino |
| Ricevute PEC (IMAP) | D.M. 44/2011 art. 15 | Polling accettazione + consegna, timeout 5 min |

### Parziale / Note ⚠️
| Aspetto | Nota |
|---------|------|
| **RFC 3161 Timestamp CAdES** | Opzionale per civile, consigliato per penale. Non implementato: il timestamp viene garantito dalla ricevuta PEC (valore legale equivalente per D.M. 44/2011). |
| **Validazione PDF/A** | Il sistema non verifica che i PDF da firmare siano PDF/A-1b (requisito per deposito). Responsabilità dell'avvocato caricare PDF/A corretti. |
| **IndiceDeposito.xml** | Non incluso nella busta. Il `DatiAtto.xml` funge da indice per D.M. 44/2011 base. Alcune corti possono richiedere file indice separato (variante regionale). |

### Regole invarianti da rispettare ad ogni modifica
1. **Mai cambiare il tag** `<Attoprincipale>` in `busta.py` — il vecchio `<AttoprincipAle>` era errato
2. **Oggetto PEC** deve sempre iniziare con `"DEPOSITO TELEMATICO"` (riconosciuto dal parser PST)
3. **Verifica scadenza certificato** deve essere chiamata prima di qualsiasi firma in `DepositoCivile.deposita()`
4. **Risposta `deposita_atto`** deve sempre contenere: `codiceEsito`, `idDeposito`, `dataDeposito`, `stato`, `ricevutaAccettazione`, `esitoControlli`, `esitoCancelleria` — sia per PDP che per PAT

## Convenzioni

- Messaggi di commit in italiano, descrittivi
- Nessuna dipendenza esterna aggiunta senza necessità
- Mantenere coerenza visiva con Bootstrap 5 e le classi già usate nel progetto

## Modularizzazione governabile — REGOLA OBBLIGATORIA

- Ogni nuova funzionalità o refactor deve produrre **codice governabile**, quindi moduli piccoli, leggibili e con responsabilità chiare.
- **Non è ammesso** spostare logica da un monolite a un nuovo file grande equivalente: se un modulo cresce, va ulteriormente suddiviso in componenti gestibili.
- La separazione va mantenuta per livelli:
  - `web/bootstrap/` → wiring Flask, registrazioni, hook, bootstrap
  - `web/services/` → logica applicativa trasversale e servizi UI/runtime
  - `pct/` → dominio e logica di business legale/PCT
- Prima di aggiungere nuovo codice in `web/app.py`, verificare sempre se può vivere in un modulo dedicato.

## UI italiana e date — REGOLA OBBLIGATORIA

- Tutto il testo visibile in UI deve essere in **lingua italiana**. Evitare etichette miste come `Dashboard`, `Logout`, `Sync`, `Runtime: missing` quando sono esposte all'utente finale.
- Tutte le date/ore **esposte in UI** devono usare formati italiani tramite i filtri template condivisi (`fmt_data`, `fmt_dataora`, `fmt_data_estesa`, ecc.), non `strftime('%B')` o `strftime('%A')` direttamente nei template.
- Eccezione consentita: i valori tecnici per campi HTML `type=\"date\"`, `datetime-local`, attributi `data-*`, API o payload macchina possono restare in formato ISO.

## PEC/email — REGOLA OBBLIGATORIA SUGLI ALLEGATI

- Ogni sincronizzazione IMAP/PEC deve salvare fisicamente gli allegati sotto la cartella runtime della casella, non solo nome, dimensione e MIME nel JSON.
- Se una email e' gia' presente nello storico ma contiene allegati senza `percorso_rel` valido, la sincronizzazione non deve saltarla: deve recuperare nuovamente il messaggio IMAP e riparare gli allegati mancanti.
- Gli allegati PEC con MIME generico `application/octet-stream` devono essere trattati in UI in base all'estensione quando sicuro: `.pdf` va aperto come PDF, `.xml` come XML; la firma `.p7s/.p7m` resta scaricabile come file tecnico.
- La UI non deve lasciare l'utente bloccato su "allegato storico non ancora salvato" dopo un aggiornamento riuscito della casella: aggiungere sempre test che simulino email storiche con allegati metadati ma file assente.

## SCSS e UI responsive — REGOLA OBBLIGATORIA

- I nuovi stili UI non vanno inseriti nei template con blocchi `<style>` o con accumulo di `style="..."`, salvo casi eccezionali strettamente tecnici.
- Ogni nuova regola grafica deve vivere in `web/static/scss/` ed essere organizzata in moduli **governabili**:
  - `components/` per pattern condivisi
  - `pages/` per le viste specifiche
  - `mobile.scss` solo per adattamenti trasversali mobile/tablet
- Gli entrypoint compilati restano quelli caricati dalla UI (`app.scss`, `design-system.scss`, `mobile.scss`, `editor-word.scss`, `portal.scss`): non creare file SCSS orfani non inclusi nel bundle.
- Dopo modifiche SCSS, verificare sempre la compilazione CSS nel flusso Docker locale obbligatorio della release.
- La UI deve essere progettata in modo **responsive** per desktop, tablet e mobile, con card compatte, gerarchia chiara e senza spazi morti.
- I feedback utente per azioni completate, errori, avvisi o stati intermedi devono usare messaggi professionali, chiari e in italiano.

## AI locale — REGOLA OBBLIGATORIA

- Il runtime AI locale (`Ollama`) va sempre trattato come **runtime sullo stesso host che esegue IUSENTRA**, non come componente da distribuire al browser del cliente.
- La strategia preferita è:
  - Windows self-hosted → provisioning automatico del pacchetto standalone ufficiale sullo stesso host
  - altri host/server → guida chiara e non bloccante, senza installazioni opache dal browser
- Il gestionale deve continuare a funzionare anche se il runtime AI non è disponibile: nessuna funzione core di fascicoli, agenda, documenti o scadenziario deve bloccarsi per assenza di Ollama.

## Local Signer / PKCS#11 — REGOLA OBBLIGATORIA

- **PKCS#11 server-side e Local Signer browser-locale non sono la stessa cosa** e non vanno mai confusi.
- Il nome operativo corretto e' **IUSENTRA Local Signer**. Il vecchio prefisso/protocollo `hacs-local-signer` non deve piu' essere usato in nuove UI, installer, script, messaggi, documentazione o test: il protocollo browser-locale primario deve essere `iusentra-local-signer://restart`.
- Eventuali riferimenti legacy `hacs` sono ammessi solo come migrazione tecnica esplicitamente commentata per disinstallare/bonificare installazioni vecchie, mai come comportamento principale o testo visibile.
- Il rilascio Windows del Local Signer deve essere sempre proposto all'utente come **file `.exe`** (`SetupLocalSigner-<versione>.exe` e alias `SetupLocalSigner.exe`). Il `.ps1` e' ammesso solo come sorgente/build artifact interno e non deve diventare CTA, download principale o istruzione operativa per l'utente finale.
- Se l'utente seleziona `Token USB (Aruba Key)` in UI, il sistema deve distinguere sempre:
  - **backend server-side**: libreria/token visibili al processo Python o al container;
  - **canale operativo locale**: `Local Signer` attivo sul PC dell'avvocato tramite `http://127.0.0.1:27272`.
- In ambiente cloud/hosted (`Railway`, server remoto, container Linux), **l'assenza della libreria PKCS#11 nel server non può essere mostrata come errore di configurazione finale** se il flusso previsto è `Local Signer` sul dispositivo cliente.
- Le schermate `Impostazioni -> Firma Digitale`, `polisWeb`, `PDP`, `PAT`, `PTT/SIGIT` e ogni wizard telematico devono:
  - trattare `pkcs11` come **canale locale/browser-guided** quando la scelta dell'utente è il token USB;
  - evitare fallback silenziosi a `demo` solo perché il container non vede il token;
  - mostrare messaggi chiari del tipo: il controllo reale avviene sul PC locale tramite `Local Signer`.
- **Divieto di verificare il token USB interrogando il server remoto** quando il controllo corretto è lato client.
  - Il pulsante `Verifica token collegato` deve usare il `Local Signer` locale (`127.0.0.1:27272`) dal browser.
  - Gli endpoint server `/api/firma/pkcs11/*` restano validi solo per casi realmente server-side o per diagnostica specifica, non come fonte unica dello stato UI in produzione hosted.
- **PEC da Impostazioni sempre locale**: il pulsante `Impostazioni -> PEC -> Verifica invio PEC` deve usare il `Local Signer` locale dal browser (`/pec/smtp/test`) e non deve mai eseguire una verifica SMTP dal server/cloud. La password PEC resta sul PC in uso; quando e' gia' salvata puo' essere consegnata al browser solo tramite `/impostazioni/pec/local-smtp-payload` per la prova locale.
  - Fix eseguito il 2026-05-09 nel commit `c3f7ff79`: `SettingsActions.tsx` chiama `testPecSmtpViaLocalSigner`, `localSigner.ts` invia la prova a `http://127.0.0.1:27272/pec/smtp/test`, `react-pec-local-signer-guard.js` protegge anche gli asset React gia' compilati intercettando il vecchio endpoint, `react_impostazioni_bridge.py` non esegue piu' il test SMTP PEC dal server e `tests/test_impostazioni_pec_local_signer_react.py` impedisce la regressione.
  - Motivo: in produzione e in cloud il server non e' il PC dello studio; la verifica invio PEC deve partire dal dispositivo dell'avvocato, dove vive IUSENTRA Local Signer e dove resta la password PEC. Il server puo' solo indicare che serve il controllo locale.
  - Non modificare, rimuovere, aggirare o sostituire questa regola per nessun motivo: eventuali refactor futuri devono mantenere il test locale via Local Signer, il recupero tenant-aware della password salvata solo per la prova locale e il blocco del test SMTP PEC server-side.
- **AI Locale da Impostazioni sempre governata dal PC dello studio**: `Impostazioni -> AI Locale` deve usare IUSENTRA Local Signer dal browser per controllare Ollama, preparare i modelli e verificare il computer dell'avvocato. Non sostituire questo flusso con controlli server/cloud come fonte finale dello stato utente.
  - Se Ollama o i modelli non risultano pronti, la UI deve offrire `Prepara AI locale` e, quando disponibile, il link installer ufficiale rilevato dal companion locale. Non lasciare campi come scelta modello senza aiuto operativo: il default deve restare automatico.
  - La scelta automatica dei modelli e' responsabilita' del bridge locale (`tools/local_ai_host_bridge.py` / Local Signer), che rileva RAM, spazio libero, CPU/GPU e profilo del PC. La UI deve spiegare in italiano che IUSENTRA controlla il computer e sceglie i modelli adatti.
  - Fix UI eseguito il 2026-05-09 dopo la regressione segnalata: la tab React chiama Local Signer per `/ai/status` e `/ai/bootstrap`, `react-ai-local-guard.js` protegge anche gli asset gia' compilati e i test devono impedire che AI Locale torni a dipendere solo dal server applicativo.
  - Non modificare, rimuovere, aggirare o sostituire questa regola per nessun motivo: il server puo' avere Ollama per l'istanza online, ma l'avvocato deve poter preparare e verificare l'AI sul proprio PC senza linguaggio tecnico.
- **Ping Local Signer Windows con `token_probe_fresh`:** se il servizio locale risponde con `ok: true`, `token[]` vuoto e `token_probe_fresh[]` valorizzato, la UI non deve mostrare `Local Signer non rilevato`. Deve distinguere:
  - servizio Local Signer raggiungibile;
  - token rilevato da probe fresco;
  - riavvio/riverifica consigliato tramite `iusentra-local-signer://restart`;
  - eventuale errore reale solo se anche il probe fresco non trova token o il servizio non risponde.
- In stato `token_probe_fresh[]` valorizzato ma `token[]` vuoto, la UI non deve chiedere il PIN e non deve abilitare la firma: deve mostrare solo l'azione `Riavvia e riverifica`. Il PIN va richiesto soltanto quando il token principale del Local Signer attivo e' presente in `token[]`.
- L'azione di riavvio deve attivare direttamente il protocollo locale `iusentra-local-signer://restart` da un click utente e poi riverificare piu' volte lo stato; un iframe nascosto da solo non e' sufficiente per considerare risolto il flusso Windows.
- Le pagine React di firma documento devono mantenere la preferenza di firma visibile (`laterale`, `basso_sinistra`, `basso_destra`) letta dalle impostazioni studio o dalla scelta locale della sessione, e devono passarla al Local Signer come `visible_signature_mode` insieme a `visible_signature_place`.
- La coccarda della firma visibile deve restare l'immagine PNG trasparente incorporata nel renderer PDF, senza bordo opaco e senza coprire il testo nelle tre posizioni.
- Ogni modifica a firma digitale, PST/polisWeb, PDP, PAT, PTT o pagina impostazioni firma deve includere **test di regressione espliciti** su:
  - scelta `pkcs11` senza libreria disponibile nel container;
  - assenza del falso messaggio `PKCS#11 selezionato ma libreria/token non disponibili` nella UI quando il canale corretto è `Local Signer`;
  - assenza del falso messaggio `Local Signer non rilevato` quando il ping locale espone `token_probe_fresh[]`;
  - assenza della richiesta PIN quando il token e' solo in `token_probe_fresh[]`;
  - passaggio della posizione firma visibile al Local Signer nelle pagine React;
  - render PDF reale delle tre posizioni della firma visibile con coccarda trasparente non sovrapposta al testo;
  - script/browser che verificano il `Local Signer` locale e non il server remoto;
  - status telematico che resta `pkcs11/browser-guided` e non ricade in `demo` per errore.

## Railway CLI — REGOLA OBBLIGATORIA

- L'ambiente di lavoro è abilitato anche alla **Railway CLI** con login valido.
- Quando un comportamento differisce tra `localhost` e produzione Railway, la verifica non può fermarsi al test locale: usare anche Railway CLI per controllare il servizio online.
- In questi casi verificare sempre, quando rilevante:
  - shell del container Railway
  - log applicativi
  - stato del volume `/data`
  - variabili/runtime effettivi del servizio online
  - risposta reale delle route in produzione
- Se un fix riguarda deploy, storage, AI locale, Local Signer bridge, SMTP, portali o differenze di configurazione tra ambienti, includere esplicitamente un controllo Railway nel flusso di test finale.

## Hetzner CPX42 — REGOLA OBBLIGATORIA

- L'accesso Hetzner esiste gia' in questa macchina e **non va dichiarato mancante** senza verifica reale.
- Profilo SSH operativo:
  - alias: `iusentra-hetzner`
  - host: `116.203.45.57`
  - server: `ubuntu-16gb-nbg1-1`
  - utente: `root`
  - chiave configurata: `~/.ssh/iusentra_hetzner_cpx42`
- Prima di dire che mancano target, credenziali o SSH, eseguire sempre:
  ```bash
  ssh -o BatchMode=yes -o ConnectTimeout=10 iusentra-hetzner "hostname; whoami; pwd"
  ```
- Profilo deploy remoto:
  - root applicativa: `/opt/iusentra`
  - repository: `/opt/iusentra/repo`
  - ambiente: `/opt/iusentra/.env.hetzner`
  - dati persistenti: `/opt/iusentra/data`
  - backup: `/opt/iusentra/backups`
  - dominio pubblico: `https://app.iusentra.it`
- Dopo ogni commit/push completato sui branch locali e remoti `claude/legal-electronic-filing-kIxcV` e `Codex/legal-electronic-filing-kIxcV`, aggiornare sempre anche Hetzner CPX42: il server remoto deve ricevere lo stesso commit tramite deploy reale, con backup prima del deploy e verifiche post-deploy. Non dichiarare concluso il lavoro se GitHub e' sincronizzato ma `/opt/iusentra/repo` su Hetzner CPX42 e' rimasto al commit precedente.
- Prima di ogni deploy Hetzner reale creare un backup dati remoto:
  ```bash
  ssh iusentra-hetzner "bash /opt/iusentra/repo/deploy/hetzner/backup.sh"
  ```
- Deploy Hetzner reale:
  ```bash
  ssh iusentra-hetzner "BRANCH=Codex/legal-electronic-filing-kIxcV bash /opt/iusentra/repo/deploy/hetzner/deploy.sh"
  ```
- Verifiche obbligatorie post-deploy Hetzner:
  ```bash
  ssh iusentra-hetzner "git -C /opt/iusentra/repo rev-parse --short HEAD"
  ssh iusentra-hetzner "docker compose --env-file /opt/iusentra/.env.hetzner -f /opt/iusentra/repo/deploy/hetzner/docker-compose.hetzner.yml ps"
  curl -i https://app.iusentra.it/api/pronto
  curl -I --max-redirs 0 https://app.iusentra.it/studio?_legacy=1
  curl -I --max-redirs 0 https://app.iusentra.it/telematico
  ```
- Le route protette in produzione possono rispondere `302` verso `/login`: questo e' esito valido se non si sta usando una sessione autenticata.
- Se un fix riguarda deploy, storage, portali, Local Signer bridge, SMTP, differenze locale/produzione o dominio `app.iusentra.it`, includere anche controllo Hetzner oltre a Railway quando il servizio Hetzner e' nel perimetro.

## Versioning — REGOLA OBBLIGATORIA

**Ad ogni implementazione (nuova funzionalità, bug fix, qualsiasi modifica al codice) eseguire SEMPRE il bump di versione e aggiornare tutti e quattro i file:**

| File | Campo | Esempio |
|---|---|---|
| `pct/__init__.py` | `__version__ = "X.Y.Z"` | unica fonte di verità |
| `setup.py` | `version="X.Y.Z"` | package Python |
| `Dockerfile` | `LABEL … version="X.Y.Z"` | immagine Docker |
| `railway.toml` | `#  version: X.Y.Z` | trigger redeploy Railway |

**La versione web è automaticamente sincronizzata** — `web/app.py` importa `pct.__version__` come `APP_VERSION` (riga 102) e la espone nel template `base.html` tramite `{{ app_version }}`. Non esiste una versione web separata.

**Sincronizzazione obbligatoria locale / GitHub / Railway:**
- Dopo ogni modifica completata, la copia locale deve coincidere con il branch GitHub di lavoro e con la release destinata a Railway.
- Non lasciare mai commit solo in locale: eseguire sempre `git push` del branch di lavoro.
- Eseguire sempre anche il push dello stesso commit su `claude/legal-electronic-filing-kIxcV` oltre che su `Codex/legal-electronic-filing-kIxcV`.
- Se Railway è collegato a un branch remoto diverso dal branch locale corrente, riallineare anche quel branch remoto allo stesso commit della copia locale.
- Considerare il lavoro concluso solo quando risultano allineati:
  - file locali
  - branch GitHub di lavoro
  - branch remoto `claude/legal-electronic-filing-kIxcV`
  - branch remoto usato da Railway
  - `railway.toml` con la stessa versione del codice locale

**Local Signer — REGOLA OBBLIGATORIA:**
- Ad ogni release del `Local Signer`, generare sempre contestualmente i pacchetti versionati per **Windows, macOS e Linux** nella cartella `tools/dist`.
- I nomi file devono includere sempre la versione del signer (es. `SetupLocalSigner-1.5.5.exe`).
- I pacchetti finali distribuiti all'utente devono essere presentati come **eseguibili**, non come semplici script:
  - Windows → `.exe`
  - macOS → installer eseguibile `.command`
  - Linux → installer eseguibile `.run`
- Il punto ufficiale e permanente di distribuzione dei pacchetti è:
  `https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma`

**Schema SemVer:**
- `MAJOR.MINOR.PATCH`
- Patch (+0.0.1): bug fix, correzioni dati, aggiornamenti documentazione
- Minor (+0.1.0): nuova funzionalità retrocompatibile
- Major (+1.0.0): breaking change

**Deploy — Docker locale (REGOLA OBBLIGATORIA):**
- Dopo ogni bump di versione, ricostruire e riavviare il Docker locale con:
  ```bash
  cd /opt/iusentra/repo
  docker compose build --no-cache
  docker compose up -d
  ```
- Eseguire **sempre** `--no-cache` per garantire che la nuova versione del codice sia inclusa nell'immagine (il layer del codice si aggiorna solo con rebuild).
- Verificare che il container sia tornato healthy prima di considerare il deploy completato:
  ```bash
  docker compose ps          # Status deve essere "healthy"
  docker compose logs --tail=20 app   # Controllare errori di avvio
  ```
- URL locale: `http://localhost` (via Nginx) oppure `http://localhost:8080` (diretto Gunicorn).

**Deploy — Railway (produzione online):**
- Il deploy su Railway avviene dopo il bump di versione e il push sul branch.
- Ad ogni release va aggiornata anche la versione sul pannello Railway (variabile d'ambiente o redeploy dell'immagine).
- Versione corrente in produzione: **1.1.2**

## Note tecniche

- **`web/app.py` — variabile `oggi` nei `render_template`**: passare **sempre** `oggi=date.today()` (oggetto `date`), **mai** `oggi=date.today().isoformat()` (stringa). `base.html` riga 350 chiama `oggi.strftime('%d/%m/%Y')` che è un metodo di `date`/`datetime`, non di `str` → se si passa la stringa si ottiene `AttributeError: 'str' object has no attribute 'strftime'`. I campi `min="{{ oggi }}"` degli input HTML `type="date"` ricevono comunque il formato corretto perché `str(date.today())` restituisce `YYYY-MM-DD`.

- **`web/app.py` — `SECRET_KEY`**: quando si imposta `app.secret_key`, impostare sempre anche `app.config["SECRET_KEY"] = app.secret_key`. La funzione `get_condivisioni()` usa `app.config["SECRET_KEY"]` e senza questa riga solleva `KeyError` causando un 500.

- **`web/app.py` — Route API senza try/except → 500 generico**: le route `/api/uffici`, `/api/uffici/stato`, `/api/uffici/aggiorna` **non hanno l'handler di errore HTTP** del Flask (a differenza di `/polisWeb`, `/polisWeb/ricerca`, `/polisWeb/documenti` che usano già try/except). Se lanciano un'eccezione non catturata, Flask risponde con "500 — Errore interno". Regola:
  - **Ogni route `/api/*` deve avere `try/except Exception`** e restituire JSON con HTTP 200 (o 4xx) — mai lasciare propagare l'eccezione al gestore Flask 500.
  - Esempio pattern corretto:
    ```python
    try:
        ...logica...
        return jsonify(risultato)
    except Exception as e:
        app.logger.exception("Errore nome_route: %s", e)
        return jsonify({"errore": str(e)}), 200  # o jsonify([]) per liste
    ```
  - Il 500 si manifesta tipicamente **dopo aggiornamenti al bundle uffici** (`pct/uffici_giudiziari.py`): `polisWeb.html` chiama `/api/uffici/stato` al caricamento e `/api/uffici?q=...` durante l'autocomplete — se il bundle lancia un'eccezione in quelle route, il template carica correttamente ma il badge e l'autocomplete generano 500.

- **`polisWeb` — ricerca uffici giudiziari**:
  - Il form (`polisWeb.html`) invia il **codice** ufficio nel campo hidden `name="tribunale"` (es. `0580010`), **non il nome**.
  - La route `polisWeb_ricerca` riceve il codice e deve risolvere il nome con:
    ```python
    _uff = next((u for u in get_gestore(cache_path).carica() if u.get("codice") == tribunale), None)
    tribunale_sel_nome = _uff["nome"] if _uff else tribunale
    ```
  - **NON usare** `cerca_ufficio_giudiziario(tribunale, ...)` per risolvere il nome: quella funzione cerca per testo nel nome, non per codice → restituisce `None` quando riceve un codice numerico.
  - `ricerca_fascicoli(tribunale=codice)` accetta sia codice che nome (il client reale usa `_risolvi_codice_ufficio` che riconosce `str.isdigit()`).
  - Il demo client (`_ClientPolisWebDemo`) usa `_nome_ufficio_demo(codice)` per risolvere il nome leggibile dal codice tramite `get_gestore().carica()`.

- **Uffici giudiziari — regole di consistenza del bundle** (`pct/uffici_giudiziari.py`):

  **Formato nomi** (helper `_t`, `_ca`, `_pr`, ecc.):
  - Tribunale → `"Tribunale di {città}"`
  - Corte d'Appello → `"Corte d'Appello di {città}"` (distretto == città)
  - Procura → `"Procura della Repubblica di {città}"` (generate auto da `_genera_procure`)
  - Procura Generale → `"Procura Generale di {città}"` (distretto == città)
  - Trib. Minorenni → `"Tribunale per i Minorenni di {città}"`
  - Trib. Sorveglianza → `"Tribunale di Sorveglianza di {città}"`
  - Corte d'Assise → `"Corte d'Assise di {città}"`
  - Giudice di Pace → `"Ufficio del Giudice di Pace di {città}"`
  - TAR → `"TAR {nome-regione-o-sezione}"`

  **Regole invarianti** (controllare dopo ogni modifica al bundle):
  1. **Slug PEC tutto minuscolo**: `tribunale.milano@giustiziapec.it` ✓ — `tribunale.reggioEmilia@…` ✗
  2. **Corte d'Appello**: `distretto` deve coincidere con la città nel nome
  3. **Procura Generale**: `distretto` deve coincidere con la città nel nome
  4. **Nessun codice duplicato** tra tutti gli uffici del bundle completo
  5. **Nessun nome duplicato** tra tutti gli uffici del bundle completo
  6. **Uffici geograficamente corretti**: es. Crotone → distretto Catanzaro, non Lecce
  7. **Codici standard**: 7 cifre per uffici ordinari, prefisso `T` per TAR, `CDS` per Consiglio di Stato

  **Script di verifica** (eseguire dopo modifiche al bundle):
  ```bash
  python3 - <<'EOF'
  import sys; sys.path.insert(0, '.')
  from pct.uffici_giudiziari import _build_bundle_completo, TIPI_UFFICIO
  from collections import Counter
  import re
  bundle = _build_bundle_completo()
  problemi = []
  dup_cod = {k for k,v in Counter(u['codice'] for u in bundle).items() if v>1}
  [problemi.append(f"CODICE-DUP {c}") for c in dup_cod]
  dup_nomi = {k for k,v in Counter(u['nome'] for u in bundle).items() if v>1}
  [problemi.append(f"NOME-DUP '{n}'") for n in dup_nomi]
  for u in bundle:
      slug = u.get('pec','').split('@')[0]
      if any(c.isupper() for c in slug):
          problemi.append(f"PEC-MAIUSC {u['codice']} {u['nome']} → {u['pec']}")
      if not u.get('distretto','').strip():
          problemi.append(f"DISTRETTO-VUOTO {u['codice']} {u['nome']}")
      if u['tipo'] == 'CORTE_APPELLO':
          citta = u['nome'].replace("Corte d'Appello di ","")
          if citta.lower() != u['distretto'].lower():
              problemi.append(f"CA-DISTRETTO {u['codice']} nome={u['nome']} dist={u['distretto']}")
      if u['tipo'] == 'PROCURA_GENERALE':
          citta = u['nome'].replace("Procura Generale di ","")
          if citta.lower() != u['distretto'].lower():
              problemi.append(f"PG-DISTRETTO {u['codice']} nome={u['nome']} dist={u['distretto']}")
  print(f"Uffici: {len(bundle)}  Problemi: {len(problemi)}")
  [print(f"  {p}") for p in problemi]
  EOF
  ```

  **Badge autocomplete** (`polisWeb.html`, funzione JS `seleziona(u)`):
  - Il badge mostra `u.nome` direttamente — **NON** aggiungere il prefisso `${label}: ` perché il tipo è già incluso in `u.nome` (es. "Tribunale di Milano").
  - Il distretto `(${u.distretto})` può apparire in parentesi per indicare il distretto di appartenenza (es. "Tribunale di Reggio Calabria (Catanzaro)" è **corretto**: Reggio Calabria appartiene al distretto Catanzaro).

  **Valore inviato dai form** (differenze per sezione app):
  - `polisWeb.html`: campo hidden invia `u.codice` (es. `0580010`)
  - `fascicoli/form.html`, `form_appuntamento.html`, `clienti/form.html`: `<select>` invia `u.nome` (es. `"Tribunale di Milano"`)

  **Verifica visiva dopo ogni modifica al bundle** — pannello admin in `polisWeb.html`:
  - Il badge "N uffici · aggiornati" (verde) è visibile solo agli admin.
  - Cliccandolo si apre il pannello con il **breakdown per tipo** (Tribunali, Procure, G.d.P., ecc.).
  - Dopo ogni modifica al bundle, cliccare **"Ricarica bundle"** per rigenerare la cache dal codice aggiornato (senza attendere TTL né fonti remote).
  - Valori attesi a bundle v1.0.2: 648 uffici totali — GDP: 155, TRIBUNALE: 146, PROCURA: 147, CORTE_APPELLO: 23, PROCURA_GENERALE: 23, SORVEGLIANZA: 26, TM: 26, TAR: 31, CORTE_ASSISE: 69.
  - Se i numeri non corrispondono dopo "Ricarica bundle", il deploy non ha incluso le modifiche a `pct/uffici_giudiziari.py`.

  **Auto-upgrade automatico** (`GestoreUfficiGiudiziari.carica()`):
  - Se la cache su disco ha **meno uffici del bundle interno**, `carica()` rigenera automaticamente la cache dal bundle al primo accesso dopo il redeploy.
  - Questo risolve il caso in cui Railway (o qualsiasi server) abbia una cache salvata da sorgente remota (PST/URL esterno) con meno uffici di quanti ne ha il bundle aggiornato.
  - Il log mostra: `Auto-upgrade cache uffici: N (cache) < M (bundle) → rigenero`
  - **Non modificare questa logica**: è la salvaguardia principale contro dati incompleti su produzione.

- **Mobile — Modal visualizzatore documenti** (`fascicoli/dettaglio.html`, `#modalVisualizzatore`):
  - Il modal deve avere **sempre** `modal-fullscreen-sm-down` per occupare tutto lo schermo su mobile.
  - Il `modal-content` deve avere `display:flex;flex-direction:column` affinché il body con l'iframe possa espandersi con `flex:1`.
  - Struttura corretta:
    ```html
    <div class="modal-dialog modal-xl modal-fullscreen-sm-down" style="max-width:95vw;height:92vh;margin:.5rem auto">
      <div class="modal-content" style="height:100%;display:flex;flex-direction:column">
        <div class="modal-header py-2">…</div>
        <div class="modal-body p-0" style="flex:1 1 auto;overflow:hidden;display:flex;flex-direction:column">
          <iframe … style="width:100%;flex:1;border:0;min-height:0"></iframe>
        </div>
      </div>
    </div>
    ```
  - **Senza `display:flex` sul `modal-content`**: il `flex:1` sul modal-body non funziona → l'iframe collassa a altezza 0 → maschera apparentemente vuota/troppo piccola.

- **Mobile — Modal Bootstrap: z-index backdrop e posizionamento**:
  - I modal devono essere **figli diretti del `<body>`**, non annidati dentro `#main` o altri container con `position:relative/absolute` → altrimenti il backdrop Bootstrap non copre correttamente tutta la pagina e il modal può apparire parzialmente nascosto o in posizione errata.
  - Regola: tutti i `<div class="modal fade" …>` vanno inseriti **in fondo al file HTML, fuori da qualsiasi wrapper**.

- **Mobile — footer navbar fisso e scroll**:
  - Il footer di navigazione mobile (`base.html`) usa `position:fixed;bottom:0` con `z-index:1030`.
  - Il contenuto principale `#main` deve avere `padding-bottom` sufficiente (≥ 70px) per non essere coperto dal footer.
  - Su iOS Safari il `100vh` include la barra URL → usare `min-height: -webkit-fill-available` come fallback per i modal fullscreen.

- **Mobile — Dropdown tagliati da `overflow:hidden` su `#main`**:
  - Su mobile `#main` è `position:fixed` con `overflow-y:auto; overflow-x:hidden` (vedi `app.css` riga ~614). Qualsiasi `position:absolute` dentro `#main` — inclusi i Bootstrap dropdown-menu — viene **clippato** ai bordi del container e risulta invisibile o troncato.
  - **Sintomo**: cliccando un dropdown (es. "Esporta") appare un rettangolo bianco vuoto invece dei voci del menu.
  - **Fix obbligatorio**: inizializzare i dropdown via JavaScript con `popperConfig: { strategy: 'fixed' }` — Popper usa `position:fixed` e aggira il clipping. Il fix globale è già in `base.html` (script alla fine del `<body>`):
    ```javascript
    new bootstrap.Dropdown(el, { popperConfig: { strategy: 'fixed' } });
    ```
  - **Regola**: ogni volta che si aggiunge un nuovo dropdown dentro `#main`, verificare che venga inizializzato dallo script globale (`[data-bs-toggle="dropdown"]` auto-rilevato). Non serve azione manuale se l'attributo standard è presente.
  - **Non usare** `data-bs-display="static"` come workaround: disabilita il posizionamento dinamico di Popper e il menu appare sempre in posizione fissa rispetto al pulsante, ignorando i bordi del viewport.

- **Mobile — pulsanti azione documento** (`fascicoli/dettaglio.html`, sezione atti):
  - I pulsanti (Visualizza, Scarica, Firma, Elimina) nelle card documento su mobile erano non cliccabili a causa di un overlay trasparente generato da un elemento parent con `pointer-events` errato.
  - Verificare sempre che i bottoni nelle card abbiano `position:relative;z-index` superiore a eventuali pseudo-elementi `::after` del container.
  - I titoli delle sezioni (es. "Atti") non devono sovrapporsi ai pulsanti: usare `d-flex align-items-center justify-content-between` per header sezione + pulsante "Aggiungi".

## MetaHarness workflow — Regola di perimetro

- MetaHarness e' ammesso solo come strumento esterno di sviluppo per ottimizzare harness, istruzioni Codex, script di test, script di validazione e documentazione operativa.
- MetaHarness non e' una dipendenza runtime di IUSENTRA e non va aggiunto a `requirements.txt`, `requirements/base.txt`, `requirements/dev.txt`, `pyproject.toml` o `setup.py` senza autorizzazione esplicita.
- Per questo repository, i run MetaHarness non devono modificare direttamente codice applicativo core (`pct/`, `web/`, `lex/`), storage, migrazioni, portali telematici, Lex AI o UI prodotto senza review manuale.
- Ogni scaffold o run con provider reali deve essere autorizzato nel task corrente.
- I risultati MetaHarness vanno trattati come proposte: prima review del diff, poi test pertinenti, poi eventuale integrazione.
- E' vietato usare MetaHarness per indebolire CI, coverage, quality gates, workflow di sicurezza o regole gia' presenti in questo `AGENTS.md`.

## Autoresearch-lite workflow — Regola di sicurezza

- Autoresearch-lite e' solo un metodo di lavoro ispirato a `karpathy/autoresearch`, adattato a IUSENTRA.
- Non e' consentito installare `karpathy/autoresearch`, aggiungere dipendenze ML/GPU o modificare dipendenze runtime per questo workflow.
- Sono vietati loop infiniti, esperimenti notturni non presidiati, branch extra, reset distruttivi e run autonomi senza nuovo task esplicito.
- Ogni esperimento deve avere obiettivo, baseline, file modificabili, file vietati, comandi di verifica e criteri `keep/discard`.
- Ogni risultato va classificato come `keep`, `discard`, `crash`, `scope-violation` o `needs-review`.
- Su IUSENTRA il ciclo sperimentale deve migliorare la qualita' di Codex senza indebolire storage, CI, coverage, portali telematici, Lex AI, multi-tenant, sicurezza o audit.

## Open Design support — Regola UI/UX

- Open Design support e' ammesso solo come supporto esterno per migliorare design system, skill UI/UX, prototipi e prompt grafici di Codex.
- Non e' consentito installare `nexu-io/open-design` dentro IUSENTRA, aggiungere dipendenze Node/pnpm al gestionale o modificare package manager per questo workflow senza autorizzazione esplicita.
- Le risorse ufficiali per Codex vivono in `tools/open-design-support/`.
- Per ogni task UI/UX, Codex deve leggere `tools/open-design-support/IUSENTRA_DESIGN.md`, `tools/open-design-support/IUSENTRA_UI_RULES.md` e la skill pertinente prima di modificare template, React, CSS o SCSS.
- Ogni modifica UI deve rispettare lingua italiana, date italiane, responsive desktop/tablet/mobile, stati vuoti, loading, errore, conferma, accessibilita' e coerenza con l'architettura esistente.
- Open Design support non autorizza modifiche libere a `web/`, `web/templates/`, `web/static/`, `web/blueprints/`, `/app-v2`, route Flask, API o storage.
- Ogni prototipo o artifact grafico va trattato come proposta: prima review, poi adattamento a Jinja/React/CSS, poi test o smoke pertinenti.

## Codex quality gate — Regola pre-report

- Per task di tooling, MetaHarness, autoresearch-lite o Open Design support, prima del report finale eseguire:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode dev-tooling
```

- Per task UI/UX di supporto, eseguire:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode ui-support
```

- Se il quality gate fallisce, non dichiarare il task completato: correggere la violazione oppure segnalarla chiaramente nel report finale.
- Il quality gate non sostituisce i test applicativi quando si modifica codice prodotto.
