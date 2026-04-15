# Deploy e Release HACS

## Obiettivo

Questa guida allinea codice, CI, Docker locale e produzione Railway in un flusso di release verificabile.

## Versioning obbligatorio

Ogni modifica al codice richiede bump coerente in:

- `pct/__init__.py`
- `setup.py`
- `Dockerfile`
- `railway.toml`

## Pipeline CI

Il workflow applicativo è `.github/workflows/ci.yml` e include:

- `Lint + syntax`
- `Governance repo`
- `Smoke test Flask`
- `Smoke scheduler worker`
- `Pytest core`
- `Local Signer e PKCS#11` su Linux/Windows/macOS

Vista live del workflow:

- [Actions / CI](https://github.com/antmm2605/hacs/actions/workflows/ci.yml)

Il lint resta bloccante solo sugli errori reali di sintassi/import.

## Verifica release locale

Dopo ogni bump versione:

```bash
docker compose build --no-cache
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=20 app
docker compose logs --tail=20 scheduler-worker
docker compose exec -T app python -c "import pct; print(pct.__version__)"
```

Controlli minimi:

- container `app` in stato `healthy`
- worker `scheduler-worker` avviato senza errori di bootstrap
- `/login` risponde `200`
- versione runtime uguale alla versione nei file di release

## Scheduler separato dal web

Il processo web non deve più avviare i job periodici dentro `create_app()`.

- web: `wsgi:app`
- worker schedulato: `python -m pct.scheduler_worker`

In Railway/produzione la configurazione corretta è avere un servizio dedicato scheduler che riusa la stessa codebase o immagine ma con comando di avvio `python -m pct.scheduler_worker`.

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
- se il tenant è `SQLite`, verifica la presenza di `data/tenants/<slug>/studio.db`
- se il tenant è `PostgreSQL`, verifica almeno il test connessione e la chiarezza tra strategia selezionata e backend effettivo

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
- log/import cache generati dal runtime
