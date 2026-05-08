# Deploy e Release IUSENTRA

## Obiettivo

Questa guida allinea codice, CI, Docker locale e produzione Railway/Hetzner in un flusso di release verificabile.

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

### Versione Python locale e CI

La CI applicativa GitHub Actions usa Python `3.12` in tutti i job principali
(`Lint + syntax`, smoke, `Pytest core`, `Coverage moduli critici`, E2E). Sulla
workstation Codex locale di sviluppo puo' essere presente un interprete piu'
recente, ad esempio Python `3.14`.

Quando un gate locale viene eseguito con Python diverso da quello CI, il report
deve dichiararlo esplicitamente. Il risultato locale resta utile come controllo
preventivo, ma il verdetto di rilascio va letto contro il workflow CI su Python
`3.12`; in caso di divergenza, rieseguire il controllo con interprete allineato
alla CI oppure attendere GitHub Actions prima di trarre conclusioni definitive.

### Pytest locale per fasi

Se `python -m pytest -q` locale diventa troppo lungo o opaco, usare il runner
a fasi:

```bash
python scripts/run_pytest_phases.py --list
python scripts/run_pytest_phases.py --core-list
python scripts/run_pytest_phases.py --suite-list
python scripts/run_pytest_phases.py --core-shard 6 --core-total-shards 10 --core-subshard 2 --core-total-subshards 16 --core-subdivide-items --timeout-minutes 5
python scripts/run_pytest_phases.py --suite signer --suite-shard 2 --suite-total-shards 4 --suite-subdivide-items --timeout-minutes 5
python scripts/run_pytest_phases.py --phase react-migration --timeout-minutes 20
python scripts/run_pytest_phases.py --phase 02-react-ui --item-batch-size 20 --timeout-minutes 5
python scripts/run_pytest_phases.py --phase full --timeout-minutes 30 --report artifacts/react-migration/pytest-phases-run.json
```

Il runner non rimuove test e non sostituisce il gate completo: per dichiarare
verde la suite backend devono passare tutte le fasi necessarie, inclusa
`09-misc`, oppure la CI equivalente su Python `3.12`. Il dettaglio operativo e'
in `docs/PYTEST_PHASES.md`.

In GitHub Actions il gate `Pytest core` e' diviso in 10 shard principali; le
fasi 5, 6, 7, 8 e 9 sono ulteriormente divise a livello di test item. Le fasi
5 e 9 hanno 6 parti, la fase 6 ha 16 parti, observability e OCR restano divisi
in 3 parti. Ogni sotto-fase ha timeout pytest di 5 minuti e il check aggregato
resta `Pytest core`, fallendo se anche una sola parte fallisce. Anche coverage
critica, Local Signer, overlay qualita', release readiness, E2E nightly e
frontend React hanno shard/aggregatori dedicati per mantenere il feedback sotto
il budget operativo senza rimuovere test.

## Codex Support Stack prima della release

Quando una modifica nasce da Codex, MetaHarness, autoresearch-lite o Open Design support, prima di entrare nel flusso di release applicativa eseguire il gate dedicato:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode dev-tooling
```

Per task UI/UX di supporto, usare invece:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode ui-support
```

Il gate controlla scope, dipendenze runtime, guardrail di `AGENTS.md` e risorse Open Design support.
Non sostituisce CI, test applicativi, Docker build o verifiche Railway/Hetzner quando il codice prodotto cambia.

Se la tranche modifica solo documentazione operativa o strumenti sotto `tools/`, senza runtime applicativo, non avviare deploy applicativo: committare e sincronizzare i branch secondo le regole di repository.

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

## Produzione Hetzner

Il profilo server dedicato vive in [deploy/hetzner](../deploy/hetzner/README.md) e la guida operativa completa e' in [DEPLOY_HETZNER_CPX42.md](DEPLOY_HETZNER_CPX42.md). Copre il nodo CPX42 Ubuntu `116.203.45.57`.

Componenti:

- Docker Compose con `app`, `redis`, `scheduler-worker`, `ocr-worker` e `caddy`.
- HTTPS automatico tramite Caddy, con cache controllata per `/app-v2`.
- dati persistenti in `/opt/iusentra/data`;
- backup e restore governati da `deploy/hetzner/backup.sh` e `deploy/hetzner/restore_data.sh`.

Controlli minimi dopo deploy Hetzner:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml ps
curl -fsS https://<dominio>/api/pronto
curl -I https://<dominio>/app-v2/agenda/nuovo
```

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
- installazione automatica di `core.hooksPath=.githooks`
- registrazione del repository come `safe.directory` per evitare il blocco Git `dubious ownership`
- cache Python locali
- `.pytest_cache`, `.ruff_cache`, `tmp/`
- artefatti runtime locali transitori come `intelligence/downloads/` e `data/portale/import_log.json` (oppure `/data/portale/import_log.json` nel container)

Dopo il primo bootstrap, gli hook versionati in `.githooks/` mantengono allineati anche i due branch locali ammessi dopo `commit`, `checkout`, `merge` e `rewrite`, mentre il workflow `.github/workflows/sync-claude-to-codex.yml` specchia automaticamente il push verso il branch gemello remoto.

## Artefatti che non devono tornare in repo

- copie tipo `* - Copia.*`
- `pct.zip`
- `__pycache__/`
- `.pyc`
- database runtime e indici locali
- log e dump temporanei del Local Signer
- asset ministeriali lasciati in root invece che sotto `docs/specs/ministero/`
