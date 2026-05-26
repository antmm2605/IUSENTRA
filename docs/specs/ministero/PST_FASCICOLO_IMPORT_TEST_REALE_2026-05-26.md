# PST/PolisWeb - Test reale scarico fascicolo e import

Data verifica: 26 maggio 2026.

Perimetro: acquisizione fascicolo PST/PolisWeb da IUSENTRA, con Local Signer sul
PC dell'avvocato, Tribunale di Palmi, R.G. 274/2026, import nel fascicolo
gestionale `B6A03AE6`.

Questa nota è parte della baseline operativa: ogni modifica futura a wizard PST,
Local Signer, anteprima, download batch o grafica dell'acquisizione deve
preservare i passaggi e il comportamento descritti qui, oppure registrare una
nuova verifica reale.

## Obiettivo utente

L'avvocato deve poter scaricare e importare il fascicolo senza passaggi tecnici:

- inserisce il PIN una sola volta quando la sessione PST è già aperta o
  riutilizzabile;
- non deve cercare la finestra PIN nella barra delle applicazioni di Windows;
- vede tutte le informazioni del fascicolo prima di importare;
- le parti visualizzate non devono essere tagliate: se il PST espone 12 righe e
  8 nominativi unici, la UI deve spiegare la differenza e mostrare comunque
  tutti i nominativi disponibili;
- vede tutti i documenti presenti nel fascicolo;
- vede una barra di avanzamento con il documento in scaricamento;
- importa nel fascicolo gestionale corretto, senza confondere id telematici e id
  dei fascicoli IUSENTRA;
- se un singolo PDF non viene consegnato dal PST, l'import dei file reali
  ricevuti resta valido e l'avvocato vede un avviso chiaro.

## Sequenza reale verificata

1. Apertura pagina React:
   `/portali/pst/acquisizione?ufficio=Tribunale%20di%20Palmi&ufficio_codice=0910011&numero=274&anno=2026&fascicolo_id=B6A03AE6&mode=update_existing`.

2. Verifica Local Signer dal browser:
   il browser usa il Local Signer locale sul PC, in test parallelo `1.6.50`.
   Il controllo leggero deve rispondere senza aprire dialog PIN e senza leggere
   inutilmente lo store certificati.

3. Ricerca PST:
   la chiamata principale è `/pst/ricerca-snapshot`.
   Il payload deve usare il codice ufficio ufficiale `0910011` e la traduzione
   PST interna solo nel Local Signer. La ricerca esatta R.G./anno non deve
   aggiungere assistito, controparte o codice fiscale come filtri restrittivi.

4. Certificato e PIN:
   se serve selezionare il certificato, il Local Signer usa la finestra nativa
   Windows. Quando Windows mostra il PIN/sicurezza smart card, il Local Signer
   prova a riportare la finestra in primo piano anche se il dialog ha titolo
   generico o resta sulla taskbar. Il software non salva PIN, credenziali o
   sessioni ministeriali nel cloud.

5. Anteprima fascicolo:
   dopo la ricerca, la pagina deve mostrare l'anteprima completa, non una vista
   ridotta. Devono essere visibili almeno:
   `Dati fascicolo`, ufficio, R.G./anno, oggetto/stato quando disponibili,
   parti, `Documenti nel fascicolo` e cronologia/eventi quando presenti.

6. Selezione documenti:
   la sezione `Selezione` deve elencare tutti i documenti del fascicolo, con
   stato chiaro `Selezionato` o `Escluso`. Non deve mostrare solo catalogo o
   informazioni tecniche.

7. Mappatura gestionale:
   in modalità `Aggiorna pratica esistente`, il valore selezionato deve essere
   l'id del fascicolo IUSENTRA (`practiceId`), non l'id della pratica telematica.
   Nel test reale il target corretto era `B6A03AE6`; il backend accetta anche un
   vecchio id telematico solo per risolverlo in sicurezza al fascicolo
   gestionale collegato.

8. Verifica prima dell'import:
   l'analisi non deve bloccare quando ci sono documenti reali scaricabili e un
   fascicolo gestionale target valido. I blocchi devono essere specifici:
   fascicolo mancante, documenti assenti, target incompatibile, autenticazione o
   timeout PST.

9. Download batch:
   l'import deve usare `/pst/download-documenti-batch`.
   Il flusso non deve tornare al download singolo ripetuto come flusso principale, perché
   quello può produrre richieste PIN ripetute e bloccare l'utente.

10. Avanzamento import:
    durante il download la UI deve mostrare:
    fase corrente, numero documenti completati/totale e nome del documento
    corrente. Questo stato deve restare leggibile su desktop, tablet e mobile.

11. Import finale:
    il backend riceve `downloaded_files` reali e completa
    `/api/portali/pst/acquisizione/import` con risposta `200`.
    Se il PST non consegna un singolo documento, la UI deve mostrare
    `Importazione completata con avvisi`, indicando il file non ricevuto, senza
    trasformare l'intero import in "non completato" quando altri file reali sono
    arrivati.

## Verifica anagrafiche e documenti

Controllo aggiuntivo del 26 maggio 2026 sul fascicolo gestionale `B6A03AE6`
dopo la prova reale Palmi R.G. 274/2026:

- il cliente principale deve restare collegato all'anagrafica clienti, con
  `id_cliente` valorizzato e nominativo visibile nel fascicolo;
- le parti devono essere presenti anche in anagrafica parti/soggetti, non solo
  come testo libero nel fascicolo. Se il PST non espone `parti` o
  `parti_dettaglio`, il gestionale crea comunque una parte `ASSISTITO` dal
  cliente collegato e una parte `CONTROPARTE` dalla controparte del fascicolo;
- i documenti scaricati devono restare collegati ai depositi ufficiali PST senza
  duplicare gli ID interni e senza perdere `tipo_atto`, classificazione portale,
  identificativo documento ministeriale, data deposito e mittente;
- l'acquisizione PST deve restare registrata come fonte del fascicolo: nella UI
  del fascicolo devono comparire almeno ufficio, R.G., stato, oggetto, conteggi
  di parti/documenti/depositi/eventi e riferimento al log di import;
- la visualizzazione del fascicolo deve quindi mostrare la classificazione
  corretta, ad esempio `Citazione`, `Decreto` e `AttoNonCodificato`, invece di
  una categoria generica quando il dato portale è disponibile.

Formula di regressione: dopo l'import PST completo o parziale con file reali, il
fascicolo deve popolare clienti, parti e documenti/depositi come dati strutturati
del gestionale; non è sufficiente salvare solo i PDF nel fascicolo.

## Cronologia e riprova

Il pannello `Cronologia - Import, esiti e azioni recenti` deve riportare anche i
tentativi non conclusi, non solo gli import riusciti. Se il fascicolo non viene
scaricato o il PST non consegna file reali, la riga deve indicare un motivo
operativo comprensibile, ad esempio timeout/sovraffollamento del portale,
certificato o PIN non accettato, sessione scaduta, nessun fascicolo trovato o
catalogo senza PDF effettivi.

La stessa informazione deve essere visibile anche nel riepilogo laterale del
wizard quando l'avvocato è dentro `/portali/pst/acquisizione`, con azione
`Riprova`. Il link di riprova deve riaprire la pagina già compilata almeno con
ufficio giudiziario, codice ufficio, numero, anno e fascicolo gestionale target
quando presente. Non devono essere salvati PIN, credenziali, sessioni o dati
sensibili del certificato nella cronologia locale del browser.

Formula di regressione: un errore recuperabile dello scarico PST deve diventare
un tentativo cliccabile e precompilato, non un messaggio effimero che sparisce al
refresh della pagina.

## Regole grafiche della pagina

La pagina è un flusso operativo per avvocati, non una pagina tecnica.

- Il primo schermo deve comunicare subito canale, stato Local Signer e passo
  corrente.
- La barra degli step deve restare visibile e comprensibile:
  `Accesso`, `Ricerca`, `Anteprima`, `Selezione`, `Mappatura`, `Verifica`,
  `Importa`.
- L'anteprima deve usare pannelli compatti e densi, con icone coerenti, senza
  spazi morti e senza testi tecnici come `backend`, `frontend`, `payload`,
  `runtime`, `json_api`, `legacy`, `undefined`, `null`, `demo` o `sample`.
- I documenti devono essere leggibili come elenco operativo: nome, tipo, data,
  deposito/id quando disponibili e stato di selezione.
- La mappatura deve evidenziare il fascicolo gestionale scelto e non deve
  confondere l'avvocato con identificativi interni.
- Gli stati devono essere espliciti:
  caricamento, anteprima pronta, verifica completata, scaricamento in corso,
  import completato, import completato con avvisi, errore recuperabile.
- Gli errori devono indicare l'azione utile: riprovare, riselezionare
  certificato, controllare PIN, verificare abilitazione del certificato o
  consultare il portale ufficiale.
- La pagina deve restare responsive: nessun overflow orizzontale, bottoni
  leggibili, progress bar e nomi documenti senza sovrapposizioni.

## Regola multi-studio

Se IUSENTRA è aperto su uno studio diverso da quello usato in un test
precedente, lo scarico PST deve dipendere dal certificato realmente selezionato
sul PC e dalla sua abilitazione ministeriale, non dal codice fiscale salvato nel
tenant corrente.

Il codice fiscale configurato nello studio è solo fallback. Quando il certificato
espone il codice fiscale dell'avvocato, quel valore prevale nelle chiamate PST e
negli header richiesti dal servizio.

Formula di regressione: il codice fiscale ricavato dal certificato selezionato prevale sul codice fiscale configurato nello studio.

Se un certificato non è abilitato al fascicolo, il software deve mostrare un
errore di autenticazione/abilitazione professionale, non "nessun fascicolo" e
non "importazione senza file reali".

## Regressioni vietate

- Non reintrodurre `/pst/preflight-auth` come chiamata preventiva dal wizard
  React o classico.
- Non reintrodurre il download singolo ripetuto per importare il fascicolo.
- Non usare il codice fiscale del tenant come valore prioritario quando il
  certificato selezionato espone un CF diverso.
- Non mostrare solo catalogo o informazioni al posto dei documenti reali.
- Non dichiarare fallita tutta l'importazione quando sono arrivati file reali e
  resta solo un documento non consegnato dal PST.
- Non lasciare la finestra PIN nascosta sulla taskbar quando è riconoscibile dal
  sistema Windows.
- Non salvare PIN, credenziali CNS/CIE/SPID o sessioni portale nel cloud.
