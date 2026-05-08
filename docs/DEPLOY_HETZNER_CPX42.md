# Deploy Hetzner CPX42

> **Versione corrente:** 2.202.0 — commit `8c1bfde`
> Guida aggiornata: 08/05/2026

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

Non salvare chiavi reali nel repository.

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
```

Il deploy stampa il commit deployed e l'URL health al termine. Il `git rev-parse` deve corrispondere all'HEAD del branch pushato.

## Backup

```bash
bash /opt/iusentra/repo/deploy/hetzner/backup.sh
```

Il comando crea un archivio di `/opt/iusentra/data` e il relativo file `.sha256` in `/opt/iusentra/backups`.

Cron consigliato:

```cron
15 2 * * * /opt/iusentra/repo/deploy/hetzner/backup.sh >/var/log/iusentra-backup.log 2>&1
```

Lo script applica anche la retention: per default conserva al massimo 3 backup applicativi, almeno 2 copie, rimuove quelli piu' vecchi di 14 giorni e mantiene la directory backup entro 8 GiB quando possibile. In produzione i valori sono governati da `IUSENTRA_BACKUP_RETENTION_COUNT`, `IUSENTRA_BACKUP_RETENTION_MIN_COUNT`, `IUSENTRA_BACKUP_RETENTION_DAYS` e `IUSENTRA_BACKUP_RETENTION_MAX_GIB` in `/opt/iusentra/.env.hetzner`.

I backup `.tar.zst` usano zstd ad alta compressione (`IUSENTRA_BACKUP_ZSTD_LEVEL=19`, `IUSENTRA_BACKUP_ZSTD_LONG_WINDOW=27` di default). I modelli locali Ollama sono esclusi di default tramite `IUSENTRA_BACKUP_EXCLUDE_PATHS=./ollama`, perche' sono rigenerabili dal deploy e non devono gonfiare ogni archivio dati. Se una singola copia supera il tetto configurato, lo script conserva comunque il numero minimo di copie e stampa un avviso esplicito invece di cancellare l'ultimo backup valido.

Per compattare lo storage live senza cambiare i path applicativi:

```bash
python3 /opt/iusentra/repo/scripts/compact_iusentra_storage.py --data-root /opt/iusentra/data
python3 /opt/iusentra/repo/scripts/compact_iusentra_storage.py --data-root /opt/iusentra/data --apply
```

Il comando usa hardlink per deduplicare allegati email e mirror backup identici nello stesso filesystem; i riferimenti salvati nei JSON restano invariati.
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
| 2.202.0 | `a06145c` | 08/05/2026 | Lex: fix CASO 1 (sentenza esatta forza ricerca pubblica, confidence cap ≤ 0.45), fix CASO 2 (studio_data_lookup mostra dati cliente reali). `giurisprudenza_specifica` in `_STRICT_LEGAL_WORKFLOWS`. Handler deterministic `studio_data_lookup`. `user_facing_output_guard`. `case_law_completeness`. `exact_case_law_guard`. Prompt: no "Ciao sono Lex" su query operative. |
| 2.201.0 | `177ca37` | 08/05/2026 | Lex: distinzione fonti pubbliche vs dati studio. Parser sentenze esatte, ExactLegalReferenceGuard, StudioDataGateway, fix `_should_force_web_fallback`, fix `_clienti_lines` (4→8, CF/email), intent `cliente_anagrafica` → `studio_data_lookup`. |
| 2.200.0 | `77a4f40` | 08/05/2026 | Hetzner CPX42: fix Caddyfile rate_limit (→ Flask-Limiter), Ollama profilo opzionale `ai`, deploy.sh robusto con `COMPOSE_PROFILES`. Lex v2.200.0: debug payload 46 campi, fasi 1-16 router/guards/contracts. |
