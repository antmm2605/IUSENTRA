# Architettura IUSENTRA

## Obiettivo

IUSENTRA è un gestionale web per studi legali con specializzazioni verticali su:

- fascicoli e documenti
- agenda e scadenziario
- PCT, PST/polisWeb, PDP, PAT e workflow telematici
- template atti, preventivi, fatturazione
- intelligence legale, giurisprudenza e assistenza AI locale
- amministrazione multi-tenant

L’architettura segue una regola semplice: il modello AI non è la fonte della verità. La verità resta nel dominio, nei repository strutturati, nello stato runtime e nelle fonti ufficiali.

## Layer applicativi

### `pct/` — dominio e logica di business

Qui vivono i modelli dati, i repository e le integrazioni verticali:

- `auth.py`
  utenti, ruoli, audit, reset password, 2FA
- `fascicoli.py`, `clienti.py`, `agenda.py`, `scadenziario.py`
  modelli core dello studio
- `deposito.py`, `polisWeb.py`, `pst_catalog.py`, `pdp_penale_workflow.py`, `telematico_workflow.py`
  motore telematico
- `giurisprudenza.py`, `giurisprudenza_corpus.py`, `legal_intelligence.py`
  motori legali e corpus professionale
- `template_atti.py`, `preventivi.py`, `applicazioni_catalogo.py`, `applicazioni_runtime.py`
  domini applicativi verticali e mappatura runtime dei workspace applicativi
- `tenant.py`, `storage.py`, `database.py`
  strategia storage multi-tenant, manifest, provisioning e backend SQLite per studio

### `web/bootstrap/` — wiring Flask

Qui si registra ciò che viene estratto dal monolite di `web/app.py`:

- route modulari per auth, dashboard, telematico, privacy, calendario, checklist, soggetti
- registrazione blueprint
- runtime template condiviso
- handler errori
- `flask_app_factory.py` per la factory base Flask e i default di sicurezza
- `runtime_bundle.py` per assemblare i runtime del profilo web completo o del profilo scheduler
- `app_wiring.py` come delegatore minimo verso registri verticali
- `core_surface_wiring.py`, `fascicoli_surface_wiring.py`, `telematico_surface_wiring.py`
  registri di wiring per superfici omogenee, così il bootstrap resta governabile

Questa cartella deve contenere moduli piccoli e leggibili, non nuovi monoliti.

### `web/services/` — servizi runtime/UI

Qui stanno i servizi trasversali che non appartengono a un singolo dominio:

- `auth_runtime.py`
  sessione, login, timeout, enforcement sicurezza accesso
- `security_runtime.py`
  secret bootstrap, cookie/session hardening, header browser, CSRF
- `runtime_settings.py`
  impostazioni runtime derivate da configurazione studio
- `observability_runtime.py`
  metriche leggere HTTP/Lex e payload tecnico per pannello e API di osservabilita'
- `applicazioni_runtime.py`
  orchestration UI/runtime dei workspace applicativi reali, con pannelli operativi coerenti e azioni inline
- servizi di contesto studio, sicurezza e compatibilità UI non proprietaria di Lex

### `pct/scheduler.py`, `pct/scheduler_worker.py` e `pct/ocr_worker.py`

I job periodici non devono vivere nel processo HTTP:

- `pct/scheduler.py`
  definisce e registra i job APScheduler
- `pct/scheduler_worker.py`
  costruisce una Flask app leggera in profilo `SCHEDULER_ONLY`, avvia lo scheduler e mantiene vivo il worker dedicato
- `pct/ocr_worker.py`
  possiede la coda OCR persistente e il pool che elabora OCR e indicizzazione fuori dal processo HTTP

Regola architetturale: `web/app.py` non avvia mai direttamente lo scheduler.

### `lex/` — modulo assistente autonomo

Lex ora ha una casa applicativa dedicata:

- `blueprint.py`
  factory del blueprint Flask compatibile con gli endpoint storici e costruttore runtime del blueprint stesso
- `router.py`, `contracts.py`, `registry.py`
  ingresso applicativo del bounded context: tipi condivisi, contratti e costruzione del servizio riusabile
- `runtime_dependencies.py`
  wiring runtime del modulo: login Flask, runtime Ollama, export documento e contesto studio entrano in Lex da qui senza dipendere direttamente dal lato `web/`
- `providers/local_ai_service.py`, `providers/ollama_runtime.py`, `providers/health.py`
  owner del servizio AI locale, della risoluzione runtime Ollama e della salute provider; i wrapper in `web/services/` restano solo facciate legacy
- `gateway/`
  instradamento provider local-first, privacy guard, fallback e diagnostica senza leakage di chiavi API
- `formatting/document_export.py`, `guards/legal_reference_guard.py`, `memory/web_execution.py`
  proprietari del bridge operativo prima disperso in `web/services/assistente_*`
- `routes.py`
  superficie HTTP dell'assistente
- `service.py`
  superficie applicativa compatibile: HTTP storico e casi d'uso bounded-context
- `orchestrator.py`
  coordinamento centrale molto sottile tra compatibilita' legacy e flusso bounded-context
- `orchestrator_http.py`
  compatibilita' HTTP legacy: status, warmup, context, chat, export documento e payload UI
- `orchestrator_workflow.py`
  pipeline bounded-context pura per request, retrieval, guardie, provider, formatter, telemetry e memory
- `api/`, `application/`, `domain/`, `context/`, `retrieval/`, `guards/`, `formatting/`, `providers/`, `memory/`, `telemetry/`, `prompts/`, `tools/`, `workflows/`, `admin/`
  sottosistemi piccoli e separati, riusabili anche fuori dalla chat
- i moduli storici `web/services/assistente_*.py` e i bridge `web/services/local_ai_runtime.py`, `web/services/ollama_runtime.py` restano solo facciate compatibili: follow-up, routing sociale, prompt, riepilogo giornaliero, export documentale, guardie legali, riconoscimento web execution e runtime AI locale vivono ora in `lex/`

### `web/blueprints/` — moduli web verticali

I blueprint raccolgono superfici applicative più autonome, ad esempio:

- API v1
- assistente come facciata compatibile del modulo `lex/`
- email client
- impostazioni
- notifiche
- fatturazione
- template atti
- giurisprudenza
- legal intelligence

### `web/templates/` e `web/static/`

- Jinja2 per rendering server-side
- Bootstrap 5 come base UI
- SCSS modulare in `web/static/scss/`
- CSS compilati nel build Docker

## Bootstrap Flask

Il punto di ingresso resta `web/app.py`, ma il ruolo corretto è:

1. creare l’app Flask
2. applicare configurazione e sicurezza base
3. registrare runtime condivisi
4. registrare blueprint e route modulari
5. esporre helper e servizi comuni

Lo scheduler deve restare fuori dal processo web: `web/app.py` costruisce il runtime HTTP, mentre `pct.scheduler_worker` possiede l'avvio dei job periodici.

`web/app.py` deve restare una facciata minima: riceve la configurazione, delega la factory base, delega l'assemblaggio dei runtime e chiama solo il wiring finale.

## Osservabilita' e prestazioni

IUSENTRA espone una superficie tecnica esplicita per misurare il comportamento reale del runtime:

- endpoint `/api/metriche/runtime`
  snapshot di latenza HTTP, primo token Lex, stato OCR e provider locali
- pannello `/admin/osservabilita`
  vista Superadmin con queue depth OCR, throughput, bucket HTTP e stato provider
- `tools/performance_smoke.py`
  benchmark operativo rapido per startup, login, metriche runtime, build context Lex e retrieval base
- `.github/workflows/performance-nightly.yml`
  benchmark notturno per intercettare regressioni di performance in modo automatico

## Strategia storage

La governance storage è per-tenant e parte dal Superadmin.

### Livelli supportati oggi

- `JSON`
  backend locale semplice, utile per snapshot, ambienti leggeri e aree che non richiedono ancora storage transazionale.
- `SQLite`
  backend tenant-aware già operativo tramite `pct/storage.py` e `studio.db`, usato dai moduli core compatibili.
- `PostgreSQL`
  strategia esterna configurabile dal Superadmin con test connessione e manifest di tenant; è la destinazione prevista per distribuzione cloud e multi-tenant seria.

### Regola di verità

Nel tenant distinguiamo sempre:

- `selected_mode`
  strategia scelta dal Superadmin
- `effective_runtime_kind`
  backend effettivamente in uso oggi dai moduli core compatibili

Questo evita ambiguità: non dichiariamo attivo un backend esterno se il tenant sta ancora lavorando su JSON o SQLite.

### Default runtime dichiarato

Quando il tenant non forza una strategia diversa, il runtime operativo dichiarato usa:

- `PCT_STORAGE_MODE=SQLITE`
- `PCT_SQLITE_MODE=1` solo come compatibilità legacy

Questo mantiene coerenti compose locale, container web e logica di risoluzione runtime senza lasciare il default implicito.

## Flussi chiave

### Autenticazione

1. login con sessione Flask
2. eventuale secondo fattore TOTP
3. timeout per inattività
4. audit login/logout/errori
5. cambio password forzato per credenziali bootstrap o temporanee

### Telematico

1. catalogo ufficiale e versionato in `pst_catalog.py`
2. consultazione/import via `polisWeb.py`
3. deposito via `deposito.py` e workflow correlati
4. monitoraggio fonti e alert in `legal_intelligence.py`
5. risposta Lex solo sopra stato e regole già verificate

### Giurisprudenza

1. ingestione/sync sorgenti in `giurisprudenza.py`
2. normalizzazione e corpus professionale SQLite
3. guardrail su citabilità e PDF reale
4. ranking e consultazione corpus-first
5. spiegazione LLM solo dopo recupero verificato

### Lex

Lex usa repository strutturati derivati dalla repo, non codice grezzo:

- applicazioni
- legal intelligence
- giurisprudenza
- telematico
- template atti
- catalogo master template atti versionato
- preventivi

Il routing deve restare deterministico; il modello serve a spiegare bene, non a decidere da solo cosa è vero.

## Sicurezza bootstrap

Le regole attuali da mantenere:

- mai secret reali nei file example
- `PCT_SECRET_KEY` forte o fallback effimero con warning
- cookie sessione blindati
- header browser minimi di hardening
- protezione CSRF sui flussi sensibili
- password iniziale o temporanea da cambiare subito

## Testing e CI

La maturità della repo richiede una pipeline continua composta da:

- lint statico conservativo su errori bloccanti
- import/syntax check
- smoke Flask
- `pytest` core su Linux
- matrix Windows/macOS/Linux per Local Signer e parti cross-platform

La CI deve restare coerente con questa architettura: testare per layer e per dominio, non solo con un job generico.
Nel breve periodo il lint di CI deve essere severo sugli errori reali ma sostenibile sul debito esistente; per questo il gate attuale blocca errori sintattici e import/failure, mentre le regole di stile possono essere irrigidite in step successivi.
Accanto a quality, smoke e pytest esiste anche un controllo `Governance repo` che impedisce regressioni su budget moduli, presenza di route inline nel monolite e sottigliezza delle facciate compatibili.

## Direzione tecnica

Le priorità architetturali corrette sono:

1. continuare a ridurre il peso residuo di `web/app.py`
2. tenere i confini netti tra bootstrap, servizi e dominio
3. far crescere i repository strutturati usati da Lex
4. mantenere documentazione e CI allo stesso livello del codice
