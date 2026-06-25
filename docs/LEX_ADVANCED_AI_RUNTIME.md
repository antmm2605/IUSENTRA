# Lex AI - runtime avanzato misurabile

Data: 2026-05-17

Questo documento traduce in pratica quattro linee di evoluzione: MTP/speculative decoding, LLM Wiki, GLM-OCR e Gemini Embedding 2. La regola e' unica: nessuna capacita' viene promossa solo perche' esiste. Prima deve essere configurata, osservata, misurata sul carico IUSENTRA e mantenere fallback sicuri.

## 1. MTP e speculative decoding

MTP e la decodifica speculativa sono utili solo con serving compatibile. In IUSENTRA non vengono attivati su Ollama in modo implicito.

Variabili:

| Variabile | Default | Uso |
|---|---:|---|
| `IUSENTRA_AI_SERVING_ENGINE` | `ollama` | Valori operativi previsti: `ollama`, `vllm`, `sglang`. |
| `IUSENTRA_AI_SPECULATIVE_MODE` | `off` | Valori da provare: `mtp`, `eagle`, `ngram`, `draft`. |
| `IUSENTRA_AI_SPECULATIVE_DRAFT_MODEL` | vuoto | Modello draft se il serving lo richiede. |

Gate prima del cutover:

- p50/p95 primo token;
- token al secondo;
- errori runtime;
- qualita' risposte su domande legali campione;
- confronto A/B con serving corrente.

## 2. LLM Wiki come livello compilato

LLM Wiki non sostituisce il RAG. Lo usiamo come livello compilato sopra fonti ufficiali gia' inventariate, con citazioni che rimandano sempre al dato originale.

Variabili:

| Variabile | Default | Uso |
|---|---:|---|
| `IUSENTRA_LLM_WIKI_ENABLED` | `0` | Abilita la verifica del livello wiki. |
| `IUSENTRA_LLM_WIKI_ROOT` | `data/intelligence/llm_wiki` | Cartella delle pagine Markdown/JSON compilate. |

Regola di qualita': ogni pagina wiki deve essere validata con probe diagnostici per trovare fatti persi, versioni superate o citazioni mancanti.

## 3. GLM-OCR per PDF legali in Markdown

GLM-OCR e' una strada promettente per PDF legali, tabelle e layout complessi. In produzione lo preferiamo self-hosted; il cloud resta bloccato finche' non e' autorizzato.

Variabili:

| Variabile | Default | Uso |
|---|---:|---|
| `IUSENTRA_GLM_OCR_ENABLED` | `0` | Abilita il presidio GLM-OCR. |
| `IUSENTRA_GLM_OCR_PROVIDER` | `self_hosted` | `self_hosted` oppure `maas`. |
| `IUSENTRA_GLM_OCR_ENDPOINT` | vuoto | Endpoint locale o self-hosted del parser. |
| `IUSENTRA_GLM_OCR_MODE` | `markdown` | Output atteso dalla pipeline. |

Gate prima del cutover:

- Markdown leggibile e stabile;
- tabelle, formule, firme e allegati;
- tempo per pagina;
- confronto con OCR corrente;
- fallback automatico al motore corrente se GLM-OCR non risponde.

## 4. Unlimited-OCR per PDF lunghi e scansionati

Unlimited-OCR è integrato come motore OCR AI opzionale self-hosted. La logica è
prudente: testo PDF nativo prima, modello AI solo sulle pagine scansionate o
povere, fallback corrente se l'endpoint non risponde, benchmark Lex prima di
promuovere il motore.

Variabili:

| Variabile | Default | Uso |
|---|---:|---|
| `IUSENTRA_UNLIMITED_OCR_ENABLED` | `0` | Abilita il motore `unlimited-ocr`. |
| `IUSENTRA_UNLIMITED_OCR_ENDPOINT` | vuoto | Endpoint OpenAI-compatible/SGLang self-hosted. |
| `IUSENTRA_UNLIMITED_OCR_MODEL` | `Unlimited-OCR` | Nome modello servito. |
| `IUSENTRA_UNLIMITED_OCR_PROVIDER` | `self_hosted` | `self_hosted`, `cloud`, `maas`, `external`. |
| `IUSENTRA_UNLIMITED_OCR_CONCURRENCY` | `2` | Concorrenza benchmark batch. |
| `IUSENTRA_UNLIMITED_OCR_MAX_PAGES` | `48` | Limite pagine per run governato. |
| `IUSENTRA_UNLIMITED_OCR_STREAM` | `1` | Usa risposte streaming OpenAI/SGLang quando disponibili. |
| `IUSENTRA_UNLIMITED_OCR_SYNTHETIC_CONFIDENCE` | `0.84` | Confidenza prudente per attivare confronto/fallback se mancano bbox reali. |
| `IUSENTRA_UNLIMITED_OCR_EXTERNAL_ALLOWED` | `0` | Autorizza endpoint non locale/privato. |

Gate prima del cutover:

- lettura completa delle pagine senza salti silenziosi;
- domande Lex con citazioni su R.G., ufficio, parti, date, norme, PEC e importi;
- confronto con OCR corrente e fallback verificato;
- tempi per pagina e profondità coda OCR;
- nessun provider esterno senza policy privacy esplicita.

Script operativo:

```powershell
python scripts/benchmark_unlimited_ocr_lex.py .\documento.pdf --tenant tenant-demo --json
```

## 5. Gemini Embedding 2

Gemini Embedding 2 e' interessante per RAG multilingua e multimodale. Non diventa default automatico perche' invia contenuti a un provider esterno e perche' gli spazi vettoriali sono incompatibili con embedding precedenti.

Variabili:

| Variabile | Default | Uso |
|---|---:|---|
| `IUSENTRA_EMBEDDING_PROVIDER` | `local` | Impostare `gemini` per usare Gemini Embedding 2. |
| `LEX_EXTERNAL_ALLOWED` | `0` | Deve essere `1` per inviare contenuti a Google. |
| `GEMINI_API_KEY` / `IUSENTRA_GEMINI_API_KEY` | vuoto | Chiave API. Non viene mai esposta nei payload. |
| `IUSENTRA_GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | ID tecnico ufficiale Gemini API per il profilo embedding; in prodotto viene esposto come Gemini Embedding 2. |
| `IUSENTRA_GEMINI_EMBEDDING_DIMENSIONS` | `768` | Dimensione vettori. Ammessi 128-3072. |

Regola obbligatoria: passando a Gemini Embedding 2 bisogna reindicizzare l'intero corpus interessato. I vettori locali precedenti non vanno mischiati con quelli Gemini.

## 6. Osservabilita'

`/api/metriche/runtime` espone `providers.advanced_ai` con:

- `mtp_serving`;
- `llm_wiki`;
- `glm_ocr`;
- `unlimited_ocr`;
- `gemini_embedding_2`.

Quando una capacita' e' abilitata ma non pronta, la tassonomia segnala:

- `AI_ACCELERATION_UNMEASURED`;
- `LLM_WIKI_NOT_READY`;
- `GLM_OCR_NOT_READY`;
- `UNLIMITED_OCR_NOT_READY`;
- `GEMINI_EMBEDDINGS_NOT_READY`.

Il comportamento corretto e' lasciare il runtime corrente operativo, correggere configurazione o benchmark, poi promuovere solo dopo risultati misurati.

## 7. Fonti tecniche verificate

- vLLM MTP: https://docs.vllm.ai/en/latest/features/speculative_decoding/mtp/
- SGLang speculative decoding: https://sgl-project-sglang-93.mintlify.app/advanced/speculative-decoding
- SpecDecode-Bench: https://specdecode-bench.github.io/
- GLM-OCR: https://github.com/zai-org/GLM-OCR
- GLM-OCR paper: https://arxiv.org/abs/2603.10910
- Unlimited-OCR: https://github.com/baidu/Unlimited-OCR
- Unlimited-OCR paper: https://arxiv.org/abs/2606.23050
- Gemini Embedding 2 docs: https://ai.google.dev/gemini-api/docs/embeddings
- WiCER / LLM Wiki: https://arxiv.org/abs/2605.07068
