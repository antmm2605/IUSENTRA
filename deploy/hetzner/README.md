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

## Note operative

- Il server CPX42 e' adeguato per app, Redis, OCR, scheduler e monitoring leggero.
- Lex/Ollama puo' girare sullo stesso host solo per modelli piccoli CPU; per carichi AI pesanti serve nodo dedicato o runtime locale dello studio.
- Il profilo Hetzner avvia il servizio Docker `ollama` e `deploy.sh` verifica/scarica `PCT_LOCAL_AI_CHAT_MODEL` (default `gemma3:1b`), cosi' il widget Lex usa una sola pipeline backend senza dipendere dal companion browser per la risposta finale.
- Il Local Signer resta sul PC dell'avvocato e dialoga con `127.0.0.1`; non va spostato nel cloud.
- Gli artefatti PST/PDP/PAT runtime restano sotto `/opt/iusentra/data`, mai nel path del repository.
