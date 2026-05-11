# Full React final report

Generato: 2026-05-09T17:09:00+02:00

Aggiornamento 2026-05-11T11:00:00+02:00: hotfix 2.215.7 su `/documenti`.
La route non restituisce piu' 404: e' censita nel manifest come
`react_operational_full`, sbloccata dal route gate e servita dalla shell React
con `StudioModulePage` e API `/api/v1/ui/studio-modules/documenti`. Il workspace
collega fascicoli/documenti, catalogo atti, Redazione Atti e ricerca documentale;
il payload filtra record locali con diciture `demo`/`sample` per non esporli in
UI.

Aggiornamento 2026-05-11T02:35:00+02:00: hotfix 2.215.5 sui dettagli
email React. Gli allegati PEC e Email ordinaria mostrano l'azione `Visualizza`
separata da `Apri` e `Scarica`; `Visualizza` usa il link inline in nuova scheda
senza parametro di download forzato.

Aggiornamento 2026-05-11T02:05:00+02:00: tranche 2.215.4 sul flusso
Preventivi/Incarichi/Fascicoli. Il catalogo `Pratiche collegate` e' ora dato
versionato `PST_XSD`; il Preventivo guidato non deduce piu' il CodiceOggetto
dalla tipologia tariffaria e il predeposito PCT blocca la busta se il fascicolo
non contiene un CodiceOggetto ufficiale. `DatiAtto.xml` usa il codice PST nel
nodo `Oggetto`.

Aggiornamento 2026-05-10T00:15:00+02:00: tranche 2.214.0 completata sul
perimetro testi visibili e dettagli email React. Le route
`/email/messaggio/<id>` e `/email-ordinaria/messaggio/<id>` sono nella shell
React con endpoint JSON dedicati. La guardia testi visibili protegge React e
template Flask da diciture tecniche rivolte allo studio. Smoke browser Docker
2.214.0 desktop/mobile su Redazione Atti, Template, Statistiche, Ricerca Legale,
News, Giurisprudenza, Strumenti, Controlli Atti, Sito Studio Contatti, dettagli
email e Database: `#root` presente, nessun overflow orizzontale e nessun termine
vietato visibile.

Tranche architetturale aggiornata: `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` promosse a `react_operational_full`, audit anti-mascheramento senza bridge residui, manifest a 37 full / 1 partial / 19 legacy. `Controlli Atti` usa titolo e payload React reali, mentre le route strumenti usano `StudioModulePage` con payload di modulo studio. Non dichiarare completata la migrazione totale per route legacy ancora giustificate da segreti, export/documenti, sottopercorsi tecnici o portali telematici non ricostruiti.

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
- npm test: passed - Contratti React 2.210.0 verificati dopo lo sblocco delle tre route.
- npm run typecheck: passed - TypeScript confermato dopo `TelematicoSurfacePage` e `StudioModulePage`.
- npm run build: passed - Vite build completata; asset React 2.210.0 generati in `web/static/react`.
- node scripts/react-migration/run-full-react-migration.mjs: passed - Audit, anti-mascheramento, no fake full, route contract e responsive workspace OK.
- Visual smoke Chrome desktop/tablet/mobile: passed - `/deposito/checklist`, `/strumenti-legali`, `/strumenti-operativi` con shell React, titoli visibili, nessun overflow orizzontale e nessun testo tecnico vietato.
- python -m pytest -q tests/test_react_shell.py::test_route_ufficiali_superfici_telematiche_restano_moduli_operativi_legacy_e_checklist_react tests/test_react_shell.py::test_react_superfici_telematiche_api_payload_reale tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short: passed - 4/4 test mirati sulle route/API/gate React.
- npm run typecheck: passed - TypeScript confermato per 2.214.0.
- npm test: passed - Contratti React confermati per 2.214.0.
- npm run build: passed - Build Vite 2.214.0 completata; asset React rigenerati.
- node scripts/react-migration/check-route-gate.mjs: passed - Route gate coerente.
- node scripts/react-migration/check-full-react-route-contract.mjs: passed - Contratto full React coerente; audit anti-mascheramento aggiornato.
- node scripts/react-migration/check-no-fake-react-full.mjs: passed - Nessuna route full mascherata.
- python -m pytest -q tests/test_email_client.py::test_email_dettaglio_visualizza_e_scarica_allegato_salvato tests/test_email_client.py::test_email_ordinaria_dettaglio_usa_repository_smtp_e_allegati_ordinari tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica tests/test_react_shell.py::test_statistiche_react_full_non_espone_fallback_legacy tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short: passed - 6/6 mirati email e React.
- python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short: passed - 8/8 dopo bump 2.214.0.
- docker compose build --no-cache app scheduler-worker ocr-worker: passed - immagini locali ricostruite da zero con package 2.214.0.
- docker compose up -d app scheduler-worker ocr-worker: passed - app, scheduler, OCR e Redis healthy.
- Invoke-WebRequest http://localhost:8080/api/pronto: passed - readiness locale `versione=2.214.0`.
- npm run typecheck: passed - TypeScript confermato per route/sidebar/workspace `/documenti`.
- npm test: passed - Contratti React confermati dopo aggiunta `/documenti`.
- npm run build: passed - Build Vite 2.215.7 completata in 6.15s; asset React rigenerati.
- node scripts/react-migration/check-route-gate.mjs: passed - `/documenti` inclusa nelle route governate consentite.
- node scripts/react-migration/check-full-react-route-contract.mjs: passed - Contratto full React e audit anti-mascheramento aggiornati.
- python -m pytest -q tests/test_react_shell.py::test_react_blocco_finale_studio_admin_completo tests/test_react_shell.py::test_react_blocco_finale_route_reali_e_vista_classica tests/test_react_shell.py::test_route_gate_non_promuove_moduli_studio_telematico_admin_incompleti tests/test_react_shell.py::test_react_migration_matrice_completa_route_api_e_card_operative --tb=short: passed - 4/4 mirati route, shell, gate e payload.
- docker compose build --no-cache app scheduler-worker ocr-worker: passed - immagini locali 2.215.7 ricostruite dopo il filtro Documenti.
- docker compose up -d --no-build redis app scheduler-worker ocr-worker nginx: passed - app, scheduler, OCR e Redis healthy.
- Browser Playwright headless `/documenti`: passed - desktop 352.9 ms, tablet 210.8 ms, mobile 167.9 ms a contenuto visibile, nessun overflow e nessun testo tecnico visibile.
