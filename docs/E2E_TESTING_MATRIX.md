# Matrice Testing End-to-End

## Obiettivo

Portare il testing oltre il singolo modulo e presidiare i flussi che attraversano bootstrap, storage, policy, UI e servizi.

## Flussi presidiati

| Flusso | Sistemi attraversati | Stato | Test di riferimento |
| --- | --- | --- | --- |
| Bootstrap app, login e pannelli admin | Flask factory, auth, template globals, admin | integrato | `tests/test_web_bootstrap.py`, `tests/test_observability_runtime.py` |
| Migrazione JSON -> SQLite con fallback | `pct.database`, tenant storage, auth, runtime storage | nuovo presidio | `tests/test_storage_governance.py` |
| Governance prodotto | admin, runtime metrics, auth audit, registry governance | nuovo presidio | `tests/test_product_governance_surface.py` |
| Telematico ufficiale | runtime telematico, repository capability, portali | integrato | `tests/test_polisweb.py`, `tests/test_simulazione_deposito.py` |
| Workspace template atti | catalogo built-in, workspace atti, repository template | integrato | `tests/test_template_atti_workspace.py`, `tests/test_template_atti_repository.py` |

## Regola

Ogni nuova wave di migrazione o di governance deve arrivare con almeno:

- un test applicativo via `Flask.test_client()`
- un test di consistenza dati
- un test che fallisce in caso di regressione di policy o superficie sensibile
