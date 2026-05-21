# API Documenti

Le API sono sotto `/api` e richiedono sessione utente o API key tenant-aware.

## Endpoint

- `POST /api/documents/upload`
- `POST /api/pec/{id}/process`
- `POST /api/documents/{id}/ocr`
- `POST /api/documents/{id}/classify`
- `POST /api/documents/{id}/validate`
- `POST /api/documents/{id}/match-case`
- `POST /api/documents/{id}/review`
- `POST /api/documents/{id}/events/approve`
- `POST /api/documents/{id}/lex-index`
- `GET /api/documents/{id}/evidence`
- `GET /api/documents/{id}/archive-tree`
- `GET /api/documents/{id}/ocr-overlay`
- `POST /api/documents/{id}/proof-bundle`

È disponibile anche `GET /api/documents?fascicolo_id=...` per alimentare la UI di revisione.

## Errori

Gli errori sono JSON con `ok=false` e messaggio operativo. Le eccezioni interne non vengono esposte al chiamante.

## Revisione

`POST /api/documents/{id}/review` accetta una decisione strutturata. Se lo stato è `validated`, il servizio registra validazione umana e consente la successiva richiesta Lex.
