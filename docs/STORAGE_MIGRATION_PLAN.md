# Piano di Migrazione Storage

## Obiettivo

Rendere ufficiale il percorso `JSON -> SQLite -> PostgreSQL` per i domini core, con report di consistenza e senza fallback invisibili.

## Flusso ufficiale

1. inventario del tenant e dei backend selezionati
2. precheck JSON e seed SQLite
3. migrazione su SQLite tenant-aware
4. replica su PostgreSQL
5. confronto conteggi JSON / SQLite / PostgreSQL
6. generazione report sotto `backup/`
7. attivazione esplicita del backend PostgreSQL per i domini core

## Domini coperti dal cutover ufficiale

- utenti
- audit
- clienti
- fascicoli
- agenda
- scadenziario

## Regole di attivazione

- PostgreSQL non diventa backend effettivo solo perche' e' configurato.
- Serve una connessione testata (`connessione_ok = true`).
- Serve una migrazione con report di consistenza positivo.
- Serve attivazione esplicita del tenant (`core_runtime_enabled = true`).

## Regole di sicurezza operativa

- se PostgreSQL attivo non e' disponibile, i domini core non ricadono in modo invisibile su JSON
- SQLite resta backend locale o fallback dichiarato per tenant non ancora cutoverizzati
- JSON resta compatibilita' legacy o ponte per domini non ancora migrati
- filesystem tenant resta sorgente primaria per documenti, buste, upload e modelli AI locali

## Comando CLI ufficiale

```bash
iusentra migrate --to=postgres --tenant=<slug-tenant>
```

Varianti utili:

```bash
iusentra migrate --to=sqlite --tenant=<slug-tenant>
iusentra migrate --to=postgres --tenant=<slug-tenant> --host=<db-host> --db-name=<nome-db> --user=<utente>
```
