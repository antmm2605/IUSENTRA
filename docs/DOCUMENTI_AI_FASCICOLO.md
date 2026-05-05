# Documenti AI Fascicolo — Reimplementazione nativa IUSENTRA

## Decisione architetturale

Mike e' stato consultato solo come riferimento funzionale di prodotto. IUSENTRA non importa, copia, traduce o adatta codice, schema, prompt, asset o componenti UI di Mike, anche perche' Mike e' AGPL-3.0-only e perche' IUSENTRA ha dominio, tenant, storage, audit, Lex e licenza propri.

La feature e' una reimplementazione nativa IUSENTRA:

- Lex resta il punto centrale per l'assistenza AI sul fascicolo.
- Il fascicolo e' il contenitore operativo dei documenti.
- Lo storage e' tenant-aware e vive nel data root scrivibile dello studio.
- RBAC, sessione, CSRF sulle scritture e audit sono obbligatori.
- L'AI non e' fonte della verita': legge testo estratto e metadati governati, segnala warning e non inventa contenuti.
- I tool Lex non accedono al filesystem: passano da service e repository.

## Corrispondenza concettuale

| Concetto Mike | Concetto IUSENTRA |
| --- | --- |
| Mike Project | IUSENTRA Fascicolo |
| Mike Documents | Documenti del fascicolo |
| Mike Document Versions | Versioni documento tenant-aware |
| Mike Document Edits | Modifiche proposte/auditate |
| Mike Chats | Sessioni Lex sul fascicolo |
| Mike Workflows | Checklist, template e procedure guidate |
| Mike Tabular Reviews | Comparazione documenti |

## Confini negativi

Non fanno parte dell'implementazione:

- frontend Next.js;
- backend Express;
- schema Supabase originale;
- auth Supabase;
- R2/S3 come dipendenza obbligatoria;
- prompt inglesi copiati;
- componenti UI copiati;
- codice AGPL;
- provider esterni per contenuti documentali sensibili fuori dalle policy Lex.

## Architettura proposta

Componenti introdotti nell'MVP 1:

- `pct/document_intelligence/`: dominio Documenti AI Fascicolo, con modelli, repository, service, estrazione, citazioni, audit, sicurezza e versioning.
- `pct/sql/20260505_documenti_ai.sql`: schema SQLite.
- `pct/sql/20260505_documenti_ai_postgres.sql`: schema PostgreSQL.
- `web/blueprints/api_v1_documenti_ai.py`: API v1 UI sotto `/api/v1/ui`.
- `lex/tools/fascicolo_documents.py`: tool Lex deterministici `list`, `read`, `find`.
- `frontend/src/components/DocumentiAIPage.tsx` e componenti collegati: sezione React nel dettaglio fascicolo.

Il runtime scrive i file originali e il testo estratto sotto `documenti_ai/<tenant>/<fascicolo>/<documento>/` nel data root dello studio. I payload API non restituiscono path filesystem assoluti.

La Fase 3 rende il repository persistente su storage strutturato: quando e' attivo SQLite o PostgreSQL tenant-aware, `DocumentAIRepository` applica le migrazioni governate e legge/scrive le tabelle `fascicolo_documenti_ai*`; il JSON resta solo fallback esplicito per runtime non ancora migrati.

## Payload API

### GET `/api/v1/ui/fascicoli/<fascicolo_id>/documenti-ai`

```json
{
  "mock_fallback": false,
  "fascicolo_id": "string",
  "documents": [
    {
      "id": "string",
      "original_filename": "string",
      "safe_filename": "string",
      "file_type": "pdf|docx|doc",
      "mime_type": "string|null",
      "size_bytes": 123,
      "sha256": "string",
      "status": "uploaded|processing|ready|error|archived",
      "current_version_id": "string|null",
      "page_count": 10,
      "created_by": "string",
      "created_at": "ISO string",
      "updated_at": "ISO string"
    }
  ],
  "capabilities": {
    "upload": true,
    "read": true,
    "search": true,
    "lex_tools": true,
    "generate_docx": false,
    "propose_edits": false,
    "compare": false
  }
}
```

### POST `/api/v1/ui/fascicoli/<fascicolo_id>/documenti-ai/upload`

Richiesta `multipart/form-data`, campo `file`.

```json
{
  "mock_fallback": false,
  "document": {
    "id": "string",
    "original_filename": "string",
    "safe_filename": "string",
    "file_type": "pdf|docx|doc",
    "mime_type": "string|null",
    "size_bytes": 123,
    "sha256": "string",
    "status": "ready|error",
    "current_version_id": "string|null",
    "page_count": 10,
    "created_by": "string",
    "created_at": "ISO string",
    "updated_at": "ISO string"
  },
  "version": {
    "id": "string",
    "version_number": 1,
    "source": "upload",
    "sha256": "string",
    "created_at": "ISO string"
  },
  "extraction": {
    "status": "completed|failed",
    "engine": "string",
    "page_count": 10,
    "warnings": []
  }
}
```

### GET `/api/v1/ui/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>`

```json
{
  "mock_fallback": false,
  "document": {},
  "versions": [
    {
      "id": "string",
      "version_number": 1,
      "source": "upload",
      "sha256": "string",
      "created_at": "ISO string"
    }
  ],
  "audit_summary": {
    "last_event": "string|null",
    "last_event_at": "ISO string|null"
  }
}
```

### GET `/api/v1/ui/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>/testo`

```json
{
  "mock_fallback": false,
  "document_id": "string",
  "version_id": "string",
  "status": "ready",
  "extraction_engine": "string",
  "page_count": 10,
  "text": "string",
  "pages": [
    {
      "page_number": 1,
      "text": "string"
    }
  ],
  "warnings": []
}
```

### POST `/api/v1/ui/fascicoli/<fascicolo_id>/documenti-ai/<documento_id>/cerca`

Richiesta:

```json
{
  "query": "string",
  "max_results": 20
}
```

Risposta:

```json
{
  "mock_fallback": false,
  "document_id": "string",
  "query": "string",
  "results": [
    {
      "page_number": 1,
      "snippet": "string",
      "start_offset": 123,
      "end_offset": 150
    }
  ]
}
```

Errori standard:

```json
{ "mock_fallback": false, "detail": "messaggio chiaro", "code": "validation_error" }
```

`permission_denied`, `not_found` e `document_ai_internal_error` seguono la stessa forma.

## Tool Lex

I tool MVP 1 sono:

- `list_fascicolo_documents`
- `read_fascicolo_document`
- `find_in_fascicolo_document`

Input e output sono JSON stabili, in italiano lato messaggi applicativi, con hash SHA-256 e pagina quando disponibile. Ogni lettura o ricerca passa dal service e produce audit senza loggare testo integrale.

## Roadmap

- MVP 1: upload PDF/DOCX/DOC, hash SHA-256, versione 1, estrazione testo best-effort, lettura Lex, ricerca e citazioni base.
- MVP 2: generazione DOCX governata da template e repository IUSENTRA.
- MVP 3: modifiche proposte, accetta/rifiuta, audit e diff.
- MVP 4: comparazione documenti e tabular review.

## Criteri di accettazione

- dati reali, nessun mock operativo;
- `mock_fallback=false` in tutte le risposte API;
- tenant-aware e nessun accesso cross-tenant;
- RBAC e sessione utente rispettati;
- audit su upload, versione, estrazione, lettura e ricerca;
- CSRF sulle scritture browser;
- test backend e contratti frontend;
- nessun codice AGPL copiato;
- UI italiana;
- nessun path filesystem assoluto nei payload;
- nessun provider esterno per contenuti documentali senza policy Lex.

## Limiti MVP 1

Il formato `.doc` e' ammesso in upload per preservare il file originale e calcolarne l'hash, ma l'estrazione testo richiede un adattatore locale di conversione governato. Se non disponibile, il documento resta in `error` con audit leggibile e file originale conservato.

Le citazioni sono predisposte a livello dominio; la generazione di atti, le modifiche proposte e la comparazione documentale restano capability esplicitamente false.
