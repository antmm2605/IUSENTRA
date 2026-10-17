# Consultazione mirata del catalogo modelli — 17 ottobre 2026

Il catalogo React deve leggere i modelli distribuiti e quelli del solo studio
autorizzato. Non deve cercare file runtime di tutti gli studi né riscrivere
modelli, schema o indici durante una consultazione.

I modelli completi sono conservati nel repository SQL nativo, nello snapshot
`template_runtime_state`. HTML, campi, date e metadati aggiuntivi rimangono
distinti dalla proiezione normalizzata. I modelli personali dell'editor e le
relative risorse continuano a essere preservati dal blocco nativo del repository.

`tools.prepare_template_catalog` usa il registro e i percorsi proprietari senza
avviare il runtime web. La prima adozione richiede scrittori fermi e backup
verificato del database esistente e del JSON storico. Il deploy controlla prima
gli studi; soltanto se necessario arresta app e worker e prepara i cataloghi
prima di attivare la candidata. Errori e snapshot discordanti fermano il passaggio.
Il riscontro della revisione proiettata impedisce di confondere uno snapshot
salvato con una preparazione terminata.

La creazione prepara il catalogo locale del nuovo studio. L'attivazione del
backend PostgreSQL prepara il catalogo dopo la connessione verificata. Le
scritture confrontano la revisione letta con quella SQL corrente: una versione
obsoleta non sostituisce né il modello né l'indice più recente.

Le prove sono registrate nelle fasi core e coverage-critical, con SQLite e
PostgreSQL controllati. Comprendono backup e ripresa, dati non validi,
formattazione, metadati, isolamento, sola lettura e concorrenza. Questo intervento
non dimostra velocità globale dell'applicativo: il perimetro è il catalogo React
e la lettura dei modelli. L'inventario amministrativo esplicito rimane distinto.

Il browser reale è tornato disponibile. La versione 2.437.53 è stata osservata su 8080: intestazione unica, campi separati, ricerca ingiuntivo e assenza dei pannelli descrittivi rimossi. La prova non certifica tutte le superfici del prodotto.


## Card operative e ricerca clienti — candidata 2.437.54

Le card del catalogo contano e filtrano la medesima lista autorizzata. La ricerca,
Categoria, Canale, Stato Cartabia e Dati si combinano prima del conteggio. I filtri
sono Tutti, Catalogo, Studio, Precompilabili e Da verificare; anche lo zero è
selezionabile e non lascia una scheda precedente come risultato corrente.
L'elenco rende 24 schede alla volta, senza limitare la ricerca ai soli modelli
visibili. La pagina viene riportata alla prima quando cambia un filtro. Il link
`/template-atti/catalogo?scope=studio` apre il perimetro mostrato nella card della
Redazione. Gli errori e gli scostamenti reali restano espliciti.

La scelta cliente usa l'endpoint esistente
`GET /api/v1/ui/redazione-atti/clienti?q=...`: query vuota o di un solo carattere
restituisce una lista vuota senza consultare gli archivi. Con almeno due caratteri
si consulta la connessione SQL già risolta per lo studio autenticato, con parametri
vincolati, caratteri LIKE letterali, ordinamento deterministico e LIMIT 21; la
risposta contiene al massimo 20 clienti e `altriRisultati` quando occorre affinare
la ricerca. Nomi e cognomi possono essere cercati in entrambi gli ordini, così
come denominazione, codice fiscale e partita IVA. I conteggi considerano i soli
fascicoli non archiviati dei clienti trovati. Non vengono costruiti i gestori che
caricano tutte le anagrafiche e tutti i fascicoli. Nessuna scrittura o associazione
viene eseguita durante la ricerca: la scelta del cliente resta esplicita.

L'interfaccia attende una breve pausa nella digitazione, interrompe la richiesta
precedente e ignora le risposte superate. Conserva il campo di ricerca durante
caricamento ed errore e offre un nuovo tentativo esplicito, senza cicli di retry.
Sono mantenuti autenticazione, tenant e redazione successiva; firma, deposito e
invio PEC restano congelati e non sono modificati da questo intervento.
