# Lex RAG Documenti Validati

Lex legge solo documenti con validazione `valid`, sicurezza `validated` e stato non in revisione. Il gate è protetto dal feature flag `lex_validated_documents_only`.

## Indicizzazione

Il job `lex_index_jobs` crea chunk in `lex_document_chunks` per paragrafo/pagina con metadati:

- `tenant_id`
- `fascicolo_id`
- procedimento, rito, fase
- ufficio e NRG estratti
- tipo documento
- provenienza: upload manuale, PEC, ZIP da PEC, portale o scansione
- affidabilità OCR
- pagina e disponibilità bbox
- warning OCR

## Esclusioni

Sono esclusi documenti unsafe, rejected, needs_review, file ZIP non validati e OCR con campi critici incoerenti. Un tentativo di indicizzazione produce job `blocked` con motivo esplicito, senza chunk.

## Risposte Lex

Quando Lex usa questi chunk deve citare documento, fascicolo, pagina, fonte, confidenza e warning. Le lacune restano dichiarate: il sistema non completa dati mancanti per inferenza non verificata.
