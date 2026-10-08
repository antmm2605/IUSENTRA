# Recupero e verifica integrale del lavoro, 07/10/2026

Stato: **APERTO**. La conservazione dei sorgenti e l'allineamento Git non sono
accettazione del funzionamento. La campagna materiale resta da eseguire
personalmente sulle copie reali, senza demandarla all'utente.

## Conservazione verificata

- Backup locale esterno: `D:/legale/backups/IUSENTRA/recovery-20261007-versions`.
  Bundle dell'intera cronologia, patch binaria, archivio dei file modificati e
  non versionati, elenchi dello stato originale e originali dei conflitti.
- Backup server esterno: `/opt/iusentra/recovery-20261007-versions`.
  Bundle Git, sorgenti della checkout, sorgenti e asset del container attivo,
  copia separata di Lex. Permessi directory 0700 e archivi 0600.
- SHA-256 archivio runtime iniziale:
  `0ba65fac42bd9220f49de4996e66561f946557c02e3199922ba978de6e692018`.
- SHA-256 archivio checkout server:
  `0c472c00c86308a6077aaf4282a8153e930596f19e88d328a99c2cf55082563b`.
- SHA-256 bundle server:
  `f02ab5f2cf48a8f63620fbe9d811b6e0cb863466386a30a36b79b4243f964f88`.
- SHA-256 archivio runtime Lex:
  `1ff489c781d8e6ea6ea80ea1946bb0a22c6ad9d1e3b18dc7cecc1aadcd2f029f`.
- Fetch limitato ai due branch ammessi. Entrambi i branch remoti e locali,
  HEAD locale e checkout server: `97959fa8371e23642ea3f73e167c44176a2b0aa0`.
- Integrazione dei quattro conflitti: Dockerfile, report dei test superati,
  report dei problemi aperti, contratti React. Conservati entrambi i contributi,
  validata la sintassi Python. Nessun reset, clean o cancellazione di dati.
- Confronto con l'archivio originale: **293 file identici**, quattro integrazioni
  intenzionali, nessuna differenza imprevista. Il lavoro locale OCR/Word resta
  intenzionalmente non versionato fino alla verifica.
- Il controllo dei sorgenti modificati nel container ha superato il confronto
  con la release candidata. Un successivo confronto completo ha distinto le
  differenze LF/CRLF da quelle sostanziali: non equivale a perdita di codice.
  Alcune differenze sono refactoring e aggiornamenti già acquisiti su GitHub.
- Durante il controllo il server è stato distribuito alla versione 2.436.11:
  `/api/pronto` HTTP 200 e unico container `iusentra-app` healthy.
  Questo deploy osservato non costituisce prova visiva di tutte le modifiche.

## Difetti già accertati nella superficie reale

### Campagna reale su Controllo Studio e topbar, 07/10/2026

- Card Notifiche: click effettivo filtra 28 presidi e mostra «Termine da
  determinare» distinto dalla data della fonte in formato italiano. Non sono
  state inventate scadenze né modificati i flussi di notifica/firma/PEC.
- Verifiche documentali Alessi: aprendo il riepilogo appare «Già letta · presa
  visione memorizzata per il tuo utente», pulsante Già letta disabilitato.
  Il dato discordante resta consultabile; non è stato eliminato o corretto
  senza confronto con la fonte.
- Comunicazioni: selezione reale di due comunicazioni storiche (Mancato deposito
  e Registrazione Deposito per RGN 593/2024), comando batch, messaggio di
  successo, conteggio 772→770, selezione azzerata ed elenco aggiornato senza
  premere Aggiorna. Dopo reload conteggio 770 persistente. La prova ha registrato
  soltanto la lettura, senza inviare messaggi o modificare documenti.
- Scadenze rapide: card «6 scadute · 5 da leggere» apre pannello con ricerca,
  filtro Lettura e checkbox; Seleziona tutte seleziona tutte le cinque voci.
  Comando reale «Segna lette le selezionate (5)» mostra presa visione salvata,
  6 scadute · 0 da leggere, lista Da leggere vuota e aggiornamento della card
  sottostante. Gli adempimenti rimangono aperti. Prova visiva esterna
  `D:/legale/backups/IUSENTRA/recovery-20261007-versions/bulk-read-deadlines-real.jpg`.

Queste osservazioni confermano solo i casi provati in produzione; non
sostituiscono la campagna completa e l'accettazione finale locale su 8080.

### Campagna reale Agenda, 07/10/2026

- Apertura Calendario dal menu: card Oggi/Periodo/Udienze/Scadenze/Alert
  compatte su una riga. Click Udienze riduce gli elementi da 16 a 9 e mostra
  selected/pressed e «9 attività trovate».
- Scroll materiale dentro la settimana dagli orari 08:00–10:00 a 13:00–15:00:
  intestazioni lunedì 5–domenica 11 ottobre restano visibili, separate dalla
  griglia oraria che scorre.
- Click sull'udienza Santocono 08/10/2026 14:00 apre Dettaglio operativo nella
  stessa pagina con dati, fonte, attività e comandi di finestra. Nessun invio,
  variazione di udienza o completamento di adempimento eseguito.
- Click sulla fonte ZIP PEC 19024903s.pdf.zip apre seconda finestra interna;
  il PDF dell'ordinanza del Tribunale di Vicenza è visibile, con parte ricorrente,
  rito e provvedimento; agenda e dettaglio restano nel contesto sottostante.
- Riapertura Scadenze scadute dopo batch: persiste 6 scadute · 0 da leggere,
  lista Da leggere vuota. La verifica riguarda lettura, non assolvimento.

### Recupero materiale del lettore in produzione, 07/10/2026

Sul documento originale `DFE17CA0` del fascicolo `58B00837`, con apertura reale
dalla lista fascicoli, è stata attivata la modalità compatta condivisa tramite
il valore predefinito di ViewerDocumentEditor. Intestazione interna da circa
102 px a 41 px; titolo interno non duplicato e toolbar sulla stessa riga.
Provati click zoom + (125%) e − (100%), chiusura/riapertura dei comandi,
scroll fino al fondo e firma in calce. Il PDF originale non è stato modificato.

La segnalazione successiva delle icone decentrate è stata riprodotta:
lo stile della pagina fascicoli imponeva display flex senza justify-content,
con tutte le icone spostate di 10 px a sinistra. Correzione in ManagedWindows.css
con centraggio condiviso indipendente dalla pagina ospitante: misurati dx=0,
dy=0 per affiancamento, minimizzazione, ingrandimento e chiusura. Download
sulla riga del titolo; barra di modifica subito sotto. L'avviso di protezione
e il pulsante Modifica testo disabilitato restano visibili.
Provati materialmente metà destra, ingrandimento, focus Tab, riduzione a icona,
richiamo dal dock e ripristino. Screenshot reale conservato esternamente:
`D:/legale/backups/IUSENTRA/recovery-20261007-versions/reader-alignment-real.jpg`.

Distribuzione server provvisoria dei soli sorgenti/asset, senza dati/volumi:
static-assets usa immagine reader-alignment-20261007 con profilo read-only;
app unica iusentra-app, readiness 2.436.11 HTTP 200. Build tecnica candidata
superata (2582 moduli, Vite 2,21 s). Codice identico riportato nella checkout
locale, ma **non verificato sulla copia Docker reale locale 8080**. Consolidamento
Git, deploy ordinato, verifica mobile/tablet e campagna complessiva ancora aperti.

1. Produzione, documento `DFE17CA0` del fascicolo `58B00837`: nell'apertura diretta
   dal fascicolo manca la modalità compatta. Il titolo interno è duplicato,
   “Chiudi comandi” occupa una riga diversa dal resto della toolbar. Nel browser
   reale il foglio di stile compatto era assente; intestazione interna alta
   circa 102 px. Il codice compatto esiste in SourceDocumentModal, ma il
   visualizzatore usato direttamente da Fascicoli non passa `compactReader` e
   ViewerDocumentEditor usa false come valore predefinito. Non è dimostrata una
   cancellazione della precedente correzione: è accertata una divergenza fra
   due punti d'ingresso equivalenti.
2. Conversione del file realmente aperto dall'utente
   `VistoAttoGenerico_265633306.pdf`: il salvataggio materiale è stato rifiutato
   perché la resa Word genera tre pagine rispetto alle due originali.
   Una grande tabella falsa viene inferita nel corpo dell'atto; i tentativi
   privati di correzione non hanno prodotto una resa accettabile e non sono
   stati integrati nel prodotto. Il problema resta aperto.
3. La rotazione dei testi verticali è stata corretta nella copia locale più
   recente; la scheda originale dell'utente caricava ancora il precedente
   bundle. La nuova resa è stata osservata su una seconda scheda dello stesso
   documento reale, ma il flusso finale sulla scheda originale resta aperto.

## Registro integrale di accettazione

Ogni riga deve ricevere prove materiali su produzione e sulla Docker reale
locale 8080. Non marcare una riga superata in base alla presenza del codice.
Per ogni superficie: azione, risultati e conteggi, persistenza/riapertura,
loading/errore, scroll completo, hover/focus, desktop/tablet/mobile.

| Perimetro richiesto | Risultato da verificare | Stato |
| --- | --- | --- |
| Verifiche documentali | Presa visione persistente per utente/revisione; discordanza consultabile senza riproposizione indebita | Da verificare materialmente |
| Controllo Studio, tutte le card | Conteggio e filtro con stesso perimetro; ricerca e azzeramento; card compatte | Da verificare materialmente |
| Comunicazioni | Selezione singola/tutte le corrispondenze; lettura massiva persistente e aggiornamento automatico | Da verificare materialmente |
| Notifiche senza termine | Motivazione reale, fonte e azioni; nessun dato temporale inventato | Da verificare materialmente |
| Scadenze rapide | Card scadute e altre operative; selezione e lettura senza completare termini legali | Da verificare materialmente |
| Agenda e calendario | Giorni visibili durante scroll; card filtro compatte; casi e priorità evidenti | Da verificare materialmente |
| Apri in agenda / prepara udienza | Contesto conservato e dettaglio nello stesso spazio; ingrandimento | Da verificare materialmente |
| Navigazione preparazione udienza | Voce dentro Fascicoli; percorso operativo raggiungibile | Da verificare materialmente |
| Finestre condivise | Trascinamento anche inattive; minimizza, ripristina, ingrandisci, X senza testo ridondante | Da verificare materialmente |
| Ridimensionamento / affiancamento | Bordi e angoli; metà/quadranti; ripristino dimensioni; tastiera e viewport | Da verificare materialmente |
| Barra finestre | Richiamo e scelta posizionamento manuale/automatico per finestre aperte | Da verificare materialmente |
| Header finestre | Titolo e comandi nella stessa riga; nessun comando invisibile o coperto | Da verificare materialmente |
| Lettore unico | Stessa logica da fascicolo, agenda, scadenze, PEC/email e notifiche; formati coinvolti | Difetto accertato nell'apertura diretta dal fascicolo |
| Toolbar documenti | −, percentuale, +, Adatta, rotazione, Scarica, Altro; compatta e accessibile | Difetto accertato nell'apertura diretta dal fascicolo |
| Incassi e pagamenti | Filtri combinabili, conteggi coerenti e caricamento reattivo | Da verificare materialmente |
| Clienti, soggetti e fascicoli | Card operative e compatte, contesti simultanei e filtri reali | Da verificare materialmente |
| Cartelle condivise | Pulsanti coerenti con il resto dell'applicativo, hover/focus leggibili | Da verificare materialmente |
| Statistiche / altre superfici | Card operative, allineamenti e spazio per il contenuto | Da verificare materialmente |
| Strumenti forensi | Card categorie compatte e filtro; strumenti realmente utilizzabili | Da verificare materialmente |
| Richiamo strumenti nel fascicolo | Icona contestuale e finestra operativa senza perdere il caso | Da verificare materialmente |
| Strumenti PDF | Unione, ZIP, acquisizione, divisione e conversione Word con esito osservabile | Conversione del documento utente fallita |
| OCR condiviso | Fascicolo e strumenti usano medesimi componenti/logica; scroll, scala e pagine allineati | Verifica integrale aperta |
| Fedeltà Word | Font/stili, punteggiatura, simboli, elenchi, tabelle, caselle, immagini, margini e tutte le pagine | Documento utente non accettato |
| Font | Catalogo utilizzabile nei contesti previsti, font incorporati governati e diritti rispettati | Aperto |
| Dati locali | SQL fonte primaria; caselle e fascicoli leggibili, stati e persistenza coerenti | Prove precedenti documentate, verifica post-riallineamento aperta |
| Aggiornamento automatico | Tutte le scritture coinvolte aggiornano viste, conteggi e finestre; niente falso successo | Campagna trasversale aperta |
| Performance | Caricamento e cambio pagina confrontati con baseline, senza regressioni silenziose | Campagna trasversale aperta |
| Regole agentiche | Dettagli, logica intuitiva, verifica personale e prove visive applicate anche all'esistente | Registrate; applicazione integrale aperta |
| Release finale | Codice verificato su GitHub, branch gemelli, copie reali healthy sul medesimo commit | Allineamento Git eseguito; WIP locale e accettazione aperti |

Preservare integralmente la baseline congelata di firma/deposito/PEC. Il recupero
grafico non autorizza modifiche a quel comportamento o agli originali dello studio.

## Prove materiali aggiuntive del 07/10/2026, ore 16:00–17:00

Stato complessivo: **APERTO**. Le prove sotto sono sul browser reale della macchina dell’utente in produzione; le nuove correzioni non sono ancora accettate sulla copia Docker 8080.

- Lettore del documento DFE17CA0 nel fascicolo 58B00837: icone finestra centrate, download nella riga titolo, azioni documento immediatamente sotto; affiancamento destro, ingrandimento, minimizzazione/richiamo, chiusura, zoom e scroll provati materialmente. Fonte e avviso di protezione conservati. Sorgenti ScadenziarioPage/ManagedWindows/ViewerDocumentEditor preservati prima delle modifiche.
- Comunicazioni: segnate lette due comunicazioni storiche selezionate, risultato persistente dopo ricaricamento, conteggio 772→770 e lista aggiornata automaticamente. Nessun invio.
- Scadenze rapide: presa visione di cinque scadenze selezionate persistente; sei scadute restano sei, da leggere 5→0. Nessuna scadenza completata.
- Agenda: giorni visibili durante scroll interno; filtro Udienze osservato, dettaglio Santocono e PDF utile dentro lo ZIP aperti nello stesso contesto.
- Incassi/pagamenti: ricerca Piccolo Lucia, selezione card Scaduto, stato vuoto e scroll finale osservati; nessuna registrazione economica.
- PEC ricevute oggi: eventi 10:46 Grosso e 11:35 Giffi presenti nel gruppo di tre attività del 07/10; termine Grosso del 21/10/2026 ore 14:00 presente in Agenda e Scadenziario (503d055e-8541-4290-b315-9af50522b2c1). Non è dimostrata una perdita della sincronizzazione automatica su questi due messaggi.
- Problema reale distinto: Giffi Vicenza RG806/2026 è collegata nel dato persistente al fascicolo Foti Palmi con lo stesso RG; Giffi 8132E1C0 non ha RG compilato. Due bozze RG806/2026 (04/01 e 07/04/2027) richiedono diagnosi fonti e correlazione; non confermate né scartate.
- Proposte Scadenziario: corretto l’anchor diretto che usciva sul download ZIP. Riutilizzato SourceEvidenceLink e SourceDocumentModal esistenti, incluse alternative di fonte quando ambigue.
- Seconda causa: i profili PEC venivano caricati solo per le righe filtrate, mentre le bozze restavano fuori; una ricerca su Grosso prima mostrava accidentalmente fonti disponibili anche nelle proposte, la vista Aperte invece no. Caricate le bozze insieme alle righe visibili, senza promuoverle operative né cambiare calcoli legali.
- Prova reale: proposta RG505/2024, fonte pec_a864f62b158dddff33a0585d, allegato 31601501s.pdf.zip; click mostra sentenza della Corte d’Appello di Reggio Calabria, parte Plataroti Fabiana, nel lettore interno sopra lo Scadenziario. Scroll fino alla conclusione e firma dei giudici, chiusura e riapertura provate. Screenshot proposal-source-reader-real.jpg conservato fuori Git.
- Guardrail mirati: build frontend candidato con typecheck e Vite 2,27s; pytest test_scadenziario_draft_source_loading + test_pec_source_context_selection, 11 superati. Copia locale sorgente preservata separatamente e modifiche applicate senza sostituire WIP preesistente.
- Hotfix produzione temporaneo: immagine static-assets proposal-reader-20261007, app unica iusentra-app; sorgente bridge aggiornato e container app riavviato per caricare il modulo. Readiness 2.436.11 positiva. Commit/push gemelli, deploy ordinato finale e prova 8080 ancora aperti.
- Nuova richiesta: lettura automatica del documento ufficiale, estrazione del passaggio giustificativo, decorrenza e tipo provvedimento. Recupero fonte corretto e materialmente provato; affidabilità semantica di tutte le proposte non ancora verificata, nessuna conferma automatica indiscriminata effettuata.
# Controllo identità PEC — 07/10/2026, 17:14 (Europe/Rome)

Lavoro ancora aperto. Sul server è stato individuato un collegamento errato reale: la PEC Giffi, R.G. 806/2026 del Tribunale di Vicenza, era collegata al fascicolo Foti del Tribunale di Palmi con lo stesso numero di ruolo. Il ramo XML certificato assegnava 0,82 al solo R.G., senza controllare l'ufficio.

Hotfix server-first in `pct/pec_pipeline.py` e nuovo helper `pct/pec_case_identity.py`: confronto ufficio, nome/cognome delle parti con ordine normalizzato, R.G. e anno esatti, CF cliente quando presente nel profilo della fonte e nell'anagrafica SQL; esclusione dei conflitti e blocco dei candidati equivalenti. Il CF del destinatario PEC non viene utilizzato come CF del cliente. Il ramo delle ricevute di deposito con identificativi certificati resta precedente e invariato. La pipeline e il helper sono stati portati nell'app e nei due worker; container healthy e readiness pubblica positiva, versione 2.436.11. Immagini pulite senza rimozione di volumi o dati.

Correzione sul dato primario `source_of_truth=sqlite`, usando GestioneFascicoli, GestioneScadenziario, Agenda e audit PEC: ripristinato R.G. 806/2026 nel fascicolo Giffi 8132E1C0, collegata la PEC al fascicolo e al cliente 04C49326, riallineata la proposta adfde3f5-337d-47ff-bef4-56c6a1a3dda8 e la voce Agenda 8CC51890. Audit `pec.case_identity.repair_started` / `repair_completed` conserva prima/dopo ed evidenza con hash ZIP. Stato BOZZA, data proposta e data/ora Agenda sono conservati. Non è stata confermata alcuna scadenza processuale.

Prova materiale sul browser reale in produzione: aperto ZIP 32364889s.pdf.zip dal pulsante della proposta, letto il provvedimento nel lettore interno (prima pagina: Tribunale ordinario di Vicenza, R.G. 806/2026, Giada Giffi). Dopo correzione, chiusura, ricarica, riapertura delle proposte e click sulla stessa fonte: intestazione aggiornata a Giffi Giada, documento leggibile. Screenshot fuori Git: `D:/legale/backups/IUSENTRA/recovery-20261007-versions/giffi-source-context-corrected-real.jpg`.

Limiti espliciti: nel testo estratto dal provvedimento e dall'XML non è presente il CF della cliente; la sua disponibilità in anagrafica non equivale a riscontro indipendente nella fonte. L'estrazione contestuale del CF di parte dai documenti diversi deve ancora essere completata e provata. La correzione del caso reale usa nome, ufficio e R.G. concordanti nell'XML e nel provvedimento personalmente visualizzato, con anagrafica SQL unica coerente. Sette guardrail mirati superati nel runtime server; non sostituiscono l'accettazione locale. Queste modifiche sono hotfix non consolidati: sorgenti finali e versione precedente conservati nella cartella privata di recupero. Restano riallineamento della copia locale reale 8080, test mirati integrati, commit/push dei branch gemelli e deploy ordinato finale dell'intero perimetro. Non verificato su macchina reale locale 8080.


Ulteriore prova visiva alle 17:16: scorrimento del provvedimento reale dalla prima pagina alle pagine centrali e fino al fondo della quinta pagina; ultima pagina renderizzata con data Vicenza, 06/10/2026. La data del provvedimento non viene automaticamente equiparata a pubblicazione/notifica. La bozza conserva il termine esistente calcolato dalla ricezione; la verifica del dies a quo e l'estrazione probatoria per il calcolo del termine restano aperte, senza conferma automatica.
