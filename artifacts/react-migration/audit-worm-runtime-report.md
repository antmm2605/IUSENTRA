# Audit WORM runtime - 2026-05-13

## Problema risolto

L'endpoint `/registro/bundle/fascicolo/<id>` rispondeva con
`audit_config_error` quando mancavano WORM e firma. Il comportamento fail-closed
resta corretto, ma ora l'ambiente locale e Hetzner hanno una configurazione
operativa reale: MinIO S3-compatible con Object Lock, Postgres audit dedicato e
firma JWS con chiave fuori repository.

## Implementazione

- Profilo Docker `audit-worm` con servizi `audit-worm`, `audit-worm-init` e
  `audit-postgres`.
- Script locale `scripts/configure_audit_worm_local.ps1` per generare
  credenziali runtime, chiave JWS e variabili `.env` senza committare segreti.
- Script Hetzner `deploy/hetzner/configure_audit_worm.sh` per generare lo stesso
  presidio sotto `/opt/iusentra/data`.
- Diagnostica `/registro/status` e payload `audit` sugli errori di
  configurazione, senza valori segreti.
- Il dettaglio fascicolo espone il bundle solo quando WORM/firma sono pronti.
- Corretto l'indice Postgres: `snapshot_id` opzionale viene scritto come `NULL`,
  non come stringa vuota.

## Verifiche eseguite

```text
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\configure_audit_worm_local.ps1
docker compose --profile audit-worm up -d --build audit-postgres audit-worm audit-worm-init redis app
docker exec iusentra-audit-worm mc stat local/iusentra-audit-worm
docker exec iusentra-app python scripts/audit_smoke_test.py --tenant-id tenant-8bf98719c459 --fascicolo-id AUDIT-SMOKE-OK --idempotency-key audit-smoke-local-worm-ok-20260513
python scripts\verify_audit.py verify-bundle data\audit\audit-smoke-ok-bundle.zip
python -m pytest -q tests/test_audit_routes.py tests/test_audit_emit.py tests/test_audit_worm.py tests/test_audit_bundle.py --tb=short
python -m pytest -q tests/test_local_signer.py::test_local_signer_dist_allineato_a_sorgente_e_installer_versionati tests/test_local_signer.py::test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download tests/test_local_signer.py::test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import --tb=short
python tools\sync_packaging_files.py --check
python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short
npm --prefix frontend run typecheck
npm --prefix frontend run test
```

Esito: bundle verificato offline con output `VALIDO`; WORM con versioning e
retention `COMPLIANCE` 10 anni; app locale healthy.
