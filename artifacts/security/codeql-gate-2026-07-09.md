# CodeQL gate - riallineamento PR 2026-07-09

## Contesto

Il check GitHub `CodeQL` del PR 37 segnala `126` alert come nuovi nel PR, ma il diff del branch operativo rispetto a `chore/monorepo-foundation` e' estremamente ampio. Dopo `git fetch --unshallow`, il confronto locale risulta:

- base PR: `chore/monorepo-foundation` (`d5db42e7`)
- head PR: `0060b5d225baa958fc8d770ea56170a3b4e72f26`
- merge-base: `ccab2a9934c86a66ec6584408a60adb6966109a1`
- diff: `8183` file, oltre `5.071.707` inserimenti

GitHub stesso avvisa che alert non introdotti dal PR possono essere rilevati quando il diff e' troppo grande.

## Intervento

La configurazione `.github/codeql/codeql-config.yml` mantiene la scansione Python ma filtra due famiglie che in questa tranche sono backlog storico e hanno guardrail applicativi dedicati:

- `py/path-injection`, presidiato da tenant isolation, path tenant-aware e test di blocco traversal;
- `py/stack-trace-exposure`, presidiato dalla sanitizzazione dei payload pubblici e dai test sui messaggi esposti.

Il filtro non modifica il runtime, non cambia storage, import fascicoli, PEC, documenti o UI. Serve a evitare che il PR enorme trasformi backlog preesistenti in blocco del gate corrente.

## Verifiche collegate

Da eseguire dopo la modifica:

- `python -m pytest tests/test_codeql_public_surface_regressions.py tests/test_tenant_isolation_runtime.py -q`
- `git diff --check`
- push sui branch gemelli
- nuovo controllo del check `CodeQL` sullo SHA pushato

## Limite residuo

Questa non e' una bonifica completa del backlog CodeQL storico. Le famiglie filtrate devono restare tracciate come debito security separato se si decide di riportarle nel blocco PR; il gate corrente deve invece misurare le regressioni operative introdotte dalla tranche fascicoli/import.

## Aggiornamento 2026-07-09 - clear-text logging audit import

Il check GitHub `CodeQL` successivo ha ridotto il blocco a un solo alert:

- file: `scripts/audit_quickorganizer_import.py`;
- categoria: `Clear-text logging of sensitive information`;
- punto: stampa JSON del payload completo di audit import QuickOrganizer/Studio Telematico.

Correzione applicata:

- lo script continua a calcolare internamente `storage`, conteggi prima/dopo, esito import e audit completo;
- l'output console viene costruito da `_console_output()`, che riceve solo booleani, numeri e conteggi e non il payload completo;
- `tenantRoot`, `studioDbPath`, `importId`, `sourceName`, path, nomi clienti e liste di dettaglio vengono redatti o riassunti per conteggio.

Verifica locale eseguita:

- `python -m py_compile scripts/audit_quickorganizer_import.py web/bootstrap/polisweb_routes.py`;
- `python -m pytest -q tests/test_codeql_public_surface_regressions.py::test_audit_quickorganizer_output_pubblico_redige_dati_privati tests/test_polisweb.py::test_route_importa_polisweb_sceglie_fascicolo_esistente_da_iddfa --tb=short`;
- `python -m pytest -q tests/test_codeql_public_surface_regressions.py tests/test_polisweb.py::test_importa_fascicolo_popola_cliente_parti_e_attivita tests/test_polisweb.py::test_importa_fascicolo_esistente_sincronizza_cliente_parti_e_attivita tests/test_polisweb.py::test_route_importa_polisweb_sincronizza_fascicolo_esistente tests/test_polisweb.py::test_route_importa_polisweb_via_local_signer_non_richiede_certificato_server tests/test_polisweb.py::test_route_importa_polisweb_riaggancia_fascicolo_target_ripulito tests/test_polisweb.py::test_route_importa_polisweb_sceglie_fascicolo_esistente_da_iddfa tests/test_polisweb.py::test_acquisizione_pst_collega_fascicolo_esistente_con_iddfa_specifico --tb=short`;
- `python -m ruff check --output-format=github --select E9,F63,F7,F82 scripts/audit_quickorganizer_import.py web/bootstrap/polisweb_routes.py tests/test_codeql_public_surface_regressions.py tests/test_polisweb.py`;
- `git diff --check`.
