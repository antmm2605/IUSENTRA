# Generazione atti con Lex nell'editor professionale IUSENTRA

## Decisione architetturale

La generazione atti ispirata funzionalmente a Mike viene reimplementata in modo nativo IUSENTRA. Mike resta un riferimento concettuale per flussi come generazione, rilettura, versionamento, fonti e modifiche puntuali, ma nessun codice, schema, prompt o asset AGPL viene copiato, importato, tradotto o adattato.

IUSENTRA mantiene l'editor professionale esistente come unica superficie di lavoro. Lex non produce una bozza lunga in chat come artefatto finale: crea un documento reale del fascicolo, lo rilegge dal repository editor e poi risponde in italiano con sintesi, fonti usate e dati da completare.

## Moduli

- `pct/editor_ai/models.py`: record, versioni, fonti, richieste, piano bozza e proposte modifica.
- `pct/editor_ai/template_resolver.py`: risolve template dal catalogo atti IUSENTRA, senza inventare modelli.
- `pct/editor_ai/draft_planner.py`: prepara un piano strutturato italiano prima della generazione.
- `pct/editor_ai/prompt_builder.py`: prompt proprietari IUSENTRA, italiano-only, fascicolo-first.
- `pct/editor_ai/editor_renderer.py`: crea e rilegge documenti reali dell'editor.
- `pct/editor_ai/edit_proposals.py`: crea modifiche puntuali pending, senza applicazione automatica.
- `pct/editor_ai/repository.py`: persistenza JSON/SQLite/PostgreSQL tenant-aware per metadati Editor AI.
- `pct/editor_ai/service.py`: orchestrazione applicativa, RBAC, audit, fonti e versionamento.
- `web/blueprints/api_v1_editor_ai.py`: API v1 UI per bootstrap, genera, dettaglio, modifiche ed export.
- `lex/tools/editor_ai.py`: tool interni Lex per template, contesto, generazione, rilettura, modifiche ed export.

## Flusso generazione

1. L'utente apre un documento nell'editor professionale e sceglie `Nuovo atto con Lex`.
2. La UI carica template reali e documenti indicizzati del fascicolo con `mock_fallback=false`.
3. Il service valida permessi, template, fascicolo e fonti disponibili.
4. Lex costruisce un piano strutturato in italiano con sezioni, campi richiesti, fonti e warning.
5. Il contenuto generato viene convertito nel formato HTML governato dall'editor.
6. IUSENTRA salva il file come documento reale del fascicolo tramite `GestioneFascicoli.aggiungi_documento`.
7. Il service crea record `AttoAIRecord`, versione 1, fonti e audit.
8. Il documento viene riletto dal repository editor prima della risposta finale.

## Modifiche successive

Le richieste di modifica non rigenerano l'intero atto. Lex legge il documento corrente e produce `AttoAIEditProposal` con stato `pending`. Solo l'accettazione utente applica la modifica al documento editor e crea una nuova versione `ai_edit`; il rifiuto registra l'esito senza modificare il documento.

Operazioni previste MVP:

- `replace`
- `insert_after`
- `insert_before`
- `delete`
- `rewrite_section`
- `add_section`

## API

- `GET /api/v1/ui/fascicoli/<fascicolo_id>/editor-ai/bootstrap`
- `POST /api/v1/ui/fascicoli/<fascicolo_id>/editor-ai/genera`
- `GET /api/v1/ui/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>`
- `POST /api/v1/ui/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/modifiche/proponi`
- `POST /api/v1/ui/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/modifiche/<edit_id>/accetta`
- `POST /api/v1/ui/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/modifiche/<edit_id>/rifiuta`
- `POST /api/v1/ui/fascicoli/<fascicolo_id>/editor-ai/<atto_ai_id>/export`

Tutte le risposte dichiarano `mock_fallback=false`, usano errori italiani e non espongono path assoluti o segreti.

## Tool Lex

- `list_template_atti`
- `read_template_atto`
- `collect_fascicolo_context`
- `generate_editor_draft`
- `read_editor_document`
- `propose_editor_edits`
- `export_editor_document`

Lex deve usare `generate_editor_draft` quando l'utente chiede un atto e `propose_editor_edits` quando chiede modifiche su un atto esistente. La risposta resta sempre in italiano, salvo citazioni letterali in lingua originale.

## Storage

La feature usa migrazioni esplicite:

- `pct/sql/20260505_editor_ai.sql`
- `pct/sql/20260505_editor_ai_postgres.sql`

Tabelle:

- `fascicolo_editor_ai_atti`
- `fascicolo_editor_ai_versioni`
- `fascicolo_editor_ai_fonti`
- `fascicolo_editor_ai_modifiche`
- `fascicolo_editor_ai_audit`

Il documento editor resta nella source of truth documentale del fascicolo. Le tabelle Editor AI conservano metadati, versioni, snapshot, fonti, proposte e audit.

## Limiti MVP

- La generazione dipende dal runtime Lex configurato; se non disponibile viene creata una bozza strutturata governata da completare, con warning esplicito.
- Le modifiche sono puntuali e richiedono sempre accettazione o rifiuto umano.
- L'export finale usa le route editor esistenti DOCX/PDF.
- Non sono ancora implementate revisioni collaborative avanzate, tracking stile Word o comparazione documenti.

## Criteri di accettazione

- Nessun codice AGPL copiato.
- Nessun editor parallelo.
- Documento reale del fascicolo creato e apribile.
- Versione 1 generata all'atto della bozza.
- Rilettura obbligatoria dal repository editor.
- Fonti documentali tracciate.
- Audit senza contenuto integrale del documento.
- Tenant/RBAC e CSRF sulle scritture.
- Test backend e contratti React.
