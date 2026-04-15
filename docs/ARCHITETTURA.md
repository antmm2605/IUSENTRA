# Architettura HACS

## Obiettivo

HACS è un gestionale web per studi legali con specializzazioni verticali su:

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
- `template_atti.py`, `preventivi.py`, `applicazioni_catalogo.py`
  domini applicativi verticali
- `tenant.py`, `storage.py`, `database.py`
  strategia storage multi-tenant, manifest, provisioning e backend SQLite per studio

### `web/bootstrap/` — wiring Flask

Qui si registra ciò che viene estratto dal monolite di `web/app.py`:

- route modulari per auth, dashboard, telematico, privacy, calendario, checklist, soggetti
- registrazione blueprint
- runtime template condiviso
- handler errori

Questa cartella deve contenere moduli piccoli e leggibili, non nuovi monoliti.

### `web/services/` — servizi runtime/UI

Qui stanno i servizi trasversali che non appartengono a un singolo dominio:

- `auth_runtime.py`
  sessione, login, timeout, enforcement sicurezza accesso
- `security_runtime.py`
  secret bootstrap, cookie/session hardening, header browser, CSRF
- `runtime_settings.py`
  impostazioni runtime derivate da configurazione studio
- `local_ai_runtime.py`
  integrazione AI locale e disponibilità runtime
- servizi di contesto studio, runtime locale e compatibilitÃ  UI

### `lex/` — modulo assistente autonomo

Lex ora ha una casa applicativa dedicata:

- `blueprint.py`
  factory del blueprint Flask compatibile con gli endpoint storici
- `runtime_dependencies.py`
  wiring runtime del modulo: login Flask, runtime Ollama, export documento e contesto studio entrano in Lex da qui
- `formatting/document_export.py`, `guards/legal_reference_guard.py`, `memory/web_execution.py`
  proprietari del bridge operativo prima disperso in `web/services/assistente_*`
- `routes.py`
  superficie HTTP dell'assistente
- `service.py`
  casi d'uso applicativi
- `orchestrator.py`
  coordinamento tra contesto, retrieval, prompt, runtime e guard rail
- `context/`, `retrieval/`, `guards/`, `formatting/`, `providers/`, `memory/`, `telemetry/`, `prompts/`
  sottosistemi piccoli e separati, riusabili anche fuori dalla chat
- i moduli storici `web/services/assistente_*.py` restano solo facciate compatibili: follow-up, routing sociale, prompt, riepilogo giornaliero, export documentale, guardie legali e riconoscimento web execution vivono ora in `lex/`

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

Il file è ancora più grande di quanto vogliamo, ma il confine corretto ormai è chiaro: nuova logica in moduli dedicati, non nel file principale.

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
