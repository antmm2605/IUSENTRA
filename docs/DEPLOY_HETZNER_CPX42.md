# Deploy Hetzner CPX42

> **Versione corrente:** 2.249.42 (fonte di verita: `pct/__init__.py` — la guida non viene piu' aggiornata ad ogni patch)
> Guida aggiornata: 17/05/2026

Questa guida rende esplicito il profilo `deploy/hetzner` come destinazione di produzione o fallback governato rispetto a Railway.

## Target

- Server Ubuntu su Hetzner CPX42.
- Root applicativa: `/opt/iusentra`.
- Dati persistenti: `/opt/iusentra/data`.
- Runtime: Docker Compose, Caddy HTTPS, Redis, worker scheduler e worker OCR.
- Backup: `/opt/iusentra/backups`, con checksum SHA-256.
- Restore: ripristino controllato dentro `/opt/iusentra/data`.

Railway puo' restare fase transitoria, ambiente di fallback o riferimento durante la migrazione, ma il profilo Hetzner non dipende da Railway per avviare app, worker, Redis o Caddy.

## File del profilo

- `deploy/hetzner/bootstrap_ubuntu.sh`: prepara Ubuntu con Docker, Compose plugin, firewall, OpenSC/pcscd, zstd e cartelle runtime.
- `deploy/hetzner/docker-compose.hetzner.yml`: avvia `app`, `redis`, `scheduler-worker`, `ocr-worker`, `caddy` (core sempre attivi) e profili opzionali `ai` (Ollama sidecar) e `monitoring` (Prometheus + Grafana).
- `deploy/hetzner/Caddyfile`: termina HTTPS, imposta header di sicurezza, gestisce SSE e WebSocket, inoltra verso l'app Flask. Il rate limiting sulle route di autenticazione è gestito da Flask-Limiter con Redis a livello applicativo.
- `deploy/hetzner/env.hetzner.example`: template delle variabili ambiente di produzione, incluse le variabili `COMPOSE_PROFILES` e `PCT_LOCAL_AI_ENABLED` per il controllo dell'AI locale.
- `deploy/hetzner/deploy.sh`: sincronizza il branch, legge `COMPOSE_PROFILES` da `.env.hetzner`, avvia i servizi con i profili corretti, scarica il modello Ollama solo se il sidecar è attivo, imposta il cron backup.
- `deploy/hetzner/backup.sh`: crea archivio dati e checksum.
- `deploy/hetzner/restore_data.sh`: verifica checksum se presente, ferma i servizi e ripristina i dati.

## Build multi-stage del Dockerfile (da v2.243.0)

L'immagine production e' costruita in 4 stage indipendenti:

| Stage | Base image | Output | Quando si ricompila |
|---|---|---|---|
| `builder` | python:3.12-slim | venv Python con dipendenze pip | se cambiano `setup.py`/`pyproject.toml`/`requirements/*` |
| `sass-builder` | debian:bookworm-slim | CSS in `/out/` | se cambiano file in `web/static/scss/` |
| `frontend-builder` | node:22-slim | bundle Vite in `/build/web/static/react/` | se cambiano `package.json`, `pnpm-lock.yaml`, `frontend/package.json`, `frontend/src/**` o `frontend/vite.config.ts` |
| runtime | python:3.12-slim | immagine finale | sempre |

Lo stage `frontend-builder` esegue `pnpm install --frozen-lockfile` + `pnpm --filter @iusentra/studio build:vite`. Il bundle generato sovrascrive `web/static/react/` nello stage runtime, garantendo che il JavaScript servito al browser sia sempre allineato ai sorgenti TSX del commit deployato. Prima di v2.243.0 il bundle era pre-compilato in locale e committato come fonte di verita': adesso il commit puo' contenere un bundle stale, il Dockerfile lo rigenera.

## Profili Docker Compose

| Profilo | Servizi aggiuntivi | Quando usarlo |
|---------|-------------------|---------------|
| *(nessuno)* | solo core: app, redis, scheduler-worker, ocr-worker, caddy | installazioni senza AI locale |
| `ai` | + sidecar `ollama` | self-hosted con AI locale (default consigliato su CPX42) |
| `monitoring` | + prometheus, grafana | dashboard metriche (porta 3000 solo localhost) |
| `ai,monitoring` | tutti | ambiente completo |

Impostare in `.env.hetzner`:

```bash
COMPOSE_PROFILES=ai
# oppure
COMPOSE_PROFILES=ai,monitoring
# oppure (senza AI)
COMPOSE_PROFILES=
PCT_LOCAL_AI_ENABLED=0
```

## Bootstrap

Sul server, come `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/antmm2605/IUSENTRA/Codex/legal-electronic-filing-kIxcV/deploy/hetzner/bootstrap_ubuntu.sh | bash
```

Poi compilare l'ambiente:

```bash
cp /opt/iusentra/repo/deploy/hetzner/env.hetzner.example /opt/iusentra/.env.hetzner
nano /opt/iusentra/.env.hetzner
```

Variabili minime da valorizzare:

- `IUSENTRA_DOMAIN`
- `ACME_EMAIL`
- `PCT_SECRET_KEY`
- `SECRET_KEY`
- `FERNET_PRIMARY_KEY`
- `AUDIT_HMAC_KEY`

Variabili PWA/Web Push opzionali:

- `IUSENTRA_WEB_PUSH_ENABLED=0`
- `IUSENTRA_VAPID_PUBLIC_KEY=`
- `IUSENTRA_VAPID_PRIVATE_KEY=`
- `IUSENTRA_VAPID_SUBJECT=mailto:admin@example.com`

Impostare `IUSENTRA_WEB_PUSH_ENABLED=1` solo dopo aver configurato chiavi VAPID reali in `/opt/iusentra/.env.hetzner`.

Non salvare chiavi reali nel repository.

Procedura Web Push sul server:

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/configure_web_push.sh
IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh
bash deploy/hetzner/verify_web_push.sh
```

Per questa procedura Web Push l'opt-out `IUSENTRA_SKIP_BACKUP_CRON=1` evita di aggiornare la pianificazione backup; ometterlo quando si vuole seguire la procedura standard completa.

Lo script di configurazione genera chiavi EC P-256 compatibili con `pywebpush`, aggiorna `/opt/iusentra/.env.hetzner`, imposta permessi `600` e non stampa la chiave privata nei log normali. Per rigenerare chiavi gia' presenti:

```bash
bash deploy/hetzner/configure_web_push.sh --force
```

Da utente autenticato, `https://<dominio>/api/push/public-key` deve restituire `ok: true`, `configured: true` e `publicKey` valorizzata. Se resta `configured: false`, leggere `diagnostics.missing` nella risposta o lanciare `bash deploy/hetzner/verify_web_push.sh`.

## Deploy

Prima di un deploy Hetzner che deriva da modifiche Codex, MetaHarness, autoresearch-lite o Open Design support, eseguire il gate di supporto dalla root locale della repository:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode dev-tooling
```

Il gate non sostituisce backup, test applicativi, Docker build o verifiche del nodo remoto.
Ogni aggiornamento completato e pushato deve arrivare anche su Hetzner CPX42: non considerare chiuso il lavoro finche' il server non punta al commit pushato e i controlli sotto non sono verdi, anche quando la modifica e' documentale o operativa.

Prima del deploy creare sempre un backup dei dati:

```bash
bash /opt/iusentra/repo/deploy/hetzner/backup.sh
```

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/deploy.sh
```

Verifiche minime:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml ps
git -C /opt/iusentra/repo rev-parse --short HEAD
curl -fsS https://<dominio>/api/pronto
curl -I https://<dominio>/app-v2/fascicoli
curl -I https://<dominio>/legal-intelligence/
curl -I https://<dominio>/legal-intelligence/ricerca
curl -I https://<dominio>/ricerca-legale
```

Il deploy stampa il commit deployed e l'URL health al termine. Il `git rev-parse` deve corrispondere all'HEAD del branch pushato.

Le ultime tre verifiche controllano il routing canonico di **Ricerca legale** (da v2.242.0): `/ricerca-legale` risponde `200` dalla shell React, mentre `/legal-intelligence/` e `/legal-intelligence/ricerca` rispondono `301` verso i corrispondenti path `/ricerca-legale/*`. Solo il download fonte (`/ricerca-legale/fonte/<id>/scarica`) e il diff giornaliero (`/ricerca-legale/daily/*`) restano serviti dal blueprint Flask.

## Backup

```bash
bash /opt/iusentra/repo/deploy/hetzner/backup.sh
```

Il comando crea un archivio di `/opt/iusentra/data` e il relativo file `.sha256` in `/opt/iusentra/backups`.

Cron consigliato:

```cron
15 2 * * * /opt/iusentra/repo/deploy/hetzner/backup.sh >/var/log/iusentra-backup.log 2>&1
```

Lo script applica anche la retention: conserva al massimo 3 backup applicativi, almeno 2 copie, rimuove quelli piu' vecchi di 14 giorni e mantiene la directory backup entro 8 GiB quando possibile. Il massimo di 3 copie e' un tetto rigido anche se l'ambiente imposta un valore piu' alto. In produzione i valori sono governati da `IUSENTRA_BACKUP_RETENTION_COUNT`, `IUSENTRA_BACKUP_RETENTION_MIN_COUNT`, `IUSENTRA_BACKUP_RETENTION_DAYS` e `IUSENTRA_BACKUP_RETENTION_MAX_GIB` in `/opt/iusentra/.env.hetzner`. La retention rimuove anche backup legacy/quarantene email non operative (`auth-before-migration-*`, `hetzner-pre-*`, `tenant-email-quarantine-*`).

I backup `.tar.zst` usano zstd ad alta compressione (`IUSENTRA_BACKUP_ZSTD_LEVEL=19`, `IUSENTRA_BACKUP_ZSTD_LONG_WINDOW=27` di default). Ollama, i modelli locali e i download rigenerabili sono esclusi in modo obbligatorio (`./ollama`, `./intelligence/downloads/ollama`, `./tenants/*/intelligence/downloads/ollama`): lo script verifica l'archivio e fallisce se trova ancora un percorso Ollama. Se durante la lettura cambiano file runtime vivi, `tar` puo' restituire un warning non fatale: da v2.243.3 lo script conserva lo snapshot best-effort e blocca solo errori gravi o compressione fallita. Se una singola copia supera il tetto configurato, lo script conserva comunque il numero minimo di copie e stampa un avviso esplicito invece di cancellare l'ultimo backup valido.

Dopo ogni deploy Hetzner il deploy elimina la cache build Docker rigenerabile e l'eventuale `/opt/iusentra/tmp-backup-snapshot` non operativo. In multi-studio la sincronizzazione PEC/email ordinaria deve fallire chiusa se non risolve un path tenant sotto `/data/tenants/<studio>/email`; `/data/email` non va popolato da scheduler o route operative.

Per compattare lo storage live senza cambiare i path applicativi:

```bash
python3 /opt/iusentra/repo/scripts/compact_iusentra_storage.py --data-root /opt/iusentra/data
python3 /opt/iusentra/repo/scripts/compact_iusentra_storage.py --data-root /opt/iusentra/data --apply
```

Il comando usa hardlink per deduplicare allegati email e mirror backup identici nello stesso filesystem; i riferimenti salvati nei JSON restano invariati.
Da v2.243.7 i nuovi allegati PEC/email possono essere salvati direttamente in `archivio-allegati.zip` con `IUSENTRA_EMAIL_ATTACHMENT_STORAGE=archive`; il lettore applicativo continua ad aprire anche i file sciolti storici, quindi download e anteprime non dipendono dal formato fisico.
Il pannello Superadmin `Server e manutenzione` mostra dimensioni hardlink-aware: i file gia' compattati restano percorsi distinti per l'applicazione, ma non vengono trattati come spazio ancora recuperabile. Il profilo Docker monta anche `/opt/iusentra/backups` nel container app, cosi' il pannello puo' misurare i backup esterni reali e applicare la retention governata solo sugli archivi `iusentra-data-*.tar.zst`/`.tar.gz`, preservando sempre le copie minime configurate.

## Restore

Caricare l'archivio su `/opt/iusentra/import`, poi:

```bash
bash /opt/iusentra/repo/deploy/hetzner/restore_data.sh /opt/iusentra/import/iusentra-data.tar.zst
bash /opt/iusentra/repo/deploy/hetzner/deploy.sh
```

Se esiste `/opt/iusentra/import/iusentra-data.tar.zst.sha256`, lo script verifica il checksum prima dell'estrazione.

## Note operative

- Local Signer resta sempre sul PC dell'avvocato, non sul server Hetzner.
- Local Deep Research resta opzionale e non viene avviato dal deploy standard. Se abilitato come overlay, montare i dati sotto `/opt/iusentra/data`, non esporre Ollama su Internet e proteggere l'accesso LDR con bind locale o proxy autenticato.
- Artefatti PST, PDP, PAT, PTT e import portali devono restare sotto `/opt/iusentra/data`.
- Le credenziali PEC e i segreti devono restare cifrati o in variabili ambiente, mai in chiaro nel repository.
- Prima dello switch definitivo da Railway verificare route principali, worker OCR, scheduler, backup, restore e log Caddy.

## Deploy automatico via GitHub Actions (da v2.241.0)

Il workflow `.github/workflows/deploy-hetzner.yml` esegue il deploy sul server Hetzner CPX42 ad ogni push sui due branch operativi ammessi, `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`, ed e' invocabile manualmente da GitHub > Actions > "Deploy Hetzner CPX42" > "Run workflow".

### Cosa fa il workflow

1. Verifica che i secrets SSH siano configurati e parsabili.
2. Apre una sessione SSH non interattiva verso `${HETZNER_USER}@${HETZNER_HOST}` con `known_hosts` pinnato (no MITM).
3. Esegue `bash /opt/iusentra/repo/deploy/hetzner/backup.sh` (saltabile via input booleano `skip_backup`).
4. Esegue `BRANCH=<branch pushato> bash deploy/hetzner/deploy.sh` sul server; nei run manuali senza override usa `Codex/legal-electronic-filing-kIxcV`.
5. Recupera `git rev-parse --short HEAD` remoto per verifica.
6. `docker compose ps` e curl pubblici su `/api/pronto`, `/legal-intelligence/`, `/legal-intelligence/ricerca`, `/ricerca-legale`.
7. Stampa un summary GitHub Actions con commit, host, esito.
8. Cancella la chiave SSH dal runner (`shred`).

`concurrency: deploy-hetzner-production` con `cancel-in-progress: false` garantisce che due push ravvicinati producano deploy in coda, mai paralleli. Se il secondo push dei branch gemelli trova gia' lo stesso commit su `/opt/iusentra/repo`, il workflow salta backup e rebuild, mantiene le verifiche post-deploy ed esegue comunque la pulizia rigenerabile con `docker builder prune --all --force` e rimozione di `/opt/iusentra/tmp-backup-snapshot`.

### Setup una tantum

**1. Generare una chiave SSH dedicata al deploy** (NON la chiave root master dell'amministratore):

```bash
# da una macchina locale sicura
ssh-keygen -t ed25519 -f iusentra-deploy-key -N "" -C "github-actions-deploy@iusentra"
```

Produce due file: `iusentra-deploy-key` (privata) e `iusentra-deploy-key.pub` (pubblica).

**2. Autorizzare la chiave pubblica sul server Hetzner**:

```bash
ssh root@116.203.45.57 'mkdir -p ~/.ssh && chmod 700 ~/.ssh'
scp iusentra-deploy-key.pub root@116.203.45.57:/tmp/
ssh root@116.203.45.57 '
  cat /tmp/iusentra-deploy-key.pub >> ~/.ssh/authorized_keys
  chmod 600 ~/.ssh/authorized_keys
  rm /tmp/iusentra-deploy-key.pub
  # restringi la chiave: solo da GitHub Actions IP range, comando limitato (opzionale ma consigliato)
  # Esempio nota: aggiungere prefisso command="..." se si vuole limitare i comandi eseguibili
'
```

**3. Generare il `known_hosts` pinnato del server**:

```bash
ssh-keyscan -H 116.203.45.57 > hetzner-known-hosts
# verifica visiva: l'output deve contenere righe ssh-ed25519 e/o ssh-rsa
cat hetzner-known-hosts
```

**4. Configurare i secrets GitHub** in `Settings → Secrets and variables → Actions → New repository secret`:

| Secret | Valore | Note |
|---|---|---|
| `HETZNER_SSH_PRIVATE_KEY` | Contenuto completo di `iusentra-deploy-key` (incluso `-----BEGIN OPENSSH PRIVATE KEY-----`) | Senza passphrase |
| `HETZNER_SSH_KNOWN_HOSTS` | Contenuto completo di `hetzner-known-hosts` | Pinning chiave host |

**5. Configurare le variabili GitHub** (opzionali, hanno default) in `Settings → Secrets and variables → Actions → Variables`:

| Variable | Default | Quando cambiarla |
|---|---|---|
| `HETZNER_HOST` | `116.203.45.57` | Se il server cambia IP |
| `HETZNER_USER` | `root` | Se viene creato un utente deploy dedicato |
| `HETZNER_DOMAIN` | *(non impostata)* | Impostare al dominio pubblico (es. `app.iusentra.it`) per abilitare le verifiche `curl` HTTPS post-deploy |

**6. Distruggere la copia locale della chiave privata**:

```bash
shred -u iusentra-deploy-key
rm iusentra-deploy-key.pub hetzner-known-hosts
```

La chiave privata vive ora solo nei GitHub Secrets, criptata a riposo.

### Test del setup

Da GitHub Actions, "Deploy Hetzner CPX42" → "Run workflow" con `skip_backup: true` per la prima prova (evita di sprecare uno slot backup mentre si testa SSH). Se i primi 3 step passano (verifica secrets, setup SSH, verifica raggiungibilita), tutto e' configurato.

Per un push operativo in cui l'utente chiede esplicitamente di non creare backup, inserire `[no-backup]` nel messaggio del commit: il workflow salta il backup preventivo e passa `IUSENTRA_SKIP_BACKUP_CRON=1` allo script di deploy, senza toccare volumi o dati applicativi.

### Rotazione chiavi

Ogni 12 mesi o dopo ogni cambio di personale con accesso ai repo, ripetere i passi 1-4 e rimuovere la vecchia chiave da `~/.ssh/authorized_keys` sul server.

### Rollback in caso di deploy fallito

Il workflow non esegue rollback automatico. Se le verifiche post-deploy falliscono:

```bash
ssh root@116.203.45.57
cd /opt/iusentra/repo
git log --oneline -5                              # individua il commit precedente
git checkout <commit_precedente>
bash deploy/hetzner/deploy.sh                     # riapplica la vecchia versione
```

Per ripristinare i dati da backup, vedere la sezione **Restore** sopra.

## Verifiche post-deploy Ricerca legale (aggiornate a v2.242.0+)

> Storia breve del routing, per leggere correttamente i changelog: in v2.240.0 le pagine erano servite dai template Flask e la shell React era esclusa; da v2.242.0 il rapporto e' invertito — la shell React e' la superficie principale sui path canonici `/ricerca-legale/*` e i vecchi `/legal-intelligence/*` rispondono `301`. Le verifiche sotto descrivono lo stato attuale.

Dopo ogni deploy controllare il routing canonico:

```bash
# home canonica — deve rispondere 200 dalla shell React
curl -fsS -o /dev/null -w '%{http_code}\n' -H "Cookie: session=<session_id>" https://<dominio>/ricerca-legale

# alias storico — deve rispondere 301 verso /ricerca-legale
curl -fsSI https://<dominio>/legal-intelligence/ | grep -i '^location' | grep -q '/ricerca-legale' && echo "redirect OK"
curl -fsSI https://<dominio>/legal-intelligence/ricerca | grep -i '^location' | grep -q '/ricerca-legale/ricerca' && echo "redirect ricerca OK"

# vista Flask legacy ancora raggiungibile esplicitamente (fallback governato)
curl -fsSL -H "Cookie: session=<session_id>" "https://<dominio>/ricerca-legale/?_legacy=1" | grep -q 'li-tabs' && echo "legacy Flask OK"

# ricerca unificata JSON (servita dal blueprint Flask: richiede Accept JSON per scavalcare il gate React)
curl -fsSL -H "Cookie: session=<session_id>" -H "Accept: application/json" \
  "https://<dominio>/ricerca-legale/ricerca?q=mediazione&formato=json" \
  | python3 -c "import sys, json; data = json.load(sys.stdin); print('ricerca OK', data['risultati']['totale'])"
```

Verifiche backend, da eseguire dentro il container app:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner \
  -f deploy/hetzner/docker-compose.hetzner.yml \
  exec app python -c "
from web.services.legal_intelligence_research import build_unified_search
from legal_intelligence.engine import LegalIntelligenceDailyEngine
import inspect
print('research service OK:', 'build_unified_search' in dir())
engine_methods = {name for name, _ in inspect.getmembers(LegalIntelligenceDailyEngine, predicate=inspect.isfunction)}
for required in ('get_source_card', 'latest_snapshot'):
    assert required in engine_methods, f'manca metodo {required}'
print('engine API OK')
"
```

Output atteso:

```
research service OK: True
engine API OK
```

Se le verifiche HTTP falliscono, controllare in ordine:

1. `web/bootstrap/react_route_gate.py` DEVE elencare `/ricerca-legale` e `/legal-intelligence` in `_REACT_PREFIXES` e i sotto-path in `_REACT_EXACT` (reintrodotti in v2.242.0); il hook `_legal_intelligence_canonical_redirect` deve essere registrato per i 301.
2. Il blueprint `legal_intelligence` deve risultare registrato due volte in `web/bootstrap/blueprint_registry.py`: con prefisso `/legal-intelligence` (alias storico) e con nome `ricerca_legale` su prefisso `/ricerca-legale` (canonico).
3. La directory `/opt/iusentra/data/legal_intelligence/` deve essere scrivibile dal container app per persistere gli snapshot del motore giornaliero.

Test interattivo del download archivio fonte (sostituire `<source_id>` con un id valido — es. `normattiva`, `pst_servizi_web`, `cassazione`):

```bash
curl -fsSL -H "Cookie: session=<session_id>" \
  https://<dominio>/ricerca-legale/fonte/<source_id>/scarica -o /tmp/fonte.txt
head -10 /tmp/fonte.txt
```

L'header deve contenere le righe `Fonte:`, `URL:`, `Hash SHA-256:`, `Scaricata il:`. Se torna un redirect alla scheda fonte con flash "snapshot non disponibile", eseguire prima un controllo dalla scheda **Fonti** (o `POST /ricerca-legale/daily/esegui`) per popolare il primo snapshot.

## Verifiche post-deploy Lex (da v2.201.0)

Dopo ogni deploy che tocca `lex/`, verificare che i nuovi moduli siano raggiungibili dall'app:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner \
  -f deploy/hetzner/docker-compose.hetzner.yml \
  exec app python -c "
from lex.research.case_law_reference_parser import parse_case_law_reference
from lex.guards.exact_legal_reference_guard import ExactLegalReferenceGuard
from lex.tools.studio_data_gateway import extract_entity_hint
from lex.research.query_helpers import is_exact_legal_reference_query
ref = parse_case_law_reference('Sentenza n. 7919 del 31/03/2026')
print('case_law_parser OK:', ref.is_exact_reference, ref.number)
print('query_helpers OK:', is_exact_legal_reference_query('sentenza n. 1/2024'))
print('studio_gateway OK:', extract_entity_hint('CF RSSMRA80A01H501Z'))
print('guard OK:', ExactLegalReferenceGuard().__class__.__name__)
"
```

Output atteso:
```
case_law_parser OK: True 7919
query_helpers OK: True
studio_gateway OK: {'codice_fiscale': 'RSSMRA80A01H501Z', ...}
guard OK: ExactLegalReferenceGuard
```

## Changelog deploy

| Versione | Commit | Data | Contenuto principale |
|----------|--------|------|----------------------|
| 2.244.0 | - | 17/05/2026 | Console superadmin `/admin/pianificazioni` con alias `/admin/cronjob`: cronjob visibili e modificabili, richieste manuali tracciate, registro persistente `scheduler_registry.sqlite`, esiti worker e agenti delegati governati per clienti/soggetti, agenda/scadenze, preventivi/parcelle, PEC, email ordinaria, fascicoli, aggiornamenti legali, backup/storage, depositi telematici, sito studio, pagamenti/notifiche e GDPR. |
| 2.243.9 | - | 17/05/2026 | `/admin/aggiornamenti-legali/fonti` e' ora un catalogo professionale con famiglie, stato per fonte, ciclo giornaliero, regole incrementali e conteggi reali. Aggiunte fonti ufficiali scelte per studi legali: INPS circolari/messaggi/sentenze, Curia CGUE, ISTAT prezzi, MIMIT incentivi, AGCM, AGCOM e Banca d'Italia; INAIL resta censita ma fuori dal ciclo automatico finche' il canale non e' stabile. |
| 2.243.8 | — | 17/05/2026 | Aggiornamenti legali e Ricerca Legale collegano gli archivi locali Normattiva/Gazzetta gia' popolati alla superficie admin e React; la ricerca usa prima archivi ufficiali locali e poi web esterno. Scheduler giornaliero alle 23:00 per archivi ufficiali e 23:10/23:15 per Update Intelligence; Normattiva scarica solo collezioni nuove/cambiate confrontando catalogo, manifest e stato locale. OpenGA esteso a Calendario Udienze, Decreti, Ordinanze, Pareri, Provvedimenti pubblicati, Ricorsi definiti/pendenti/pervenuti e Sentenze; aggiunti anche interpelli Ministero Lavoro, Garante Privacy, ANAC e PST Giustizia. La verifica web legge anche contesto pagina e allegati ufficiali collegati (PDF/XML/testo) con timeout e limiti di dimensione per elemento, cosi' il job notturno resta governato. |
| 2.243.7 | — | 16/05/2026 | Console Hetzner/storage: cache Docker build eliminata dopo deploy, snapshot temporanei rimossi, retention backup rigida massimo 3 copie, posta multi-studio fail-closed sui tenant, allegati PEC/email nuovi in archivio ZIP compatibile con anteprime/download e aggiornamenti legali massivi eseguiti come job per elemento con timeout. |
| 2.243.3 | — | 16/05/2026 | Backup preventivo Hetzner robusto sui dati runtime vivi: `backup.sh` considera non fatale `tar` exit 1 dovuto a file cambiati durante la lettura, produce comunque lo snapshot best-effort e continua a bloccare errori gravi (`tar > 1`) o fallimenti zstd/gzip. |
| 2.243.2 | — | 16/05/2026 | Dockerfile frontend reso ripetibile su server: lo stage Vite usa `npm ci --include=dev`, cosi' Tailwind/PostCSS sono disponibili anche con `NODE_ENV=production`; `.dockerignore` esclude `node_modules` per impedire drift fra build locale e build Hetzner. |
| 2.243.0 | — | 16/05/2026 | Dockerfile: aggiunto stage `frontend-builder` su `node:22-slim` che esegue `npm ci` + `npm run build:vite` durante il build dell'immagine. Lo stage runtime copia il bundle React appena ricompilato sopra `web/static/react/`, eliminando il drift tra sorgenti TSX e bundle JavaScript servito al browser. Lo stage e' indipendente (Node non finisce nell'immagine finale, solo gli artefatti). Layer cache su `package*.json` per ricompilazioni rapide quando cambiano solo i `.tsx`. |
| 2.242.2 | — | 16/05/2026 | Ricompilato e committato il bundle React in `web/static/react/`: il chunk `LegalIntelligencePage-*.js` include adesso `MediazioneImportPanel` con sync/import. Il Dockerfile non esegue il build Vite, quindi il bundle pre-compilato e' la fonte di verita' in produzione; finche' la build node non sara' aggiunta come stage Docker, ogni modifica a `frontend/src/**` richiede `npm --prefix frontend run build` + commit di `web/static/react/`. |
| 2.242.1 | — | 16/05/2026 | Ricerca legale React: aggiunto pannello "Carica tutti gli organismi" nella vista mediazione con due flussi paralleli — sincronizzazione registro ministeriale (`POST /ricerca-legale/mediazione/sync`) e import snapshot HTML (`POST /ricerca-legale/mediazione/import`). Componente `MediazioneImportPanel` renderizzato solo per `view === 'mediazione'`. Stili dedicati `.iu-li-mediazione-import*` con divider, layout responsive e azioni primary/neutral. Blueprint Flask `legal_intelligence` ora usa `url_for('.endpoint')` invece di `url_for('legal_intelligence.endpoint')` per rispettare il prefisso effettivo (`/legal-intelligence` o `/ricerca-legale`) della richiesta in corso, evitando doppi hop redirect dopo i POST. |
| 2.242.0 | — | 16/05/2026 | Ricerca legale: ripristino della shell React come UX principale, rename canonico delle rotte a `/ricerca-legale/*` (cruscotto, news, mediazione, ricerca), redirect 301 server-side da `/legal-intelligence/*` → `/ricerca-legale/*` via hook `_legal_intelligence_canonical_redirect`. Blueprint Flask `legal_intelligence` montato anche su `/ricerca-legale` per servire scheda fonte, download `.txt` e diff giornaliero (fallback legacy `?_legacy=1`). Nuovi endpoint API `/api/v1/ui/ricerca-legale[/news|/mediazione|/ricerca]`. Aggiornati `studioModuleData`, `legalIntelligenceData`, `LegalIntelligencePage.tsx`, bridge `react_giurisprudenza/redazione_atti/studio_module/legal_intelligence` per puntare ai nuovi path canonici. Registro mediazione: rimosso il limite hardcoded `filtered[:400]` (ora restituisce tutti gli organismi presenti nella cache). Parser HTML esteso: legge TUTTE le tabelle plausibili dell'HTML importato (non solo la migliore), preservando gli organismi distribuiti su sezioni multiple. |
| 2.241.1 | — | 16/05/2026 | Deploy automatico GitHub Actions esteso ai due branch ammessi (`Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`), con branch deployato derivato dal ref pushato e default manuale conservato su `Codex/legal-electronic-filing-kIxcV`. Il secondo push gemello salta backup e rebuild quando trova gia' lo stesso commit sul server, mantenendo le verifiche. Secrets e variables Actions configurati per `app.iusentra.it`, host `116.203.45.57` e utente `root`. Aggiunta nuova regola obbligatoria in `CLAUDE.md` ("Deploy Hetzner automatico"): dopo ogni push Claude deve verificare la run del workflow e considerare il task chiuso solo a esito verde, con fallback manuale documentato in caso GitHub Actions non sia raggiungibile. |
| 2.241.0 | — | 16/05/2026 | Deploy automatico via GitHub Actions: nuovo workflow `.github/workflows/deploy-hetzner.yml` triggerato dai push su `Codex/legal-electronic-filing-kIxcV` (e manuale via `workflow_dispatch`). SSH key dedicata in `HETZNER_SSH_PRIVATE_KEY`, host pinning via `HETZNER_SSH_KNOWN_HOSTS`, backup preventivo opt-out, verifiche post-deploy con curl su rotte Ricerca legale + Motori Legali, summary GitHub Actions con commit/host/esito, `concurrency` lock per evitare deploy paralleli, pulizia chiave SSH con `shred` a fine job. Documentazione setup secrets/variables/test/rotazione/rollback aggiunta. |
| 2.240.0 | `be5131e` | 16/05/2026 | Ricerca legale e Motori Legali: `/legal-intelligence/` riscritto come pagina tabbed (Panoramica · Fonti · Aggiornamenti · Normativa · Audit · Console). Nuovo endpoint `/legal-intelligence/ricerca` con search cross-source su fonti, normativa, news, organismi mediazione e aggiornamenti. `/ricerca-legale` ora punta alla ricerca unificata. Nuove rotte `/legal-intelligence/fonte/<id>` (scheda con storico snapshot, metadati e variazioni) e `/legal-intelligence/fonte/<id>/scarica` (download `.txt` del testo archiviato con header URL, SHA-256, ETag). Rimosse `/legal-intelligence` e `/ricerca-legale` dalla shell React legacy: ora servite direttamente dai template Flask. News page ripulita da blocchi superadmin duplicati. Nuovo service `web/services/legal_intelligence_research.py`, estensione `LegalIntelligenceDailyEngine.get_source_card/latest_snapshot` e `LegalIntelligenceStore.source_snapshots/source_updates`. SCSS `.li-tabs`, `.li-search-form`, `.li-news-stack`, `.li-quick-actions`, `.li-empty` con responsive mobile. |
| 2.215.0 | — | 10/05/2026 | PST acquisizione: PIN chiesto al massimo una volta per visualizzazione e una volta per download. TTL sessione portata a 1800 s. `awEnsurePstPreviewDocumentCatalog` riusa snapshot in memoria senza ri-autenticazione. |
| 2.202.0 | `a06145c` | 08/05/2026 | Lex: fix CASO 1 (sentenza esatta forza ricerca pubblica, confidence cap ≤ 0.45), fix CASO 2 (studio_data_lookup mostra dati cliente reali). `giurisprudenza_specifica` in `_STRICT_LEGAL_WORKFLOWS`. Handler deterministic `studio_data_lookup`. `user_facing_output_guard`. `case_law_completeness`. `exact_case_law_guard`. Prompt: no "Ciao sono Lex" su query operative. |
| 2.201.0 | `177ca37` | 08/05/2026 | Lex: distinzione fonti pubbliche vs dati studio. Parser sentenze esatte, ExactLegalReferenceGuard, StudioDataGateway, fix `_should_force_web_fallback`, fix `_clienti_lines` (4→8, CF/email), intent `cliente_anagrafica` → `studio_data_lookup`. |
| 2.200.0 | `77a4f40` | 08/05/2026 | Hetzner CPX42: fix Caddyfile rate_limit (→ Flask-Limiter), Ollama profilo opzionale `ai`, deploy.sh robusto con `COMPOSE_PROFILES`. Lex v2.200.0: debug payload 46 campi, fasi 1-16 router/guards/contracts. |
