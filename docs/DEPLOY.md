# Deploy e Release IUSENTRA

## Obiettivo

Questa guida allinea codice, CI, Docker locale e produzione Railway in un flusso di release verificabile.

## Versioning obbligatorio

Ogni modifica al codice richiede bump coerente in:

- `pct/__init__.py`
- `setup.py`
- `Dockerfile`
- `railway.toml`

## Pipeline CI

Il workflow applicativo e' `.github/workflows/ci.yml` e include:

- `Lint + syntax`
- `Governance repo`
- `Smoke test Flask`
- `Smoke scheduler worker`
- test core su storage SQLite, osservabilita' runtime e worker OCR persistente
- `Pytest core`
- `Local Signer e PKCS#11` su Linux, Windows e macOS

Workflow complementari di sicurezza:

- `.github/workflows/codeql.yml`
- `.github/workflows/dependency-review.yml`
- `.github/workflows/security-supply-chain.yml`

Vista live del workflow applicativo:

- [Actions / CI](https://github.com/antmm2605/IUSENTRA/actions/workflows/ci.yml)

Il lint resta bloccante solo sugli errori reali di sintassi e import.
Il benchmark notturno gira in `.github/workflows/performance-nightly.yml` e usa `tools/performance_smoke.py`.

## Verifica release locale

Dopo ogni bump versione:

```bash
docker compose build --no-cache
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=20 app
docker compose logs --tail=20 scheduler-worker
docker compose logs --tail=20 ocr-worker
docker compose exec -T app python -c "import pct; print(pct.__version__)"
```

Controlli minimi:

- container `app` in stato `healthy`
- worker `scheduler-worker` avviato senza errori di bootstrap
- worker `ocr-worker` avviato e collegato alla coda persistente OCR
- `/login` risponde `200`
- versione runtime uguale alla versione nei file di release

## Scheduler separato dal web

Il processo web non deve avviare i job periodici dentro `create_app()`.

- web: `wsgi:app`
- worker schedulato: `python -m pct.scheduler_worker`

In produzione la configurazione corretta e' avere un servizio dedicato scheduler che riusa la stessa codebase o immagine, ma con comando di avvio `python -m pct.scheduler_worker`.

## OCR worker separato dal web

La pipeline documentale pesante non deve vivere nel processo HTTP:

- web: upload, enqueue del job e consultazione stato
- worker OCR: `python -m pct.ocr_worker`

Verifiche minime dopo release che toccano OCR o indicizzazione:

- presenza di `PCT_OCR_QUEUE_DB`
- presenza del file `ocr_jobs.db` nel volume `data/search`
- stato della pagina `/admin/osservabilita`
- job OCR completabili senza bloccare le richieste web

## Produzione Railway

Quando il fix tocca deploy, storage, AI locale, Local Signer bridge, SMTP o portali:

- verifica il branch remoto davvero usato da Railway
- controlla log applicativi e volume `/data`
- verifica la route reale online coinvolta
- conferma la versione effettiva del servizio remoto

## Storage strategy e rollout ambienti

Per ambienti seri la strategia storage va decisa dal `SUPERADMIN` a livello studio, non con flag globali opachi.

- `JSON`
  adatto a studio leggero, snapshot e aree non ancora migrate
- `SQLite`
  scelta raccomandata per single-tenant locale e installazioni on-prem governabili
- `PostgreSQL`
  scelta target per cloud e multi-tenant distribuito, con configurazione e test connessione dal pannello studio

Prima di chiudere una release che tocca storage:

- verifica la strategia selezionata sullo studio
- controlla il manifest `data/tenants/<slug>/config/storage.json`
- se il tenant e' `SQLite`, verifica la presenza di `data/tenants/<slug>/studio.db`
- se il tenant e' `PostgreSQL`, verifica almeno il test connessione e la chiarezza tra strategia selezionata e backend effettivo
- aggiorna la matrice in [docs/STORAGE_MATRIX.md](docs/STORAGE_MATRIX.md) se cambia la maturita' di un modulo
- se il flusso operativo cambia, esegui anche `iusentra demo-check --tenant=<slug-tenant>` oppure il relativo test automatico

## Repo hygiene

Prima di chiudere la release esegui:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/repo_hygiene.ps1
```

Lo script riallinea:

- worktree
- branch ammessi
- branch remoti sincronizzati
- cache Python locali
- `.pytest_cache`, `.ruff_cache`, `tmp/`
- artefatti runtime locali transitori come `intelligence/downloads/` e `portale/import_log.json`

## Artefatti che non devono tornare in repo

- copie tipo `* - Copia.*`
- `pct.zip`
- `__pycache__/`
- `.pyc`
- database runtime e indici locali
- log e dump temporanei del Local Signer
- asset ministeriali lasciati in root invece che sotto `docs/specs/ministero/`
