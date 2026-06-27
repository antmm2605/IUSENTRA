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

## Etichetta React economia 2.253.111

- Durante la prova visiva di produzione della `2.253.110` sul fascicolo `FC81009F` / `RG 697/2025` è emerso un difetto UI: il dato era già classificato come `Spese/esborsi`, ma la griglia economica continuava a usare l'etichetta statica `Contributo unificato` in intestazione e negli `aria-label`.
- Il bridge React espone ora `displayLabel` e `natura` per ogni voce economica; la UI usa `displayLabel` per testi, salvataggi e accessibilità. La colonna storica diventa `Contributo / spese`, mentre il singolo record mostra `Spese/esborsi` quando la sentenza parla di esborsi.
- Il badge compatto non ripete più la natura normalizzata quando coincide con l'etichetta: `Spese/esborsi` resta una sola volta, mentre casi diversi come `Contributo unificato da PDF` possono ancora mostrare la natura di controllo.
- Prova locale Docker `2.253.111` su `127.0.0.1:8080`: `app`, `scheduler-worker` e `ocr-worker` sono allineati alla stessa versione; il gate `check_runtime_services.py --wait-job-seconds 900 --require-all-due-jobs` ha atteso la run automatica reale del worker e ha confermato `lex_sentenza_economia_auto` `completed` alle `13:50:13Z`, `errors=0`, `vector_embedding_errors=0`.
- Prova visiva locale su `/fascicoli?vista=economica`: desktop `scrollWidth=clientWidth`, header `CONTRIBUTO / SPESE`, badge `Spese/esborsi`, `aria-label` `Spese/esborsi - importo`, focus leggibile sull'input importo, hover sul pulsante salva senza testo illeggibile. Mobile `390x844` e tablet `768x1024` senza overflow orizzontale, con `Spese/esborsi` visibile nella card economica.

## Gate worker automatici e runtime 2.253.112

- Durante il deploy `2.253.111` il gate server ha bloccato correttamente il rilascio: `lex_sentenza_economia_auto` era rimasto `running` oltre la finestra attesa e `pec_audit_pipeline_workers` registrava `missed` perché una istanza precedente era ancora in corso.
- Diagnosi con log e `strace` sul server Hetzner: il backfill sentenze leggeva e compattava testi molto grandi anche quando il documento non era una sentenza. La causa strutturale era che, se mancava la classificazione, `_metadata_for_text` assegnava di default `Sentenza Tribunale`, rendendo il parser troppo permissivo e costoso.
- Correzione: il backfill non inventa più la classificazione `Sentenza Tribunale`, fa una sola passata sugli `extracted_text.json`, raccoglie la prova CU/PagoPA solo su documenti con segnali rapidi e aggancia la prova al candidato sentenza prima dell'applicazione. Il parser evita la compattazione completa quando mancano segnali reali di sentenza.
- Seconda causa reale: la pipeline PEC provava a trattare allegati con header `PCTEN` e nome `.pdf` come PDF, generando warning `pypdf` e consumo inutile. Ora i PDF vengono passati a OCR/PDF reader solo se il contenuto inizia con `%PDF-`; le buste o payload non PDF restano `non_applicabile` con motivo `contenuto non PDF`.
- Test aggiunti: metadato senza classificazione non diventa sentenza, la prova CU letta dopo la sentenza resta collegata (`spese_esborsi_confermate_pdf`), e gli allegati `PCTEN` mascherati da PDF vengono saltati sia in OCR sia in verifica firma.

## Gate worker automatici e concorrenza SQLite 2.253.113

- Durante il deploy server della `2.253.112` il gate runtime ha bloccato di nuovo il rilascio: il worker era vivo, ma `lex_sentenza_economia_auto` ha registrato prima `database is locked` sulla tabella `parcelle` e poi una nuova run `running` non ancora conclusa entro la finestra di attesa del controllo.
- Diagnosi server: il job sentenze partiva al minuto `*/10`, quindi allo stesso secondo di `pec_audit_pipeline_workers`, `mailbox_sync_runtime` e `local_ai_maintenance` nei minuti `:30`. In parallelo, `GestioneFatturazione` sostituiva tutta la tabella `parcelle` anche quando doveva aggiornare una sola proforma Lex AI.
- Correzione fatturazione: con backend SQLite/PostgreSQL governato da `StudioDB`, creazione/aggiornamento/cambio stato di una parcella fanno `UPSERT` del singolo record invece di `DELETE` completo e reinserimento della tabella. La cancellazione resta gestita dal percorso esistente, ma il flusso automatico sentenze non tiene più un lock tabellare lungo per una sola proforma.
- Correzione scheduler: `lex_sentenza_economia_auto` resta automatico ogni dieci minuti, ma viene sfalsato sui minuti `7-57/10` per non partire insieme ai job PEC, mailbox e manutenzione AI. La migrazione del registry aggiorna gli studi già salvati con la vecchia schedulazione `*/10`.
- Correzione PEC aggiuntiva: gli allegati `.p7m` non CAdES/PKCS#7 non vengono più passati al controllo firma/PDF; restano `non_applicabile` con dettaglio `contenuto non CAdES/PKCS#7`, evitando warning pypdf su payload come `PCTEN`.
- Il gate `scripts/check_runtime_services.py` accetta il cron sfalsato come intervallo reale di dieci minuti e continua a bloccare se il worker non produce una run `completed` con `totals`, `errors=0` e `vector_embedding_errors=0`.

## Filtro fatturazione RG completo 2.253.114

- Durante la prova visiva reale di produzione su `https://app.iusentra.it/fascicoli?vista=economica` il fascicolo `FC81009F` / `RG 697/2025` risultava corretto nella matrice economica: `Spese/esborsi` `EUR 21,50`, `Liquidazione giudice` `EUR 321,50`, `Parcella` `EUR 490,61`, totale `EUR 343,00`, data `23/09/2025`.
- La stessa prova su `/fatturazione` ha trovato un difetto reale di filtro: la proforma Montagnese esisteva, ma il filtro `Nr fascicolo` trovava il record con `697` o `FC81009F` e non con `697/2025`, perché il bridge fatturazione esponeva solo `numero_rg` quando `numero_rg` e `anno_rg` erano salvati in campi separati.
- Correzione: `react_fatturazione_bridge` ricostruisce sempre il RG completo da `rg_completo` oppure da `numero_rg` + `anno_rg`; `caseRg`, `caseReference`, `caseTitle`, opzioni fascicolo e profilo fascicolo usano lo stesso valore. La card proforma deve quindi mostrare e filtrare `RG 697/2025`, non solo `RG 697`.
- Test aggiunto: `test_bridge_fatturazione_ricostruisce_rg_completo_da_numero_e_anno` presidia il caso Montagnese con `numero_rg=697` e `anno_rg=2025`.

## Gerarchia operativa fatturazione 2.253.115

- Segnalazione utente del 25/06/2026 su `https://app.iusentra.it/fatturazione`: i blocchi informativi `PDF, XML ed export restano governati`, `Avvisi economici` e `Invio e monitoraggio SdI` occupavano la pagina prima delle funzioni realmente usate.
- Correzione React: nella vista archivio di `/fatturazione` la prima parte mostra indicatori, card operative, filtri e archivio parcelle/proforme; numerazione resta subito dopo l'archivio; i presidi fiscali e SdI vengono conservati in un pannello compatto richiudibile a fondo flusso.
- Il percorso di recupero legacy non viene più mostrato nella vista archivio fatturazione: non deve sembrare una soluzione operativa alternativa rispetto al flusso React principale.
- La regola da preservare è funzione prima di spiegazione: filtri per bonifico, parcella emessa, cliente e nr fascicolo, record proforma/parcella e azioni `Emetti parcella` / `Registra bonifico` devono restare più in alto dei presidi informativi.
- Correzione visuale successiva richiesta dall'utente: i KPI a `EUR 0,00` non vengono più mostrati quando sono tutti a zero; i chip operativi restano in alto e il record archivio resta subito leggibile. Il titolo `Archivio parcelle e fatture` non viene più spostato sotto i record perché `Panel` usa l'header sezione senza riordino route-sequence.
- La testata `/fatturazione` usa un override circoscritto alla pagina: altezza reale `72px`, padding `12px 18px`, titolo `24px`, senza cambiare le altre route React.
- Prova reale locale su Docker `http://127.0.0.1:8080/fatturazione`, versione `2.253.115`: browser integrato visibile, `#root` presente, nessun pannello informativo obsoleto sopra l'archivio, nessun KPI zero, click reali su `Bonifico registrato`, `Parcella emessa` e `Azzera filtri` con select e conteggi aggiornati, tablet `768x1024` e mobile `390x844` senza overflow orizzontale.

## Presidio PEC, OCR e prova worker 2.253.116

- Correzione richiesta dall'utente: il presidio PEC deve restare super funzionale e non deve rompere lettura di ZIP, XML, allegati compressi, catalogazione, agenda, scadenziario, notifiche, Web Push, Lex AI e DB vettoriale.
- `pct.document_intelligence.extraction` non manda più ai parser PDF un contenuto che non inizia come PDF reale. Se il documento è etichettato `.pdf` ma contiene ZIP, XML o testo recuperabile, il software usa il parser corretto e conserva un warning esplicito; se è un payload non leggibile, fallisce con `pdf_magic_mismatch` invece di produrre warning pypdf ripetuti.
- La pipeline PEC deduplica `issues`, `agent_questions` e `recommended_actions` senza togliere semantica: gli stessi controlli restano, ma la UI non deve più mostrare testi operativi ripetuti quando profilo procedurale, contesto semantico e workflow generano la stessa frase.
- `scripts/check_runtime_services.py` ora conserva anche gli ultimi run recenti: se il job obbligatorio `lex_sentenza_economia_auto` ha già una run `completed` valida dopo il deploy e subito dopo il worker ne ha avviata una nuova ancora fresca, il gate usa la completed come prova reale e registra `superseded_running_started_at`. Una run `running` stantia, fallita, missed o senza totals resta bloccante.
- Integrazione Unlimited-OCR: il motore `unlimited-ocr` è disponibile ma spento di default, local/private-first e con fallback corrente. È pensato per benchmark OCR+Lex su PDF lunghi/scansionati; non invia documenti legali a endpoint esterni senza `IUSENTRA_UNLIMITED_OCR_EXTERNAL_ALLOWED`.
- La pipeline OCR produce anche `vector_index_manifest` e `vector_chunks.jsonl`, così i testi OCR validati hanno una base strutturata per l'indicizzazione Lex/vector DB senza sostituire SQL o i repository documentali come fonte di verità.
- Nessun backup creato per questa release. La verifica deve includere test mirati PEC/OCR/runtime, build React, Docker locale reale su `127.0.0.1:8080`, prova visiva `/fatturazione`, gate worker locale e gate worker Hetzner dopo deploy.

## Cursore incrementale job Lex Sentenze 2.253.117

- Chiarimento utente del 25/06/2026: tutti i job frequenti devono usare la stessa logica operativa, altrimenti il software diventa pesante. Dopo che un archivio è stato letto e completato, i giri successivi devono lavorare solo nuovi arrivi o pendenti, non ripartire da capo.
- `lex_sentenza_economia_auto` ora legge dall'ultimo run completato il cursore `mtime_ns` e passa al backfill solo gli `extracted_text.json` modificati dopo quel valore. I documenti invariati restano catalogati nei conteggi, ma non vengono aperti e parsati.
- La full scan resta possibile solo con `IUSENTRA_SENTENZA_LEX_FULL_SCAN=1`, quindi un controllo completo è una manutenzione esplicita e non il comportamento ordinario ogni dieci minuti.
- Il report espone `scan_mode`, `incremental`, `documents_catalogued`, `documents_seen` e `skipped_by_cursor`; il gate runtime accetta un run incrementale con `documents_seen=0` solo se esiste il riepilogo operativo e `errors=0`, `vector_embedding_errors=0`.
- La stessa disciplina di audit è stata estesa ai job frequenti collegati: `pec_audit_pipeline_workers`, `mailbox_sync_runtime`, `calendar_sync_engine_retry` e `local_ai_maintenance` restituiscono `scan_mode`/`totals` e non restano più righe scheduler mute.
- Con `--require-all-due-jobs`, il gate blocca i job operativi frequenti completati senza `totals` o con `errors>0`, così il worker deve dimostrare cosa ha fatto davvero.
- Test mirati aggiunti: `test_backfill_sentenza_incrementale_salta_documenti_invariati`, `test_lex_sentenza_economia_job_riusa_cursore_ultimo_run` e `test_validate_scheduler_run_audit_accetta_job_sentenza_incrementale_senza_nuovi_documenti`.

## CU da PDF, esenzione e bonifica vettori RAG 2.253.118

- Chiarimento utente del 25/06/2026: gli importi economici della sentenza devono essere corretti al 100% perché alimentano fatturazione e DB vettoriale Lex AI. In particolare il contributo unificato non deve essere inventato da valore causa, scaglione o importi generici della sentenza; può essere riportato solo se esiste prova nel fascicolo.
- Il parser distingue ora tre voci:
  - `liquidazione_giudice`: importo spettante allo studio, estratto da formule come `Euro 1500,00 per compensi professionali`;
  - `spese_esborsi`: spese vive/esborsi riconosciuti in sentenza, per esempio `Euro 125,00 per spese`;
  - `contributo_unificato`: importo CU solo da PDF/documento PagoPA/CU del fascicolo, oppure stato esente se il fascicolo contiene `contributo unificato non dovuto`, `esente dal pagamento del contributo unificato`, `patrocinio a spese dello Stato` o `prenotazione a debito`.
- Se il cliente è esente dal CU, la matrice salva `contributo_unificato` con `status=non_previsto`, `previsto=false`, `importo=null`, `natura=esenzione_contributo_unificato` e label `Contributo unificato esente`. Non viene creata una voce proforma CU senza importo.
- Lo schema vettoriale passa a `sentenza_tribunale_compact_v4` e include `contributo_unificato_esente`, `contributo_unificato_natura`, `contributo_unificato_label` e `spese_esborsi`, così Lex AI non può riusare schede v3 con semantica economica vecchia.
- Il reset `--reset-lex-amounts` cancella ora anche i documenti RAG rigenerabili `source_type=lex_sentenza_tribunale` del tenant. Questo evita che vecchie risposte Lex continuino a usare importi sbagliati anche dopo la pulizia dei pagamenti fascicolo.
- Prova locale dati del tenant `tenant-8bf98719c459`: `studio.db` e `intelligence/local_ai.db` con `PRAGMA integrity_check=ok`; backfill full scan con report `artifacts/unlimited-ocr/sentenza-economia-reset-apply-v5-rag-clean-20260625.json`, `documents_seen=667`, `raw_sentenze_found=14`, `sentenze_found=7`, `applied=1`, `matrix_confirmed=1`, `vector_indexed=1`, `vector_embedding_errors=0`.
- Caso `DC5BF1DB`: `liquidazione_giudice=1500,00`, `contributo_unificato=98,00` da PDF fascicolo, `spese_esborsi=125,00`, proforma `c6a1c268-2f55-4583-9ac9-ca2d90c316c1` con voci `1500,00`, `98,00`, `125,00`, totale `2126,20`.
- Caso `AF656B01`: nessun pagamento Lex residuo, nessuna proforma Lex residua e nessun documento RAG `lex_sentenza_tribunale` residuo con il falso `5200,00`.
- Audit dati dopo la bonifica: `audit_data_flow_contract.py` repair e cold ok; `audit_tenant_data_structure.py` repair e cold ok, `source_of_truth=sqlite`, `json_authoritative=false`, `operational_untracked=0`, zero warning e zero errori.

## CU da PDF e voce unica Spese/esborsi 2.253.126 - 2026-06-26

- Segnalazione utente: nella vista economica alcuni fascicoli reali riportavano `Contributo unificato da PDF` con importi falsi, in particolare `500,00` da sentenze Carta docente e `38.514,03` da dichiarazione reddituale/esenzione. Il dato era pericoloso perché alimenta Lex AI, vettori RAG, parcelle e decisioni operative dell'avvocato.
- Il riconoscimento del contributo unificato da PDF è stato ristretto: un importo viene accettato solo con ancoraggio di pagamento reale (`PagoPA`, `IUV`, ricevuta/avviso pagamento, F23/F24, importo versato/pagato) o con esenzione esplicita. Sentenze, ricorsi, autocertificazioni reddituali, soglie DPR 115/2002, Carta docente e importi nominali annui non possono più diventare CU.
- La voce storica `fondo_spese` non è più una colonna operativa autonoma: viene normalizzata in `spese_esborsi`, etichettata `Spese/esborsi`, e gli importi legacy vengono assorbiti senza doppio totale. La rotta legacy `/pagamenti/fondo_spese` resta compatibile ma salva sotto `spese_esborsi`.
- Vista React fascicoli: rimossa la colonna/filtro `Fondo spese`, lasciate le sole colonne economiche `Contributo`, `Spese/esborsi`, `Liquidazione`, `Parcella`; la griglia è stata allargata e i testi lunghi di badge/source/details ora vanno a capo invece di tagliarsi.
- Script operativo aggiunto: `scripts/merge_fondo_spese_into_spese_esborsi.py`, senza backup, tenant-aware e basato sui repository runtime SQLite/PostgreSQL; serve per ripulire i dati esistenti e prevenire doppioni.
- Bonifica locale reale del tenant `tenant-8bf98719c459`: `sentenza-economia-reset-local-v6-cu-fondo-20260626.json` con `documents_catalogued=667`, `errors=0`, `vector_embedding_errors=0`, `reset_payment_entries_removed=4`, `reset_vector_documents_removed=2`, `vector_indexed=1`; `fondo-spese-merge-local-apply-20260626.json` con `fascicoli_seen=7`, `legacy_entries_removed=0` perché il tenant locale non aveva più chiavi legacy.
- Controllo a freddo locale pagamenti: `bad_fondo=[]`, `bad_cu=[]`, `fascicoli=7`, `cu_entries=0`, `spese_entries=1`.
- Stato da completare prima della chiusura: rebuild Docker locale su `127.0.0.1:8080`, prova browser reale della vista economica, commit/push branch gemelli, check GitHub/CodeQL, deploy Hetzner, reset/backfill e merge produzione su `/data`, verifica dei fascicoli reali segnalati nello screenshot.

## CU da PDF e voce unica Spese/esborsi 2.253.126 - verifica locale finale - 2026-06-26

- Rebuild Docker locale completato con `docker compose build --no-cache app scheduler-worker ocr-worker` e recreate di `app`, `scheduler-worker`, `ocr-worker`.
- `/api/pronto` locale: `ok=true`, `timezone=Europe/Rome`, `versione=2.253.126`; i tre container applicativi espongono tutti `pct.__version__=2.253.126`.
- Gate runtime finale `scripts/check_runtime_services.py --wait-job-seconds 900 --require-all-due-jobs`: `lex_sentenza_economia_auto` completato dopo il riavvio, `documents_catalogued=667`, `skipped_by_cursor=667`, `errors=0`, `vector_embedding_errors=0`.
- Prova browser integrato su `http://127.0.0.1:8080/fascicoli?vista=economica`: desktop, tablet e mobile verificati; nessuna colonna/card/filtro `Fondo spese`; intestazioni e card mostrano `Spese/esborsi` come voce unica.
- Caso locale RG `466/2023`: `Contributo unificato da pagare` `EUR 98,00`, stato `Da registrare`, data vuota; `Spese/esborsi` `EUR 125,00`, `Liquidazione` `EUR 1.500,00`, `Parcella` `EUR 2.028,20`; totale registrato `EUR 1.625,00`.
- La UI economica è stata rifinita: le note lunghe restano compatte chiuse, si leggono aprendo `Dettagli`, e il focus sul campo `Spese/esborsi - metodo` è visibile senza sovrapposizioni.
- Stato residuo non locale: commit/push, check GitHub/CodeQL, deploy Hetzner e bonifica una tantum dei dati server già salvati con euristiche precedenti.
## CU esente senza data pagamento 2.253.127 - 2026-06-26

## Vista economica compatta 2.253.128 - 2026-06-26

- Dopo la verifica visiva su produzione la tabella economica risultava ancora troppo larga: la vecchia `min-width` da 2048px teneva conto di quattro colonne economiche separate e produceva scrollbar interne anche dopo l'unificazione di `fondo_spese` in `Spese/esborsi`.
- Correzione React: la vista economica desktop usa ora una sola colonna `Controllo economico`, con matrice interna per `Contributo`, `Spese/esborsi`, `Liquidazione giudice` e `Parcella`. Le quattro voci restano modificabili singolarmente, ma non occupano più quattro colonne tabellari.
- Il comportamento dati non cambia: `Fondo spese` resta solo alias legacy verso `spese_esborsi`, non viene ricreata una voce autonoma e non ci sono doppi importi per la stessa causale.
- Gate mirati eseguiti prima del rebuild Docker: suite OCR/economia, backfill, filtri economici, UTF-8, packaging, OpenAPI e build React.
- Verifica locale reale completata il 27/06/2026 su Docker `127.0.0.1:8080`, versione `2.253.128`: `app`, `scheduler-worker` e `ocr-worker` healthy, `/api/pronto` in `Europe/Rome`, browser integrato desktop `1440x900` e mobile `390x844` senza overflow orizzontale, console senza errori.
- Caso locale RG `466/2023`: la matrice desktop e la card mobile mostrano `Contributo unificato da pagare EUR 98,00 Da registrare`, `Spese/esborsi EUR 125,00 Pagato`, `Liquidazione giudice EUR 1.500,00 Pagato`, `Parcella EUR 2.028,20 Da emettere`, totale registrato `EUR 1.625,00`; nessun `Fondo spese` e nessun falso CU `EUR 500,00`.
- Worker locale dopo rebuild: `lex_sentenza_economia_auto` completato alle `2026-06-26T23:57:14Z`, `documents_catalogued=667`, `skipped_by_cursor=667`, `errors=0`, `vector_embedding_errors=0`. Questo conferma che, dopo il deploy, il server usa automaticamente la nuova pipeline per i prossimi fascicoli; l'intervento manuale resta solo bonifica una tantum dei valori storici già salvati.

- Corretto il salvataggio del contributo unificato esente: la pipeline mantiene `Contributo unificato esente`, `status=non_previsto`, `importo=null`, ma non compila più `data_pagamento` con la data della sentenza.
- Il backfill `--reset-lex-amounts` v9 rigenera la matrice economica locale usando questa regola, così i vecchi importi e le vecchie date fittizie vengono sostituiti dalla logica governata.
- Prova locale reale su `127.0.0.1:8080`: vista economica Fascicoli verificata in browser integrato desktop e mobile, senza colonna `Fondo spese`, con `Spese/esborsi` unica e senza overflow orizzontale.

## Vista economica leggibile 2.253.132 - 2026-06-27

- Segnalazione utente: la prova visiva server mostrava `/fascicoli?vista=economica` non leggibile; la tabella economica restava troppo compressa e la vecchia modifica dentro la cella rischiava sovrapposizioni tra righe.
- Correzione React: la riga economica desktop mostra una sintesi compatta a due colonne dentro `Controllo economico`; la modifica dei quattro valori (`Contributo`, `Spese/esborsi`, `Liquidazione`, `Parcella`) si apre in una riga editor dedicata sotto il fascicolo, non dentro la cella della tabella.
- Correzione layout: intestazione finale accorciata a `Totale`, select stato vincolata alla colonna, header con ellissi e totale senza overflow. La tabella resta `full React`, senza modifiche alla logica dati, al parser sentenze, ai job PEC/OCR o ai repository economici.
- Prova reale locale su Docker `127.0.0.1:8080`, versione `2.253.132`, con Chrome installato visibile (`C:/Program Files/Google/Chrome/Application/chrome.exe`) perché il browser integrato non era disponibile nella sessione: `/api/pronto` `ok=true`, `timezone=Europe/Rome`.
- Prova desktop `1440x900`: `wrapClientWidth=1091`, `wrapScrollWidth=1091`, `bodyScrollWidth=bodyClientWidth=1425`, `summaryCount=28`, `toggleCount=7`, header `TOTALE`, console senza errori.
- Prova apertura editor: focus/hover su `Modifica controllo economico` visibile, `editorFitsWrap=true`, `overlapsNextRow=false`, `formCount=4`, `saveButtonCount=4`, `selectCount=4`, `inputCount=16`, campi `Stato`, `Importo`, `Data`, `Metodo e note` presenti.
- Prova responsive: tablet `768x1024` con `bodyScrollWidth=bodyClientWidth=753`, mobile `390x844` con `bodyScrollWidth=bodyClientWidth=375`; le card mobile restano leggibili e mostrano la matrice economica senza overflow orizzontale.
