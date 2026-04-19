# IUSENTRA — Gestionale per Studi Legali

IUSENTRA è una web app Flask per studi legali italiani, con focus su gestione operativa di studio, fascicoli, PCT/portali telematici, documenti, scadenze, intelligence legale e assistenza AI locale.

La repo oggi non è più solo un tool CLI per il Processo Civile Telematico: contiene un gestionale web ampio, modulare e multi-dominio, con layer separati per bootstrap Flask, servizi UI/runtime e logica di dominio.

## Cosa fa oggi

- Gestione fascicoli, clienti, soggetti, agenda e scadenziario.
- Deposito telematico civile, penale e dashboard servizi telematici.
- Workflow completo `cliente -> preventivo -> conferimento -> fascicolo -> attivita' -> parcella -> incasso`.
- Timesheet operativo con valorizzazione del tempo e generazione parcella dalle attivita' validate.
- Fatturazione, pagamenti, saldo cliente e KPI economici per studio, cliente e fascicolo.
- Template atti, strumenti legali e workspace professionali.
- Giurisprudenza, legal intelligence, repository strutturati per Lex.
- Motore `Update Intelligence` per monitoraggio normativo, giurisprudenziale e di prassi con area di acquisizione, coda revisioni e pagina news giuridiche strutturate.
- Pipeline `Coverage AI` per audit tassonomico, gap queue, draft v2, review e publish SQL con retrieval interno, funzionante sia su `SQLite locale` sia su `PostgreSQL tenant-aware`.
- La console `Copertura AI` aggancia automaticamente il backend SQL reale del tenant selezionato: `studio.db` per gli studi `SQLite` oppure PostgreSQL tenant-aware per gli studi cloud o legacy gia' configurati.
- Workspace/applicazioni, portali di acquisizione, privacy e audit.
- Runtime AI locale con Lex come strato linguistico sopra motori deterministici.
- Multi-tenant amministrabile dalla piattaforma.

## Architettura

La struttura è organizzata per responsabilità:

- `pct/`
  Logica di dominio, modelli dati, repository e integrazioni legali/PCT.
- `web/bootstrap/`
  Wiring Flask e registrazione route modulari, inclusi `flask_app_factory.py` e `runtime_bundle.py` per mantenere `web/app.py` minimale.
- `web/services/`
  Servizi runtime, autenticazione, sicurezza e contesto UI non proprietario di Lex.
- `lex/`
  Modulo autonomo di Lex con blueprint, router, registry, orchestrator, context, retrieval, guard rail, provider, prompt builder, memoria conversazionale e wiring runtime dedicato, incluso il bridge del servizio AI locale e della risoluzione runtime Ollama.
- `web/blueprints/`
  Blueprint verticali per moduli autonomi.
- `web/templates/` e `web/static/`
  UI Jinja2, Bootstrap 5, SCSS compilato.
- `tests/`
  Test di dominio, smoke test Flask, flussi telematici, signer e sicurezza.

Per una mappa più completa vedi [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

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
- la pagina `/admin/assistente-migrazione` mostra l'ultima esecuzione reale con domini migrati, parita' di consistenza, errori bloccanti e istruzioni operative per la correzione

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

Check rapido di operativita' end-to-end:

```bash
iusentra demo-check --tenant=<slug-tenant>
```

Il comando verifica se lo studio e' pronto per un uso reale e racconta il prossimo passo del ciclo `cliente -> incasso`.

## Demo studio reale

La demo mentale finale non e' piu' un racconto separato dal prodotto: e' una capability verificabile.

- La dashboard mostra il riquadro `Studio reale in 5 minuti` con lo stato dei sette passaggi chiave.
- Il timesheet espone il riepilogo di valorizzazione e puo' generare la parcella dalle voci validate.
- Il portale cliente, la cartella cliente, il fascicolo e la dashboard economica usano lo stesso flusso condiviso.
- La CLI `iusentra demo-check` riassume lo stato dello studio e la prossima azione utile.

Per il percorso completo vedi [docs/DEMO_STUDIO_REALE.md](docs/DEMO_STUDIO_REALE.md).

## CI GitHub

La CI non si limita più alla sola sincronizzazione branch. Il workflow principale applicativo è `.github/workflows/ci.yml` e copre i push in modo generico, senza dipendere da due branch hardcoded.

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

## Update Intelligence

IUSENTRA include ora un motore dedicato di aggiornamento normativo e giurisprudenziale:

- monitora fonti ufficiali e istituzionali
- salva area di acquisizione raw e documenti normalizzati
- classifica con AI il contenuto tra normativa, giurisprudenza, prassi, news e casi incerti
- confronta il risultato con l'archivio interno
- apre una coda revisioni amministrativa per i contenuti strutturati
- pubblica news giuridiche tracciabili nella UI dedicata
- usa repository SQL locale o PostgreSQL tenant-aware in modo coerente con il backend migrato dello studio

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

## Osservabilità tecnica

Il pannello Superadmin include una vista tecnica dedicata in `/admin/osservabilita`.

- metriche HTTP con media, P95 e max per endpoint
- tempo medio del primo token Lex
- stato del provider AI locale
- queue depth e throughput OCR dell'ultima ora
- stato operativo di storage e runtime applicativo
- segnali di degrado con rimedi operativi per errori 5xx, OCR, AI locale e storage

Sul bounded context AI, il confine corretto adesso è:

- `web/blueprints/assistente.py` come facciata HTTP sottilissima
- `lex/runtime_dependencies.py` come wiring runtime del modulo
- `lex/providers/local_ai_service.py` e `lex/providers/ollama_runtime.py` come owner del runtime AI locale e della risoluzione Ollama
- `lex/router.py` e `lex/registry.py` come ingresso applicativo riusabile
- `lex/context/`, `lex/retrieval/`, `lex/guards/`, `lex/providers/`, `lex/tools/`, `lex/workflows/` come sottosistemi del pacchetto

## Test utili

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
- [docs/DEMO_STUDIO_REALE.md](docs/DEMO_STUDIO_REALE.md) — percorso ufficiale `cliente -> incasso`, check operativo e demo mentale in meno di 5 minuti.
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




