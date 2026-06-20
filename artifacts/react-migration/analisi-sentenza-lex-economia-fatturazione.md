# Analisi operativa: Sentenza Lex AI, fascicolo, economia e fatturazione

Ultimo aggiornamento: 2026-06-20.

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

## Prova reale locale 2.253.86

- Docker locale ricostruito e riavviato su `http://127.0.0.1:8080`; `/api/pronto` ha risposto `versione=2.253.86` e i container `app`, `scheduler-worker`, `ocr-worker`, `redis` risultano healthy.
- Il browser integrato non era agganciabile tramite Node REPL per errore MCP `missing field sandboxPolicy`; la prova visiva è stata quindi eseguita in Google Chrome installato e visibile (`C:\Program Files\Google\Chrome\Application\chrome.exe`) con profilo temporaneo e sessione locale autenticata.
- `/fatturazione` è stata verificata con React attivo, scroll completo, pannello numerazione, hover/focus sul campo `Ultimo numero usato`, click su `Salva numerazione` e conferma `Numerazione fatture aggiornata.`.
- `/fascicoli` è stata verificata sulla lista reale locale: colonne `Prossima scad.` e `Stato` visibili, metriche e tab coerenti, nessun fallback legacy o overlay di errore.
- Responsive verificato su desktop, tablet e mobile: nessun overflow orizzontale rilevato su tablet/mobile e testi principali leggibili nelle card.
- Per coprire i pulsanti proforma, sono state create due proforme controllate locali con origine `Sentenza Lex AI`, poi rimosse dal DB a fine prova: `2026/001` è passata con click reale da `Proforma/Bozza` a `Fattura/Emessa`; `2026/002` è passata con click reale su `Registra bonifico` a `Fattura/Pagata` con incasso `20/06/2026`.
- Durante la prova è ricomparso il lock SQLite tipico del volume Windows/Docker; è stato risolto con riavvio dei servizi applicativi, verifica di scrittura e pulizia dei record controllati. A fine prova `/api/pronto` è tornato OK su `2.253.86` e i record di test risultano assenti.
- La verifica sui fascicoli reali e sui documenti sentenza presenti solo sul server resta parte del deploy Hetzner: dopo il push la produzione dovrà processare i documenti reali e mostrare la matrice economia/DB vettoriale sugli stessi dati dello studio.
