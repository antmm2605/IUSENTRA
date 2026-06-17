# Audit SQL fonte di verità e JSON mirror censito - 2026-06-16

## Obiettivo

Chiudere il rischio operativo segnalato dall'utente: i file JSON sotto il tenant non devono più essere trattati come fonte della verità quando lo studio lavora su SQL. Per gli studi in modalità SQL la fonte operativa è `studio.db` o PostgreSQL; i JSON possono esistere solo come mirror rigenerabile, bootstrap controllato, cache, archivio o import/export storico.

## Regola applicata

- Ogni JSON operativo tenant-aware deve avere un presidio SQL in `moduli_dati` e `moduli_json_records`, oppure un repository verticale SQLite/PostgreSQL dedicato.
- Se l'audit trova un JSON operativo non censito, il lavoro resta aperto finché non viene creato il mapping, popolato il database e rieseguito l'audit a freddo.
- Le famiglie dinamiche vengono mappate con nomi modulo stabili derivati dal percorso:
  - `fascicoli/documenti_ai/**/*.json` -> `documenti_ai_file_*`;
  - `fascicoli/importazioni/**/*.json` -> `fascicoli_importazione_*`;
  - `intelligence/lex_dataset/**/*.json` -> `lex_dataset_*`.
- Cache, backup, file corrotti preservati e archivi sono ammessi solo se classificati come non operativi.

## Codice aggiornato

- `pct/storage_migration.py`: esteso il censimento dei JSON monitorati e dei repository operativi; i moduli non verticali vengono indicizzati comunque in `moduli_json_records`.
- `pct/database.py`: il mirror SQL viene popolato per tutti i moduli monitorati passati alla migrazione, non solo per i moduli già presenti nella lista core.
- `pct/tenant.py`: aggiunti path tenant-aware per Documenti AI, importazioni fascicolo, Lex dataset, editor AI, stato PEC cancelleria, repository intelligence/giurisprudenza/legal/telematico, preventivi, termini processuali e template.
- `scripts/audit_tenant_data_structure.py`: l'audit conosce gli stessi path tenant-aware e non segnala più come nascosti i JSON operativi correttamente censiti.
- `web/services/storage_runtime.py`, `web/services/core_runtime.py`, `web/services/tenant_isolation_runtime.py`: aggiornati i path runtime e l'isolamento tenant per gli stessi moduli.
- `tests/test_storage_strategy.py`: aggiunto test che crea JSON operativi noti in un tenant temporaneo, lancia la riparazione e verifica che non restino JSON operativi non censiti.

## Tenant verificato

Tenant locale reale: `tenant-8bf98719c459`.

Esito database locale:

- `studio.db`: presente;
- `moduli_dati`: 436 moduli;
- `moduli_json_records`: 7772 record;
- moduli `documenti_ai_file_%`: 348 moduli, 3132 record;
- moduli `fascicoli_importazione_%`: 1 modulo, 6 record;
- moduli `lex_dataset_%`: 4 moduli, 950 record;
- `studio_local_pack`: 18 record;
- `editor_ai`: 5 record;
- `pec_cancelleria_state`: 2 record;
- `preventivi_repository`: 9 record;
- `termini_processuali`: 7 record;
- `template_repository`: 3 record;
- `telematico_sources_repository`: 3 record.

Il mirror corrotto `agenda/calendar_sync_engine.json` è stato preservato come `agenda/calendar_sync_engine.corrotto-20260617-000241.bak` e rigenerato in UTF-8 valido senza BOM.

## Comandi eseguiti

```powershell
python -m py_compile .\pct\storage_migration.py .\pct\database.py .\pct\tenant.py .\scripts\audit_tenant_data_structure.py .\web\services\storage_runtime.py .\web\services\core_runtime.py .\web\services\tenant_isolation_runtime.py
```

```powershell
python -m pytest tests/test_storage_strategy.py::test_audit_tenant_data_structure_verifica_json_sqlite_postgres tests/test_storage_strategy.py::test_audit_tenant_data_structure_segnala_mirror_json_sql_non_autorevole tests/test_storage_strategy.py::test_audit_tenant_data_structure_repair_risincronizza_mirror_json_sql tests/test_storage_strategy.py::test_audit_tenant_data_structure_json_mancante_non_blocca_sql_autorevole tests/test_storage_strategy.py::test_audit_tenant_data_structure_blocca_json_operativo_nascosto tests/test_storage_strategy.py::test_audit_tenant_data_structure_popola_sql_per_json_operativi_noti tests/test_storage_strategy.py::test_admin_database_react_payload_uses_tenant_backup_dir tests/test_storage_governance.py::test_runtime_storage_crea_sqlite_da_json_senza_fallback_operativo -q --tb=short
```

Esito: 8 test passati.

```powershell
python scripts\audit_tenant_data_structure.py --registry data\tenants.json --repair --json
python scripts\audit_tenant_data_structure.py --registry data\tenants.json --json
```

Esito audit a freddo:

- `ok=true`;
- `source_of_truth=sqlite`;
- `json_authoritative=false`;
- errori: 0;
- warning: 0;
- `hidden_json_summary.operational_untracked=0`;
- JSON classificati come cache/archivio: 242.

Controllo contratto dati generale:

```powershell
python scripts\audit_data_flow_contract.py --registry data\tenants.json --json
```

Esito: `ok=true`, errori 0, warning 0.

## Stato prova reale

La parte dati e script è stata verificata con audit e test automatici mirati. La verifica visiva reale della pagina `/admin/database` deve essere eseguita sulla copia reale `127.0.0.1:8080` dopo rebuild/riavvio Docker locale e poi, dopo commit/push/deploy, anche sul server `https://app.iusentra.it`.

Fino a quella prova visiva materiale il lavoro resta formalmente aperto per la regola anti falso-verde.
