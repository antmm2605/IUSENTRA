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
- `pct/document_intelligence/sources.py` e `pct/document_intelligence/indexer.py`: adattatori sorgenti reali del fascicolo e indicizzazione automatica per Lex.
- `pct/document_intelligence/pdf_quality.py`: scoring qualita' testo e riparazione conservativa dei segnaposto PDF `(cid:NN)`.
- `legal_ocr/unlimited_ocr.py` e `legal_ocr/unlimited/*`: motore opzionale `unlimited-ocr`, isolato dietro feature flag, per alimentare l'indice fascicolo con OCR integrale quando l'endpoint self-hosted e' pronto.
- I documenti firmati `.pdf.p7m` vengono trattati come PDF interni quando il contenuto è già leggibile oppure passano dall'estrazione CAdES governata; se un file resta non indicizzato, la pagina fascicolo riceve avvisi per-file invece di mostrare un completamento generico.
- I file `.txt` vengono indicizzati come testo puro; i file `.eml` vengono letti come email reale con intestazioni, corpo e allegati supportati (`pdf`, `docx`, `doc`, `txt`, `eml`). Gli allegati non leggibili generano avvisi, non completamenti finti.
- `pct/sql/20260505_documenti_ai.sql`: schema SQLite.
- `pct/sql/20260505_documenti_ai_postgres.sql`: schema PostgreSQL.
- `web/blueprints/api_v1_documenti_ai.py`: API v1 UI sotto `/api/v1/ui`, incluse le azioni interne `lex-indexing`.
- `web/services/document_intelligence_runtime.py`: wiring runtime Flask tenant-aware per service, sorgenti e stato indicizzazione.
- `lex/tools/fascicolo_documents.py`: tool Lex deterministici `list`, `read`, `find` basati sull'indice automatico.
- Area fascicoli React: box compatto `Indicizzazione Lex` dentro i documenti del fascicolo.

Scelta prodotto aggiornata: `Documenti AI` non e' una sezione operativa visibile all'utente e non deve sembrare un secondo archivio documentale. L'utente continua a usare i `Documenti fascicolo`; il dominio `pct/document_intelligence` indicizza automaticamente quei documenti per Lex. Eventuali componenti diagnostici o API legacy restano superfici tecniche, non CTA dell'avvocato.

Scelta OCR aggiornata: Unlimited-OCR non crea un indice parallelo e non spezza la lettura OCR in chunk. Quando abilitato, entra nell'estrazione `pct/document_intelligence` come sorgente integrale per `DocumentAIText`: testo completo, mappa pagine, hash/versione documento e warning. Se l'endpoint non e' configurato, se il documento supera il limite governato o se una pagina resta senza testo, IUSENTRA non registra il risultato AI come indice del fascicolo e conserva il percorso corrente (`pdfplumber`, OCR locale o fallback controllato). La successiva indicizzazione vettoriale puo' suddividere il testo solo partendo da questa sorgente completa e verificabile.

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
      "file_type": "pdf|docx|doc|txt|eml",
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
    "upload": false,
    "read": true,
    "search": true,
    "lex_tools": true,
    "generate_docx": false,
    "propose_edits": false,
    "compare": false
  }
}
```

Nota prodotto: la capability `upload` e' `false` nella superficie utente standard. I documenti entrano dall'archivio reale del fascicolo, dagli import portale o dall'editor professionale; il motore Document Intelligence li indicizza senza chiedere un secondo caricamento.

### GET `/api/v1/ui/fascicoli/<fascicolo_id>/lex-indexing`

```json
{
  "mock_fallback": false,
  "fascicolo_id": "string",
  "lex_indexing": {
    "total_documents": 16,
    "ready": 16,
    "queued": 0,
    "indexing": 0,
    "errors": 0,
    "stale": 0,
    "last_indexed_at": "ISO string|null",
    "status": "ready|partial|working|error|stale"
  }
}
```

### POST `/api/v1/ui/fascicoli/<fascicolo_id>/lex-indexing/aggiorna`

Aggiorna o processa i documenti pendenti/stale usando solo sorgenti reali del fascicolo. Risposta identica a `GET /lex-indexing`.

### POST `/api/v1/ui/fascicoli/<fascicolo_id>/lex-indexing/riprova-errori`

Riprova documenti in errore quando l'utente e' autorizzato. Risposta identica a `GET /lex-indexing`.

### POST `/api/v1/ui/fascicoli/<fascicolo_id>/documenti-ai/upload`

Endpoint interno/legacy per compatibilita' tecnica. Non e' esposto come CTA standard: il flusso prodotto corretto salva prima il documento nel fascicolo reale e poi indicizza la sorgente.

Richiesta `multipart/form-data`, campo `file`.

```json
{
  "mock_fallback": false,
  "document": {
    "id": "string",
    "original_filename": "string",
    "safe_filename": "string",
    "file_type": "pdf|docx|doc|txt|eml",
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

Input e output sono JSON stabili, in italiano lato messaggi applicativi, con hash SHA-256 e pagina quando disponibile. Ogni lettura o ricerca passa dal service e produce audit senza loggare testo integrale. I tool leggono solo documenti `ready` dell'indice automatico; i documenti non indicizzati vengono segnalati come non disponibili, senza inventarne il contenuto.

## Regole Lex

- Lex risponde sempre in italiano, salvo citazioni letterali o denominazioni ufficiali non traducibili.
- Le risposte su fascicolo usano prima documenti indicizzati, dati strutturati, attivita', scadenze, comunicazioni e depositi.
- Fonti ufficiali esterne sono ammesse solo quando la domanda le richiede davvero; in quel caso il payload espone `external_sources_used=true` e una `external_sources_reason`.
- Se un'informazione non risulta dall'indice/documenti disponibili, Lex deve scrivere: `Non risulta dai documenti disponibili nel fascicolo.`

## Roadmap

- MVP 1: indicizzazione automatica di PDF/DOCX/DOC gia' presenti nel fascicolo, hash SHA-256, versione 1, estrazione testo best-effort, lettura Lex, ricerca, stato indicizzazione nel fascicolo e citazioni base.
- MVP 2: generazione DOCX governata da template e repository IUSENTRA.
- MVP 3: modifiche proposte, accetta/rifiuta, audit e diff.
- MVP 4: comparazione documenti e tabular review.

## Criteri di accettazione

- dati reali, nessun mock operativo;
- `mock_fallback=false` in tutte le risposte API;
- tenant-aware e nessun accesso cross-tenant;
- RBAC e sessione utente rispettati;
- audit su upload/import fascicolo, versione, estrazione, lettura e ricerca;
- CSRF sulle scritture browser;
- test backend e contratti frontend;
- nessun codice AGPL copiato;
- UI italiana;
- nessuna sezione utente standard `Documenti AI` separata;
- Lex sempre in italiano e fascicolo-first;
- nessun path filesystem assoluto nei payload;
- nessun provider esterno per contenuti documentali senza policy Lex.

## Limiti MVP 1

Il formato `.doc` e' ammesso in upload per preservare il file originale e calcolarne l'hash, ma l'estrazione testo richiede un adattatore locale di conversione governato. Se non disponibile, il documento resta in `error` con audit leggibile e file originale conservato.

Le citazioni sono predisposte a livello dominio; la generazione di atti, le modifiche proposte e la comparazione documentale restano capability esplicitamente false.

Gli adapter sorgente maturi in questa tranche sono `Documenti fascicolo`, import portale e salvataggio editor professionale. Attivita', udienze, scadenze, comunicazioni e istanze restano disponibili a Lex tramite i bounded context esistenti; l'eventuale trasformazione in documenti indicizzati separati sara' una tranche successiva solo quando esiste un artefatto documentale reale.
