# Catalogazione documentale completa dei fascicoli

- Stato: analisi specialistica e progettazione Fase 4. Nessuna modifica applicativa è stata ancora eseguita.
- Data: 24/08/2026, Europa/Roma.
- Obiettivo: permettere a IUSENTRA di inventariare, comprendere, classificare, collegare e far revisionare ogni documento di ogni fascicolo, in ogni famiglia di contenzioso o procedimento trattabile dallo studio.
- Fonte operativa dei record: SQL tenant-aware — SQLite locale e PostgreSQL produzione. I JSON restano soltanto mirror rigenerabili.

## Mandato e criterio professionale

Il problema non è assegnare una generica etichetta a un file. In un fascicolo un documento può essere contemporaneamente una copia notificata, prova di deposito, atto di parte, allegato a un atto, origine di un termine e versione firmata di un originale. Una classificazione che riconosce soltanto `PDF + ricorso` o `nome file + sentenza` può generare errori procedurali, duplicazioni e termini errati.

L'obiettivo operativo è quindi questo: ogni documento deve essere recuperabile, avere provenienza e integrità verificabili, essere collocato nella sequenza corretta del procedimento, mantenere le relazioni con contenitore, allegati, depositi, comunicazioni e provvedimenti, e dichiarare con trasparenza se la sua qualificazione richiede revisione professionale.

Non esiste un elenco finito di tutti i supporti probatori possibili. La completezza si ottiene con una tassonomia a più assi: il sistema copre tutte le famiglie, i tipi processuali controllati e le prove trasversali; un documento davvero nuovo non viene né ignorato né etichettato con certezza fittizia, ma conservato come `da_revisionare` con proposta, evidenze e motivo. Questo è il solo comportamento coerente con un fascicolo legale affidabile.

## Modello unico di catalogazione

Ogni documento riceverà dati separati e non intercambiabili.

| Asse | Contenuto | Perché è necessario |
| --- | --- | --- |
| Identità e custodia | tenant, fascicolo, hash SHA-256, versione, autore, origine, path tenant-aware, data acquisizione | impedisce scambi, perdite, duplicazioni e contaminazione fra studi. |
| Contenitore e discendenti | EML/PEC, ZIP/RAR/ARJ, P7M/SMIME, documento originale, elementi figli, percorso di estrazione, profondità | una busta PEC o ZIP non è un singolo allegato; l'originale non deve sparire dopo l'estrazione. |
| Integrità tecnica | MIME rilevato, magic bytes, firma digitale, cifratura, malware/limiti, OCR, pagine e warning | l'estensione non è una prova del formato né della leggibilità. |
| Provenienza giuridica | studio, cliente, controparte, ufficio giudiziario, PEC, PST/PolisWeb, PAT/SIGA, PTT/SIGIT, PDP/PPT, autorità, documento generato | il metadato ufficiale di canale prevale sulla sola inferenza testuale. |
| Famiglia e rito | giurisdizione, materia, sottobranche, rito, grado, fase | lo stesso termine “ricorso” ha significato diverso in civile, tributario, amministrativo o penale. |
| Natura e tipo puntuale | atto di parte, provvedimento, atto d'ufficio, prova, procura, ricevuta, pagamento, documento interno; codice controllato di tipo | evita l'appiattimento in “atto”, “allegato” o “documento”. |
| Ruolo e relazioni | atto principale, allegato, prova notifica, procura, ricevuta, fuori busta; padre/figlio, deposito, udienza, termine, provvedimento impugnato | rende possibile indice, deposito, alert, navigazione e audit senza ricostruzioni manuali. |
| Decisione | proposta/confermata/corretta/da revisionare/duplicato/non leggibile, confidenza, regole, estratti, pagine e revisore | un algoritmo non può trasformare un'incertezza in un fatto processuale. |

## Matrice integrale delle famiglie di fascicolo

La matrice comprende sia i riti principali sia le materie che producono documenti caratteristici. Un fascicolo può avere più famiglie: per esempio mediazione, giudizio civile, appello ed esecuzione rimangono collegati ma non confusi.

### 1. Documenti trasversali a ogni fascicolo

- Identità, rappresentanza e poteri: procura alle liti, delega, mandato, nomina/revoca, documento di identità, codice fiscale, visure, certificati e autorizzazioni.
- Corrispondenza e notifiche: messaggio PEC/EML, ricevuta di accettazione, RdAC, mancata consegna, esito controlli, accettazione/rifiuto cancelleria, relata, attestazione di conformità, prova notifica e busta di trasporto.
- Atti dell'ufficio: comunicazioni, verbali, decreti, ordinanze, sentenze, avvisi, inviti a regolarizzare, certificazioni e copie.
- Pagamenti: contributo unificato, ricevuta telematica PagoPA/RT XML, marca/bollo, nota iscrizione a ruolo, spese, esenzioni, patrocino a spese dello Stato, SIAMM/liquidazioni.
- Prove comuni: contratti, scritture private, fatture, bonifici, estratti conto, fotografie, chat/e-mail, registrazioni, tabulati, documenti tecnici, perizie/CTU/CTP, dichiarazioni e certificati.
- Gestione interna: indice, fascicolo di parte, checklist, note di studio, bozze e documenti generati. Questi non possono essere scambiati per originali d'ufficio.

### 2. Civile ordinario, rito semplificato e giudice di pace

Procedimenti: cognizione ordinaria e semplificata, responsabilità e danni, contratti, proprietà e diritti reali, locazioni e condominio, successioni non volontarie, bancario/assicurativo, consumo, digitale/IP/privacy, recupero crediti e cause davanti al giudice di pace.

Documenti: citazione, ricorso, comparsa di risposta, chiamata del terzo, domanda riconvenzionale, intervento, memorie integrative, note scritte, conclusionali, repliche, istanze istruttorie, capitoli di prova, interrogatorio, testimonianze, consulenze, verbali, ordinanze, sentenze, notifiche, appelli, ricorsi in cassazione e relativi provvedimenti.

### 3. Monitorio, convalida, possessorio, cautelare e urgenza

Procedimenti: decreto ingiuntivo e opposizione, sfratto/convalida, reintegrazione/manutenzione, procedimento cautelare uniforme, art. 700 c.p.c., sequestri, ATP e istruzione preventiva.

Documenti: ricorso monitorio, prove scritte del credito, decreto ingiuntivo, provvisoria esecuzione, notifica, opposizione, intimazione/licenza, citazione per convalida, verbale, ordinanza di rilascio, ricorso cautelare, decreto inaudita altera parte, reclamo, sequestro, provvedimento urgente, ricorsi possessori, relazioni e accertamenti tecnici.

### 4. Esecuzioni, vendite e UNEP

Procedimenti: mobiliare, immobiliare, presso terzi, obblighi di fare/non fare, ricerca telematica dei beni, opposizioni, vendite PVP, delega e distribuzione.

Documenti: titolo esecutivo, attestazione/conformità, precetto, pignoramento, nota di iscrizione a ruolo, istanza 492-bis, dichiarazione del terzo, istanza di vendita/assegnazione, ordinanza di vendita/delega, avvisi, custodia, perizia/stima, offerte e ricevute PVP, verbali, piano di riparto, opposizioni all'esecuzione/agli atti, ordinanze e provvedimenti conclusivi.

### 5. Lavoro e previdenza

Procedimenti: licenziamento, retribuzioni, inquadramento, discriminazione, infortuni, previdenza e ATP previdenziale.

Documenti: ricorso del lavoro, memoria/costituzione, contratto e lettere di assunzione, buste paga/CU, estratti contributivi, lettere disciplinari/licenziamento, certificazioni e cartelle sanitarie, diffide, verbali conciliativi, certificati INPS/INAIL, CTU medico-legale, appello, sentenze e provvedimenti.

### 6. Famiglia, minori, persone, successioni e volontaria giurisdizione

Procedimenti: separazione, divorzio, affidamento e responsabilità genitoriale, alimenti, filiazione, adozione, amministrazione di sostegno, tutela/curatela, successioni e autorizzazioni di volontaria giurisdizione.

Documenti: ricorsi e memorie, dichiarazioni reddituali/patrimoniali, certificati di stato civile, relazioni dei servizi sociali, ascolto del minore, CTU, provvedimenti urgenti, accordi, decreti e sentenze; inventari, autorizzazioni alla vendita, proroghe, nomine, rendiconti e atti di straordinaria amministrazione. I documenti sensibili devono inoltre mantenere le policy di minimizzazione e di accesso per ruolo.

### 7. Crisi d'impresa, insolvenza, societario e commerciale

Procedimenti: composizione negoziata, concordato, accordi/ristrutturazione, liquidazione giudiziale, sovraindebitamento, procedure anteriori transitorie; governance e contenzioso societario.

Documenti: domanda di accesso, bilanci, registri e scritture, elenco creditori/debiti/beni, attestazioni, piani/proposte, relazioni di professionisti/curatore/commissario, stato passivo e insinuazioni, osservazioni, decreti/sentenze, vendite/riparti; statuti, verbali organi societari, libri sociali, visure, patti, delibere e documentazione contabile.

### 8. Bancario, finanziario, assicurativo, consumo e autorità settoriali

Procedimenti: ABF, ACF, arbitro assicurativo, reclami bancari/assicurativi, ConciliaWeb/AGCOM, Garante privacy, autorità e organismi di settore.

Documenti: reclamo, risposta dell'intermediario/autorità, ricorso, controdeduzioni, contratti, estratti conto/scalari, rendiconti, evidenze tecniche, provvedimenti/sanzioni, verbali, accordi e ricevute di piattaforma. Non devono essere impropriamente marcati come atti PCT.

### 9. Amministrativo e appalti

Procedimenti: TAR, Consiglio di Stato/CGARS, silenzio, accesso, cautelare, ottemperanza, appalti e concessioni.

Documenti: ricorso introduttivo, ricorso incidentale, motivi aggiunti, intervento, istanze cautelari, memorie, repliche, documenti, moduli PAT/Formweb, bando, disciplinare, capitolato, offerta, verbali di gara, provvedimenti di ammissione/esclusione/aggiudicazione, ordinanze, sentenze, appelli, revocazione, opposizione di terzo, atti di ottemperanza e ricevute SIGA.

### 10. Tributario

Procedimenti: ricorso, reclamo-mediazione, sospensione, controdeduzioni, memorie/documenti, primo e secondo grado, cassazione.

Documenti: avviso di accertamento/liquidazione, cartella, intimazione, atto di recupero, avviso bonario, ricorso-reclamo, istanza/mediazione, prova di notifica, deposito, controdeduzioni, memorie, repliche, produzione documentale, istanza cautelare, verbali, decreti, ordinanze, sentenze, appello, ricorso in cassazione, quietanze e ricevute SIGIT/PTT.

### 11. Penale e indagini

Procedimenti: notizia di reato, indagini preliminari, misure cautelari, incidente probatorio, udienza preliminare, riti speciali, dibattimento, persona offesa/parte civile, impugnazioni, esecuzione e sorveglianza.

Documenti: denuncia, querela, procura speciale, nomina/revoca difensore, elezione di domicilio, istanze/memorie/richieste difensive, deposito difensivo, atti ex art. 415-bis, opposizione all'archiviazione, atti per misure, liste testi, costituzione parte civile, documenti e indagini difensive, verbali, sentenze/decreti, appello/cassazione/reclami, incidente di esecuzione. Il catalogo non costruirà a mano una lista incompleta: importerà la tassonomia vigente degli atti PDP/PPT e la versionerà con fonte e data.

### 12. ADR, stragiudiziale e arbitrato

Procedimenti: mediazione, negoziazione assistita, arbitrato, conciliazioni settoriali, diffide e transazioni.

Documenti: domanda, adesione, convocazione, verbali di primo incontro/prosecuzione, proposta, verbale positivo/negativo/mancata partecipazione, accordo, autentiche, nullaosta/autorizzazioni, lodo, clausola compromissoria, diffida, riscontro, transazione, prova invio e consegna.

### 13. Immigrazione, cittadinanza, proprietà intellettuale, digitale e procedimenti europei

Comprende atti amministrativi e ricorsi collegati su protezione internazionale/cittadinanza, UIBM, diritto d'autore, dominio digitale e strumenti UE, inclusi ingiunzione europea e procedimenti standardizzati. I moduli UE, le traduzioni, le apostille/legalizzazioni e i certificati sono tipi controllati, non semplici allegati.

### 14. Giurisdizioni speciali e nuove materie

Corte dei conti, costituzionale e ogni procedimento per cui non è ancora disponibile un connettore governato restano comunque coperti: la famiglia `giurisdizione_speciale` conserva documenti e relazioni, ma non dichiara depositabilità o conformità fino alla registrazione della fonte e del canale ufficiale applicabile.

## Formati, firme e contenitori

L'acquisizione deve riconoscere contenuto effettivo e non l'estensione. Formati minimi: PDF/PDF firmato PAdES, P7M/SMIME, DOC/DOCX/ODT/RTF, TXT/CSV/XLS/XLSX, XML/HTML, EML/MIME/MSG, ZIP/RAR/ARJ, JPG/JPEG/PNG/TIFF/TIF/BMP/GIF, DICOM, MPEG-2/MPEG-4/AVI e MP3/FLAC/RAW/WAV/AIFF. La busta e ogni elemento estratto restano collegati, con limite di dimensione/profondità e stato di sicurezza. Audio/video restano prove tecniche fino a trascrizione o revisione: il sistema non deve fingere di averne compreso il contenuto.

## Fonti primarie esterne consultate

1. [PST — Deposito generico di un atto](https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC239&modelId=12): atto PDF, allegati ammessi, XML specifico, RdAC, mancata consegna, controlli automatici e accettazione di cancelleria.
2. [PST — Documentazione](https://pst.giustizia.it/PST/it/documentation.page): indice ufficiale delle specifiche DGSIA, incluso il provvedimento del 7 agosto 2024.
3. [Ministero della Giustizia — circolare 6 settembre 2024](https://www.giustizia.it/giustizia/it/mg_1_8_1.page?contentId=SDC1422812): PDT, atti difensivi penali e allegati multimediali/archivi ammessi.
4. [Giustizia amministrativa — regole tecnico-operative PAT 2025](https://www.giustizia-amministrativa.it/documents/20142/74204502/Pubblicazione%2BRegole%2Btecnico-operative%2BPAT.pdf/db2b8d35-4e88-c32a-a7c6-15715348d34b?t=1748969121419): deposito e adempimenti PAT per primo/secondo grado e ricorso straordinario.
5. [Giustizia tributaria — D.Lgs. 546/1992, art. 23](https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?articolo=Articolo+23&codiceOrdinamento=0000000000000230000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7BECD81E71-D37B-4722-AA36-116B5BCB2232%7D) e [circolare n. 1/E](https://def.giustiziatributaria.gov.it/DocTribFrontend/getContent.do?id=%7B5B20B562-2745-4BBF-AF80-1A2994DEF5E1%7D): ricorso, controdeduzioni, memorie e documenti PTT restano tipi distinti.
6. [Ministero — decreto 30 giugno 2026 su volontaria giurisdizione](https://www.giustizia.it/giustizia/page/it/provvedimento_ministeriale_selezionato?contentId=SDC1511030): perimetro nazionale dei depositi personali telematici e procedimenti da classificare.
7. [Ministero — disciplina mediazione civile](https://www.giustizia.it/giustizia/it/mg_1_2_1.page?contentId=SAN92842): domanda, proposta, verbali e accordi hanno valore autonomo.
8. [Portale europeo della giustizia elettronica — ingiunzione europea](https://e-justice.europa.eu/topics/money-monetary-claims/european-payment-order_it): moduli standard e fasi dell'ingiunzione transfrontaliera.

## Protocollo di lettura del fascicolo: domande che il sistema deve saper porre

Il catalogatore non può limitarsi a riconoscere un'etichetta. Per ciascun
documento deve costruire una scheda argomentata, ripetendo le domande che un
legale specializzato pone quando apre un fascicolo. Le risposte automatiche
sono sempre distinte fra fatto osservato, inferenza tecnica e valutazione
giuridica da confermare.

| Domanda operativa | Evidenze da ricercare | Esito corretto del sistema |
| --- | --- | --- |
| Che documento è davvero? | magic bytes, MIME, firma, contenitore, testo, intestazione, metadati del portale e relazione con altri file | tipo documentale e livello di confidenza; se i segnali confliggono, `da verificare`, mai una classificazione forzata. |
| Da quale procedimento e fase proviene? | organo, numero di ruolo/pratica, registro, canale, data di deposito/comunicazione, riferimenti a atto o provvedimento precedente | famiglia, rito, fase e canale separati; il fascicolo può avere procedimenti collegati senza fondere i relativi atti. |
| Chi l'ha formato, firmato, ricevuto o notificato? | autore, destinatario, procuratore, delega, certificati e firme, ricevute PEC/portale, relata e indirizzi | ruoli e catena di provenienza; validità di firma e notifica come verifica tecnica o richiesta di controllo, non come presunzione. |
| Quale fatto o requisito prova, contesta o attua? | oggetto, fatti allegati, domande, eccezioni, conclusioni, importi, beni, rapporti contrattuali, riferimenti probatori | collegamenti espliciti `afferma`, `prova`, `contesta`, `richiede`, `decide`, `esegue`; nessuna valutazione autonoma di veridicità. |
| Da quale norma, procedura o precedente è governato? | fonte primaria vigente, regolamento/istruzione dell'autorità, decreto, atto di portale, massimario o provvedimento ufficiale | fonti versionate con ambito ed efficacia temporale; il sistema mostra la base e segnala conflitti, senza inventare una regola. |
| Che rapporto ha con gli altri documenti? | allegato, versione, originale/copia, ricevuta, busta, atto principale, risposta, replica, provvedimento, pagamento o esecuzione | grafo del fascicolo e ordine cronologico italiano; deduplicazione per impronta senza perdere gli originali o le diverse provenienze. |
| È completo, integro e tempestivo? | pagine, allegati dichiarati, hash, firma, marca temporale, ricevute, date di evento, decorrenze dichiarate e scadenze configurate | checklist di completezza e alert su dati mancanti; il termine è proposto solo quando la fonte e il dies a quo sono identificati e resta da validare. |
| Produce un effetto processuale o sostanziale? | natura del provvedimento, stato di portale, esito, esecutorietà, sospensione, accordo, omologa, iscrizione o pagamento | effetto solo come `dichiarato dalla fonte`/`da verifica professionale`; nessun invio, firma, deposito o aggiornamento di stato vincolante senza conferma umana. |
| Ci sono contraddizioni, anomalie o rischi? | incongruenze fra importi/date/parti, documento illeggibile, firma assente, fonte superata, duplicati non identici, contenitore ostile, file mancante | coda di revisione con spiegazione, evidenze e priorità; mai correzione o cancellazione automatica del documento originale. |
| Qual è il prossimo atto utile? | stato documentato, procedimento, relazioni, scadenze validate, regole di canale e atti richiesti | proposta non vincolante con fonte, prerequisiti e documenti mancanti; l'avvocato approva prima di generazione, firma o trasmissione. |

Questo protocollo deve valere per ogni famiglia e sottofamiglia, compresi
fascicoli misti (per esempio reclamo assicurativo, mediazione, causa civile ed
esecuzione) e fonti con valore diverso. La conoscenza non sarà un blocco di
testo: ogni risposta conserverà documento, estratto/evidenza, fonte normativa o
tecnica, versione della regola, data e operatore che l'ha confermata.

### Giurisprudenza: conoscenza utile, mai una citazione inventata

La giurisprudenza va trattata con la stessa disciplina delle fonti normative:
non una massa da cui il sistema estrapola principi in silenzio, ma risultati
tracciabili dal fascicolo. Le fonti istituzionali acquisite sono le rassegne e
raccolte dell'Ufficio del Massimario e del Ruolo della Corte di cassazione, la
ricerca EUR-Lex per la Corte di giustizia UE e HUDOC per la Corte EDU.

Per ogni decisione o massima proposta, il motore deve conservare `organo`,
`sezione`, `numero`, `data`, `ECLI o identificativo ufficiale`, `URL`,
`testo o estratto localizzato`, `materia`, `questione`, `esito`, `grado di
vincolatività/pertinenza`, `lingua`, `versione` e `data di verifica`. Una
rassegna o una massima non sostituisce il provvedimento quando il fascicolo
richiede il testo integrale; una traduzione non ufficiale va dichiarata come
tale. Il sistema può segnalare precedenti potenzialmente pertinenti e mostrare
il collegamento argomentato a fatti/norme del fascicolo, ma non deve qualificare
come "orientamento consolidato" un risultato isolato, superato o non verificato
dall'avvocato.

## Governo delle fonti: autorevolezza prima della quantità

Ogni regola del catalogatore avrà un riferimento a una o più fonti, ma non tutte le fonti hanno lo stesso peso. Il motore deve applicare questa gerarchia, registrare la versione e mettere in revisione qualunque conflitto.

| Priorità | Fonte | Uso nella catalogazione |
| --- | --- | --- |
| 1 | Normattiva, Gazzetta Ufficiale, regolamenti UE su EUR-Lex | definiscono rito, atti, fasi, termini e qualificazioni normative vigenti. |
| 2 | Provvedimenti, specifiche e portali dell'autorità competente: Ministero/PST-PDP, Giustizia amministrativa/PAT, Giustizia tributaria/PTT, PVP, ministeri e autorità indipendenti | definiscono tipi/codici di canale, format, ricevute, buste e vincoli tecnici di deposito. |
| 3 | Giurisprudenza ufficiale di Cassazione, Corte costituzionale, Consiglio di Stato, CGUE/CEDU e banche pubbliche delle giurisdizioni | chiarisce interpretazione e segnali di riconoscimento; non modifica autonomamente il tipo tecnico di deposito. |
| 4 | Manuali pubblicati dall'ente, moduli ufficiali e istruzioni di servizio | completano alias, sequenze e campi obbligatori quando coerenti con le fonti superiori. |
| 5 | Template e checklist IUSENTRA, prassi di studio e correzioni umane | arricchiscono sinonimi e casi pratici; non possono prevalere su una fonte ufficiale. |

La fonte viene memorizzata con `id`, URL, autorità, livello, stato di vigenza, data di verifica, versione/pubblicazione, hash dello snapshot e ambito. Una regola non può essere marcata `certa` se manca una fonte di priorità 1 o 2 pertinente, se lo snapshot non è verificato o se due fonti applicabili sono in conflitto.

### Piano di acquisizione delle fonti mancanti

Il repository contiene già un registro di 118 fonti ufficiali e snapshot del 02/06/2026. Prima dell'implementazione vengono aggiunti al manifest e scaricati nel repository centrale delle fonti — mai nel tenant di uno studio — i documenti mancanti o aggiornati per:

- DGSIA/PST 2024 e successive specifiche PCT/PPT, schema di busta e cataloghi ufficiali degli atti;
- PAT 2025 e documentazione Formweb/SIGA;
- PTT/SIGIT, D.Lgs. 546/1992 vigente, D.M. 163/2013 e specifiche tecniche applicabili;
- disciplina e specifiche del portale di volontaria giurisdizione 2024-2026;
- CPP, D.Lgs. 150/2022 e catalogo PDP/PPT vigente degli atti difensivi;
- CPC, CCII, mediazione e negoziazione, PVP ed esecuzioni;
- CPA, codice appalti e fonti ANAC per appalti; fonti ufficiali di Banca d'Italia/ABF, Consob/ACF, IVASS/AAS, AGCOM/ConciliaWeb, Garante, UIBM, Ministero dell'Interno e portale e-Justice per i rispettivi fascicoli.

L'acquisizione non consiste nel copiare testo normativo nei documenti dei clienti: crea snapshot verificabili, con impronta e data, da cui derivare regole aggiornabili. A ogni aggiornamento della fonte il sistema confronta la versione, segnala le regole da riesaminare e non modifica retroattivamente classificazioni confermate senza audit e nuova proposta.

### Esiti verificati delle fonti tecniche acquisite

Il registro `docs/specs/ministero/fonti_ufficiali/2026-08-24/README.md`
collega quarantacinque nuove copie ufficiali all'URL, alla finalità e alla rispettiva
impronta SHA-256. La lettura tecnica produce requisiti implementativi concreti,
non semplici collegamenti bibliografici:

- Le specifiche DGSIA del 7 agosto 2024, con le due rettifiche ufficiali,
  separano atto principale, allegati, `DatiAtto.xml`, busta e ricevute. Per il
  PCT/PDP il catalogo deve rendere consultabile quel rapporto, riconoscere che
  un atto principale è PDF/PDF-A trasformato da testo e che un allegato può
  avere formati ulteriori autorizzati dal canale. Le rettifiche impongono di
  registrare la nomenclatura `atto.enc` e di non dedurre dallo stato PDP di una
  denuncia/querela un'iscrizione del procedimento che la fonte non dichiara.
- Le regole PAT 2025 distinguono il flusso Formweb, i suoi dati obbligatori e
  opzionali, il passaggio `Richiesta e Allegati`, il riepilogo e la firma PAdES
  estesa ai documenti; il catalogo deve quindi distinguere atto, allegato,
  campo/formulario e ricevuta di quel canale, conservando giurisdizione e fase.
- Il decreto PAT n. 38/2026 fissa limiti specifici per Formweb: massimo 50 file
  e 300 MB complessivi, con limite di 300 MB per singolo file. Il profilo PAT
  va quindi applicato soltanto alla coda di acquisizione di quel canale e non
  deve indebolire i limiti anti-abuso dell'import ordinario dello studio.
- Le specifiche della volontaria giurisdizione distinguono ricorso, documento
  allegato, firma, busta e ricevuta, impongono il canale del portale dedicato
  per il depositante personale e descrivono gli stati `In attivazione`,
  `Attivo`, `Chiuso` e `Annullato`. Tali stati sono dati di deposito, non
  sinonimi della fase giuridica o della classificazione dell'allegato.
- La sequenza dei decreti di volontaria giurisdizione del 2025 e del 2026 prova
  che il perimetro dei procedimenti e degli uffici varia nel tempo. Le regole
  di canale devono avere decorrenza e ambito, senza applicare retroattivamente
  il deposito personale a fascicoli o date non comprese.
- Il manuale ANAC FVOE individua fascicoli di gara, documenti, associazioni,
  notifiche, dettaglio e stati di utilizzabilità; i documenti di requisito
  generale/speciale restano oggetti autonomi e possono collegarsi a più gare
  nel periodo di efficacia. Il catalogo deve quindi distinguere identità
  dell'operatore, gara/CIG, documento, associazione e stato di comprova.
- Le specifiche PVP 1.2 individuano autonomamente avviso di vendita, ordinanza
  di vendita, planimetrie, perizie, fotografie, ricevute di pagamento e
  certificazioni. La relazione fra bene, lotto, esperimento, annuncio e suoi
  allegati deve essere strutturale; il limite e i formati ammessi dal portale
  valgono per quella specifica acquisizione, non come permesso indiscriminato
  per ogni upload dell'applicazione.
- Le fonti PDP/PPT confermano che, nel fascicolo penale, atti difensivi e
  allegati multimediali possono avere natura e formati propri. Il motore deve
  riconoscere anche il contenitore e il contenuto effettivo, applicare limiti di
  sicurezza contestuali e inoltrare l'elaborazione pesante a job asincroni.
- Le fonti PTT, volontaria giurisdizione, CCII ed e-Justice confermano che
  parole ricorrenti quali `ricorso`, `memoria`, `istanza` o `provvedimento` non
  identificano da sole il documento: rito, organo, fase, canale e modulo
  ufficiale sono assi indispensabili per una catalogazione affidabile.
- Le fonti INPS distinguono riesame e ricorso amministrativo previdenziale da
  un ricorso giudiziale: provvedimento lesivo, motivi, delega, identità,
  istruttoria, deliberazione ed eventuale documentazione integrativa sono tipi
  e relazioni esplicite; la PEC è un canale residuale, non una classe di atto.
- Le fonti ABF, ACF e AGCOM descrivono fascicoli elettronici a contraddittorio
  sequenziale. Reclamo presupposto, ricevuta/prova di presentazione, ricorso o
  istanza, procura e identità, controdeduzioni, repliche, controrepliche,
  integrazioni e decisione o verbale devono restare documenti diversi, con il
  rispettivo canale e termine: non una catena di PDF indistinta.
- La fonte del Garante privacy separa reclamo, segnalazione, integrazione,
  richiesta di informazioni o esibizione, archiviazione e provvedimento. Il
  sistema deve preservare questa distinzione e non inferire il merito o la
  liceità di un trattamento dal solo contenuto estratto.
- Le fonti del Ministero dell'interno e MIMIT/UIBM mostrano che anche i
  fascicoli immigrazione e proprietà industriale hanno oggetti verticali:
  domanda/formalizzazione, colloquio, decisione e ricorso per la protezione;
  domanda, descrizione, disegni/logo, priorità, istanze connesse, pagamento e
  ricevuta per titoli di proprietà industriale. Tali profili richiedono
  vocabolari propri e metadati di portale, non l'etichetta generica
  `documento amministrativo`.
- La fonte ministeriale sulla mediazione conferma che domanda, verbale di
  primo incontro o conclusivo, proposta, accordo, omologa e titolo esecutivo
  sono oggetti e stati diversi. L'accordo allegato e il verbale non vanno
  fusi; firme, assistenza degli avvocati e decreto di omologa sono evidenze da
  registrare e sottoporre a verifica, mai dedotte automaticamente.

Due endpoint del portale tributario hanno restituito un errore tecnico
dell'autorità, non il documento richiesto. Le risposte sono conservate
separatamente come prova di acquisizione non valida e non alimentano alcuna
regola. La lacuna di fonte primaria è stata chiusa con le pubblicazioni
ufficiali della Gazzetta del 4 agosto 2015, della modifica del 28 novembre 2017
e dell'aggiornamento del 20 aprile 2023, tutte con URL e impronta nel manifest
`docs/specs/ministero/fonti_ufficiali/2026-08-24/README.md`.

Ne deriva una scelta architetturale vincolante: le estensioni abilitate dal
lettore non saranno usate come catalogo giuridico né estese globalmente per
seguire un singolo portale. Ogni acquisizione avrà profilo di canale, tipo MIME
e magic bytes verificati, limiti anti-bomba e anti-malware, relazione
padre/figlio per buste e archivi e un esito esplicito di elaborazione o
revisione.

## Fonti interne e riuso obbligatorio

- `pct/template_atti_catalogo.py` e `pct/checklist_atti.py`: 708 template distribuiti in 25 aree e 47 sottobranche; diventano vocabolario/alias, non un duplicato di record.
- `pct/template_atti_legal_sources.py`: 118 fonti ufficiali versionate (`2026.06.06.template-fonti-ufficiali.v2`) già collegate alle materie.
- `pct/fascicolo_document_catalog.py`: classificatore deterministico vigente. Resta compatibile ma è insufficiente: 17 soli `TipoDocumento`, regole nome/OCR e nessuna persistenza completa di rito, fase, relazione e revisione.
- `pct/document_intelligence/`: acquisizione tenant-aware, hash, versioni ed estrazione da PDF, Office, immagini/OCR, EML/MSG, ZIP e P7M. Va esteso, non sostituito.
- `pct/sql/20260521_legal_document_understanding.sql`: contiene `document_classifications` con tipo, area, rito, fase, procedimento, portale, confidenza e motivazione. È il punto di riuso primario; dalla ricognizione non emerge un equivalente PostgreSQL omonimo, pertanto la parità è una precondizione di rilascio.
- `pct/polisWeb.py`, `pct/pat.py`, `pct/sigit.py`, `pct/pdp_penale_workflow.py`, `pct/pst_catalog.py` e relative fixture/test: fonti operative per metadati di canale e codici di deposito.
- `docs/specs/ministero/fonti_ufficiali/2026-06-02/`: baseline scaricata con URL e impronte. Le fonti 2025/2026 mancanti saranno aggiunte come snapshot governati, non come contenuti sparsi nei fascicoli degli studi.

### Audit di copertura delle fonti e dei modelli interni

Il registro `TEMPLATE_ATTI_LEGAL_SOURCES` contiene 118 fonti: 56 normative,
11 normative secondarie, 11 telematiche, 27 di autorità, 10 deontologiche,
2 di ordinamento professionale e una collegata. I 708 template disponibili
coprono 25 aree editoriali, dal civile alla crisi, da penale e tributario a
immigrazione, IP/digitale, privacy e tutela del consumatore. Sono una base
preziosa, ma il catalogo non può assumerne automaticamente la completezza:

Il minimo vincolante fissato per questa verifica è di **tre fonti ufficiali,
indipendenti e pertinenti** per ogni profilo applicabile. La triade non è un
conteggio meccanico di link: deve includere fonte normativa vigente, fonte del
canale/procedura o dell'autorità competente e fonte di controllo/interpretazione
istituzionale. Per gli atti interni di studio sostituisce il canale processuale
una fonte professionale, deontologica o privacy pertinente; non viene inventata
una procedura giudiziaria inesistente.

| Famiglia da catalogare | Copertura già individuata | Azione prima della regola definitiva |
| --- | --- | --- |
| Civile, monitorio, cautelare, esecuzioni e PCT | CPC, fonti PCT/PST e varie fonti specifiche già associate; nuove specifiche DGSIA 2024 archiviate. | Mappare codici di atto, ricevute e struttura busta ai tipi puntuali; separare atto da allegato e prova. |
| Famiglia, persone, successioni e volontaria giurisdizione | molte fonti sostanziali/processuali; tre riferimenti `VGS` nel registro e due nuove fonti tecniche del portale. | Collegare il provvedimento DGSIA, i decreti di estensione 2024–2026 e l'elenco dei procedimenti a un vocabolario dedicato. |
| Lavoro e previdenza | ampia base normativa/giurisprudenziale e 38 modelli fra area lavoro/previdenza. | Formalizzare ricorso, memoria, verbali, CTU/ATP, provvedimenti e documentazione previdenziale. |
| Penale e PDP/PPT | CPP, D.Lgs. 150/2022, PDP/PPT, D.M. 206/2025 e 59 modelli fra Penale/Diritto penale. | Acquisire e versionare il catalogo ufficiale degli atti PDP per ruolo; distinguere atti difensivi, richiesta accesso, querela, prova e stati. |
| Amministrativo e PAT | CPA, PAT/Formweb e 27 modelli amministrativi; fonti PAT 2025 e limiti 2026 acquisiti. | Codificare moduli/Formweb, ricorso, motivi aggiunti, istanze, memorie, provvedimenti e ricevute; associare limiti al solo canale PAT. |
| Appalti e ANAC | Codice contratti, PCP ANAC e precontenzioso sono già nel registro, ma la mappatura usa il prefisso amministrativo generale e lascia l'area appalti quasi non esplicitata. | Creare famiglia/sottobrancha `APPALTI` e catalogo di bando, disciplinare, capitolato, offerta, verbale, FVOE, provvedimento e parere ANAC. |
| Tributario e PTT/SIGIT | D.Lgs. 546/1992, D.Lgs. 220/2023, D.M. 163/2013 e la triade G.U. 2015/2017/2023 delle specifiche PTT sono acquisiti; i prefissi `TRIB`/`TRI` restano da uniformare. | Applicare l'alias controllato a ogni modello, distinguendo ricorso, controdeduzioni, memorie, appello, istanze e ricevute. |
| Crisi, concorsuale e PVP | CCII, correttivo, BDAG/PVP e 15 modelli crisi; nuove specifiche PVP 1.2 acquisite. | Modellare procedure, lotti, esperimenti, avvisi, perizie, offerte, pagamenti e certificazioni come relazioni. |
| Bancario, finanziario, consumo e ADR | fonti civili, UE, ABF/autorità e 53 modelli bancario/consumo/ADR. | Separare reclami, decisioni ABF/ACF, contratti, estratti, mediazione, negoziazione e documenti probatori. |
| Societario, immobiliare, IP/digitale, privacy e immigrazione | fonti di base e 47 modelli specifici. | Estrarre i tipi documentali verticali da fonti UIBM, Garante, Ministero dell'interno e UE, mantenendo la relazione al rito giudiziale quando presente. |
| Stragiudiziale e gestione studio | fonti deontologiche/professionali e 49 modelli. | Tenere incarico, procura, preventivo, fattura e corrispondenza fuori dalla classificazione degli atti giudiziari pur collegandoli allo stesso fascicolo. |

Le righe che oggi hanno fonti generali ma non un prefisso o codice puntuale
sono lacune di modellazione, non coperture complete. La Fase 4.1 le chiuderà
con una matrice fonte → famiglia → rito → tipo → test, anziché gonfiare
indistintamente le regole a parole chiave.

## Decisioni architetturali vincolanti

### Una sola identità del documento, non tre archivi concorrenti

La ricognizione ha trovato tre componenti che oggi parlano di documenti:

| Componente esistente | Responsabilità corretta da preservare | Limite da non propagare |
| --- | --- | --- |
| `GestioneFascicoli` / tabella SQL `fascicoli` | documento effettivamente collegato al fascicolo, file tenant-aware, metadati di portale e tipo storico | il campo JSON `documenti_json` e l'enum a 17 tipi non possono contenere da soli una tassonomia processuale completa. |
| `pct/document_intelligence` / `fascicolo_documenti_ai*` | versioni, estrazione, OCR, testo per Lex, audit e ricerca del documento reale | è un indice tecnico, non un secondo archivio operativo né la sede di una decisione processuale. |
| `legal_document_ingestion` / tabelle `documents*` | funzioni riusabili di sniffing, estrazione sicura, catena di prova e revisione | oggi duplica lo schema, è SQLite-centrico e non deve diventare una terza fonte di verità. |

Il nuovo catalogo sarà un **sidecar SQL versionato**, riferito al documento già
presente nel fascicolo tramite la chiave `(tenant_id, fascicolo_id,
document_id, versione/hash)`. Non copierà i file, non salverà testo del cliente
nelle fonti normative e non utilizzerà il marcatore economico `pagamenti` come
sede della classificazione. Gli endpoint e i payload esistenti resteranno
compatibili; il vecchio `TipoDocumento` continuerà a essere valorizzato come
proiezione prudente del tipo puntuale confermato, mai come perdita di dati.

### Contratto dati proposto

| Entità SQL | Contenuto | Regola di sicurezza e parità |
| --- | --- | --- |
| `document_catalog_assignments` | versione attiva/storica della classificazione: famiglia, materia, giurisdizione, rito, procedimento, fase, natura, tipo puntuale, ruolo, stato, motore/regole e confidenza | tenant, fascicolo e documento obbligatori; una sola assegnazione attiva; storico append-only; SQLite e PostgreSQL con gli stessi vincoli e indici. |
| `document_catalog_candidates` | proposte alternative ordinate, punteggio e motivo del loro scarto o della loro conferma | nessun candidato diventa deposito, firma o invio; i candidati confliggenti richiedono revisione. |
| `document_catalog_evidence` | evidenza atomica: metadato portale, firma, MIME/magic bytes, testo/OCR con pagina/offset, nome, relazione, fonte o correzione umana | conserva locatore e impronta, non un copia-incolla superfluo del documento; il metadato ufficiale ha peso maggiore. |
| `document_catalog_relations` | legami semantici: allegato di, ricevuta di, prova notifica di, procura per, provvedimento impugnato, lotto/esperimento PVP, busta/contenuto | non duplica il legame fisico padre/figlio già presente nei contenitori; ogni legame indica origine, confidenza e revisione. |
| `document_catalog_reviews` | coda e decisione umana con autore, motivazione, data italiana in UI e audit | `unknown`, conflitto, bassa confidenza, firma/anomalia o impatto deposito restano aperti finché non valutati. |
| `catalog_rule_sets`, `catalog_rules`, `catalog_source_snapshots` | bundle versionato di tassonomia, regole deterministiche e fonti ufficiali con URL, impronta, ambito e stato | fonti applicative globali separate dai dati dello studio; alias o rettifiche di studio sono tenant-aware e non possono sovrascrivere una regola ufficiale. |
| `document_catalog_jobs` | lavoro asincrono, idempotenza, checksum/versione, tentativi, esito e tempi | nessuna scansione ricorsiva in pagina; limitazione per tenant e fascicolo, annullamento sicuro e nessun doppio processamento della stessa versione. |

Le migrazioni saranno create in coppia esplicita: una per SQLite e una per
PostgreSQL. L'audit di release confronterà tabelle, colonne, `CHECK`, indici e
query del repository; l'assenza dell'equivalente PostgreSQL della migrazione
`20260521_legal_document_understanding.sql` è una lacuna nota da chiudere,
non un dettaglio rinviabile.

### Tassonomia: assi distinti e codici controllati

Ogni documento avrà valori `unknown` leciti e visibili, oltre ai seguenti assi:

1. **origine e integrità:** caricamento studio, PEC, PST/PolisWeb, PAT/SIGA,
   PTT/SIGIT, PDP/PPT, PVP, autorità, editor; MIME rilevato, firma, contenitore,
   hash e stato di sicurezza;
2. **contesto giuridico:** famiglia, materia/sottomateria, giurisdizione, rito,
   organo, procedimento, grado e fase;
3. **natura del documento:** atto di parte, provvedimento, atto d'ufficio,
   prova, documento negoziale/amministrativo, ricevuta, pagamento, documento
   tecnico o interno;
4. **tipo puntuale e ruolo:** per esempio ricorso introduttivo, memoria 171-ter,
   comparsa, decreto ingiuntivo, relata, ricevuta RdAC/RdAC, avviso PVP, perizia,
   piano di riparto, querela, istanza PDP, controdeduzione tributaria; e ruolo
   quale atto principale, allegato, prova, procura, ricevuta o contenuto busta;
5. **relazioni e stato operativo:** padre/figlio, deposito, notifica, udienza,
   termine, lotto, provvedimento impugnato, proposta/da rivedere/confermata;
6. **provenienza della decisione:** regola ufficiale, metadato del portale,
   analisi tecnica, correzione umana o suggerimento AI non decisivo.

L'intelligenza artificiale, quando utilizzata, potrà proporre tipi e richiamare
evidenze ma non confermerà da sola valore probatorio, conformità per deposito,
necessità di firma, validità della notifica o invio.

### Compatibilità, prestazioni e anti-regressione

- L'import, l'apertura, il download, il lettore interno, la deduplicazione per
  identificativo portale/hash e la firma esistenti non saranno riscritti.
- Il classificatore `pct/fascicolo_document_catalog.py` resta un adattatore
  iniziale: le sue decisioni generano candidati/evidenze, non sostituiscono una
  conferma o cancellano classificazioni pregresse.
- Il reader di fascicolo continuerà a usare il file originale. L'indice OCR e
  i figli estratti saranno caricati su richiesta e con paginazione; non sarà
  introdotto rendering o OCR sincrono all'apertura della pagina.
- Ogni job usa hash e versione come chiave idempotente, batch piccoli,
  limiti per dimensione/profondità/numero elementi, scansione malware prima
  dell'estrazione e profili per canale. ZIP, RAR, ARJ, EML, P7M/SMIME e file
  multimediali sono trattati come contenitori o artefatti con stato esplicito;
  un formato non leggibile non diventa né invisibile né classificato a caso.
- Nessun contenuto del fascicolo è inviato a una fonte normativa o a un
  provider esterno per poter classificare. Eventuali modelli Lex rispettano le
  policy tenant e producono soltanto proposte auditate.

### Verifica dei motori PDF nella copia reale

Il 24/08/2026 è stato controllato il container locale reale `iusentra-app`,
healthy e pubblicato su `127.0.0.1:8080`: `pdftoppm` di Poppler è presente e
sono importabili `pypdfium2`, PyMuPDF, Tesseract e `pypdf`. L'assenza di
Poppler era limitata alla sessione di analisi esterna al container e non blocca
né il prodotto né il piano.

Resta una correzione preventiva da eseguire nel blocco 4.3: l'estrattore OCR
usa direttamente `pypdfium2`, ma tale pacchetto non è dichiarato esplicitamente
nel `requirements.txt` esaminato. La release dovrà dichiarare la dipendenza e
testarla nel build, oppure adottare in modo esplicito il renderer PyMuPDF già
dichiarato; una dipendenza transitiva presente per caso non sarà accettata come
garanzia di produzione.

## Lacune confermate e correzione prevista

1. Classificatore piatto basato in prevalenza su regex: non conosce sufficientemente rito, fase, sotto-tipo, provenienza e relazioni.
2. Vocabolari/template/fonti esistenti non alimentano ancora un record catalogo completo per ogni documento.
3. Occorre chiudere la parità della migrazione fra SQLite e PostgreSQL.
4. I metadati ufficiali di portale devono prevalere sulle inferenze locali deboli.
5. Il lavoro pesante deve essere asincrono, idempotente e a piccoli lotti: nessuna scansione ricorsiva in apertura del fascicolo e nessun lag UI.
6. Il renderer OCR PDF deve avere una dipendenza dichiarata e provata nel build, non soltanto disponibile nel container corrente.

## Piano tecnico prima del codice — Fase 4 articolata

| Blocco | Implementazione prevista | Uscita obbligatoria prima del blocco successivo |
| --- | --- | --- |
| 4.1 Fonti e vocabolario | Chiudere il registro di provenienza, mappare le 118 fonti e i 708 template a famiglie/riti, acquisire le fonti tecniche mancanti, definire codici stabili e alias controllati. | Audit di copertura per famiglia/canale, fonte normativa e tecnica, hash e revisione legale; nessuna regola senza provenienza. |
| 4.2 Contratti e migrazioni | Introdurre il sidecar SQL, il repository unico e le migrazioni SQLite/PostgreSQL; adattare senza rompere il `TipoDocumento` storico e gli endpoint esistenti. | Contratti dati/API, test di parità, tenant/RBAC/IDOR, import idempotente e rollback migration provati. |
| 4.3 Pipeline sicura | Collegare sniff MIME/magic bytes, firma, contenitori, estrazione/OCR, limiti per canale e job asincroni alla singola versione del documento. | Test per PDF nativo/scansione, ZIP PEC, EML, P7M, XML, immagini e formato non leggibile; nessun lag nel caricamento fascicolo. |
| 4.4 Regole e revisione | Applicare prima metadati ufficiali, poi regole versionate e infine proposte non decisive; salvare candidati, evidenze, conflitti e correzioni. | Dataset controllato per tutte le famiglie, casi ambigui e conflitti; correzione umana auditata e riproducibile. |
| 4.5 API e lettore | Esporre inventario, albero, filtri, dettaglio classificazione, coda revisione e azioni di conferma/correzione con API JSON tenant-aware. | OpenAPI aggiornato, autorizzazioni provate, nessun path assoluto o contenuto di altro tenant esposto. |
| 4.6 Workspace React | Integrare nel fascicolo una sola vista `Documenti e atti`: stato, origine, tipo, motivazione, albero, filtri, revisione e lettore interno. | Prova reale locale di ogni click, upload/import, salvataggio, reader PDF/ZIP e almeno un formato non PDF; desktop/tablet/mobile, scroll, hover e focus. |
| 4.7 Backfill governato | Pianificare i documenti storici per piccoli batch, evitare scansioni ricorsive, registrare copertura, errori e revisioni. | Dry-run, run su copia controllata, report SQL `source_of_truth`, nessun doppio record e nessun degrado rilevabile nell'uso. |
| 4.8 Rilascio e chiusura | Rieseguire regressioni mirate, golden journeys toccati, build e security/performance, poi commit/push/deploy. | Copia Docker reale su `127.0.0.1:8080` verificata materialmente, CI, Hetzner su stesso commit, `iusentra-app` unico e healthy, report completo. |

## Criteri di accettazione

- Nessun documento resta invisibile; ogni elemento ha tenant, fascicolo, origine, hash e stato.
- Un contenitore mostra e conserva i figli senza perdere l'originale.
- Una classificazione nota espone codice, famiglia, rito, fase, ruolo, confidenza, motivazione ed evidenze; una incerta è sempre visibile in revisione.
- Atti, provvedimenti, ricevute, prove di notifica e documenti di portale non sono più confusi.
- SQLite e PostgreSQL hanno identico contratto di dati e migrazioni; API e UI usano SQL come fonte di verità.
- L'elaborazione non rallenta apertura, ricerca o navigazione del fascicolo.
- La catalogazione non abilita automaticamente firma, deposito o invio.

## Stato della prova reale

Non verificato su macchina reale: è analisi documentata richiesta prima del codice. La prova reale inizierà dopo persistenza, pipeline, API e UI effettive.

## Implementazione Fase 4 — catalogo governato del fascicolo

Implementazione eseguita il 24/08/2026, prima della campagna di accettazione
materiale sulla copia locale:

- le migrazioni gemelle SQLite e PostgreSQL `20260824_fascicolo_document_catalog`
  introducono `rule_sets`, snapshot delle fonti, job, assegnazioni, candidati,
  evidenze e revisioni; ogni record ha tenant e fascicolo obbligatori;
- il repository usa SQL come fonte di verità e rifiuta esplicitamente la
  catalogazione strutturata se il tenant non ha SQL disponibile: JSON resta solo
  mirror/import storico e non sostituisce decisioni, conteggi o audit;
- il resolver copre 25 profili, 47 combinazioni famiglia/sottofamiglia e 708
  template. Per ogni profilo conserva almeno tre fonti indipendenti già
  verificate nel registro versionato. Dove il profilo non è determinabile, non
  assegna una classificazione silenziosa: crea una revisione umana esplicita;
- la pipeline riceve solo fonti documentali nominate dal fascicolo e usa hash e
  versione resolver per l'idempotenza. Non avvia ricerche web, OCR, estrazioni o
  scansioni ricorsive quando l'avvocato apre il fascicolo;
- le API JSON tenant-aware espongono lettura, aggiornamento esplicito e
  conferma/revisione; l'aggiornamento avvia prima l'indicizzazione documentale
  esistente e poi la catalogazione collegata allo stesso fascicolo;
- la sezione React `Catalogazione documentale` è stata inserita nel pannello
  `Documenti` del fascicolo. Mostra stato, origine, candidati, evidenze, fonti,
  motivazione e azioni di revisione, continuando a usare il lettore interno per
  il documento originale;
- lo storico delle revisioni consente decisioni successive sul medesimo
  documento, senza perdere l'audit delle decisioni già chiuse.

Guardrail tecnici eseguiti prima dell'accettazione utente:

- `python -m compileall -q pct/document_intelligence`;
- test resolver/pipeline SQLite, contratto migrazioni SQLite/PostgreSQL e API
  catalogazione su database SQLite reale di test: superati;
- migrazioni provate anche contro PostgreSQL 16 effimero: le sette tabelle del
  catalogo e l'inserimento del rule set sono riusciti, poi container e directory
  temporanea sono stati rimossi;
- `pnpm --dir frontend typecheck` e `pnpm --dir frontend build`: superati; il
  chunk della pagina Fascicoli è 319,64 kB, sotto il budget operativo di 500 kB.

Stato iniziale della prova reale: la copia Docker su `127.0.0.1:8080` è stata
ricostruita ed è healthy. Il completamento della prova materiale e del rilascio
è registrato nella sezione successiva.

## Chiusura della fase SQL, resolver, pipeline, API e React

Il 24/08/2026 la fase è stata completata nella copia Docker reale prima del
rilascio. Il fascicolo resta il contesto operativo unico: l'assegnazione SQL,
le evidenze, i candidati, le revisioni e il job riportano sempre tenant,
fascicolo, hash della versione documentale e versione del resolver. Nessun
archivio parallelo può diventare fonte di verità.

### Implementazione effettiva

- SQLite e PostgreSQL ricevono lo stesso contratto `20260824_fascicolo_document_catalog`:
  set di regole, snapshot delle fonti, job, assegnazioni, candidati, evidenze e
  storico delle revisioni. SQLite/PostgreSQL sono fonte di verità; i JSON sono
  soltanto mirror o import storico governato.
- Il resolver `2026.08.24.catalogo-fascicolo.v3` usa profilo, provenienza,
  nome, metadati ed evidenze. In particolare il nome verificabile
  `attestazione di conformità` prevale su un OCR ambiguo che contenga parole
  relative a provvedimenti: il documento non viene più confuso con una sentenza.
- La pipeline è idempotente per hash e versione del resolver. Recupera in una
  sola query gli snapshot già presenti, evita estrazioni ripetute quando il
  documento è invariato e raggruppa le scritture del catalogo in un'unica
  transazione. Il percorso normale non esegue scansioni ricorsive; solo lo
  script nominato di audit/riparazione può chiederle esplicitamente.
- L'API React aggiorna l'indicizzazione completa solo se manca un'assegnazione
  corrente o se è richiesto un retry. Il normale pulsante `Aggiorna
  catalogazione` legge il catalogo SQL già corrente, quindi non riavvia OCR,
  Lex o analisi dell'intero fascicolo.
- Il pannello React del fascicolo mostra contatori, stato, motivazione,
  candidati, evidenze, fonti e azioni di revisione. L'apertura del file resta
  nel lettore interno IUSENTRA, anche per la busta P7M mostrata nel caso reale.

### Guardrail e parità dati

Sono risultati superati: compilazione Python, 32 test mirati su resolver,
pipeline, migrazioni e casi catalogo, contratto API di catalogazione, typecheck
React e build Vite. Il test di regressione include: assenza di classificazione
silenziosa, storico revisioni senza vincolo che cancelli le decisioni precedenti,
nessuna nuova estrazione per documento invariato, nessuna scrittura dello
snapshot fonte invariato e una sola `COMMIT` per l'esecuzione iniziale della
pipeline. Il bundle `FascicoliPage` è 319,64 kB, sotto il budget di 500 kB.

La migrazione e il repository sono stati inoltre provati su PostgreSQL 16
effimero reale: schema, set di regole, batch e confronto degli snapshot fonti
sono riusciti; il container e la directory temporanea sono stati poi rimossi.

### Prova materiale sulla copia locale dell'utente

La prova è stata svolta nel browser integrato già autenticato della copia Docker
`http://127.0.0.1:8080`, fascicolo reale di prova `DD242366 — Fascicolo da
sincronizzare (prova PST)` con 14 documenti. Sono stati osservati e azionati
materialmente:

- catalogo con 14 documenti, tutti mantenuti in `Da verificare` perché nel
  fascicolo mancano area, branca e sottofamiglia verificabili; nessuna conferma
  è stata prodotta artificialmente;
- ricalcolo del documento `Attestazione_di_conformita_1025_2026.pdf`, ora
  mostrato come `Attestazione di conformità`, `Profilo da definire`, confidenza
  55%, con la motivazione prudenziale corretta;
- `Aggiorna catalogazione`, in stato normale, con ritorno al bottone abilitato
  senza rilanciare l'estrazione; il test API rende esplicito che il percorso
  comune non invoca il processo Lex;
- apertura e chiusura con click reale del documento
  `Decreto_28162803.pdf.p7m` nel lettore interno, con comandi `Scarica`,
  riduci, adatta e ingrandisci disponibili;
- passaggio del mouse e focus da tastiera sul controllo del lettore: hover e
  focus mantengono etichetta leggibile, contrasto e outline visibile;
- scroll materiale dall'inizio fino al fondo della pagina e ritorno all'inizio;
  alla larghezza reale disponibile di 891 px non è comparso overflow orizzontale
  (`scrollWidth` 876 px) e il pulsante di aggiornamento è rimasto visibile,
  leggibile e cliccabile.

La prova non convalida una classificazione giuridica assente: dimostra invece
che SQL, resolver, pipeline, API e React preservano il principio corretto di
revisione umana quando mancano dati processuali verificabili. Restano fuori da
questa singola prova il giudizio professionale dell'avvocato sul merito e
l'eventuale successiva compilazione dei dati di materia del fascicolo.

Riprova post-rebuild: il container `iusentra-app` è stato ricostruito dalla
sorgente finale, è healthy sulla porta 8080 e contiene il resolver v3. Dopo il
reload della medesima scheda reale sono stati cliccati nuovamente `Aggiorna
catalogazione` e il documento P7M nel lettore interno; il pulsante è tornato
abilitato, l'attestazione ha conservato il tipo corretto e il lettore si è
aperto e richiuso correttamente.
