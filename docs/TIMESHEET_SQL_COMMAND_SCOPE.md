# Timesheet: fonte SQL e salvataggi puntuali

Candidata 2.437.55, lavoro aperto fino all’accettazione reale e al rilascio.

## Risultato richiesto

Creare o cambiare una voce deve leggere e scrivere solo quella voce e i suoi
collegamenti necessari nello studio autorizzato. Una modifica da una pagina
superata deve essere respinta, senza perdere dati o dichiarare successo.

## Procedura esistente e causa

Il factory operativo risolve già il database SQL dello studio dall’ancora clienti.
La migrazione esplicita `tools/migrate_timesheet_canonical_sql.py` conserva backup,
identificativi e collegamenti; non viene avviata dalle richieste. La modalità
legacy del repository resta disponibile alle procedure esplicite che la usano.
Non si tratta di creare un secondo database o un nuovo motore di migrazione.

Il vecchio repository carica tutte le voci alla costruzione e salva sostituendo
l’intera tabella. Due snapshot concorrenti riproducono sia la perdita di una
modifica su un’altra riga, sia la cancellazione di una nuova voce concorrente.

## Correzione in verifica

Il repository SQL carica una riga per chiave alla prima richiesta. L’elenco viene
letto solo quando richiesto come elenco o riepilogo. La creazione non legge
l’archivio. Il comando salva soltanto le righe cambiate, senza DELETE globale;
confronta tutte le colonne SQL e i metadati originali, con transazione e retry
nativi SQLite/PostgreSQL. Un conflitto annulla tutto il comando.

Le colonne SQL sono primarie; note e metadati annidati restano nella colonna JSON
della stessa riga SQL. Questo non è un ritorno a un file JSON operativo. File
storici non vengono letti, riscritti o cancellati nel percorso SQL. Metadati non
validi o identità della riga discordante restano errori espliciti.

Una nuova associazione verifica cliente e fascicolo nel database proprietario e
la loro concordanza. Le relazioni storiche non cambiate non vengono ricostruite.
I segnali persistenti già presenti restano nella stessa transazione; il comando
non introduce notifiche parallele, scansioni o nuove elaborazioni documentali.

L’API espone l’impronta di revisione della voce. Il cambio di stato React e della
vista classica invia la revisione effettivamente mostrata; revisione assente o
superata produce HTTP 409, nessun audit di successo e nessuna modifica dello
stato. Il confronto SQL nella transazione protegge anche l’intervallo successivo
alla lettura della richiesta. Flussi fiscali, firma, deposito e PEC non cambiano.

## Evidenze e limiti

Due test negativi riproducono il difetto iniziale. Le prove successive comprendono
snapshot concorrenti, rollback, letture e scritture puntuali, origine SQL, JSON
storico preservato, note/metadati, collegamenti e revisione HTTP. Il confronto
controllato su 1.000 voci misura costruzione del repository e modifica: mediana
41,96 ms prima, 1,24 ms nella candidata, tre campioni per versione nello stesso
ambiente. Non misura rete, rendering o velocità globale dell’applicazione.

Restano accettazione sul browser reale 8080, persistenza e sincronizzazione fra
finestre, prova di errore/bozza, immagine finale, gate, deploy e pulizia. Nessuna
riconvalida massiva o modifica automatica ai dati reali è parte della correzione.


## Verifica delle fonti e navigazione

Audit in sola lettura: tre archivi locali (una voce complessiva) e due studi sul
server (tre voci complessive), nessun metadato invalido o collegamento orfano. Le
due voci del vecchio database del modulo sul server sono già presenti nel
canonico; i JSON delle voci sono vuoti e non richiedono importazioni. Originali
conservati. Il repository distinto delle proposte di tracking passivo conserva
ancora il proprio JSON: è censito nel lavoro globale di migrazione e non va
confuso con le voci Timesheet già confermate in SQL.

Timesheet passa sotto Ricerca Studio, fuori da Agenda. Sito Studio diventa
Sito Web Studio. Il menu Studio conserva i collegamenti e i relativi permessi,
riordinati in Gestione e contabilità, Documenti e atti, Ricerca giuridica e
Strumenti Lex; ricerca locale delle funzioni per etichetta e termini operativi.
Recupero crediti in serie passa dai Fascicoli a Gestione e contabilità, accanto
alla fatturazione, conservando il permesso fascicoli.leggi. Nessuna ricerca del
menu consulta database, carica pagine o avvia processi.

Il canale di controllo segnala il browser locale come disabilitato in Work
durante il collaudo, benché l’utente lo segnali attivo: la conferma materiale di queste modifiche non è ancora
eseguita e il lavoro resta aperto, anche con test e build positivi.

Direttiva esplicita utente del 17/10/2026: procedere con commit, push e deploy della candidata 55 senza bloccare il rilascio sul canale browser indisponibile. Collaudo visivo non verificato su macchina reale; nessuna accettazione visiva simulata. Restano obbligatori test tecnici, CI, parità sorgenti, salute dei servizi e pulizia.
