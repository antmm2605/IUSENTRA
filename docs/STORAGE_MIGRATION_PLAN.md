# Piano di Migrazione Storage

## Obiettivo

Rendere ufficiale il percorso `JSON -> SQLite -> PostgreSQL` per tutti i domini migrabili, con report di consistenza e senza fallback invisibili.

## Flusso ufficiale

1. inventario del tenant e dei backend selezionati
2. precheck JSON e seed SQLite
3. migrazione su SQLite tenant-aware
4. replica su PostgreSQL
5. confronto conteggi JSON / SQLite / PostgreSQL
6. generazione report sotto `backup/`
7. attivazione esplicita del backend PostgreSQL per i domini tenant-aware compatibili

## Superficie amministrativa ufficiale

La console `/admin/assistente-migrazione` non si limita a descrivere il piano:

- lancia davvero la migrazione completa verso `SQLite` o `PostgreSQL`
- salva il report reale nel `backup/` del tenant
- mostra a video l'ultima esecuzione con:
  - domini core migrati o verificati
  - repository SQL sincronizzati
  - diff `pre/post` tra sorgente e destinazione
  - failure mode del tenant sporco
  - postura di rollback e recovery guidato
  - eventuali errori bloccanti
  - passi consigliati per la risoluzione

Questo consente al superadmin di capire subito se il cutover e' riuscito o dove intervenire prima di riprovare.

## Domini coperti dal cutover ufficiale

- utenti
- audit
- clienti
- fascicoli
- agenda
- scadenziario
- timesheet
- preventivi
- conferimenti
- fatturazione
- pagamenti
- template atti e preferenze editor
- legal intelligence
- giurisprudenza
- repository telematico
- workspace intelligence
- aggiornamenti legali
- coverage AI

## Regole di attivazione

- PostgreSQL non diventa backend effettivo solo perche' e' configurato.
- Serve una connessione testata (`connessione_ok = true`).
- Serve una migrazione con report di consistenza positivo.
- Serve attivazione esplicita del tenant (`core_runtime_enabled = true`).

## Regole di sicurezza operativa

- se PostgreSQL attivo non e' disponibile, i domini migrati non ricadono in modo invisibile su JSON
- SQLite resta backend locale o fallback dichiarato per tenant non ancora cutoverizzati
- JSON resta compatibilita' legacy o ponte per domini non ancora migrati
- filesystem tenant resta sorgente primaria per documenti, buste, upload e modelli AI locali
- il cutover completo del tenant include anche i repository SQL laterali e le pipeline `Coverage AI` / `Update Intelligence`, non solo `studio.db`

## Cosa rende una migrazione "blindata"

- `diff pre/post` leggibile per dominio
- `dirty tenant findings` espliciti su riferimenti orfani, delta e incongruenze
- `rollback posture` dichiarata e guidata nel report
- `recovery steps` coerenti con il failure mode rilevato
- `cutover PostgreSQL` attivato solo se staging, consistenza e repository strutturati risultano chiusi

## Comando CLI ufficiale

```bash
iusentra migrate --to=postgres --tenant=<slug-tenant>
```

Varianti utili:

```bash
iusentra migrate --to=sqlite --tenant=<slug-tenant>
iusentra migrate --to=postgres --tenant=<slug-tenant> --host=<db-host> --db-name=<nome-db> --user=<utente>
```
