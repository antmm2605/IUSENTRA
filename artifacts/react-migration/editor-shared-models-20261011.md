# Modello editor comune agli studi — verifica in corso

Direttiva: condividere la struttura del modello «Richiesta sostituzione udienza con note scritte». Ogni studio compila esclusivamente i propri dati di studio, PEC, cliente e fascicolo; i modelli personali restano separati.

Catalogo SQL di piattaforma distinto dai repository tenant. Identificativo con prefisso `shared:`; pubblicazione soltanto tramite procedura amministrativa puntuale con impronta revisionata, backup coerente del catalogo esistente e ricevuta SQL atomica. Il modello distribuito conserva i font incorporati ma nessun testo del documento sorgente nel pacchetto dei font. Nessuna copia degli archivi personali. PostgreSQL usa un DSN di piattaforma esplicito, mai quello dello studio corrente.

Il corpo revisionato ha 24 campi collegati. Oggetto Carta docente e controparte ministeriale appartengono a questo tipo di atto: non sono un'automatizzazione universale di tutti i procedimenti. La revisione preventiva deve controllare anche il testo libero: il controllo automatico di codice fiscale e email non dimostra l'assenza di ogni nome o recapito.

## Riscontri locali effettivi

- Primo studio: compilazione dal comando Modelli, salvataggio PDF nel fascicolo, apertura e scroll di entrambe le pagine. Confronto del PDF con il precedente caso corretto: due pagine, testo e pixel uguali per entrambe. Non è prova di fedeltà di tutti i documenti.
- Secondo studio tecnico: accesso reale con le sue credenziali; catalogo comune visibile, modelli personali del primo studio assenti. Versione personale salvata tramite comando normale nello studio tecnico.
- Difetto trovato: la PEC assente ereditava SMTP_FROM generico. Corretto il contesto dell'editor usando soltanto configurazione e timbro del tenant corrente. Nel comando normale, dopo aggiornamento della copia Docker 8080, la PEC assente rimane esplicitamente da compilare.
- Dati controllati salvati dalle Impostazioni dello studio tecnico: nome studio, professionista, indirizzo, CAP, città e provincia. Compilazione normale li ha riportati in intestazione, domicilio e sottoscrizione. Bozza DOCX salvata e riaperta: documento 0A55E6C8 nel fascicolo tecnico 7FFD0C5D. PDF A52DAFBC salvato e aperto nel lettore reale; osservati intestazione e conclusione. Con i numerosi segnaposto mancanti il PDF ha tre pagine: questa prova non attesta impaginazione uguale al caso completo di due pagine.
- Guardrail: 53 test mirati repository modelli/campi/font/API dopo la correzione del contesto; nove test repository Editor AI/API modelli dopo correzione della lettura; due test payload editor reali; Ruff positivo. PostgreSQL nativo su sole tabelle temporanee: pubblicazione, replay e rollback ricevuta discordante già provati.

## Problemi e passi aperti

Il caricamento dopo creazione DOCX ha impiegato 37,7 secondi nella lettura dei dati editor. La lettura costruiva l'intero servizio AI, inizializzando schemi e componenti non necessari. Ora consulta direttamente il repository SQL esistente senza DDL né import JSON: test nativo con scrittore SQLite concorrente positivo. Candidato ricostruito e installato; riapertura materiale della stessa pagina alle 09:03: caricamento dati 360,6 ms, contenuto e stato «Nessuna modifica pendente» osservati. Un singolo riscontro non è un benchmark di tutto il prodotto.

Scheduler locale degradato per `legal_notification_relata_presidio`: alle 08:49 del 11/10 errore `database is locked`. Nessun reset dell'esito o disattivazione del controllo; lavorazione fonti e checkpoint preservati. Il successivo giro nativo delle 09:04 ha riportato il controllo e il container a healthy senza riavvio. Il recupero non dimostra quale scrittore avesse trattenuto il lock: l'episodio rimane registrato e non è dichiarato risolto strutturalmente.

Restano ripetizione finale nel primo studio, prova visiva delle pagine intermedie nel secondo, verifiche pertinenti dei permessi, aggiornamento/versione/commit/push dei due branch, riallineamento locale e pubblicazione puntuale del modello sul server con deploy healthy. Questo punto e l'incarico generale restano aperti. Nessuno spegnimento PC; scaricamento fonti solo locale.

## Riscontro aggiuntivo richiesto dall'utente: timbro in produzione

Browser reale del server: Impostazioni dello studio Giuseppe Montagnese e relativo codice fiscale corretti; pannello Timbro mostra Roberto Montagnese. Riscontro SQL in sola lettura: nessun profilo personalizzato nel database del tenant. Causa nel callback del pannello: leggeva `g.config_studio`, assente, e usava i default dell'installazione. Corretto usando il medesimo servizio tenant-aware dell'autocompilazione, con configurazione caricata dal gestore nativo e DSN/percorso dello studio. Nessuna sostituzione dell'identità nelle impostazioni, nessun cambio del flusso firma/deposito/PEC.

Accettazione locale dopo installazione puntuale e reload dei soli processi web: comando Timbro studio nel browser reale 8080, osservati Studio tecnico — prova modelli, Professionista di collaudo e Via del Collaudo, 12 - 00100 Roma (RM). Screenshot privato stamp-tenant-local.png. Due prove specifiche contesto/API e 30 guardrail modelli/creazione/editor positivi. La verifica del pannello corretto in produzione resta necessaria dopo deploy.

E2E nightly riprodotto: migrazione core positiva senza perdite, sincronizzazione repository fallisce su Agenda con KeyError tipo. Il JSON storico del fixture non ha tipo/stato/durata/luogo, ma le colonne SQL migratorie li conservano. Lettura corretta unendo soltanto i campi SQL persistenti assenti dal JSON, preservando la precedenza della fonte. E2E ripetuto positivo e 31 guardrail Agenda positivi. Il primo tentativo con venv incompleto e quello con temp fuori radici consentite non riproducevano il guasto CI; ripetizione nella directory temporanea ammessa ha dimostrato la causa. Versione candidata 2.437.5; deploy 2.437.4 annullati per includere il difetto segnalato. Gate/deploy/catalogo condiviso ancora aperti.
