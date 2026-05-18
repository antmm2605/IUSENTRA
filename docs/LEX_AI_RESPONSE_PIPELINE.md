# Percorso obbligatorio per arrivare alla risposta di Lex AI

Data di registrazione: 18 maggio 2026.

Questo documento serve a impedire risposte generiche quando una domanda ha già
un riferimento ufficiale nel database. Ogni passaggio deve essere verificabile:
se un punto non funziona, Lex deve dire quale punto è saltato, non rispondere
con un finto completamento.

## Caso guida

Domanda utente:

```text
Quale allegato ufficiale ha la questione penale R.G. 9926/2026?
```

Evidenza ufficiale già acquisita:

- pagina Cassazione: `https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194`;
- allegato ufficiale: `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`;
- titolo allegato: `Ordinanza di rimessione`;
- testo OCR salvato nel database;
- hash SHA-256 salvato;
- nota obbligatoria: la domanda scrive `9926/2026`, mentre il documento ufficiale
  acquisito riporta `9966/2026`. Lex deve segnalare la discrepanza e non deve
  fingere che i due numeri siano identici.

Risposta minima attesa:

```text
Ho trovato una fonte ufficiale Cassazione collegata. L'allegato ufficiale è
"Ordinanza di rimessione", PDF:
https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf

Attenzione: nella domanda compare R.G. 9926/2026, mentre nell'allegato ufficiale
acquisito risulta R.G. 9966/2026. Va verificato se è un refuso o se si cerca un
altro procedimento.
```

## Passaggi obbligatori

1. L'utente scrive la domanda nel widget Lex.
   - Il testo non deve essere modificato in modo distruttivo.
   - Numeri, sigle e URL devono restare disponibili: `R.G.`, `9926/2026`,
     `QSP50194`, `Cassazione`, `allegato`, `ordinanza`, `PDF`.

2. Il frontend invia la richiesta all'endpoint chat.
   - Il widget deve inviare domanda, route corrente, eventuale fascicolo attivo,
     tenant e contesto autorizzato.
   - La UI non deve sostituire una risposta tecnica con un messaggio generico se
     il backend restituisce sorgenti o lacune.

3. Il backend costruisce il contesto operativo.
   - Vengono risolti utente, studio e tenant.
   - I permessi decidono quali archivi possono essere consultati.
   - La domanda non deve uscire dallo studio senza percorso governato.

4. Il router classifica la domanda.
   - Se la domanda contiene segnali come `Cassazione`, `QSP`, `R.G.`,
     `questione penale`, `allegato ufficiale`, `ordinanza di rimessione`,
     `circolare`, `messaggio`, `Gazzetta`, `Normattiva` o `fonte ufficiale`,
     deve usare la rotta delle fonti ufficiali e degli aggiornamenti legali.
   - Non deve usare `documenti collegati` salvo richiesta esplicita di documenti
     del fascicolo interno o allegati caricati dallo studio.

5. Il servizio operativo esegue gli strumenti della rotta scelta.
   - Per fonti legali deve interrogare almeno:
     - inventario legal intelligence;
     - archivio aggiornamenti legali;
     - catalogo fonti ufficiali.
   - Il percorso decisivo per questo caso è l'archivio aggiornamenti legali.

6. L'archivio aggiornamenti legali interroga il database.
   - La ricerca deve usare titolo, URL, fonte, estratto, testo OCR, hash,
     `attachment_url`, `attachments_json` e numero R.G.
   - Se la domanda chiede un allegato, i risultati con `attachment_url` e testo
     OCR reale devono essere promossi prima della pagina generica.

7. Il database deve restituire prove reali, non solo riferimenti.
   - Prova minima valida:
     - URL pagina ufficiale;
     - URL allegato ufficiale;
     - titolo allegato;
     - estratto leggibile;
     - hash o metadato di download;
     - stato della verifica.
   - Se manca il testo OCR ma esistono URL e hash, Lex deve dirlo chiaramente.

8. Il compositore costruisce una risposta leggibile.
   - Deve citare il nome dell'allegato e il link ufficiale.
   - Deve indicare se la fonte è Cassazione, Gazzetta, INPS, Normattiva o altra
     fonte riconosciuta.
   - Deve evidenziare le discrepanze, per esempio `9926/2026` contro
     `9966/2026`.
   - Non deve limitarsi a contare le fonti trovate.

9. La risposta torna al widget Lex.
   - Il testo deve essere impaginato in modo leggibile.
   - I link devono essere cliccabili.
   - Non devono comparire messaggi come `Non ho trovato dati reali sufficienti`
     quando il database ha restituito un allegato ufficiale valido.

10. L'audit registra cosa è stato consultato.
    - Devono essere tracciati rotta scelta, strumenti chiamati, numero risultati,
      sorgenti, eventuali lacune e motivo di blocco.
    - Se viene usata la rotta sbagliata, il test deve fallire.

## Ricerca web libera manuale

La ricerca web libera non deve essere un job, una pianificazione o una coda.
Parte solo dalla domanda Lex quando l'utente attiva il comando `Web libero` nel
widget.

Passaggi obbligatori:

1. Il widget invia insieme alla singola domanda:
   - `free_web_enabled=true`;
   - `force_free_web_search=true`;
   - `public_web_forced=true`;
   - `web_execution_requested=true`;
   - `source_mode=free_web`.
2. Il backend applica questi flag solo a quella richiesta.
3. Lex non applica allowlist ufficiali e non blocca per mancanza di fonte
   autorizzata.
4. Lex non porta quei risultati dentro il database, il corpus, la coda review o
   gli archivi fonti: valgono solo per la singola risposta in chat.
5. Il router non deve trascinare fonti DB, fascicolo o contesto pagina dentro la
   modalità libera; il risultato resta marcato `web_libero`,
   `verified_reference=false`.
6. La risposta non deve mostrare warning o avvisi di responsabilità: in questa
   modalità il software esegue la ricerca richiesta e il controllo spetta
   interamente all'avvocato.
7. La console pianificazioni non deve creare, avviare o mostrare job per questa
   funzione.

## Prove prima di dichiarare risolto

1. Test del router:
   - la domanda `Quale allegato ufficiale ha la questione penale R.G. 9926/2026?`
     deve andare alle fonti ufficiali, non a `documenti_fascicolo`.
   - la domanda `Questione Penale Pendente del ricorso R.G. 9926/2026` non deve
     mai essere classificata come bozza di atto solo per la parola `ricorso`.

2. Test del repository:
   - la stessa domanda deve restituire come primo risultato l'allegato
     `Ordinanza di rimessione` con URL PDF ufficiale.

3. Test del compositore:
   - la risposta deve contenere `Ordinanza di rimessione`;
   - deve contenere il link PDF;
   - deve segnalare la discrepanza `9926/2026` / `9966/2026` quando presente;
   - non deve contenere `Non ho trovato dati reali sufficienti`.

4. Test end-to-end del servizio Lex:
   - chiamata con lo stesso testo della domanda reale;
   - verifica della rotta;
   - verifica del testo finale;
   - verifica delle sorgenti restituite.

5. Verifica produzione:
   - il container deve avere la versione corretta;
   - il database di produzione deve contenere pagina, PDF, OCR e hash;
   - la domanda reale deve rispondere con allegato e nota sulla discrepanza;
   - il deploy deve rispettare `no backup`.

## Regola di blocco

Il lavoro non può essere dichiarato chiuso se uno solo di questi punti resta
vero:

- la domanda viene classificata come `documenti collegati`;
- il repository trova l'allegato ma Lex non lo usa;
- la risposta non mostra il link ufficiale;
- la risposta ignora la differenza tra `9926/2026` e `9966/2026`;
- il widget mostra ancora `Non ho trovato dati reali sufficienti` per questo
  caso.

## Correzione percorso widget del 18 maggio 2026

Problema riscontrato in produzione:

```text
Questione Penale Pendente del ricorso R.G. 9926/2026
```

veniva risposta dal percorso editor con:

```text
Riferimento: fascicoli rilevanti
Editor Lex: Editor normale e professionale con Lex...
Limiti: Nessun dato reale disponibile dalla sorgente template_atti.
```

Causa verificata:

1. Il focus conversazionale leggeva `ricorso` come competenza `atti_template`.
2. La parola `questione` veniva riconosciuta erroneamente come follow-up perché conteneva la sequenza `questi`.
3. La domanda effettiva diventava `atti template Questione Penale...`.
4. Il router operativo controllava `template` prima di `questione penale`, `QSP` e `R.G.`, quindi sceglieva `template_lookup`.
5. Il widget mostrava un riferimento di contesto non coerente con la fonte ufficiale richiesta.

Correzione applicata:

1. `web/services/assistente_conversation_focus.py` riconosce prima le richieste di fonte ufficiale (`questione penale`, `questione civile`, `QSP`, `R.G.`, allegato ufficiale, ordinanza di rimessione, Cassazione).
2. I marker di follow-up ora usano parole intere, quindi `questione` non attiva più `questi`.
3. `lex/operational_knowledge/query_router.py` dà priorità a `official_sources_lookup` prima di `template_lookup`.
4. `web/static/js/pct-lex-assistant.js` mostra il riferimento `fonti ufficiali` e non tratta la domanda come documento/bozza.
5. La prova end-to-end passa da `/api/assistente/chat` con cronologia precedente da editor, non solo dal servizio interno.

Test di blocco regressione:

```powershell
python -m pytest tests\test_assistente_focus.py::test_focus_conversazionale_rg_questione_penale_resta_fonte_ufficiale tests\test_lex_operational_knowledge.py::test_rg_questione_penale_prefisso_template_resta_fonte_ufficiale tests\test_lex_assistente_context_real_requests.py::test_assistente_chat_questione_penale_rg_non_finisce_nell_editor -q
node tests\js\lex_assistant_render.test.mjs
```

Esito atteso:

- rotta `official_sources_lookup`;
- risposta con `Ordinanza di rimessione`;
- link PDF `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`;
- nota sulla discrepanza `R.G. 9926/2026` / `R.G. 9966/2026`;
- assenza di `Editor Lex`, `template_atti`, `Camera Arbitrale` e fonti R.G. non pertinenti.

## Correzione qualità risposta del 18 maggio 2026

Problema residuo dopo la correzione del routing:

- Lex arrivava finalmente alla fonte ufficiale, ma mostrava una risposta troppo
  povera: indicava il PDF senza sintetizzare la questione giuridica.
- Il percorso streaming `/api/assistente/chat` comprimeva le risposte bounded con
  `clean_spaces`, perdendo titoli, righe e punti elenco.
- Il renderer del widget interpretava gli underscore dell'URL PDF come enfasi
  Markdown, spezzando il link in frammenti non professionali.

Regola aggiornata:

1. Per una domanda come `Questione Penale Pendente del ricorso R.G. 9926/2026`,
   Lex deve rispondere al contenuto della scheda, non solo all'esistenza del PDF.
2. Se nel DB esistono sia la pagina Cassazione sia l'allegato, la risposta deve
   includere:
   - quesito ufficiale;
   - riferimenti normativi;
   - data udienza, relatore e ricorrente quando presenti;
   - allegato ufficiale e URL PDF;
   - nota sulla discrepanza `9926/2026` / `9966/2026`;
   - distinzione tra dato certo e punto da verificare.
3. Il widget deve preservare titoli, elenchi e link cliccabili anche in streaming.

Test di blocco regressione aggiunti o aggiornati:

```powershell
python -m pytest tests\test_lex_operational_knowledge.py tests\test_lex_assistente_context_real_requests.py -q
node tests\js\lex_assistant_render.test.mjs
```

Risposta sostanziale minima attesa:

```text
Ho trovato una fonte ufficiale collegata alla richiesta.

Cosa dice la scheda ufficiale:
- Questione: se, avverso la sentenza emessa a seguito di concordato in appello,
  siano deducibili con il ricorso per cassazione i vizi attinenti alla
  determinazione della pena non comportanti l'illegalità della stessa.
- Riferimenti normativi: Cod. proc. pen. artt. 599-bis e 606.
- Scheda: inserita il 05 maggio 2026; udienza 09 luglio 2026; relatore
  E. Morosini; ricorrente Turco G.

Allegato ufficiale:
- Ordinanza di rimessione.
- PDF ufficiale cliccabile.

Punto da verificare:
- La domanda cita R.G. 9926/2026, mentre l'allegato acquisito riporta
  R.G. 9966/2026.
```

## Generatore Corpus Fonti

Il passaggio successivo al collaudo fonte è il generatore del corpus reale:
`scripts/generate_lex_source_corpus.py`.

Regole:

- legge solo `web_verification_evidence`;
- non naviga il web;
- non chiama LLM o provider esterni;
- include nel corpus solo evidenze con `content_text` e `context_chars`
  sufficienti;
- conserva metadati fonte: `review_id`, `normalized_document_id`,
  `source_url`, `attachment_url`, `sha256`, `source_code`,
  `verification_status`;
- produce `manifest.json`, `documents.jsonl`, `chunks.jsonl`,
  `expected_queries.jsonl` e un `documenti_ai/documenti_ai.json` compatibile
  con la pipeline dataset Lex;
- abilita l'uso RAG delle evidenze verificate senza revisione umana;
- non abilita training automatico: la revisione umana resta richiesta solo se
  le Q&A candidate vengono esportate o usate per training/fine-tuning.

Prova locale del 18 maggio 2026 sul DB
`data/intelligence/legal_updates.db`:

```powershell
python scripts\generate_lex_source_corpus.py `
  --intelligence-db data\intelligence\legal_updates.db `
  --output-dir tmp\lex-source-corpus-local `
  --limit 100 `
  --overwrite
```

Esito: 2 evidenze verificate leggibili, 2 documenti corpus, 13 chunk.

Dry-run dataset sul corpus generato:

```powershell
$env:PYTHONPATH='.'
python scripts\build_lex_studio_dataset.py `
  --tenant-id legal-sources `
  --document-ai-json tmp\lex-source-corpus-local\documenti_ai\documenti_ai.json `
  --max-documents 100
```

Esito RAG: 2 documenti e 13 chunk leggibili da Lex senza revisione umana.

Esito dataset opzionale: 13 task Q&A candidate e 13 coppie candidate, training
automatico disattivato, training esterno disattivato. La revisione umana è
obbligatoria solo prima di usare quelle Q&A per training/fine-tuning. È stato
rilevato 1 documento/chunk sensibile: l'export dataset resta governato e non va
trattato come training pronto.

## Prova Lex Locale

Prova del 18 maggio 2026 sulla domanda:

```text
Questione Penale Pendente del ricorso R.G. 9926/2026
```

Esito atteso e verificato:

- rotta Lex: `official_sources_lookup`;
- sorgenti effettive: pagina Cassazione QSP50194 e allegato `Ordinanza di
  rimessione`;
- PDF restituito:
  `https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`;
- nota visibile sulla discrepanza tra `R.G. 9926/2026` nella domanda e
  `R.G. 9966/2026` nell'allegato;
- nessun fallback `Non ho trovato dati reali sufficienti`;
- nessuna fonte non pertinente come `Camera Arbitrale` tra risposta e sorgenti.

La rotta con identificativo specifico filtra l'indice generale delle fonti
ufficiali: le schede generiche restano disponibili per ricerche generali, ma non
devono contaminare una risposta puntuale già fondata su `legal_updates.db`.

## Caso Pilota QSP 9926/2026 - Risposta Da Avvocato

Aggiornamento operativo del 18 maggio 2026.

Aggiornamento 2.245.26: la discrepanza `R.G. 9926/2026` / `R.G. 9966/2026`
non va più trattata come motivo per scartare il PDF, perché il collegamento
scheda -> PDF è già stato verificato. La regola corretta è: Lex cita la scheda
`9926/2026`, mantiene il PDF ufficialmente collegato e cliccabile, cita il
contenuto del PDF come contenuto del PDF collegato, ma non attribuisce
automaticamente dati processuali, parti, pena o contesto del PDF alla scheda
`9926/2026`. La risposta non deve riprodurre OCR sporco né fondere scheda e PDF
in un unico racconto certo.

Forma obbligatoria della risposta sintetica: una sola sezione `Sintesi` con
oggetto, stato, punto di diritto/principio, motivi/censure, effetto pratico e
nota R.G.; una sezione `Norme rilevanti` che spiega perché contano gli articoli;
una sezione `Fonte e PDF` con link cliccabile; poi `Punto da verificare` ed
`Esito`. Sono vietate risposte che ripetono `Cosa dice la scheda ufficiale`,
`Sintesi dell'ordinanza`, estratti OCR grezzi e log di recupero fonte.

Approvazione utente 18 maggio 2026: la risposta prodotta dopo questa correzione
è stata verificata dall'utente e confermata come risposta corretta. Da questo
momento il caso `QSP50194` / `R.G. 9926/2026` è il test reale definitivo da
preservare prima di lavorare sul generatore corpus.

## Matrice domande obbligatorie prima del corpus

Prima del generatore corpus ogni documento Cassazione della tranche deve essere
controllato anche contro le domande da avvocato stabilite sul caso pilota. Il
report qualità del backfill deve quindi esporre una `question_matrix` con almeno
questi controlli:

- sintesi vera della fonte richiesta;
- natura dell'atto: sentenza definitiva, ordinanza, questione pendente o altro;
- oggetto della questione o decisione;
- stato del procedimento o dell'atto;
- punto di diritto o principio in discussione;
- motivi, censure o passaggi rilevanti;
- norme richiamate e spiegazione del perché contano;
- effetto pratico per l'avvocato;
- esito finale o pendenza;
- PDF/allegato ufficiale e link cliccabile quando presente;
- discrepanza R.G. quando scheda e PDF riportano numeri diversi;
- articoli richiamati spiegati, non solo elencati, quando il testo li contiene.

Questa matrice viene generata in modo deterministico dal job
`python -m pct.legal_update_job --backfill-web-evidence`: non usa LLM, non
naviga oltre il connettore già previsto e serve a decidere se la fonte è pronta
per la tranche e, solo dopo, per il corpus RAG.

## Riuso PDF già presenti sul server

Il passaggio `pagina ufficiale -> allegato/PDF` non deve riscaricare un allegato
quando il file è già presente nello storage runtime. Prima della richiesta HTTP
il backfill controlla la cache allegati configurata:

- `IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR`;
- `IUSENTRA_LEGAL_DOWNLOAD_CACHE_DIR`;
- in produzione Hetzner, se `PCT_DATA_ROOT=/data`, anche
  `/data/intelligence/downloads`, `/data/fonti_ufficiali` e
  `/data/tenants`.

Se trova un PDF con lo stesso nome, lo usa direttamente per hash, testo e OCR.
Solo se il file non è presente passa al download dalla fonte ufficiale e salva
il file nella cache runtime per i passaggi successivi. Questo mantiene la prova
end-to-end ma evita download e OCR ripetuti quando il materiale è già sul server.

## Tranche Cassazione del 18 maggio 2026

Sequenza eseguita dopo il caso pilota:

1. Backfill Cassazione su 20 record: il flusso pagina -> allegato -> OCR/testo
   ha salvato 41 evidenze e 21 allegati, tutti pronti, ma il lotto ha mostrato
   che alcune pagine generiche del sito potevano entrare nella tranche.
2. Correzione selezione: per `cassazione_massimario` il backfill e il
   generatore corpus accettano solo schede documentali Cassazione:
   `civile_dettaglio`, `penale_dettaglio`, `qsp_dettaglio`, `qsc_dettaglio`,
   `quc_dettaglio`, `rlc_dettaglio`, `rlp_dettaglio` e `su_dettaglio`.
3. Backfill filtrato su 10 record: 10 controllati, 22 evidenze salvate, 12
   allegati, 10/10 pronti, 10 PDF trovati e letti, 0 OCR mancanti, 0 hash
   mancanti.
4. Generatore corpus dopo la tranche:

```powershell
python scripts\generate_lex_source_corpus.py `
  --intelligence-db data\intelligence\legal_updates.db `
  --output-dir tmp\lex-source-corpus-cassazione-tranche `
  --source-code cassazione_massimario `
  --limit 50 `
  --overwrite
```

Esito locale: 50 documenti Cassazione, 538 chunk RAG, filtro documentale attivo,
`expected_queries.jsonl` arricchito con `question_matrix`. Il comando non naviga
il web e non chiama LLM.

Verifiche mirate:

```powershell
python -m pytest tests\test_legal_update_web_verification_attachments.py `
  tests\test_lex_source_corpus_generator.py `
  tests\test_legal_update_publish_context.py::test_backfill_web_verification_evidence_rinfresca_allegato_ocr_vuoto `
  tests\test_legal_update_publish_context.py::test_backfill_web_verification_evidence_query_cerca_in_evidenze_e_allegati `
  tests\test_legal_update_publish_context.py::test_backfill_cassazione_esclude_pagine_non_documentali_dalla_tranche `
  tests\test_legal_update_batch_runner.py::test_legal_update_job_cli_backfill_evidenze_usa_limiti_governati -q
python -m pytest tests\test_utf8_integrity.py -q
git diff --check
```

Esito: 18 test mirati passati, 4 test UTF-8 passati, diff senza whitespace
errati.

Passaggi eseguiti per arrivare al test definitivo:

1. Domanda reale iniziale: `mi puoi sintetizzare questa sentenza Penale Pendente
   del ricorso R.G. 9926/2026`.
2. Primo problema rilevato: Lex non rispondeva in modo utile, mostrava log di
   recupero fonte o risposte generiche e talvolta finiva nel contesto editor o
   template invece che nelle fonti ufficiali.
3. Correzione del focus conversazionale: la richiesta `Questione Penale
   Pendente`, `QSP` o `R.G.` viene trattata come fonte ufficiale Cassazione, non
   come richiesta di bozza, editor o template.
4. Recupero fonte: il database `legal_updates.db` viene interrogato per la
   scheda Cassazione `QSP50194` e per l'allegato collegato.
5. Verifica allegato: il PDF
   `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf` viene mantenuto come
   PDF ufficialmente collegato alla scheda.
6. Lettura PDF/OCR: il testo OCR dell'allegato entra nel contesto interrogabile,
   ma non deve essere riversato grezzo nella risposta finale.
7. Discrepanza R.G.: è stata confermata la differenza tra scheda/domanda
   `R.G. 9926/2026` e numero interno del PDF `R.G. 9966/2026`; il collegamento
   non va rimesso in discussione, ma i dati della scheda e i dati del PDF vanno
   tenuti separati.
8. Prima risposta migliorata ma non definitiva: Lex trovava fonte, PDF, punto
   di diritto, motivi e articoli, però ripeteva troppe sezioni, esponeva ancora
   OCR sporco e mescolava troppo scheda e PDF.
9. Regola corretta richiesta dall'utente: Lex può citare entrambi, ma non può
   attribuire i dati del PDF alla scheda richiesta come se fossero certi.
10. Correzione finale del composer: per una domanda di sintesi Lex produce una
    sola sezione `Sintesi` con oggetto, stato, punto di diritto/principio,
    motivi/censure, effetto pratico e nota R.G.
11. Aggiunta spiegazione norme: Lex non deve solo elencare gli articoli, ma
    spiegare perché contano `599-bis c.p.p.`, `606 c.p.p.`, `129 c.p.p.`,
    `610 c.p.p.` quando presente e `81 c.p.`.
12. Guardia OCR: frammenti deformati come `Corte d'appello di N Caltanissetta`,
    `al medesimo | d`, `anni due e mesi o`, `edi` e simili non devono comparire
    nella risposta finale.
13. Guardia qualità finale: prima della restituzione vengono evitati duplicati,
    sezioni ripetute, estratti OCR grezzi, link PDF rotti e fusione impropria
    tra scheda e PDF.
14. Test mirati aggiunti/aggiornati: domande su sintesi, punto di diritto,
    motivi, natura dell'atto, udienza/norme, articoli, ricorrente/relatore,
    PDF, uso in atto, esito e discrepanza R.G.
15. Test end-to-end verificato: DB -> scheda ufficiale -> allegato PDF -> OCR ->
    retrieval/RAG operativo -> risposta Lex -> test di regressione.
16. Deploy senza backup eseguito su Hetzner con versione `2.245.26`.
17. Verifica utente finale: l'utente ha confermato che la risposta ora va bene e
    ha autorizzato l'approvazione del test come definitivo e reale.

Problema emerso nella prova reale:

- Lex trovava la scheda Cassazione e il PDF, ma rispondeva ancora come log di
  recupero fonti.
- La sintesi dell'allegato era povera e il punto di diritto poteva uscire
  tronco.
- La stessa risposta veniva restituita a domande diverse, invece di rispondere
  al quesito effettivo dell'avvocato.
- Il link PDF con underscore poteva essere spezzato dal rendering Markdown del
  widget già aperto.

Logica introdotta sul caso pilota:

1. Prima si recuperano pagina QSP, allegato ufficiale, OCR e discrepanza R.G.
2. Poi si costruisce una risposta focalizzata sulla domanda concreta.
3. La risposta conserva sempre fonte, PDF, avviso su `9926/2026` / `9966/2026`
   e separazione dai dati riservati dello studio.
4. Se la domanda chiede norme o articoli, Lex estrae gli articoli dalla scheda e
   dall'allegato e può attivare una ricerca web libera.
5. La ricerca web libera resta separata dalla fonte ufficiale della questione,
   non entra nel corpus e non applica allowlist o blocchi da fonte autorizzata.

Matrice minima di domande coperte per il caso pilota:

- `mi puoi sintetizzare questa sentenza Penale Pendente del ricorso R.G. 9926/2026`;
- `qual è il punto di diritto della questione penale R.G. 9926/2026?`;
- `quali sono i motivi del ricorso R.G. 9926/2026?`;
- `è una sentenza o una questione pendente R.G. 9926/2026?`;
- `quando è fissata l'udienza e quali norme sono indicate per R.G. 9926/2026?`;
- `trova gli articoli di riferimento della questione R.G. 9926/2026`;
- `chi sono ricorrente e relatore della questione penale R.G. 9926/2026?`;
- `mi dai il PDF e l'allegato ufficiale della questione R.G. 9926/2026?`;
- `posso citare la questione R.G. 9926/2026 in un atto come decisione definitiva?`;
- `qual è l'esito della questione R.G. 9926/2026?`;
- `spiegami la discrepanza tra R.G. 9926/2026 e R.G. 9966/2026`.

Articoli da presidiare nel caso pilota:

- dalla scheda Cassazione: `Cod. proc. pen. artt. 599-bis e 606`;
- dall'ordinanza/OCR: `art. 599-bis c.p.p.`, `art. 129 c.p.p.`,
  `art. 81, comma secondo c.p.`, quando presenti nel testo leggibile;
- dalla fase web libera: risultati pubblici scelti dalla ricerca libera della
  singola domanda, sempre marcati `web_libero` e mai promossi a fonte ufficiale
  o corpus.

Regola da riusare sugli altri documenti:

- fatto bene un documento significa avere domanda, fonte, allegato, testo,
  sintesi, norme, eventuale web libero, limiti e test ripetibili;
- solo dopo questa chiusura si estende la stessa logica al generatore corpus e
  agli altri documenti.
