# Storage Probatorio

Lo storage probatorio è gestito da `LegalDocumentRepository` sotto una radice tenant-aware. Ogni file è salvato con nome normalizzato e SHA-256; l’URI resta interno alla radice configurata.

## Contenuti Conservati

- file originale;
- ZIP originale;
- file estratti da ZIP;
- hash SHA-256;
- relazione padre/figlio;
- OCR raw/corretto;
- token, bbox e confidence;
- classificazioni;
- entità;
- validazioni;
- revisioni umane;
- audit log;
- hash chain;
- proof bundle esportabile.

## Append-Only

`evidence_audit_logs` è protetta da trigger anti-update e anti-delete. Le nuove classificazioni, validazioni, matching, OCR, eventi e job Lex sono inseriti come nuove righe; le modifiche operative sono tracciate in audit e hash chain.

## Proof Bundle

`POST /api/documents/{id}/proof-bundle` genera uno ZIP con `manifest.json`, evidenze e file originale disponibile. Il bundle è tenant-aware: un tenant diverso non può leggerlo né crearlo per documenti altrui.
