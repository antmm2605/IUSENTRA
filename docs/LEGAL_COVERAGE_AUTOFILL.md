# Coverage AI e Autopubblicazione Controllata

## Obiettivo

Trasformare la tassonomia procedure da catalogo statico a capability continua:

`DB -> auditor -> gap queue -> AI + retrieval -> draft v2 -> review -> publish SQL -> DB aggiornato -> training implicito`

## Componenti

- `pct/legal_coverage_repository.py`
  Gestisce schema PostgreSQL, snapshot, gap queue, draft, publish history e learning events.
- `pct/legal_coverage_pipeline.py`
  Orchestration pura del flusso audit -> gap -> draft -> review -> publish.
- `pct/legal_coverage_ai.py`
  AI + retrieval interno con Ollama, preset e fallback prudente.
- `pct/legal_taxonomy_sql_generator.py`
  Validatore spec v2 e generatore SQL operativo.
- `web/blueprints/legal_coverage_admin.py`
  Dashboard admin, review UI e API JSON di revisione.

## Tabelle create

- `legal_subbranch_profiles`
- `legal_procedures`
- `legal_procedure_variants`
- `legal_procedure_phase_map`
- `legal_procedure_acts`
- `legal_procedure_documents`
- `legal_procedure_document_map`
- `legal_procedure_norms`
- `legal_procedure_checklists`
- `legal_procedure_requirements`
- `legal_procedure_deadlines`
- `legal_procedure_outcomes`
- `legal_procedure_rules`
- `legal_templates`
- `legal_template_variables`
- `coverage_snapshots`
- `coverage_gap_queue`
- `generated_procedure_drafts`
- `published_procedure_history`
- `coverage_policies`
- `coverage_learning_events`

## Configurazione

Variabili supportate:

- `LEGAL_COVERAGE_DB_URL`
- `LEGAL_COVERAGE_DB_HOST`
- `LEGAL_COVERAGE_DB_PORT`
- `LEGAL_COVERAGE_DB_NAME`
- `LEGAL_COVERAGE_DB_USER`
- `LEGAL_COVERAGE_DB_PASSWORD`

Alias con prefisso `PCT_` equivalenti:

- `PCT_LEGAL_COVERAGE_DB_URL`
- `PCT_LEGAL_COVERAGE_DB_HOST`
- `PCT_LEGAL_COVERAGE_DB_PORT`
- `PCT_LEGAL_COVERAGE_DB_NAME`
- `PCT_LEGAL_COVERAGE_DB_USER`
- `PCT_LEGAL_COVERAGE_DB_PASSWORD`

Per attivare la pipeline reale puoi usare due strade:

- configurazione esplicita con `LEGAL_COVERAGE_DB_*` o `PCT_LEGAL_COVERAGE_DB_*`
- riuso automatico del PostgreSQL tenant-aware gia' attivo per lo studio, senza dover duplicare la configurazione coverage
- riuso automatico anche di configurazioni tenant legacy gia' valorizzate con host/database/utente PostgreSQL, quando il registry storico non ha ancora riallineato formalmente il `db_config.mode`

L'AI usa il runtime locale gia' configurato nel gestionale:

- `LOCAL_AI_BASE_URL`
- `LOCAL_AI_CHAT_MODEL`

## UI admin

- Dashboard: `/admin/copertura-ai`
- Review queue: `/admin/copertura-ai/review`

Se il tenant ha gia' PostgreSQL attivo, la dashboard non resta piu' bloccata su "Database coverage non raggiungibile" solo per mancanza delle variabili dedicate: usa il backend studio gia' disponibile e mostra la pipeline reale.
Se il superadmin opera fuori impersonazione, la dashboard seleziona automaticamente il tenant unico attivo oppure permette di scegliere esplicitamente lo studio dalla UI, propagando lo stesso contesto a review, action forms e API.
La UI mostra anche il nome studio configurato nel `config/studio.json` del tenant e il backend coverage effettivo (`PostgreSQL tenant-aware`, `SQLite locale`, `JSON locale`), cosi' il contesto operativo non resta ambiguo.
La schermata review autoseleziona la prima bozza disponibile, spiega il flusso da seguire e rende visibile il contesto di retrieval usato per generare il draft.

## CLI

- `python tools/coverage_auditor.py ...`
- `python tools/gap_builder.py ...`
- `python tools/priority_engine.py ...`
- `python tools/auto_fill_generator.py ...`
- `python tools/draft_reviewer.py list ...`
- `python tools/publisher.py ...`

## Regole di pubblicazione

Auto publish solo se:

- policy consente `auto_publish_allowed = true`
- `complexity_level = LOW`
- validazione senza errori
- score validazione >= 90
- subbranch non specialistico

Review obbligatoria per:

- penale
- sanitario
- immigrazione complessa
- crisi
- internazionale
- casi `MEDIUM`, `HIGH`, `SPECIALIST`

## Training implicito

Ogni publish registra un evento in `coverage_learning_events`.
Il retrieval dei draft successivi usa:

1. procedure gia' presenti nel DB
2. storico publish
3. learning events recenti
4. seed operativo interno
