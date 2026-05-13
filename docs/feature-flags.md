# Feature flag IUSENTRA

Aggiornato: 2026-05-13.

## Principio

I flag della migrazione React/App V2 sono default-off. Servono a introdurre capability nuove o sperimentali senza spegnere le superfici React gia' promosse come operative nel manifest.

## Flag canonici fase 3

La fase 3 introduce un flag canonico per ogni pagina o famiglia App V2, con
nome `routes.appV2.<area>.<pagina>`. Tutti i flag sono `off` di default; se un
flag e' spento la shell mostra uno stato operativo e non carica i dati della
pagina. Il mapping completo pagina/flag/default/fallback e' generato in
`docs/app-v2-page-registry.md`.

| Area | Esempi di flag canonici | Default | Protezione |
| --- | --- | --- | --- |
| Panoramica e regia | `routes.appV2.dashboard.home`, `routes.appV2.dashboard.regia`, `routes.appV2.search.global` | off | backend `/app-v2`, frontend menu/fetch |
| Fascicoli e anagrafiche | `routes.appV2.cases.list`, `routes.appV2.cases.detail`, `routes.appV2.clients.list`, `routes.appV2.contacts.list` | off | route dinamiche e tenant sessione |
| Comunicazioni | `routes.appV2.comms.pec`, `routes.appV2.comms.ordinaryMail`, `routes.appV2.comms.messages` | off | nessuna chiamata mail se spento |
| Agenda e scadenze | `routes.appV2.agenda.calendar`, `routes.appV2.deadlines.list`, `routes.appV2.deadlines.hearingWizard` | off | route e drawer bloccati |
| Documenti e redazione | `routes.appV2.documents.list`, `routes.appV2.documents.templates`, `routes.appV2.documents.drafting`, `routes.appV2.documents.checklist` | off | editor e checklist fail-closed |
| Studio, mandato e amministrazione | `routes.appV2.studio.statistics`, `routes.appV2.billing.quotes`, `routes.appV2.admin.users`, `routes.appV2.settings.studio` | off | menu nascosto e shell bloccata |
| Notifiche dispositivo | `routes.appV2.notifications.mobilePush` | off | frontend evita Web Push, backend rifiuta subscribe/test |

## Alias compatibilita fasi 1-2

| Flag | Variabile env | Default | Ambito |
| --- | --- | --- | --- |
| `routes.appV2.docsPanel` | `IUSENTRA_FF_ROUTES_APPV2_DOCS_PANEL` | off | `/app-v2/documenti` |
| `routes.appV2.commsDeposits` | `IUSENTRA_FF_ROUTES_APPV2_COMMS_DEPOSITS` | off | `/app-v2/comunicazioni` |
| `routes.appV2.uploadClassification` | `IUSENTRA_FF_ROUTES_APPV2_UPLOAD_CLASSIFICATION` | off | upload/classificazione documenti App V2 |
| `routes.appV2.deadlines` | `IUSENTRA_FF_ROUTES_APPV2_DEADLINES` | off | `/app-v2/scadenziario` |
| `routes.appV2.agenda` | `IUSENTRA_FF_ROUTES_APPV2_AGENDA` | off | `/app-v2/agenda` |
| `routes.appV2.caseFiles` | `IUSENTRA_FF_ROUTES_APPV2_CASE_FILES` | off | `/app-v2/fascicoli` |
| `notifications.mobilePush` | `IUSENTRA_FF_NOTIFICATIONS_MOBILE_PUSH` | off | Web Push dispositivo |

Questi alias restano accettati per non rompere configurazioni esistenti, ma
vengono risolti verso i flag canonici equivalenti.

## Configurazione

Si puo' usare una variabile per singolo flag:

```bash
IUSENTRA_FF_NOTIFICATIONS_MOBILE_PUSH=1
```

Oppure un JSON unico:

```bash
IUSENTRA_FEATURE_FLAGS='{"routes.appV2.documents.list":true,"routes.appV2.notifications.mobilePush":true}'
```

Valori accettati per `true`: `1`, `true`, `yes`, `on`, `si`.
Valori accettati per `false`: `0`, `false`, `no`, `off`.

## API e bootstrap

`GET /api/v1/ui/feature-flags` restituisce lo stato pubblico dei flag per la sessione autenticata.

La shell React riceve gli stessi flag nel bootstrap `iusentra-react-bootstrap`, cosi' il frontend puo' nascondere le superfici non abilitate senza chiamare API sperimentali.

## Comportamento flag-off

- route sperimentali `/app-v2/<area>`: HTTP 403 con messaggio operativo;
- Web Push: il frontend mostra che il canale non e' attivo e non chiama `/api/push/public-key`, `/api/push/subscribe` o `/api/push/test`;
- backend: le azioni sensibili protette da flag restituiscono `403` e registrano `policy_denied`;
- toggle governati: `set_feature_flag(...)` registra `feature_flag_toggled` quando viene fornito il gestore audit.

## Routing fase 4

La fase 4 aggiunge `web/services/app_v2_routing.py`: un redirect legacy -> App
V2 puo' essere considerato solo se il target e' interno a `/app-v2`, il mapping
e' esplicito, la query e' whitelistata e il flag pagina e' acceso. In assenza
di flag attivo la decisione resta fail-closed e il template/route legacy resta
fallback.

Query preservate: `page`, `q`, `search`, `filter`, `sort`, `tab`, `view`,
`from`, `to`, `status`, `drawer`, `section`, `focus`.

Query sempre bloccate: `next`, `return`, `return_url`, `redirect`,
`redirect_url`, `callback`, `url`, `target`, `tenant_id`, `studio_id`,
`user_id`, `role`, `permission`, `is_admin`, `debug`, `token`.

## Rollback rapido

Spegnere il flag via env o JSON, riavviare app e worker web. Non serve migrazione dati.

## Registro fase 4

Il mapping pagina/flag/routing e' ora censito in `docs/app-v2-page-registry.md`,
`docs/frontend-app-v2-pages.md` e `docs/legacy-to-app-v2-routing-map.md`, tutti
generato da `scripts/react-migration/generate_app_v2_page_registry.py`. Le
route sperimentali App V2 con flag restano default-off; per ogni riga sono
documentati fallback flag-off, protezione frontend, protezione backend, redirect
strategy, deep link, query params e test on/off. Le route ufficiali gia'
`react_operational_full` restano governate dal manifest e dal route gate quando
non entrano nella shell App V2.
