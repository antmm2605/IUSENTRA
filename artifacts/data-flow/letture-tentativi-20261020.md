# Coda letture: tentativi e preparazione

Candidata 2.441.4; accettazione reale e rilascio ancora da eseguire.

## Risultato richiesto

Un errore del motore non deve riavviare lo stesso lavoro ad ogni tick, bloccare la pagina né diventare un risultato positivo. I dati già acquisiti, le bozze e la fonte restano conservati.

## Procedura primaria

La tabella esistente `letture_eventi` conserva contatore, disponibilità del prossimo tentativo e ultima causa. Tre tentativi per generazione, attese persistenti30/60secondi. `letture_eventi_esiti` conserva ogni tentativo, incluse lease scadute e cause. Non è una seconda coda. Nuova fonte o comando esplicito riaprono soltanto quel fascicolo e azzerano il budget della nuova generazione; un vecchio worker non può consumarla.

La preparazione condivisa prima dell’avvio è:

`python -m tools.prepare_reading_runtime --tenant-registry /data/tenants.json --backup-dir /data/backup/reading-runtime-20261020`

La procedura prepara lo schema documentale nativo, esegue backup SQL verificato prima di estendere la coda e verifica nuovamente lo schema proprietario. Recupera soltanto le righe del tenant con causa `DocumentAISchemaNotPrepared`, conservando lo storico. Ripetere il comando non riaccoda quelle già recuperate. Nessuna enumerazione di documenti, nessuna lettura OCR e nessuna riparazione nelle GET.

Usare lo stesso comando anche sulla copia Docker locale prima di attivare app, scheduler e OCR della candidata. Non basta ricreare i servizi: l’immagine nuova e gli archivi persistenti devono essere preparati insieme.

## Riscontri tecnici iniziali

Undici prove native SQLite/PostgreSQL senza skip: backoff, arresto, lease scadute, nuovo evento durante vecchio lavoro, riferibilità al tenant, migrazione conservativa, backup antecedente al DDL e ripresa idempotente con storico conservato. Undici guardie Node dei riepiloghi e34guardie editor/stato positive; suite precedente di35prove runtime positiva con4skip PostgreSQL dell’esecuzione Windows, compensati dalle prove native dedicate. Typecheck e build frontend positivi. Questi controlli non sostituiscono il collaudo reale8080.
