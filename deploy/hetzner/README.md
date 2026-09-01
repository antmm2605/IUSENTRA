# Deploy Hetzner CPX42

Questa cartella contiene il profilo di produzione per spostare IUSENTRA su un server Hetzner Ubuntu, mantenendo Railway come sorgente dati solo durante la migrazione.

Guida di release collegata: `docs/DEPLOY_HETZNER_CPX42.md`.

Target validato per il server indicato:

- server: `ubuntu-16gb-nbg1-1`
- IP: `116.203.45.57`
- taglio: CPX42, 8 vCPU, 16 GB RAM, 320 GB disco locale
- runtime: Docker Compose, Caddy HTTPS, Redis, worker scheduler e worker OCR; sidecar Ollama solo con profilo `ai` esplicito
- persistenza: `/opt/iusentra/data`

## Prerequisiti DNS

Prima di avviare HTTPS automatico, puntare il dominio scelto al server:

```text
A    iusentra.tuodominio.it    116.203.45.57
AAAA iusentra.tuodominio.it    2a01:4f8:1c18:e49f::1
```

Usare il record `AAAA` solo se IPv6 e firewall sono configurati correttamente sul server.

## Bootstrap server

Sul server, come `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/antmm2605/IUSENTRA/Codex/legal-electronic-filing-kIxcV/deploy/hetzner/bootstrap_ubuntu.sh | bash
```

Oppure copiare lo script e lanciarlo localmente:

```bash
bash deploy/hetzner/bootstrap_ubuntu.sh
```

Lo script installa Docker, Compose plugin, Git, UFW, OpenSC/pcscd, `zstd`, `unzip` e apre solo SSH, 80 e 443.

## Ambiente

Creare `/opt/iusentra/.env.hetzner` partendo da `env.hetzner.example`:

```bash
cp /opt/iusentra/repo/deploy/hetzner/env.hetzner.example /opt/iusentra/.env.hetzner
nano /opt/iusentra/.env.hetzner
```

Valori obbligatori per il deploy:

- `IUSENTRA_DOMAIN`
- `ACME_EMAIL`
- `PCT_SECRET_KEY`
- `SECRET_KEY`
- `FERNET_PRIMARY_KEY`
- `AUDIT_HMAC_KEY`
- `AUDIT_DATABASE_URL` per l'indice query/cache Postgres dell'audit probatorio
- `AUDIT_WORM_*` verso bucket S3-compatible con versioning e Object Lock
- `AUDIT_SIGNING_*` e, in modalita CAdES, `AUDIT_CADES_LOCAL_SIGNER_URL` / `AUDIT_CADES_VERIFY_URL`
- `AUDIT_TSA_URL` se `AUDIT_REQUIRE_TSA_FOR_SNAPSHOT=true`
- `PCT_DOC_KEY` se i documenti cifrati sono attivi

Se non e' ancora disponibile un provider WORM esterno, configurare il presidio
probatorio self-hosted S3-compatible con Object Lock prima del deploy:

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/configure_audit_worm.sh
```

Lo script abilita il profilo `audit-worm`, genera credenziali WORM, Postgres
audit dedicato e chiave JWS in `/opt/iusentra/data/audit/keys` fuori dal
repository. Il deploy avvia poi `audit-worm`, `audit-worm-init` e
`audit-postgres` prima dell'app.

Variabili opzionali per PWA/Web Push:

- `IUSENTRA_WEB_PUSH_ENABLED=0` o `1`
- `IUSENTRA_VAPID_PUBLIC_KEY`
- `IUSENTRA_VAPID_PRIVATE_KEY`
- `IUSENTRA_VAPID_SUBJECT=mailto:admin@example.com`

Lasciare il canale disattivo finche' le chiavi VAPID reali non sono state generate e inserite solo nell'ambiente del server.

Default performance da mantenere su CPX42:

```bash
COMPOSE_PROFILES=
PCT_LOCAL_AI_ENABLED=0
IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED=0
IUSENTRA_MAILBOX_SYNC_AUTOMATIC_LIMIT=25
IUSENTRA_PEC_DOCUMENT_PRESIDIO_LIMIT=0
IUSENTRA_DEPOSIT_POLL_DAYS=3
IUSENTRA_PEC_CANCELLERIA_POLL_DAYS=2
```

Con questi valori i job frequenti controllano solo il nuovo o le code pendenti. Eventuali recuperi storici devono essere avviati come manutenzione esplicita, non lasciati allo scheduler automatico.

Configurazione guidata sul server:

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/configure_web_push.sh
IUSENTRA_SKIP_BACKUP_CRON=1 IUSENTRA_DISABLE_BACKUP_JOBS=1 bash deploy/hetzner/deploy.sh
bash deploy/hetzner/verify_web_push.sh
```

`IUSENTRA_SKIP_BACKUP_CRON=1` e `IUSENTRA_DISABLE_BACKUP_JOBS=1` mantengono
disattivati il cron e gli archivi completi automatici. Non disattivano il backup
SQLite preventivo del workflow di deploy, che viene creato a ogni aggiornamento
effettivo salvo richiesta manuale esplicita.
Lo script genera chiavi VAPID EC P-256 se mancanti, abilita il canale, aggiorna `/opt/iusentra/.env.hetzner` con permessi `600` e non stampa la chiave privata nei log normali. Usare `--force` solo quando si vuole rigenerare la coppia di chiavi.

Generazione chiavi:

```bash
python3 - <<'PY'
import secrets
for name in ("PCT_SECRET_KEY", "PCT_DOC_KEY", "SECRET_KEY", "AUDIT_HMAC_KEY"):
    print(f"{name}={secrets.token_hex(32)}")
PY
```

Per `FERNET_PRIMARY_KEY` usare il generatore applicativo:

```bash
docker run --rm iusentra-app python -c "from core.security.secrets_manager import SecretsManager; print(SecretsManager.generate_key())"
```

## Deploy

Regola operativa obbligatoria: dopo ogni aggiornamento completato, committato e pushato sui branch gemelli, eseguire sempre il deploy su Hetzner CPX42. Il lavoro non e' concluso finche' `/opt/iusentra/repo` non punta al commit pushato, i container non sono healthy e `/api/pronto` non risponde.

**Da v2.241.1 il deploy parte automaticamente** da GitHub Actions quando viene pushato uno dei due branch ammessi, `Codex/legal-electronic-filing-kIxcV` o `claude/legal-electronic-filing-kIxcV`. Workflow: `.github/workflows/deploy-hetzner.yml`. Per setup secrets, rotazione chiavi e rollback vedere `docs/DEPLOY_HETZNER_CPX42.md` sezione "Deploy automatico via GitHub Actions".

Il comando manuale sotto resta valido per esecuzioni fuori banda. Prima del deploy crea una copia SQLite coerente di tutti i tenant; il workflow GitHub esegue automaticamente gli stessi controlli.

```bash
cd /opt/iusentra/repo
python3 deploy/hetzner/backup_structured.py \
  --source-root /opt/iusentra/data/tenants \
  --backup-dir /opt/iusentra/backups \
  --retention-count 1 \
  --min-free-gib 2 \
  --prune-legacy-single-db
bash deploy/hetzner/deploy.sh
```
Verifiche:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml ps
git rev-parse --short HEAD
curl -fsS https://iusentra.tuodominio.it/api/pronto
curl -I https://iusentra.tuodominio.it/app-v2/agenda/nuovo
curl -I https://iusentra.tuodominio.it/legal-intelligence/
curl -I https://iusentra.tuodominio.it/legal-intelligence/ricerca
curl -I https://iusentra.tuodominio.it/ricerca-legale
```

Pulizia obbligatoria dopo build/deploy:

```bash
docker builder prune --all --force
```

La cache di build Docker e' rigenerabile e non contiene dati degli studi. Dopo ogni deploy Hetzner va eliminata per evitare che il disco del server venga saturato da layer di compilazione non piu' necessari. Non usare comandi che rimuovono volumi o dati applicativi.

Le ultime tre `curl` verificano il routing canonico di Ricerca legale (da v2.242.0): `/ricerca-legale` e i suoi sotto-path sono serviti dalla shell React come superficie principale, mentre `/legal-intelligence/` e `/legal-intelligence/ricerca` devono rispondere `301` verso i corrispondenti path `/ricerca-legale/*`. Restano serviti dal blueprint Flask solo il download `/ricerca-legale/fonte/<id>/scarica` e il diff `/ricerca-legale/daily/*`.

## Migrazione dati da Railway

Opzione preferita:

1. generare un backup applicativo o un archivio del volume `/data` su Railway;
2. scaricare il file in locale;
3. caricarlo sul server:

```bash
scp iusentra-data.tar.zst root@116.203.45.57:/opt/iusentra/import/
```

4. ripristinare:

```bash
bash /opt/iusentra/repo/deploy/hetzner/restore_data.sh /opt/iusentra/import/iusentra-data.tar.zst
bash /opt/iusentra/repo/deploy/hetzner/deploy.sh
```

## Backup server

### Copia preventiva del deploy

```bash
python3 /opt/iusentra/repo/deploy/hetzner/backup_structured.py \
  --source-root /opt/iusentra/data/tenants \
  --backup-dir /opt/iusentra/backups \
  --retention-count 1 \
  --min-free-gib 2 \
  --prune-legacy-single-db
```

La copia usa l'API SQLite, valida ogni database tenant con quick_check, salva SHA-256 e manifest e conserva una sola istantanea. La copia precedente viene rimossa soltanto dopo il successo completo della nuova. Il workflow la esegue sui push ordinari; può saltarla esclusivamente con l'input manuale skip_backup=true o il marcatore [no-backup].

La copia preventiva protegge i dati strutturati studio.db; non è un backup completo di documenti, allegati, posta, indici verticali o altri dati sotto /opt/iusentra/data.

### Archivio completo

```bash
bash /opt/iusentra/repo/deploy/hetzner/backup.sh
```

Il backup completo produce archivio e checksum in /opt/iusentra/backups e verifica il checksum generato. Va eseguito solo quando la destinazione dispone di spazio sufficiente; il controllo fail-closed non consente di saturare il nodo. Per il corpus completo è raccomandato uno storage separato dimensionato rispetto a /opt/iusentra/data.

I backup .tar.zst usano zstd a budget server e partono con nice/ionice prudenti. Ollama, modelli locali e download rigenerabili sono esclusi. Host e container applicativi usano Europe/Rome.

Dopo ogni deploy Hetzner il deploy esegue `docker builder prune --all --force` e rimuove `/opt/iusentra/tmp-backup-snapshot` se presente. La posta multi-studio non deve essere sincronizzata in `/data/email`: scheduler e route devono usare solo `/data/tenants/<studio>/email`.

La retention dell'archivio completo resta governata da `IUSENTRA_BACKUP_RETENTION_COUNT`, `IUSENTRA_BACKUP_RETENTION_MIN_COUNT`, `IUSENTRA_BACKUP_RETENTION_DAYS` e `IUSENTRA_BACKUP_RETENTION_MAX_GIB`. Gli allegati PEC/email nuovi possono usare `IUSENTRA_EMAIL_ATTACHMENT_STORAGE=archive`; il lettore resta compatibile con i file storici sciolti.

## Ricerca legale e archivio fonti (v2.240.0)

Da v2.240.0 il motore giornaliero `LegalIntelligenceDailyEngine` salva ogni snapshot acquisito nel database SQLite `/opt/iusentra/data/legal_intelligence/daily.sqlite` (tabella `legal_source_snapshots`, campo `normalized_text`). Da quello stesso archivio la UI offre il pulsante "Scarica testo archiviato" su ogni scheda fonte (`/legal-intelligence/fonte/<id>/scarica`).

Per popolare l'archivio dopo il primo deploy:

```bash
# trigger manuale del controllo giornaliero (autenticato)
curl -fsS -X POST -H "Cookie: session=<session_id>" \
  https://iusentra.tuodominio.it/legal-intelligence/daily/esegui -o /dev/null -w "%{http_code}\n"
```

In alternativa il cron applicativo dello scheduler esegue lo stesso controllo alle 04:30. Lo studio puo' anche cliccare `Esegui controllo ora` dalla tab Fonti del nuovo `Motori Legali`.

Per verificare la persistenza:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner \
  -f deploy/hetzner/docker-compose.hetzner.yml \
  exec app sqlite3 /data/legal_intelligence/daily.sqlite \
  "SELECT source_id, fetched_at, length(normalized_text) FROM legal_source_snapshots ORDER BY id DESC LIMIT 5"
```

Il backup completo (`backup.sh`) include `/opt/iusentra/data/legal_intelligence/` come parte di `/opt/iusentra/data`; il backup preventivo strutturato del deploy copre invece soltanto i database `studio.db` dei tenant.

## Note operative

- Il server CPX42 e' adeguato per app, Redis, OCR, scheduler e monitoring leggero.
- Lex/Ollama puo' girare sullo stesso host solo per modelli piccoli CPU; per carichi AI pesanti serve nodo dedicato o runtime locale dello studio.
- Il profilo Hetzner avvia il servizio Docker `ollama` e `deploy.sh` verifica/scarica `PCT_LOCAL_AI_CHAT_MODEL` (default `gemma3:1b`), cosi' il widget Lex usa una sola pipeline backend senza dipendere dal companion browser per la risposta finale. La manutenzione AI automatica dello scheduler resta disattivata salvo opt-in esplicito con `IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED=1`, per evitare che il server carichi Ollama in background durante l'uso dell'app.
- Local Deep Research non e' attivo nel deploy standard. Se lo studio decide di abilitarlo, usare `docker-compose.ldr.yml` come overlay solo con `IUSENTRA_DATA_DIR=/opt/iusentra/data`, bind LDR su `127.0.0.1` o dietro proxy autenticato, e mantenere fascicoli/dati cliente nel retrieval tenant-aware di Lex.
- Il Local Signer resta sul PC dell'avvocato e dialoga con `127.0.0.1`; non va spostato nel cloud.
- Gli artefatti PST/PDP/PAT runtime restano sotto `/opt/iusentra/data`, mai nel path del repository.
