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

## Chiusura controllo globale server 2.253.93

- Il backfill/apply sul server reale ha letto il perimetro Document AI tenant-aware senza creare backup nuovi, come richiesto dall'utente.
- Conteggi server applicati e confermati: `documents_seen=4124`, `sentenze_found=109`, `fascicoli_found=109`, `applied=7`, `matrix_confirmed=34`, `vector_indexed=34`, `vector_embedding_errors=0`, `duplicates_skipped=75`, `unique_sentenze=34`, `unique_fascicoli_found=27`, `unique_fascicoli_applied=4`, `unique_fascicoli_confirmed=27`, `unique_missing_fascicoli=0`, `errors=0`.
- Il caso Betti `87E77B0E` ha confermato il difetto segnalato dall'utente: il contributo unificato non doveva prendere `€ 1.100,00`, che è la liquidazione, ma `€ 98,00` come spese/contributi. La correzione 2.253.93 conserva `liquidazione_giudice=1100,00` e `contributo_unificato=98,00`.
- Lex AI sul server è stato ripulito dai documenti vettoriali legacy non versionati: `stable_docs=34`, `legacy_docs=0`, `legacy_chunks=0`, `stable_chunks_by_state.embedded=66`, `stable_pending_docs=[]`, `stable_chunks_missing_schema=0`.
- Le proforme/fatture generate o riusate restano collegate alla sentenza tramite `origine=lex_ai_sentenza_tribunale` e metadati `lex_ai_sentenza`; la deduplica per chiave stabile impedisce nuove proforme se la stessa sentenza viene reindicizzata.

## Verifica visuale card fatturazione 2.253.94

- Durante il controllo visuale reale della matrice fino a `Parcelle e Fatture` è emerso un problema grafico non contabile: nelle card proforma/fattura di `/fatturazione`, testi lunghi di cliente/origine/date potevano sovrapporsi alle azioni.
- La correzione 2.253.94 riguarda solo `frontend/src/components/FatturazionePage.css`: la card parcella usa colonne dati con `minmax`, manda le azioni su riga autonoma, consente `overflow-wrap` nei testi lunghi e corregge anche la lista compatta `Canale SdI / XML FatturaPA / Ricevute SdI` che aveva quattro elementi dentro una griglia a tre colonne.
- Prova reale locale eseguita su Docker reale `http://127.0.0.1:8080`, versione `2.253.94`, con Chrome installato visibile: pagina `/fatturazione` full React con `#root`, scroll completo desktop e mobile, hover/focus su controllo interattivo, nessuna sovrapposizione su `.iu-fatt-record`, nessuna sovrapposizione su `.iu-fatt-list__item`, mobile `scrollWidth=375` e `clientWidth=375`.
- Screenshot locali fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-225394-local-fatturazione-card-fixed2-desktop.png` e `C:\Users\antmm\AppData\Local\Temp\iusentra-225394-local-fatturazione-card-fixed2-mobile.png`.
- Per la prova visuale locale è stato usato un record controllato con origine `lex_ai_sentenza_tribunale_codex_visual_225394`; il record è stato eliminato subito dopo il test e la verifica SQL finale ha restituito `remaining_temp_records=0`.

## Validazione contesto sentenza e card operative 2.253.95

- Correzione richiesta dall'utente: non basta che un PDF sia classificato come `Sentenza Tribunale`. Prima di applicare la matrice economica, creare/riusare una proforma o alimentare Lex AI come sentenza del fascicolo, il testo deve confermare il cliente del fascicolo e lo stesso RG della pratica.
- Il caso esplicito `Sentenza Tribunale Vicenza.pdf` è trattato come possibile materiale strategico/giurisprudenza di supporto: se nel testo non compaiono nome e cognome del cliente del fascicolo, oppure l'RG estratto non coincide con quello del fascicolo, il documento viene saltato con warning `cliente_non_presente_nella_sentenza` o `rg_sentenza_non_coincidente_con_fascicolo`.
- Il backfill ora distingue `raw_sentenze_found` da `sentenze_found`: il primo conteggia intestazioni/parsing grezzo, il secondo solo sentenze accettate dopo validazione cliente+RG. Anche `unique_sentenze` conta solo le sentenze accettate, così il test globale non può risultare falsato da precedenti strategici.
- Il runtime Document AI/Lex applica la stessa regola: se `context.ok` è falso, non aggiorna la matrice e non indicizza la scheda vettoriale come `lex_sentenza_tribunale` del fascicolo.
- `/fatturazione` è stata riorganizzata con card compatte operative: stati parcella come filtri reali, card `Bonifico registrato` e `Parcella emessa` che impostano i filtri richiesti, link reali a nuova parcella, export CSV, numerazione e impostazioni SdI. PDF e XML restano sulle singole righe parcella/fattura, dove il record corretto è noto.
- Aggiunti filtri locali dell'archivio per `Bonifico registrato`, `Parcella emessa`, `Cliente` e `Nr fascicolo`, oltre alla ricerca generale. I filtri lavorano sul payload React reale già caricato, senza introdurre dati paralleli.
- Il filtro `Nr fascicolo` non dipende più dal solo titolo pratica: il payload React espone `caseId`, `caseReference` e `caseRg` per ogni parcella collegata a un fascicolo, così la ricerca per ID fascicolo o RG resta verificabile e non ambigua.
- Prova reale locale eseguita dopo rebuild Docker `2.253.95` su `http://127.0.0.1:8080/fatturazione`: 12 card compatte operative, nessun overflow desktop/mobile, click su `Bonifico registrato` e `Parcella emessa` con select reali aggiornati, `Azzera filtri`, anchor `Numerazione`, link `Nuova parcella`, focus visibile sui filtri e mobile `390x844` con `scrollWidth=clientWidth=375`.

## Bonifica RG Vicenza e parser importi 2.253.106

- Segnalazione utente del 25/06/2026: il documento `Sentenza Tribunale Vicenza.PDF` risultava ancora usato per il calcolo economico, pur essendo materiale strategico della causa e riportando `VERBALE DELLA CAUSA n. r.g. 1548/2023`, non il numero RG del fascicolo corrente.
- Verifica server reale: il codice corrente scarta già quel documento quando il fascicolo ha RG diverso (`rg_sentenza_non_coincidente_con_fascicolo`), ma erano rimasti dati scritti dal backfill precedente del 22/06/2026.
- Bonifica applicata sul server Hetzner senza creare backup: `9` proforme Lex AI in bozza annullate, `9` fascicoli ripuliti da economia/proforme/automation collegate al falso RG, `11` documenti vettoriali `lex_sentenza_tribunale` rimossi da Lex AI.
- Post-check server a freddo: `bad_bozza_proforme=0`, `bad_active_proforme=0`, `bad_fascicoli=0`, `bad_vector_docs=0` per la chiave `2024-05-07 / Sentenza 230/2024 / RG 1548/2023` su fascicoli con RG diverso.
- Corretto anche il parser importi: una liquidazione come `€ 1030,00` viene letta come `1030.00` e non più come `103.00`; questo evita errori economici sulle sentenze corrette che non usano il punto migliaia.
- Regola operativa confermata: una sentenza entra nella matrice economica solo se il suo RG coincide con il fascicolo; il nome cliente resta controllo aggiuntivo, ma il mismatch RG è da solo sufficiente a bloccare economia, proforma e indicizzazione vettoriale come sentenza del fascicolo.

## Automazione scheduler 2.253.107

- Dopo l'ulteriore chiarimento dell'utente, la procedura non deve dipendere da lancio manuale Codex o da script richiamati a console.
- Aggiunto job built-in `lex_sentenza_economia_auto` nel worker `pct.scheduler`: ogni 10 minuti esegue il motore `run_backfill(..., apply=True)` sul registry tenant-aware, applica la matrice solo alle sentenze con contesto valido e alimenta Lex AI con deduplica.
- Il job non crea backup e non usa una fonte dati parallela: legge Document AI tenant-aware, repository fascicoli/fatturazione e DB vettoriale del tenant; SQL/SQLite resta fonte di verità.
- La console pianificazioni espone `Sentenze Lex ed economia` nella famiglia `Lex AI`, così l'automazione è visibile come presidio di sistema e non resta una manutenzione nascosta.
- I test `tests/test_scheduler.py`, `tests/test_scheduler_worker.py` e `tests/test_scheduler_registry.py` presidiano presenza del job, frequenza ogni 10 minuti e chiamata in modalità `apply=True`.
- Aggiunto `scripts/check_runtime_services.py`: dopo rebuild/deploy controlla tutti i servizi Docker attivi, confronta `app`, `scheduler-worker` e `ocr-worker` con la stessa versione `pct.__version__` e fallisce se il job `lex_sentenza_economia_auto` non è registrato. Questo presidia il caso reale emerso in locale, in cui l'app era aggiornata ma il worker scheduler stava ancora girando con immagine vecchia.

## Gate job reali 2.253.108

- Estensione richiesta dall'utente: non basta che un job sia registrato o che il container sia healthy; il controllo operativo deve dimostrare che il worker vivo ha eseguito davvero il job previsto oppure bloccare il rilascio indicando la causa.
- `scripts/check_runtime_services.py` ora legge il registro `scheduled_job_runs` dal container `scheduler-worker`, controlla gli ultimi esiti di tutte le pianificazioni attive e blocca se il job obbligatorio non ha una prova reale recente, è fallito, è saltato, è rimasto in corso oltre il tempo atteso o ha restituito un risultato privo del riepilogo operativo.
- Il gate può attendere una nuova esecuzione automatica con `--wait-job-seconds`, così per `lex_sentenza_economia_auto` la prova resta del software che gira da solo e non di uno script lanciato manualmente.
- Primo esito locale del gate: `lex_sentenza_economia_auto` ha scritto un run reale con `documents_seen=667`, `matrix_confirmed=1`, `vector_indexed=1`, `errors=0`; il gate ha però bloccato il rilascio su `pst_certificati_cifratura_weekly`, che risultava ultimo run fallito.
- Risoluzione immediata del problema job PST: il refresh ministeriale resta tentato, ma se il PST non risponde e il certificato `.cer` in cache è valido, il job registra `fallback_cache_valida` e non marca fallito l'intero perimetro operativo coperto dalla cache tecnica.
- Rafforzamento successivo: `running` non basta più come esito positivo del job obbligatorio. Il gate resta rosso finché `lex_sentenza_economia_auto` non registra `completed` con `totals`, `errors=0` e `vector_embedding_errors=0`.
- Il controllo locale reale del 25/06/2026 su Docker `127.0.0.1:8080`, versione `2.253.108`, ha prima trovato un problema reale su `pst_certificati_cifratura_weekly`: il codice `0651160115` aveva un certificato scaduto in cache. Il fix fa proseguire al refresh remoto quando la cache è scaduta; il worker ha poi registrato una run manuale reale `completed`, `scaricati_o_validi=593`, `errori=0`, `cache_cer_presenti=913`.
- Lo stesso gate locale ha atteso una nuova run automatica del worker per `lex_sentenza_economia_auto`: run `completed` alle `10:40:08Z`, `documents_seen=667`, `raw_sentenze_found=12`, `sentenze_found=7`, `fascicoli_found=7`, `matrix_confirmed=1`, `vector_indexed=1`, `errors=0`, `vector_embedding_errors=0`. Questo è il controllo minimo da ripetere dopo deploy, non un semplice check di registrazione.

## Esborsi Carta docente e record parziali 2.253.109

- Segnalazione utente del 25/06/2026: nel fascicolo `FC81009F` / `RG 697/2025`, documento `Sentenza.pdf`, il testo della sentenza contiene `liquidando la complessiva somma di € 321,50, di cui € 21,50 per esborsi`, ma la vista economica lasciava contributo/spese e parcella senza importo o comunque parziali.
- Verifica tecnica sul PDF allegato `C:\Users\antmm\Downloads\Sentenza.pdf`: il documento è una sentenza reale del Tribunale di Vicenza, contiene `N. R.G 697/2025`, `ROBERTA MONTAGNESE`, footer ministeriale `Sentenza n. 465/2025 pubbl. il 23/09/2025` e dispositivo con `€ 321,50` più `€ 21,50 per esborsi`. Il beneficio `euro 500,00` riguarda la Carta docente e non deve alimentare la parcella dello studio.
- Il parser ora riconosce anche `N. R.G`, date testuali come `23 settembre 2025`, prefisso `euro` e simboli euro degradati da OCR/encoding; `esborsi` e `spese vive` alimentano la stessa voce operativa del contributo/spese da recuperare, senza indebolire il blocco cliente+RG.
- L'applicazione idempotente non si ferma più davanti a un documento già segnato come processato se mancano dati economici: alla run successiva completa contributo/esborsi, aggiorna l'importo della voce `parcella` e integra la proforma Lex in bozza con la voce `ANTICIPO` mancante.
- Lo schema vettoriale passa a `sentenza_tribunale_compact_v2`, così Lex AI non considera più attuali le vecchie schede prive di esborsi e deve reindicizzare i metadati economici completi.
- Test mirati aggiunti: estrazione Montagnese/Carta docente senza prendere `500,00`, estrazione da data testuale, completamento di record parziale già processato, backfill tenant-aware con esborsi e importo parcella.

## Spese/esborsi distinti da contributo unificato 2.253.110

- Chiarimento utente del 25/06/2026: `21,50 sono spese non contributo unificato`. La voce estratta dalla formula `di cui € 21,50 per esborsi/per spese` deve quindi essere classificata come `Spese/esborsi`, anche se tecnicamente viene conservata nel campo operativo storico `contributo_unificato` della matrice economica.
- Il PDF CU/PagoPA presente nello stesso fascicolo viene letto dal job automatico solo come prova di controllo: se conferma lo stesso importo aggiunge audit `contributo_unificato_confermato_pdf`; se l'importo diverge dagli esborsi della sentenza, il software non sovrascrive la voce `Spese/esborsi` e registra `contributo_unificato_pdf_diverso_da_spese_sentenza`.
- Il beneficio Carta docente `euro 500,00` è metadato `beneficio_cliente` / `carta_docente`: appartiene al cliente, non all'avvocato, e non entra nelle voci di proforma/parcella né nel bonifico dello studio.
- Le voci proforma generate o sincronizzate per `21,50` usano descrizione `Spese ed esborsi riconosciuti in sentenza`, non `Contributo unificato`.
- Lo schema vettoriale passa a `sentenza_tribunale_compact_v3` per includere `contributo_unificato_natura`, `contributo_unificato_label`, `beneficio_cliente` e `beneficio_cliente_tipo`; Lex AI deve reindicizzare le schede Carta docente/Spese con la nuova semantica.
- Prova locale Docker `2.253.110` su `127.0.0.1:8080`: `app`, `scheduler-worker` e `ocr-worker` healthy; il gate `check_runtime_services.py --wait-job-seconds 900 --require-all-due-jobs` ha atteso la run automatica reale del worker e ha confermato `lex_sentenza_economia_auto` `completed` alle `12:40:14Z`, `errors=0`, `vector_embedding_errors=0`.
- Prova visiva locale: `/fascicoli?vista=economica` e `/fatturazione` full React, filtri fatturazione `Bonifico registrato`, `Parcella emessa`, `Nome cliente` e `RG o ID fascicolo` funzionanti, focus visibile e responsive desktop/tablet/mobile senza overflow orizzontale.
