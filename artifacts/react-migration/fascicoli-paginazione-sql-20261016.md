# Elenco fascicoli: paginazione SQL — candidata 2.437.51

Stato: aperto. Commit, CI, riallineamento finale e rilascio non ancora eseguiti.

## Risultato richiesto

Il comando elenco deve selezionare in SQL solo la pagina richiesta (25 elementi iniziali), mantenendo ricerca, filtri, raggruppamenti, ordinamenti e conteggi riferiti all'intero archivio autorizzato. Nessuna preparazione delle altre pagine, documenti o OCR durante la GET.

## Procedura primaria

Catalogo derivato nel database proprietario, preparazione esplicita a lotti con backup verificati di core e registro; identità e scadenze indicizzate mediante regole native. Outbox condivisa e scrittori puntuali aggiornano solo i record dipendenti. Cambio giorno limitato ai termini indicizzati interessati, con cursore e CAS. SQLite e PostgreSQL conservano gli stessi contratti. Pagina e aggregazioni usano un'istantanea consultiva coerente; catalogo non confermato produce un errore esplicito.

Il client richiede la sola pagina scelta, senza prefetch su apertura, hover o focus e senza anticipare la vista economica. Cache per query e deduplicazione delle richieste restano locali alla vista. Gli errori non diventano archivi vuoti. Il raggruppamento partecipa alla query.

## Prove eseguite

- 36 casi nativi del catalogo, scrittori, migrazione e preparazione positivi su SQLite e PostgreSQL; inclusi filtri confrontati con regole originali, lock fra due connessioni, registri condivisi fra tenant, cambio giorno, eventi ripetuti, archivio vuoto e fonte SQL modificata.
- Guardie API per autenticazione, tenant, accesso fra studi e parametri forzati positive sul provider primario.
- 24 casi JavaScript per caricamento e coda condivisa positivi dopo il collegamento live; typecheck, ordine hook e contratti React positivi. Primo typecheck del collegamento live ha rilevato due handler con parametro evento incompatibile: corrette le due invocazioni esplicite.
- Preparazione locale reale di tre studi terminata con backup coerenti verificati; le fonti aziendali erano invariate prima/dopo la preparazione. Nessuna lettura documentale massiva.
- Confronto consultivo di cinque selezioni locali con il costruttore precedente: nessuna differenza nei campi, normalizzando esclusivamente l'ordine dei termini aventi la stessa data.
- Browser reale inizialmente visibile sulla 8080: 23 pratiche locali, pagina da 5, seconda e ultima pagina (tre righe), ricerca di un cliente fuori dalla pagina corrente e ricerca senza risultati; raggruppamento Stato e vista economica aperti. Mobile 375×812 (area utile 360) con cambio pagina e tablet 820×1180 (area utile 805); scorrimento osservato e viewport ripristinato.
- Richieste locali dell'elenco: 195,3–288,2 ms. Non è un confronto omogeneo con la produzione, che contiene 307 pratiche e prima della modifica aveva due richieste da 8823,1 e 8416,6 ms.

## Difetto emerso durante il collaudo

Il salvataggio normale del titolo di una pratica sintetica aggiorna correttamente il catalogo e la ricerca. L'elenco aperto non risultava però sottoscritto alla regia condivisa. Aggiunta la sottoscrizione del solo dominio fascicoli; una bozza economica aperta impedisce la sostituzione e lascia una segnalazione esplicita, con ripresa tramite la coda esistente quando la bozza viene salvata o chiusa. Risposte invalidate non devono ripopolare la cache e una risposta destinata a un filtro superato non deve sostituire la pagina corrente. Il titolo sintetico originale è stato ripristinato tramite la UI; riscontro SQL consultivo positivo.

17/10: ripetizione con Browser visibility=true e nuova immagine immutabile, 10033 impronte senza differenze. Salvataggio normale nella seconda finestra: titolo aggiornato automaticamente nell'elenco senza reload. Bozza economica sintetica non salvata: testo e focus conservati, avviso esplicito di aggiornamento in attesa; chiusura della bozza riattiva la coda e riceve il titolo originale ripristinato. Risposte503 durante consegna SQL pendente recuperate automaticamente dopo la conferma; nessun elenco vuoto. Il vecchio tentativo senza visibilità resta diagnostico.

## Pulizia e conservazione

Prima della nuova immagine: margine Windows C: 21,59 GB, D: 309,35 GB; motore Docker oltre 1002 GB liberi. Pulizia governata locale: immagini contabilizzate 29,65→19,64 GB; tre riferimenti obsoleti rimossi, cache rimossa 6,037 GB. Restano 1,193 GB di record BuildKit in uso e non reclamabili; non si dichiara cache zero. Dieci volumi conservati, applicazione/scheduler/OCR sani. Sorgenti divergenti delle immagini 48/49 recuperati e verificati fuori da Docker prima della rimozione. Immagine accettata 50 conservata per ripristino. Queste cifre sono contabilità Docker, non spazio fisico restituito a Windows.

Restano prova live/bozze/errori dell'ultima immagine, CI completa sul commit, verifica produzione sul medesimo archivio di 307 pratiche, server unico iusentra-app healthy sullo stesso SHA, pulizia finale verificata. Addestramento, fonti, checkpoint, volumi e flussi deposito/firma/PEC congelati non modificati.

Ulteriore riscontro prestazionale: una richiesta economica su23righe durante la prova concorrente ha impiegato5419,3ms; non si dichiara velocità globale. Nel registro scheduler un aggiornamento della firma pianificata ha incontrato database is locked alle00:10:05; la successiva esecuzione nativa alle00:11:02 è riuscita. Il percorso usa il database distinto del registro pianificazioni: resta censito nella diagnosi database/prestazioni globale, senza modificarne i criteri o occultare il fallimento. Per l'elenco operativo restano richieste normalmente inferiori a300ms; produzione307 ancora da confrontare. La prima invocazione di ricreazione usava nomi servizio non esistenti e non ha applicato cambiamenti; corretta sui servizi nativi app/scheduler-worker/ocr-worker, tutti healthy. Pulizia dopo questa immagine:1,986GBcache rimossi;14record in uso1,193GBrestano non reclamabili.

## Correzione dopo il primo push

Il commit992abdd7ef è stato fermato dal gate API provider: il banco nuovo non preparava il catalogo e il registro assente sollevava FileNotFoundError. Correzione primaria:503 con codice esplicito, nessuna creazione dalla GET; preparazione nativa del catalogo sintetico nel banco. Guardia assenza/errore/preparazione/recupero positiva. Rigenerati riferimenti di riga OpenAPI. Sette prove native preparazione/contratti positive su snapshot Git con sole modifiche correnti, senza dati runtime o node_modules Windows; la ripetizione sulla root era stata interrotta per scansione preesistente dei template nel data_root globale, individuata con faulthandler. Questa scansione resta censita nel lavoro prestazioni/editor e non è introdotta dalla paginazione. Ultima immagine correttiva: sorgenti modificati confrontati, tre servizi sani, normale pagina2/5 provata su8080 con Browser visibile. Nuovo push/CI e produzione ancora da verificare.

## Precisione della guardia client

Il controllo di sottoscrizione ora estrae con il parser gia installato l'AST della sola funzione FascicoliListPage; il precedente delimitatore testuale non esistente comprendeva anche l'archivio. Caso negativo dedicato dimostra che una sottoscrizione soltanto nell'archivio non certifica l'elenco. Venticinque casi Node positivi dopo l'adeguamento al parser TypeScript6 gia presente; TypeScript7 non espone la vecchia API ScriptTarget e il primo tentativo e registrato come errore del banco. Nessuna dipendenza nuova e nessuna modifica del comportamento runtime. Nuova CI completa prima del deploy.
