# Fase 3 — Storage e outbox: audit iniziale

**Stato:** completata e rilasciata. Implementazione, guardrail, prova materiale locale, 15 golden journey, CI completa, push gemello e deploy Hetzner sono verificati.

## Obiettivo e confini

La fase deve rendere SQL la fonte operativa per i domini P0, mantenendo i JSON soltanto come mirror o bootstrap dichiarato. Deve inoltre introdurre un outbox transazionale, idempotente e tenant-aware per le conseguenze esterne o asincrone. Non introduce nuovi invii PEC, firme, pagamenti o automazioni decisive.

## Evidenze rilevate

* `pct/data_flow_contract.py` censisce route React, API, path tenant-aware, moduli JSON, tabelle SQLite/PostgreSQL e repository per le aree di prodotto.
* `pct/storage_migration_full.py` conosce già le tabelle core e le migrazioni tenant-aware JSON → SQLite → PostgreSQL; conserva report di migrazione.
* `scripts/audit_data_flow_contract.py` verifica mirror e tabelle core, ma non esprime ancora per dominio una policy unica di shadow-read, dual-write, riconciliazione e cutover.
* I repository verticali sono già presenti per telematico, preventivi, procedure, notifiche PEC, document intelligence, legal intelligence e workspace; non vanno sostituiti con un repository generico.

## Decisioni vincolanti

1. Nessuna lettura runtime dei domini SQL potrà tornare silenziosamente al JSON: SQLite/PostgreSQL assente, non migrato o incoerente deve produrre un errore operativo chiaro.
2. Il JSON resta mirror rigenerabile o bootstrap esplicito, mai base per conteggi, audit conclusivi o decisioni dopo il cutover SQL.
3. SQLite e PostgreSQL ricevono lo stesso schema, indici, vincoli e contratto di repository; ogni migrazione avrà prova di parità.
4. L'outbox viene scritto nella stessa transazione della mutazione business. Ogni messaggio include tenant, aggregate, versione, tipo, idempotency key, correlation/causation ID, payload minimizzato, stato e tentativi.
5. Il dispatcher non esegue azioni legali autonome: consegna solo eventi interni o integrazioni già autorizzate, con retry controllato, audit e dead-letter osservabile.
6. Shadow-read, dual-write e riconciliazione sono strumenti temporanei, espliciti e per dominio; il loro termine e rollback sono documentati.

## Sequenza di implementazione

1. Inventario eseguibile dei domini P0 e policy di ownership/cutover.
2. Schema outbox SQLite/PostgreSQL, repository e transazione atomica.
3. Guardrail source-of-truth, shadow-read e report di riconciliazione senza scansioni ricorsive runtime.
4. API JSON amministrativa read-only per il Data Consistency Center e vista React solo se i dati sono reali e autorizzati.
5. Test SQLite/PostgreSQL, tenant A/B, idempotenza, rollback, mancata consegna e regressione dei 15 golden journey interessati.
6. Docker locale no-cache, prova browser reale, performance, commit, CI, deploy Hetzner e verifica diretta.

## Criteri di accettazione

La fase non sarà chiusa se anche un solo dominio P0 legge dal JSON come fallback nascosto, se SQLite/PostgreSQL divergono, se l'outbox può duplicare o perdere un evento, se una mutazione manca di tenant/audit/idempotenza o se la console mostra dati non autorizzati.

## Implementazione eseguita

1. `pct/data_consistency.py` definisce l'inventario eseguibile dei sette domini P0: identità/audit, anagrafiche, fascicoli, agenda, scadenze, preventivi/incarichi ed eventi. La lettura è limitata a tabelle SQL dichiarate; non calcola alcun conteggio da JSON e non esegue scansioni del filesystem.
2. `pct/transactional_outbox.py` fornisce il DDL condiviso SQLite/PostgreSQL e l'accodamento senza commit implicito. Ogni evento richiede tenant, aggregate, versione positiva, tipo, chiave di idempotenza, attore, correlation/causation ID e payload minimizzato. Il vincolo univoco impedisce la duplicazione e il chiamante mantiene commit/rollback nella stessa transazione business.
3. `pct/storage.py` e `pct/storage_postgres.py` applicano lo stesso schema, indici e upgrade `actor_id`; `pct/storage_migration.py` trasferisce integralmente l'outbox tra backend mantenendo identificativi e chiavi di idempotenza.
4. `web/services/react_data_consistency_bridge.py`, la route JSON protetta `/api/v1/ui/amministrazione/consistenza-dati` e la vista React `AmministrazionePage.tsx?tab=consistenza-dati` espongono solo conteggi aggregati e stati del backend SQL del tenant corrente. Il permesso richiesto è `admin.configura`; il payload non espone record, path tenant o mirror.
5. La console dichiara in modo verificabile `scritture: nessuna`, `scansione JSON: assente` e `fallback JSON: assente`. Gli eventi outbox restano registrazioni interne: nessun dispatcher di PEC, firma, deposito, pagamento o altra azione esterna è stato introdotto.

## Guardrail automatici eseguiti prima della prova reale

* `tests/test_transactional_outbox.py`: idempotenza, rollback atomico, obbligatorietà dell'attore, migrazione e snapshot SQL senza JSON.
* `tests/test_data_consistency_react_api.py`: sessione, RBAC `admin.configura`, backend SQLite del tenant, assenza di fallback/scansione JSON e route React.
* `tests/test_product_readiness_react_api.py`, `tests/test_data_flow_contract.py`, `tests/test_storage_governance.py`, `tests/test_repository_sql_parity.py`, `tests/test_storage_postgres_migration.py`: regressione mirata su contratti dati, storage e parità repository.
* `npm run typecheck` e `npm run test` nella cartella `frontend`: contratti React, policy UI, App V2, copertura superfici e assistente vocale.

## Limiti governati

Il dispatcher outbox e le politiche di consegna/retry sono deliberatamente separati: non sono prerequisito per registrare l'evento atomico e non possono essere usati per inviare atti, PEC, firme o pagamenti dal server. Ogni futura integrazione dovrà dichiarare consumer, retry, dead-letter, audit, idempotenza esterna e prova autorizzata.

## Prova materiale locale del 23/08/2026

La copia Docker reale su `http://127.0.0.1:8080` è stata ricostruita senza cache alla versione `2.278.71`; `app`, `scheduler-worker` e `ocr-worker` sono healthy e `/api/pronto` risponde `ok=true`, timezone `Europe/Rome`, versione `2.278.71`.

Nel browser integrato autenticato è stata aperta la route React `/amministrazione?tab=consistenza-dati` e sono stati osservati dati reali del tenant corrente: fonte `sqlite`, sette domini P0 leggibili, 24 clienti, 10 fascicoli, 361 appuntamenti, 187 scadenze e outbox inizialmente vuota. Sono stati cliccati materialmente `Aggiorna controllo`, il dettaglio `Fascicoli` e il dettaglio `Eventi transazionali`; il refresh ha mantenuto la fonte SQL e l'assenza del fallback, mentre il focus tastiera sul dettaglio è rimasto leggibile. La pagina è stata percorsa dall'inizio alla fine su desktop, tablet 768×1024 e mobile 390×844.

Durante la prima prova mobile un badge di stato poteva sovrapporsi al nome interno di repository molto lungo. Il difetto è stato corretto con impilamento della sintesi su mobile e `overflow-wrap` sul testo lungo; dopo una seconda build Docker senza cache e un nuovo click reale, tutti i badge `presidiato`, inclusi `Scadenze e termini` ed `Eventi transazionali`, risultano su righe distinte, leggibili e senza overflow orizzontale. La console browser non ha registrato errori JavaScript.

## Controlli eseguiti prima del rilascio

* `pytest tests/test_transactional_outbox.py tests/test_data_consistency_react_api.py tests/test_product_readiness_react_api.py -q`: superato.
* `pytest tests/test_data_flow_contract.py tests/test_storage_governance.py tests/test_repository_sql_parity.py tests/test_storage_postgres_migration.py -q`: superato.
* `scripts/audit_data_flow_contract.py --registry data/tenants.json --json`: superato sul tenant locale reale; `studio.db` integro e leggibile, con source of truth SQL e mirror verificato soltanto come mirror.
* `npm run typecheck` e `npm run test` in `frontend`: superati; contratti React, accessibilità/governance, App V2 e copertura UI sono risultati conformi.
* I gate locali di pre-push (`sync_packaging_files`, contratti API/App V2, Ruff e whitespace) sono superati dopo la rigenerazione di OpenAPI, mappa endpoint e inventario test.
* Misurazione locale della copia Docker `2.278.71` su `/api/pronto`, ripetuta dopo l'ultima ricostruzione: cinque richieste HTTP 200, mediana `5 ms`, massimo `135 ms` al primo campione; nessun peggioramento percepibile del bootstrap già misurato.

* Campagna golden release: `pct.cli golden-journey --run-id run-fase3-release-20260823` conclusa alle `23:31` Europe/Rome con **15/15 journey superati**. Il report immutabile è `data/golden-journeys/reports/golden_journeys_20260823_233118.json`; include deposito/predeposito, notifiche e relata, migrazione/cutover/rollback, backup/restore, tenant A/B e profilo sola lettura. Gli eventuali provider esterni restano esplicitamente classificati come dry-run o non eseguiti, senza simulazione presentata come invio reale.

## Correzione rilevata nella prova reale

La prima ricostruzione dopo l'introduzione della vista ha mostrato conteggi provenienti dall'archivio derivato dalla configurazione globale, non dal path `CLIENTI_DB` del tenant attivo. Il problema non era grafico: avrebbe potuto rendere il controllo SQL ambiguo in una sessione multi-tenant. La route ora risolve l'ancora con `tenant_data_path(..., require_tenant=True)` prima di ottenere il backend; `tests/test_data_consistency_react_api.py` prepara e autentica un tenant reale. Dopo la seconda ricostruzione Docker senza cache, la vista ha mostrato i conteggi SQL del tenant corrente indicati sopra. La correzione è coperta dai 40 test finali Storage/RBAC/React, dalla prova browser reale e dai 15 golden journey release superati.

## Correzione gate remoto

Il primo passaggio CI del commit Fase 3 ha bloccato `Lint + syntax` non per un difetto della route, ma perché l'artefatto generato `docs/backend-endpoint-security-map.md` non era stato rigenerato dopo l'aggiunta dell'endpoint protetto. Il generatore `scripts/react-migration/generate_backend_security_map.py` è stato eseguito, il controllo `--check` è ora verde e sono stati rieseguiti i test di sicurezza backend insieme ai test della nuova console e dell'outbox. Il commit correttivo viene sottoposto nuovamente a Docker locale, CI completa e deploy prima della chiusura formale.

## Rilascio verificato

Il sorgente Fase 3 è nei commit `a2246776c7fd47dd6d2f1b73f9a23a26caff2a50` e `a031465421a7f11d249b2a134d2e4fe815d75e8c`, identici sui branch `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`. Il report automatico `artifacts/ci/current-sha-required-gates.md` attesta esito **OK** sullo SHA correttivo: lint, CodeQL, test frontend, coverage 12/12, shard Pytest, Local Signer/PKCS#11, supply-chain e branch protection sono superati.

La copia Docker locale è stata ricreata dopo il correttivo e ha risposto il 24/08/2026 alle `01:10` Europe/Rome con `ok=true`, versione `2.278.71`; il container applicativo locale è `iusentra-app`, healthy. Il workflow Hetzner ha concluso con successo il deploy del medesimo SHA. La verifica SSH diretta ha confermato `/opt/iusentra/repo` su `a031465421a7f11d249b2a134d2e4fe815d75e8c`, un unico container applicativo `iusentra-app`, running e healthy; `https://app.iusentra.it/api/pronto` ha restituito `ok=true`, `Europe/Rome` e versione `2.278.71` il 24/08/2026 alle `01:13`. La cache Docker rigenerabile è stata ripulita (`0B` residui) e `/opt/iusentra/tmp-backup-snapshot` non risulta presente.
