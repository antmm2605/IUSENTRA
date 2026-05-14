# Database e migrazioni

Aggiornato: 2026-05-14, fase 12 `fasereact`.

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
