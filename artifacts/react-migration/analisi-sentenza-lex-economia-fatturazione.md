# Analisi operativa: Sentenza Lex AI, fascicolo, economia e fatturazione

Ultimo aggiornamento: 2026-06-22.

## Regola di rilettura

Questo file deve essere riletto dopo ogni compattazione, insieme ad `AGENTS.md` e ad `artifacts/data-flow/incarico-operativo-permanente.md`, prima di riprendere qualunque lavoro su Fascicoli, Documenti AI, indicizzazione Lex, economia fascicolo, parcelle, fatture, proforma o numerazione.

## Obiettivo concreto

Quando un documento del fascicolo viene indicizzato da Lex AI e catalogato come provvedimento `Sentenza Tribunale`, il software deve leggere il testo estratto, riconoscere i dati economici e processuali della sentenza, applicarli automaticamente alla matrice dati del fascicolo e alimentare la conoscenza di Lex AI nel database vettoriale tenant-aware.

Caso base indicato dall'utente:

- intestazione: `Sentenza n. 230/2024 pubbl. il 07/05/2024`;
- numero ruolo: `RG n. 1548/2023`;
- contributo/spese: `€ 98,00` come sommatoria dei contributi unificati o spese vive indicate nel testo;
- liquidazione: `liquidando la complessiva somma di € 1.100,00`;
- formula accessoria: spese generali, IVA e CPA;
- difensore antistatario: eventuale indicatore utile nelle note, senza forzare regole contabili non richieste.

Risultato atteso:

- `Prossima scad.` passa da `n.d.` alla data della sentenza, per esempio `07/05/2024`;
- lo stato del fascicolo passa da `In corso` a `Definito`;
- nella sezione economia del fascicolo:
  - `contributo_unificato` diventa `pagato`, importo estratto, data sentenza;
  - `fondo_spese`, quando presente nel testo, usa la stessa logica del contributo: `pagato`, importo estratto, data sentenza;
  - `liquidazione_giudice` diventa `pagato`, importo liquidato, data sentenza, nota con il titolo della liquidazione;
  - `parcella` diventa `da_emettere`, data sentenza e collegamento alla proforma generata;
- viene generata automaticamente una parcella/fattura proforma coerente con la logica esistente di `Parcelle e Fatture`;
- l'avvocato può trasformare la proforma in parcella/fattura con un click;
- quando il pagamento reale viene registrato, la proforma collegata diventa parcella/fattura pagata;
- la numerazione fatture può essere inizializzata per continuare da un ultimo numero già usato in altro sistema.
- Lex AI indicizza anche il contenuto strutturato della sentenza nel DB vettoriale, con metadati su fascicolo, RG, data sentenza, liquidazione, contributo, fondo spese, cliente e fonte documento, così le risposte future possono usare quella conoscenza senza reimport manuale.

## Domande tecniche da presidiare prima del codice

1. Dove nasce il dato: documento indicizzato in `Document AI` / `Lex indexing` collegato a un fascicolo.
2. Chi possiede il dato: tenant dello studio proprietario del fascicolo.
3. Dove si salva il dato strutturato: SQL come fonte di verità, con JSON solo mirror o blob compatibile già previsto dal dominio.
4. Quali oggetti esistenti riusare: `GestioneFascicoli`, `Fascicolo.pagamenti`, `GestioneFatturazione`, API React fascicoli, API React fatturazione, repository Document AI.
5. Quale logica deve essere idempotente: lo stesso documento non deve creare più proforme né duplicare storico pagamenti se reindicizzato.
6. Quali campi non vanno sovrascritti senza motivo: una scadenza futura reale già compilata non va cancellata; la data sentenza va applicata quando il campo è assente o `n.d.` e comunque tracciata nella matrice economica.
7. Come si evita una regressione contabile: numerazione proforma/fatture centralizzata, configurabile per anno, e calcolo del prossimo numero basato sul massimo fra documenti esistenti e ultimo numero inizializzato.
8. Come si evita un falso positivo Lex: usare estrazione deterministica su intestazione `Sentenza n. ... pubbl. il ...`, `RG n. ...`, parole chiave `sentenza`, `tribunale`, `liquidando`, `contributo unificato`, `c.u.`, `fondo spese`.
9. Come si gestisce `fondo_spese`: voce autonoma, stessa data/stato del contributo, importo solo se il testo la identifica in modo distinto.
10. Come si alimenta Lex AI: il testo sentenza e i metadati estratti devono entrare nel DB vettoriale tramite il repository/servizio Lex esistente, con chiave idempotente documento-fascicolo-tenant.
11. Come si rende il flusso verificabile: audit nel fascicolo, history nei pagamenti, collegamento `proforma_id`, evidenza indicizzazione vettoriale, test mirati e prova reale su `127.0.0.1:8080`.

## Struttura dati prevista

Fascicolo:

- `stato = DEFINITO`;
- `data_prossima_udienza = data_sentenza` quando il valore visibile era mancante;
- `data_chiusura = data_sentenza` se non già valorizzata;
- avanzamento/audit con origine `lex_ai_sentenza_tribunale`.

Pagamenti fascicolo:

- `contributo_unificato.status = pagato`;
- `contributo_unificato.importo = importo estratto`;
- `contributo_unificato.data_pagamento = data_sentenza`;
- `fondo_spese.status = pagato` quando rilevato;
- `fondo_spese.importo = importo estratto`;
- `fondo_spese.data_pagamento = data_sentenza`;
- `liquidazione_giudice.status = pagato`;
- `liquidazione_giudice.importo = importo liquidato`;
- `liquidazione_giudice.data_pagamento = data_sentenza`;
- `liquidazione_giudice.note = titolo/frase liquidazione`;
- `parcella.status = da_emettere`;
- `parcella.data_pagamento = data_sentenza`;
- `parcella.proforma_id = id parcella/fattura proforma`;
- `history[]` con timestamp Europe/Rome, utente/attore e origine automazione.

Parcella/fattura proforma:

- creata tramite `GestioneFatturazione`, non con record parallelo;
- collegata a `id_fascicolo` e, se disponibile, `id_cliente`;
- origine `lex_ai_sentenza_tribunale`;
- riferimento al documento indicizzato;
- stato iniziale coerente con proforma/bozza;
- voci economiche derivate dalla sentenza;
- conversione esplicita a parcella/fattura;
- marcatura pagata quando il pagamento reale viene registrato.

Lex AI / DB vettoriale:

- nessun indice parallelo non governato;
- alimentazione tramite il servizio Lex già esistente;
- chiave idempotente basata su tenant, fascicolo, documento e hash/versione;
- contenuto vettorializzato: testo sentenza o chunk già estratti, più scheda strutturata con data sentenza, RG, importi, ruolo economico e collegamenti fascicolo/proforma;
- metadati minimi: `tenant_id`, `fascicolo_id`, `document_id`, `sha256`, `tipo_documento=sentenza_tribunale`, `data_sentenza`, `rg`, `cliente`, `importo_liquidazione`, `contributo_unificato`, `fondo_spese`, `proforma_id`;
- il DB vettoriale serve a migliorare le risposte e le ricerche di Lex, non sostituisce SQL come fonte di verità contabile.

Numerazione:

- impostazione per anno;
- ultimo numero usato configurabile;
- prossimo numero = massimo tra numeri già presenti e ultimo numero configurato + 1;
- persistenza tenant-aware con parità SQLite/PostgreSQL tramite configurazione SQL esistente, evitando file JSON autoritativi.

## UI React da presidiare

Fascicoli:

- lista fascicoli: `Prossima scad.` e `Stato`;
- dettaglio/economia: card o pannelli per contributo, fondo spese, liquidazione e parcella;
- testi italiani con accenti corretti;
- badge/stati leggibili per `pagato`, `da emettere`, `definito`;
- hover, focus, disabled e loading leggibili;
- nessun salto layout su desktop, tablet e mobile.

Fatturazione:

- evidenza della proforma creata automaticamente;
- pulsante chiaro per passare da proforma a parcella/fattura;
- azione di pagamento reale collegata allo stato `pagata`;
- pannello compatto per inizializzare la numerazione;
- conferme ed errori in italiano.

## Rischi e contromisure

- Reindicizzazione dello stesso documento: usare chiave documento/fascicolo e deduplica sulla proforma.
- Duplicati dello stesso PDF o della stessa sentenza nello stesso fascicolo: riusare la proforma esistente quando coincidono data sentenza, numero sentenza e RG, anche se cambia `document_id`.
- Importi ambigui nel testo: salvare solo importi estratti da contesti riconosciuti; in caso di dubbio lasciare nota/audit senza sovrascrivere dati esistenti.
- Scadenza già valorizzata: non cancellare scadenze reali future se non è chiaramente un campo `n.d.` o mancante.
- Numerazione già usata: calcolare sempre dal massimo reale, non solo dalla configurazione.
- Divergenza SQLite/PostgreSQL: usare repository/configurazioni già presenti e testare lo stesso contratto applicativo.
- Doppia indicizzazione vettoriale: usare chiave idempotente e aggiornare il documento vettoriale invece di aggiungere duplicati.
- Conoscenza Lex non verificabile: salvare metadati di indicizzazione e rendere testabile il fatto che la sentenza sia entrata nell'indice.
- Regressione UI: prima verifica visiva mirata sul flusso reale, poi gate automatici.
- Performance: l'estrazione deve essere regex/deterministica e lavorare sul testo già estratto, senza bloccare caricamenti o routing React.

## Test e verifiche obbligatorie

Test mirati:

- estrazione data sentenza, RG, importo liquidazione, contributo unificato e fondo spese;
- applicazione idempotente al fascicolo;
- generazione singola della proforma;
- configurazione numerazione e calcolo prossimo numero;
- conversione proforma/parcella e marcatura pagata;
- alimentazione idempotente del DB vettoriale Lex AI con testo e metadati sentenza;
- payload React di fascicoli e fatturazione.

Prova reale obbligatoria:

- Docker locale aggiornato e healthy su `http://127.0.0.1:8080`;
- apertura reale di Fascicoli e documento indicizzato;
- controllo della riga fascicolo con data e stato aggiornati;
- apertura della sezione economia e verifica di contributo, fondo spese se presente, liquidazione e parcella;
- apertura di `Parcelle e Fatture`, verifica della proforma automatica;
- interrogazione o stato indice Lex che confermi la conoscenza vettoriale aggiornata per la sentenza;
- click reale su conversione proforma/parcella;
- registrazione pagamento reale o flusso controllato equivalente e verifica stato pagata;
- inizializzazione numero fattura e conferma prossimo numero;
- scroll completo e responsive desktop/tablet/mobile.
- report visivo end-to-end della matrice richiesta: documento sentenza, riga fascicolo con `Prossima scad.` e `Stato`, tab economia con contributo/fondo spese/liquidazione/parcella, `Parcelle e Fatture` con proforma collegata e passaggio a fattura/parcella.

## Documentazione da aggiornare a fine lavoro

- questo file, se cambiano decisioni operative;
- `artifacts/react-migration/pytest-confirmed-ok.md`;
- `artifacts/react-migration/pytest-open-issues.md`;
- report dedicato della prova reale locale;
- changelog/version bump;
- eventuali note su `procedura-deposito-telematico.md` solo se il lavoro tocca deposito, firma, PEC o notifiche legali.

## Stato implementazione 2.253.86

- Implementata estrazione deterministica in `pct/fascicolo_sentenza_economica.py` con data sentenza, RG, liquidazione, contributo unificato, fondo spese, spese generali e antistatario.
- Implementata applicazione idempotente al fascicolo: stato `Definito`, prossima scadenza da `n.d.` a data sentenza, chiusura, pagamenti economici e audit `lex_ai_sentenza_tribunale`.
- Implementata proforma automatica tramite `GestioneFatturazione`, senza record paralleli, con conversione a fattura/parcella su `EMESSA` o `PAGATA`.
- Implementata inizializzazione numerazione per anno in configurazione tenant-aware e pannello React in `Parcelle e Fatture`.
- Implementata alimentazione DB vettoriale Lex AI tramite `LocalAIService.index_text_document`, con fonte `lex_sentenza_tribunale`, metadati strutturati e deduplica su documento/fascicolo/tenant.
- Implementato recupero delle sentenze già applicate prima dell'estensione vettoriale: se manca `vector_indexes`, Lex AI viene alimentato una sola volta senza riscrivere la matrice economica.
- Test mirati, contratti API, build Vite e prova reale locale Docker/browser sono registrati in `pytest-confirmed-ok.md` e nel report dedicato `artifacts/react-migration/prova-reale-sentenza-lex-economia-fatturazione-2.253.86.md`.
- Aggiunta protezione anti-duplicato per il backfill/server: nello stesso fascicolo una sentenza già riconosciuta con stessa data, numero sentenza e RG riusa la proforma Lex AI esistente invece di crearne una seconda.

## Backfill globale 2.253.90

- Dopo la segnalazione dell'utente è stato rieseguito un controllo allargato sul server reale: il perimetro dati contiene `331` fascicoli totali, `4237` testi `extracted_text.json`, `4200` testi non vuoti, `1321` occorrenze della parola `sentenza`, `622` testi con `Sentenza n.`, `110` testi con intestazione `Sentenza n. ... pubbl.` e `106` documenti riconosciuti dalla regola precedente.
- Il numero operativo non coincide con le occorrenze testuali: molte citazioni di sentenze sono dentro atti, diffide o memorie e non devono aggiornare economia, stato fascicolo o proforma. Il backfill deve quindi distinguere documento-sentenza ufficiale, duplicato della stessa sentenza e citazione interna.
- Il parser è stato esteso per riconoscere una sentenza ufficiale anche senza la parola `Tribunale`, quando vicino all'intestazione ci sono RG e segnali ministeriali come `Firmato Da`, `Emesso Da`, `Serial#`, repertorio o cronologico. Il test negativo su citazione Cassazione presidia il falso positivo opposto.
- Il backfill ora raggruppa per chiave stabile `tenant:fascicolo:data_sentenza:numero_sentenza:RG`, sceglie il documento migliore quando la stessa sentenza è presente più volte, scarta i duplicati con warning esplicito e usa `sentenza_key` anche per l'idempotenza della proforma e dell'indice Lex AI.
- Il report espone anche `matrix_confirmed`, `duplicates_skipped`, `vector_embedding_errors` e `unique_fascicoli_confirmed`, così una riesecuzione dopo un apply parziale distingue i fascicoli già corretti da quelli ancora da aggiornare.
- Il primo apply server precedente è stato interrotto perché la vecchia logica indicizzava troppi duplicati Lex AI; ha lasciato dati parziali reali su `10` fascicoli e `4` proforme Lex. La nuova riesecuzione deve completare il perimetro restante in modo idempotente e con embedding limitati per batch.
- Restano obbligatori prima della chiusura: rebuild locale `127.0.0.1:8080`, dry-run server con codice 2.253.90, apply server senza backup, verifica dei conteggi SQL/Lex/proforme e prova visiva della matrice fino alla proforma/parcella.

## Lex AI backfill 2.253.91

- Il primo apply con `2.253.90` è stato fermato dopo oltre 30 minuti: il processo non era morto, Ollama stava lavorando, ma la scheda vettoriale conteneva fino a `80000` caratteri del testo OCR per sentenza e il costo di embedding rendeva il backfill globale troppo lento.
- La correzione `2.253.91` mantiene la conoscenza Lex AI, ma indicizza una scheda compatta: dati sentenza, fascicolo, RG, importi, proforma, titolo liquidazione, intestazione e finestre testuali attorno a liquidazione, contributo unificato, fondo spese, spese generali e antistatario.
- Il limite dell'estratto vettoriale è presidiato da test: deve restare abbastanza piccolo per completare il job, ma conservare importi e formule economiche che servono a Lex per rispondere.
- Dopo il deploy `2.253.91` va ripetuto l'apply: i fascicoli già aggiornati dal tentativo precedente devono risultare `matrix_confirmed`, quelli mancanti devono essere applicati, e Lex AI deve essere alimentato con la scheda compatta.

## Backfill globale 2.253.89

- Corretto il perimetro dell'incarico: la matrice dati non deve essere applicata a un fascicolo dimostrativo o a un singolo caso noto, ma a tutti i fascicoli reali che hanno documenti AI già estratti e riconoscibili come sentenza.
- Aggiunto `scripts/backfill_sentenza_lex_economics.py` con due modalità operative:
  - dry-run: legge tutti gli `extracted_text.json` tenant-aware, riconosce le sentenze, indica fascicolo trovato/non trovato e non scrive dati;
  - apply: applica la matrice al fascicolo, crea/riusa la proforma, aggiorna `contributo_unificato`, `fondo_spese`, `liquidazione_giudice`, `parcella`, stato, data sentenza e alimenta Lex AI nel DB vettoriale.
- Il report del backfill espone `documents_seen`, `sentenze_found`, `fascicoli_found`, `applied`, `vector_indexed`, `skipped_missing_fascicolo`, errori e conteggi unici (`unique_sentenze`, `unique_fascicoli_found`, `unique_fascicoli_applied`, `unique_missing_fascicoli`), così il test non può limitarsi a un caso hardcoded o a duplicati dello stesso fascicolo.
- Dry-run locale del 22/06/2026 su `tenant-8bf98719c459`: letti `666` testi estratti, riconosciuti `12` documenti sentenza, `3` sentenze uniche, `1` fascicolo corrente collegato, `2` fascicoli storici non presenti nel repository locale e zero errori; report JSON in `artifacts/react-migration/backfill-sentenza-local-dry-run-2.253.89.json`.
- Test automatico esteso: `tests/test_backfill_sentenza_lex_economics.py` copre due fascicoli distinti e un duplicato della stessa sentenza nello stesso fascicolo, verificando che il backfill copra tutti i fascicoli eleggibili e non generi una seconda proforma per il duplicato.
- Per il difetto segnalato su `Salva modifiche` fascicolo `DD242366`, `StudioDB` è stato rafforzato sui lock SQLite dei bind mount Windows/Docker e la rotta React di modifica fascicolo risponde con JSON leggibile invece di restituire una pagina HTML 500.
- Prova reale locale del 22/06/2026 su `http://127.0.0.1:8080/fascicoli/DD242366/modifica`: Chrome installato visibile, form popolato dopo il caricamento async, hover/focus su `Salva modifiche`, POST JSON 200 in 1,883s, redirect a `/fascicoli/DD242366`, dettaglio completo caricato, mobile `390x844` senza warning console. Fix React aggiuntivo: i campi `type=date` normalizzano solo valori ISO/italiani e non passano più `n.d.` all'input HTML.
- Prima della chiusura resta obbligatorio eseguire il dry-run e l'apply sul server reale, senza creare nuovi backup come richiesto dall'utente, e poi fare il test visivo end-to-end su più fascicoli reali fino a proforma/parcella.

## Correzione RG sentenza 2.253.87

- Durante il dry-run di produzione sui documenti `extracted_text.json` del server Hetzner è emerso che alcune sentenze contengono nel corpo riferimenti a vecchi `RG n.` prima dell'intestazione ministeriale della sentenza.
- L'estrazione RG ora preferisce il blocco immediatamente successivo a `Sentenza n. ... pubbl. il ...`; solo se quel blocco manca usa il fallback storico.
- Questo evita che duplicati della stessa sentenza nello stesso fascicolo vengano considerati diverse sentenze solo perché nel corpo è citato un altro RG.
- Il test `test_estrazione_rg_preferisce_intestazione_sentenza` presidia il caso reale prima del backfill sui fascicoli server.
- Prima della chiusura resta obbligatorio produrre un test visivo completo che riporti tutti i dati della matrice fino alla fattura proforma/parcella, non solo il parser o i test automatici.

## Prova reale locale 2.253.86

- Docker locale ricostruito e riavviato su `http://127.0.0.1:8080`; `/api/pronto` ha risposto `versione=2.253.86` e i container `app`, `scheduler-worker`, `ocr-worker`, `redis` risultano healthy.
- Il browser integrato non era agganciabile tramite Node REPL per errore MCP `missing field sandboxPolicy`; la prova visiva è stata quindi eseguita in Google Chrome installato e visibile (`C:\Program Files\Google\Chrome\Application\chrome.exe`) con profilo temporaneo e sessione locale autenticata.
- `/fatturazione` è stata verificata con React attivo, scroll completo, pannello numerazione, hover/focus sul campo `Ultimo numero usato`, click su `Salva numerazione` e conferma `Numerazione fatture aggiornata.`.
- `/fascicoli` è stata verificata sulla lista reale locale: colonne `Prossima scad.` e `Stato` visibili, metriche e tab coerenti, nessun fallback legacy o overlay di errore.
- Responsive verificato su desktop, tablet e mobile: nessun overflow orizzontale rilevato su tablet/mobile e testi principali leggibili nelle card.
- Per coprire i pulsanti proforma, sono state create due proforme controllate locali con origine `Sentenza Lex AI`, poi rimosse dal DB a fine prova: `2026/001` è passata con click reale da `Proforma/Bozza` a `Fattura/Emessa`; `2026/002` è passata con click reale su `Registra bonifico` a `Fattura/Pagata` con incasso `20/06/2026`.
- Durante la prova è ricomparso il lock SQLite tipico del volume Windows/Docker; è stato risolto con riavvio dei servizi applicativi, verifica di scrittura e pulizia dei record controllati. A fine prova `/api/pronto` è tornato OK su `2.253.86` e i record di test risultano assenti.
- La verifica sui fascicoli reali e sui documenti sentenza presenti solo sul server resta parte del deploy Hetzner: dopo il push la produzione dovrà processare i documenti reali e mostrare la matrice economia/DB vettoriale sugli stessi dati dello studio.
