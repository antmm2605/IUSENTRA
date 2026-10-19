# Scadenziario: adozione del repository SQL nativo

L'intervento riutilizza `scadenze`, `GestioneScadenziario`, lo scrittore puntuale
con confronto dello snapshot, le proiezioni indicizzate del calendario e i
segnali persistenti già esistenti. Non cambia regole di calcolo, date,
priorità, stati, riferimenti a fascicoli, documenti o PEC, né invii e firme.

## Procedura e tutela della fonte

`tools.prepare_scadenziario_sql --check` verifica gli studi registrati senza
importazioni. Il deploy ferma app e worker soltanto se occorre l'adozione;
verifica l'assenza dei produttori, poi esegue il comando con
`--writers-drained --backup-dir /data/backup/scadenziario-sql-20261019`.
Backup SQL coerente verificato e originale JSON precedono qualsiasi scrittura.
Un'identità duplicata, un campo sconosciuto o versioni discordanti bloccano
l'adozione: nessuna riga viene ignorata o sostituita per somiglianza.

Il file `scadenze.json.sql-owner` contiene esclusivamente il collegamento
allo studio e al database, impronta e riferimento del backup, senza dati
operativi o credenziali. La conferma è registrata nello stesso database in
`scadenziario_sql_state`, con audit nativo nella stessa transazione.
Una barriera senza conferma SQL impedisce il ritorno al JSON. La ripresa
usa fonte, proprietario e backup originari; non rimuovere la barriera per
aggirare un errore. Non riattivare immagini precedenti che non la rispettano.
Il database non può essere adottato da un secondo studio o da una seconda
fonte. La verifica avviene nella transazione; su PostgreSQL il lock della
tabella di proprietà serializza anche adozioni concorrenti da fonti diverse.

Tutti i costruttori nativi risolvono il collegamento confermato, inclusi CLI,
scheduler e produttori storici privi del parametro database. Un backend
esplicito diverso dal proprietario viene respinto. Su PostgreSQL il resolver
riutilizza il registro degli studi e la factory core; su SQLite apre solo il
database esistente, senza inizializzazioni dello schema nella consultazione.

Dopo l'adozione il caricamento non legge, importa, deduplica o riscrive il
JSON. Le modifiche conservano il CAS nativo e gli indici derivati. Il JSON
rimane storico: non è un mirror operativo e una cancellazione SQL non può
essere annullata dal suo contenuto. Una vecchia istanza JSON viene bloccata
sotto il medesimo lock della migrazione prima di scrivere.

## Evidenze e stato

Confronto preliminare in sola lettura del 19/10/2026: produzione 1.582 e 37
scadenze, tre archivi locali con 0, 5 e 191 righe SQL. Nessun campo storico
sconosciuto o conflitto tra i modelli SQL e JSON. La riga locale presente solo
in SQL viene preservata. Non sono nuove scadenze né prove di correttezza legale.

Guardie mirate SQLite e PostgreSQL comprendono persistenza, concorrenza,
originali, audit, corruzione del JSON dopo adozione, cancellazione senza
resurrezione, errore di backup, conflitti, ripresa e perimetro minimo delle
consultazioni. Il deploy verifica inoltre il drain prima dell'adozione.

Accettazione non verificata su macchina reale: Computer Use non espone i
browser della sessione. Controlli tecnici, migrazione e deploy non sostituiscono
click, scroll e osservazione dell'interfaccia reale su 127.0.0.1:8080.
La chiusura funzionale resta aperta fino a tale prova; nessuna copertura globale
di Agenda, PEC o degli altri incarichi è dichiarata da questo intervento.

Prima applicazione locale: tre adozioni confermate, un solo audit per studio,
backup coerenti con controllo di integrità e impronte SQL/JSON identiche a
quelle precedenti. Confermata la lettura senza importazioni, deduplicazioni
o scritture JSON anche nei costruttori senza database esplicito. Durante la
revisione è stato aggiunto il caso di configurazione con due studi sullo
stesso database: la seconda adozione deve essere respinta integralmente,
preservando il primo proprietario. Non è una nuova riassegnazione dei dati.
