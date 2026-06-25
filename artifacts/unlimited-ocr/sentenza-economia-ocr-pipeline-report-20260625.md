# Report OCR, Lex Sentenza ed economia

Data: 25 giugno 2026

## Obiettivo

Rendere la lettura OCR una sorgente unica e governata per Document AI, Lex AI,
PEC, notifiche e deposito, e correggere la matrice economica delle sentenze
prima che alimenti fatturazione e DB vettoriale.

## Decisioni operative

- Unlimited-OCR resta un motore opzionale, self-hosted e spento di default.
- La sorgente OCR per Lex AI resta integrale: testo completo, pagine, hash,
  manifest e warning. I chunk sono solo una fase successiva dell'indice
  vettoriale, non il modo in cui viene letto il PDF.
- `pct.ocr.estrai_testo` delega prima a Document AI e poi usa fallback locale
  storico solo se il percorso comune non produce testo.
- PEC, notifiche e deposito non devono reintrodurre parser PDF/OCR paralleli:
  usano Document AI o l'adapter comune.

## Regole economiche

- `liquidazione_giudice`: importo spettante allo studio, estratto da formule
  esplicite di compenso/onorari.
- `spese_esborsi`: spese vive o esborsi riconosciuti in sentenza, separati dal
  contributo unificato.
- `contributo_unificato`: importo riportato solo se presente in un PDF/documento
  CU/PagoPA del fascicolo. Valore causa, scaglione, spese CTU o importi generici
  non alimentano il CU.
- Esenzione CU: se il fascicolo contiene `contributo unificato non dovuto`,
  `esente dal pagamento del contributo unificato`, `patrocinio a spese dello
  Stato` o `prenotazione a debito`, il pagamento CU viene salvato come
  `non_previsto`, senza importo e senza voce proforma.

## Bonifica tenant locale

Tenant: `tenant-8bf98719c459`.

Backfill eseguito:

```powershell
python scripts\backfill_sentenza_lex_economics.py --tenant tenant-8bf98719c459 --reset-lex-amounts --apply --report artifacts\unlimited-ocr\sentenza-economia-reset-apply-v5-rag-clean-20260625.json
```

Esito:

- `documents_seen=667`
- `raw_sentenze_found=14`
- `sentenze_found=7`
- `applied=1`
- `matrix_confirmed=1`
- `vector_indexed=1`
- `vector_embedding_errors=0`
- `reset_vector_documents_removed=4`
- `reset_vector_chunks_removed=6`

Caso `DC5BF1DB`:

- liquidazione giudice: `1500,00`
- contributo unificato da PDF fascicolo: `98,00`
- spese/esborsi: `125,00`
- proforma Lex: `c6a1c268-2f55-4583-9ac9-ca2d90c316c1`
- totale proforma: `2126,20`
- indice RAG: un solo documento `lex_sentenza_tribunale`, schema
  `sentenza_tribunale_compact_v4`, 2 chunk embedded a 768 dimensioni.

Caso `AF656B01`:

- nessun pagamento Lex residuo;
- nessuna proforma Lex residua;
- nessun documento RAG `lex_sentenza_tribunale` residuo con il falso importo
  `5200,00`.

## Integrità dati

- `studio.db`: `PRAGMA integrity_check=ok`.
- `intelligence/local_ai.db`: `PRAGMA integrity_check=ok`.
- `audit_data_flow_contract.py` repair e cold: ok.
- `audit_tenant_data_structure.py` repair e cold: ok.
- Stato dati: `source_of_truth=sqlite`, `json_authoritative=false`,
  `operational_untracked=0`, zero warning e zero errori.

## Test eseguiti

- `python -m compileall pct\ocr.py pct\fascicolo_sentenza_economica.py pct\pec_pipeline.py web\services\document_intelligence_runtime.py scripts\backfill_sentenza_lex_economics.py`
- `python -m pytest tests/test_ocr_pipeline_adapter.py tests/test_fascicolo_sentenza_economica.py tests/test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline tests/test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag tests/test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler -q`
- `python -m pytest tests/test_fascicolo_sentenza_economica.py tests/test_backfill_sentenza_lex_economics.py tests/test_ocr_pipeline_adapter.py tests/test_unlimited_ocr_integration.py tests/test_legal_ocr_structured.py tests/test_document_intelligence_extraction.py tests/test_document_intelligence_auto_indexing.py tests/test_legal_ocr_pipeline.py tests/test_pec_audit_pipeline.py::test_extract_text_with_coverage_pdf_usa_adapter_ocr_pipeline tests/test_pec_auto_acquire.py -q`

## Stato prova reale

Prova materiale eseguita nel browser integrato su `http://127.0.0.1:8080`,
Docker locale `2.253.118`:

- `/fascicoli?vista=economica`: card Alessi Robertino visibile in layout
  compatto con `Contributo unificato da PDF EUR 98,00`, `Spese/esborsi
  EUR 125,00`, `Liquidazione giudice EUR 1.500,00`, `Parcella EUR 2.126,20`;
  nessun importo falso `5.200`.
- `/fatturazione`: proforma `2026/001`, origine `Sentenza Lex AI`, cliente
  Alessi Robertino, totale `EUR 2.126,20`; dettaglio aperto con voci
  `Compensi liquidati in sentenza EUR 1.500,00`, `Contributo unificato
  confermato da PDF nel fascicolo EUR 98,00`, `Spese ed esborsi riconosciuti
  in sentenza EUR 125,00`.
- `/email` e `/notifiche-legali`: superfici React aperte sulla copia reale,
  senza errori console; PEC mostra messaggi e allegati reali, notifiche mostra
  relata, controlli PEC e allegati.
- `/fascicoli/DC5BF1DB/deposito/prepara`: dopo il caricamento dati mostra
  `RG 466/2023 - Alessi Robertino`, `20` documenti nel fascicolo, `8`
  documenti in busta, indice generato dal software in tempo reale e lista
  documentale reale.

Prova PDF reale sul fascicolo `DC5BF1DB`:

- `Sentenza_3080731.pdf` e `depositoMinutaSentenzaSemplificata.pdf` letti con
  `pdfplumber+ocr`, 4 pagine, zero errori Tesseract; parser: sentenza
  `199/2026`, RG `466/2023`, liquidazione `1500,00`, spese/esborsi `125,00`.
- `attoACQ.pdf` e `attoACQ.pdf.p7m` letti con `pdfplumber+ocr` e
  `cades:pdfplumber+ocr`, zero errori Tesseract; evidenza CU:
  `Contributo unificato da PDF`, importo `98,00`.

Correzione runtime OCR locale: `TESSDATA_PREFIX` viene ora risolto e impostato
senza passare `--tessdata-dir` quotato a pytesseract. Su Windows il flag quotato
rompeva `image_to_data`/`image_to_string` con path
`"...\tessdata"/ita.traineddata`; il runtime usa quindi la variabile ambiente
valida e i test bloccano la regressione.

Riprova post-rebuild Docker: `app`, `scheduler-worker` e `ocr-worker` healthy
su `2.253.118`; OCR dentro il container `app` confermato sugli stessi file
reali (`Sentenza_3080731.pdf`, `attoACQ.pdf.p7m`) con zero errori Tesseract.
Il gate runtime ha atteso `lex_sentenza_economia_auto` `completed` alle
`21:27:15Z` e `pec_audit_pipeline_workers` `completed` alle `21:25:02Z`, con
`errors=0` e `vector_embedding_errors=0`.
