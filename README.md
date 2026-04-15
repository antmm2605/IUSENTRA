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
  Servizi runtime, autenticazione, sicurezza, contesto UI, AI locale.
- `web/blueprints/`
  Blueprint verticali per moduli autonomi.
- `web/templates/` e `web/static/`
  UI Jinja2, Bootstrap 5, SCSS compilato.
- `tests/`
  Test di dominio, smoke test Flask, flussi telematici, signer e sicurezza.

Per una mappa più completa vedi [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md).

## Avvio locale

### Docker consigliato

```bash
cp .env.example .env
docker compose build --no-cache
docker compose up -d
```

Accessi:

- [http://localhost](http://localhost)
- [http://localhost:8080](http://localhost:8080)

Bootstrap locale:

- primo accesso con `admin / admin`
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
- Sessioni Flask con cookie `HttpOnly`, `SameSite=Lax`, refresh controllato e timeout.
- Header browser di hardening (`X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, HSTS quando HTTPS è attivo).
- Protezione CSRF sui flussi sensibili di autenticazione e gestione utenti.
- Password bootstrap e password temporanee con cambio obbligatorio prima dell’uso normale del gestionale.

## CI GitHub

La CI non si limita più alla sola sincronizzazione branch. La pipeline applicativa esegue:

- lint statico di base
- import/syntax check
- smoke test Flask
- suite `pytest` core su Linux
- job matrix Linux / Windows / macOS per Local Signer e componenti correlati

I workflow vivono in `.github/workflows/`.

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

- [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md) — struttura moduli, flussi e confini applicativi.
- [AGENTS.md](AGENTS.md) — regole operative del repository, release, sicurezza e PCT.

## Stato del progetto

Il codice oggi è più maturo di una semplice demo:

- routing web già in fase avanzata di modularizzazione
- repository strutturati per Lex su giurisprudenza, intelligence, telematico, template, preventivi e applicazioni
- test coverage distribuita su molti domini reali
- bootstrap di sicurezza più severo per uso professionale

Il prossimo passo naturale resta continuare a ridurre il monolite residuo di `web/app.py` e mantenere tutta la documentazione allo stesso livello del codice.
