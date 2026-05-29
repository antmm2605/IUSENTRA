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

## Aggiornamento reale 27 maggio 2026 - Local Signer 1.6.56

Verifica autorizzata eseguita su macchina locale con certificato dell'avvocato
abilitato, senza salvare PIN, cookie, sessioni ministeriali o XML grezzi.

Perimetro verificato:

- Tribunale di Palmi selezionato in UI come `0910011`, tradotto dal Local Signer
  verso il PST in `0800570094`;
- R.G. `1025/2024`;
- Local Signer `1.6.56`;
- ricerca snapshot PST riuscita: 1 fascicolo e 16 documenti nel catalogo;
- scarico batch fascicolo intero riuscito: 16 file ricevuti, 0 fallimenti;
- primo documento scaricato in prova singola/batch: `Documento_33584995.pdf`;
- primi tipi documento letti dal catalogo: `Documento`, `SentenzaDefinitiva`,
  `VerbaleUdienza`, `AttoNonCodificato`, `ProduzioneDocumentiRichiesti`.

Correzione certificata dal test: per i download documenti QBuilder il Local
Signer usa il certificato client diretto sul canale download e non invia i cookie
della ricerca; il lotto resta comunque un unico processo `curl`, con warm-up
tecnico nello stesso processo quando necessario, così non si torna al download
singolo ripetuto.

Verifica aggiuntiva dopo installazione del Local Signer `1.6.57`: diagnosi
locale OK, ricerca reale Palmi R.G. `1025/2024` OK, 16 documenti a catalogo,
scarico batch di un documento OK (`Documento_33584995.pdf`, contenuto base64
presente), 0 fallimenti. La differenza `1.6.57` rispetto a `1.6.56` riguarda il
foreground della finestra PIN Windows.

Limite dichiarato della verifica: questa prova live certifica il percorso reale
Palmi/SICID con certificato autorizzato. Le tabelle ministeriali degli altri
servizi sono presidiate da matrice di regressione su cataloghi/WSDL presenti in
repository; per una certificazione live di SIL, SIVG, MIN/SIMIN, SIECIC, SIGP,
Cassazione o richieste copie serve un fascicolo reale e un certificato
autorizzato per quello specifico registro.

Verifica aggiuntiva SIGP/Giudice di Pace dopo installazione del Local Signer
`1.6.58`: diagnosi locale OK, ricerca reale Giudice di Pace di Palmi R.G.
`466/2023` OK, 1 fascicolo, 34 documenti a catalogo. Il primo tentativo con
`1.6.57` trovava il catalogo ma il download andava in timeout; la prova diretta
ha confermato che il PST SIGP accetta `estraiProfiloDocumento`,
`estraiMasterDetailAtto` e `calcolaHash`, e che il `downloadAtto` riesce dopo
`calcolaHash`. Con `1.6.58` il download batch di `Atto_3080760.pdf` è riuscito
con 0 fallimenti e il download batch multiplo di `Atto_3080760.pdf` e
`Atto_3080731.pdf` è riuscito 2/2 con 0 fallimenti.

Verifica aggiuntiva dopo installazione del Local Signer `1.6.59`: diagnosi
locale OK, selezione certificato automatica da `/ping?auto=1&prefer_cf=...`
con `auto_selezionato=true`, ricerca reale Palmi/SICID R.G. `274/2026` inviata
senza `cert_thumbprint` manuale nel payload, 1 fascicolo e 6 documenti a
catalogo. Lo scarico batch degli stessi 6 documenti è riuscito 6/6 con 0
fallimenti, sempre riusando il certificato selezionato automaticamente dal
Local Signer. Questa verifica presidia la regressione lamentata dall'utente:
l'avvocato non deve riselezionare ogni volta il certificato quando sul PC esiste
già un certificato PST compatibile con il codice fiscale richiesto.

Verifica log live del 27 maggio 2026 su Palmi R.G. `3441/2025`, schema
ministeriale lavoro: il browser ha aperto l'acquisizione con ufficio `0910011`,
numero `3441`, anno `2025`, Local Signer `1.6.59` aggiornato e diagnostica
locale OK. Il PST ha restituito una SOAP Fault sul namespace civile
`CONS-SICC-BE`, quindi la correzione `1.6.60` rende obbligatoria la traduzione
automatica degli indizi espliciti `lavoro`, `LAV`, `SIL`, `SILP`, previdenza o
assistenza verso `JPW_SIL`/`LAV` prima di SICID. La regola vale anche quando la
tabella uffici locale non elenca ancora `JPW_SIL` tra i servizi Palmi, perché la
famiglia SICID consente il tentativo sullo stesso GL e con lo stesso certificato.
La stessa correzione non deve spostare genericamente le pratiche penali fuori da
PST: `penale` da solo resta neutro, mentre una tabella ministeriale esplicita
`CASSPE`, `JPW_CASSPE` o `cassazione penale` usa il canale PST/QBuilder di
Cassazione penale; `cassazione civile` usa `JPW_CASSCI`.

Aggiornamento live `1.6.62`: dopo la correzione `1.6.60`, Palmi/lavoro ha
risposto HTTP 404 su `/pda/pycons/GLRC/JPW_SIL`; il canale lavoro deve quindi
provare prima `JPW_SIL_DISTR`/`LAV`, mantenendo `JPW_SIL`, `JPW_SILP_DISTR` e
`JPW_SILP` come varianti immediate dello stesso rito prima del ritorno a SICID.
Nella stessa prova, un HTTP 401 durante il tentativo cookie-only deve scartare il
cookie PST e ritentare subito col certificato client, così Windows può riproporre
il PIN invece di riusare una sessione rifiutata.

Aggiornamento live `1.6.63`: la prova cliente successiva ha mostrato Local Signer
`1.6.62` correttamente installato, schema `lavoro` riconosciuto e autenticazione
non più bloccata, ma il PST ha restituito HTTP 404 sui path fisici `JPW_SIL*`,
`JPW_SIVG`, `JPW_MIN` e `JPW_SIMIN` sotto `GLRC`. Il registro uffici ministeriale
locale per Palmi espone `JPW_SICID` e `JPW_SIECIC`, non i path fisici delle
sotto-tabelle SICID-family. Da `1.6.63` la tabella resta logica nel SOAP
(`CONS-SIL-BE-DISTR`/`LAV` per lavoro), mentre l'endpoint HTTP usa il gateway
fisico `JPW_SICID` per la famiglia SICID. Il log del batch registra comunque
`servizio_logico`, così la diagnostica distingue il rito tentato dal path usato.

Prova cliente successiva con deploy diretto `1.6.63` / app `2.248.82`, ore
`20:39` del 27 maggio 2026: la ricerca Palmi `0910011`, PST `0800570094`, R.G.
`3441/2025`, schema `lavoro`, materia `lavoro`, registro `lavoro`, ha prodotto
`pst_search_success`, `1` fascicolo e `6` documenti. Il fascicolo restituito dal
PST è:

- numero `3441/2025`;
- procedimento `RITO LAVORO 1 GRADO`;
- oggetto `retribuzione`;
- stato `RISERVATO`;
- data iscrizione `2025-11-04`;
- registro portale `LAV`;
- tabella ministeriale `SICID_LAVORO`;
- servizio logico `JPW_SIL_DISTR`;
- `data_udienza` vuota.

Documenti esposti dal catalogo PST nella prova:

- `ProduzioneDocumentiRichiesti_34942889.pdf`, deposito `2026-04-28`, id
  `34942889`;
- `CostituzioneSemplice_34911163.pdf`, deposito `2026-04-24`, id `34911163`;
- `ProduzioneDocumentiRichiesti_34275720.pdf`, deposito `2026-03-04`, id
  `34275720`;
- `Documento_32916765.pdf`, deposito `2025-11-06`, id `32916765`;
- `FissazioneTermineNoteSostituzioneUdienza_32899061.pdf`, deposito
  `2025-11-05`, id `32899061`;
- `Ricorso_32883326.pdf`, deposito `2025-11-04`, id `32883326`.

Conclusione tecnica della prova: la ricerca fascicolo è corretta e il messaggio
`Il portale non espone una prossima udienza da tradurre in scadenziario` non è
un errore di ricerca. Il PST, in questo caso, non valorizza `data_udienza` nei
metadati del fascicolo. La prossima scadenza o il termine possono essere dentro
il PDF `FissazioneTermineNoteSostituzioneUdienza_32899061.pdf`, quindi il
completamento del flusso deve scaricare i documenti e, quando `data_udienza` è
vuota ma il catalogo contiene atti di fissazione termine, sostituzione udienza,
ordinanza, decreto o provvedimento analogo, proporre lettura/OCR del documento
per estrarre data, termine e fonte senza inventare una scadenza dai soli
metadati.

Aggiornamento app `2.248.83`: la regola è stata resa generale e visibile in UI.
La precedenza è vincolante: se il PST espone una data o una udienza strutturata,
IUSENTRA usa quella come fonte primaria per udienza/scadenziario; solo nei casi
in cui la data non viene esposta, l'anteprima e l'analisi cercano nel catalogo
documentale atti fonte come fissazione termine, sostituzione udienza, rinvio,
verbale, ordinanza, decreto o provvedimento con termini. Il documento fonte
viene mostrato nella sezione `Scadenziario` del wizard e negli avvisi di verifica;
la scadenza viene creata solo dopo lettura/scarico del documento e solo se data e
termine sono estratti con fonte verificabile.

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
