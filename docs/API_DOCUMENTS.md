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
- `GET /api/documents/{id}/proof-bundle/{bundle_id}`

È disponibile anche `GET /api/documents?fascicolo_id=...` per alimentare la UI di revisione.

Le risposte pubbliche non espongono `stored_uri`, path filesystem, root di storage o percorsi locali. Lista documenti, evidence, archive tree e creazione proof bundle restituiscono solo identificativi, metadati probatori, hash SHA-256, stato sicurezza e percorsi virtuali interni all'archivio quando servono a ricostruire la catena ZIP/PEC.

Il proof bundle scaricabile contiene `manifest.json`, `evidence.json`, `chain/audit.json`, `chain/hash-chain.json`, `hashes.sha256` e l'originale sotto nome archivio sicuro. La route di download è l'unico canale previsto per ottenere il pacchetto; il client non riceve mai il path di storage.

## Errori

Gli errori sono JSON con `ok=false` e messaggio operativo. Le eccezioni interne non vengono esposte al chiamante.

## Revisione

`POST /api/documents/{id}/review` accetta una decisione strutturata. Se lo stato è `validated`, il servizio registra validazione umana e consente la successiva richiesta Lex.
