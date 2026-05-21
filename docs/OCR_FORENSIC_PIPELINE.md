# OCR Forense

L’OCR forense salva originale, testo grezzo, testo corretto, motore, versione, lingua, timestamp, pagine, token, coordinate approssimate, confidenza per token e confidenza documento.

## Flusso

1. Acquisizione file originale con SHA-256.
2. Rilevamento MIME da magic bytes.
3. Estrazione testo nativa per PDF, DOCX, DOC, TXT, EML, XML e P7M quando il payload è leggibile.
4. OCR immagine tramite motore locale IUSENTRA/PCT quando disponibile.
5. Normalizzazione testuale controllata.
6. Tokenizzazione con bounding box e confidenza.
7. Evidenza audit `ocr.started` e `ocr.completed`.
8. Revisione umana se confidenza documento < `0.78` o token < `0.85`.

## Soglie

- Token sotto `0.85`: marcato `token_low_confidence`.
- Documento sotto `0.78`: review task `ocr`.
- Nessun testo leggibile: validazione `unreadable_document` o `needs_review`.

## Versioning

I record sono append-only: ogni esecuzione OCR produce un nuovo `document_ocr_runs` con token collegati. Le revisioni umane restano in `document_review_tasks`, `document_versions`, audit e hash chain.

## Estensione

Per aggiungere un motore OCR nuovo, implementare l’estrazione in `LegalDocumentIngestionService.run_ocr`, restituendo testo, warnings, errors, engine e versione. Non saltare mai la registrazione di confidenza e warning.
