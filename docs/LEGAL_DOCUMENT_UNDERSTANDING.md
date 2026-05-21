# Legal Document Understanding

La piattaforma documentale IUSENTRA acquisisce documenti da upload, PEC e ZIP PEC, conserva evidenza probatoria e avvia una pipeline unica:

`document.uploaded / pec.received -> sicurezza file -> estrazione ZIP -> OCR forense -> classificazione -> entità -> validazione -> matching fascicolo -> eventi proposti -> revisione umana -> Lex solo se validato`.

## Ambito

Le regole di classificazione coprono civile, penale, amministrativo/PAT, tributario/PTT, Giudice di Pace/SIGP e stragiudiziale. Il motore riconosce atti introduttivi, provvedimenti, sentenze, verbali, ricevute PEC/deposito, allegati, consulenze, contratti, diffide, atti penali, TAR/CDS e tributari. Se la confidenza è bassa lo stato diventa `needs_review`; il sistema non inventa tipo documento o dati mancanti.

## Moduli

- `legal_document_ingestion/file_intake.py`: servizio end-to-end.
- `mime_detector.py`: MIME reale da magic bytes con fallback prudente.
- `zip_safety.py` e `archive_extractor.py`: estrazione ZIP sicura e ricorsiva.
- `repository.py`: schema SQLite tenant-aware, storage probatorio, audit e hash chain.
- `metrics.py`: report misurabile per il target 80%.
- `web/blueprints/legal_documents_api.py`: API `/api/documents*` e `/api/pec/<id>/process`.
- UI React `Documenti AI`: pannello “Lettura forense” con upload, badge, albero allegati, revisione e proof bundle.

## Database

La migrazione canonica è `pct/sql/20260521_legal_document_understanding.sql`. Le tabelle includono `documents`, `document_versions`, `document_files`, `document_archive_children`, `document_ocr_runs`, `document_ocr_tokens`, `document_classifications`, `legal_entities`, `document_validations`, `document_case_matches`, `document_events`, `document_review_tasks`, `evidence_audit_logs`, `evidence_hash_chain`, `proof_bundles`, `lex_index_jobs` e `lex_document_chunks`.

Ogni tabella contiene `tenant_id` o è collegata a record tenant-aware. Le query del repository filtrano sempre per studio; i test coprono l’impossibilità di leggere proof bundle o documenti di un tenant diverso.

## Feature Flag

I flag sono attivi di default e spegnibili:

- `ocr_forensic`
- `legal_document_understanding`
- `pec_zip_ocr`
- `lex_validated_documents_only`

Con flag spento le API restituiscono una risposta JSON governata e non alterano lo stato esistente.

## Limiti Noti

L’OCR usa estrattori locali disponibili nel runtime: PDF/DOCX/testo/XML sono gestiti nativamente, immagini e PDF scansionati dipendono dal motore OCR installato. Quando il testo non è leggibile il documento entra in revisione. Il target 80% non viene dichiarato raggiunto senza metriche su documenti reali.
