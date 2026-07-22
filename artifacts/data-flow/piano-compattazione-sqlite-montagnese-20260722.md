# Piano sicuro di compattazione SQLite — Studio Legale Giuseppe Montagnese

Data audit: 22/07/2026, fuso `Europe/Rome`.

Stato del presente documento: audit eseguito esclusivamente in lettura. Durante
l'analisi non sono stati fermati container, non sono stati modificati dati e non
è stato eseguito alcun checkpoint. I processi diagnostici lenti avviati per
`dbstat` sono stati terminati al termine del controllo e non sono rimasti in
esecuzione.

## Risultato sintetico

Il file interessato è:

```text
/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/studio.db
```

Il database è integro (`PRAGMA quick_check = ok`), ma quasi tutto il suo peso è
una duplicazione SQL di JSON ricorsivi già presenti sul filesystem. La
manutenzione corretta non deve ricostruire il database dai JSON e non deve
toccare le tabelle verticali: deve eliminare soltanto i record mirror
ricostruibili dalle tabelle `moduli_*`, creare una copia compatta, confrontarla
logicamente con l'originale e sostituire il file soltanto dopo il confronto.

## Evidenze misurate sul server

### Disco, dati e backup

- filesystem: ext4 sul volume `/dev/sda1`;
- capacità: `322.302.373.888` byte;
- spazio libero rilevato: circa `55.117.766.656` byte;
- `/opt/iusentra/data`: `215.240.609.007` byte;
- `/opt/iusentra/backups`: sostanzialmente vuota (`12 KiB` al controllo);
- backup applicativo corrente: con percentuale `65%` e margine `4 GiB`, lo
  script richiede `144.201.363.150` byte liberi e rileva un deficit di
  `89.049.525.966` byte. `deploy/hetzner/backup.sh` quindi, correttamente,
  rifiuta oggi il backup globale per spazio insufficiente.

Lo script globale comprime il contenuto vivo di `/data` e tollera file cambiati
durante la lettura. Non è quindi il solo presidio adatto a una manutenzione
SQLite: per questa operazione serve prima una copia SQLite coerente a container
fermi.

### Database e WAL

Valori misurati mentre il servizio era attivo:

- `studio.db`: circa `15,172 GB` e in normale lieve crescita operativa;
- `studio.db-wal`: tra `120` e `144 MB` durante l'audit;
- pagina SQLite: `4.096` byte;
- `page_count`: circa `3.703.992` pagine al primo rilievo;
- `freelist_count = 0`;
- `auto_vacuum = 0`;
- `journal_mode = wal`;
- `wal_autocheckpoint = 1000`;
- `PRAGMA quick_check = ok`, durata sul file gonfiato: `191,59` secondi.

Il solo processo che manteneva aperti stabilmente database, WAL e SHM al
momento del controllo era il worker scheduler. L'applicazione può comunque
aprire il database in risposta alle richieste. Per la manutenzione vanno quindi
fermati almeno `app` e `scheduler-worker`; se presente va fermato anche
`ocr-worker`.

### Righe da rimuovere e righe da preservare

Righe mirror ricorsive presenti:

| Famiglia | `moduli_dati` | `moduli_json_records` |
| --- | ---: | ---: |
| `documenti_ai_file_*` | 14.111 | 126.999 |
| `fascicoli_importazione_*` | 0 | 0 |
| `lex_dataset_*` | 0 | 0 |

Totali delle due tabelle:

- `moduli_dati`: 14.193 righe;
- `moduli_json_records`: 133.800 righe;
- da preservare: 82 moduli espliciti e 6.801 record non ricorsivi.

I JSON sorgente sotto
`fascicoli/documenti_ai` sono 14.141 per `14.905.416.347` byte. Il loro peso è
coerente con la duplicazione SQL rilevata. La directory completa misura circa
`64,76 GB` perché contiene anche file originali e altri artefatti: **non deve
essere cancellata né esclusa integralmente dal backup**.

Dimensione fisica misurata con `dbstat`:

| Oggetto SQLite | Byte |
| --- | ---: |
| `moduli_json_records` | 15.065.341.952 |
| indice PK `moduli_json_records` | 18.034.688 |
| `idx_moduli_json_records_modulo` | 16.441.344 |
| `moduli_dati` | 6.217.728 |
| indice PK `moduli_dati` | 1.810.432 |

Questi cinque oggetti occupano `15.107.846.144` byte. Poiché devono restare
solo 82 moduli e 6.801 record, la dimensione compatta attesa è prudentemente
inferiore a `200 MB`, con stima realistica nell'intervallo `65–100 MB`.

### Baseline strutturata da preservare

Conteggi principali al momento dell'audit:

- fascicoli: 334;
- clienti: 261;
- appuntamenti: 870;
- scadenze: 778;
- soggetti: 272;
- soggetti-parti: 774;
- documenti AI verticali: 120 documenti, 120 versioni, 36 testi e 480 eventi
  audit;
- utenti: 1;
- moduli espliciti non ricorsivi: 82;
- record mirror espliciti non ricorsivi: 6.801.

Tutte le tabelle non vuote dispongono di una chiave primaria esplicita. Il
passaggio tramite `VACUUM INTO` non dipende quindi da rowid anonimi usati come
identificatori applicativi.

`PRAGMA foreign_key_check` rileva già 25 anomalie storiche:

- 4 `fascicoli -> clienti`;
- 20 `scadenze -> appuntamenti`;
- 1 `scadenze -> fascicoli`.

La compattazione non deve mascherarle né aumentarle. Il criterio di accettazione
è: stesso contenuto logico delle tabelle preservate e stesso raggruppamento di
violazioni prima/dopo, con zero nuove violazioni. La bonifica di queste 25
relazioni è un intervento distinto.

## Blocco da risolvere prima della manutenzione

Il runtime è stato corretto affinché
`_build_json_to_sqlite_sources(..., include_recursive=False)` sia il default.
Tuttavia `scripts/audit_tenant_data_structure.py --repair` usa ancora
`include_recursive=True`: una sua esecuzione reinserirebbe circa 15 GB di OCR e
testi estratti appena rimossi.

Prima della manutenzione occorre pertanto:

1. distribuire il guardrail runtime che esclude i ricorsivi;
2. correggere anche la modalità `--repair`, affinché verifichi i ricorsivi con
   manifest/fingerprint o opt-in esplicito senza copiarne il payload in
   `studio.db`;
3. non eseguire `audit_tenant_data_structure.py --repair` sul tenant finché il
   punto 2 non è stato distribuito e verificato.

## Procedura raccomandata: copia ombra, confronto, scambio atomico

La procedura seguente è intenzionalmente offline. Il database attivo rimane
intatto fino a quando la copia compatta non ha superato tutti i controlli.
Durante la finestra non devono essere inseriti dati dallo studio. Dopo il primo
riavvio, se si rende necessario un rollback e nel frattempo sono state eseguite
operazioni utente, il database compatto va prima preservato e riconciliato: non
è ammesso sovrascrivere alla cieca scritture successive allo scambio.

### 1. Variabili e preflight

Eseguire come `root` sul server:

```bash
set -euo pipefail

TENANT=/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese
DB="$TENANT/studio.db"
REPO=/opt/iusentra/repo
ENV=/opt/iusentra/.env.hetzner
COMPOSE="$REPO/deploy/hetzner/docker-compose.hetzner.yml"
STAMP="$(date +%Y%m%d_%H%M%S)"
WORK="/opt/iusentra/maintenance/studio-montagnese-$STAMP"
ROLLBACK="/opt/iusentra/backups/studio-montagnese-precompact-$STAMP"

test "$(readlink -f "$TENANT")" = "/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese"
test -f "$DB"
test ! -e "$WORK"
test ! -e "$ROLLBACK"

DB_BYTES="$(stat -c %s "$DB")"
FREE_BYTES="$(df -PB1 /opt/iusentra | awk 'NR==2 {print $4}')"
MIN_REQUIRED="$((2 * DB_BYTES + 8 * 1024 * 1024 * 1024))"
printf 'db=%s free=%s minimo=%s\n' "$DB_BYTES" "$FREE_BYTES" "$MIN_REQUIRED"
test "$FREE_BYTES" -ge "$MIN_REQUIRED"

install -d -m 700 "$WORK" "$ROLLBACK"
```

La soglia richiede due volte la dimensione del database più 8 GiB: una copia
ombra e, nel caso peggiore, un rollback journal di circa 15 GB. Con i valori
misurati il picco lascia oltre 20 GB liberi.

### 2. Fermare tutti gli scrittori e consolidare il WAL

```bash
cd "$REPO"
docker compose --env-file "$ENV" -f "$COMPOSE" stop scheduler-worker ocr-worker app

if fuser "$DB" "$DB-wal" "$DB-shm" >/dev/null 2>&1; then
  echo "Errore: uno o più processi mantengono aperto studio.db" >&2
  fuser -v "$DB" "$DB-wal" "$DB-shm" || true
  exit 1
fi

DB="$DB" python3 - <<'PY'
import os, sqlite3

db = os.environ["DB"]
con = sqlite3.connect(db, isolation_level=None, timeout=60)
checkpoint = tuple(con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
if checkpoint != (0, 0, 0):
    raise SystemExit(f"checkpoint non concluso: {checkpoint!r}")
result = [row[0] for row in con.execute("PRAGMA quick_check")]
if result != ["ok"]:
    raise SystemExit(f"quick_check non valido: {result!r}")
con.close()
print("checkpoint e quick_check: ok")
PY

test ! -e "$DB-wal" || test "$(stat -c %s "$DB-wal")" -eq 0
```

### 3. Creare la copia ombra coerente

```bash
cp --reflink=auto --sparse=always --preserve=mode,ownership,timestamps \
  "$DB" "$WORK/studio.work.db"
sync "$WORK/studio.work.db"

sha256sum "$DB" "$WORK/studio.work.db" | tee "$ROLLBACK/SHA256SUMS-pre.txt"
test "$(sha256sum "$DB" | awk '{print $1}')" = \
     "$(sha256sum "$WORK/studio.work.db" | awk '{print $1}')"
```

Il file attivo non viene più modificato. Tutte le operazioni successive, fino
allo scambio, interessano soltanto `studio.work.db`.

### 4. Salvare il manifest logico pre-compattazione

Il manifest deve ignorare soltanto le tre famiglie ricorsive. Per ogni altra
tabella calcola numero di righe e hash del multinsieme dei record, indipendente
dall'ordine fisico e dai rowid. Il confronto comprende anche schema e gruppi di
violazioni delle chiavi esterne.

```bash
DB="$DB" OUT="$ROLLBACK/manifest-pre.json" python3 - <<'PY'
import base64, hashlib, json, os, sqlite3

db, out = os.environ["DB"], os.environ["OUT"]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")

def encoded(value):
    if value is None:
        return ["null", None]
    if isinstance(value, bytes):
        return ["bytes", base64.b64encode(value).decode("ascii")]
    if isinstance(value, float):
        return ["float", value.hex()]
    return [type(value).__name__, value]

def row_hash(row):
    raw = json.dumps([encoded(v) for v in row], ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def table_digest(table, sql=None, params=()):
    query = sql or f'SELECT * FROM "{table.replace(chr(34), chr(34) * 2)}"'
    hashes = sorted(row_hash(tuple(row)) for row in con.execute(query, params))
    aggregate = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
    return {"rows": len(hashes), "sha256_multiset": aggregate}

objects = [tuple(row) for row in con.execute(
    "SELECT type,name,tbl_name,coalesce(sql,'') FROM sqlite_master "
    "WHERE name NOT LIKE 'sqlite_autoindex_%' ORDER BY type,name"
)]
schema_hash = hashlib.sha256(json.dumps(objects, ensure_ascii=False,
    separators=(",", ":")).encode("utf-8")).hexdigest()

tables = [row[0] for row in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' "
    "AND name NOT IN ('moduli_dati','moduli_json_records') ORDER BY name"
)]
logical = {table: table_digest(table) for table in tables}

prefixes = ("documenti_ai_file_*", "fascicoli_importazione_*", "lex_dataset_*")
where_mod = "NOT (nome GLOB ? OR nome GLOB ? OR nome GLOB ?)"
logical["moduli_dati"] = table_digest(
    "moduli_dati",
    "SELECT * FROM moduli_dati WHERE " + where_mod,
    prefixes,
)
allowed_modules = [row[0] for row in con.execute(
    "SELECT nome FROM moduli_dati WHERE " + where_mod + " ORDER BY nome", prefixes
)]
record_hashes = []
record_rows = 0
for module in allowed_modules:
    for row in con.execute(
        "SELECT * FROM moduli_json_records WHERE modulo=? ORDER BY record_key",
        (module,),
    ):
        record_rows += 1
        record_hashes.append(row_hash(tuple(row)))
logical["moduli_json_records"] = {
    "rows": record_rows,
    "sha256_multiset": hashlib.sha256(
        "".join(sorted(record_hashes)).encode("ascii")
    ).hexdigest(),
}

targets = {
    "moduli_dati": con.execute(
        "SELECT count(*) FROM moduli_dati WHERE NOT (" + where_mod + ")", prefixes
    ).fetchone()[0],
    "moduli_json_records": con.execute(
        "SELECT count(*) FROM moduli_json_records WHERE "
        "modulo GLOB ? OR modulo GLOB ? OR modulo GLOB ?", prefixes
    ).fetchone()[0],
}
fk_groups = {}
for table, rowid, parent, fkid in con.execute("PRAGMA foreign_key_check"):
    key = f"{table}->{parent}#fk{fkid}"
    fk_groups[key] = fk_groups.get(key, 0) + 1

payload = {
    "schema_sha256": schema_hash,
    "logical_tables": logical,
    "target_rows": targets,
    "foreign_key_groups": dict(sorted(fk_groups.items())),
}
with open(out, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
con.close()
print(out)
PY
```

### 5. Eliminare esclusivamente i mirror sulla copia ombra

Si usa `GLOB`, non `LIKE`, affinché gli underscore siano caratteri letterali.
La tabella figlia viene eliminata prima della tabella padre.

```bash
WORK_DB="$WORK/studio.work.db" COUNTS="$ROLLBACK/cleanup-counts.json" python3 - <<'PY'
import json, os, sqlite3

db, counts_path = os.environ["WORK_DB"], os.environ["COUNTS"]
prefixes = ("documenti_ai_file_*", "fascicoli_importazione_*", "lex_dataset_*")
con = sqlite3.connect(db, isolation_level=None, timeout=60)
con.execute("PRAGMA foreign_keys=ON")
mode = con.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
if str(mode).lower() != "delete":
    raise SystemExit(f"journal_mode inatteso: {mode!r}")
con.execute("PRAGMA synchronous=FULL")

before = {
    "moduli_dati": con.execute(
        "SELECT count(*) FROM moduli_dati WHERE "
        "nome GLOB ? OR nome GLOB ? OR nome GLOB ?", prefixes
    ).fetchone()[0],
    "moduli_json_records": con.execute(
        "SELECT count(*) FROM moduli_json_records WHERE "
        "modulo GLOB ? OR modulo GLOB ? OR modulo GLOB ?", prefixes
    ).fetchone()[0],
}
con.execute("BEGIN IMMEDIATE")
deleted_records = con.execute(
    "DELETE FROM moduli_json_records WHERE "
    "modulo GLOB ? OR modulo GLOB ? OR modulo GLOB ?", prefixes
).rowcount
deleted_modules = con.execute(
    "DELETE FROM moduli_dati WHERE "
    "nome GLOB ? OR nome GLOB ? OR nome GLOB ?", prefixes
).rowcount
con.execute("COMMIT")

after = {
    "moduli_dati": con.execute(
        "SELECT count(*) FROM moduli_dati WHERE "
        "nome GLOB ? OR nome GLOB ? OR nome GLOB ?", prefixes
    ).fetchone()[0],
    "moduli_json_records": con.execute(
        "SELECT count(*) FROM moduli_json_records WHERE "
        "modulo GLOB ? OR modulo GLOB ? OR modulo GLOB ?", prefixes
    ).fetchone()[0],
}
if deleted_modules != before["moduli_dati"]:
    raise SystemExit("numero moduli eliminati non coerente")
if deleted_records != before["moduli_json_records"]:
    raise SystemExit("numero record eliminati non coerente")
if after != {"moduli_dati": 0, "moduli_json_records": 0}:
    raise SystemExit(f"mirror residui: {after!r}")

result = [row[0] for row in con.execute("PRAGMA quick_check")]
if result != ["ok"]:
    raise SystemExit(f"quick_check dopo DELETE non valido: {result!r}")
with open(counts_path, "w", encoding="utf-8") as handle:
    json.dump({"before": before, "deleted": {
        "moduli_dati": deleted_modules,
        "moduli_json_records": deleted_records,
    }, "after": after}, handle, ensure_ascii=False, indent=2, sort_keys=True)
con.close()
print(counts_path)
PY
```

### 6. Creare e verificare il file compatto

```bash
test ! -e "$WORK/studio.compact.db"

WORK_DB="$WORK/studio.work.db" COMPACT="$WORK/studio.compact.db" python3 - <<'PY'
import os, sqlite3

source, compact = os.environ["WORK_DB"], os.environ["COMPACT"]
con = sqlite3.connect(source, isolation_level=None, timeout=60)
escaped = compact.replace("'", "''")
con.execute(f"VACUUM INTO '{escaped}'")
con.close()

check = sqlite3.connect(f"file:{compact}?mode=ro", uri=True, timeout=60)
result = [row[0] for row in check.execute("PRAGMA quick_check")]
if result != ["ok"]:
    raise SystemExit(f"quick_check compatto non valido: {result!r}")
check.close()
print(compact)
PY

COMPACT_BYTES="$(stat -c %s "$WORK/studio.compact.db")"
printf 'database compatto: %s byte\n' "$COMPACT_BYTES"
test "$COMPACT_BYTES" -lt $((200 * 1024 * 1024))
```

Generare `manifest-post.json` ripetendo il comando del punto 4 con:

```bash
DB="$WORK/studio.compact.db"
OUT="$ROLLBACK/manifest-post.json"
```

Poi confrontare:

```bash
PRE="$ROLLBACK/manifest-pre.json" POST="$ROLLBACK/manifest-post.json" python3 - <<'PY'
import json, os

with open(os.environ["PRE"], encoding="utf-8") as handle:
    pre = json.load(handle)
with open(os.environ["POST"], encoding="utf-8") as handle:
    post = json.load(handle)
if pre["schema_sha256"] != post["schema_sha256"]:
    raise SystemExit("schema differente")
if pre["logical_tables"] != post["logical_tables"]:
    raise SystemExit("contenuto logico preservato differente")
if pre["foreign_key_groups"] != post["foreign_key_groups"]:
    raise SystemExit("gruppi foreign key differenti")
if post["target_rows"] != {"moduli_dati": 0, "moduli_json_records": 0}:
    raise SystemExit(f"mirror ricorsivi ancora presenti: {post['target_rows']!r}")
print("confronto logico pre/post: ok")
PY
```

### 7. Scambio atomico e riavvio

Con tutti i container scrittori ancora fermi:

```bash
# Gli eventuali sidecar consolidati vengono conservati, mai lasciati accanto
# al nuovo database.
mv "$DB" "$ROLLBACK/studio.original.db"
if [ -e "$DB-wal" ]; then mv "$DB-wal" "$ROLLBACK/studio.original.db-wal"; fi
if [ -e "$DB-shm" ]; then mv "$DB-shm" "$ROLLBACK/studio.original.db-shm"; fi

mv "$WORK/studio.compact.db" "$DB"
chown root:root "$DB"
chmod 0644 "$DB"

DB="$DB" python3 - <<'PY'
import os, sqlite3

db = os.environ["DB"]
con = sqlite3.connect(db, isolation_level=None, timeout=60)
mode = con.execute("PRAGMA journal_mode=WAL").fetchone()[0]
con.execute("PRAGMA wal_autocheckpoint=1000")
result = [row[0] for row in con.execute("PRAGMA quick_check")]
if str(mode).lower() != "wal" or result != ["ok"]:
    raise SystemExit(f"post-swap non valido: mode={mode!r}, check={result!r}")
con.close()
print("post-swap SQLite: ok")
PY

rm -f -- "$WORK/studio.work.db" "$WORK/studio.work.db-journal"
rmdir "$WORK"

cd "$REPO"
docker compose --env-file "$ENV" -f "$COMPOSE" start app scheduler-worker
docker compose --env-file "$ENV" -f "$COMPOSE" ps app scheduler-worker
curl -fsS https://app.iusentra.it/api/pronto
```

Il comando `rm` è limitato ai due file esatti della directory di lavoro già
validata; non usa glob, variabili non risolte o cancellazioni ricorsive.

### 8. Verifica dopo riavvio

Accettare la manutenzione soltanto se:

1. `quick_check = ok`;
2. dimensione `studio.db < 200 MB`;
3. `journal_mode = wal`;
4. i conteggi core coincidono con il manifest;
5. target ricorsivi ancora a zero dopo almeno due cicli scheduler;
6. le 25 anomalie FK storiche non sono aumentate;
7. `app` e `scheduler-worker` sono healthy;
8. `/api/pronto` risponde;
9. nel browser reale di produzione il tenant Montagnese apre fascicoli, Agenda,
   Scadenziario, PEC e fonti senza regressioni;
10. il tempo di `quick_check` e le letture applicative non mostrano il ritardo
    causato dal file da 15 GB.

Solo dopo queste verifiche comprimere la copia di rollback:

```bash
zstd -T2 -6 --long=27 --no-progress \
  -o "$ROLLBACK/studio.original.db.zst.tmp" "$ROLLBACK/studio.original.db"
zstd -t "$ROLLBACK/studio.original.db.zst.tmp"
mv "$ROLLBACK/studio.original.db.zst.tmp" "$ROLLBACK/studio.original.db.zst"
sha256sum "$ROLLBACK/studio.original.db.zst" > "$ROLLBACK/studio.original.db.zst.sha256"
sha256sum -c "$ROLLBACK/studio.original.db.zst.sha256"
rm -f -- "$ROLLBACK/studio.original.db"
```

Conservare checksum, manifest e backup compresso almeno fino alla conclusione
dei test reali e del deploy sul medesimo commit.

## Rollback esatto

Se il file originale non è ancora stato compresso:

```bash
cd "$REPO"
docker compose --env-file "$ENV" -f "$COMPOSE" stop scheduler-worker ocr-worker app
DB="$DB" python3 - <<'PY'
import os, sqlite3
con = sqlite3.connect(os.environ["DB"], isolation_level=None, timeout=60)
checkpoint = tuple(con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
if checkpoint != (0, 0, 0):
    raise SystemExit(f"checkpoint del compatto non concluso: {checkpoint!r}")
con.close()
PY
test ! -e "$ROLLBACK/studio.compact.failed.db"
mv "$DB" "$ROLLBACK/studio.compact.failed.db"
if [ -e "$DB-wal" ]; then mv "$DB-wal" "$ROLLBACK/studio.compact.failed.db-wal"; fi
if [ -e "$DB-shm" ]; then mv "$DB-shm" "$ROLLBACK/studio.compact.failed.db-shm"; fi
mv "$ROLLBACK/studio.original.db" "$DB"
chown root:root "$DB"
chmod 0644 "$DB"
docker compose --env-file "$ENV" -f "$COMPOSE" start app scheduler-worker
```

Se esiste solo il backup compresso:

```bash
cd "$REPO"
docker compose --env-file "$ENV" -f "$COMPOSE" stop scheduler-worker ocr-worker app
DB="$DB" python3 - <<'PY'
import os, sqlite3
con = sqlite3.connect(os.environ["DB"], isolation_level=None, timeout=60)
checkpoint = tuple(con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
if checkpoint != (0, 0, 0):
    raise SystemExit(f"checkpoint del compatto non concluso: {checkpoint!r}")
con.close()
PY
sha256sum -c "$ROLLBACK/studio.original.db.zst.sha256"
test ! -e "$ROLLBACK/studio.restore.tmp"
zstd -dc "$ROLLBACK/studio.original.db.zst" > "$ROLLBACK/studio.restore.tmp"
test "$(sha256sum "$ROLLBACK/studio.restore.tmp" | awk '{print $1}')" = \
     "$(awk 'NR==1 {print $1}' "$ROLLBACK/SHA256SUMS-pre.txt")"
test ! -e "$ROLLBACK/studio.compact.failed.db"
mv "$DB" "$ROLLBACK/studio.compact.failed.db"
if [ -e "$DB-wal" ]; then mv "$DB-wal" "$ROLLBACK/studio.compact.failed.db-wal"; fi
if [ -e "$DB-shm" ]; then mv "$DB-shm" "$ROLLBACK/studio.compact.failed.db-shm"; fi
mv "$ROLLBACK/studio.restore.tmp" "$DB"
chown root:root "$DB"
chmod 0644 "$DB"
DB="$DB" python3 - <<'PY'
import os, sqlite3
con = sqlite3.connect(os.environ["DB"], isolation_level=None, timeout=60)
print(con.execute("PRAGMA journal_mode=WAL").fetchone()[0])
print(con.execute("PRAGMA quick_check").fetchone()[0])
con.close()
PY
docker compose --env-file "$ENV" -f "$COMPOSE" start app scheduler-worker
curl -fsS https://app.iusentra.it/api/pronto
```

## Pulizia successiva e backup globale

Nel tenant sono presenti due vecchi WAL di recovery da circa `15,248 GB`
ciascuno e più copie storiche del database PEC. Non vanno eliminati prima della
creazione e verifica del nuovo rollback esatto. Dopo la piena accettazione, i
due vecchi recovery `studio_db_20260721_225859` e
`studio_db_install_20260721_232416` risultano superseded dal backup nuovo e
possono essere valutati per rimozione esplicita. Le copie `pec_audit` sono fuori
dal perimetro di questa procedura e richiedono verifica/retention separata.

Dopo ogni pulizia ricalcolare:

```bash
du -sb /opt/iusentra/data
df -PB1 /opt/iusentra/backups
```

Non forzare il backup globale se il preflight resta insufficiente. Il backup
deve essere trasferito verso capacità esterna/off-host oppure lo script deve
calcolare correttamente il set realmente incluso, senza escludere directory che
contengono originali legali. La variabile `BACKUP_ALLOW_LOW_SPACE=1` non è una
soluzione ordinaria e non deve essere usata senza una stima reale dell'archivio
e margine verificato.

## Criteri finali di accettazione

- nessun JSON o file originale cancellato;
- eliminate soltanto le tre famiglie mirror in `moduli_dati` e
  `moduli_json_records`;
- manifest logico pre/post identico per tutte le informazioni preservate;
- schema identico;
- zero nuove violazioni di chiavi esterne;
- database compatto integro e inferiore a 200 MB;
- target ricorsivi a zero anche dopo lo scheduler;
- rollback esatto verificato con SHA-256 e test zstd;
- app e scheduler healthy;
- prova reale sul tenant Montagnese positiva;
- nessuna futura esecuzione `--repair` capace di duplicare nuovamente OCR e
  staging nel database.
