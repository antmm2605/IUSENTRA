# Coverage AI e Autopubblicazione Controllata

## Obiettivo

Trasformare la tassonomia procedure da catalogo statico a capability continua:

`DB -> auditor -> gap queue -> AI + retrieval -> draft v2 -> review -> publish SQL -> DB aggiornato -> training implicito`

## Componenti

- `pct/legal_coverage_repository.py`
  Gestisce schema PostgreSQL, snapshot, gap queue, draft, publish history e learning events.
- `pct/legal_coverage_sqlite_repository.py`
  Gestisce lo stesso flusso sull'archivio SQLite condiviso di piattaforma, con schema SQL locale, review e publish reali anche senza PostgreSQL.
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
- `coverage_review_audit_log`

## Configurazione

Variabili supportate:

- `LEGAL_COVERAGE_SQLITE_DB`
- `LEGAL_COVERAGE_DB_URL`
- `LEGAL_COVERAGE_DB_HOST`
- `LEGAL_COVERAGE_DB_PORT`
- `LEGAL_COVERAGE_DB_NAME`
- `LEGAL_COVERAGE_DB_USER`
- `LEGAL_COVERAGE_DB_PASSWORD`

Alias con prefisso `PCT_` equivalenti:

- `PCT_LEGAL_COVERAGE_SQLITE_DB`
- `PCT_LEGAL_COVERAGE_DB_URL`
- `PCT_LEGAL_COVERAGE_DB_HOST`
- `PCT_LEGAL_COVERAGE_DB_PORT`
- `PCT_LEGAL_COVERAGE_DB_NAME`
- `PCT_LEGAL_COVERAGE_DB_USER`
- `PCT_LEGAL_COVERAGE_DB_PASSWORD`

Per attivare la pipeline reale puoi usare due strade:

- archivio SQLite condiviso di piattaforma, configurabile con `LEGAL_COVERAGE_SQLITE_DB` / `PCT_LEGAL_COVERAGE_SQLITE_DB` e, di default, sotto `intelligence/legal_coverage.db`
- configurazione PostgreSQL esplicita di piattaforma con `LEGAL_COVERAGE_DB_*` o `PCT_LEGAL_COVERAGE_DB_*`
- nessun riuso automatico di `studio.db`, `TENANT_DATABASE_CONFIG`, PostgreSQL tenant-aware o configurazioni legacy del singolo studio

L'AI usa il runtime locale gia' configurato nel gestionale:

- `LOCAL_AI_BASE_URL`
- `LOCAL_AI_CHAT_MODEL`

## UI admin

- Dashboard: `/admin/copertura-ai`
- Review queue: `/admin/copertura-ai/review`

La dashboard non seleziona piu' uno studio: audit, gap queue, draft, review, publish e API JSON operano sullo stesso archivio condiviso per tutta la piattaforma.
Questo evita che il superadmin debba ripetere la stessa ricerca o pubblicazione per ogni studio quando gli studi diventano 10, 20 o piu'.
La UI mostra il numero di studi attivi coperti e il backend condiviso effettivo, senza propagare `tenant_slug` nei form o nella review.
Quando una sottobranca ha gia' una bozza `generated`, `validated`, `needs_review` o `approved`, la gap queue non la riapre come gap pendente: il lavoro resta nella coda review fino a rifiuto o publish SQL. La generazione draft evita inoltre duplicati su gap storici ancora aperti.
Il publish da dashboard pubblica solo bozze approvate; se non esistono draft `approved`, la UI mostra un avviso operativo e invita ad aprire la coda revisioni invece di dichiarare un riallineamento SQL non avvenuto.
La schermata review autoseleziona la prima bozza disponibile, spiega il flusso da seguire e rende visibile il contesto di retrieval usato per generare il draft.
La review ora espone anche:

- `firma reviewer` obbligatoria per approvazione, rifiuto e publish
- `motivo decisione` obbligatorio per approvare o rifiutare
- `diff bozza -> versione corrente` costruito sulla spec originale generata dall'AI
- `storico revisioni` persistito nel repository SQL
- `ultima decisione`, reviewer, firma e motivazione direttamente nella panoramica draft

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

## Audit review difendibile

La review admin non e' piu' un semplice cambio stato del draft.

Per ogni bozza vengono persistiti:

- spec originale generata dall'AI
- spec corrente salvata dal reviewer
- diff strutturato tra versione iniziale e stato corrente
- reviewer
- firma reviewer
- motivo approvazione o rifiuto
- azione review eseguita (`generated`, `saved`, `approved`, `rejected`, `published`)

Questo rende il flusso piu' difendibile e leggibile anche a posteriori, quando serve ricostruire perche' una procedura e' stata approvata, modificata o respinta.
