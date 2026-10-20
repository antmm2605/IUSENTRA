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

Undici prove native SQLite/PostgreSQL senza skip: backoff, arresto, lease scadute, nuovo evento durante vecchio lavoro, riferibilità al tenant, migrazione conservativa, backup antecedente al DDL e ripresa idempotente con storico conservato. Dodici guardie Node dei riepiloghi e34guardie editor/stato positive; suite precedente di35prove runtime positiva con4skip PostgreSQL dell’esecuzione Windows, compensati dalle prove native dedicate. Typecheck e build frontend positivi. Questi controlli non sostituiscono il collaudo reale8080.


## Dipendenze non disponibili

La proiezione non conferma `tutto_letto` quando un passo del registro non è verificabile. Il pannello conserva i risultati salvati, mostra le cause e non riutilizza un riepilogo positivo storico come conferma della richiesta corrente. Due guardie dedicate provano errore terminale e schema non disponibile; il riepilogo ha una guardia specifica anche senza oggetti. Gli errori già esposti dalla lettura automatica non sono duplicati nel nuovo elenco delle cause.

La verifica estesa ha intercettato una difformità di formattazione nel contratto delle colonne SQL; corretta e riprovata prima dell’attivazione. La prima immagine non è stata attivata; la seconda compilazione è stata interrotta per includere la correzione del riepilogo degradato. Nessun rilascio parziale di queste candidate sulla macchina dell’utente.


## Correzione emersa dal collaudo reale

La prova materiale su8080 ha esaurito tre prese in carico da60secondi, lasciate scadere realmente sul solo fascicolo controllato31541BDA. La quarta presa in carico è stata rifiutata e lo scheduler locale è stato ripristinato healthy. Nessuna modifica diretta agli stati né al tempo del sistema. Il percorso normale aveva già prodotto un esito persistente succeeded al primo tentativo.

Aprire successivamente i dati collegati dell’editor ha però riaccodato la stessa pratica, azzerando il budget: comportamento realmente osservato nella candidata5008, non accettato come corretto. La nuova correzione elimina il POST automatico all’apertura: l’editor consulta i dati e osserva le lavorazioni prodotte dagli eventi delle fonti. Il recupero esplicito resta disponibile con un unico comando; il lavoro in background non possiede un indicatore globale bloccante.

Il POST di recupero dell’editor trasporta la generation osservata nel GET come recoveryGeneration. L’UPSERT SQL ammette una nuova generazione soltanto da idle e sulla generazione attesa; una consegna ripetuta, anche dopo la conclusione, oppure un lavoro già attivo non viene riaccodato. Le chiamate storiche senza generation sono consultive; su un errore terminale richiedono l’aggiornamento della pagina senza azzerare i tentativi. Tenant, permessi e collegamenti restano verificati prima del comando. Non cambia l’accodamento dei veri eventi di nuova fonte.

Diciassette guardie native SQLite/PostgreSQL comprendono concorrenza, ripetizione del comando, errori terminali e conservazione dello storico. Trentuno guardie Node comprendono i confini GET/comandi dell’editor, il caricamento condiviso e le route pigre. Trentaquattro guardie dell’editor positive. Nuova immagine, ripetizione dell’accettazione materiale, push/deploy e pulizia restano necessari; nessun completamento anticipato.
