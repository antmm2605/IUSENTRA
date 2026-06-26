# Job incrementali e memoria persistente

Aggiornato: 2026-06-26.

## Regola operativa

I job automatici frequenti di IUSENTRA devono lavorare solo su dati nuovi, modificati o rimasti in coda. Una rilettura storica completa è ammessa solo come manutenzione esplicita, tracciata e non schedulata ogni pochi minuti.

La memoria non vive nella chat e non è volatile: ogni cursore, hash o deduplica deve essere salvato in storage tenant-aware, SQLite/PostgreSQL o repository dedicato.

## Matrice

| Area | Storage memoria | Logica incrementale |
| --- | --- | --- |
| PEC IMAP | `EMAIL_CASELLA_DB` sotto `/data/tenants/<studio>/email`, UID IMAP e `Message-ID` nei record email | `mailbox_sync_runtime` chiama `sincronizza_imap(..., incremental_only=True)` e limita la finestra automatica con `IUSENTRA_MAILBOX_SYNC_AUTOMATIC_LIMIT` |
| Email ordinaria | `EMAIL_ORDINARIA_DB` sotto `/data/tenants/<studio>/email`, UID IMAP e `Message-ID` | stesso contratto PEC: solo nuovi messaggi; riparazione storico solo da motore basso livello con flag esplicito |
| PEC audit-grade | `pec_audit.sqlite`, tabelle `pec_messages`, `pec_local_acquire_runs`, `pec_local_acquire_items` | l'acquisizione locale salva cursore `pec_local_acquire_v2`; dopo bootstrap/backlog legge nuovi arrivi e boundary, non tutta la casella |
| Worker PEC | `pec_jobs` in `pec_audit.sqlite` | i worker processano solo job pendenti/dovuti, a budget per tick |
| Documenti fascicolo Lex | `pec_audit_log` con azione `pec.document_presidio.checked` e indice `idx_pec_audit_action_resource` | marker calcolato da fascicolo, documento e hash SHA-256; se hash invariato il documento non viene riletto |
| Documenti AI | repository Document AI tenant-aware e mirror `fascicoli/documenti_ai` | se il documento ha già `hash_sha256`, la sorgente non riapre il file solo per ricalcolare l'hash |
| Dataset Lex studio | `/data/tenants/<studio>/intelligence/lex_dataset/latest_job.json`, `jobs.json`, `source_index.json` | fingerprint su path, dimensione, `mtime_ns` e opzioni; se invariato restituisce `skipped_unchanged` senza rileggere `documenti_ai.json` |
| Local AI / RAG | `/data/tenants/<studio>/intelligence/local_ai.db` | indicizzazione file basata su impronta contenuto/metadati; file invariati vengono saltati |
| Notifiche e Web Push | `/data/tenants/<studio>/notifications/notifications.db`, tabelle `notifications`, `push_subscriptions`, `notification_deliveries` | `dedupe_key` per notifica e storico consegne impediscono doppi invii push sullo stesso evento |
| Polling deposito/cancelleria | stato polling tenant-aware e repository fascicoli/PEC | scheduler automatico usa finestre corte (`IUSENTRA_DEPOSIT_POLL_DAYS`, `IUSENTRA_PEC_CANCELLERIA_POLL_DAYS`) e massimo 7 giorni |
| Calendari | repository `calendar_sync_engine` tenant-aware | retry solo su job pendenti, non su tutto il calendario |

## Variabili di produzione consigliate

```bash
COMPOSE_PROFILES=
PCT_LOCAL_AI_ENABLED=0
IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED=0
IUSENTRA_MAILBOX_SYNC_AUTOMATIC_LIMIT=25
IUSENTRA_PEC_DOCUMENT_PRESIDIO_LIMIT=0
IUSENTRA_DEPOSIT_POLL_DAYS=3
IUSENTRA_PEC_CANCELLERIA_POLL_DAYS=2
```

`IUSENTRA_PEC_DOCUMENT_PRESIDIO_LIMIT=0` disattiva il ripasso automatico massivo dei fascicoli. Quando viene riabilitato per una finestra di manutenzione, il presidio resta comunque incrementale grazie ai marker in `pec_audit_log`.

## Dove non si deve tornare

- Non usare JSON globali come fonte operativa in multi-tenant.
- Non aumentare i limiti automatici per "recuperare tutto" nello scheduler frequente.
- Non abilitare Ollama o manutenzione AI locale come default di produzione.
- Non inviare Web Push quando `create_notification()` restituisce `created=False` per deduplica.
- Non usare full scan PEC se non con variabile esplicita di manutenzione e report operativo.
