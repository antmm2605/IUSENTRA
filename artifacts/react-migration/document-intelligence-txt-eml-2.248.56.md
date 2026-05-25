# Document Intelligence TXT/EML - 2.248.56

Data verifica: 2026-05-25.

## Esito

- Document Intelligence accetta `pdf`, `docx`, `doc`, `txt`, `eml`.
- La migrazione SQLite aggiorna i database esistenti con vincolo storico `pdf/docx/doc`.
- La migrazione PostgreSQL sostituisce il vincolo `file_type` con la matrice `pdf/docx/doc/txt/eml`.
- Il fascicolo visualizza `.eml` e `.txt` e li elimina con risposta JSON senza errore 500.
- Il pannello Documenti AI consente upload `TXT` ed `EML` e il tipo front-end include i nuovi formati.

## Verifiche

| Comando / verifica | Esito | Nota |
| --- | --- | --- |
| `python -m py_compile pct\document_intelligence\repository.py pct\document_intelligence\extraction.py web\bootstrap\fascicoli_document_helpers.py web\bootstrap\fascicoli_document_routes.py` | OK | Sintassi confermata sul perimetro repository, estrazione e anteprima fascicolo. |
| `python -m pytest -q tests/test_document_intelligence_repository_sql.py tests/test_document_intelligence_auto_indexing.py tests/test_document_intelligence_extraction.py tests/test_document_intelligence_security.py tests/test_document_intelligence_api.py tests/test_document_intelligence_frontend.py tests/test_fascicoli_document_resilience.py tests/test_fascicolo_detail_ux.py::test_documenti_eml_e_txt_si_visualizzano_e_si_eliminano --tb=short` | OK | 53 test passati su SQL, indicizzazione, API, front-end statico, sicurezza, anteprima e cancellazione. |
| `npm run typecheck` in `frontend/` | OK | TypeScript verde dopo l'estensione del tipo `DocumentAIFileType`. |
| `python tools\sync_packaging_files.py --check`; `python scripts\validate_openapi.py docs\openapi.yaml`; `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short` | OK | Packaging, OpenAPI e readiness allineati a `2.248.56`. |
