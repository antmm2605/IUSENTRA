# OCR — Esportazioni strutturate, NER legale e motori ensemble

Estensione **engine-independent** della pipeline esistente `legal_ocr/`
(ingest+ZIP, preprocessing, motore primario+fallback, QC/confidenza, Lex export,
audit hash-chain). Le funzioni qui descritte non richiedono un motore OCR per
essere eseguite e testate: lavorano sui token già prodotti.

## Cosa aggiunge

| Modulo | Funzione | Output |
|---|---|---|
| `legal_ocr/alto.py` | `build_alto_xml(tokens, pages)` | ALTO-XML v4 (TextBlock/TextLine/String con HPOS/VPOS/WIDTH/HEIGHT + WC) |
| `legal_ocr/tables.py` | `reconstruct_tables(tokens)` + `table_to_csv/html` | tabelle ricostruite da coordinate → CSV e HTML |
| `legal_ocr/ner_legal.py` | `extract_legal_entities(text)` | NumeroRuolo (R.G.), Uffici, Parti, Date, Riferimenti normativi |
| `legal_ocr/engines.py` | `EasyOcrEngine`, `PaddleOcrEngine` | adapter motori generali locali (reali se installati) |
| `legal_ocr/unlimited/` | `UnlimitedOcrEngine`, batch, domande Lex | adapter Unlimited-OCR self-hosted, native-first e benchmark |

Nell'evidenza di ogni documento (`_run_single`) compaiono ora:
`alto_xml_path` (file ALTO su disco), `tables` (lista con `csv_path`, `html`,
`n_rows`, `n_cols`, `page`), `legal_entities` e `vector_source_manifest`
con testo OCR completo, mappa pagine, hash e stato qualità per Lex AI. Non è
chunking OCR: il database vettoriale potrà segmentare dopo, ma la fonte resta
il documento letto integralmente. L'evento
`ocr.structured_export` è aggiunto alla audit-chain firmata.

## Motori ensemble e disponibilità reale

La pipeline usa un motore primario con catena di fallback (nessun silenzio: ogni
fallimento è un EngineRun con `errors`, e si passa al motore successivo).

| Motore | `build_engine(...)` | Stato in questo ambiente |
|---|---|---|
| Tesseract (stampato IT) | `tesseract` | wrapper presente, **binario `tesseract` non installato** → degrada |
| EasyOCR (generale) | `easyocr` | libreria non installata → degrada al fallback |
| PaddleOCR / PP-OCR (generale) | `paddleocr` / `pp-ocr` | libreria non installata → degrada al fallback |
| Unlimited-OCR self-hosted | `unlimited-ocr` | opzionale, spento di default; richiede endpoint locale/privato OpenAI-compatible |
| Testo nativo (PDF con testo) | `native-text-fallback` | **disponibile** (pdfplumber): fallback reale |
| QC deterministico | `static-low-confidence` | disponibile (test QC) |

Gli adapter `EasyOcrEngine`/`PaddleOcrEngine` sono **reali**: se la libreria è
installata caricano il modello una sola volta (cache) e producono token con
bbox e confidenza; se assente ritornano errori e la pipeline prosegue col
fallback. Per attivarli serve un ambiente con le librerie e i modelli scaricati
(rete/Docker), vedi sotto.

`UnlimitedOcrEngine` usa codice IUSENTRA e un servizio esterno solo come endpoint
self-hosted: non importa `trust_remote_code` nel processo applicativo. La lettura
è ibrida: testo nativo PDF quando è affidabile, Unlimited-OCR per pagine
scansionate, fallback corrente se il servizio non è pronto. Se l'endpoint non
fornisce coordinate o confidenze native, i token vengono marcati come sintetici e
restano soggetti a QC/HIL invece di dichiarare certezza falsa.

## Layout, tabelle e limiti onesti

- La ricostruzione tabellare è basata sulle **coordinate dei token** (righe per
  banda verticale, colonne per bande occupate, così le celle multi-parola
  restano unite). Funziona quando i token hanno bbox reali (Tesseract/EasyOCR/
  PaddleOCR). Con il solo fallback testo nativo (bbox degenerato) le tabelle
  possono non emergere: è atteso, non un errore.
- Il rilevamento layout **visivo** con OpenCV (classi testo/tabella/timbro/mano/
  codice) e l'**HTR** per il manoscritto richiedono `cv2`/modelli non presenti
  in questo ambiente: restano un miglioramento lato motore, da abilitare in un
  ambiente provvisto.

## Esempio

```python
from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline

store = LegalOcrEvidenceStore("/data/ocr", "studio-rossi")
pipeline = LegalOcrPipeline(
    LegalOcrConfig(tenant_id="studio-rossi", primary_engine="easyocr", fallback_engine="native-text-fallback"),
    store,
)
evidence = pipeline.run_path("/incoming/busta.zip", tenant_id="studio-rossi", document_id="D-1")[0]
print(evidence["alto_xml_path"], evidence["legal_entities"]["numero_ruolo"])
```

## NER legale — campi estratti

Deterministico (pattern + dizionario IT), non inventa: ogni entità riporta il
testo realmente trovato.

- **numero_ruolo**: `{numero, anno, testo}` — varianti R.G./R.G.N.R./Ruolo Generale; anni a 2 cifre normalizzati.
- **uffici**: tipo canonico + sede (`Tribunale di Milano`), case-insensitive.
- **parti**: `{attore, convenuto}` da `c/`, `contro`, `vs`.
- **date**: formati `gg/mm/aaaa` e `gg mese aaaa`.
- **riferimenti**: `art./artt./articolo N (c.p.c./c.p.p./c.c./cost.)`, `L./D.Lgs./D.L./D.P.R./D.M./D.P.C.M. n/anno`.

## Stato test

Suite engine-independent verde in sandbox (`tests/test_legal_ocr_structured.py`,
11 casi: ALTO ben formato, tabelle 3×3 con celle multi-parola, NER positivi e
negativi, normalizzazione anno, factory motori, degrado adapter, E2E pipeline con
ALTO+entità+audit). La suite ensemble end-to-end con 30+ file reali
(stampato/storto/timbri/tabelle/manoscritto/PDF multipagina/ZIP mix/rumorosi) e
il Docker con modelli scaricati restano da eseguire su un **ambiente OCR
provvisto** (binario tesseract + cv2/numpy + easyocr/paddle + rete per i modelli).
```
