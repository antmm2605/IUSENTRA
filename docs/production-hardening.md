# Production hardening IUSENTRA

Questa guida descrive il presidio introdotto per rendere IUSENTRA piu stabile in produzione: storage SQL governato, Redis, worker RQ, controlli sicurezza, audit HMAC, health check, backup e monitoring.

## Migrazione JSON verso database

I dati storici JSON non vengono cancellati. La migrazione crea un backup preventivo, legge i JSON sotto `data/`, calcola hash SHA-256 e popola la tabella `json_documents` con indice full-text SQLite FTS5.

```powershell
python scripts/migrate_json_to_db.py --data-root data --database-url sqlite:///data/iusentra.sqlite --backup-dir data/backup
python scripts/migrate_json_to_db.py --data-root data --database-url $env:DATABASE_URL --limit 50
```

Per PostgreSQL impostare `DATABASE_URL=postgresql://...`. Il repository principale mantiene anche i percorsi SQL gia presenti in `pct/storage_migration_full.py`; la tabella `json_documents` e' il layer di sicurezza per migrazione e ricerca full-text governata.

## Redis, cache e worker

Redis e' usato come backend preferito per cache, rate limit e RQ. Se Redis non risponde, l'app usa fallback controllati dove possibile e segnala stato `degraded`.

```powershell
docker compose up -d redis
python worker.py
```

Con Docker:

```powershell
docker compose --profile hardening up -d redis rq-worker
```

## Gunicorn produzione

Il file `gunicorn.conf.py` legge le variabili:

```powershell
$env:WEB_CONCURRENCY="2"
$env:GUNICORN_THREADS="2"
$env:GUNICORN_TIMEOUT="120"
gunicorn -c gunicorn.conf.py wsgi:app
```

## Secrets Fernet

Non salvare mai chiavi reali nel repository.

```powershell
python -c "from core.security.secrets_manager import SecretsManager; print(SecretsManager.generate_key())"
```

Configurare `FERNET_PRIMARY_KEY` e, durante una rotazione, `FERNET_OLD_KEYS`.

## Upload sicuri

Il modulo `core.security.upload_validator` verifica nome file, path traversal, estensioni, magic bytes, MIME reale, dimensione massima, doppie estensioni pericolose e XML con entita esterne.

## Rate limiting e security headers

`core.security.rate_limit` preferisce Flask-Limiter con Redis e usa fallback in memoria se la dipendenza non è disponibile. Gli asset statici React/PWA (`/static/*`, manifest, service worker e favicon) sono esclusi dal rate limit utente per non bloccare caricamento e cambio pagina; API, login, upload e route operative restano invece protette. `core.security.headers` applica CSP, HSTS su cookie secure, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` e COOP.

## Audit HMAC

Gli eventi sensibili possono essere firmati con `core.security.audit_log`. Impostare `AUDIT_HMAC_KEY` in produzione e verificare l'integrita con `verify_event`.

## Health check e metriche

Endpoint disponibili:

```text
/health/live
/health/ready
/health/dependencies
/metrics
```

`/health/ready` controlla database, Redis e filesystem. `/health/dependencies` aggiunge RQ, Ollama e SMTP in modalita non sensibile. `/metrics` espone metriche Prometheus senza secrets.

## Backup e verifica

```powershell
python scripts/backup_database.py --database-url sqlite:///data/iusentra.sqlite --data-root data --backup-dir data/backup
python scripts/verify_backup.py data/backup/iusentra-backup-YYYYMMDD_HHMMSS.zip
```

Per PostgreSQL lo script usa `pg_dump` se `DATABASE_URL` non e' SQLite.

## Prometheus e Grafana

```powershell
docker compose --profile monitoring up -d prometheus grafana
```

Prometheus legge `prometheus.yml`; Grafana puo importare `monitoring/grafana-dashboard.json`.

## Checklist deploy produzione

- Eseguire migrazione JSON verso DB su backup verificato.
- Configurare `DATABASE_URL`, `REDIS_URL`, `FERNET_PRIMARY_KEY`, `AUDIT_HMAC_KEY`, `SECRET_KEY`.
- Avviare app con `gunicorn -c gunicorn.conf.py wsgi:app`.
- Avviare `worker.py` per le code RQ.
- Verificare `/health/live`, `/health/ready`, `/health/dependencies`.
- Verificare `/metrics` da Prometheus.
- Eseguire backup e `scripts/verify_backup.py`.
- Controllare GitHub Actions: `Lint + syntax`, `Pytest core`, le 12 parti `Coverage moduli critici parte */12`, quality gates e CodeQL.
