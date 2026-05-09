# Full React final report

Generato: 2026-05-09T13:03:44+02:00

Tranche architetturale aggiornata: `/statistiche` promossa a `react_operational_full`, audit anti-mascheramento senza bridge residui, manifest a 27 full / 1 partial / 25 legacy. Durante il gate Docker locale sono stati corretti anche il fallback runtime della posta ordinaria e lo startup multi-tenant: `email/ordinaria.json` non deve piu' essere creato nel repository, ma sotto `/data/email/ordinaria.json`, e `sync_user_directory` non rilancia reconcile storage pesanti nel worker HTTP. Non dichiarare completata la migrazione totale per route legacy ancora giustificate da segreti, export/documenti, impostazioni e portali telematici.

## Test

- python -m pytest -q: timeout - Interrotto dal timeout locale dopo circa 45 minuti; nessun verde completo dichiarabile.
- npm test: passed - Contratti React verificati.
- npm run typecheck: passed - tsc --noEmit completato.
- npm run build: passed - Vite build completata; asset generati in web/static/react.
- node scripts/react-migration/run-full-react-migration.mjs: passed - Audit, anti-mascheramento e check Full React passati.
- node scripts/react-migration/run-legal-ui-checks.mjs: passed - Check UI legale, responsive e anti-Bootstrap passati.
- node scripts/react-migration/check-route-gate.mjs: passed - Manifest e gate route allineati allo stato corrente.
- python -m pytest -q tests/test_react_shell.py::test_statistiche_react_full_non_espone_fallback_legacy: passed - Regressione mirata su `/statistiche` full senza fallback legacy.
- python tools/check_repo_governance.py: passed - Governance repo verde; `web/app.py` 40 righe e 0 route inline.
- python -m pytest -q lex/tests/unit/test_router.py lex/tests/test_gateway_router.py tests/test_lex_sentenze_clienti_fix.py --tb=short: passed - 32 test Lex passati dopo ripristino regex accentate cliente.
- docker compose build --no-cache app: passed - Immagine locale 2.208.0 ricostruita da zero.
- python -m pytest -q tests/test_database.py::test_create_app_bootstrap_moduli_monitorati tests/test_web_bootstrap.py::test_create_app_email_ordinaria_deriva_da_email_db_runtime tests/test_web_bootstrap.py::test_docker_compose_prevede_runtime_ollama_sulla_stessa_macchina --tb=short: passed - 3 test sul fallback email ordinaria runtime e bootstrap dati.
- python -m pytest -q tests/test_storage_strategy.py::test_sync_user_directory_indicizza_utenti_tenant_sqlite tests/test_storage_strategy.py::test_sync_user_directory_puo_saltare_reconcile_pesante tests/test_web_bootstrap.py::test_runtime_bundle_startup_sync_directory_non_rilancia_reconcile_pesante --tb=short: passed - 3 test su directory utenti tenant e startup web senza reconcile pesante.
- docker compose up -d --no-build redis app nginx: passed - Dopo rebuild: `iusentra-app` healthy, `nginx` avviato, `/api/pronto` 200 con versione `2.208.0`.
