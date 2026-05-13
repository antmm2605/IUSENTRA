# Audit probatorio WORM

IUSENTRA tratta l'audit probatorio come prova tecnica-forense, non come log applicativo. La fonte probatoria e' l'oggetto JSON canonico e firmato salvato in storage S3-compatible con Object Lock; l'indice SQL serve solo per ricerca, filtri e ricostruzione rapida.

## Modello probatorio

Ogni evento `audit-event-v1` viene:

1. validato e minimizzato;
2. collegato alla catena `tenant_id + fascicolo_id` tramite `prev_event_hash`;
3. canonicalizzato con `RFC8785-JCS`;
4. hashato con `SHA-256`;
5. firmato come payload esplicito `signed_event + event_hash`;
6. scritto su WORM prima dell'indice SQL;
7. indicizzato in `audit_events_index`.

Il formato usa due livelli:

- `audit-envelope-v1`: contiene `signed_event`, `event_hash` e firma. Questo e' l'oggetto probatorio primario e non include i dati WORM perche' `version_id` e retention sono noti solo dopo l'upload.
- `audit-worm-receipt-v1`: ricevuta separata firmata, salvata in WORM, che collega `event_id`, `event_hash`, bucket, key, version_id, retention e modalita Object Lock.

Questo evita firme su campi valorizzati dopo l'upload e mantiene verificabile il vincolo WORM.

## Storage WORM

Configurazione richiesta:

```text
AUDIT_WORM_ENDPOINT_URL
AUDIT_WORM_REGION
AUDIT_WORM_BUCKET
AUDIT_WORM_ACCESS_KEY
AUDIT_WORM_SECRET_KEY
AUDIT_WORM_RETENTION_YEARS=10
AUDIT_WORM_MODE=COMPLIANCE
AUDIT_WORM_REQUIRE_OBJECT_LOCK=true
```

Per l'ambiente locale Docker e per Hetzner senza provider esterno gia'
disponibile, IUSENTRA fornisce un profilo `audit-worm` che avvia:

- `audit-worm`: MinIO S3-compatible con Object Lock reale;
- `audit-worm-init`: inizializzazione bucket con `--with-lock`, versioning e
  default retention `COMPLIANCE` 10 anni;
- `audit-postgres`: indice/query cache Postgres dedicato all'audit.

Configurazione locale:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\configure_audit_worm_local.ps1
docker compose --profile audit-worm up -d --build audit-postgres audit-worm audit-worm-init redis app
```

Configurazione Hetzner:

```bash
cd /opt/iusentra/repo
bash deploy/hetzner/configure_audit_worm.sh
bash deploy/hetzner/deploy.sh
```

Gli script generano le credenziali WORM e la chiave JWS fuori repository:
`data/audit/keys` in locale, `/opt/iusentra/data/audit/keys` su Hetzner. La
chiave privata non viene committata e non viene stampata nei log.

In produzione il sistema rifiuta:

- retention inferiore a 10 anni;
- `AUDIT_REQUIRE_WORM=false`;
- `AUDIT_REQUIRE_SIGNATURE=false`;
- bucket senza versioning;
- bucket senza Object Lock;
- modalita diversa da `COMPLIANCE`.

Il modulo non espone funzioni delete e rifiuta l'overwrite della stessa key.

## Firma e TSA

La firma preferita resta CAdES/PKCS#7 tramite Local Signer/HSM/PKCS#11 quando configurato. Il runtime usa `AUDIT_SIGNING_MODE=CADES` con `AUDIT_CADES_LOCAL_SIGNER_URL` e `AUDIT_CADES_VERIFY_URL`: il payload canonico viene inviato al signer esterno e la verifica passa dal verificatore PKCS#7 configurato. Il fallback implementato e' JWS (`RS256` o `ES256`) con chiave fornita da key vault o file sigillato; non esistono chiavi hardcoded o generate dal runtime.

Gli snapshot Merkle possono richiedere RFC 3161 TSA. In produzione, se `AUDIT_REQUIRE_TSA_FOR_SNAPSHOT=true` e la TSA fallisce, lo snapshot fallisce. In development/test e' ammesso solo un token non qualificato marcato come tale.

## Snapshot e bundle

`audit_snapshot_job(period="daily", tenant_id=...)` seleziona gli eventi non inclusi, li ordina per `event_ts_utc,event_id`, calcola Merkle root con domain separation e salva lo snapshot firmato in WORM. Se `tenant_id` non viene passato, il job scopre dall'indice i tenant con eventi aperti nel periodo. Il bundle fascicolo contiene:

- `events/*.json`
- `snapshots/*.json`
- `proofs/*.json`
- `tsa/*.tsr` o token non qualificati dev/test
- `files_manifest.json`
- `signers/*.pem`
- `README_VERIFICA.md`

Il bundle si verifica offline con:

```bash
python scripts/verify_audit.py verify-bundle bundle.zip
python scripts/verify_audit.py verify-chain bundle.zip --fascicolo-id <id>
python scripts/verify_audit.py verify-proof proofs/<event_id>.json
```

## Ricostruzione indice

Se WORM e indice SQL divergono, usare:

```bash
python scripts/rebuild_audit_index.py --tenant-id <tenant>
```

Lo script legge solo oggetti WORM, verifica hash/firma minimi, ricrea righe mancanti e segnala conflitti senza modificare gli oggetti probatori.
