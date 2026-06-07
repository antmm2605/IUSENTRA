# Database e migrazioni

Aggiornato: 2026-05-29, presidio anti-perdita SQLite `2.248.84`.

## Stato reale

IUSENTRA usa piu' livelli di persistenza:

- JSON tenant-aware sotto data root per molte entita operative;
- SQLite locale per repository strutturati e tenant locali;
- PostgreSQL tenant-aware dove configurato per runtime cloud o repository specifici;
- audit WORM/Object Lock per eventi probatori.

Non esiste un singolo comando Alembic obbligatorio per tutta l'app in questa fase. Non documentare migrazioni Alembic come presenti se non sono collegate al modulo toccato.

## Regole tenant

- Ogni lettura/scrittura usa il tenant corrente da sessione/request context o API key tenant-aware.
- In multi-studio senza tenant valido si fallisce chiusi.
- Il client non puo' inviare `tenant_id`, `studio_id`, `tenant_slug` o path root.
- I path repository si risolvono con helper tenant-aware, non con fallback globali.

## Setup test/dev

Per test locali usare data root temporaneo quando il test puo' scrivere dati:

```powershell
python -m pytest -q tests/test_tenant_isolation_runtime.py --tb=short
python -m pytest -q tests/test_storage_strategy.py --tb=short
python scripts\audit_tenant_data_structure.py --repair
```

Per App V2/security:

```powershell
python -m pytest -q tests/test_auth.py tests/test_backend_security_phase5.py tests/test_tenant_isolation_runtime.py --tb=short
```

## Migrazioni dati

Ogni migrazione dati deve:

1. dichiarare repository e tenant impattati;
2. creare backup o snapshot prima di scrivere;
3. essere idempotente;
4. non inventare record quando manca un dato reale univoco;
5. registrare audit se modifica dati operativi;
6. avere test su tenant A/B o data root temporaneo;
7. documentare rollback.

Ogni modifica che tocca JSON, SQLite, PostgreSQL, agenda, scadenziario, notifiche, PEC o creazione studi deve inoltre passare `scripts/audit_tenant_data_structure.py`. Lo script verifica tutti i JSON previsti del tenant, `studio.db`, `notifications.db`, `moduli_dati`, `moduli_json_records` e gli schemi PostgreSQL equivalenti. Con `--repair` riallinea solo la struttura minima tenant-aware e non crea backup o snapshot.

## Presidio anti-perdita SQLite

Il passaggio JSON -> SQLite dello studio non può più cancellare un database
operativo già popolato quando i JSON correnti sono vuoti, incompleti o puntano
al tenant sbagliato.

Regole applicate da `GestioneDatabase.migra_verso_sqlite`:

- prima di scrivere viene letto il target esistente e viene eseguito un
  precheck anti-perdita sui domini operativi: clienti, fascicoli, agenda,
  scadenze, timesheet, timer, preventivi, conferimenti, fatturazione,
  pagamenti, messaggi, utenti, privacy e backup;
- se la sorgente JSON contiene meno record di un target SQLite già popolato,
  la migrazione torna `riuscita=false`, conserva il database esistente e
  riporta `Blocco anti-perdita` nel report;
- la scrittura persistente avviene su database di staging nascosto e viene
  installata sul target solo dopo validazione di conteggi, identificativi e
  payload JSON;
- i repository secondari che generano o aggiornano JSON vengono seguiti da un
  secondo passaggio core controllato, così anche i mirror `moduli_json_records`
  restano allineati;
- `time_tracking` è tenant-aware in `timesheet/time_tracking.json` e viene
  migrato in `time_tracking_timers`, incluso nei report e nel cutover
  PostgreSQL.

Audit manuale su uno studio:

```powershell
python scripts\audit_sqlite_migration_integrity.py `
  --db data\tenants\<studio>\studio.db `
  --data-root data\tenants\<studio> `
  --report-json artifacts\sqlite-migration-audit-<studio>.json
```

Il comando esce con codice `1` se manca anche un solo record o se un payload
non conserva tutti i campi della sorgente.

### Pre-verifica e riconciliazione sicura

L'azione `Attiva SQLite` non deve più essere un singolo comando ambiguo. Il
flusso amministrativo espone quattro passaggi distinti:

1. `Analizza`: esegue `preverifica_attivazione_sqlite` senza scrivere dati.
2. `Migra JSON`: crea il database da sorgente JSON solo se il precheck non
   rileva rischio perdita dati.
3. `Riconcilia`: usa il database operativo esistente come base, crea backup e
   importa solo i record presenti nella sorgente ma assenti dal database.
4. `Attiva SQLite`: abilita la modalità SQLite solo quando il database
   risultante supera i controlli di integrità.

Gli stati ammessi nel messaggio finale sono:

- `Completata`;
- `Completata con avvisi non bloccanti`;
- `Bloccata per protezione dati`;
- `Non eseguita`;
- `Eseguita riconciliazione`;
- `Rollback eseguito`;
- `Richiede intervento SUPERADMIN`.

Se il database operativo contiene più record della sorgente, ad esempio
`clienti 25 / 9`, la migrazione distruttiva resta bloccata. La riconciliazione
sicura:

- crea un backup del database operativo prima di scrivere;
- conserva i record presenti solo nel database;
- aggiunge i record presenti solo nella sorgente;
- non sovrascrive alla cieca i conflitti sullo stesso ID;
- segnala record in conflitto, orfani o non migrati con motivo e azione
  consigliata;
- registra nel report finale record preservati, importati, già presenti e in
  conflitto.

In multi-tenant il tenant è obbligatorio e il percorso
`/data/tenants/<tenant_id>/studio.db` è trattato come risorsa protetta. In
single-tenant `PCT_STORAGE_MODE=SQLITE` è la configurazione esplicita; il flag
storico `PCT_SQLITE_MODE=1` resta compatibile ma non deve produrre stati
contraddittori.

## Rollback migrazione

Rollback minimo:

- fermare scritture sul modulo impattato;
- ripristinare backup/snapshot del tenant interessato;
- rieseguire integrity check mirato;
- verificare `/api/pronto` e smoke della pagina;
- registrare commit, tenant redatto, comando e risultato.

## PostgreSQL

Quando PostgreSQL e' configurato, il DSN deve arrivare da configurazione ambiente/tenant, mai da documenti o codice hardcoded. I test devono preservare parita con SQLite quando il modulo supporta entrambi.

## File runtime

Non committare modifiche runtime in:

- `data/`
- `email/`
- `output/`
- `intelligence/`
- cache o database generati

Eccezioni solo se esplicitamente richieste e motivate. Se Docker/local runtime modifica questi file, ripulire la worktree prima del commit.
