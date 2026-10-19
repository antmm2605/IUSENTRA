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

Per un nuovo studio SQLite, `GestioneTenant.crea` prepara entrambi i calendari
prima di pubblicare lo studio nel registro. In questa fase nessun produttore
può ancora raggiungerlo: l'adozione riusa backup, audit e collegamenti già
previsti. Un errore di preparazione impedisce la pubblicazione; la ripresa sullo
stesso slug conserva i collegamenti confermati e non duplica gli audit.
Questo passaggio non cambia la configurazione degli studi già presenti e non
costituisce una conversione del backend da SQLite a PostgreSQL.

La manutenzione legacy riconosce inoltre le proprietà SQL registrate nel
database di destinazione, anche quando l'importazione usa un'altra cartella
legacy. Riusa la riconciliazione conservativa: conserva tutte le tabelle native,
aggiunge soltanto record nuovi in transazione e aggiorna le proiezioni calendario
esistenti per i soli ID importati. Il JSON storico del medesimo calendario non
viene reimportato; una cancellazione SQL non può essere annullata dal vecchio
file. Il confronto anti-perdita conserva come riferimento i conteggi SQL prima
del comando, distinguendoli dai conteggi storici JSON ancora consultabili.

Nella preparazione documentale SQLite la connessione del backup viene chiusa
prima della rinomina: la stessa procedura rispetta così il vincolo di apertura
dei file su Windows, mantenendo controllo di integrità e originali.

Le prove automatiche coprono preservazione, concorrenza, isolamento, errore del
backup e ripresa; la verifica materiale su 8080 e quella di produzione devono
essere registrate separatamente prima di dichiarare chiusa la consegna.
