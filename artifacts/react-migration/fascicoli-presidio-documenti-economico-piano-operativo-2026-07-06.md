# Fascicoli: presidio documenti, economia e adempimenti operativi

Data analisi: 06/07/2026.

Obiettivo: trasformare il controllo fascicoli da semplice visualizzazione a presidio operativo per l'avvocato. Il software deve classificare prima i documenti, poi decidere dove leggere i dati, poi proporre azioni concrete e verificabili: scadenze, note 127-ter, udienze, PEC, relata, contributo unificato, esenzioni, sentenze, liquidazioni, spese, parcelle/proforma e anomalie sui doppioni.

## Evidenza reale emersa sul server

Fonte dati verificata: SQLite tenant `studio-legale-giuseppe-montagnese`, `studio.db`, su server Hetzner.

- Fascicoli totali in SQL: 333.
- Prima ricognizione storica: 240 `IN_CORSO`, 50 `ARCHIVIATO`, 42 `DEFINITO`, 1 `APERTO`.
- Ricognizione corrente del 06/07/2026 dopo il presidio economico: 238 `IN_CORSO`, 61 `DEFINITO`, 33 `ARCHIVIATO`, 1 `APERTO`.
- Fascicoli non archiviati visibili in lista: 300.
- La card `Da archiviare` deve mostrare 61, cioè i fascicoli `DEFINITO` non ancora archiviati; i 33 già archiviati devono restare nota informativa separata.
- Parcelle/proforma in tabella SQL `parcelle`: 12.
- Proforma Lex Sentenza: 11 in `BOZZA`.
- Fascicoli `DEFINITO` con parcella collegata: 5.
- Fascicoli `DEFINITO` senza parcella collegata: 37.
- Il mirror JSON `fatturazione/parcelle.json` risulta vuoto; quindi la verità operativa è SQL, non JSON.

Verifica produzione aggiornata del 06/07/2026:

- API React `/api/v1/ui/fascicoli?view=economica&page_size=25`: `toArchive=61`, `archived=33`, `duplicatePractices=0`, `registeredAmount=14340`, `invoiceWorkTotal=67`, `invoicesToIssue=46`, `invoiceDraftsToReview=21`.
- UI produzione `https://app.iusentra.it/fascicoli?vista=economica`: card `Da archiviare 61`, nota `61 definiti, 33 già archiviati`, card `Parcelle 67`, nota `46 da emettere, 21 bozze da visionare`, card `Doppioni 0`.
- UI locale reale `http://127.0.0.1:8080/fascicoli?vista=economica`, dopo rebuild Docker `2.253.188`: bundle React caricato, card `Parcelle 2` con nota `1 da emettere, 1 bozze da visionare`; nelle righe economiche la parcella è mostrata come `Da calcolare` / `DA EMETTERE` senza tagli o testi tecnici.
- Rigo Betti verificato: contributo unificato `€ 49,00`, stato `Pagato`, fonte `Ricevuta pagoPA`, nessun identificativo tecnico visibile.

Conclusione: il numero attuale di proforma non rappresenta la realtà dello studio. La logica oggi genera proforma soprattutto quando una sentenza viene riconosciuta e indicizzata; deve invece presidiare tutti i fascicoli definiti/chiusi e distinguere:

- definito con sentenza e liquidazione leggibile;
- definito senza sentenza classificata;
- definito con sentenza ma importi non leggibili;
- definito con liquidazione zero/non dovuta;
- definito con compenso da mandato/preventivo;
- definito ma da non fatturare per motivo esplicito;
- definito duplicato o archiviato da riconciliare.

Aggiornamento operativo 06/07/2026: la proforma non deve essere soltanto segnalata. Quando il presidio economico trova una base sufficiente, deve creare automaticamente una bozza `BOZZA` collegata al fascicolo; l'avvocato la visiona, corregge se serve e solo dopo la conferma la emette o la converte in documento fiscale. La generazione automatica deve restare idempotente: se una proforma/parcella attiva esiste già, il motore la riusa e non duplica.

Regola di generazione automatica:

- se esiste una sentenza indicizzata con liquidazione/spese leggibili, usare `apply_sentenza_tribunale_automation` e creare la proforma da sentenza;
- se il fascicolo è definito e non ha proforma, ma ha `compenso_pattuito` o `valore_preventivato`, creare una bozza proforma da revisionare con fonte "compenso pattuito/preventivato nel fascicolo";
- se mancano sentenza, importi e compenso pattuito, non creare una bozza fittizia: mostrare "Sentenza/importo da acquisire" e mettere la pratica nella lista da integrare;
- se il fascicolo ha cliente/RG duplicato, segnalare prima la riconciliazione per evitare due proforme sulla stessa pratica sostanziale;
- ogni bozza automatica deve restare `BOZZA`, avere `documento_operativo=PROFORMA`, fonte leggibile, link a `/fatturazione`, e messaggio "da visionare prima dell'emissione".

## Fonti normative e operative da usare

Fonti consultate il 06/07/2026:

- Art. 127-ter c.p.c., Gazzetta Ufficiale: il giudice può sostituire l'udienza con deposito di note scritte; il provvedimento assegna un termine perentorio non inferiore a 15 giorni; ciascuna parte può opporsi entro 5 giorni dalla comunicazione; il giudice provvede entro 30 giorni dalla scadenza del termine.
  URL: https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticoloart.codiceRedazionale=040U1443&art.dataPubblicazioneGazzetta=1940-10-28&art.flagTipoArticolo=1&art.idArticolo=127&art.idGruppo=19&art.idSottoArticolo=3&art.idSottoArticolo1=10&art.progressivo=0&art.versione=3
- D.P.R. 115/2002, art. 9, Normattiva: contributo unificato nel processo civile e regole di esenzione.
  URL: https://www.normattiva.it/uri-res/N2Lsurn:nir:stato:decreto.del.presidente.della.repubblica:2002-05-30;115!vig=~art9
- Ministero della Giustizia, regime fiscale cause di lavoro: esenzione per reddito o patrocinio a spese dello Stato nelle cause di lavoro.
  URL: https://www.giustizia.it/giustizia/it/mg_1_40_0.pagecontentId=IGC1419362
- PST Giustizia, pagamento telematico contributo unificato e pagoPA.
  URL: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.pagecontentId=ACC433&modelId=12
- PST Giustizia, specifiche tecniche ex art. 34 D.M. 44/2011, provvedimento 7 agosto 2024.
  URL: https://pst.giustizia.it/PST/it/paginadettaglio.pagecontentId=ACC3429
- PST Giustizia, notificazioni via PEC da avvocati L. 53/1994.
  URL: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.pagecontentId=ACC432&modelId=12

## Principio tecnico obbligatorio

Il motore non deve cercare direttamente "il contributo", "la sentenza" o "l'udienza" nel nome file. Deve fare così:

1. acquisire il documento e i metadati;
2. calcolare impronta, data caricamento, origine, fascicolo, RG e cliente;
3. classificare il documento in una tassonomia stabile;
4. determinare quali estrattori sono ammessi per quella classe;
5. estrarre solo i dati compatibili con quella classe;
6. produrre evidenze leggibili per l'avvocato;
7. aggiornare scadenze, controllo economico o attività solo se l'evidenza è sufficiente;
8. lasciare una domanda operativa quando l'evidenza non è sufficiente;
9. non rieseguire l'analisi se nessun documento nuovo o modificato è entrato nel fascicolo.

## Tassonomia documentale minima

Classi primarie:

- `provvedimento_fissazione_udienza`: decreto o ordinanza che fissa udienza, sostituisce udienza, assegna termine note o disciplina collegamento audiovisivo.
- `provvedimento_127_ter`: provvedimento che sostituisce l'udienza con note scritte.
- `provvedimento_127_bis`: provvedimento di udienza da remoto/audiovisiva.
- `sentenza`: sentenza, ordinanza decisoria, decreto definitorio o provvedimento che chiude il giudizio.
- `verbale_udienza`: verbale di udienza, con esiti, rinvii, letture e disposizioni.
- `atto_difensivo`: ricorso, memoria, note, istanze, opposizioni, costituzione.
- `ricevuta_pagopa_cu`: ricevuta pagamento contributo unificato o avviso pagoPA con esito.
- `autocertificazione_esenzione_cu`: dichiarazione reddituale/esenzione contributo unificato.
- `patrocinio_spese_stato`: ammissione o istanza di patrocinio a spese dello Stato.
- `spese_esborsi`: ricevute spese vive, marche, diritti, anticipazioni diverse dal contributo unificato.
- `relata_notifica`: relata, attestazione di conformità, prova notifica.
- `ricevuta_pec`: RAC, RdAC, mancata consegna, accettazione/consegna PEC.
- `procura_mandato_preventivo`: procura, mandato, conferimento incarico, preventivo accettato.
- `documento_non_classificato`: documento senza classe certa, da mostrare come "da classificare".

Regola essenziale: un'autocertificazione di esenzione CU non può alimentare `spese/esborsi`; deve alimentare il contributo unificato come `Non previsto / esente`, con fonte leggibile.

## Mappa classe -> dati da leggere

`provvedimento_127_ter`:

- data termine deposito note;
- data comunicazione, se presente o da PEC;
- termine opposizione entro 5 giorni dalla comunicazione;
- parte onerata;
- eventuale onere di notifica;
- formula sintetica per agenda/scadenziario.

`provvedimento_127_bis`:

- data e ora udienza;
- piattaforma/link/stanza;
- termine richiesta presenza, se previsto;
- decorrenza da comunicazione;
- istruzioni per l'avvocato.

`sentenza`:

- data sentenza/deposito/pubblicazione;
- esito;
- liquidazione spese;
- distrazione ex art. 93 c.p.c.;
- compensi liquidati;
- spese generali, CPA, IVA se presenti;
- contributo unificato, se menzionato;
- eventuale raddoppio CU o non debenza;
- termine impugnazione se classificabile;
- stato pratica e azione economica.

`ricevuta_pagopa_cu`:

- importo versato;
- identificativo pagamento;
- data pagamento;
- causale;
- RG o fascicolo;
- stato `Pagato`.

`autocertificazione_esenzione_cu`:

- dichiarazione di esenzione;
- base normativa o reddituale;
- soggetto dichiarante;
- anno/reddito se presente;
- stato CU `Non previsto / esente`, non importo zero generico.

`spese_esborsi`:

- importo anticipato;
- tipo spesa;
- data;
- documento giustificativo;
- recuperabilità dal cliente o dalla controparte.

`relata_notifica` e `ricevuta_pec`:

- atto notificato;
- destinatario;
- domicilio digitale;
- data invio;
- accettazione;
- consegna;
- mancata consegna o errore;
- prova completa da conservare/depositare.

`procura_mandato_preventivo`:

- cliente;
- compenso pattuito;
- fondo spese;
- preventivo accettato;
- condizioni di emissione parcella/proforma;
- eventuale incarico non fatturabile o gratuito.

## Quando avviare una nuova analisi

Non bisogna analizzare sempre tutto. Il fascicolo deve avere un'impronta documentale.

Il controllo si riavvia quando:

- viene caricato un nuovo documento;
- cambia hash, dimensione o data modifica di un documento;
- arriva una nuova PEC collegata;
- viene acquisito un nuovo documento dal portale;
- cambia classificazione manuale di un documento;
- cambia stato fascicolo in `DEFINITO`, `ARCHIVIATO`, `IN_CORSO` o `APERTO`;
- cambia un pagamento o una parcella collegata;
- cambia una regola normativa o una tabella interna rilevante.

Il controllo non si riavvia quando:

- si apre solo la pagina;
- si cambia vista operativa/economica;
- non cambia l'impronta documentale;
- l'analisi precedente è già allineata alla stessa impronta.

## Domande operative che il software deve porsi

### Identità fascicolo

- Il fascicolo è unico per cliente e RG
- Esiste un altro fascicolo con stesso cliente e stesso RG
- Se esiste un doppione, quale fascicolo contiene i documenti più aggiornati
- Le PEC sono finite su un fascicolo diverso dal fascicolo principale
- Le scadenze sono duplicate o divergenti tra copie
- Le parcelle/proforma sono collegate al fascicolo giusto
- Il fascicolo è in corso, definito, archiviato o aperto per errore
- Il titolo, cliente e controparte corrispondono al contenuto dei documenti

### Documenti e classificazione

- Qual è la classe del documento
- La classe deriva dal nome file, dal testo OCR, dal portale o da classificazione manuale
- La classificazione è certa, probabile o da confermare
- Il documento contiene RG, cliente o controparte compatibili col fascicolo
- Il documento è una copia, un duplicato o una versione più recente
- Il documento è firmato digitalmente o è solo una copia
- Il testo OCR è sufficiente o serve rilettura/OCR migliore
- La classe del documento consente davvero di estrarre quel dato
- Il documento è stato caricato dopo l'ultima analisi
- La fonte da mostrare all'avvocato è leggibile

### Udienze e termini

- Il documento fissa un'udienza o sostituisce l'udienza con note scritte
- Si tratta di art. 127-ter c.p.c.
- Il termine delle note è perentorio
- Il termine decorre dalla comunicazione PEC
- Esiste una data certa di comunicazione
- Serve opposizione entro 5 giorni dalla comunicazione
- Il giudice deve provvedere dopo la scadenza delle note
- È richiesta presenza fisica, collegamento audiovisivo o solo deposito
- Esiste link o istruzione per udienza da remoto
- Serve notificare ricorso e decreto prima dell'udienza
- Chi è onerato: ricorrente, resistente, entrambe le parti o lo studio
- La scadenza è già in agenda/scadenziario
- La scadenza mostra fonte documento e fonte PEC

### PEC e decorrenze

- Quale PEC fa decorrere il termine
- La PEC è collegata al fascicolo corretto
- La PEC contiene allegati non ancora indicizzati
- Esistono ricevute complete
- Ci sono errori, rifiuti, mancata consegna o esiti PCT da presidiare
- L'invio operativo resta dal PC locale, non dal server
- Una comunicazione di cancelleria è stata letta ma non associata
- Una PEC contiene una sentenza, un decreto o una fissazione udienza non ancora analizzata

### Relata e notifiche

- Il provvedimento deve essere notificato
- L'atto da notificare è quello corretto e completo
- Serve relata separata
- Serve attestazione di conformità
- La relata è firmata quando necessario
- Sono presenti RAC e RdAC per ogni destinatario
- Esistono mancata consegna o indirizzo PEC errato
- La prova notifica è pronta per deposito
- Il software sta evitando notifiche doppie sullo stesso atto

### Contributo unificato

- Il CU è dovuto
- Il CU è esente per materia, reddito, patrocinio o altra norma
- Esiste autocertificazione di esenzione
- Esiste ricevuta pagoPA
- L'importo è stato letto da una ricevuta o calcolato da valore causa
- L'importo zero significa esente o dato mancante
- Il documento di esenzione è stato classificato nel posto corretto
- Spese/esborsi sono distinti dal CU
- Il valore causa è presente e affidabile
- Il controllo economico mostra fonte leggibile e non chiavi tecniche

### Sentenza, liquidazione e proforma

- Il fascicolo è `DEFINITO` o `CHIUSO`
- Esiste una sentenza o provvedimento definitorio classificato
- La sentenza contiene liquidazione spese
- Le spese sono liquidate in favore della parte o distratte al difensore
- L'importo è netto, lordo, comprende spese generali, CPA o IVA
- La liquidazione è sufficiente per generare una proforma
- Se manca la sentenza, il fascicolo definito deve apparire come "sentenza da acquisire/classificare"
- Esiste mandato/preventivo che consente comunque una parcella
- Esiste già una parcella/proforma collegata
- La proforma è in bozza, emessa, pagata, annullata o scaduta
- La proforma deve essere generata o solo proposta all'avvocato
- La proforma è già stata annullata e non deve essere rigenerata automaticamente
- La pratica è definita ma non fatturabile per motivo esplicito
- La parcella deve derivare dalla liquidazione giudiziale, dal compenso pattuito o da tariffario

### Qualità e linguaggio UI

- L'avvocato capisce immediatamente cosa deve fare
- Sono sparite chiavi tecniche come `sentenza_key`, hash, id interni, nomi tenant
- Ogni evidenza ha una fonte leggibile
- La UI distingue "Da verificare", "Da confermare", "Non previsto", "Pagato", "Da emettere"
- Gli importi sono in formato italiano `€ 1.234,56`
- Le date sono in formato italiano `06/07/2026`
- Lo stato "n.d." significa davvero dato non disponibile e non dato non letto
- Ogni azione ha un motivo e un collegamento al documento/fascicolo

## Piano di lavoro prima del codice

1. Censire le classi documentali già esistenti.
2. Confrontare le classi esistenti con la tassonomia minima sopra.
3. Separare classificazione da estrazione: prima classe, poi parser.
4. Creare o completare un motore unico di presidio fascicolo con settori:
   - documenti;
   - PEC;
   - relata;
   - economico;
   - doppioni;
   - attività odierne.
5. Aggiungere impronta documentale per decidere quando rianalizzare.
6. Collegare ogni classe ai parser ammessi.
7. Correggere il caso autocertificazione CU:
   - nome file con underscore o nome imprevisto;
   - OCR assente o scarso;
   - classificazione su CU, non su spese.
8. Correggere il caso fascicoli definiti:
   - contare tutti i `DEFINITO`;
   - evidenziare quelli senza proforma;
   - generare/proporre proforma solo se c'è base economica;
   - mostrare "sentenza o liquidazione da acquisire" se manca base documentale.
9. Correggere la UI economica:
   - niente chiavi tecniche;
   - fonte documento leggibile;
   - stato operativo chiaro;
   - azione consigliata chiara.
10. Creare test mirati:
   - autocertificazione CU con nome diverso;
   - fascicolo definito senza sentenza;
   - fascicolo definito con sentenza e liquidazione;
   - fascicolo definito già con proforma;
   - proforma annullata da non rigenerare automaticamente;
   - doppione cliente/RG;
   - nuova analisi solo se documenti cambiano.
11. Eseguire prova reale su server:
   - vista fascicoli economica;
   - filtro/ricerca fascicoli definiti;
   - controllo proforma;
   - controllo CU esente;
   - assenza di testi tecnici.
12. Riportare tutto in locale, testare su `127.0.0.1:8080`, commit, push branch gemelli, deploy e igiene.

## Regola per proforma su fascicoli definiti

Il software non deve inventare fatture. Deve classificare lo stato:

- `Proforma presente`: esiste parcella/proforma collegata.
- `Proforma da preparare`: esiste sentenza/liquidazione o compenso pattuito sufficiente.
- `Da acquisire sentenza`: fascicolo definito senza provvedimento definitorio classificato.
- `Da confermare importi`: sentenza presente ma importi non leggibili.
- `Non fatturabile`: esiste motivo esplicito salvato dall'avvocato.
- `Doppione da riconciliare`: cliente/RG duplicati, non generare nuova proforma finché non si sceglie il fascicolo principale.

Per i 61 fascicoli definiti attuali, il software deve mostrare un quadro studio:

- quanti sono già coperti da proforma;
- quanti sono da proformare;
- quanti richiedono sentenza/documento;
- quanti richiedono conferma importi;
- quanti sono esclusi/non fatturabili;
- quanti sono bloccati da doppione.

## Esito atteso per l'avvocato

La schermata non deve dire "aggiornato in lettura" o mostrare chiavi interne. Deve dire, per esempio:

- "Contributo unificato: non dovuto. Fonte: autocertificazione esenzione contributo unificato."
- "Sentenza letta: liquidate spese per € 258,00. Proforma da emettere: € 376,46."
- "Fascicolo definito senza proforma: acquisire o classificare la sentenza prima di generare la bozza."
- "Termine note scritte ex art. 127-ter: deposito entro 09/07/2026. Verificare comunicazione PEC per opposizione entro 5 giorni."
- "Pratica duplicata: stesso cliente e RG. Riconciliare prima di aggiornare scadenze o proforma."

## Stato del lavoro

Questo documento è la base prima del nuovo codice. Le modifiche applicative successive devono rispettare questa analisi e lasciare test/prova reale per dimostrare che:

- i documenti vengono classificati;
- i parser leggono solo dati coerenti con la classe;
- il controllo economico si popola da fonti reali;
- i fascicoli definiti non restano invisibili al presidio proforma;
- la UI parla all'avvocato in italiano operativo, senza dettagli tecnici interni.

## Esito implementazione server 06/07/2026

Regola finale per la proforma: il presidio economico crea automaticamente una bozza proforma quando trova una base economica certa, ma non emette il documento al posto dell'avvocato. La bozza resta in stato `BOZZA`, viene collegata al fascicolo e viene mostrata in vista economica come `Bozza proforma da visionare`; l'avvocato deve visionarla, correggerla se serve, completare i profili fiscali e confermarla prima dell'emissione.

Logica applicata:

- se il fascicolo definito contiene una sentenza compatibile per RG/cliente e una liquidazione leggibile, il motore usa la sentenza come fonte primaria;
- se non esiste una sentenza leggibile ma nel fascicolo e' presente un compenso pattuito o un valore preventivato affidabile, il motore crea una bozza di revisione da fascicolo;
- se non esistono sentenza, importi o compenso, il motore non inventa una fattura e lascia la pratica fra quelle da integrare;
- se esiste gia' una proforma/parcella attiva, il motore la segnala e non duplica;
- se ci sono fascicoli con stesso cliente e stesso RG, il software blocca la generazione automatica e chiede prima la riconciliazione.

Verifica dati produzione su tenant `studio-legale-giuseppe-montagnese`:

- fascicoli censiti in produzione: 333;
- fascicoli definiti/archiviati da presidiare economicamente: 94;
- parcelle/proforme prima del presidio automatico: 12;
- parcelle/proforme dopo il presidio automatico: 21;
- bozze create automaticamente dal presidio sentenze/fascicoli: 9;
- fascicoli definiti ancora senza proforma/parcella: 78.

Esempi reali creati in produzione:

- Minniti, proforma `2024/005`, totale `€ 1.167,30`, fonte sentenza;
- Araniti, proforma `2024/004`, totale `€ 1.306,86`, fonte sentenza;
- Grande, proforma `2024/003`, fonte sentenza;
- Sgrò, proforma `2024/002`, fonte sentenza;
- Bastianello, proforma `2025/007`, fonte sentenza;
- Cantiani, proforma `2025/006`, fonte sentenza;
- Morelli, Cicco e Compagnone create dal primo presidio automatico.

Motivi dei fascicoli ancora non proformati:

- 17 fascicoli hanno documenti letti ma non classificabili come sentenza economica utilizzabile;
- 38 fascicoli hanno documenti con contesto non compatibile con il fascicolo;
- 15 fascicoli non hanno candidati sentenza utili;
- 3 fascicoli hanno candidati senza testo estraibile;
- 7 fascicoli hanno sentenza coerente ma senza liquidazione leggibile.

Verifica visiva produzione eseguita su `https://app.iusentra.it/fascicoli?vista=economica`:

- dashboard fascicoli: `300` fascicoli visibili, `DA ARCHIVIARE 61`, `DOPPIONI 0`, `REGISTRATO € 14.340,00`, `PARCELLE 67`, `46 da emettere, 21 bozze da visionare`, `DOCUMENTI 13052`;
- riga Betti: liquidazione `€ 1.100,00`, parcella `€ 1.605,03`, fascia `Bozza proforma da visionare` con messaggio di bozza automatica da confermare prima dell'emissione;
- riga Merdini: contributo unificato `n.d.` e stato `Non previsto` con fonte `Autocertificazione esenzione contributo unificato`;
- riga Vinci: liquidazione `€ 350,00`, parcella `€ 510,69`, bozza proforma da visionare;
- ricerca `Betti` nella vista economica: una sola riga visibile, confermando che il filtro client/server funziona;
- non sono piu' visibili chiavi tecniche come `sentenza_key`, `docai`, `document_id` o path tenant nelle evidenze economiche.

Guardrail eseguiti durante la tranche:

- `python -m py_compile web/services/react_fascicoli_bridge.py pct/fascicolo_sentenza_economica.py`;
- `python -m pytest tests/test_fascicolo_sentenza_economica.py::test_sentenza_con_rg_importato_a_zeri_iniziali_aggiorna_economia tests/test_fascicolo_sentenza_economica.py::test_sentenza_con_cliente_ma_rg_diverso_non_aggiorna_economia tests/test_react_shell.py::test_react_fascicoli_presidio_economico_crea_bozza_proforma_definito tests/test_react_shell.py::test_react_fascicoli_presidio_economico_legge_sentenza_fisica_non_indicizzata -q`.

Nota prestazionale: la vista economica non avvia OCR massivo a ogni apertura. Il presidio usa prima Document AI/OCR gia' indicizzato, poi testo PDF nativo quando il documento e' candidato sentenza; l'OCR pesante resta compito del worker documentale e non del caricamento lista.

Stato residuo prima della chiusura di rilascio: riallineare locale, rebuild Docker su `127.0.0.1:8080`, prova reale locale, commit/push branch gemelli, deploy Hetzner dal commit finale, check GitHub/CodeQL e igiene repository.
