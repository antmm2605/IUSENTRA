# Lex Studio LLM Dataset Pipeline

## Scopo

Questa pipeline prepara dati di studio per due usi distinti, senza confonderli:

- **RAG immediato**: i documenti vengono indicizzati in chunk tenant-aware e restano dentro il perimetro dello studio. Lex può usarli subito come evidenze di retrieval.
- **Fine-tuning supervisionato**: dai chunk si preparano solo coppie domanda/risposta candidate, con metadati fonte, revisione umana obbligatoria e nessun addestramento automatico.

Caricare PDF o testi in archivio non è fine-tuning. Il fine-tuning richiede esempi supervisionati, verificati e coerenti con una finalità precisa.

## Moduli

- `lex/dataset/models.py`: dataclass serializzabili per documenti, manifest, chunk, task Q&A e coppie Q&A.
- `lex/dataset/manifest.py`: manifest di ingestione tenant-aware, con path sorgente sanitizzati.
- `lex/dataset/chunking.py`: chunking puro di testi, pagine e PDF già estratti o letti tramite estrattore iniettabile.
- `lex/dataset/qa.py`: generazione deterministica di task e Q&A mock per test/review, senza chiamare LLM reali.
- `lex/dataset/export.py`: export nei formati `alpaca`, `sharegpt` e `multilingual`, con file `jsonl`, `json` e `csv`.
- `lex/dataset/easy_dataset.py`: specifica di compatibilità per Easy Dataset come strumento esterno opzionale, senza importare codice AGPL.
- `lex/dataset/llama_factory.py`: specifica di interoperabilità con LLaMA Factory, LLaMA Board e import manuale in Ollama.
- `lex/dataset/pipeline.py`: orchestrazione pura manifest -> chunk -> task -> Q&A.
- `lex/dataset/batch.py`: batch tenant-aware per leggere `documenti_ai.json`, costruire manifest/chunk/Q&A ed esportare artefatti solo con consenso esplicito.
- `scripts/build_lex_studio_dataset.py`: CLI governata per dry-run e scrittura artefatti senza avviare training.

## Regole di governance

- Il `tenant_id` del manifest deve coincidere con il `tenant_id` di ogni documento.
- I path assoluti non vengono esportati: resta solo il nome file sanitizzato.
- I chunk sono `rag_ready=True` e possono alimentare il retrieval tenant-aware.
- Le coppie Q&A sono `supervised_fine_tuning_candidate` finché non vengono approvate.
- L'export JSONL include solo esempi approvati, salvo scelta esplicita di esportare una coda di revisione.
- Gli esempi con dati sensibili vengono esclusi dall'export ordinario; per dataset locali serve autorizzazione esplicita e rimangono marcati nei metadata.
- La pipeline non salva ragionamento interno e non ha campi dedicati a ragionamenti nascosti.
- `external_training=True` è rifiutato: l'export prepara file, ma non avvia training esterno.

## Easy Dataset come strumento esterno opzionale

Easy Dataset è il repository GitHub `ConardLi/easy-dataset`, pubblicato con licenza **AGPL-3.0**. Può essere utile come applicazione esterna per parsing di PDF, Markdown, DOCX, TXT ed EPUB, segmentazione, pulizia dati, label tree di dominio, generazione domande/risposte, dataset single-turn, multi-turn, dataset di valutazione ed export Alpaca, ShareGPT, Multilingual, JSON, JSONL e CSV.

IUSENTRA non copia e non incorpora codice Easy Dataset. Il confine ammesso è solo di interoperabilità:

- Easy Dataset gira fuori da IUSENTRA come tool governato dall'operatore.
- I file esportati rientrano in IUSENTRA come artefatti da revisione, mai come verità automatica.
- Ollama locale è il canale preferito quando si usa un generatore esterno governato.
- Endpoint OpenAI-compatible sono ammessi solo se la policy Lex privacy/source scope lo consente.
- L'import non deve includere ragionamento interno o campi di chain-of-thought.
- L'addestramento resta un passo separato, manuale e approvato.

## LLaMA Factory, LLaMA Board e Ollama

Il video `8T9epgWmaNI` chiarisce il passaggio successivo al dataset: usare LLaMA Factory/LLaMA Board come strumento esterno per supervised fine-tuning, registrando il dataset in `data/dataset_info.json`, scegliendo un formato Alpaca o ShareGPT, aprendo la preview del dataset, configurando SFT con LoRA/QLoRA, valutando il checkpoint e solo dopo esportando il modello.

IUSENTRA registra questo percorso in `lex/dataset/llama_factory.py` senza avviare training automatici:

- `build_llama_factory_dataset_info_entry(...)` produce la voce da inserire in `data/dataset_info.json`.
- `llama_factory_supported_capabilities()` dichiara formati, stage, licenza Apache-2.0 e policy Lex.
- `build_llama_factory_project_spec(...)` descrive il flusso operativo: export Q&A approvate, copia nel dataset directory di LLaMA Factory, preview, SFT, valutazione, export e import manuale in Ollama.
- La specifica espone `dataset_registration`, `privacy_policy`, `automation_policy` e `acceptance_gate` per rendere verificabile che il training e l'import Ollama restino manuali.

Passaggi manuali ammessi per l'operatore:

```powershell
llamafactory-cli webui
ollama create <nome-modello-lex> -f Modelfile
ollama show <nome-modello-lex>
ollama run <nome-modello-lex>
```

Questi comandi sono documentati come istruzioni operative, non vengono eseguiti dalla pipeline IUSENTRA.

Per Ollama il comportamento corretto resta governato:

- il modello base o adattato non viene importato automaticamente;
- l'operatore deve creare un `Modelfile` e usare comandi come `ollama create <nome-modello-lex> -f Modelfile`;
- prima di usare il modello nello studio servono test di accettazione su domande note, assenza di dati non autorizzati e confronto con RAG IUSENTRA;
- il RAG rimane il canale immediato per leggere i documenti reali, mentre il fine-tuning serve solo dopo revisione e autorizzazione.

Gate di accettazione prima dell'uso in studio:

- Preview dataset in LLaMA Board senza righe vuote, colonne errate o testi sensibili non autorizzati.
- Valutazione checkpoint su domande note e risposte attese approvate dallo studio.
- Confronto con RAG IUSENTRA: il modello non deve sostituire le citazioni documentali.
- Test Ollama locale con Modelfile approvato e modello creato manualmente.
- Verifica privacy: nessuna risposta espone dati fuori tenant, fonti non autorizzate o ragionamento interno.

Il gate rifiuta il percorso se viene rilevato training automatico, import Ollama automatico, dataset con dati sensibili non autorizzati, chain-of-thought salvato o risposte che inventano fonti.

Riferimenti riconosciuti:

- Repository LLaMA Factory: `https://github.com/hiyouga/LLaMA-Factory`
- WebUI LLaMA Factory: `https://llamafactory.readthedocs.io/en/latest/getting_started/webui.html`
- Dataset README: `https://github.com/hiyouga/LLaMA-Factory/blob/main/data/README.md`
- Video analizzato: `https://www.youtube.com/watch?v=8T9epgWmaNI`

## Flusso operativo

1. Costruire `StudioDatasetDocument` da documenti già autorizzati dello studio.
2. Generare il manifest con `build_ingestion_manifest(...)`.
3. Creare chunk con `chunk_document(...)` o `chunk_documents(...)`.
4. Preparare task Q&A con `build_qa_generation_tasks(...)`.
5. Generare coppie mock o sostituire in futuro il generatore con un componente governato e locale.
6. Far revisionare le coppie da un umano con responsabilità di studio.
7. Esportare JSONL solo dopo approvazione con `export_qa_pairs_jsonl(...)`.

## CLI batch tenant-aware

Il percorso operativo per i documenti/fascicoli già autorizzati passa dal JSON
runtime di Documenti AI Fascicolo. Il comando è in dry-run per impostazione
predefinita e non scrive chunk, Q&A o dataset se rileva dati sensibili senza
flag esplicito.

```powershell
python scripts\build_lex_studio_dataset.py `
  --tenant-id studio-rossi `
  --document-ai-json D:\data\tenants\studio-rossi\fascicoli\documenti_ai\documenti_ai.json `
  --fascicolo-id fas-123
```

Per scrivere artefatti locali:

```powershell
python scripts\build_lex_studio_dataset.py `
  --tenant-id studio-rossi `
  --document-ai-json D:\data\tenants\studio-rossi\fascicoli\documenti_ai\documenti_ai.json `
  --output-dir D:\data\tenants\studio-rossi\intelligence\lex_dataset\run-20260517 `
  --write
```

Se il batch contiene dati sensibili, la scrittura di `chunks.jsonl`,
`qa_tasks.jsonl`, `qa_review_queue.json` e degli export dataset resta bloccata
finché l'operatore non usa consapevolmente `--allow-sensitive-export`. Per
generare file candidate da coppie ancora in revisione serve anche
`--export-pending-review`; quei file non sono materiale di training pronto e
devono essere approvati da un umano prima di LLaMA Factory, Ollama o qualunque
altro runtime locale.

Artefatti previsti con scrittura autorizzata:

- `manifest.json`: inventario tenant-aware, senza path assoluti.
- `chunks.jsonl`: testi indicizzabili nel RAG interno dello studio.
- `qa_tasks.jsonl`: task Q&A con istruzioni e fonte, senza ragionamento interno.
- `qa_review_queue.json`: coppie candidate da revisione umana.
- `alpaca.jsonl`, `sharegpt.jsonl`, `multilingual.jsonl`: export opzionali,
  vuoti per impostazione predefinita finché gli esempi non sono approvati.

## Job notturno Superadmin

Il job governato `lex_dataset_nightly` compare nella console
`/admin/pianificazioni` come **Preparazione archivio Lex** dentro la famiglia
**Lex AI**. Gira alle 01:45, dopo gli agenti Lex operativi, e usa
`lex.dataset.nightly.run_lex_dataset_nightly(...)`.

Comportamento previsto:

- scorre gli studi attivi o, in single-tenant, il data root configurato;
- legge solo `fascicoli/documenti_ai/documenti_ai.json`;
- se il file Documenti AI non esiste ancora dentro la cartella tenant ma
  l'archivio condiviso contiene documenti con lo slug dello studio, usa quella
  sorgente e scrive comunque gli artefatti sotto il tenant corretto;
- prepara `manifest.json`, chunk, coda Q&A e file candidate sotto
  `intelligence/lex_dataset`;
- registra `latest_job.json` e `jobs.json`, così Impostazioni AI e
  Pianificazioni mostrano l'ultimo lavoro;
- non avvia fine-tuning, non chiama provider esterni e non importa modelli in
  Ollama senza revisione umana.

Variabili operative:

- `IUSENTRA_LEX_DATASET_MAX_DOCUMENTS`: limita i documenti per ciclo.
- `IUSENTRA_LEX_DATASET_LOCAL_SENSITIVE_STORAGE=1`: consente la scrittura
  locale tenant-aware dei chunk sensibili. È attivo per il job notturno perché
  resta dentro l'archivio dello studio.
- `IUSENTRA_LEX_DATASET_ALLOW_SENSITIVE_EXPORT=0`: compatibilità per bloccare
  anche la scrittura locale dei chunk sensibili quando serve una modalità più
  restrittiva.
- `IUSENTRA_LEX_DATASET_EXPORT_PENDING_REVIEW=1`: esporta anche esempi in
  revisione come file candidate, non come training approvato.

## Coda revisione in Impostazioni AI

Le domande non vengono inserite manualmente dall'avvocato partendo da zero.
IUSENTRA le genera come candidate in `qa_review_queue.json`, usando i
documenti già letti da Documenti AI e conservando la fonte del fascicolo.

Da **Impostazioni -> AI Locale -> Archivio e revisione Lex**, la card
**Domande in revisione** apre una coda operativa:

- la domanda proposta e la risposta proposta sono modificabili prima
  dell'approvazione;
- **Salva e approva** marca l'elemento come `approved`, registra revisore e
  orario, ma non avvia alcun training;
- **Scarta** marca l'elemento come `rejected` e lo esclude dal materiale da
  usare;
- ogni operazione scrive solo nell'archivio locale dello studio e registra un
  evento in `review_events.jsonl`;
- export, addestramento LLaMA Factory e import in Ollama restano passaggi
  separati e governati.

## Esempio minimo

```python
from lex.dataset import (
    ChunkingOptions,
    QAGenerationPolicy,
    StudioDatasetDocument,
    build_studio_dataset_pipeline,
    export_qa_pairs_jsonl,
    mark_qa_pair_reviewed,
)

document = StudioDatasetDocument(
    tenant_id="tenant-a",
    document_id="doc-1",
    title="Memoria autorizzata",
    text="Testo già estratto dal documento dello studio.",
    source_name="memoria.pdf",
    mime_type="application/pdf",
    source_kind="pdf",
)

result = build_studio_dataset_pipeline(
    "tenant-a",
    [document],
    chunking_options=ChunkingOptions(max_chars=1200, overlap_chars=120),
    qa_policy=QAGenerationPolicy(min_chunk_chars=80),
)

approved = mark_qa_pair_reviewed(result.qa_pairs[0], approved=True, reviewer_id="avv-1")
jsonl = export_qa_pairs_jsonl([approved], dataset_format="alpaca")
```

## Confine privacy

Il RAG interno lavora sui chunk nel tenant e conserva la provenienza documentale. Il dataset di fine-tuning, invece, è un artefatto derivato e più delicato: deve essere revisionato, ridotto a domanda/risposta, privo di ragionamento interno, con fonte tracciabile e senza invii esterni automatici.

Per dati sensibili la pipeline applica una redazione deterministica minima su codice fiscale, email, IBAN, RG e telefono. La redazione non sostituisce la revisione umana: serve solo come guardrail iniziale.

## Verifiche locali

Verifica del 17 maggio 2026 sul perimetro nuovo:

```powershell
python -m pytest tests\test_lex_studio_dataset_pipeline.py -q
python scripts\build_lex_studio_dataset.py --tenant-id tenant-a --document-ai-json <documenti_ai.json>
python -m ruff check lex\dataset tests\test_lex_studio_dataset_pipeline.py
```

Esito: test mirati e Ruff verdi. Il controllo `utf8-integrity` sul documento non ha rilevato mojibake o caratteri sostitutivi.
