# Audit iniziale migrazione React/App V2

Aggiornato: 2026-05-13, fase 4 `fasereact`.

## Aggiornamento fase 4

La fase 4 completa la governance routing/fallback tra legacy Flask/Jinja e
React/App V2. Il nuovo `web/services/app_v2_routing.py` accetta solo target
interni `/app-v2`, richiede mapping esplicito, rimuove query sensibili e
permette redirect solo quando il feature flag pagina e' acceso.

Il registro generato aggiunge redirect strategy, deep link, query params,
classificazione template legacy e stato finale fase 4. Il nuovo documento
`docs/legacy-to-app-v2-routing-map.md` censisce manifest, route App V2 frontend,
alias legacy e mapping backend sicuri; i redirect live attivati restano 0 per
evitare regressioni prima delle migrazioni funzionali delle fasi successive.

Nuovi presidi: `scripts/smoke_app_v2_routing.py`,
`tests/test_app_v2_routing.py`, normalizzazione query/hash in
`frontend/src/app/router.tsx` e contratti statici in
`frontend/scripts/check-react-contracts.mjs`.

## Aggiornamento fase 3

La fase 3 completa il mapping feature flag per pagina App V2. I nuovi flag
canonici seguono `routes.appV2.<area>.<pagina>`, restano default-off e sono
applicati sia dal backend `/app-v2` sia dal frontend React prima dei fetch.

Il registro `docs/app-v2-page-registry.md` ora documenta per ogni riga:
feature flag, default, fallback flag-off, protezione frontend, protezione
backend e test on/off. Gli alias fase 1 (`routes.appV2.docsPanel`,
`routes.appV2.caseFiles`, `notifications.mobilePush`, ecc.) restano compatibili
ma vengono ricondotti ai flag canonici.

Nuovi presidi: `frontend/src/lib/featureFlags.ts` con mappa percorsi, guard
`FeatureUnavailablePage` in `frontend/src/App.tsx` limitata a `/app-v2` e
`/app`, menu App V2 filtrato e test statici in
`tests/test_app_v2_feature_flags.py`.

## Aggiornamento fase 2

La fase 2 aggiunge il registro ufficiale `docs/app-v2-page-registry.md`,
generato da `scripts/react-migration/generate_app_v2_page_registry.py`. Il
registro copre tutte le 98 route del manifest con stato migrazione, feature
flag, permessi, rischio tenant/PII, test presenti, test mancanti e priorita.

Il riepilogo operativo `docs/frontend-app-v2-pages.md` espone anche le 13 route
di shell App V2, i 31 alias legacy verso App V2 e il backlog delle route non
full: 28 P0 e 1 P1. Nessuna di queste route viene dichiarata completa dalla
fase 2; resta richiesta la parita reale prima della promozione.

Aggiunto `scripts/smoke_app_v2_pages.py` per smoke post-deploy parametrico. Le
credenziali sono lette solo da variabili ambiente e la modalita `--list`
consente di verificare manifest e target senza chiamate HTTP.

## Stato sintetico

Il manifest governato `tools/react-migration/route-manifest.json` censisce 98 route:

- 69 `react_operational_full`;
- 3 `react_operational_partial`;
- 26 `legacy_operational`.

La shell React e' servita da `web/blueprints/react_shell.py` e dal gate centrale `web/bootstrap/react_route_gate.py`. Le API JSON principali vivono in `web/blueprints/api_v1_react.py` e delegano a bridge in `web/services/react_*_bridge.py`, senza duplicare la source of truth frontend.

## Rotte Flask legacy individuate

Restano legacy-first i percorsi ad alto rischio o non ancora parificati: servizi telematici profondi, portali non-PST, SIGP sync, tribunali/PEC, osservabilita, download, allegati, export, PDF/XML/ZIP, sottopercorsi tecnici di backup, template, redazione, fatturazione e azioni POST non ricostruite in JSON.

Il gate esclude inoltre suffissi e segmenti sensibili (`download`, `export`, `allegato`, `visualizza`, `.pdf`, `.xml`, `.zip`, `.eml`) per evitare che la shell React mascheri flussi backend ancora necessari.

## Template Jinja ancora usati

Sono presenti 258 template Jinja in `web/templates/`. Restano necessari per login, pagine classiche non migrate, errori HTTP, superfici amministrative/piattaforma e fallback tecnici `_legacy=1` dove dichiarati nel manifest. I template non devono essere rimossi senza contratto equivalente React/API.

## Pagine React gia' migrate

Tra le superfici `react_operational_full` risultano: Panoramica, Agenda, Scadenziario lista/dettaglio, Fascicoli, Documenti, Comunicazioni/email/messaggi, Clienti/Soggetti, Studio, Amministrazione, Utenti, Profili, Audit/Registro attivita, Database, Impostazioni, Pagamenti, Notifiche, Backup, Calendari, Fatturazione, Preventivi, Compensi, Tariffario, Template Atti, Redazione Atti, Giurisprudenza, Ricerca Legale, Sito Studio e builder verificato.

I componenti React sono 112 in `frontend/src/components`, con feature verticali aggiuntive in `frontend/src/features/*`.

## Pagine React incomplete

Le partial o legacy operative riguardano soprattutto:

- workflow telematici profondi e portali istituzionali non-PST;
- export/download/allegati e generazione documenti;
- sottoroute tecniche non ancora coperte da API JSON;
- percorsi dove serve Local Signer, credenziale locale o evidenza ufficiale esterna.

La regola e' fail-closed: una route non viene promossa a `react_operational_full` finche' letture, scritture, permessi, audit, tenant e UI states non sono equivalenti.

## Endpoint API coinvolti

Endpoint principali:

- `/api/v1/ui/bootstrap`;
- `/api/v1/ui/feature-flags`;
- `/api/v1/ui/fascicoli*`;
- `/api/v1/ui/scadenziario*`;
- `/api/v1/ui/messaggi*`, `/api/v1/ui/email*`, `/api/v1/ui/email-ordinaria*`;
- `/api/v1/ui/impostazioni*`, `/api/v1/ui/calendari*`, `/api/push/*`;
- `/api/v1/ui/studio-modules/<module_id>`;
- `/api/v1/ui/telematico*` per superfici governate.

## Tabelle e storage multi-tenant coinvolti

Le aree sensibili restano tenant-aware: `AUTH_DB`, `AUDIT_DB`, `CLIENTI_DB`, `FASCICOLI_DB`, `FASCICOLI_DOCS`, `AGENDA_DB`, `SCADENZIARIO_DB`, `MESSAGGI_DB`, `EMAIL_CASELLA_DB`, `EMAIL_ORDINARIA_DB`, `NOTIFICATIONS_DB`, `PREVENTIVI_DB`, `FATTURAZIONE_DB`, `TELEMATICO_DB`, `PDP_PENALE_DB`, `TEMPLATE_ATTI_DB`, repository intelligence e audit WORM.

In multi-studio l'accesso senza `g.data_paths` valido deve fallire chiuso.

## RBAC, tenant e audit

RBAC corrente: ruoli e permessi sono in `pct/auth.py`; le API React applicano guardie dedicate o permessi di dominio. Tenant isolation corrente: `web/services/tenant_isolation_runtime.py`, `web/services/tenant_paths.py` e `web/services/tenant_api_auth.py`.

La fase 1 aggiunge `web/services/feature_flags.py`, con default-off, audit `feature_flag_toggled` per toggle governati e log `policy_denied` quando una capability flag-off viene richiesta.

## Test presenti e mancanti

Presenti: pytest mirati su shell React, route gate, storage tenant, email, notifiche, audit WORM, packaging/release readiness; frontend `npm run test`, `npm run typecheck`, `npm run build`; gate `scripts/react-migration/*`.

Mancanti o da completare nelle fasi successive:

- OpenAPI/provider verification esteso a tutte le API App V2;
- matrice E2E completa tenant A/B su browser;
- visual regression sistematica o alternativa Storybook sostenibile;
- smoke post-deploy parametrico con credenziali da env.

## Rischi principali

- `frontend/src/App.tsx` e' ancora monolitico, quindi ogni cambio UI deve essere minimo e testato.
- Alcune route condividono endpoint JSON con alias ufficiali: il manifest deve dichiararle esplicitamente.
- Il primo warm-up tenant dopo restart puo' essere lento ed e' gia' registrato in `pytest-open-issues.md`.
- Web Push e nuove capability App V2 sono ora sotto feature flag: la produzione deve abilitarle esplicitamente quando desiderato.

## Ordine consigliato

1. Feature flag default-off e guardie backend/frontend.
2. Inventario completo pagine/rotte e priorita P0/P1/P2/P3.
3. Mapping route/feature flag per ogni pagina App V2.
4. Routing/fallback legacy sicuri.
5. Sicurezza backend: RBAC, tenant, audit.
6. OpenAPI/provider verification.
7. Frontend React/App V2 per pagina.
8. Workflow specifici per area.
9. Test UI/VRT/accessibilita.
10. Test completi, CI, runbook, smoke e Go/No-Go.

## Feature flag introdotti

Fase 3, canonici per pagina/famiglia:

- `routes.appV2.dashboard.home`, `routes.appV2.dashboard.regia`, `routes.appV2.search.global`;
- `routes.appV2.cases.*`, `routes.appV2.clients.*`, `routes.appV2.contacts.*`;
- `routes.appV2.comms.*`, `routes.appV2.agenda.*`, `routes.appV2.deadlines.*`;
- `routes.appV2.documents.*`, `routes.appV2.legalResearch.*`, `routes.appV2.telematico.*`;
- `routes.appV2.studio.*`, `routes.appV2.admin.*`, `routes.appV2.settings.*`;
- `routes.appV2.billing.*`, `routes.appV2.notifications.mobilePush`.

Alias compatibilita fasi 1-2:

- `routes.appV2.docsPanel`;
- `routes.appV2.commsDeposits`;
- `routes.appV2.uploadClassification`;
- `routes.appV2.deadlines`;
- `routes.appV2.agenda`;
- `routes.appV2.caseFiles`;
- `notifications.mobilePush`.

Tutti sono default-off in assenza di configurazione esplicita.
