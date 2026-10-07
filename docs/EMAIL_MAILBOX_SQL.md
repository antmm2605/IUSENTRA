# Catalogo SQL della posta — accettazione ancora aperta

Stato al 06/10/2026: attivati in produzione i quattro cataloghi dei due studi
SQLite, insieme a tutti i chiamanti operativi nella stessa immagine EK.
Conservate le acquisizioni con originali verificati e gli stati di lettura.
La selezione multipagina è stata osservata nel browser reale; restano aperte
la campagna materiale completa e l'accettazione della copia locale.
Il documento non certifica accettazione sul browser reale o sulla copia locale.

## Fonte primaria e isolamento

`email_mailbox_records` conserva il catalogo per studio, tipo di casella e ID
del messaggio. `email_mailbox_bootstrap` registra l'inizializzazione verificata;
`email_mailbox_audit` registra nello stesso commit attore e campi modificati.
SQLite e PostgreSQL usano lo stesso contratto e indice cartella/stato.
Le migrazioni di sola struttura sono `pct/sql/20261006_email_mailbox.sql` e
`pct/sql/20261006_email_mailbox_postgres.sql`, identiche al DDL del repository;
non importano dati e non attivano automaticamente le caselle storiche.
Le firme, il parser MIME, gli originali, gli allegati e i trasporti del gestore
nativo non cambiano. I file originali restano nel percorso dello studio.

In modalità SQL il JSON è soltanto un mirror rigenerabile. Una casella vuota
rimane vuota; un archivio non inizializzato o indisponibile non importa copie
storiche durante una richiesta e non produce conteggi fittizi. La factory
risolve il tenant dal contesto autorizzato o dal registro esplicito del worker.
Una nuova casella può inizializzarsi vuota solo se anche il modulo SQL core e
il mirror sono vuoti. Le caselle storiche richiedono la procedura sotto.

## Lettura multipla e concorrenza

La selezione usa gli stessi filtri dell'elenco, su tutte le pagine, fino a
5.000 messaggi reali nella posta in arrivo. La selezione contiene gli ID
esistenti in quel momento, senza includere i messaggi arrivati successivamente.
Gli audit virtuali privi di messaggio non sono selezionabili.

La scrittura controlla presenza, cartella e conflitti prima del commit.
Gli aggiornamenti indipendenti si conservano, un conflitto annulla il batch,
le letture già registrate non generano nuovi audit. Il salvataggio riguarda
soltanto le righe selezionate. Dopo la conferma primaria la pagina ricarica
elenco, conteggi e dettaglio usando i filtri più recenti.

Gli esportatori del mirror si serializzano mediante il marcatore SQL della
casella, leggono il catalogo dopo aver acquisito il lock e sostituiscono il
file temporaneo con flush/fsync e replace atomico. L'errore del mirror non
annulla una lettura già committata: la risposta indica esplicitamente la
presa visione salvata e la copia da riallineare. Tale esito non viene esteso
a invii o eliminazioni fisiche. Un errore di storage nell'allineamento degli
inviati raggiunge il gestore JSON, senza essere nascosto dal catch storico.

## Procedura storica SQLite

Gli script versionabili sono in `scripts/mailbox/`. I piani completi e i
backup contengono dati riservati e restano esclusivamente nell'area backup
autorizzata, fuori dal repository. La produzione attuale ha due studi SQLite;
questa procedura non pretende di migrare storici PostgreSQL.

1. Preparare immagine, chiamanti, API e superficie React coerenti senza
   sostituire ancora il servizio operativo. Conservare i backup verificati.
2. Fermare tutti i writer applicativi del profilo ufficiale: app, scheduler
   e worker OCR. Non avviare un secondo container applicativo.
3. Generare piani freschi con `plan-mailbox-reconciliation.py` dalle fonti
   SQL, dagli stati SQL delle letture e dagli originali EML verificati.
   Nessuna assenza dal mirror elimina un messaggio SQL. Ogni acquisizione
   aggiuntiva richiede percorso sicuro, provenienza nativa e SHA-256.
4. Eseguire `apply-mailbox-plans.py --plan-dir <piani> --registry <registro>
   --data-root <dati> --backup-manifest <manifest>` per la validazione senza
   scrittura; aggiungere `--apply` soltanto dopo i controlli preliminari.
   La sola validazione non ricontrolla le impronte dei backup.
5. Con `--apply` la procedura verifica writer fermi, copertura completa delle
   caselle, appartenenza al tenant, fonti e target, backup di entrambi i
   database di ogni studio. Dopo il controllo dei backup ricontrolla tutte
   le fonti immediatamente prima di scrivere. Non modifica i moduli core.
6. In caso di errore mantenere i writer fermi. La transazione è per casella;
   non esiste una transazione atomica tra database di studi diversi. La
   ripresa conserva una casella già inizializzata soltanto se coincide
   esattamente col piano. Non ripristinare automaticamente un backup.
7. Verificare cataloghi e mirror, attivare tutti i chiamanti nella stessa
   immagine e riavviare esclusivamente i servizi del profilo ufficiale.
   Verificare container unico `iusentra-app`, stato healthy e readiness.

## Guardrail e accettazione

La suite candidata `mailbox-storage` è registrata in
`scripts/run_pytest_phases.py`: quattro shard, `--timeout-minutes 5`.
I test PostgreSQL richiedono un database controllato configurato tramite
le variabili `AUDIT_POSTGRES_*` e `CONDIVISIONI_TEST_PG_HOST`; credenziali
mai nel codice o nel report. Ogni fixture usa schema/database temporaneo
isolato e lo rimuove alla fine, senza accedere ai dati operativi.
Il collegamento della suite alla CI resta da integrare con tale database.

Guardrail mirati: selezione e permessi, CAS, isolamento, rollback e audit,
campi storici sconosciuti, mirror concorrenti e falliti, schema gemello,
bootstrap fail-closed, migrazione completa controllata e ripresa senza
nuovi audit. Sono controlli tecnici, non accettazione utente.

Restano obbligatorie la campagna materiale completa in produzione,
seguita dal riallineamento finale e dalla prova visibile su 127.0.0.1:8080:
selezione multipagina, lettura, diminuzione di contatori ed elenco, persistenza
dopo riapertura, errori, hover/focus, scroll completo, desktop/tablet/mobile
e tempi percepiti. Nessuna chiusura prima di queste prove e dell'allineamento
locale, branch gemelli, CI e deploy finale.

## Casella React, finestre e aggiornamento delle viste

L’apertura della radice della casella in una finestra usa `view=mailbox`:
restano disponibili ricerca, filtri, selezione e comandi. Un collegamento
puntuale a messaggio o audit mantiene il lettore originale. Il parametro
esplicito della casella resta valido anche dopo la selezione di una riga.

Le scritture della posta pubblicano l’aggiornamento del dominio comunicazioni
soltanto dopo la conferma JSON `ok=true`. La lista consentita comprende
lettura/non lettura, cestino/ripristino/eliminazione, bulk e sincronizzazione.
Invio, firma, deposito e SMTP restano esclusi dal meccanismo; il trasporto
accettato non viene modificato. Il collegamento tra finestre accetta solo
origine identica e finestre effettivamente gestite dall’applicazione.
La vista che esegue il comando si aggiorna dal proprio percorso di successo;
le altre ricevono gli eventi inoltrati, conservano i filtri e ricaricano
elenco e dettaglio. Un lettore incorporato non riutilizza uno snapshot
obsoleto dopo l’aggiornamento di un altro contesto.

Guardrail Node registrati in `frontend/package.json`: `email_page_errors`,
`mailbox_operational_refresh`, `mailbox_work_windows` (33 controlli mirati
prima dell’ulteriore correzione del dettaglio). Non sostituiscono click,
scorrimento, hover/focus, persistenza e accettazione locale reale. La campagna
completa e il riallineamento finale restano aperti.

### Lettore originale e conferme dei comandi
Il lettore mostra Segna letta sui messaggi non letti dell'archivio normale; durante la registrazione disabilita il comando, conserva il contenuto e visualizza lo stato. Dopo la conferma JSON positiva ricarica il dettaglio e comunica l'aggiornamento alle finestre della stessa origine. La fonte audit resta distinta e non offre una lettura operativa inesistente. I comandi PEC read/unread rispondono JSON alle richieste della UI; il redirect non-XHR resta invariato. Nessuna modifica a invio SMTP, Local Signer, classificazione o firme.

Un 404 indica fonte non più disponibile; errori di connessione, sessione, permessi o risposta incompleta mostrano un errore esplicito e Riprova. Un dettaglio senza identificativo viene rifiutato. Le fonti audit mantengono i tentativi limitati già previsti per disponibilità temporanea. Il riepilogo Oggi usa il giorno italiano e si riallinea dopo le scritture pertinenti, senza polling quando chiuso. Guardrail aggiuntivo tests/js/mailbox_detail_errors.test.mjs; non sostituisce l'accettazione materiale su 8080.