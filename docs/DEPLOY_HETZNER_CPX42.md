# Deploy Hetzner CPX42

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
- `deploy/hetzner/docker-compose.hetzner.yml`: avvia `app`, `redis`, `scheduler-worker`, `ocr-worker`, `caddy` e profilo opzionale monitoring.
- `deploy/hetzner/Caddyfile`: termina HTTPS, imposta header di sicurezza e inoltra verso l'app Flask.
- `deploy/hetzner/env.hetzner.example`: template delle variabili ambiente di produzione.
- `deploy/hetzner/deploy.sh`: sincronizza il branch e ricrea i servizi.
- `deploy/hetzner/backup.sh`: crea archivio dati e checksum.
- `deploy/hetzner/restore_data.sh`: verifica checksum se presente, ferma i servizi e ripristina i dati.

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

Non salvare chiavi reali nel repository.

## Deploy

Prima di un deploy Hetzner che deriva da modifiche Codex, MetaHarness, autoresearch-lite o Open Design support, eseguire il gate di supporto dalla root locale della repository:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode dev-tooling
```

Il gate non sostituisce backup, test applicativi, Docker build o verifiche del nodo remoto.
Se la modifica e' solo documentale/tooling e non cambia il runtime, non eseguire il deploy Hetzner.

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/deploy.sh
```

Verifiche minime:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml ps
curl -fsS https://<dominio>/api/pronto
curl -I https://<dominio>/app-v2/fascicoli
```

## Backup

```bash
bash /opt/iusentra/repo/deploy/hetzner/backup.sh
```

Il comando crea un archivio di `/opt/iusentra/data` e il relativo file `.sha256` in `/opt/iusentra/backups`.

Cron consigliato:

```cron
15 2 * * * /opt/iusentra/repo/deploy/hetzner/backup.sh >/var/log/iusentra-backup.log 2>&1
```

## Restore

Caricare l'archivio su `/opt/iusentra/import`, poi:

```bash
bash /opt/iusentra/repo/deploy/hetzner/restore_data.sh /opt/iusentra/import/iusentra-data.tar.zst
bash /opt/iusentra/repo/deploy/hetzner/deploy.sh
```

Se esiste `/opt/iusentra/import/iusentra-data.tar.zst.sha256`, lo script verifica il checksum prima dell'estrazione.

## Note operative

- Local Signer resta sempre sul PC dell'avvocato, non sul server Hetzner.
- Artefatti PST, PDP, PAT, PTT e import portali devono restare sotto `/opt/iusentra/data`.
- Le credenziali PEC e i segreti devono restare cifrati o in variabili ambiente, mai in chiaro nel repository.
- Prima dello switch definitivo da Railway verificare route principali, worker OCR, scheduler, backup, restore e log Caddy.
