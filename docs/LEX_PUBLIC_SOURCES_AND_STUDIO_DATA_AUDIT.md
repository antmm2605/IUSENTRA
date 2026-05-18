# LEX — Audit: Fonti Pubbliche e Dati Studio (v2.201.0)

Documento di audit tecnico sul comportamento attuale di Lex nella gestione delle fonti pubbliche (sentenze, normativa, giurisprudenza) e dei dati interni dello studio (clienti, fascicoli, anagrafica).

## Aggiornamento operativo 2.245.38 - 2026-05-18

Corretto il caso `02_Assoradio.pdf` segnalato in Ricerca Legale:

- il blocco `Contesto in IUSENTRA` non ripete più lo stesso testo come
  `Contesto operativo` e `Contenuto` quando riepilogo ed estratto coincidono;
- i contributi AGCOM di consultazione pubblica, pianificazione frequenze DAB+
  o posizioni tecniche di terzi vengono marcati fuori perimetro quando non
  contengono un provvedimento, una delibera, una sanzione, una controversia,
  un elemento Corecom/tutela utenti o altro valore operativo per lo studio;
- il filtro agisce sia sull'import deterministico degli aggiornamenti legali
  sia sui risultati già esposti da `legal_updates.db`, così Lex e Ricerca
  Legale non trasformano una prova web generica in materiale utile allo studio;
- la scheda mostra solo anteprima e contesto pulito, mentre il testo PDF esteso
  resta nel riquadro `Testo letto in IUSENTRA` e nei chunk/RAG quando il
  documento è pertinente e il testo è stato letto correttamente.

---

## Aggiornamento operativo 2.245.34 - 2026-05-18

Aggiunta la Fase 5 Auto-fetch governato. La pipeline non parte più come
scansione massiva indistinta: prima costruisce un piano deterministico, poi
accoda job deduplicati, poi esegue solo le fonti dovute entro il budget.

Passaggi tracciati:

- aggiunto `pct/legal_update_autofetch.py`;
- ogni tick legge fonti abilitate, cursori persistenti e intervallo di polling;
- il budget `LEGAL_AUTOFETCH_SOURCE_BUDGET` limita quante fonti possono essere
  processate nel giro;
- ogni fonte selezionata viene accodata in `LegalUpdateJobQueue` con schema
  `iusentra.legal_update_autofetch.v1`, URL, nome fonte, timeout, tentativi e
  checklist qualità;
- i cursori registrano ultimo job, ultimo stato, errore leggibile e fallimenti
  consecutivi;
- `web/services/legal_update_surface.py` usa il tick governato per l'azione
  `scan`;
- `pct/scheduler.py` usa il tick governato per gli aggiornamenti legali
  pianificati;
- il monitor operativo espone coda, fonti pronte/non pronte, job recenti,
  fonti bloccate e domande qualità obbligatorie.

Domande qualità obbligatorie per ogni fonte/documento:

- fonte censita nel database;
- pagina ufficiale o pubblica raggiungibile;
- allegati, PDF o documenti collegati;
- allegati scaricati e hashati;
- testo estratto o passato da OCR;
- OCR pulito oppure marcato come sporco;
- norme, R.G., date e riferimenti utili estratti;
- discrepanze tra scheda, PDF, R.G., date o titolo;
- prontezza per Memory Tree e RAG;
- risposta Lex con sintesi vera, link cliccabile e limiti chiari.

Verifiche eseguite:

- `python -m py_compile pct\legal_update_autofetch.py pct\scheduler.py web\services\legal_update_surface.py`;
- `python -m pytest tests\test_legal_update_autofetch.py tests\test_legal_update_job_queue.py tests\test_legal_update_batch_runner.py tests\test_legal_update_surface_jobs.py -q --tb=short`.

## Aggiornamento operativo 2.245.33 - 2026-05-18

Aggiunta la Fase 4 Tool Registry e Model Routing per Lex, necessaria prima di
estendere il lavoro a Cassazione, Ricerca Legale, Archivio Giurisprudenza e area
AI.

Passaggi tracciati:

- `lex/tools/registry.py` mantiene il dizionario storico `registry.tools`, ma
  aggiunge descrittori governati per ogni strumento;
- ogni tool dichiara schema, categoria, trasporto, permessi, lettura/scrittura,
  mutazione stato e compatibilità con web libero;
- la modalità web libero non impone allowlist ufficiali sulle ricerche
  dell'avvocato, ma non espone strumenti riservati dello studio come se fossero
  fonti pubbliche;
- gli strumenti di scrittura dell'editor professionale sono marcati come
  mutanti e richiedono un canale applicativo autorizzato;
- `lex/providers/registry.py` espone una policy di routing con profilo,
  provider effettivo, uso LLM, costo relativo, target latenza e controllo
  qualità;
- i provider esterni restano disattivati salvo `LEX_EXTERNAL_ALLOWED=1`, senza
  fallback implicito su dati sensibili.

Verifiche eseguite:

- `python -m py_compile lex\tools\registry.py lex\providers\registry.py`;
- `python -m pytest tests\test_lex_tool_registry_governance.py tests\test_lex_model_routing_governance.py lex\tests\unit\test_registry.py tests\test_lex_editor_ai_tools.py tests\test_lex_operational_knowledge.py::test_tool_registry_exposes_operational_knowledge_tool_default_on tests\test_lex_operational_knowledge.py::test_tool_registry_can_disable_operational_knowledge -q --tb=short`.

## Aggiornamento operativo 2.245.32 - 2026-05-18

Aggiunta la Fase 3 job queue per fonti legali, necessaria prima di estendere
Cassazione e le altre fonti oltre il caso pilota.

Passaggi tracciati:

- aggiunto `pct/legal_update_job_queue.py` con coda SQLite persistente per
  fonte, pagina, PDF/allegato o documento;
- ogni job registra chiave dedupe, hash contenuto, fonte, URL, tipo elemento,
  payload stabile, tentativi, timeout, stato, errore leggibile e orari;
- `claim_next`, `complete`, `fail` e `recover_stale_running` permettono retry,
  timeout finale e ripresa dei job rimasti in corso dopo crash del worker;
- il batch runner espone `build_legal_update_source_job_queue`, così una
  tranche di fonti può essere accodata e verificata prima di avviare i
  subprocess;
- la deduplica conserva un solo job per lo stesso documento/hash, ma crea un
  nuovo job quando cambia l'hash del contenuto.

Verifiche eseguite:

- `python -m py_compile pct\legal_update_job_queue.py pct\legal_update_batch_runner.py`;
- `python -m pytest tests\test_legal_update_job_queue.py tests\test_legal_update_batch_runner.py -q --tb=short`.

## Aggiornamento operativo 2.245.31 - 2026-05-18

Aggiunta la Fase 2 TokenJuice, reimplementata in Python per Lex senza copiare
codice esterno e senza chiamate LLM.

Passaggi tracciati:

- aggiunto `lex/tokenjuice.py` come compattatore deterministico per HTML, JSON,
  log, OCR/PDF già estratti e testi legali lunghi;
- la compattazione preserva ancoraggi legali: articoli, R.G., date, atti,
  fonte, motivi e passaggi con valore giuridico;
- `lex/memory_tree.py` registra per ogni chunk i metadati TokenJuice:
  schema, regola applicata, caratteri originali/compattati, rapporto di
  riduzione, ancoraggi e avvisi OCR;
- il testo originale resta nel corpus, mentre il contesto compattato è
  disponibile per il RAG quando riduce davvero il payload;
- il generatore corpus dichiara nel manifest la policy TokenJuice, così il
  consumo crediti resta riservato alla risposta o ai test qualità e non ai
  passaggi tecnici ripetibili.

Verifiche eseguite:

- `python -m py_compile lex\tokenjuice.py lex\memory_tree.py scripts\generate_lex_source_corpus.py`;
- `python -m pytest tests\test_lex_tokenjuice.py tests\test_lex_memory_tree.py tests\test_lex_source_corpus_generator.py -q --tb=short`.

## Aggiornamento operativo 2.245.30 - 2026-05-18

Avviata l'assimilazione funzionale dei pattern OpenHuman senza copiarne codice
GPL: la prima fase è il Memory Tree Lex deterministico.

Passaggi tracciati:

- aggiunto `lex/memory_tree.py` come memoria strutturata per documenti già
  acquisiti: fonte, PDF/OCR, sentenza, questione pendente o documento fascicolo;
- ogni chunk ha ID stabile, hash contenuto, provenienza, qualità, norme,
  riferimenti R.G., date, argomenti e metadati RAG;
- il generatore `scripts/generate_lex_source_corpus.py` scrive anche
  `memory_tree/index.json`, `memory_tree/documents.jsonl` e
  `memory_tree/chunks.jsonl`;
- la ricerca memoria è deterministica per fonte, norma, R.G. e argomento,
  senza consumo LLM;
- OCR sporco e riferimenti R.G. multipli restano visibili nello stato qualità,
  così Lex non deve fonderli come fatti certi nella risposta finale.

Verifiche eseguite:

- `python -m py_compile lex\memory_tree.py scripts\generate_lex_source_corpus.py`;
- `python -m pytest tests\test_lex_memory_tree.py tests\test_lex_source_corpus_generator.py -q --tb=short`.

## Aggiornamento operativo 2.245.29 - 2026-05-18

Ricerca Legale e catalogo fonti sono stati riallineati alla logica decisa sul
caso Cassazione: prima dati reali visibili e interrogabili, poi generatore
corpus solo sui documenti pronti.

Passaggi tracciati:

- la pagina `/ricerca-legale` non mostra più un cruscotto descrittivo separato:
  i conteggi reali diventano accessi operativi verso fonti, news, acquisizioni,
  Normattiva, Gazzetta, Registro mediazione e Archivio Giurisprudenza;
- la lista `Fonti monitorate` è resa dentro la pagina con stato e famiglia
  della fonte, e ogni fonte avvia una ricerca invece di restare un link
  generico;
- `https://www.cortedicassazione.it/it/ultime_sent_ord_e_questioni.page` è
  stata aggiunta al catalogo degli aggiornamenti legali come fonte ufficiale
  Cassazione dedicata (`cassazione_ultime_sent_ord_questioni`);
- la fonte Cassazione deve essere navigata con la stessa sequenza già stabilita:
  DB -> pagina ufficiale -> allegati/PDF -> download/cache -> hash -> OCR/testo
  -> metadati qualita' -> documenti pronti -> corpus RAG;
- il commit/push deve seguire la checklist `docs/COMMIT_PUSH_REQUIRED_GATES.md`,
  che rende espliciti i gate shardati e impedisce di usare aggregatori o suite
  monolitiche come diagnosi primaria.

Verifiche locali già eseguite in questa tranche:

- `python -m pytest tests\test_legal_updates_pipeline.py::test_fonti_default_includono_pagina_cassazione_ultime_sent_ord_e_questioni tests\test_react_legal_intelligence_search.py -q`;
- `pnpm --filter @iusentra/studio typecheck`.

## Aggiornamento operativo 2.245.24 - 2026-05-18

Il caso Cassazione `QSP50194` / `R.G. 9926/2026` è diventato il caso pilota
obbligatorio per il comportamento Lex sulle fonti pubbliche: non basta più
dimostrare che pagina, PDF e OCR siano stati trovati. Lex deve rispondere alla
domanda effettiva dell'avvocato con una risposta strutturata e controllabile.

Passaggi tracciati:

- corretta la risposta troppo superficiale che riportava solo fonte, PDF,
  discrepanza R.G. ed estratto OCR iniziale;
- aggiunta una risposta focalizzata sulla domanda concreta prima della scheda
  fonte;
- aggiunta sintesi dell'ordinanza con natura dell'atto, vicenda processuale,
  pena concordata, motivi/censure, punto di diritto, articoli richiamati e stato
  pendente;
- corretto il link PDF con etichetta stabile `Apri PDF ufficiale` e underscore
  percent-encoded per evitare rotture nel rendering Markdown del widget già
  aperto;
- aggiunta matrice di domande da avvocato: sintesi, punto di diritto, motivi,
  natura sentenza/questione pendente, udienza/norme, articoli, ricorrente e
  relatore, PDF/allegato, uso in atto, esito e discrepanza R.G.;
- aggiunta fase di integrazione web libera per gli articoli, distinta dalla
  fonte ufficiale Cassazione.
- corretto il comportamento `Web libero` della chat: con il flag attivo Lex non
  usa allowlist ufficiali, non blocca per `fonte autorizzata`, non trascina
  fonti DB/fascicolo nel risultato libero, non salva nel corpus e non mostra
  warning visibili; i risultati restano tecnicamente `web_libero` e
  `verified_reference=false`, con controllo rimesso all'avvocato.

Verifiche eseguite:

- `python -m py_compile lex\retrieval\sources\official_web.py lex\retrieval\source_router.py lex\http_bounded_bridge.py lex\orchestrator_http.py lex\operational_knowledge\tools.py lex\operational_knowledge\response_composer.py lex\operational_knowledge\source_registry.py pct\legal_update_repository.py`;
- `python -m pytest lex\tests\test_official_web.py lex\tests\test_http_bounded_bridge_governed_only.py lex\tests\test_orchestrator.py tests\test_lex_operational_knowledge.py::test_rg_questione_penale_risponde_a_domande_da_avvocato tests\test_lex_operational_knowledge.py::test_rg_questione_penale_articoli_attiva_web_libero_distinto_dalla_fonte_ufficiale -q`;
- `python -m pytest tests\test_assistente_focus.py tests\test_lex_operational_knowledge.py tests\test_lex_assistente_context_real_requests.py tests\test_lex_widget_contract.py tests\test_lex_fascicolo_first_retrieval.py lex\tests\unit\test_retrieval_orchestrator.py -q`;
- `node tests\js\lex_assistant_render.test.mjs`;
- `git diff --check`.

Regola di estensione: prima di applicare la logica al generatore corpus o a
10.000 documenti, un documento deve passare end-to-end con test ripetibili e
risposta professionale. Solo dopo si estende la stessa griglia agli altri
documenti.

## Aggiornamento operativo 2.245.26 - 2026-05-18

Rafforzata la regola del caso pilota `QSP50194`: pagina e PDF sono già stati
verificati come collegati, quindi Lex non deve rimettere in discussione il
collegamento a ogni risposta. Deve però separare l'attribuzione:

- dati della scheda `R.G. 9926/2026`: quesito, udienza, relatore, ricorrente,
  riferimenti normativi e stato pendente;
- dati del PDF ufficialmente collegato, che nel testo letto riporta
  `R.G. 9966/2026`: motivi/censure, punto di diritto e articoli ricavati dal
  PDF devono essere presentati come contenuto del PDF collegato;
- nota R.G.: resta visibile e non deve diventare un dubbio generico su fonti già
  verificate;
- OCR: estratti sporchi, frammenti con barre, lettere isolate o testo
  chiaramente deformato non devono essere riprodotti nella risposta finale.
- forma della risposta: deve essere una sintesi unica, non una lista ripetuta di
  sezioni; oggetto, stato, principio, motivi, norme spiegate, effetto pratico,
  PDF e nota R.G. devono comparire una sola volta.

Questa regola è il blocco da tenere davanti prima del generatore corpus: prima
separazione corretta di scheda, allegato e OCR su un documento, poi propagazione
agli altri documenti.

Aggiornamento operativo 2.245.36 - 2026-05-18:

- la pagina Cassazione `ultime_sent_ord_e_questioni.page` non viene più trattata
  come lista documentale diretta: il connettore segue le pagine ufficiali
  `giurisprudenza_penale.page` e `giurisprudenza_civile.page` e conserva solo
  schede `*_dettaglio.page?contentId=...`;
- pagine di servizio, navigazione, privacy, supporto, preferenze e link generici
  del sito Cassazione sono escluse prima del DB operativo e di nuovo prima del
  generatore corpus;
- il generatore corpus applica il filtro anche a
  `cassazione_ultime_sent_ord_questioni`, non solo a `cassazione_massimario`,
  così eventuali evidenze sporche già acquisite non entrano nel RAG;
- le domande del corpus vengono create dal contesto reale letto: titolo della
  scheda, testo PDF/OCR, riferimenti normativi, R.G., presenza di allegato e
  qualità del testo; gli articoli estratti sono salvati come riferimenti
  espliciti e la risposta Lex può integrarli con `web_libero` senza promuovere
  quella ricerca a fonte DB;
- verifica locale sulla fonte Cassazione: 10 schede documentali pronte, 9 con
  PDF letto, una senza PDF ma con testo pagina, 10/10 con matrice domande;
  corpus di prova da 20 documenti e 174 chunk, Memory Tree pronto, zero pagine
  di servizio;
- test mirati confermati: filtro pagina Cassazione, generatore corpus, articoli
  con `web_libero`, Ricerca Legale e Archivio Giurisprudenza.
- corretto anche il caso chat `Web libero`: il flag manuale svuota realmente
  contesto studio, fascicolo, template atti, impostazioni e fonti interne prima
  del workflow bounded. La risposta non deve più mostrare `Fonti interne
  verificate` quando la ricerca è libera e deve restare in italiano anche se il
  provider produce frasi inglesi.

Aggiornamento operativo 2.245.28 - 2026-05-18:

- il backfill delle evidenze Cassazione ora restituisce un report qualità per
  documento prima del generatore corpus;
- il report distingue pagina verificata, PDF/allegato trovato, hash presente,
  testo letto, OCR pulito/sporco, norme estratte, riferimenti R.G.,
  discrepanze, link PDF cliccabile e stato `pronto`, `pronto_con_note`,
  `da_ocr` o `testo_mancante`;
- la matrice delle domande da avvocato è diventata un campo obbligatorio
  `question_matrix`: sintesi, natura dell'atto, oggetto, stato, punto di
  diritto, motivi/censure, norme spiegate, effetto pratico, esito, PDF/allegato
  e discrepanza R.G. quando presente;
- il download PDF ora prova prima il riuso della cache runtime del server
  (`/data/intelligence/downloads`, `/data/fonti_ufficiali` e `/data/tenants`
  quando `PCT_DATA_ROOT=/data`, oppure le directory configurate con
  `IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR` /
  `IUSENTRA_LEGAL_DOWNLOAD_CACHE_DIR`), così un PDF già presente non viene
  scaricato di nuovo;
- la tranche reale ha prima evidenziato rumore da pagine generiche del sito
  Cassazione; il filtro è stato quindi ristretto alle schede documentali
  (`civile_dettaglio`, `penale_dettaglio`, `qsp_dettaglio`, `qsc_dettaglio`,
  `quc_dettaglio`, `rlc_dettaglio`, `rlp_dettaglio`, `su_dettaglio`);
- la verifica filtrata locale ha controllato 10 documenti Cassazione: 10/10
  pronti, 10 PDF letti, 12 allegati salvati, nessun OCR mancante, nessun hash
  mancante;
- solo dopo questa verifica è stato generato un corpus locale Cassazione da 50
  documenti e 538 chunk RAG, con `question_matrix` nelle query attese;
- le fonti pronte non devono restare solo nel job o nel corpus: devono essere
  usabili in Lex Chat AI, visibili in `/ricerca-legale` e consultabili in
  Archivio Giurisprudenza quando sono fonti giurisprudenziali o Cassazione;
- test mirati passati: 18 test su allegati/OCR/cache, backfill, filtro
  Cassazione e generatore corpus; 4 test UTF-8; `git diff --check`;
- questo controllo è deterministico e non consuma crediti LLM. Lex/LLM resta
  riservato alla risposta finale o a test qualità espliciti, non al download,
  hash, OCR o chunking.

Approvazione reale del 18 maggio 2026:

- domanda validata: `mi puoi sintetizzare questa sentenza Penale Pendente del
  ricorso R.G. 9926/2026`;
- risultato accettato dall'utente: risposta sintetica con oggetto, stato,
  principio, motivi, norme spiegate, effetto pratico, PDF e nota R.G.;
- percorso validato: DB -> pagina ufficiale -> allegato -> OCR/PDF -> retrieval
  operativo -> risposta Lex -> test di verifica;
- regola definitiva: questo caso è il baseline da propagare al generatore corpus
  e agli altri documenti, senza tornare a risposte con log fonte, sezioni
  duplicate o OCR grezzo.

## Aggiornamento operativo 2.245.21 - 2026-05-18

Il caso Cassazione `QSP50194` è stato verificato sul database locale: prima
l'allegato ufficiale era presente come URL/hash, ma il contenuto era fermo a
`context_chars=0`. Dopo l'aggancio OCR locale il PDF
`Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf` è stato letto con
`pdfplumber+ocr`, salvando `45813` caratteri interrogabili nel record
`review_id=390`.

Lex ora risponde alla domanda `Quale allegato ufficiale ha la questione penale
R.G. 9926/2026?` con l'allegato `Ordinanza di rimessione`, il PDF ufficiale,
un estratto OCR e l'avviso sulla differenza tra `9926/2026` nella domanda e
`9966/2026` nell'allegato. La risposta non espone più errori tecnici interni se
una sorgente secondaria non è disponibile nel contesto corrente.

È stato aggiunto anche il comando manuale `Web libero` nel widget Lex: non è un
job, non è una pianificazione e non passa dalla console scheduler. Il comando
vale solo per la singola richiesta Lex e abilita una ricerca pubblica libera,
separata dalle fonti ufficiali già acquisite.

## Aggiornamento operativo 2.245.20 - 2026-05-18

Dopo il salvataggio OCR di Cassazione `QSP50194`, le prove di domanda hanno
mostrato un problema di ordine: quando la domanda chiedeva "quale allegato",
la pagina QSP poteva precedere il PDF ufficiale anche se il PDF era presente
e leggibile. Il ranking Lex ora riconosce le domande su allegato, PDF,
ordinanza, rimessione, nota o documento e promuove le evidenze con
`attachment_url` e testo OCR reale.

## Aggiornamento operativo 2.245.19 - 2026-05-18

Il test reale su Cassazione `QSP50194` ha evidenziato un secondo blocco:
l'OCR in produzione leggeva il PDF, ma il backfill non selezionava più il record
perché il database conteneva già evidenze web vecchie con allegato a
`context_chars=0`.

Da questa versione il backfill mirato con `--backfill-review-id` o
`--backfill-query` può rientrare sui record già tracciati, cerca anche in
`attachments_json` e nelle evidenze salvate, e aggiorna l'allegato normalizzato
quando il nuovo testo OCR è più ricco della prova precedente. Le vecchie prove
con `testo non estraibile` vengono sostituite dalla prova interrogabile, così
Lex può recuperare non solo pagina, URL e hash, ma anche il contenuto OCR
dell'ordinanza.

## Aggiornamento operativo 2.245.18 - 2026-05-18

La prova su Cassazione `QSP50194` ha confermato che la pagina ufficiale e
l'allegato pubblico vengono trovati: il database locale contiene il record e il
backfill mirato salva pagina, URL allegato e hash. Il problema reale era il
testo del PDF: l'allegato `Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf`
è una scansione e il percorso usato dagli aggiornamenti legali si fermava a
`context_chars=0`.

Da questa versione l'estrattore documentale usato dalla verifica web applica
OCR tramite `pypdfium2` e Tesseract quando un PDF ufficiale non contiene testo
selezionabile. In produzione il container include Tesseract italiano: il
backfill può quindi salvare anche il testo OCR dell'ordinanza, non solo la
prova di download. Se Tesseract non è disponibile nel runtime locale, il
warning resta esplicito e l'allegato continua comunque a essere conservato con
URL e hash.

## Aggiornamento operativo 2.245.15 - 2026-05-17

Il recupero delle evidenze web non dipende più solo dall'ordine del lotto
temporizzato. La CLI `python -m pct.legal_update_job --backfill-web-evidence`
accetta ora `--backfill-query` e `--backfill-review-id`: un riferimento preciso
già presente nel database, ad esempio `Circolare numero 53 del 07-05-2026`,
può essere completato subito leggendo la fonte ufficiale e i suoi allegati.

La selezione mirata cerca titolo, testo normalizzato, URL della fonte e sintesi
della revisione, includendo anche numeri brevi come `53`, `07` e `05`. Questo
serve a impedire che un record approvato resti fermo solo perché il backfill a
tempo non lo ha ancora raggiunto.

## Aggiornamento operativo 2.245.14 - 2026-05-17

La ricerca Lex sulle evidenze web non ordina più soltanto per freschezza o
numero di termini comuni. Il ranking assegna peso maggiore a titolo, URL,
allegato, numeri identificativi e frase esatta, così una ricerca puntuale come
`Messaggio numero 685 del 26-02-2026` deve riportare prima l'evidenza
verificata corrispondente e non un risultato INPS più recente ma generico.

Il bacino SQL dei candidati viene ampliato prima del ranking: questo evita che
un'evidenza esatta ma meno recente venga scartata troppo presto quando molte
fonti condividono parole comuni come `circolare`, `messaggio`, `numero` o
`2026`.

## Aggiornamento operativo 2.245.13 - 2026-05-17

Il recupero evidenze web è stato ristretto al perimetro che serve davvero allo
studio: per default vengono trattati solo record `pending`, `approved` e
`published`, mentre metadati chiusi e dataset open-data massivi restano esclusi
finché non vengono richiesti esplicitamente.

La modalità predefinita del backfill è ora "fonte diretta": legge la pagina
ufficiale già collegata al documento e gli allegati pubblici collegati, salva
URL, testo, PDF/hash quando disponibili e registra `insufficient` con motivo
esplicito quando la prova non basta. La ricerca web estesa resta disponibile,
ma deve essere richiesta come secondo passaggio perché è più lenta e va
governata per fonte.

La CLI accetta `--backfill-max-seconds`, `--backfill-status`,
`--backfill-include-closed`, `--backfill-include-open-data` e
`--backfill-full-search`. Questo impedisce job appesi e rende misurabile ogni
tranche: quanti record sono stati selezionati, controllati, salvati, con
allegati, fermati dal limite di tempo o lasciati con diagnosi interrogabile.

## Aggiornamento operativo 2.245.12 - 2026-05-17

Le evidenze web non dipendono piu' dalla sola coda di pubblicazione: ogni
documento nuovo o modificato da fonte governata registra subito una verifica
fonte con URL, testo letto, eventuali allegati ufficiali, hash e stato della
prova in `web_verification_evidence`.

La verifica parte dalla pagina originaria gia' acquisita, legge il contesto
ufficiale e gli allegati collegati, poi usa archivi ufficiali e ricerca web
governata come confronto. In questo modo la metrica delle evidenze misura
prove archiviate, non solo schede pubblicate.

E' disponibile il backfill operativo
`python -m pct.legal_update_job --backfill-web-evidence` per recuperare record
gia' normalizzati ma privi di prova web salvata.

## Aggiornamento operativo 2.245.11 - 2026-05-17

Sono state aggiunte e classificate le fonti richieste nella verifica manuale:
Corte dei Conti, Giustizia Amministrativa `Decisioni e pareri`, Studio Cataldi,
Avvocato Andreani e IusSearch.

La Corte dei Conti entra nel ciclo delle fonti ufficiali come fonte primaria:
portale istituzionale, pagina sentenze, pagina delibere e banca dati pubblica
sono registrati per ricerche su responsabilità erariale, giudizi contabili,
controllo/referto e appalti con profili contabili.

La pagina `https://www.giustizia-amministrativa.it/dcsnprr` è censita come
fonte ufficiale verificabile, ma non viene usata come canale automatico
principale finché rimangono instabili certificato, paginazione e recupero
allegati. Il presidio automatico resta OpenGA ufficiale, che è più adatto al
lavoro schedulato.

Studio Cataldi e Avvocato Andreani sono registrati solo come fonti secondarie
di consultazione rapida per codice civile, procedura civile, codice penale e
codice della strada. Non sono fonti ufficiali: Lex può usarle per orientare la
ricerca o confrontare il testo, ma non può pubblicare una scheda normativa
senza riscontro su Normattiva, Gazzetta Ufficiale o altra fonte primaria.

IusSearch è stato censito come motore di ricerca giuridica P2. Il sito risponde
da `http://www.iussearch.it/` con pagina in `ISO-8859-1` e form Google custom
su `/search`: può aiutare a trovare piste, non a chiudere una prova. Ogni URL
trovata tramite quel motore deve essere poi confermata e scaricata dalla fonte
originaria.

La ricerca web governata accetta ora anche URL dirette appartenenti a fonti
censite e le classifica con priorità e natura della fonte. Questo consente di
testare una fonte passando l'indirizzo esatto, senza fingere che un sito privato
o un motore di ricerca sia un archivio ufficiale.

## Aggiornamento operativo 2.245.10 - 2026-05-17

Il completamento web degli aggiornamenti legali non si ferma più al primo
riferimento non confermato: la coda valuta più candidati, registra ogni
tentativo, abbassa la priorità degli elementi senza conferme e continua con i
riferimenti successivi. Se il web non produce conferme sufficienti, IUSENTRA
salva comunque una diagnosi interrogabile nel database con query tentate,
fonti provate e motivo della mancata pubblicazione.

È stata introdotta la tabella `web_verification_evidence`, usata da Lex e
dalla ricerca legale insieme agli archivi `normative`, `jurisprudence`,
`prassi` e `news`. Le evidenze conservano fonte, query, URL ufficiale,
allegato, hash SHA-256, estratto, testo disponibile e stato della verifica.
Gli allegati verificati vengono collegati anche al documento normalizzato,
così una query successiva può recuperare l'evidenza e non solo il riferimento.

INPS viene letto attraverso il JSON ufficiale caricato dalla pagina pubblica
`dettaglio.content-fragment-detail...json`: il caso reale `Circolare numero
53 del 07-05-2026` salva testo, PDF principale e allegati; il caso `Messaggio
numero 685 del 26-02-2026` salva testo e PDF. La ricerca usa anche la query
minima del titolo e un piano esteso, non solo la fonte già agganciata al
record.

Cassazione QSP viene letta dalla pagina ufficiale e dagli allegati esposti:
per `qsp_dettaglio.page?contentId=QSP50202` viene scaricato il PDF
`14740_04_2026_pen_noindex.pdf`. Se il PDF non contiene testo estraibile, il
database registra comunque allegato, hash e nota di testo non estraibile, senza
dichiarare completamento testuale fittizio.

Gazzetta Ufficiale viene letta con un resolver diretto sull'archivio annuale
ufficiale quando la query contiene un codice redazionale o un riferimento
normativo puntuale. Il caso reale `26G00056` / `D.Lgs. 13 marzo 2026, n. 39`
viene risolto da `showArchivioNews?anno=2026` alla scheda ELI
`https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg`, con contesto
ufficiale e PDF del fascicolo GU. La pagina di aiuto `Formato Grafico PDF` non
viene più trattata come allegato.

Gli atti amministrativi di sola gestione contabile, ad esempio liquidazioni
fattura o mandati di pagamento privi di segnali come ricorso, appalto, gara,
contenzioso o accesso agli atti, vengono chiusi fuori perimetro e non diventano
news legali solo perché provengono da un sito pubblico.

## Aggiornamento operativo 2.245.9 - 2026-05-17

Il contesto ufficiale usato dal dataset Lex accetta ora solo URL appartenenti
al catalogo dei domini istituzionali riconosciuti o a domini di classe A nella
source policy. Domini simili, credenziali nell'URL e redirect verso domini non
riconosciuti vengono scartati prima di costruire contesto citabile.

La lettura degli allegati ufficiali conserva il vincolo sui domini ammessi e
non usa più etichette cumulative o CTA generiche come titolo dell'evidenza:
quando il link mostra solo formule tipo `Leggi la notizia` o `Scarica PDF`, il
dataset usa il nome file dell'allegato ufficiale scaricato e hashato.

## Aggiornamento operativo 2.245.8 - 2026-05-17

Lex non tratta più una richiesta redazionale con cliente, ad esempio
`scrivi diffida per il cliente Marco Moscato`, come semplice ricerca
anagrafica. Il profilo `bozza_lettera` forza il workflow redazionale,
poi il contesto studio autorizzato viene usato per compilare intestazione,
avvocato e cliente quando disponibili.

Le richieste operative su dati studio sono state verificate con test reali su
`/api/assistente/context` e `/api/assistente/chat`: dati cliente, recapiti,
PEC, telefono e ultime udienze vengono letti dagli archivi tenant-aware invece
di rispondere con base documentale insufficiente.

Le bozze Lex vengono restituite senza appendici `Fonti consultate` non
pertinenti quando il workflow è una lettera/diffida. Il widget rende la
risposta come documento leggibile: titoli, grassetto, corsivo, separatori,
elenchi e blocco documento. Se una bozza arriva già schiacciata in una riga,
la UI la normalizza prima del rendering.

È stato aggiunto il presidio UTF-8 `utf8-integrity`: CLI, servizio e job
notturno rilevano mojibake, caratteri sostitutivi e testi con accenti italiani
rotti. Le guardie Lex riparano l'output prima di mostrarlo all'utente.

## Aggiornamento operativo 2.245.5 - 2026-05-17

Il presidio creato per fonti, agenti notturni, archivi ufficiali e funzioni AI
avanzate e' ora esposto anche nelle pagine usate dallo studio:
`/ricerca-legale` e `/giurisprudenza/`. Non rimane confinato alle console
amministrative.

`/ricerca-legale` mostra una sezione `Presidio Lex AI` con agenti controllati,
ricerca completa su fonti ufficiali e allegati pubblici quando disponibili,
archivi Normattiva/Gazzetta locali e stato delle funzioni MTP, LLM Wiki,
GLM-OCR e Gemini Embedding 2 come presidi misurabili o da autorizzare.

`/giurisprudenza/` mostra `Citazioni verificate` e `Presidio Lex
giurisprudenza`: conteggio delle schede citabili, stato Cassazione, agenti
collegati, archivi ufficiali e allegati fonte letti se presenti. Le modalita'
di accesso sono rese in linguaggio operativo per l'avvocato, non con codici
interni.

## Aggiornamento operativo 2.243.5 - 2026-05-16

Aggiornamento 2.245.3: IUSENTRA ha ora micro-agenti Lex interni collegati
alla console pianificazioni e al job notturno `lex_operational_agents_nightly`.
Gli agenti non sono sub-processi liberi o comandi shell: derivano dai template
autorizzati, leggono solo archivi tenant-aware e salvano un inventario in
`lex_operational_agents.json`. La copertura include anagrafiche, fascicoli,
agenda/scadenze, preventivi/parcelle, PEC, posta ordinaria, documenti,
editor Lex, Cassazione, PCT, SDI/pagamenti, portale cliente, GDPR/AML, AI
locale/RAG e integrazioni. Se manca un archivio, un indice o una fonte
verificabile, l'esito resta `Da verificare` con chiavi mancanti e controllo
supervisore, invece di essere mostrato come completato.

Lo stesso aggiornamento estende il presidio pubblico: i codici fondamentali
su Normattiva (civile, procedura civile, penale, procedura penale, processo
amministrativo e strada) sono censiti come fonti di classe A, insieme al
presidio Cassazione per citazioni verificabili. Lex non deve pubblicare
massime, sezione, numero o data se non trova riscontro nel corpus ufficiale o
in una fonte ufficiale governata.

Aggiornamento 2.245.2: per Giustizia Amministrativa il canale HTML
istituzionale diretto e' stato messo in osservazione, perche' puo' fallire in
modo instabile durante crawler/SSL. Il presidio automatico principale passa a
OpenGA ufficiale (`openga_giustizia_amministrativa` e cartelle `openga_*`),
che espone dataset CKAN per sentenze, ordinanze, decreti, pareri,
provvedimenti, ricorsi e calendario udienze. Gli agenti fonte non marcano piu'
come completata una scansione che contiene errori interni: l'esito diventa
`failed`/da verificare e registra anche la soluzione alternativa applicata.
La stessa normalizzazione vale per gli esiti gia' salvati: un vecchio record
`completed` con errore dentro `payload_json.reports[].error` viene riletto come
`Da verificare`, cosi' la console non conserva stati falsamente positivi.
La pagina React `Archivio Giurisprudenza` traduce gli stati tecnici in esiti
operativi: `Da verificare`, `Aggiornata` o `Recupero assistito`; per la fonte
diretta amministrativa espone la nota di risoluzione verso OpenGA invece di
lasciare un errore non governato.
Lo stesso criterio e' applicato alle altre fonti giurisprudenziali: Cassazione
ha come canale automatico la pagina ufficiale delle ultime sentenze e ordinanze,
Corte costituzionale tenta direttamente lo ZIP open data se la pagina indice
fallisce, CURIA usa il feed RSS ufficiale e HUDOC espone il fallback RSS per
ricerche salvate.

Aggiornamento 2.245.0: le fonti legali sono governate anche come agenti
separati. Il batch con timeout resta il percorso notturno principale, ma ogni
fonte registra una run autonoma in `source_agent_runs` con stato, durata,
timeout, documenti trovati, documenti lavorati, invariati e messaggio di
errore. `/admin/aggiornamenti-legali/fonti` mostra l'ultimo esito agente per
canale e `/admin/pianificazioni` crea job `legal_source_<codice>` avviabili
manualmente o schedulabili dal superadmin, sempre da catalogo autorizzato e
senza comandi shell.

Aggiornamento 2.243.9: `/admin/aggiornamenti-legali/fonti` espone il
catalogo professionale delle fonti con famiglie, stato per canale,
conteggi reali, ciclo giornaliero e regole incrementali. Oltre alle fonti
richieste sono stati aggiunti presidi ufficiali scelti per gli studi legali:
INPS circolari/messaggi/sentenze, Curia CGUE, ISTAT prezzi, MIMIT incentivi,
AGCM, AGCOM e Banca d'Italia. INAIL e' censita come fonte in osservazione ma
non entra nel ciclo automatico finche' il canale pubblico non sara' leggibile
con stabilita' dal worker.

Aggiornamento 2.243.8: gli archivi locali ufficiali non restano piu'
separati dalla UI. La Ricerca Legale e la console admin Aggiornamenti legali
mostrano i conteggi reali di Normattiva/Gazzetta e, quando l'utente cerca, il
backend interroga prima `legal_updates.db`, poi `/data/normativa/normattiva.sqlite`
e `/data/fonti_ufficiali/lex_sources.sqlite`; solo se le evidenze locali non
bastano viene tentata la ricerca web governata. Questo rende visibili i
189.851 documenti, 800.757 articoli e 639.273 chunk Normattiva gia' presenti
sul volume Hetzner.

Lo scheduler 2.243.8 governa il ciclo quotidiano richiesto: alle 23:00 esegue
sincronizzazione degli archivi ufficiali, alle 23:10/23:15 passa a Update
Intelligence con timeout per fonte/pubblicazione. La sincronizzazione
Normattiva confronta il catalogo Open Data remoto con lo stato locale e non
riscarica ZIP gia' presenti e invariati; quando una collezione cambia mantiene
una sola copia per collezione/formato/vigenza. OpenGA viene trattata come fonte
ufficiale CKAN nelle cartelle Calendario Udienze, Decreti, Ordinanze, Pareri,
Provvedimenti pubblicati, Ricorsi definiti, Ricorsi pendenti, Ricorsi pervenuti
e Sentenze. La verifica pubblica legge anche contesto pagina e allegati
ufficiali collegati, cosi' Lex riceve evidenze testuali e non solo link.
Sono stati aggiunti anche presidi ufficiali ad alto valore per studi legali:
interpelli del Ministero del Lavoro, newsletter/provvedimenti del Garante
Privacy, atti ANAC e download tecnici del PST Giustizia.

Update Intelligence non pubblica piu' automaticamente una proposta strutturale solo per confidenza AI: prima dell'autopublish viene eseguita una verifica pubblica governata su archivio fonti ufficiali, Normattiva, Gazzetta e ricerca web allowlist. Per normativa, prassi e giurisprudenza servono almeno una fonte primaria e una seconda conferma coerente; in caso contrario la proposta resta in coda revisioni con una nota operativa.

Aggiornamento 2.243.6: lo staging non usa piu' la coda revisione come stato primario del documento grezzo. All'apertura di `/admin/aggiornamenti-legali/staging` viene tentata la riconciliazione automatica: duplicati chiusi, cataloghi open data archiviati come non pubblicabili, contenuti ufficiali utili ma non strutturali pubblicati come news informativa quando superano la verifica fonte.

I path di Normattiva e Gazzetta sono ora collegati ai volumi runtime (`/data/normativa` e `/data/fonti_ufficiali`) tramite variabili ambiente e fallback container-aware, cosi' Lex e il motore aggiornamenti usano gli archivi generati in produzione invece dei soli file smoke locali.

Verifica infrastrutturale del 2026-05-16: i database canonici Normattiva/Gazzetta non erano presenti su Railway ne' su Hetzner. Su Hetzner sono stati ricreati nel volume attivo: Gazzetta (`lex_sources.sqlite` 32.129.024 byte, JSONL 20.342.735 byte, 28 documenti e 3.911 chunk) e Normattiva (`normattiva.sqlite` 2.868.604.928 byte, JSONL 1.093.268.667 byte, 19 ZIP raw validi, 189.851 documenti, 800.757 articoli e 639.273 chunk). Il manifest ufficiale Normattiva letto da `https://dati.normattiva.it/assets/come_fare_per/Normattiva%20OpenData.html` espone 23 collezioni: 19 hanno restituito ZIP validi, mentre `Regolamenti di delegificazione`, `Regolamenti governativi`, `Regolamenti ministeriali` e `Testi Unici` hanno restituito stream vuoto `application/octet-stream` e sono tracciate nel manifest tentativi. Railway ha il volume `/data` al 100% (1.8 GB usati su 1.8 GB, con circa 1.3 GB in allegati email) e non puo' ospitare l'indice Normattiva completo finche' non viene aumentato o liberato spazio senza cancellare dati di studio.

Aggiornamento 2.243.7: il lotto notturno `legal_updates_batch`, la console admin e il comando CLI possono eseguire la scansione massiva come job isolati per fonte/pubblicazione con timeout per elemento (`IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS`, default 180s). Le verifiche web esterne restano attive, ma un elemento lento non blocca l'intero processo.

---

## Aggiornamento operativo 2.243.4 - 2026-05-16

Lex AI legge ora anche il registro mediazione interno popolato dai tre elenchi ufficiali del Ministero della Giustizia: Registro Organismi, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione. Le evidenze sono marcate come fonte ufficiale di classe A e includono sezione, numero registro, denominazione o nominativo, stato, natura/tipo docente, territorio, codice fiscale, partita IVA, email e sito quando presenti.

La pagina `/ricerca-legale/mediazione` usa gli stessi dati acquisiti: non e' piu' un elenco di collegamenti, ma un archivio consultabile in IUSENTRA con ricerca e filtri. Lex riceve il contesto dal repository interno `normative_tables`, mentre il collegamento ministeriale resta riferimento di verifica.

La verifica API autenticata restituisce 3.038 schede: 3.035 record ministeriali piu' i tre accessi ufficiali. Il bridge usa l'identita' della riga importata e non l'URL ministeriale, cosi' i dati non vengono ridotti a una sola scheda per fonte.

OpenGA Giustizia Amministrativa e il gruppo `calendario-udienze` sono stati aggiunti al presidio Update Intelligence come fonti CKAN JSON; le risorse JSON disponibili vengono acquisite come testo consultabile per ricerca e Lex.

---

## Aggiornamento operativo 2.239.2 - 2026-05-16

La pagina React `Registro Mediazione` non dipende piu' dalla sola notizia di ripristino: espone tre schede di accesso ufficiale separate verso Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione. Le schede sono disponibili anche nella Ricerca Legale per query su mediazione, enti e formatori, senza leggere dati privati dello studio e senza avviare una ricerca esterna.

---

## Aggiornamento operativo 2.238.2 - 2026-05-15

Le richieste Lex su sentenze specifiche con numero e date multiple, ad esempio `Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026`, non cadono piu' sul metadata `SourceScope.reason`: il campo e' compatibile con i payload debug e il workflow `giurisprudenza_specifica` continua a produrre risposta governata.

Per i riferimenti Cassazione esatti, Lex prioritizza `cassazione` tra le fonti ufficiali e, se la ricerca generica non e' necessaria, legge la pagina pubblica `Giurisprudenza Penale` della Corte. La query sopra individua la scheda ufficiale `https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP50042`; la risposta indica cosa e' certo e resta `needs_review` finche' mancano testo integrale, motivazione e dispositivo.

Il widget Lex non mostra piu' pagine HTML di errore dentro la conversazione. Se `/api/assistente/chat` fallisce prima dello stream, l'endpoint risponde con JSON controllato e la UI mostra un messaggio operativo breve, lasciando il dettaglio tecnico ai log applicativi.

---

## Aggiornamento operativo 2.238.0 - 2026-05-15

`/ricerca-legale` non e' piu' una vista con filtro locale sulle sole schede gia' caricate. La query viene passata a `/api/v1/ui/ricerca-legale?q=...`, cercata nel repository giuridico SQL tenant-aware e arricchita con fallback ufficiale governato quando non ci sono almeno due fonti ufficiali con estratto testuale sufficiente.

La notizia PST `NWS4865` sul ripristino dei registri mediazione e' presente come fonte ufficiale stabile in News e Ricerca Legale, con link al Portale dei Servizi Telematici, data 2026-05-11 e contesto del ripristino dal 22/04/2026.

---

## Aggiornamento operativo 2.237.9 - 2026-05-15

Lex Operational Knowledge e' ora attivo di default nel bounded workflow: le domande su clienti, fascicoli, agenda, scadenze, preventivi, conferimenti, fatturazione, messaggi, documenti e template passano dal layer deterministico tenant-aware senza richiedere `LEX_OPERATIONAL_KNOWLEDGE_ENABLED=1`.

La ricerca giuridica pubblica resta separata: richieste su sentenze specifiche, giurisprudenza, normativa, Normattiva, Gazzetta, Cassazione o fonti ufficiali vengono deferite al workflow pubblico/web governato e non sono intercettate dal layer dei dati di studio. Restano sempre attivi RBAC, isolamento tenant, blocco azioni dispositive e protezione dei dati riservati.

Il fallback web legale non viene piu' bloccato dalla sola presenza di contesto interno: per `ricerca_legale`, giurisprudenza, normativa e fonti ufficiali, se il contesto locale non basta a rispondere, il payload Lex abilita `allow_external_research` e richiede fonti ufficiali governate. Le risposte strict includono il contesto testuale delle fonti effettivamente usate; se una fonte e' solo nominata ma non porta un estratto, Lex degrada la risposta a `needs_review`.

---

## 1. Come Lex decide oggi se usare contesto interno

Il contesto studio viene costruito da `web/services/assistente_studio_context.py` tramite `build_lex_studio_context()`. La decisione avviene in due step:

### Step A — Selezione sezioni per keyword (`_select_detail_sections`)
Le sezioni vengono incluse in base a match testuale sulla domanda. Threshold: top 5 sezioni per punteggio.

| Sezione | Keyword trigger |
|---------|----------------|
| Clienti | "cliente", "clienti", "assistito", "anagrafica" |
| Fascicoli | "fascicolo", "fascicoli", "rg", "pratica", "causa" |
| Agenda | "agenda", "appuntamento", "udienza" |
| Scadenziario | "scadenza", "termine", "scadenze" |
| Fatturazione | "fattura", "parcella", "onorario" |

**Problema**: se la domanda è "dammi i dati del cliente Mario Rossi" ma il nome del cliente è in minuscolo e la sezione non viene triggerata per via di normalizzazioni, Lex non carica il contesto cliente.

### Step B — Caricamento dati (`_clienti_lines`)
```python
selected = matches[:4] if matches else all_rows[:4]
```
**Limite critico**: massimo 4 clienti. Se ci sono omonimi o la ricerca restituisce molti risultati, i dati dettagliati vengono tagliati. Il testo restituito è solo `nome_completo + stato + referente` — mancano CF, PEC, email, telefono, fascicoli.

---

## 2. Come Lex decide oggi se usare il web

La funzione `_should_force_web_fallback()` in `assistente_studio_context.py` forza ricerca web se:
- NON è una query solo operativa (agenda/fascicolo/cliente senza termini legali)
- NON c'è contesto locale specifico (`_has_specific_local_context` = False)
- Almeno un token legale è presente: norma, normativa, legge, decreto, sentenza, cassazione, tar, giurisprudenza, etc.

**Problema critico**: `_has_specific_local_context` restituisce True se ci sono fonti `cliente:*` o `fascicolo:*` nei sources, **bloccando la ricerca web anche per sentenze specifiche**. Se la domanda è "nel fascicolo Rossi trova la Sentenza n. 7919" → contesto fascicolo viene caricato → `_has_specific_local_context = True` → web bloccato → Lex usa solo il DB locale che non contiene quella sentenza.

---

## 3. Perché una sentenza specifica non forza ricerca web

Il router classifica correttamente "Sentenza n. 7919 del 31/03/2026" come `giurisprudenza_specifica` (priorità 7 in `lex/router.py`). Ma il retrieval layer non ha un meccanismo di "exact reference override": anche per `giurisprudenza_specifica`, se esiste qualsiasi fonte locale (anche solo `studio:default` o agenda), `_has_specific_local_context` può restituire True e bloccare il web.

Non esiste `case_law_reference_parser.py` che estragga numero+data da una query e forzi `public_web_forced=True`. Il sistema non distingue "dimmi delle sentenze sulla prescrizione" (generico) da "trovami la Sentenza n. 7919 del 31/03/2026" (riferimento esatto).

---

## 4. Perché vengono mostrate fonti correlate non richieste

Il motore di retrieval (`lex/retrieval/orchestrator.py`, `lex/research/public_legal_research_gateway.py`) non ha un "exact match guard". Quando cerca sul web governato, restituisce tutti i risultati rilevanti per il query semantico, non filtrati per numero/data sentenza. L'`answer_builder.py` non distingue tra "fonte esatta richiesta" e "fonti correlate non richieste".

Risultato: per "Sentenza n. 7919/2026" vengono mostrate le prime 5-12 sentenze che contengono termini simili, nessuna delle quali è necessariamente la 7919.

---

## 5. Perché confidence diventa media anche se manca testo integrale/dispositivo

In `lex/formatting/answer_builder.py`, la confidence viene calcolata su:
- numero di evidenze
- presenza di fonti ufficiali
- freshness score
- post-guard risk

Non considera se il testo integrale o il dispositivo della sentenza specifica è effettivamente nelle evidenze. Quindi: 3 sentenze correlate → confidence media (0.6-0.7) anche se nessuna è la sentenza richiesta e nessuna ha il testo integrale.

---

## 6. Perché il cliente presente nello studio può non essere letto

Cinque cause distinte:

1. **Keyword mismatch**: la sezione "Clienti" si attiva solo se la domanda contiene "cliente/assistito/anagrafica". "dammi i dati di Mario Rossi" → nessun trigger → sezione non caricata.
2. **Limite 4 risultati**: `_clienti_lines` ritorna max 4 clienti, testo ridotto a nome+stato.
3. **Cache stale**: TTL 90s — se i dati del cliente sono stati modificati di recente, la cache restituisce dati vecchi.
4. **Testo fonte insufficiente**: il campo `text` nella source è solo "Tipo: X. Stato: Y. Referente: Z." — mancano email, PEC, CF, fascicoli, note.
5. **No entity extraction**: la domanda non viene analizzata per estrarre nome proprio, CF, PIVA, email → la ricerca `gestore.cerca(question)` può non trovare il cliente se la domanda ha molte parole estranee.

---

## 7. Sezioni del contesto studio caricate

Le sezioni vengono selezionate da `_select_detail_sections_for_chat()` (chat mode) o `_select_detail_sections()` (default), massimo 4-5 sezioni per richiesta:

| Sezione | TTL cache | Contenuto |
|---------|-----------|-----------|
| Fascicoli | 90s | Titolo, RG, tribunale, oggetto — massimo 4 |
| Clienti | 90s | Nome, stato, referente — massimo 4 |
| Agenda | 60s | Appuntamenti prossimi 21 giorni — massimo 4 |
| Scadenziario | 60s | Scadenze imminenti — massimo 4 |
| Fatturazione | 120s | Parcelle recenti — massimo 4 |
| Template atti | 120s | Template disponibili — massimo 4 |
| Tariffario | 300s | Scaglioni DM 55 |
| Ricerca legale | 180s | Motori ricerca legale |
| Archivio sentenze | 120s | Sentenze indicizzate localmente |

---

## 8. Limiti di `_clienti_lines`

```python
def _clienti_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_clienti()
    all_rows = gestore.tutti()
    stats = gestore.statistiche()
    matches = gestore.cerca(question) if _clean_spaces(question) else []
    selected = matches[:4] if matches else all_rows[:4]      # ← MAX 4
    sources = [_source(...)  for row in selected]           # ← solo nome+stato+referente
```

Limiti:
- Ritorna massimo 4 clienti
- Non include email, PEC, CF, PIVA, telefono, indirizzo
- Non include fascicoli collegati
- Non include documenti, note, tag
- Non fa entity extraction prima di chiamare `gestore.cerca()`
- Se `question` ha molte parole inutili, `cerca()` può non trovare il match

---

## 9. Limiti di `_select_detail_sections`

```python
def _select_detail_sections(question: str) -> set[str]:
    # Punteggio per keyword → top 5 sezioni
    return set(selected[:5])
```

Limiti:
- Nessuna entity extraction (nomi propri, CF, PIVA non triggerano sezioni)
- Massimo 5 sezioni → può scartare sezioni rilevanti se competono con altre
- Non distingue tra "cliente con dati anagrafici" e "cliente nel contesto di un fascicolo"
- Nessun meccanismo di force-include per intent specifici

---

## 10. Limiti di `_should_force_web_fallback`

```python
if _has_specific_local_context(local_sources):
    return False          # ← blocca web se c'è QUALSIASI fonte locale specifica
```

Limiti critici:
- Blocca ricerca web anche per `giurisprudenza_specifica` se c'è un fascicolo in contesto
- Non distingue exact reference (sentenza specifica) da query generica
- Non considera il workflow corrente (giurisprudenza_specifica dovrebbe sempre usare web)
- Nessun parametro `exact_reference` o `force_public_web`

---

## 11. Limiti di `official_web.search_recognized_official_web`

In `lex/retrieval/official_web.py`:
- Usa DuckDuckGo come motore di ricerca su domini allowlisted
- Non ha query optimizer per sentenze specifiche (no "site:cortedicassazione.it N. XXXX")
- Non fa exact match verification sui risultati: restituisce i primi N risultati per query semantica
- Nessun filtro per numero/anno sentenza
- Non distingue tra "trovato documento esatto" e "trovato documento correlato"
- Cache TTL 900s — query per "Sentenza 7919/2026" può restituire risultati cached per query diverse

---

## 12. Cosa va corretto (piano di azione)

| Problema | Soluzione | Fase |
|----------|-----------|------|
| Sentenza specifica non forza web | `case_law_reference_parser.py` + `exact_legal_reference_guard.py` | 4, 5 |
| `_has_specific_local_context` blocca web per sentenze specifiche | Modifica `_should_force_web_fallback` per bypassare se exact reference | 6 |
| Clienti non letti (keyword mismatch) | Entity extraction + intent `cliente_anagrafica` | 9, 10 |
| Max 4 clienti con dati ridotti | `studio_data_gateway.py` con dati completi | 8 |
| Risultati correlati presentati come fonte | `exact_legal_reference_guard.py` filtro post-retrieval | 5 |
| Confidence media senza testo integrale | Confidence cap in `exact_legal_reference_guard.py` | 5 |
| Nessuna classificazione public/private scope | `source_scope_policy.py` | 2 |
| Debug insufficiente | Aggiornamento `debug_payload_builder.py` | 12 |
