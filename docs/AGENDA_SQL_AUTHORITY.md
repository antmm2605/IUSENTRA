# Agenda: archivio SQL proprietario

Il passaggio riutilizza appuntamenti, `agenda_sql_writer`, proiezioni calendario
e la procedura di adozione dello Scadenziario. Non introduce un altro database.
Il comando esplicito è `python -m tools.prepare_agenda_sql --tenant-registry ...`:
`--check` consulta soltanto; l'adozione richiede `--writers-drained` e
`--backup-dir` nel volume dati. Il deploy arresta e verifica i produttori prima
di eseguire backup e adozione.

Lo storico JSON resta conservato byte per byte insieme al backup SQL coerente,
verificato con impronta. La conferma SQL e il collegamento `.sql-owner`
impediscono il ritorno al JSON, anche ai produttori senza backend esplicito.
Un'interruzione dopo il collegamento richiede ripresa sul medesimo backup: non
riattivare immagini precedenti all'adozione. Errori, campi sconosciuti e identità
discordanti fermano la migrazione senza scartare righe.

Per gli identificativi già presenti, Agenda conserva la precedenza SQL prevista
dal precedente loader. Non sovrascrive righe SQL, neppure quando lo storico ha
uno stato diverso, e preserva righe presenti soltanto in SQL. Le differenze sono
registrate nell'audit `agenda.adozione_sql` con ID, campi e impronte delle due
versioni; i backup conservano i contenuti originali. Questa precedenza preserva
il dato operativo e non costituisce prova dell'avvenimento di un'udienza o
dell'identità di chi ha effettuato una modifica storica.

Le consultazioni successive leggono SQL senza importare o riscrivere JSON.
Modifiche e cancellazioni usano il confronto concorrente nativo e le proiezioni
già esistenti. Il file storico non può resuscitare appuntamenti cancellati.
Le conferme sono distinte per dominio ma il database non può essere adottato
da studi differenti. La ripetizione della migrazione non aggiunge altri audit.

Anche la cache del contesto Lex segue i contatori SQL persistenti della regia
live per Agenda e Scadenziario adottati, oltre alle impronte delle altre fonti.
Legge soltanto il contatore del dominio pertinente, riutilizzando il backend
della richiesta: nessun caricamento dei gestori, inizializzazione o scansione.
Una modifica SQL invalida il contesto pur lasciando invariato il JSON storico.

Le prove automatiche coprono preservazione, concorrenza, isolamento, errore del
backup e ripresa; la verifica materiale su 8080 e quella di produzione devono
essere registrate separatamente prima di dichiarare chiusa la consegna.
