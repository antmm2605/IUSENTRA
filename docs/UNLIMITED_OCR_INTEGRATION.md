# Unlimited-OCR in IUSENTRA

Data: 25 giugno 2026

## Obiettivo

Unlimited-OCR viene integrato come motore AI opzionale, isolato e misurabile per
PDF lunghi, PDF scansionati e documenti legali con layout complesso. Non
sostituisce automaticamente Tesseract, testo nativo, EasyOCR o PaddleOCR: entra
nella pipeline `legal_ocr` come motore `unlimited-ocr` con fallback corrente e
controlli di qualità.

Il target operativo è leggere il 100% delle pagine utili senza successi
silenziosi: testo nativo quando affidabile, AI solo sulle pagine scansionate,
fallback ibrido locale (`local-hybrid-ocr`) se l'endpoint non risponde,
revisione umana quando confidenza, coordinate o campi obbligatori non sono
abbastanza solidi.

Per Lex AI e il futuro database vettoriale, l'output OCR resta integrale: testo
completo, mappa pagine, hash e stato qualità. La lettura OCR non viene spezzata
in chunk; eventuale segmentazione per embedding è una fase successiva e deve
partire sempre dalla sorgente completa verificata.

## Struttura

Codice nostro, ispirato alla logica della repo Baidu ma senza vendoring:

| File | Ruolo |
|---|---|
| `legal_ocr/unlimited/config.py` | feature flag, endpoint, privacy, limiti pagine, concorrenza, retry |
| `legal_ocr/unlimited/client.py` | client OpenAI-compatible/SGLang, payload immagini, parsing risposta |
| `legal_ocr/unlimited/batch.py` | conversione PDF in immagini, job concorrenti, output Markdown |
| `legal_ocr/unlimited/qa.py` | domande Lex-style su testo OCR con citazioni dal documento |
| `legal_ocr/unlimited_ocr.py` | adapter `EngineRun` per la pipeline OCR legale |
| `scripts/benchmark_unlimited_ocr_lex.py` | benchmark OCR + domande Lex sui PDF letti |
| `scripts/manage_unlimited_ocr.ps1` | doctor/start/health/logs/stop del servizio self-hosted |
| `scripts/check_unlimited_ocr_endpoint.py` | healthcheck OpenAI-compatible e smoke OCR |
| `deploy/unlimited-ocr/docker-compose.unlimited-ocr.yml` | sidecar SGLang isolato per host GPU |

## Configurazione

Default sicuro: spento.

| Variabile | Default | Uso |
|---|---:|---|
| `IUSENTRA_UNLIMITED_OCR_ENABLED` | `0` | abilita il motore |
| `IUSENTRA_UNLIMITED_OCR_ENDPOINT` | vuoto | endpoint self-hosted, es. `http://127.0.0.1:10000` |
| `IUSENTRA_UNLIMITED_OCR_MODEL` | `Unlimited-OCR` | nome modello servito |
| `IUSENTRA_UNLIMITED_OCR_PROVIDER` | `self_hosted` | `self_hosted`, `cloud`, `maas`, `external` |
| `IUSENTRA_UNLIMITED_OCR_TIMEOUT_SECONDS` | `300` | timeout richiesta |
| `IUSENTRA_UNLIMITED_OCR_MAX_RETRIES` | `3` | retry controllati |
| `IUSENTRA_UNLIMITED_OCR_CONCURRENCY` | `2` | concorrenza benchmark batch |
| `IUSENTRA_UNLIMITED_OCR_MAX_PAGES` | `48` | limite pagine per run governato |
| `IUSENTRA_UNLIMITED_OCR_MAX_IMAGE_BYTES` | `8388608` | limite immagine pagina |
| `IUSENTRA_UNLIMITED_OCR_IMAGE_MODE` | `base` | profilo immagini SGLang |
| `IUSENTRA_UNLIMITED_OCR_STREAM` | `1` | usa risposta streaming OpenAI/SGLang quando disponibile |
| `IUSENTRA_UNLIMITED_OCR_SYNTHETIC_CONFIDENCE` | `0.84` | confidenza prudente quando l'endpoint non dà coordinate/confidenze token |
| `IUSENTRA_UNLIMITED_OCR_EXTERNAL_ALLOWED` | `0` | autorizza endpoint non locale/privato |

Endpoint pubblici o cloud restano bloccati senza policy privacy esplicita.

## Uso

Doctor/avvio endpoint self-hosted:

```powershell
.\scripts\manage_unlimited_ocr.ps1 doctor
.\scripts\manage_unlimited_ocr.ps1 start
.\scripts\manage_unlimited_ocr.ps1 health
```

Il comando `start` usa il compose isolato `deploy/unlimited-ocr/docker-compose.unlimited-ocr.yml`.
Il container espone un server SGLang OpenAI-compatible su `127.0.0.1:10000`.
Se l'host non espone un acceleratore compatibile, il comando si ferma prima
dell'avvio e IUSENTRA resta fail-closed: nessun risultato viene marcato
`unlimited-ocr` senza modello reale.

Profilo Hetzner/host GPU:

```bash
COMPOSE_PROFILES=ai,unlimited-ocr
IUSENTRA_UNLIMITED_OCR_ENABLED=1
IUSENTRA_UNLIMITED_OCR_ENDPOINT=http://unlimited-ocr:10000
```

Pipeline legal-grade con fallback ibrido:

```powershell
python scripts/run_legal_ocr.py .\documento.pdf --tenant tenant-demo --primary unlimited-ocr --fallback local-hybrid-ocr --json
```

Benchmark OCR + domande Lex:

```powershell
python scripts/benchmark_unlimited_ocr_lex.py .\documento.pdf --tenant tenant-demo --json --output-report artifacts/unlimited-ocr/report.json
```

Benchmark concorrente stile repo Baidu, utile per throughput:

```powershell
python scripts/benchmark_unlimited_ocr_lex.py .\documento.pdf --tenant tenant-demo --run-page-batch --batch-output-dir artifacts/unlimited-ocr/pages --json
```

## Garanzie e limiti

- IUSENTRA non carica `trust_remote_code` nel processo applicativo.
- Il server SGLang/vLLM resta esterno e governato, preferibilmente locale o rete
  privata dello studio.
- I PDF con testo nativo affidabile vengono letti senza GPU.
- Le pagine scansionate vengono inviate al motore AI e ricomposte nel testo OCR.
- Se il motore non risponde, il fallback ibrido corrente resta operativo.
- Anche quando il motore risponde, la confidenza sintetica predefinita resta
  sotto la soglia di fallback: il motore corrente può quindi confrontare il
  risultato invece di essere sostituito secco.
- Le risposte Lex del benchmark richiedono citazioni testuali; se manca evidenza
  scrivono che non è possibile rispondere senza inventare.
- Quando l'endpoint non fornisce coordinate/confidenze native, la pipeline marca
  token e QC in modo prudente: non dichiara certezza probatoria falsa.

## Criteri prima della promozione

1. Campione reale di PDF lunghi, scansionati, storti, con timbri, tabelle e PEC.
2. Zero pagine saltate senza warning.
3. Domande Lex risposte con citazioni per R.G., ufficio, parti, date, norme, PEC e importi.
4. Tempi per pagina e coda OCR sotto soglia rispetto al baseline.
5. Nessun provider esterno senza autorizzazione.
6. Fallback corrente verificato quando endpoint o modello non sono disponibili.

## Prova fascicolo reale del 25 giugno 2026

Fascicolo locale: `data/fascicoli/documenti/4AC27E0B`.

Report salvati in `artifacts/unlimited-ocr/real-fascicolo-2026-06-25/`.

- `Citazione_53242802.pdf`: fallback ibrido `native=6 tesseract=0`, `6/6` pagine con testo, `11438` caratteri nel manifest sorgente, domande Lex `5/7`.
- `Memoria183_68894819.pdf`: fallback ibrido `native=9 tesseract=0`, `9/9` pagine con testo, `13099` caratteri nel manifest sorgente, domande Lex `6/7`.
- `Documento_65209905.pdf`: candidato scansionato; fallback ibrido `native=0 tesseract=1`, `1100` caratteri nel benchmark, domande Lex `4/7`, confidenza media `0.5173`, token sotto `0.75` pari a `55.696%`, PEC letta in modo rumoroso. Questo documento resta il campione negativo per misurare l'upgrade Baidu.
- Indice `Documenti AI`: `3/3` documenti `ready`; `Documento_65209905.pdf` indicizzato con `pdfplumber+ocr`, `1` pagina, `1124` caratteri e warning OCR espliciti.
- `--require-unlimited` su endpoint non pronto fallisce con blocco esplicito: non sono ammessi successi finti.

Questa prova conferma l'indice fascicolo e i guardrail, non la qualità del
modello Baidu. La qualità Baidu va misurata solo dopo `manage_unlimited_ocr.ps1
health` con smoke OCR positivo.

## Aggiornamento pipeline comune del 25 giugno 2026

La logica OCR comune è ora raggiunta anche dai flussi che prima usavano
l'adapter storico `pct.ocr.estrai_testo`:

- PEC e allegati: `pct.pec_pipeline.extract_text_with_coverage` passa da
  `pct.ocr.estrai_testo`, che delega prima a `pct.document_intelligence.extraction`;
- notifiche e recupero scadenze da documenti fascicolo: il presidio documentale
  continua a usare `DocumentAIService.process_lex_indexing_sources` e quindi la
  stessa estrazione Document AI;
- deposito e indice documenti: il flusso React `Prepara deposito` legge il
  fascicolo tramite Document AI e i testi OCR indicizzati, non tramite un percorso
  parallelo;
- route manuali e worker OCR che chiamano `pct.ocr.estrai_testo` ricevono lo
  stesso comportamento: Document AI/Unlimited-OCR quando disponibile, fallback
  locale storico solo se il motore primario non produce testo.

La correzione è intenzionalmente conservativa: Unlimited-OCR resta spento di
default e self-hosted, ma quando viene configurato non serve duplicare codice nei
flussi PEC, notifiche o deposito. Tutti usano la stessa sorgente OCR integrale:
testo completo, pagine, hash, warning e manifest, prima dell'eventuale indice
Lex o vettoriale.

Guardrail eseguiti:

- `tests/test_ocr_pipeline_adapter.py`: verifica che `pct.ocr.estrai_testo`
  deleghi a Document AI e accetti anche path locali;
- `tests/test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline`:
  verifica che un PDF allegato PEC passi dall'adapter OCR comune;
- `tests/test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag`:
  conferma che il recupero documentale per agenda/scadenze/Lex usa Document AI.
