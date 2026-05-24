# Report test pipeline PEC OCR

Data: 24 maggio 2026.

## Esito

Verde sul perimetro mirato.

## Comandi eseguiti

| Comando | Esito |
| --- | --- |
| `python -m ruff check pct\pec_ocr_pipeline.py legal_document_ingestion\mime_detector.py tests\test_pec_ocr_pipeline.py scripts\test_pec_ocr_pipeline.py` | OK |
| `python -m pytest tests\test_pec_ocr_pipeline.py tests\test_legal_document_ingestion.py -q --tb=short` | OK, 20 test passati |
| `python -m compileall -q pct\pec_ocr_pipeline.py legal_document_ingestion\mime_detector.py scripts\test_pec_ocr_pipeline.py` | OK |
| `python scripts\test_pec_ocr_pipeline.py --runtime-root .tmp\pec-ocr-script-test-final` | OK |

## Output script veritiero

Lo script ha generato una PEC sintetica con ZIP, duplicato e `daticert.xml`, poi ha confermato:

- `mail.ingest`: 1
- `mail.unzip`: 1
- `raw_blob.stored`: 3
- `ocr.skipped`: 1
- `ocr.task`: 2
- `ocr.result`: 2
- `document.indexed`: 2
- `lex.ingest.doc`: 2
- OCR success: 100%
- dedup hit-rate: 0,333

La cartella temporanea usata per lo smoke è stata rimossa dopo la verifica.
