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
3. Lex continua a interrogare prima gli archivi interni utili, poi esegue la
   ricerca web libera manuale se serve integrare risultati.
4. I risultati web liberi restano distinti dalle fonti ufficiali già acquisite:
   quando una pagina o un allegato è utile, va acquisito nell'archivio dello
   studio per diventare fonte stabile interrogabile.
5. La console pianificazioni non deve creare, avviare o mostrare job per questa
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
