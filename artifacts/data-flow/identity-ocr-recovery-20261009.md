# Recupero identità e addestramento OCR — incarico aperto

## Prova reale e causa

Nel browser reale sul server, aperta l'anagrafica Borgese Maria e premuto
«Leggi documento / MRZ». Il comando restituisce codice fiscale e tipo carta,
ma non la lettura completa. Nessun salvataggio anagrafico effettuato.
La fonte corrente ha due pagine con CIE e tessera sanitaria: il recupero
regione-v1 richiedeva un solo riquadro, quindi escludeva la pagina con più carte.
Riscontrata anche la confusione O/0 nel numero della CIE, che rende negativi
i controlli MRZ. Sorgenti e immagini originali preservati fuori Git.

## Preparazione, non installazione

Nel checkout: candidato regione-v2 con riquadri limitati, ingrandimento,
rotazioni, riconoscimento del fronte CIE e controlli MRZ invariati; recupero
versionato senza cancellare il testo archiviato. Non installato né accettato
nel comando normale. Il riconoscimento del titolare resta obbligatorio.

Addestramento effettivo Tesseract LSTM eseguito localmente, senza rete,
con un thread, una CPU e limite di memoria di 2 GB. Base float ufficiale
tessdata_best al commit e2aad9b983032bb1beff9133104a67cdbb87ca4d;
origine e SHA-256 conservati nel manifest privato.
Centosessanta immagini sintetiche controllate: 120 addestramento e 40
valutazione separata. Nessun documento dello studio usato per addestrare.
Checkpoint e candidato conservati; modello applicativo invariato.

Il primo avvio non generava i file LSTM perché la configurazione di
addestramento non era nella directory della base candidata. Corretto il
percorso alla configurazione nativa e aggiunto controllo materiale dei file.
Il secondo avvio ha terminato 400 iterazioni e prodotto il candidato.

Confronto tecnico sulle stesse 40 immagini, 1.664 caratteri:

| Modello | Errori di carattere | Campioni con errori | Tempo |
| --- | ---: | ---: | ---: |
| Italiano installato | 248 | 37 | 5,066 s |
| Base float | 129 | 31 | 7,162 s |
| Candidato addestrato | 9 | 9 | 7,208 s |

Non sono risultati generali, né accettazione utente. Il candidato conserva
errori O/0 e numerici in alcuni campioni e richiede prove più ampie.
Sul ritaglio reale del fronte Borgese, ingrandito tre volte, il candidato
legge correttamente il numero con PSM 6, dove le due basi leggono uno zero.
Con PSM 11 non ottiene lo stesso risultato. Su retro e zona MRZ, ingranditi
quattro volte, nessuno dei tre modelli produce ancora una MRZ che superi
tutti i controlli: il candidato introduce spazi tra gruppi di caratteri.
Nessun dato adottato e nessun controllo indebolito.

## Percorso richiesto dall'utente

1. Individuare le carte effettive nelle pagine del documento originale.
2. Riconoscere carta cartacea, CIE e tessera sanitaria, distinguendo i lati.
3. Applicare le zone del modello riconosciuto e leggere fronte e retro.
4. Ingrandire soltanto le zone piccole; diagnosticare illuminazione,
   contrasto, inclinazione e nitidezza e riusare le trasformazioni condivise.
5. Conservare pagina, zona, trasformazioni, modello e risultato di ogni prova.
6. Unire i campi soltanto con titolare concordante; separare scadenza della
   tessera sanitaria e scadenza della carta. Una posizione prevista guida la
   ricerca, ma non prova un valore né giustifica un dato inventato.
7. Verificare automatismi, salvataggio e riapertura nel browser reale su 8080
   e poi sul server, senza regressioni dei documenti già leggibili.

## Passaggi ancora aperti

Profili geometrici e recupero adattivo devono essere integrati nel motore
condiviso già esistente, non in un lettore parallelo. Restano confronto
su altre carte cartacee/CIE/tessere sanitarie, testi ordinari e casi negativi,
prove di dati discordanti e concorrenza, archivio SQL/audit del recupero,
installazione, prova visiva reale e verifica di salvataggio/riapertura.
Il candidato addestrato non è promosso. Nessun commit/push/deploy di questo
punto; lavoro formalmente aperto. EmbeddingGemma 300M e flussi congelati
preservati.

Prove private: D:/legale/backups/IUSENTRA/identity-borgese-20261009 e
D:/legale/backups/IUSENTRA/ocr-training-ambiguities-20261009.

## Aggiornamento materiale: retro CIE, 09/10/2026

La direttiva dell'utente richiede dal retro codice fiscale e residenza,
individuati dalle etichette bilingui stampate. Il recupero di questi valori
non dipende dal superamento dei controlli MRZ. Il CF conserva il controllo
formale/checksum e il vincolo del titolare; nessuna sostituzione O/0 a intuito.
I dati del fronte, della tessera sanitaria e le rispettive scadenze rimangono
distinti. Le letture complete restano disponibili come provenienza.

Il candidato regione-v2 include diagnosi della zona, misura dei caratteri per
lo zoom e preparazione soltanto per difetti riscontrati dopo una prima lettura.
La rotazione segue il rilevatore condiviso e non prova quattro angoli per ogni
riquadro. Sul PDF originale Borgese sono state riscontrate due carte CIE e
sedici valori anagrafici/documentali coincidenti con la fonte osservata;
lettura tecnica nativa 18,421 secondi, senza promozione del modello addestrato.

Cinque sorgenti installati puntualmente nella copia Docker reale 8080, con
backup dei file precedenti e backup SQLite coerente (quick_check ok).
Riavviati soltanto i worker locali; produzione invariata. Il caricamento da
anagrafica ora chiama la stessa estrazione DocumentAI con identity_scan=True,
evitando il percorso che ometteva il recupero delle zone del modello.

Nel browser reale visibile su 8080 sono stati eseguiti personalmente:
- Marchetti: Leggi documento sul documento cartaceo già nel fascicolo;
  quindici campi mostrati, con fonti concordanti per nascita e residenza.
  Bozza preesistente preservata; nessun salvataggio eseguito.
- Borgese: caricamento del PDF originale nella scheda locale di collaudo,
  click Leggi documento, stato di lettura disabilitato e risultato osservato:
  diciassette campi, inclusi CF e residenza corretti, dati del fronte e numero
  con lettera O corretti. Nome/cognome della scheda di collaudo mantenuti dalla
  protezione dei campi già compilati; nessun salvataggio né attribuzione a quel
  cliente. Questa prova non dimostra il salvataggio SQL di Borgese.
- Focus da tastiera: osservato. Rilevata sovrapposizione del pulsante Genera CF
  al valore; predisposta correzione condivisa CSS, da riconvalidare visivamente.

Guardrail client reader/PDF inspector/diagnosi positivi, con un test CV saltato
sull'host che non dispone di OpenCV; la misura CV è stata eseguita nel runtime
nativo. Ruff positivo. Le prove non costituiscono consegna integrale: restano
salvataggio/riapertura pertinenti, altri documenti e casi negativi, responsive,
consolidamento Git, copia locale definitiva sul commit e distribuzione server.

Correzione della nota precedente sull'addestramento: il candidato isolato legge
una MRZ valida sul retro intero dopo la normale rimozione degli spazi prevista
dal parser, mentre il ritaglio MRZ resta negativo. Il modello attivo non è stato
sostituito. Non confondere il risultato del candidato con il comando installato.

## Ulteriori prove materiali locali del 09/10/2026

Corretto e riprovato il pulsante Genera CF: valore completo e pulsante separati
su desktop, mobile 390 px e tablet 768 px, con focus leggibile. Viewport poi
ripristinato. Build isolata dalla tranche CTU in corso, distribuita soltanto
alla copia Docker reale 8080; produzione non aggiornata in questa fase.

Riprodotta perdita della bozza pendente al focus/blur di un campo immutato:
il salvataggio automatico iniziale cancellava la bozza prima di Ripristina.
Il hook condiviso ora protegge la bozza pendente fino a ripristino o scarto
esplicito. Prova reale ripetuta positiva, con messaggio Bozza ripristinata e
valore OCR conservato. Scartata soltanto la bozza creata dalla prova; bozze
preesistenti degli utenti preservate.

L'upload in modifica ora trasmette l'identificativo cliente e la route verifica
permesso di scrittura, esistenza nel tenant e titolare con il resolver nativo.
Prova reale negativa: documento Borgese su una scheda di collaudo con altro
titolare rifiutato, messaggio esplicito e nessun campo applicato. Guardrail
per cliente inesistente positivo prima dell'OCR; suite client reader positiva.

Prova positiva richiesta sui quattro dati documentali: caricamento della fonte
originale Borgese in un modulo nuovo con bozza contestuale separata, lettura,
salvataggio attraverso il comando nativo e riapertura con Modifica anagrafica
nell'area di lavoro. Numero, ente di rilascio, data rilascio e scadenza sono
stati ritrovati nei campi e visti materialmente, con date italiane. Creata una
sola anagrafica locale di prova con nota esplicita, senza preventivo/atto o
comunicazione; nessuna modifica all'anagrafica di produzione. Screenshot e
identificativo locale nel dossier privato fuori Git. Questa prova non attesta
la distribuzione server né tutti i modelli di documento richiesti.

Ripetuto anche Salva modifiche nell'area di lavoro: messaggio Modifiche salvate,
chiusura della finestra e riapertura tramite lo stesso collegamento. I quattro
valori sono rimasti identici. Nuovo upload sulla scheda dello stesso titolare
accettato: diciassette campi letti, dati documentali già compilati preservati.
La prova negativa sul titolare diverso e quella positiva sul titolare corretto
sono distinte. Tutte le prove sono locali; il server resta a 3ee4b09, healthy e
con unico container applicativo iusentra-app, checkout pulita.

Suite mirata su client reader, riacquisizione DocumentAI, PDF Inspector,
diagnosi immagine e training positiva (un guardrail CV saltato sull'host).
Ruff positivo. Codex quality gate ui-support non superato per scope: il
checkout contiene la tranche prodotto OCR e CTU, fuori dal profilo tooling
ui-support; dipendenze, AGENTS e Open Design positivi. Non è stato aggirato
il controllo né presentato il risultato come consegna o rilascio completato.

## PDF allegato dall'utente: carta identità, prova normale del software

Fonte C:/Users/antmm/Downloads/carta identità.PDF, due pagine CIE entrambe
ruotate. Originale e render di entrambe le pagine ispezionati senza modificare
il file. Nel browser reale visibile su 8080, modulo nuovo con contesto bozza
separato: Carica documento e Leggi documento / MRZ, nessun dato digitato e
nessuna rotazione manuale. Il software ha compilato diciassette campi Alfano.
Confronto materiale positivo per nome/cognome, sesso, nascita, luogo/provincia,
numero, Comune emittente, rilascio/scadenza, CF e indirizzo/civico/comune.
Il documento non è stato salvato come nuova anagrafica per questa prova.
La nazionalità è letta dal fronte, mentre la MRZ resta esplicitamente incapace
di provarla: il dato MRZ non viene inventato. Screenshot privato in
D:/legale/backups/IUSENTRA/identity-upload-20261009/browser-document-fields.jpg.

Riprodotto inoltre messaggio OCR «modifiche non ancora salvate» dopo effettivo
salvataggio positivo. Correzione del messaggio predisposta nei due moduli,
soltanto dopo riscontro del comando riuscito e quando non sono intervenute
altre modifiche durante la richiesta. Snapshot dei dati realmente inviati
separato dai dati modificati in seguito, evitando di cancellare quella bozza.
Typecheck e build mirati positivi; bundle installato nella copia locale.
Accettazione materiale del nuovo messaggio ancora in esecuzione.

09/10/2026 — Comune da lettura, prova materiale locale: nel browser reale visibile 127.0.0.1:8080 il comando normale Leggi documento / MRZ sul PDF originale Alfano ha compilato Comune Vicenza, Provincia VI e CAP 36100 partendo da campi vuoti, senza selezione del Comune. Il componente condiviso usa il catalogo territoriale esistente anche per valori applicati da OCR. Nel caso controllato Roma ha compilato RM mantenendo CAP vuoto e mostrando la motivazione dei CAP multipli; con Provincia VI discordante ha conservato VI e mostrato il conflitto, senza scegliere un CAP. Bozza temporanea del caso negativo scartata, nessuna anagrafica salvata per queste prove. Corretto anche Scarta bozza: azzera i campi marcati come modificati e lo stato OCR, evitando che la lettura successiva lasci i campi vuoti. Typecheck e build mirati positivi (2,44 s). Evidenza privata: D:/legale/backups/IUSENTRA/identity-upload-20261009/browser-comune-cap-automatici.jpg. Questo riscontro non è rilascio server: consolidamento, CI e deploy della tranche OCR rimangono aperti.

09/10/2026 — Ulteriore accettazione materiale locale. Sulla sola scheda di prova Borgese già creata, upload dell'originale e comando Leggi documento / MRZ, quindi Salva modifiche: osservati «Modifiche salvate» e «Dati riconosciuti del documento salvati nell’anagrafica». Screenshot privato identity-borgese-20261009/browser-ocr-salvato.jpg. Nessuna mutazione del cliente di produzione. Nel Comune condiviso eliminato il secondo automatismo al blur che cancellava CAP discordanti: risoluzione automatica unica conserva 99999 nel caso controllato Vicenza/VI e mostra il motivo anche dopo uscita dal campo e riapertura della bozza. Corretto l'allineamento quando compare il messaggio: Comune, Provincia e Nazione tutti alla stessa coordinata verticale, altezza 42 px; riscontro DOM e visivo effettivi. Bozza negativa temporanea scartata senza salvataggio SQL. Typecheck positivo, bundle finale di questa prova costruito in 2,27 s e installato solo sul Docker reale 8080, senza includere sorgenti CTU nel bundle. Screenshot privato identity-upload-20261009/browser-cap-discordante-conservato.jpg. Restano aperte prove residue dei modelli/multipli, consolidamento, CI e deploy; nessun rilascio server o promozione del modello addestrato.


09/10/2026 — OCR, titolari multipli: prova reale visibile su Docker 127.0.0.1:8080. PDF controllato composto dalle quattro pagine originali di Borgese e Alfano, senza alterare contenuti: Carica documento e Leggi documento / MRZ hanno mostrato il rifiuto per due codici fiscali validi distinti; nessun campo personale applicato al modulo vuoto. Screenshot privato identity-upload-20261009/browser-due-titolari-rifiutati.jpg. Ripetizione sul solo originale Alfano: diciassette campi e Comune/Provincia/CAP automatici ancora osservati; nessun salvataggio SQL di una nuova anagrafica.
Ulteriore controllo installato nel lettore condiviso: più TD1 complete e verificate distinte impediscono di scegliere la prima carta anche quando non è presente un CF. Prova materiale con PDF controllato nativo di due MRZ ICAO: rifiuto esplicito osservato, bozza Alfano già presente conservata senza sovrascrittura. Scartata soltanto questa bozza temporanea propria dopo la prova; nessun cliente salvato. Screenshot privato browser-due-mrz-rifiutate.jpg. Non attribuire a questa prova una scansione OCR di immagini: il PDF di controllo contiene testo nativo.
Recupero riquadri: conservati tutti i testi e le evidenze quando dimostrano la medesima carta; fronte e MRZ sono collegabili solo con identico numero documento. Guardrail positivo/negativo sul confronto; un retro privo di collegamento dimostrabile resta distinto. Questa modifica è installata localmente, ma il suo caso fronte/MRZ nello stesso foglio non è ancora verificato su macchina reale. Suite lettore/PDF Inspector/diagnosi positiva, con un caso OpenCV host saltato; Ruff positivo. La prova sintetica non è accettazione utente. Nessun commit/push/deploy della tranche; CTU WIP preservata, produzione invariata. Il consolidamento e le prove residue mantengono aperto l'incarico.


09/10/2026 — Nel controllo visivo rilevato e corretto il titolo/nome file compresso tra i pulsanti del lettore. Header condiviso ora va a capo per gruppi senza ridurre il titolo a una colonna stretta. Bundle isolato ricostruito e installato sul Docker reale, quindi ripetuto comando normale negativo MRZ con campi vuoti: avviso e campi vuoti osservati, focus visibile. Desktop, mobile390 e tablet768 osservati materialmente; dimensione normale ripristinata. Screenshot privati browser-lettore-compatto-desktop.jpg/mobile.jpg/tablet.jpg. Nessun salvataggio SQL o deploy server.
Durante lo scorrimento è emerso un ulteriore difetto preesistente: QualityRail mostra quattro controlli verdi statici anche con modulo vuoto e documento rifiutato. La causa è checkItems statico con CheckCircle2, non un riscontro del repository o del form. Non corretto né nascosto: deve essere collegato ai controlli effettivi prima di attribuire una qualità verificata all'anagrafica. Questa evidenza mantiene aperto il perimetro UI; nessuna dichiarazione di completamento.


09/10/2026 — Ulteriori originali forniti dall’utente, lavoro OCR ancora aperto. Tre PDF originali di due pagine ciascuno caricati tramite Carica documento e comando normale Leggi documento / MRZ nel browser reale visibile 127.0.0.1:8080. Nessuna trascrizione manuale dei campi né salvataggio di nuovi clienti in questa prova. Riscontri iniziali: carta cartacea sbiadita due campi; CIE molto piccola sette; carta cartacea ruotata e tessera sanitaria sei. Dopo correzioni del recupero condiviso, osservati otto campi sull’ultimo originale, incluso CF realmente compilato, e nove sulla CIE, con luogo/provincia di nascita aggiunti. La data stampata di nascita deve coincidere con la MRZ verificata della medesima carta e Comune/provincia con il catalogo; prova positiva/negative tecniche su data, provincia e numero carta. Questa accettazione riguarda quei campi, non una lettura completa: rilascio, indirizzo e CF CIE restano incompleti, la prima carta sbiadita non è recuperata integralmente.
Evidenze private in D:/legale/backups/IUSENTRA/identity-extra-20261009: rendering di entrambe le pagine dei tre originali, diagnosi e browser-cie-nove-campi.jpg. Nessun documento personale o testo OCR originale da inserire nel commit.
Correzioni installate puntualmente nel Docker reale, candidato non rilasciato: maschera localizza i riquadri sui pixel originali senza filtro mediano che cancellava lettere sottili; riquadro originale prima, zoom misurato conservativo solo dopo lettura insufficiente; MRZ valida non interrompe il recupero dei campi stampati; zone CIE per emissione/scadenza e dati anagrafici, con tentativi insufficienti registrati. Sfondo disomogeneo rilevato dai percentili dei quadranti, normalizzazione solo se diagnosticata. Raddrizzamento fine riusa la misura condivisa, tentativo dopo letture insufficienti e adozione solo se supera il riscontro del documento. Nitidezza non equivale a ricostruzione di informazioni assenti o autofocus fisico.
Prova diagnostica antirumore sulla CIE: filtro mediano peggiora confidenza e cifre, quindi non adottato. Nessun miglioramento percentuale complessivo promesso o dimostrato. Il raddrizzamento fine e lo sfondo disomogeneo nuovi non hanno ancora accettazione materiale su un caso pertinente; guardrail tecnici non sostitutivi. Nessun commit/push/deploy di questa tranche, produzione invariata, CTU WIP e bozze utente preservate.

09/10/2026 — Riscontro geografico OCR installato puntualmente sul Docker reale 8080, non rilasciato. Resolver condiviso SQL territorio: nome esatto e provincia, senza completamenti per somiglianza; distingue non riscontrato, provincia discordante, ambiguità e catalogo non disponibile. Luogo di nascita può usare Belfiore storico con provincia concordante; località estere EE non vengono forzate nel catalogo italiano. Un Comune non riscontrato rimane nei campi da verificare e non entra nella patch. Prova materiale: PDF controllato con Comune Inventato letto tramite Carica documento e Leggi documento / MRZ; Comune vuoto, valore riconosciuto 70% e avviso esplicito osservati. Nessun cliente salvato. Screenshot privato identity-extra-20261009/browser-comune-non-applicato.jpg. Non attribuire a questa prova nativa la qualità dell'OCR immagini.
CIE originale aggiuntiva: nuovo comando normale 8080 mantiene dieci campi, compreso Comune di rilascio, nascita e provincia; CF retro ancora non letto. Il codice calcolato già inserito nella bozza è stato preservato e non dichiarato letto dal documento. Riscontro fiscale condiviso confronta soltanto dati della lettura, checksum e omocodia compatibile; non prova l'assegnazione ufficiale, non applica il CF calcolato e rifiuta provincia incoerente anche se il resolver storico ha fallback. Guardrail mirati positivi; aggiornamento fiscale installato, prova positiva/negativa completa nell'interfaccia ancora aperta. Nuovo feedback sul numero pagine predisposto/installato, comando CIE di riprova avviato. UI correzione stato CF costruita 2,29 s e installata, ma non ancora accettata materialmente su svuotamento. Nessun commit/push/deploy di questa tranche. Originali, bozze e CTU WIP preservati.

09/10/2026 — Riprova materiale completata sul comando normale della CIE originale aperta, browser reale visibile 127.0.0.1:8080: osservati «Lette 2 pagine del documento», dieci campi riconosciuti e avviso che il codice fiscale della fonte resta non leggibile. Il CF calcolato preesistente nella bozza è preservato, non confuso con un CF letto. Screenshot privato identity-extra-20261009/browser-cie-due-pagine.jpg. Nessun salvataggio SQL. Questo esito attesta il percorso su due pagine, non il recupero completo del retro; CF, rilascio e residenza rimangono nel lavoro aperto. Produzione non modificata.

09/10/2026 — Recupero CIE: CF e data rilascio ora osservati materialmente nel comando normale della copia reale 8080. Il PDF originale aggiuntivo restituisce dodici campi, comprendendo CF (96%) e data rilascio 20/02/2020 (94%); la data vuota è stata compilata automaticamente, mentre il CF già calcolato nella bozza è rimasto conservato ed è ora confrontabile con il valore realmente decodificato. Nessuna trascrizione manuale né salvataggio SQL in questa prova. Screenshot privato identity-extra-20261009/browser-cie-cf-rilascio.jpg. Residenza ancora incompleta: non attribuire dodici campi a lettura completa dell'intero documento.
Schiarimento richiesto dall'utente: originale e curva dei soli mezzitoni chiari confrontati localmente sul riquadro della seconda pagina; pixel scuri e originale preservati. Confidenza del secondo lettore da 0,720 a 0,785, nessun CF valido in entrambi i tentativi. Questa trasformazione diagnostica non è stata adottata come dato né presentata come recupero del CF. Prova supplementare residenza: lo schiarimento peggiora il ritaglio stretto (0,705→0,643), mentre il riquadro più ampio migliora leggermente ma resta insufficiente (0,617→0,669). Nessun indirizzo inventato/applicato.
Riscontro CF: nuova decodifica locale del codice a barre (Code 39) nel riquadro della medesima carta con MRZ italiana completa verificata; codice univoco, checksum CF e confronto nome/cognome, nascita e sesso, con omocodia compatibile. Decoder zxing-cpp 3.0.0 dal progetto ufficiale/PyPI, installato sul solo Docker locale e dichiarato in requirements/pdf.txt; nessun testo dello studio inviato all'esterno. Assenza decoder, codici multipli, checksum o identità discordanti restano negativi espliciti. Non è una verifica dell'assegnazione fiscale ufficiale. Fonte ufficiale tecnica: https://github.com/zxing-cpp/zxing-cpp/blob/master/wrappers/python/README.md
Data rilascio: zona Emissione ora delimitata separatamente dalla Scadenza; originale prima e zoom misurato solo dopo lettura insufficiente. Ritaglio dell'etichetta e valore restituisce EMISSIONEASSUING e 20.02.2020 con confidenza 0,970. Parser richiede etichetta sulla propria riga e data immediatamente successiva: una riga mescolata con Scadenza non diventa data rilascio. Guardrail positivo/negativo aggiunto. Regione-v4 governa il recupero puntuale aggiornato; nessuna scansione generale né riattivazione job embedding2.
Suite mirata barcode/lettore/PDF Inspector/diagnosi/confronto fiscale positiva, un guardrail OpenCV host saltato; Ruff positivo. Backend installato puntualmente e unico Docker locale healthy, non release sullo stesso commit. Nessun commit/push/deploy server della tranche; CTU WIP, backup, bozze e flussi congelati preservati. Restano prove residue dei modelli/campi, provenienza dettagliata nell'interfaccia, consolidamento e rilascio: incarico aperto.

09/10/2026 — Residenza CIE, separazione sfondo richiesta dall’utente: diagnostica locale sul riquadro originale della seconda pagina, senza modifica dell’originale o dell’anagrafica. Il fondo contiene linee di sicurezza nere intrecciate ai caratteri: divisione sul fondo stimato conserva la lettura precedente (0,705), binarizzazione globale/locale non produce una lettura utile. Separazione per spessore dei tratti con otto aperture misurate: migliore confidenza 0,851, ma persistono lettere e civico discordanti fra varianti; ulteriori scale non superano il riscontro. Ritaglio della riga letto dai due motori locali, ancora non concordante. Nessun indirizzo applicato, nessuna soglia abbassata, nessuna variante diagnostica promossa nel motore. Risultati privati address-background-separation.json, address-strokes.json, address-strokes-second.json, address-line.json e address-stroke-scales.json in identity-extra-20261009. Residenza ancora aperta; queste prove non equivalgono ad accettazione del comando nell’interfaccia. CF e data rilascio della precedente prova normale restano distinti da questo esito negativo. Nessun commit/push/deploy della tranche.

09/10/2026 — Strumenti di sfondo richiesti dall’utente integrati nel motore condiviso (regione-v6-modelli-sfondo): selezione dei pixel vicini alla luminanza locale, separazione, schiarimento e scurimento dello sfondo su copie. Applicazione soltanto dopo lettura insufficiente e su zone non uniformi; tratti scuri e originali preservati. Guardrail mirati lettore/modelli/immagine/reacquisizione positivi, un caso OpenCV host saltato; Ruff e build isolata 2,41 s positivi. Installazione puntuale locale 8080 healthy, non rilascio su commit.
Riscontro tecnico sull’originale cartaceo più tessera sanitaria, impronta uguale al PDF caricato nella prova browser: prima pagina orientamento-v1 adotta 270°; seconda pagina resta 0° complessivi ma il riquadro della tessera sanitaria è letto a 270°. Registro privato identity-model-routing-20261009/identity-ts-v6-audit.json. Tre varianti dello sfondo realmente provate sui riquadri insufficienti; nessun miglioramento accettabile, originale di lettura conservato. Questo registro tecnico non sostituisce la prova materiale del comando aggiornato nel browser, in corso. Corretto anche l’azzeramento dei modelli riconosciuti nello stato UI dopo upload, ancora da accettare visivamente. Produzione invariata; nessun commit/push/deploy OCR; incarico aperto.

09/10/2026 — Orientamento prima dei trattamenti (regione-v7-orientamento-prima): originale nei versi pertinenti, poi diagnosi/varianti solo quando le letture originali sono insufficienti. I tre strumenti sullo sfondo rimangono disponibili, senza generare caratteri. Riprova del comando normale sul PDF cartaceo originale più tessera sanitaria: osservati due modelli distinti e nove campi riconosciuti, compresa data rilascio 08/08/2014. Il timbro stampato era mescolato con l'etichetta del pannello accanto: separazione conservativa della sola etichetta, senza cambiare la fonte o il valore. Non attribuire questo esito a tutti i campi del documento.
Difetto materiale successivo: il ripristino della bozza marcava anche ogni campo vuoto come modifica manuale, quindi la data riconosciuta non veniva applicata. Introdotta conservazione dei soli campi protetti nella bozza; compatibilità storica conserva differenze dalla base e cancellazioni di valori preesistenti, senza bloccare campi vuoti mai compilati. Installazione puntuale nel Docker reale 8080, build isolata 2,35 s; nessun sorgente CTU incorporato. Riprova con upload dello stesso originale e click Leggi documento / MRZ: la data 08/08/2014 è effettivamente comparsa nel campo precedentemente vuoto, osservata con focus e screenshot privato identity-model-routing-20261009/browser-data-rilascio-applicata.jpg. Nessun salvataggio SQL di questa scheda di prova. Quattro guardrail di ripristino positivi, compresa cancellazione manuale con base vuota; prova materiale negativa della cancellazione in corso.
Le regole supplementari di corroborazione dei dati stampati tramite CF sono coperte dai test del lettore e Ruff positivi, ma non ancora installate o accettate nell'interfaccia. Restano campi cartacei mancanti, zone specifiche del modello da completare e prove residue; nessun commit/push/deploy OCR, produzione invariata, incarico aperto.

09/10/2026 — Carta cartacea e tessera sanitaria: recupero automatico dei campi mancanti per fasi, prova reale locale.
Il ritaglio della riga Via e del contesto è stato ispezionato materialmente. La riga contiene etichette distinte Via, Num. e Piano: il civico non va ricavato dal piano o dall'interno. Il recupero condiviso localizza le etichette sull'immagine già orientata, ritaglia e ingrandisce per primo il solo campo; se insufficiente legge il contesto del medesimo titolare. La diagnosi del contesto ingrandito richiede nitidezza, non schiarimento indiscriminato. Il dato è adottato soltanto con letture concordanti della stessa zona, riscontro del titolare e corroborazione nella fonte iniziale; l'ambiguità I/1 è limitata al prefisso numerico effettivamente stampato, senza correzioni arbitrarie del nome della strada o del civico.
Sul PDF originale di due pagine, nel browser reale visibile 127.0.0.1:8080, il comando normale Leggi documento / MRZ ha restituito sedici campi. Dopo Scarta bozza della sola scheda controllata propria, la ripetizione ha applicato i sedici campi partendo da valori vuoti, compresi nascita, luogo/provincia, Comune, via, civico, ente emittente, rilascio e scadenza. CAP e provincia della residenza sono stati completati dal catalogo condiviso, senza selezione manuale del Comune. Data rilascio effettivamente visibile con focus; via/civico distinti dal piano. Nessuna trascrizione manuale dei valori. Evidenze private: identity-model-routing-20261009/browser-cartacea-rilascio-residenza.jpg e browser-cartacea-via-civico.jpg.
La data inizialmente vuota nell'ultima bozza non era una regressione della lettura: era stata cancellata volontariamente nella prova negativa di protezione delle modifiche manuali. Dopo pagehide/ripristino e nuova lettura la cancellazione è rimasta protetta; dopo lo scarto di questa bozza tecnica e nuova lettura il campo è stato compilato dal software. Quattro guardrail JS positivi, ora registrati anche nel comando frontend test e nel comando mirato test:anagrafica-draft-ocr.
Ricaricata la pagina dopo blur: i campi OCR, compresa la data di rilascio e la residenza, sono stati ripristinati nella bozza. Questa prova dimostra persistenza della bozza nel browser, non salvataggio SQL di un nuovo cliente; non è stata creata una nuova anagrafica duplicata della persona reale.
Suite mirata paper_address_recovery, identity_image_diagnosis, document_catalog_identita_personale e client_document_reader positiva; un controllo OpenCV host saltato, Ruff positivo. Il riscontro di questo documento non dimostra accuratezza complessiva del 90% o 100% su tutti i modelli.
Direttiva successiva: un trattamento per fase, lettura e riscontro immediato, scarto dell'esito insufficiente prima del successivo sulla zona preservata. Fine della lista dei tentativi pertinenti = arresto, nessun ciclo automatico continuo. Candidato regione-v9 divide normalizzazione luce, contrasto e nitidezza nei tre percorsi condivisi (carta, zone CIE, recupero comune), mantenendo gli strumenti sfondo separati. Due guardrail supplementari confermano separazione delle fasi e fine del ciclo senza accumulo. Installato puntualmente solo nel Docker locale; riprova materiale dell'ultimo candidato avviata sullo stesso originale, esito ancora in attesa al momento di questa registrazione. Nessun commit/push/deploy OCR, produzione invariata; altri casi e rilascio rimangono aperti.

09/10/2026 — Preparazione prima dell’OCR, candidato locale non rilasciato.
Riscontro osservabile richiesto: su tutte le pagine delle carte fornite, diagnosi → eventuale rettifica dimostrata → orientamento → luce/dettaglio/ingrandimento pertinenti → OCR; successivamente soltanto recuperi dei campi mancanti. Nessuna trascrizione dell’agente come risultato del lettore. Direttiva registrata in AGENTS.md.
La riprova regione-v9 della carta cartacea più tessera sanitaria si è conclusa nel browser reale con sedici campi; corregge la precedente nota «in attesa». Il nuovo caso Carta d’identità (2).PDF, due pagine, restituisce ancora soltanto tipo e numero nel comando normale 8080, sia dopo la correzione della densità sia con regione-v11. Esito osservato a lettura terminata, nessun cliente salvato; screenshot privato identity-resolution-20261009/browser-carta2-due-campi.jpg. Il risultato non è accettato come lettura completa.
Causa tecnica accertata: il secondo lettore serializzava i ritagli al doppio della densità di rilettura, dimezzando i pixel per asse. Aggiunto parametro esplicito per preservare la risoluzione, usato nel nuovo primo tentativo preparato; i chiamanti storici restano invariati. La correzione da sola non recupera gli altri campi del caso. Geometria e preparazione lavorano su copie; quattro bordi e rette interne concordanti richiesti prima di rettificare. Su questo originale i pannelli hanno inclinazioni diverse e bordi incompleti: nessuna rettifica globale è stata dichiarata eseguita. Una rotazione locale di diagnosi e una deconvoluzione sperimentale hanno peggiorato la lettura e non sono state adottate.
Ispezionate fonte nativa e immagine preparata. Il contrasto visivo maggiore non dimostra una lettura migliore: i tentativi producono anche date discordanti, talvolta con confidenza elevata. Nessuna scadenza derivata da tali varianti è stata applicata. Il confronto originale/variante prima dei recuperi puntuali è in integrazione; il primo OCR globale storico precedeva ancora la preparazione, quindi l’ordine richiesto non era garantito dall’inizio della pipeline.
Guardrail aggiunti al parser: valori affidabili discordanti esclusi, titolari distinti senza CF comune non composti in una sola scheda, scadenze TS separate, doppioni identici conservati. Replay di quattro estrazioni storiche e 33 varianti invariato; non è parità materiale dei risultati finali da dodici/sedici campi. Profilo della faccia interna cartacea riconosciuto dalle etichette anagrafiche e connotati fisici senza richiedere la copertina; questo guida i tentativi e non certifica dati o titolare. Rotazione misurata sempre disponibile, eliminate sonde CIE cieche sul modello già riconosciuto.
Le prove geometriche sono state eseguite anche nel Docker reale con OpenCV; corretto il differente formato delle rette restituito dal binding. I test tecnici non sostituiscono accettazione del comando normale. Installazione delle ultime correzioni parser/pipeline, riprova dei tre casi, consolidamento, CI, commit/push dei due branch e deploy restano aperti. Produzione, CTU WIP, originali e backup preservati; EmbeddingGemma 300M invariato.

09/10/2026 — Riprova materiale v12/v6: regressione rilevata, rilascio non accettato.
Installati i sorgenti candidati nel Docker reale con copie preventive, compilazione e riapertura dei worker; readiness positiva. I due comandi avviati nell’interfaccia sono terminati: Carta (1) restituisce quattordici campi invece di sedici, con nascita e nazionalità escluse per discordanza; Carta (2) applica anche un nome errato oltre al tipo e numero. Questi esiti sono difetti reali, non letture accettate. Nessuna anagrafica salvata in SQL. Evidenza privata browser-carta2-v12-nome-errato.jpg in identity-resolution-20261009.
Diagnosi riproducibile delle estrazioni: pagina cartacea del primo PDF invariata; OCR generale della tessera sanitaria associa la scadenza all’etichetta della nascita, mentre il recupero regionale legge la nascita corretta concordante con CF e titolare. La nazionalità alternativa include colonne di residenza mescolate. Nel secondo PDF il nome errato nasce dall’OCR generale, senza alcun recupero qualificato: l’88% visibile è un peso fisso del parser, non una misura OCR del campo. Necessaria distinzione delle fonti native/OCR/recuperi qualificati prima di comporre la patch; le vere discordanze fra riscontri validi devono restare bloccanti.
Predisposte provenienze separate per pagina nell’engine v7, con test che impedisce al recupero dell’indirizzo di qualificare il testo generale circostante. Correzione UI delle percentuali fisse in esiti e provenienza predisposta, typecheck e build isolata positivi; accettazione visiva della versione aggiornata ancora da eseguire. Le due letture complete diagnostiche durano 84,87 e 74,68 secondi; questi tempi non sono un miglioramento prestazionale dimostrato.
Confronto locale dei modelli italiano fast, best ufficiale e candidato addestrato: nessun miglioramento affidabile della fonte difficile; date discordanti e latenza maggiore nel best/candidato. Nessuna promozione. Ritaglio diagnostico della copertina della seconda pagina: nome/cognome concordanti fra due lettori, ma localizzazione automatica e comando normale ancora da integrare/provare; non presentare il ritaglio manuale come capacità del software. Nascita non confermata dai lettori. Tutte le prove e i testi personali restano nei backup privati, fuori Git.

09/10/2026 — Candidato v13/engine v8 installato soltanto sulla copia reale locale, rilascio ancora aperto.
Backup preventivo dei sei sorgenti precedenti in identity-resolution-20261009/v13-before; compilazione, riapertura dei worker e readiness positivi. Pixel originali delle scansioni monoimmagine usati solo nel recupero della copertina dopo esito insufficiente, con controllo struttura PDF, matrice, limiti, maschere, sovrapposizioni e annotazioni. Nessuna soglia OCR ridotta; un solo tentativo alternativo. Fonti native/OCR/recuperi conservate separatamente nei pages_json SQL esistenti; tredici prove PostgreSQL/SQLite controllate positive, compresi rollback, tenant e idempotenza. Centonove guardrail OCR e settantanove parser positivi. Tali prove non sostituiscono il browser.
Prova materiale mediante click Leggi documento / MRZ su Carta d’identità (2).PDF: quattro campi applicati partendo da scheda tecnica vuota, cognome e nome corretti oltre a tipo e numero. Il precedente nome errato non viene applicato. Screenshot privato browser-carta2-v13-quattro-campi.jpg, campi mancanti espliciti; non è una lettura completa. Nessuna anagrafica SQL duplicata creata. UI ora distingue riscontro MRZ, codice a barre, lettura documentale e dato da verificare, senza percentuali fisse del parser presentate come probabilità OCR.
La riprova CIE nel comando normale ha evidenziato dieci campi invece dei dodici precedenti: luogo e provincia di nascita mancanti. Restano osservati MRZ, codice fiscale da barcode, rilascio e scadenza. Regressione non accettata, diagnosi in corso. Riprova carta più tessera sanitaria avviata ma non ancora conclusa a questo checkpoint. Nessun commit/push/deploy, produzione invariata. Non attribuire il recupero dei quattro campi alla chiusura della tranche.

09/10/2026 — Riprova successiva v13: recuperati i risultati precedenti nei due casi, senza chiusura della tranche.
Carta più tessera sanitaria: sedici campi applicati nel comando normale da scheda vuota; osservati residenza, civico, comune, CAP, nascita e rilascio. CIE: causa della regressione individuata nell’etichetta inglese unita dall’OCR; parser corretto senza inferire la città. Nuova prova materiale da scheda vuota, caricamento del PDF utente e click normale: dodici campi applicati, inclusi Cosenza e CS, confermati visivamente. Residenza incompleta esplicita e nazionalità MRZ non applicata. Nessun cliente duplicato salvato. Screenshot privati browser-ts-v13-data-rilascio.jpg, browser-ts-v13-fondo-modulo.jpg e browser-cie-v13-cosenza.jpg nel backup identity-resolution-20261009. Il pannello browser temporaneamente non visibile è stato riaperto dall’agente nella chat corrente, senza delegare l’accettazione all’utente.
Individuata divergenza per upload immagine con identity_scan: JPG/PNG seguivano OCR generico. Aggiunto adattatore limitato e senza ricompressione dei pixel al medesimo PDF Inspector identità; orientamento EXIF, trasparenza su fondo bianco, massimo 35 milioni di pixel, rifiuto esplicito dei file multiframe senza perdere pagine. Quaranta guardrail estrazione/fonti/adattatore positivi, Ruff positivo; sorgente installato localmente, prova UI immagine ancora aperta. Nessun risultato tecnico sostituisce tale prova. Campi residui Carta (2), persistenza, accettazione e release restano aperti. Nessun commit/push/deploy di questa tranche.

09/10/2026 — Accettazione parziale immagini nel comando normale. Il primo PNG era un ritaglio diagnostico e non un confronto equivalente; prova corretta sulla pagina completa 1423 × 951. Individuato errore di precisione decimale tra box e matrice dell’adattatore: controllo nativo respingeva l’immagine come ritagliata. Corretto l’adattatore, senza tolleranze allargate nel controllo. Aggiunta decodifica Flate a dimensione massima dichiarata, rifiuto stream eccedenti, dati residui e predittori. Centoquattordici guardrail estrazione/lettore/fonti/adattatore positivi e Ruff positivo. Rilettura UI PNG completa: cognome e nome applicati, numero preservato concordante, quattro campi riconosciuti; screenshot browser-png-v13-titolare.jpg nel backup privato. Modello cartaceo e tentativi espliciti, nessun altro campo presentato come verificato. JPEG originale estratto senza ricompressione dall’oggetto effettivamente disegnato del PDF utente; prova UI avviata. CIE: rilascio, scadenza e ufficio osservati a fondo modulo, screenshot browser-cie-v13-date.jpg. Nessuna persistenza SQL cliente né release dichiarata.

JPEG originale: comando reale terminato con i medesimi quattro campi del PNG, valori concordanti già compilati preservati; screenshot browser-jpg-v13-titolare.jpg. Nome file e modello apparivano uniti senza spazio nel lettore: inserito separatore leggibile; build isolata/typecheck positivi (2,36 s), asset aggiornati localmente preservando i precedenti. Accettazione visiva separatore e ripristino bozza in corso, nessuna chiusura generale.

09/10/2026 — Su istruzione esplicita dell’utente viene consolidata e distribuita la tranche OCR materialmente provata. JPEG ripetuto da scheda tecnica vuota: quattro campi applicati e separatore nome/modello verificato visivamente; bozza ripristinata dopo reload. CIE dodici campi e carta più tessera sanitaria sedici campi restano riscontri per caso. Campi illeggibili residui espliciti, residenza CIE lasciata manuale come accettato dall’utente. Esplorazione dell’ente della copertina cartacea esclusa dall’indice della release, poiché il riscontro reale non è ancora concordante; titolare corretto preservato. CTU WIP e lavori generali restano separati e aperti. Server sul commit precedente con repository pulito; controllo dei sorgenti e asset hot positivo senza perdite. Commit, push e deploy in corso, da registrare soltanto dopo verifica finale.
