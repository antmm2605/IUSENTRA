# IUSENTRA — Gestionale per Studi Legali

IUSENTRA è una web app Flask per studi legali italiani, con focus su gestione operativa di studio, fascicoli, PCT/portali telematici, documenti, scadenze, intelligence legale e assistenza AI locale.

La repo oggi non è più solo un tool CLI per il Processo Civile Telematico: contiene un gestionale web ampio, modulare e multi-dominio, con layer separati per bootstrap Flask, servizi UI/runtime e logica di dominio.

## Cosa fa oggi

- Gestione fascicoli, clienti, soggetti, agenda e scadenziario.
- Deposito telematico civile, penale e dashboard servizi telematici.
- Modulo separato `Integrazione SIGP - Giudice di Pace` per generazione XML, predeposito, validazione XSD ufficiale e UI `/sigp-sync/` di sincronizzazione fascicolo telematico tramite soli canali autorizzati PST/PdA/Model Office o Local Connector, senza scraping HTML.
- Acquisizione guidata dei portali PST/SIGP, PDP, PAT e PTT/SIGIT: se il canale tecnico non consente lettura diretta, IUSENTRA accompagna l'utente al portale ufficiale, importa file/ZIP/cartelle o payload JSON autorizzati e smista tutto nelle sezioni reali del fascicolo (`Documenti`, `Attivita`, `Udienze`, `Comunicazioni`, `Istanze`).
- Workflow completo `cliente -> preventivo -> conferimento -> fascicolo -> attivita' -> parcella -> incasso`.
- Wizard preventivi e console tariffaria ora usano davvero il tariffario corretto per fase: `D.M. 55/2014` per i giudiziali, `Tabella A25` per lo stragiudiziale e `Tabella A27` per mediazione / negoziazione assistita, con checkbox fiscali che incidono davvero sul totale.
- Il ramo `Compenso a tempo` e' integrato nello stesso workflow preventivo/conferimento/parcella: applica l'art. 22-bis D.M. 55/2014, gestisce tariffa oraria, minuti, arrotondamento, soglie, warning e clausola di pattuizione espressa senza sostituire il motore ordinario per fasi.
- Nei casi di mediazione civile / commerciale il preventivo e il tariffario possono includere anche i costi organismo ex `D.M. 24 ottobre 2023, n. 150` (artt. 28, 30, 31 e Tabella A), distinguendo volontaria / obbligatoria-demandata, esito del primo incontro o degli incontri successivi e maggiorazione art. 31, comma 3.
- Le superfici economiche finali usano ora microcopy coerente, ricalcolo guidato inline e log applicativi leggibili come una storia operativa, senza `alert()` ambigui o stati poco spiegabili.
- Timesheet operativo con valorizzazione del tempo e generazione parcella dalle attivita' validate.
- Fatturazione, pagamenti, saldo cliente e KPI economici per studio, cliente e fascicolo.
- Fascicolo con `cabina operativa` a tab: quadro intelligente, workflow `fascicolo -> incasso`, controllo economico, governo documentale e conformita' deposito nella stessa vista.
- Il `Quadro intelligente fascicolo` non usa piu' avanzamenti statici: valuta davvero documenti, classificazioni portale, scadenze rispetto a oggi, provvedimenti presenti e coerenza dello stato, mentre la PEC/auto-esiti associa i messaggi usando `RG + nominativo cliente/controparte + tribunale`.
- Template atti, Checklist Atti professionale e workspace legali allineati sullo stesso catalogo operativo per aree, branche e sottobranche, con catalogo master versionato da 420 template e split `core`, `advanced`, `specialist`, `studio_interno`.
- `Applicazioni` e' ora una cabina applicativa vera: moduli economici, telematici, template, lookup, utility e rassegna si aprono nello stesso workspace coerente invece di limitarsi a rinviare a link esterni o schede descrittive.
- Giurisprudenza, legal intelligence, repository strutturati per Lex.
- Motore `Update Intelligence` per monitoraggio normativo, giurisprudenziale e di prassi con area di acquisizione, coda revisioni e pagina news giuridiche strutturate.
- Pipeline `Coverage AI` per audit tassonomico, gap queue, draft v2, review e publish SQL con retrieval interno, funzionante sia su `SQLite locale` sia su `PostgreSQL tenant-aware`.
- Review `Coverage AI` con audit forte: motivo decisione, firma reviewer, diff tra spec originale e corrente, storico revisioni e publish SQL tracciato.
- La console `Copertura AI` aggancia automaticamente il backend SQL reale del tenant selezionato: `studio.db` per gli studi `SQLite` oppure PostgreSQL tenant-aware per gli studi cloud o legacy gia' configurati.
- `Crash test operativo` con simulazione di una giornata reale di studio, repair loop, ticket di riparazione, checklist finale `si/no`, backup blindato completo + incrementale e report persistiti per tenant.
- Il preventivo guidato puo' creare subito il cliente minimale come `Cliente potenziale`, gestisce classificazioni tassonomiche ripetibili `area -> macro-area -> sottobranca`, le porta nei repository SQL/PostgreSQL e somma le relative voci di compenso nella bozza economica; il conferimento resta bloccato finche' l'anagrafica non e' completa.
- Workspace/applicazioni, portali di acquisizione, privacy e audit.
- Registro audit storico spiegabile: se un fascicolo e' stato migrato, ricreato o rimosso, la UI segnala se l'evento e' attivo, riconciliato verso il fascicolo corrente oppure solo storico.
- Runtime AI locale con Lex come strato linguistico sopra motori deterministici.
- Lex espone anche un gateway provider local-first con privacy guard: i dati sensibili restano sui runtime locali e gli esterni sono utilizzabili solo con policy esplicita.
- Lex dispone ora del `Centro Fonti Ufficiali`: Normattiva e Gazzetta Ufficiale alimentano un archivio locale SQLite/JSONL interrogabile dal retrieval, con registro fonti disabilitabile e predisposizione per Ministero Giustizia, PST/PCT, PAT/SIGA, PTT/SIGIT, PDP, CNF, Agenzia Entrate, Garante Privacy, EUR-Lex e authority.
- Lex usa ora fast-path deterministici per i casi operativi, fallback automatico a fonti ufficiali quando il retrieval interno non basta, cache TTL tenant-aware sul retrieval e guardrail che degradano o bloccano le risposte legali senza riferimenti verificati, esponendo sempre `official_sources`, `coverage_gaps`, `fallback_triggered`, `retrieval_cache` e confronto fonti nella risposta finale.
- Il catalogo fonti di Lex distingue ora anche `fonte aperta`, `fonte con registrazione`, `fonte partner`, `fonte riservata` e `portale istituzionale`, cosi' le risposte spiegano quando il fallback web pubblico basta davvero e quando invece servono credenziali, convenzioni o accessi dedicati dello studio.
- Il widget chat di Lex non lascia piu' le richieste operative a prompt generici: `preventivo`, `tariffario`, `fatturazione`, `telematico`, `fascicolo` e `ricerca legale` passano dal bounded workflow anche dalla UI, con contesto studio completo e fallback web ufficiale quando il contesto interno non basta.
- Nei workflow operativi (`preventivo`, `tariffario`, `fattura`, `cabina`, `prossima azione`) Lex usa una via di mezzo governata: prima contesto studio e moduli interni, poi eventuale ricerca esterna solo se la richiesta diventa davvero normativa o il contesto locale non basta, senza gonfiare la risposta con fonti legali inutili.
- Il corpus giurisprudenziale non esplode piu' su query con date e punteggiatura (`sentenza n. 8785 del 08/04/2026`): le ricerche FTS vengono normalizzate prima di interrogare SQLite, cosi' il fallback legale degrada in modo spiegabile invece di lanciare errori interni.
- Multi-tenant amministrabile dalla piattaforma.
- Assistenza remota cliente sempre da `SUPERADMIN`, con schermo WebRTC, microfono opzionale, chat tecnica, audit, consensi ed escalation governata al controllo remoto avanzato esterno.
- `Sito Studio` nativo per ogni tenant: pagine a blocchi, articoli, servizi, professionisti, sedi, contatti, agenda appuntamenti pubblica e sito web pubblicabile senza WordPress esterno.
- Le sezioni pubbliche `Strumenti legali`, `Applicazioni` e `News giuridiche strutturate` non sono esposte in automatico: compaiono sul sito dello studio solo se l'amministratore del sito attiva i flag dedicati da `Sito Studio -> Impostazioni`.

## Architettura

La struttura è organizzata per responsabilità:

- `pct/`
  Logica di dominio, modelli dati, repository e integrazioni legali/PCT.
- `web/bootstrap/`
  Wiring Flask e registrazione route modulari, inclusi `flask_app_factory.py` e `runtime_bundle.py` per mantenere `web/app.py` minimale.
- `web/services/`
  Servizi runtime, autenticazione, sicurezza e contesto UI non proprietario di Lex.
- `/applicazioni` usa ora un runtime dedicato e governabile: `pct/applicazioni_runtime.py` mappa i moduli reali e `web/services/applicazioni_runtime.py` costruisce i pannelli operativi senza gonfiare il blueprint.
- `lex/`
  Modulo autonomo di Lex con blueprint, router, registry, orchestrator, context, retrieval, guard rail, provider, prompt builder, memoria conversazionale e wiring runtime dedicato, incluso il bridge del servizio AI locale e della risoluzione runtime Ollama.
- `web/blueprints/`
  Blueprint verticali per moduli autonomi.
- `web/templates/` e `web/static/`
  UI Jinja2, Bootstrap 5, SCSS compilato.
- `tests/`
  Test di dominio, smoke test Flask, flussi telematici, signer e sicurezza.

Per una mappa più completa vedi [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).
Per il workspace applicazioni vedi anche [docs/APPLICAZIONI_WORKSPACE.md](docs/APPLICAZIONI_WORKSPACE.md).
Per la separazione ferrea tra `Product Pack`, `Studio Local Pack` e `Update Pack` vedi [docs/PACK_ARCHITECTURE.md](docs/PACK_ARCHITECTURE.md).
Per hardening, observability e source policy vedi anche [docs/OBSERVABILITY_AUDIT_PRODUCT.md](docs/OBSERVABILITY_AUDIT_PRODUCT.md) e [docs/LEX_SOURCE_POLICY_SYSTEM.md](docs/LEX_SOURCE_POLICY_SYSTEM.md).
Per il gateway provider di Lex vedi [docs/LEX_GATEWAY.md](docs/LEX_GATEWAY.md).
Per il Centro Fonti Ufficiali Lex vedi [docs/CENTRO_FONTI_UFFICIALI_LEX.md](docs/CENTRO_FONTI_UFFICIALI_LEX.md).
Per il workflow giurisprudenziale di Lex vedi [docs/LEX_GIURISPRUDENZA.md](docs/LEX_GIURISPRUDENZA.md).
Per l'assistenza remota cliente vedi [docs/ASSISTENZA_REMOTA.md](docs/ASSISTENZA_REMOTA.md).
Per il modulo `Sito Studio` vedi [docs/SITO_STUDIO.md](docs/SITO_STUDIO.md).
Per la `Ricerca Studio` globale vedi [docs/RICERCA_STUDIO.md](docs/RICERCA_STUDIO.md).
Per il catalogo master dei template atti vedi [docs/TEMPLATE_ATTI_CATALOGO_MASTER.md](docs/TEMPLATE_ATTI_CATALOGO_MASTER.md).
Per la Suite professionale integrata nel catalogo template atti vedi [docs/template_atti_catalogo_professionale.md](docs/template_atti_catalogo_professionale.md).
Per il modulo SIGP Giudice di Pace vedi [docs/SIGP_GIUDICE_DI_PACE.md](docs/SIGP_GIUDICE_DI_PACE.md).
Per l'acquisizione guidata dei portali vedi [docs/PORTALI_ACQUISIZIONE_GUIDATA.md](docs/PORTALI_ACQUISIZIONE_GUIDATA.md).

## Packaging e deploy coerenti

La build container usa il package Python del repo, ma ora il packaging non dipende piu' da liste duplicate scollegate:

- la versione sorgente vive in `pct/__init__.py`
- `setup.py` legge versione e dipendenze dal manifest governato
- la sorgente runtime e' `requirements/base.txt`
- la sorgente dev e' `requirements/dev.txt`
- gli extra ufficiali vivono in `requirements/pdf.txt`, `requirements/pades.txt`, `requirements/pkcs11.txt`
- `requirements.txt` e `requirements-dev.txt` sono file flat generati da `python tools/sync_packaging_files.py`

Guardrail attivi:

- versione unica riallineata tra package, immagine Docker e release Railway;
- dipendenze DB runtime coerenti tra package e requirements (`sqlalchemy`, `PyMySQL`, `psycopg2-binary`);
- container runtime con bootstrap sicuro del volume `/data`, drop privilegiato verso `iusentra` quando il mount lo consente e fallback esplicito a `root` solo sui bind mount host incompatibili, piu' `HEALTHCHECK` e volume esplicito solo su `/data`;
- CI con check packaging dedicato, lint Ruff piu' severo sui moduli governati, gate mypy sui boundary packaging, coverage minima sui moduli critici ed E2E smoke in pull request;
- workflow E2E notturno separato su GitHub Actions, schedulato in UTC ma allineato alla notte italiana.

Documenti di governance pubblica ora presenti in root:

- `pyproject.toml`
- `LICENSE`
- `SECURITY.md`
- `CONTRIBUTING.md`

## Pack di installazione governati dal SUPERADMIN

La piattaforma distingue ora in modo esplicito tre pack, con governo esclusivo del `SUPERADMIN`:

- `Product Pack`
  runtime installabile e condivisibile: servizi locali, Lex core, prompt/policy, knowledge pubblica, manifest prodotto.
- `Studio Local Pack`
  memoria privata dello studio: `studio.db`, `vectors`, `memory`, `documents`, `attachments`, `audit`, `backups`, `cache`, `keys`.
- `Update Pack`
  aggiornamenti firmati e governati: nuove regole, template, knowledge pubblica aggiornata e migrazioni schema SQL/PostgreSQL.

La superficie ufficiale e' `Piattaforma -> Pack installazione` (`/admin/installazione-pack`).

Da questa cabina il `SUPERADMIN` puo' vedere e rigenerare:

- identita' installazione e chiavi per installazione
- manifest del `Product Pack`
- manifest degli `Studio Local Pack` tenant-aware
- manifest dell'`Update Pack`
- repository SQL/PostgreSQL dei manifest
- servizi locali previsti sul nodo (`hacs-web`, `hacs-lex`, `hacs-embed`, `hacs-jobs`, `hacs-telematico`, `hacs-updater`)

## Assistenza remota cliente

La piattaforma include ora il modulo `Assistenza remota` governato solo dal `SUPERADMIN`.

Superfici ufficiali:

- `Piattaforma -> Assistenza remota` -> `/admin/supporto-remoto`
- pulsante `Assistenza remota` nella panoramica studio durante impersonazione
- pulsante `Assistenza cliente` nella scheda cliente
- pulsante `Sessione tecnica` nel fascicolo

Capability coperte:

- link cliente firmato e senza login
- stanza operatore separata
- screen sharing WebRTC
- audio opzionale
- chat tecnica
- audit leggibile come storia
- consensi espliciti
- escalation verso controllo remoto avanzato esterno solo dopo approvazione del cliente

Requisiti operativi:

- `HTTPS` o `localhost`
- reverse proxy con upgrade WebSocket su `/support/ws/`
- `STUN` consigliato
- `TURN` raccomandato per reti esterne o NAT difficili

La configurazione operativa (`STUN`, `TURN`, secret temporanei, URL controllo avanzato) e' salvabile direttamente dalla console `Piattaforma -> Assistenza remota`, senza modifica manuale dei file sul server.

## Sito Studio nativo

Ogni studio puo' gestire dentro IUSENTRA un sito pubblico nativo, senza integrare WordPress esterno.

Superfici ufficiali:

- `Studio -> Sito Studio` per dashboard, contenuti, branding, sedi e agenda pubblica
- `Piattaforma -> Siti studio` per la console `SUPERADMIN`
- `/web/<public_slug>/` per il sito pubblico dello studio

Capacita' coperte:

- logo, favicon, colori e identita' del sito
- `Sito Studio Builder Pro` con un solo sito per studio/tenant anche se lo studio ha piu' utenti
- otto modelli grafici professionali, design token, font preset, spaziature, radius, ombre ed effetti
- editor visuale a blocchi senza scrittura manuale di JSON
- anteprima desktop/tablet/mobile e validazioni SEO, accessibilita', privacy/cookie e deontologia base
- pagine a blocchi e menu navigabile
- articoli e news editoriali
- servizi, professionisti, sedi, contatti e dove siamo
- richieste contatto e prenotazioni appuntamenti sincronizzabili in agenda studio
- anteprima bozza per utenti autenticati dello studio

Sezioni opzionali pubbliche governate da flag:

- `Strumenti legali`
- `Applicazioni`
- `News giuridiche strutturate`

Queste sezioni sono disponibili nel prodotto ma restano nascoste sul sito pubblico finche' l'amministratore del sito non le attiva da `Sito Studio -> Impostazioni`.

## Ricerca Studio

`Ricerca Studio` e' la ricerca globale operativa di IUSENTRA:

- pagina principale: `/global-search`
- API: `/api/global-search`, `/api/global-search/suggest`, `/api/global-search/reindex`
- indice centrale tenant-aware: `global_search_index`
- SQLite FTS5 quando disponibile, fallback compatibile e predisposizione PostgreSQL `tsvector/pg_trgm`
- adapter per fascicoli, clienti, soggetti, agenda, scadenze, documenti, economia, comunicazioni, template atti, depositi e intelligence interna
- ranking con boost per RG, codici fiscali, email, fascicoli attivi, scadenze imminenti, comunicazioni non lette, documenti ufficiali/firmati e risultati recenti

Lex AI puo' usare la funzione `pct.global_search.service.search_for_lex(...)` come fonte interna verificata per risposte operative sui dati dello studio.

## Strategia storage per studio

La strategia storage non è più una scelta implicita o globale: viene definita dal `SUPERADMIN` quando crea lo studio e resta modificabile dal dettaglio tenant.

- `JSON`
  percorso più leggero per installazioni piccole o cache/snapshot locali.
- `SQLite`
  backend tenant-aware reale per studio, con file `studio.db` creato e agganciato ai moduli core compatibili.
- `PostgreSQL`
  strategia esterna per distribuzione cloud e multi-tenant seria, con configurazione e test connessione dal pannello Superadmin.

La parte importante, adesso, è che lo stato non viene più raccontato in modo generico:

- la matrice modulo-per-modulo vive in [docs/STORAGE_MATRIX.md](docs/STORAGE_MATRIX.md)
- `selected_mode` e `effective_runtime_kind` restano distinti per evitare promesse ambigue
- il profilo runtime locale e containerizzato dichiara esplicitamente `PCT_STORAGE_MODE=SQLITE`
- `PCT_SQLITE_MODE=1` resta supportato come compatibilità legacy, ma non è più l’unico punto di verità
- i moduli economici (`preventivi`, `conferimenti`, `timesheet`, `fatturazione`, `pagamenti`) usano ora lo stesso percorso ufficiale di storage tenant-aware, con parita' reale su SQLite e PostgreSQL
- anche `template atti`, `legal intelligence`, `giurisprudenza`, `repository telematico` e `workspace intelligence` hanno ora repository SQL/PostgreSQL dedicati, con JSON mantenuto come export o bootstrap controllato
- l'`Assistente migrazione dati` esegue ormai il cutover completo del tenant: `studio.db`, repository strutturati laterali, `Update Intelligence` e `Coverage AI`, con report persistito sotto `backup/`
- la pagina `/admin/assistente-migrazione` mostra l'ultima esecuzione reale con domini migrati, diff pre/post, snapshot pre-migrazione, log operativo, failure mode del tenant sporco, rollback guidato e istruzioni operative per la correzione

## Avvio locale

### Docker consigliato

```bash
cp .env.example .env
docker compose build --no-cache
docker compose up -d
```

Il `docker compose` locale avvia:

- `app` per il traffico web Flask/Gunicorn
- `scheduler-worker` per i job periodici separati dal processo HTTP
- `ocr-worker` per la pipeline OCR e indicizzazione documentale asincrona
- `nginx` come reverse proxy locale

Nel profilo container locale il default operativo è esplicito:

- `PCT_STORAGE_MODE=SQLITE`
- `PCT_SQLITE_MODE=1` come compatibilità con i moduli legacy

Accessi:

- [http://localhost](http://localhost)
- [http://localhost:8080](http://localhost:8080)

Bootstrap locale:

- IUSENTRA crea un utente `admin` con password temporanea
- se `PCT_BOOTSTRAP_ADMIN_PASSWORD` non è impostata, la password viene generata al primo avvio e salvata in `./data/auth/bootstrap_admin.json`
- cambio password obbligatorio immediato al primo login

### Avvio Python diretto

```bash
pip install -r requirements.txt
python -m web
```

## Sicurezza bootstrap

Le regole di base oggi sono:

- `.env.example` contiene solo placeholder neutri, mai secret reali.
- Se `PCT_SECRET_KEY` manca o resta un placeholder, l’app usa una chiave effimera e segnala il problema.
- La password bootstrap admin non usa più credenziali fisse: va fornita via `PCT_BOOTSTRAP_ADMIN_PASSWORD` oppure viene generata in modo casuale al primo avvio.
- Il probing PKCS#11 è passivo di default su Windows per evitare crash dei middleware durante smoke test, dashboard e controlli di sola disponibilità.
- Sessioni Flask con cookie `HttpOnly`, `SameSite=Lax`, refresh controllato e timeout.
- Header browser di hardening (`X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, HSTS quando HTTPS è attivo).
- Protezione CSRF sui flussi sensibili di autenticazione e gestione utenti.
- Password bootstrap e password temporanee con cambio obbligatorio prima dell’uso normale del gestionale.
- API v1 con CORS chiuso di default: gli origin esterni vanno esplicitamente autorizzati con `PCT_API_V1_ALLOWED_ORIGINS`.

## Bootstrap multi-tenant

Per ambienti multi-tenant il flusso corretto e' questo:

1. accesso come `SUPERADMIN`
2. creazione studio
3. scelta strategia storage
4. creazione amministratore del tenant
5. configurazione PostgreSQL dal dettaglio storage dello studio
6. test connessione
7. attivazione esplicita del backend core con migrazione e report di consistenza

Questo evita configurazioni globali opache, rende ogni tenant governabile in modo indipendente e impedisce cutover invisibili.

Regole di governance:

- il `SUPERADMIN` e' unico e vive solo a livello piattaforma
- il `SUPERADMIN` ha una superficie dedicata `admin/utenti-piattaforma`, separata dagli utenti degli studi
- il `SUPERADMIN` governa anche `Product Pack`, `Studio Local Pack` e `Update Pack` dal pannello `admin/installazione-pack`
- uno studio non puo' creare o promuovere utenti `SUPERADMIN`
- il pannello `admin/utenti-piattaforma` permette di modificare davvero gli account globali, generare o sostituire il `SUPERADMIN` e trasferire il ruolo a un altro account globale con logout pulito della sessione uscente
- le route legacy di studio `/utenti*` non governano il `SUPERADMIN`: in multi-tenant il superadmin viene reindirizzato al pannello piattaforma e i form utenti studio filtrano e rifiutano sempre il ruolo `SUPERADMIN`
- in multi-tenant l'account `SUPERADMIN` usa sempre la persistenza auth di piattaforma e non eredita ruoli o permessi da `studio.db`
- il `SUPERADMIN` fuori dall'impersonazione non entra nei moduli di studio: la shell operativa viene sostituita dalla sola navigazione piattaforma e le route non piattaforma lo riportano al pannello admin
- ogni studio ha il proprio `AMMINISTRATORE` tenant-aware
- se esistono account globali anomali non `SUPERADMIN`, il pannello `admin/utenti-piattaforma` consente di spostarli davvero dentro uno studio preservando credenziali, audit e ruolo tenant-aware oppure di correggerli direttamente dalla piattaforma
- le console piattaforma che operano su dati di studio, come `Update Intelligence`, lavorano sempre sul tenant selezionato e non su un archivio globale implicito
- nelle superfici superadmin il nome autorevole dello studio resta quello del tenant di piattaforma; un eventuale nome diverso dentro `config/studio.json` viene mostrato solo come configurazione interna, non come nuovo studio
- il bootstrap applicativo inizializza in modo idempotente l'identita' installazione e i manifest dei pack, ma la rigenerazione governata resta disponibile solo nella superficie `SUPERADMIN`

## Stato storage professionale

Oggi i domini `utenti`, `clienti`, `fascicoli`, `agenda`, `scadenziario`, `timesheet`, `preventivi`, `conferimenti`, `fatturazione` e `pagamenti` possono lavorare in lettura e scrittura anche su PostgreSQL tenant-aware.

Regole operative:

- `JSON` resta backend legacy o ponte di bootstrap, non piu' source of truth professionale per i moduli economici e core gia' migrati.
- `SQLite` resta backend locale o fallback controllato per tenant non ancora cutoverizzati.
- `PostgreSQL` diventa backend effettivo solo dopo test connessione, migrazione ufficiale e attivazione esplicita.
- se PostgreSQL e' attivo ma non disponibile, i domini migrati non degradano in modo invisibile su JSON.

Comando ufficiale di migrazione:

```bash
iusentra migrate --to=postgres --tenant=<slug-tenant>
```

Rollback guidato:

```bash
iusentra migrate --tenant=<slug-tenant> --rollback
```

Check rapido di operativita' end-to-end:

```bash
iusentra demo-check --tenant=<slug-tenant>
```

Il comando verifica se lo studio e' pronto per un uso reale e racconta il prossimo passo del ciclo `cliente -> incasso`.

## Demo studio reale

La demo mentale finale non e' piu' un racconto separato dal prodotto: e' una capability verificabile.

- La dashboard mostra il riquadro `Studio reale in 5 minuti` con lo stato dei sette passaggi chiave.
- Il timesheet espone il riepilogo di valorizzazione e puo' generare la parcella dalle voci validate.
- Il portale cliente, la cartella cliente, il fascicolo e la dashboard economica usano lo stesso flusso condiviso, con il fascicolo come cabina unica fino all'incasso.
- La CLI `iusentra demo-check` riassume lo stato dello studio e la prossima azione utile.

Per il percorso completo vedi [docs/DEMO_STUDIO_REALE.md](docs/DEMO_STUDIO_REALE.md).

## CI GitHub

La CI non si limita più alla sola sincronizzazione branch. Il workflow principale applicativo è `.github/workflows/ci.yml` e copre i push in modo generico, senza dipendere da due branch hardcoded.

Il mirror dei due branch gemelli ammessi è ora separato dalla CI applicativa: `.github/workflows/sync-claude-to-codex.yml` riallinea automaticamente `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV` in entrambe le direzioni, mentre `scripts/repo_hygiene.ps1` installa i hook versionati in `.githooks/` per mantenere coerenti anche i branch locali.

La pipeline applicativa esegue:

- governance repo e modularizzazione (`Governance repo`)
- lint statico conservativo su errori bloccanti (`ruff` + `flake8`)
- import/syntax check
- smoke test Flask sul runtime reale e su `create_app()`
- smoke del worker scheduler dedicato
- test core su storage SQLite, osservabilità runtime e worker OCR persistente
- suite `pytest` core su Linux
- job matrix Linux / Windows / macOS per Local Signer e componenti correlati

Ai workflow applicativi si affiancano ora controlli DevSecOps dedicati:

- `CodeQL` per code scanning statico
- `Dependency Review` sulle pull request
- `Security Supply Chain` con `pip-audit` e generazione SBOM
- `Performance Nightly` per benchmark leggero e regressioni di runtime

I workflow vivono in `.github/workflows/`.
La vista live del workflow e' [Actions / CI](https://github.com/antmm2605/IUSENTRA/actions/workflows/ci.yml).
Le dipendenze di sviluppo della pipeline sono raccolte in `requirements-dev.txt`.
Le dipendenze oggi sono organizzate anche sotto `requirements/` con separazione tra runtime base e sviluppo.
Il gate lint attuale è volutamente centrato su errori sintattici e import/fatal error, così la CI resta verde mentre il debito storico di stile viene ridotto in modo progressivo.
Il job `Governance repo` esegue `tools/check_repo_governance.py` e blocca regressioni su modularizzazione, budget dei moduli e confini tra `web/` e `lex/`.
La pipeline notturna `.github/workflows/performance-nightly.yml` esegue `tools/performance_smoke.py` per misurare startup, login, metriche runtime e tempi base di Lex.

## Golden path ufficiali

I flussi critici non sono piu' documentati soltanto a parole: esiste una suite ufficiale eseguibile con report persistito.

```bash
iusentra golden-path
```

Il comando:

- esegue i golden path ufficiali del prodotto
- salva report JSON e report leggibile Markdown sotto `./data/governance/`
- alimenta la vista `Piattaforma -> Governance prodotto`

I flussi oggi presidiati come golden path di primo livello sono:

- bootstrap, login e superfici admin
- migrazione tenant, diff e cutover
- workflow `cliente -> fascicolo -> parcella -> incasso`
- `Coverage AI` con review e publish SQL
- `Update Intelligence` con review e pubblicazione news
- telematico ufficiale

La matrice completa e i test di riferimento vivono in [docs/E2E_TESTING_MATRIX.md](docs/E2E_TESTING_MATRIX.md).

Test ufficiali nominati chiaramente:

- `tests/e2e/test_studio_reale_flow.py`
- `tests/e2e/test_ai_pipeline_full.py`
- `tests/e2e/test_tenant_migration_full.py`
- `tests/e2e/test_operational_crash_day.py`

## Crash test operativo e backup blindato

La cabina `Piattaforma -> Crash test operativo` esegue il test di una giornata reale di studio senza fermarsi a un riepilogo teorico:

- avvio e setup studio con stato chiaro di database, AI e worker
- blocco dati sporchi su clienti e fascicoli
- workflow economico `cliente -> fascicolo -> parcella -> incasso`
- pipeline AI con review, audit, reject e publish SQL
- migrazione tenant con snapshot, diff e rollback
- observability azionabile per operatore non tecnico

In piu':

- genera ticket di riparazione leggibili
- salva report JSON persistiti nel backup del tenant
- pianifica autotest di riparazione alle `07:00`, `13:30`, `19:30`
- pianifica backup blindato completo + incrementale alle `23:50`
- usa i test E2E ufficiali quando `pytest` e' disponibile e, nel runtime di produzione, passa automaticamente a controlli operativi interni equivalenti senza dipendere dai tool di sviluppo

Comandi ufficiali:

```bash
iusentra crash-test-operativo --tenant=<slug-tenant>
iusentra backup-blindato --tenant=<slug-tenant>
```

Configurazioni operative:

- `PCT_BACKUP_LOCAL_MIRROR_DIR`: cartella locale del PC cliente dove salvare la copia giornaliera
- `PCT_BACKUP_SECONDARY_MIRROR_DIR`: seconda destinazione esterna o sincronizzata cloud
- `PCT_BACKUP_SECONDARY_LABEL`: etichetta leggibile della seconda destinazione, ad esempio `Google Drive studio`

Dettagli completi in [docs/CRASH_TEST_OPERATIVO.md](docs/CRASH_TEST_OPERATIVO.md).

## Update Intelligence

IUSENTRA include ora un motore dedicato di aggiornamento normativo e giurisprudenziale:

- monitora fonti ufficiali e istituzionali
- salva area di acquisizione raw e documenti normalizzati
- classifica con AI il contenuto tra normativa, giurisprudenza, prassi, news e casi incerti
- confronta il risultato con l'archivio interno
- apre una coda revisioni amministrativa per i contenuti strutturati
- pubblica news giuridiche tracciabili nella UI dedicata
- usa repository SQL locale o PostgreSQL tenant-aware in modo coerente con il backend migrato dello studio
- in contesto multi-tenant il `SUPERADMIN` seleziona esplicitamente lo studio da governare, mentre archivio, review e publish restano segregati per tenant
- se il nome configurato nello `studio.json` del tenant differisce dal nome registrato in piattaforma, il pannello superadmin mostra prima il nome del tenant e solo come nota il nome interno configurato

Superfici principali:

- `/legal-intelligence/news`
- `/admin/aggiornamenti-legali`
- `/admin/aggiornamenti-legali/fonti`
- `/admin/aggiornamenti-legali/staging`
- `/admin/aggiornamenti-legali/analisi`
- `/admin/aggiornamenti-legali/archivio`
- `/admin/aggiornamenti-legali/review`

Comando CLI:

```bash
iusentra aggiornamenti-legali
```

Dettagli architetturali e regole operative in [docs/LEGAL_UPDATE_INTELLIGENCE.md](docs/LEGAL_UPDATE_INTELLIGENCE.md).

## Coverage AI

La console `Copertura AI` non si limita piu' a generare draft. Il flusso governato e' ora:

`DB -> auditor -> gap queue -> AI + retrieval -> draft v2 -> review -> publish SQL -> training implicito`

La review admin include:

- contesto di retrieval usato per generare il draft
- salvataggio controllato della spec JSON
- motivazione obbligatoria per approvazione o rifiuto
- firma reviewer obbligatoria per chiudere la revisione
- diff tra spec originaria e versione corrente
- storico revisioni persistito nel repository SQL
- policy di autopublish leggibile insieme al draft
- evidenza `AI -> review umana -> publish SQL` ricostruibile via audit

Dettagli in [docs/LEGAL_COVERAGE_AUTOFILL.md](docs/LEGAL_COVERAGE_AUTOFILL.md).

## Osservabilità tecnica

Il pannello Superadmin include una vista tecnica dedicata in `/admin/osservabilita`.

- metriche HTTP con media, P95 e max per endpoint
- tempo medio del primo token Lex
- stato del provider AI locale
- queue depth e throughput OCR dell'ultima ora
- stato operativo di storage e runtime applicativo
- segnali di degrado con codici tassonomici, soglie operative, messaggio operatore e rimedi per errori 5xx, OCR, worker OCR, AI locale, PEC/IMAP e storage
- logging strutturato con masking automatico di CF, email, IBAN, telefoni e altri dati sensibili nei log applicativi
- circuit breaker operativi su runtime AI locale e sincronizzazione PEC, per evitare loop di timeout e rendere gli errori leggibili
- endpoint JSON operativo in `/admin/system-health` con stato `scheduler`, `ocr`, `ai` e `db`

Sul bounded context AI, il confine corretto adesso è:

- `web/blueprints/assistente.py` come facciata HTTP sottilissima
- `lex/runtime_dependencies.py` come wiring runtime del modulo
- `lex/providers/local_ai_service.py` e `lex/providers/ollama_runtime.py` come owner del runtime AI locale e della risoluzione Ollama
- `lex/router.py` e `lex/registry.py` come ingresso applicativo riusabile
- `lex/context/`, `lex/retrieval/`, `lex/guards/`, `lex/providers/`, `lex/tools/`, `lex/workflows/` come sottosistemi del pacchetto

## Test utili

Golden path ufficiali eseguibili:

```bash
iusentra golden-path
```

Il comando esegue le suite ufficiali e persiste un report leggibile sotto `./data/governance/`, poi la pagina `admin/governance` mostra stato `pass/fail` dei flussi core:

- bootstrap, login e superfici admin
- migrazione tenant, diff e cutover
- workflow business `cliente -> fascicolo -> parcella -> incasso`
- `Coverage AI` review/publish SQL
- `Update Intelligence` review/publish news
- telematico ufficiale

I tre golden path "citizen di primo livello" sono questi:

```bash
python -m pytest tests/e2e/test_studio_reale_flow.py -q
python -m pytest tests/e2e/test_ai_pipeline_full.py -q
python -m pytest tests/e2e/test_tenant_migration_full.py -q
```

Esecuzione rapida locale:

```bash
python -m pytest tests/test_auth.py tests/test_web_bootstrap.py tests/test_web_security.py -q
```

Suite più ampia:

```bash
python -m pytest tests -q
```

Suite affidabilita' consigliate dopo modifiche a storage, osservabilita' o moduli admin nuovi:

```bash
python -m pytest tests/test_observability_runtime.py tests/test_migration_assistant.py tests/test_storage_postgres_migration.py tests/test_operational_surfaces.py tests/test_legal_coverage_surface.py tests/test_legal_updates_pipeline.py -q
```

Test telematici di riferimento:

```bash
python -m pytest tests/test_simulazione_deposito.py -v
python -m pytest tests/test_polisweb.py -q
python -m pytest tests/test_pdp_penale_web.py -q
```

## Documentazione operativa

- [docs/QUICKSTART.md](docs/QUICKSTART.md) — avvio rapido locale, bootstrap admin e verifiche iniziali.
- [docs/DEPLOY.md](docs/DEPLOY.md) — release, Docker locale, Railway, CI e controlli finali.
- [docs/STORAGE_MATRIX.md](docs/STORAGE_MATRIX.md) — matrice esplicita dei backend storage per modulo e stato di maturità.
- [docs/production-hardening.md](docs/production-hardening.md) — hardening produzione: JSON -> DB, Redis, RQ, Gunicorn, sicurezza, health, backup e monitoring.
- [docs/DEMO_STUDIO_REALE.md](docs/DEMO_STUDIO_REALE.md) — percorso ufficiale `cliente -> incasso`, check operativo e demo mentale in meno di 5 minuti.
- [docs/CHECKLIST_ATTI.md](docs/CHECKLIST_ATTI.md) — catalogo professionale delle checklist atti con aree, branche, sottobranche, canali di deposito e naming cartelle in formato italiano.
- [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md) — checklist di release, tagging, changelog e sincronizzazione ambienti.
- [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md) — struttura moduli, flussi e confini applicativi.
- [CHANGELOG.md](CHANGELOG.md) — traccia delle release e delle modifiche rilevanti.
- [AGENTS.md](AGENTS.md) — regole operative del repository, release, sicurezza e PCT.

## Stato del progetto

Il codice oggi è più maturo di una semplice demo:

- routing web già in fase avanzata di modularizzazione
- repository strutturati per Lex su giurisprudenza, intelligence, telematico, template, preventivi e applicazioni
- test coverage distribuita su molti domini reali
- bootstrap di sicurezza più severo per uso professionale

`web/app.py` oggi è una factory sottile: delega la costruzione base a `web/bootstrap/flask_app_factory.py`, l'assemblaggio dei runtime a `web/bootstrap/runtime_bundle.py` e il wiring finale a `web/bootstrap/app_wiring.py`. Il registro blueprint è dichiarativo in `web/bootstrap/blueprint_registry.py`, così il wiring non dipende più da una lista manuale fragile. Lo scheduler non parte più dal processo web: i job periodici vivono nel worker dedicato `pct.scheduler_worker`, eseguito in locale dal servizio `scheduler-worker` e predisposto per un servizio separato anche in produzione. Sul lato Lex, il contesto studio include ora anche l’headline del cockpit `Motori Legali`, così il bounded context AI ragiona sullo stesso stato operativo mostrato dalla dashboard.




