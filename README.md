# HACS — Gestionale per Studi Legali

HACS è una web app Flask per studi legali italiani, con focus su gestione operativa di studio, fascicoli, PCT/portali telematici, documenti, scadenze, intelligence legale e assistenza AI locale.

La repo oggi non è più solo un tool CLI per il Processo Civile Telematico: contiene un gestionale web ampio, modulare e multi-dominio, con layer separati per bootstrap Flask, servizi UI/runtime e logica di dominio.

## Cosa fa oggi

- Gestione fascicoli, clienti, soggetti, agenda e scadenziario.
- Deposito telematico civile, penale e dashboard servizi telematici.
- Template atti, preventivi, fatturazione e strumenti legali.
- Giurisprudenza, legal intelligence, repository strutturati per Lex.
- Workspace/applicazioni, portali di acquisizione, privacy e audit.
- Runtime AI locale con Lex come strato linguistico sopra motori deterministici.
- Multi-tenant amministrabile dalla piattaforma.

## Architettura

La struttura è organizzata per responsabilità:

- `pct/`
  Logica di dominio, modelli dati, repository e integrazioni legali/PCT.
- `web/bootstrap/`
  Wiring Flask e registrazione route modulari.
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

Stato attuale del runtime:

- `JSON` e `SQLite` sono backend effettivi già usati dai moduli compatibili.
- `PostgreSQL` è già configurabile, verificabile e documentato come strategia target; il passaggio dei moduli core allo storage transazionale esterno procede in modo progressivo e governato per tenant.

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
- `nginx` come reverse proxy locale

Accessi:

- [http://localhost](http://localhost)
- [http://localhost:8080](http://localhost:8080)

Bootstrap locale:

- HACS crea un utente `admin` con password temporanea
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

Per ambienti multi-tenant il flusso corretto è:

1. accesso come `SUPERADMIN`
2. creazione studio
3. scelta strategia storage
4. creazione amministratore del tenant
5. eventuale configurazione PostgreSQL dal dettaglio storage dello studio

Questo evita configurazioni globali opache e rende ogni tenant governabile in modo indipendente.

## CI GitHub

La CI non si limita più alla sola sincronizzazione branch. La pipeline applicativa esegue:

- governance repo e modularizzazione (`Governance repo`)
- lint statico conservativo su errori bloccanti (`ruff` + `flake8`)
- import/syntax check
- smoke test Flask sul runtime reale e su `create_app()`
- smoke del worker scheduler dedicato
- suite `pytest` core su Linux
- job matrix Linux / Windows / macOS per Local Signer e componenti correlati

I workflow vivono in `.github/workflows/`.
Il workflow principale applicativo è `.github/workflows/ci.yml`.
La vista live del workflow è [Actions / CI](https://github.com/antmm2605/hacs/actions/workflows/ci.yml).
Le dipendenze di sviluppo della pipeline sono raccolte in `requirements-dev.txt`.
Il gate lint attuale è volutamente centrato su errori sintattici e import/fatal error, così la CI resta verde mentre il debito storico di stile viene ridotto in modo progressivo.
Il job `Governance repo` esegue `tools/check_repo_governance.py` e blocca regressioni su modularizzazione, budget dei moduli e confini tra `web/` e `lex/`.

Sul bounded context AI, il confine corretto adesso Ã¨:

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

Test telematici di riferimento:

```bash
python -m pytest tests/test_simulazione_deposito.py -v
python -m pytest tests/test_polisweb.py -q
python -m pytest tests/test_pdp_penale_web.py -q
```

## Documentazione operativa

- [docs/QUICKSTART.md](docs/QUICKSTART.md) — avvio rapido locale, bootstrap admin e verifiche iniziali.
- [docs/DEPLOY.md](docs/DEPLOY.md) — release, Docker locale, Railway, CI e controlli finali.
- [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md) — struttura moduli, flussi e confini applicativi.
- [AGENTS.md](AGENTS.md) — regole operative del repository, release, sicurezza e PCT.

## Stato del progetto

Il codice oggi è più maturo di una semplice demo:

- routing web già in fase avanzata di modularizzazione
- repository strutturati per Lex su giurisprudenza, intelligence, telematico, template, preventivi e applicazioni
- test coverage distribuita su molti domini reali
- bootstrap di sicurezza più severo per uso professionale

`web/app.py` oggi è una factory sottile: crea l'app Flask, applica i default di sicurezza, costruisce i runtime e delega il wiring a `web/bootstrap/app_wiring.py`. Lo scheduler non parte più dal processo web: i job periodici vivono nel worker dedicato `pct.scheduler_worker`, eseguito in locale dal servizio `scheduler-worker` e predisposto per un servizio separato anche in produzione. Il prossimo passo naturale resta spezzare ulteriormente i runtime più densi in `web/services/`, mantenendo documentazione e CI allo stesso livello del codice.
