# Crash Test Operativo

## Obiettivo

Il `Crash test operativo` simula una giornata reale di studio e verifica che IUSENTRA resti:

- spiegabile
- difendibile
- ripristinabile
- coerente sui dati

La superficie ufficiale e':

- `Piattaforma -> Crash test operativo`

I comandi ufficiali sono:

```bash
iusentra crash-test-operativo --tenant=<slug-tenant>
iusentra backup-blindato --tenant=<slug-tenant>
```

Nel runtime di produzione il crash test non dipende da `pytest`: se i tool di sviluppo non sono installati, il motore usa fallback interni equivalenti per le stesse fasi operative, mantenendo tracciabilita' verso i test E2E ufficiali dichiarati nel repository.

## Fasi presidiate

1. `Avvio e setup studio`
   verifica login, tenant, database, AI e worker.
2. `Cliente e fascicolo con dati sporchi`
   blocca duplicati, codice fiscale errato e campi obbligatori mancanti.
3. `Attivita', parcella e incasso`
   verifica coerenza del workflow economico.
4. `Pipeline AI e review`
   verifica diff AI vs umano, audit, approvazione e reject.
5. `Publish sicuro`
   verifica che un errore di publish SQL non corrompa draft o database.
6. `Migrazione tenant e rollback`
   verifica snapshot, diff, failure mode e rollback.
7. `Observability e remediation`
   verifica messaggi chiari per operatore non tecnico.

I test E2E ufficiali collegati alle fasi sono:

- `tests/e2e/test_operational_crash_day.py`
- `tests/e2e/test_studio_reale_flow.py`
- `tests/e2e/test_ai_pipeline_full.py`
- `tests/e2e/test_tenant_migration_full.py`

## Checklist finale

Ogni esecuzione produce una checklist `si/no` sulle cinque domande critiche:

- Posso rompere il DB e il sistema non fa danni?
- Posso spiegare ogni decisione AI?
- Un non tecnico capisce tutti gli errori?
- Posso migrare e tornare indietro senza paura?
- I dati sporchi NON entrano mai?

## Repair loop

Il crash test non si limita a fallire:

- salva il report
- genera ticket di riparazione
- esegue un backup blindato prima dei tentativi successivi
- riprova fino al numero massimo di tentativi configurato

I ticket vengono salvati come JSON nella coda di riparazione del tenant e anche nel repository SQL operativo.

## Pianificazione reale

Autotest di riparazione:

- `07:00`
- `13:30`
- `19:30`

Backup blindato:

- `23:50`

Il backup blindato esegue sempre:

- un backup `COMPLETO`
- un backup `INCREMENTALE`

## Destinazioni backup

Configurazioni supportate:

- `PCT_BACKUP_LOCAL_MIRROR_DIR`
  cartella locale del PC cliente
- `PCT_BACKUP_SECONDARY_MIRROR_DIR`
  seconda destinazione esterna o sincronizzata cloud
- `PCT_BACKUP_SECONDARY_LABEL`
  etichetta leggibile della seconda destinazione

Esempio pratico:

- copia 1: cartella locale sul PC del cliente
- copia 2: cartella sincronizzata Google Drive dello studio

## Report persistiti

Percorsi tipici nel backup del tenant:

- `backup/operational_crash_tests/operational_crash_test_<tenant>_<timestamp>.json`
- `backup/repair_queue/repair_ticket_<tenant>_<timestamp>_<nn>.json`
- `backup/operational_backups/operational_backup_<tenant>_<timestamp>.json`

## Regola di sicurezza

Se una fase critica fallisce:

- il sistema non continua in silenzio
- il sistema non nasconde il degrado
- il sistema non dichiara verde il tenant

Deve invece:

- bloccare la parte non affidabile
- spiegare cosa e' successo
- suggerire cosa fare
- lasciare traccia in audit e report
