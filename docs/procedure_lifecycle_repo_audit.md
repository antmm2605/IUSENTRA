# Audit repository - Procedure Lifecycle Knowledge Pipeline

Aggiornato: 21 maggio 2026.

Stato: inventario iniziale eseguito prima delle modifiche codice della tranche "IUSENTRA Procedure Lifecycle Knowledge Pipeline".

## 1. File letti

Documentazione e policy consultate:

- `README.md`
- `AGENTS.md` ricevuto nel contesto operativo
- `docs/COMMIT_PUSH_REQUIRED_GATES.md`
- `docs/ci-cd-gates.md`
- `docs/test-plan-app-v2.md`
- `docs/index.md`
- `docs/CENTRO_FONTI_UFFICIALI_LEX.md`
- `docs/LEX_SOURCE_POLICY_SYSTEM.md`
- `docs/PORTALI_ACQUISIZIONE_GUIDATA.md`
- `docs/LOCAL_PEC_CONNECTOR.md`
- `docs/TEMPLATE_ATTI_CATALOGO_MASTER.md`
- `docs/security-rbac-tenant-isolation.md`
- `docs/OBSERVABILITY_AUDIT_PRODUCT.md`
- `docs/procedure_lifecycle_knowledge_pipeline.md`
- inventario `docs/specs/ministero/`, inclusi schemi e WSDL locali per PCT/PST, SIGP, ReGIndE, Cassazione, PLO e pagamenti telematici.

Fonti interne lette:

- `pct/data/pratiche_collegate_catalog.json`
- `pct/data/legal_sources_registry.json`
- `lex/research/source_policy/sources_registry.yaml`

Moduli letti:

- `pct/procedure_inventory_importer.py`
- `pct/procedure_xsd_mapper.py`
- `pct/procedure_source_research.py`
- `pct/procedure_knowledge_pipeline.py`
- `pct/procedure_lifecycle.py`
- `pct/procedure_lifecycle_repository.py`
- `pct/digital_signature_workflow.py`
- `pct/telematic_deposit_workflow.py`
- `pct/post_acceptance_obligations.py`
- `pct/notification_workflow.py`
- `pct/evidence_vault.py`
- `pct/procedure_coverage_ext.py`
- `pct/legal_platform_catalog.py`
- `pct/legal_platform_seed.py`
- `pct/legal_coverage_sqlite_repository.py`
- `pct/deposito_guidato.py`
- `pct/telematico_repository.py`
- `pct/template_deposit_rules.py`
- `pct/busta.py`
- `pct/practice_engine/*` tramite ricerca testuale e lettura dei riferimenti principali in README/test.

Migration e configurazioni lette:

- `pct/sql/20260417_legal_coverage_pipeline.sql`
- `pct/sql/20260417_legal_taxonomy_operational_tables.sql`
- `pct/sql/20260504_practice_engine.sql`
- `pct/sql/20260520_procedure_lifecycle_knowledge_pipeline.sql`
- `config/coverage-procedure-lifecycle.ini`

Test letti:

- `tests/procedure_pipeline_support.py`
- `tests/test_procedure_inventory_importer.py`
- `tests/test_procedure_xsd_mapper.py`
- `tests/test_procedure_source_research.py`
- `tests/test_procedure_knowledge_pipeline.py`
- `tests/test_procedure_lifecycle.py`
- `tests/test_procedure_lifecycle_repository.py`
- `tests/test_digital_signature_workflow.py`
- `tests/test_telematic_deposit_workflow.py`
- `tests/test_post_acceptance_obligations.py`
- `tests/test_notification_workflow.py`
- `tests/test_evidence_vault.py`
- `tests/test_procedure_coverage_ext.py`
- test Practice Engine, Local Signer, portali guidati e Template Atti individuati con `rg`.

Ricerche obbligatorie eseguite con `rg`:

- `practice_engine`, `deposito`, `deposit`, `ricevuta`, `ricevute`, `accettazione`, `rifiuto`
- `DatiAtto`, `busta`, `firma`, `signer`, `Local Signer`
- `notifica`, `notifiche`, `relata`, `proof`, `evidence`
- `XSD`, `PST`, `SIGP`, `UNEP`, `Cassazione`, `ReGIndE`, `PEC`
- `Lex`, `source_policy`, `coverage`, `gap_queue`, `template_atti`, `audit`

## 2. Moduli esistenti riutilizzati

- `pct/procedure_inventory_importer.py`: importer PST/XSD già presente. Legge il catalogo, preserva gli item senza `children`, calcola `import_hash`, supporta dry-run/apply e usa il repository auditato.
- `pct/procedure_xsd_mapper.py`: mapper XSD -> procedura già presente. Usa `PROCEDURE_REGISTRY` e genera mapping conservativi `needs_review`.
- `pct/procedure_source_research.py`: piano multi-fonte governato già presente. Usa fonti tecniche/ufficiali e crea evidenze sintetiche senza scraping.
- `pct/procedure_knowledge_pipeline.py`: validazione fonti multi-sorgente e knowledge card originali già presente.
- `pct/procedure_lifecycle.py`: state machine e template lifecycle già presenti, con transizioni bloccanti su firma, deposito, notifica, prova e chiusura.
- `pct/procedure_lifecycle_repository.py`: repository SQLite, tabelle, audit deterministico e gap queue già presenti.
- `pct/digital_signature_workflow.py`: workflow firma digitale già presente; non firma realmente e blocca credenziali/PIN nei payload.
- `pct/telematic_deposit_workflow.py`: workflow deposito telematico già presente; usa stub/connettore, ricevute e stati.
- `pct/post_acceptance_obligations.py`: obblighi successivi già presenti per 010/050, 030, cautelari, possessorie e unknown.
- `pct/notification_workflow.py`: workflow notifica, relata, prova e deposito prova già presente.
- `pct/evidence_vault.py`: registro evidenze e hash già presente.
- `pct/procedure_coverage_ext.py`: coverage estesa e gap queue già presenti.
- `pct/practice_engine/*`: motore pratica esistente da rispettare; gestisce profili, predeposito, ricevute, evidence pack e blocchi di stato.
- `pct/deposito_guidato.py`, `pct/telematico_repository.py`, `pct/template_deposit_rules.py`, `pct/busta.py`: moduli deposito/busta già esistenti, da non bypassare.
- `lex/research/source_policy/*` e documenti Lex Source Policy: sistema fonte già esistente, da non aggirare.
- Local Signer e portali guidati in `web/bootstrap/*`, `web/services/telematico_runtime.py`, `web/services/local_pec_runtime.py`: canale locale già esistente per firma/PEC/portali.

## 3. Moduli da non duplicare

Non vanno creati sistemi paralleli per:

- Practice Engine: `pct/practice_engine/*`
- deposito guidato e busta: `pct/deposito_guidato.py`, `pct/busta.py`, `pct/template_deposit_rules.py`
- repository telematico: `pct/telematico_repository.py`
- fonti Lex: `lex/research/source_policy/*`, `pct/data/legal_sources_registry.json`
- template atti: `pct/template_atti.py`, `pct/template_atti_repository.py`, `pct/template_atti_master_catalog.py`, `pct/template_atti_lex_service.py`
- firma reale/PEC locale: Local Signer e Local PEC runtime già presenti
- audit prodotto generale: moduli e documenti già presenti in `audit/`, `web/services/observability_runtime.py`, `docs/OBSERVABILITY_AUDIT_PRODUCT.md`

Conflitto rilevato: i nomi richiesti `pct/procedure_source_evidence.py`, `pct/procedure_knowledge_cards.py`, `pct/procedure_lifecycle_templates.py` e `pct/procedure_workflow_runtime.py` non esistono come file separati, ma la responsabilità è già implementata in `pct/procedure_knowledge_pipeline.py`, `pct/procedure_lifecycle.py` e `pct/procedure_lifecycle_repository.py`. La modifica corretta è estendere questi moduli e, se serve una superficie importabile con quei nomi, creare solo façade sottili senza duplicare logica.

## 4. Tabelle già presenti

La migration esistente `pct/sql/20260520_procedure_lifecycle_knowledge_pipeline.sql` crea già le tabelle richieste:

- `legal_ministerial_xsd_objects`
- `legal_procedure_xsd_map`
- `legal_procedure_source_evidence`
- `procedure_knowledge_cards`
- `procedure_lifecycle_templates`
- `procedure_lifecycle_steps`
- `fascicolo_workflow_instances`
- `fascicolo_workflow_events`
- `digital_signature_events`
- `telematic_deposit_packages`
- `telematic_deposit_receipts`
- `post_acceptance_obligations`
- `notification_events`
- `evidence_documents`
- `procedure_audit_log`

Tabelle collegate già esistenti:

- `legal_procedures` da `pct/sql/20260417_legal_taxonomy_operational_tables.sql`
- `coverage_gap_queue` da `pct/sql/20260417_legal_coverage_pipeline.sql`
- tabelle/stores Practice Engine da `pct/sql/20260504_practice_engine.sql` e storage tenant-aware `fascicoli/practice_engine/*`

Gap rilevato: l'ID migration richiesto dalla tranche è `pct/sql/20260520_xsd_procedure_lifecycle_knowledge.sql`; il file equivalente già presente ha nome `20260520_procedure_lifecycle_knowledge_pipeline.sql`. La correzione deve rendere canonico l'ID richiesto senza perdere compatibilità con la migration già introdotta.

## 5. Endpoint o flussi già presenti

Flussi già presenti e da riusare:

- Practice Engine/Regia Operativa: bridge React e runtime in `web/services/react_practice_engine_bridge.py`, `web/services/core_runtime.py`, storage tenant-aware in `pct/tenant.py`.
- Portali guidati: `web/bootstrap/portali_acquisizione_routes.py` con acquisizione, preview, import, precheck deposito, preparazione, assistant, ricevute e finalizzazione governata.
- PolisWeb/PDP/PAT/SIGIT/SIGP: route in `web/bootstrap/*` e runtime telematico.
- Firma digitale/Local Signer: `web/bootstrap/fascicoli_signature_routes.py`, `web/bootstrap/telematico_local_signer_routes.py`, `web/services/local_signer_release.py`.
- PEC locale: `web/services/local_pec_runtime.py` e documentazione `docs/LOCAL_PEC_CONNECTOR.md`.
- Template Atti/Lex: `lex/retrieval/sources/template_atti.py`, `pct/template_atti_lex_service.py`, `lex/tools/template_atti_tool.py`.
- Coverage e gap: `pct/legal_coverage_sqlite_repository.py`, `pct/procedure_coverage_ext.py`.

Non è stato creato alcun nuovo endpoint operativo nella tranche: i nuovi elementi restano infrastrutturali/domain layer e quindi non introducono superfici HTTP prive di tenant, RBAC e audit.

## 6. Test già presenti

La suite mirata già copre:

- migration idempotente e audit repository;
- import XSD con `children`;
- item senza `children`;
- dry-run senza scrittura dati;
- apply idempotente;
- CLI dry-run/apply;
- mapping prefissi `010`, `050`, `030`, cautelari e `020`;
- mapping incerto `needs_review`;
- fonte professionale senza principio e quote oltre 500 caratteri;
- fonte ufficiale valida;
- fonte interna con PII e flag privacy;
- scheda non pubblicabile senza fonte ufficiale;
- lifecycle template e transizioni;
- blocchi su `FIRMATO`, `DEPOSITO_ACCETTATO`, `NOTIFICA_EFFETTUATA`, `PROVA_NOTIFICA_ACQUISITA`, `CHIUSA`;
- deposito READY bloccato senza firma verificata;
- `OFFICE_ACCEPTED` bloccato senza ricevuta;
- obblighi post-accettazione per `010`;
- notifica e deposito prova;
- coverage estesa e gap;
- evidence vault.

Gap test rilevati:

- CLI obbligatoria della tranche deve funzionare anche senza `--catalog`.
- Il report `artifacts/procedure-lifecycle/xsd_import_report.json` deve essere generato.
- L'audit deve mascherare dati sensibili e path prima di salvare `before_json`, `after_json` e `diff_json`.
- Deve essere coperto il nuovo ID migration richiesto.
- Devono essere esposte enumerazioni Python esplicite per stati firma/deposito/lifecycle/gap.

## 7. Gap reali

1. Migration richiesta con nome esatto assente: esiste una migration equivalente ma con ID diverso.
2. CLI importer richiede `--catalog`, mentre la tranche chiede i comandi senza parametro catalogo.
3. Il report JSON obbligatorio dell'import non viene scritto automaticamente in `artifacts/procedure-lifecycle/xsd_import_report.json`.
4. Audit deterministico presente, ma serve mascheramento applicativo esplicito di PIN/password/token/cookie, path, email, codice fiscale, IBAN e telefono.
5. Stati presenti come tuple/dizionari, ma non tutte le famiglie hanno enumerazioni Python nominali.
6. Tenant-safety supportata dai flussi di runtime esistenti, ma le nuove tabelle procedurali devono poter conservare `tenant_id` opzionale senza rompere SQLite esistente.
7. I moduli richiesti come nomi separati per source evidence, knowledge cards, lifecycle templates e workflow runtime non esistono; la logica è già in moduli equivalenti e va esposta senza duplicazione se necessario.

## 8. Rischi di duplicazione

- Creare un nuovo practice engine parallelo romperebbe il workflow fascicolo già governato.
- Creare nuove tabelle deposito/ricevute con altri nomi renderebbe ambiguo lo stato `OFFICE_ACCEPTED` e violerebbe la regola "nessun deposito accettato senza ricevuta".
- Creare un motore fonti separato da Lex Source Policy produrrebbe riferimenti non governati.
- Creare un flusso firma reale nel server aggirerebbe Local Signer.
- Creare endpoint operativi nuovi senza RBAC/tenant/audit violerebbe le policy di sicurezza.
- Copiare testo da fonti professionali dentro schede conoscitive violerebbe la regola anti-copia.

## 9. Piano implementativo definitivo

1. Rendere canonico il file migration richiesto `pct/sql/20260520_xsd_procedure_lifecycle_knowledge.sql`, mantenendo compatibilità con il file precedente.
2. Estendere `ProcedureLifecycleRepository.ensure_extended_schema()` con migrazione colonne idempotente per `tenant_id` e con audit masking prima della scrittura.
3. Aggiungere enumerazioni Python per stati lifecycle, step type, firma, deposito, ricevute, notifica, obblighi e gap.
4. Estendere `pct/procedure_inventory_importer.py` con catalogo di default, report JSON obbligatorio e CLI compatibile con i due comandi richiesti.
5. Integrare gap queue e audit per le azioni critiche mancanti senza duplicare repository.
6. Creare, se necessario, façade sottili con i nomi richiesti, che reimportano le funzioni esistenti senza logica parallela.
7. Aggiornare test mirati per migration ID, CLI senza `--catalog`, report JSON, mascheramento audit, enumerazioni e tenant columns.
8. Aggiornare `docs/procedure_lifecycle_knowledge_pipeline.md`, `docs/index.md`, `docs/ci-cd-gates.md`, `docs/test-plan-app-v2.md`, `CHANGELOG.md` e report pytest React richiesti dalle regole repo.
9. Eseguire gate mirati, coverage dei nuovi moduli, compile, commit, push dei branch gemelli, igiene repository e deploy Hetzner.

## 10. Motivazione di ogni nuovo file da creare

- `docs/procedure_lifecycle_repo_audit.md`: richiesto dalla Fase 0 come audit iniziale obbligatorio prima del codice.
- `pct/sql/20260520_xsd_procedure_lifecycle_knowledge.sql`: richiesto dalla Fase 2 come ID migration canonico; deve estendere lo schema esistente in modo idempotente senza creare tabelle parallele.
- `artifacts/procedure-lifecycle/xsd_import_report.json`: richiesto dalla Fase 3 come report obbligatorio dell'import XSD.
- `pct/procedure_source_evidence.py`: solo façade di compatibilità se introdotto; motiva il nome richiesto senza duplicare `pct/procedure_knowledge_pipeline.py`.
- `pct/procedure_knowledge_cards.py`: solo façade di compatibilità se introdotto; motiva il nome richiesto senza duplicare `pct/procedure_knowledge_pipeline.py`.
- `pct/procedure_lifecycle_templates.py`: solo façade di compatibilità se introdotto; motiva il nome richiesto senza duplicare `pct/procedure_lifecycle.py`.
- `pct/procedure_workflow_runtime.py`: solo façade di compatibilità se introdotto; motiva il nome richiesto senza duplicare `pct/procedure_lifecycle.py`.

## Stop condition applicata

L'inventario ha rilevato moduli già equivalenti per quasi tutte le funzioni richieste. La tranche non deve creare un sistema parallelo: le modifiche devono estendere il repository e i moduli esistenti, correggendo i gap reali sopra elencati.
