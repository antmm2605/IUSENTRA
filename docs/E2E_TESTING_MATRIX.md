# Matrice Testing End-to-End

## Obiettivo

Portare il testing oltre il singolo modulo e presidiare i flussi che attraversano bootstrap, storage, policy, UI e servizi.

## Flussi presidiati

| Flusso | Sistemi attraversati | Stato | Test di riferimento |
| --- | --- | --- | --- |
| Bootstrap app, login e pannelli admin | Flask factory, auth, template globals, admin | integrato | `tests/test_web_bootstrap.py`, `tests/test_observability_runtime.py` |
| Migrazione JSON -> SQLite con fallback | `pct.database`, tenant storage, auth, runtime storage | nuovo presidio | `tests/test_storage_governance.py` |
| Assistente migrazione dati e cutover tenant | UI admin, `pct.storage_migration_full`, tenant registry, report backup | rinforzato | `tests/test_migration_assistant.py`, `tests/test_storage_postgres_migration.py` |
| Governance prodotto | admin, runtime metrics, auth audit, registry governance | nuovo presidio | `tests/test_product_governance_surface.py` |
| Osservabilita' e failure handling | metriche runtime, provider AI locale, OCR, remediation UI | rinforzato | `tests/test_observability_runtime.py` |
| Copertura AI end-to-end | dashboard admin, repository SQLite/PostgreSQL, review e publish SQL | integrato | `tests/test_legal_coverage_surface.py`, `tests/test_legal_coverage_pipeline.py` |
| Update Intelligence end-to-end | fonti ufficiali, staging, analisi AI, review queue, news | integrato | `tests/test_legal_updates_pipeline.py` |
| Telematico ufficiale | runtime telematico, repository capability, portali | integrato | `tests/test_polisweb.py`, `tests/test_simulazione_deposito.py` |
| Workspace template atti | catalogo built-in, workspace atti, repository template | integrato | `tests/test_template_atti_workspace.py`, `tests/test_template_atti_repository.py` |
| Coerenza UI moduli nuovi | menu admin, copy italiana, route protette, superfici operative | rinforzato | `tests/test_operational_surfaces.py`, `tests/test_web_bootstrap.py` |

## Golden path ufficiali

I golden path non sono piu' solo una lettura architetturale: esiste un comando ufficiale che esegue le suite e persiste un report riusabile anche dalla governance prodotto.

```bash
iusentra golden-path
```

Il report vive sotto `./data/governance/` e viene letto anche da `admin/governance`.

| Golden path | Esito atteso | Suite ufficiali |
| --- | --- | --- |
| Bootstrap, login e superfici admin | pass | `tests/test_web_bootstrap.py`, `tests/test_observability_runtime.py`, `tests/test_operational_surfaces.py` |
| Migrazione tenant, diff e cutover | pass | `tests/test_migration_assistant.py`, `tests/test_storage_postgres_migration.py`, `tests/test_storage_governance.py` |
| Workflow business `cliente -> fascicolo -> parcella -> incasso` | pass | `tests/test_clienti_workflow.py`, `tests/test_workflow_pipeline.py`, `tests/test_workflow_commerciale.py`, `tests/test_economic_dashboard.py`, `tests/test_portale_economici.py` |
| Coverage AI review/publish SQL | pass | `tests/test_legal_coverage_pipeline.py`, `tests/test_legal_coverage_surface.py` |
| Update Intelligence review/publish | pass | `tests/test_legal_updates_pipeline.py`, `tests/test_legal_intelligence.py` |
| Telematico ufficiale | pass | `tests/test_polisweb.py`, `tests/test_telematico_workflow.py`, `tests/test_pdp_penale_workflow.py`, `tests/test_simulazione_deposito.py` |

## Regola

Ogni nuova wave di migrazione o di governance deve arrivare con almeno:

- un test applicativo via `Flask.test_client()`
- un test di consistenza dati
- un test che fallisce in caso di regressione di policy o superficie sensibile

## Cosa significa "chiuso" sui flussi critici

- `Assistente migrazione`: deve eseguire davvero la migrazione, persistire un report, mostrare errori veri e indicare come risolverli.
- `Cutover PostgreSQL`: se la migrazione fallisce o la consistenza non torna, il tenant non deve attivare il backend esterno.
- `Osservabilita'`: non basta un dump tecnico; il pannello deve segnalare i degradi e suggerire il prossimo intervento operativo.
- `Coverage AI` e `Update Intelligence`: le superfici admin devono essere raggiungibili, in italiano, coerenti tra dashboard, review e publish.
