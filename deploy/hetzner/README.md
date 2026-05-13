# Deploy Hetzner CPX42

Questa cartella contiene il profilo di produzione per spostare IUSENTRA su un server Hetzner Ubuntu, mantenendo Railway come sorgente dati solo durante la migrazione.

Guida di release collegata: `docs/DEPLOY_HETZNER_CPX42.md`.

Target validato per il server indicato:

- server: `ubuntu-16gb-nbg1-1`
- IP: `116.203.45.57`
- taglio: CPX42, 8 vCPU, 16 GB RAM, 320 GB disco locale
- runtime: Docker Compose, Caddy HTTPS, Redis, worker scheduler, worker OCR, sidecar Ollama per Lex
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
- `PCT_DOC_KEY` se i documenti cifrati sono attivi

Variabili opzionali per PWA/Web Push:

- `IUSENTRA_WEB_PUSH_ENABLED=0` o `1`
- `IUSENTRA_VAPID_PUBLIC_KEY`
- `IUSENTRA_VAPID_PRIVATE_KEY`
- `IUSENTRA_VAPID_SUBJECT=mailto:admin@example.com`

Lasciare il canale disattivo finche' le chiavi VAPID reali non sono state generate e inserite solo nell'ambiente del server.

Configurazione guidata sul server:

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/configure_web_push.sh
IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh
bash deploy/hetzner/verify_web_push.sh
```

`IUSENTRA_SKIP_BACKUP_CRON=1` evita di aggiornare il cron backup durante questa configurazione operativa. Ometterlo per il deploy standard.

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

Backup preventivo:

```bash
bash /opt/iusentra/repo/deploy/hetzner/backup.sh
```

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/deploy.sh
```

Verifiche:

```bash
docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml ps
git rev-parse --short HEAD
curl -fsS https://iusentra.tuodominio.it/api/pronto
curl -I https://iusentra.tuodominio.it/app-v2/agenda/nuovo
```

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

Backup manuale:

```bash
bash /opt/iusentra/repo/deploy/hetzner/backup.sh
```

Cron consigliato:

```cron
15 2 * * * /opt/iusentra/repo/deploy/hetzner/backup.sh >/var/log/iusentra-backup.log 2>&1
```

Il backup produce archivio e checksum in `/opt/iusentra/backups` e verifica subito il checksum generato. Il restore verifica il file `.sha256` quando presente prima di estrarre in `/opt/iusentra/data`.
La retention e' applicata dallo script: per default conserva al massimo 3 backup applicativi, almeno 2 copie, rimuove quelli piu' vecchi di 14 giorni e mantiene la directory backup entro 8 GiB quando possibile. I valori sono configurabili con `IUSENTRA_BACKUP_RETENTION_COUNT`, `IUSENTRA_BACKUP_RETENTION_MIN_COUNT`, `IUSENTRA_BACKUP_RETENTION_DAYS` e `IUSENTRA_BACKUP_RETENTION_MAX_GIB`.
I backup `.tar.zst` sono prodotti con zstd ad alta compressione (`IUSENTRA_BACKUP_ZSTD_LEVEL=19`, long window 27) per ridurre l'impatto disco senza cambiare il formato di restore. Ollama, i modelli locali e i download rigenerabili sono esclusi in modo obbligatorio (`./ollama`, `./intelligence/downloads/ollama`, `./tenants/*/intelligence/downloads/ollama`): lo script verifica l'archivio e fallisce se trova ancora un percorso Ollama.

## Note operative

- Il server CPX42 e' adeguato per app, Redis, OCR, scheduler e monitoring leggero.
- Lex/Ollama puo' girare sullo stesso host solo per modelli piccoli CPU; per carichi AI pesanti serve nodo dedicato o runtime locale dello studio.
- Il profilo Hetzner avvia il servizio Docker `ollama` e `deploy.sh` verifica/scarica `PCT_LOCAL_AI_CHAT_MODEL` (default `gemma3:1b`), cosi' il widget Lex usa una sola pipeline backend senza dipendere dal companion browser per la risposta finale.
- Local Deep Research non e' attivo nel deploy standard. Se lo studio decide di abilitarlo, usare `docker-compose.ldr.yml` come overlay solo con `IUSENTRA_DATA_DIR=/opt/iusentra/data`, bind LDR su `127.0.0.1` o dietro proxy autenticato, e mantenere fascicoli/dati cliente nel retrieval tenant-aware di Lex.
- Il Local Signer resta sul PC dell'avvocato e dialoga con `127.0.0.1`; non va spostato nel cloud.
- Gli artefatti PST/PDP/PAT runtime restano sotto `/opt/iusentra/data`, mai nel path del repository.
