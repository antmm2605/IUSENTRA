# PEC ZIP Ingestion

Quando arriva una PEC con allegato ZIP, IUSENTRA non tratta lo ZIP come documento unico: conserva lo ZIP originale, calcola SHA-256, apre l’archivio in modo sicuro, estrae i file validati, mantiene la relazione PEC -> ZIP -> allegato e processa ogni file interno supportato.

## Garanzie

- ZIP originale conservato come evidenza immutabile.
- Hash SHA-256 per ZIP e file interni.
- ZIP annidati fino alla profondità configurata.
- Blocco di path traversal, path assoluti, drive Windows, zip bomb, file troppo grandi, troppi file, estensioni non ammesse e archivi corrotti.
- File non validati in quarantena o `needs_review`.
- Audit `archive.detected`, `archive.extracted`, `archive.unsafe_blocked`.
- Albero allegati disponibile via `GET /api/documents/{id}/archive-tree`.

## Configurazione

Le soglie sono in `ZipSafetyConfig` e possono essere sovrascritte da config Flask:

- `LEGAL_DOC_ZIP_MAX_SINGLE_FILE_BYTES`
- `LEGAL_DOC_ZIP_MAX_TOTAL_BYTES`
- `LEGAL_DOC_ZIP_MAX_FILES`
- `LEGAL_DOC_ZIP_MAX_DEPTH`
- `LEGAL_DOC_ZIP_MAX_COMPRESSION_RATIO`

## Regola Lex

Lex non indicizza lo ZIP né i file interni se non superano validazione e sicurezza. Gli allegati bloccati restano visibili in audit e revisione.
