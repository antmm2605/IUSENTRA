# Feature flag IUSENTRA

Aggiornato: 2026-05-14, fase 12 `fasereact`.

## Principio

I flag della migrazione React/App V2 restano il meccanismo di rollback e protezione. Le superfici gia' promosse operative nel manifest sono attive di default, mentre i workflow non parificati o sensibili restano default-off e fail-closed.

## Flag canonici fase 3

La fase 3 introduce un flag canonico per ogni pagina o famiglia App V2, con
nome `routes.appV2.<area>.<pagina>`. I flag delle pagine operative sono `on`
di default e possono essere spenti esplicitamente per rollback; i flag
telematici non parificati e Web Push restano `off`. Se un flag e' spento la
shell mostra uno stato operativo e non carica i dati della pagina. Il mapping
completo pagina/flag/default/fallback e' generato in
`docs/app-v2-page-registry.md`.

| Area | Esempi di flag canonici | Default | Protezione |
| --- | --- | --- | --- |
| Panoramica e regia | `routes.appV2.dashboard.home`, `routes.appV2.dashboard.regia`, `routes.appV2.search.global` | on | backend `/app-v2`, frontend menu/fetch |
| Fascicoli e anagrafiche | `routes.appV2.cases.list`, `routes.appV2.cases.detail`, `routes.appV2.clients.list`, `routes.appV2.contacts.list` | on | route dinamiche e tenant sessione |
| Portale Cliente | `routes.appV2.clientPortal.enabled`, `routes.appV2.clientPortal.notifications`, `routes.appV2.clientPortal.signatures`, `routes.appV2.clientPortal.webPush`, `routes.appV2.clientPortal.videoCalls` | misto | console studio e vista cliente attive; Web Push e videocall restano fail-closed |
| Comunicazioni | `routes.appV2.comms.pec`, `routes.appV2.comms.ordinaryMail`, `routes.appV2.comms.messages`, `routes.appV2.comms.newMessage` | on | nessuna chiamata mail se spento |
| Agenda e scadenze | `routes.appV2.agenda.calendar`, `routes.appV2.deadlines.list`, `routes.appV2.deadlines.hearingWizard` | on | route e drawer bloccati se spenti |
| Documenti e redazione | `routes.appV2.documents.list`, `routes.appV2.documents.templates`, `routes.appV2.documents.drafting`, `routes.appV2.documents.checklist` | on | editor e checklist spegnibili |
| Studio, mandato e amministrazione | `routes.appV2.studio.statistics`, `routes.appV2.billing.quotes`, `routes.appV2.admin.users`, `routes.appV2.settings.studio` | on | menu nascosto e shell bloccata se spenti |
| Legal Document Understanding | `ocr_forensic`, `legal_document_understanding`, `pec_zip_ocr`, `lex_validated_documents_only` | on | OCR forense, ZIP PEC, validazione e gate Lex |
| Servizi telematici non parificati | `routes.appV2.telematico.center`, `routes.appV2.telematico.surface` | off | workflow ministeriali fail-closed |
| Notifiche dispositivo | `routes.appV2.notifications.mobilePush` | off | frontend evita Web Push, backend rifiuta subscribe/test |
| Legal Skills | `lex.legalSkills.enabled`, `routes.appV2.legalSkills.*` | on | catalogo, profilo, esecuzione e revisione sono attivi; trust layer, custom skill e agenti schedulati restano fail-closed |

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

Si puo' usare una variabile per singolo flag. Per rollback si imposta `0` sul
flag della pagina; per attivare una capability protetta si imposta `1`.

```bash
IUSENTRA_FF_ROUTES_APPV2_COMMS_NEWMESSAGE=0
```

Oppure un JSON unico:

```bash
IUSENTRA_FEATURE_FLAGS='{"routes.appV2.comms.newMessage":false,"routes.appV2.notifications.mobilePush":true}'
```

Valori accettati per `true`: `1`, `true`, `yes`, `on`, `si`.
Valori accettati per `false`: `0`, `false`, `no`, `off`.

## API e bootstrap

`GET /api/v1/ui/feature-flags` restituisce lo stato pubblico dei flag per la sessione autenticata.

La shell React riceve gli stessi flag nel bootstrap `iusentra-react-bootstrap`, cosi' il frontend puo' nascondere le superfici non abilitate senza chiamare API sperimentali.

## Flag Lex e AI

Le capability Lex che accedono a dati operativi o fonti giuridiche restano governate da variabili dedicate e default sicuri. Questi flag non sostituiscono RBAC, tenant isolation o audit: li attivano solo come primo cancello.

| Capability | Flag/env | Default | Protezione |
| --- | --- | --- | --- |
| Lex Operational Knowledge | `LEX_OPERATIONAL_KNOWLEDGE_ENABLED` | on | abilita i tool deterministici tenant-aware su dati reali dello studio; `0` resta rollback esplicito |
| Audit query operative Lex | `LEX_OPERATIONAL_AUDIT_ENABLED` | off | registra domanda, sorgenti, oggetti letti, permessi applicati ed esito nel registro audit |
| Strict mode operativo Lex | `LEX_OPERATIONAL_STRICT_MODE_ENABLED` | off | riservato a policy piu' restrittive; le guardie base restano sempre attive |
| Legal Source Engine nativo | `IUSENTRA_LEX_AI_LEGAL_SOURCES_ENABLED` | off | abilita fonti ufficiali locali, rete sempre off salvo `IUSENTRA_LEGAL_SOURCES_ALLOW_NETWORK=1` |
| Legal Skills Engine | `IUSENTRA_FF_LEX_LEGALSKILLS_ENABLED` / `lex.legalSkills.enabled` | on | abilita catalogo, profilo e run Legal Skills; RBAC e tenant isolation restano obbligatori |
| Trust layer Legal Skills | `IUSENTRA_FF_LEX_LEGALSKILLS_TRUSTLAYER` / `lex.legalSkills.trustLayer` | off | consente solo controllo statico di skill custom, senza installarle |
| Agenti schedulati Legal Skills | `IUSENTRA_FF_LEX_LEGALSKILLS_SCHEDULEDAGENTS` / `lex.legalSkills.scheduledAgents` | off | abilita agenti read-only con audit, nessuna scrittura automatica |
| Unlimited-OCR self-hosted | `IUSENTRA_UNLIMITED_OCR_ENABLED` | off | abilita solo adapter OCR verso endpoint locale/privato; fallback corrente e benchmark obbligatori prima della promozione |

Per i dati di clienti, fascicoli, agenda, scadenze, preventivi, documenti e comunicazioni Lex non usa web esterno. Il layer operativo e' attivo di default per evitare risposte bloccate su dati reali dello studio; se il flag viene spento esplicitamente, il bounded workflow esistente continua senza interrogare il nuovo layer.

## Comportamento flag-off

- route App V2 con flag spento: HTTP 403 con messaggio operativo;
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

## Registro operativo fase 12

La fonte eseguibile resta `web/services/feature_flags.py`; la fonte frontend compatibile e' `frontend/src/lib/featureFlags.ts`. La tabella completa pagina/flag/fallback/test e' generata in `docs/app-v2-page-registry.md`. Le aree operative sotto sono `on` di default; telematico non parificato e Web Push restano `off`.

| Area | Flag | Backend protected | Fallback | Test |
| --- | --- | --- | --- | --- |
| Dashboard | `routes.appV2.dashboard.home`, `routes.appV2.dashboard.regia`, `routes.appV2.search.global` | si, route App V2 e API collegate | legacy/stato modulo non attivo | `tests/test_feature_flags.py`, `tests/test_app_v2_feature_flags.py`, `tests/test_app_v2_routing.py` |
| Fascicoli | `routes.appV2.cases.list`, `routes.appV2.cases.detail`, `routes.appV2.cases.create` | si | legacy/stato modulo non attivo | stessi gate flag/routing |
| Clienti/soggetti | `routes.appV2.clients.list`, `routes.appV2.clients.create`, `routes.appV2.clients.detail`, `routes.appV2.contacts.list`, `routes.appV2.contacts.create` | si | legacy/stato modulo non attivo | stessi gate flag/routing |
| Portale Cliente | `routes.appV2.clientPortal.enabled`, `routes.appV2.clientPortal.notifications`, `routes.appV2.clientPortal.signatures`, `routes.appV2.clientPortal.webPush`, `routes.appV2.clientPortal.videoCalls` | si, API `/api/v1/ui/client-portal/*` | link invito non valido o canale non attivo | `tests/test_client_portal_api.py`, `tests/test_client_portal_repository.py`, OpenAPI/provider, gate React |
| Comunicazioni | `routes.appV2.comms.deposits`, `routes.appV2.comms.pec`, `routes.appV2.comms.ordinaryMail`, `routes.appV2.comms.messages`, `routes.appV2.comms.newMessage` | si | legacy/stato modulo non attivo | stessi gate flag/routing |
| Agenda/scadenze | `routes.appV2.agenda.calendar`, `routes.appV2.agenda.create`, `routes.appV2.agenda.timesheet`, `routes.appV2.deadlines.list`, `routes.appV2.deadlines.create`, `routes.appV2.deadlines.detail`, `routes.appV2.deadlines.hearingWizard` | si | legacy/stato modulo non attivo | stessi gate flag/routing |
| Documenti | `routes.appV2.documents.list`, `routes.appV2.documents.templates`, `routes.appV2.documents.templateEditor`, `routes.appV2.documents.drafting`, `routes.appV2.documents.editor`, `routes.appV2.documents.uploadClassification`, `routes.appV2.documents.checklist` | si | legacy/stato modulo non attivo | stessi gate flag/routing |
| Ricerca legale | `routes.appV2.legalResearch.home`, `routes.appV2.legalResearch.giurisprudenza` | si | legacy/stato modulo non attivo | stessi gate flag/routing |
| Telematico | `routes.appV2.telematico.center`, `routes.appV2.telematico.surface` | si, fail-closed sui workflow non parificati | legacy/protetto | stessi gate flag/routing + test telematici mirati |
| Studio | `routes.appV2.studio.home`, `routes.appV2.studio.statistics`, `routes.appV2.studio.modules`, `routes.appV2.studio.site`, `routes.appV2.studio.siteBuilder`, `routes.appV2.studio.siteDrafting` | si | legacy/stato modulo non attivo | stessi gate flag/routing |
| Admin | `routes.appV2.admin.home`, `routes.appV2.admin.users`, `routes.appV2.admin.roles`, `routes.appV2.admin.auditLogs`, `routes.appV2.admin.database`, `routes.appV2.admin.privacyRegistry` | si | legacy/stato modulo non attivo | stessi gate flag/routing + RBAC |
| Impostazioni | `routes.appV2.settings.studio`, `routes.appV2.settings.payments`, `routes.appV2.settings.notifications`, `routes.appV2.settings.backup`, `routes.appV2.settings.calendarSync` | si | legacy/stato modulo non attivo | stessi gate flag/routing + test impostazioni |
| Mandato/economico | `routes.appV2.billing.invoices`, `routes.appV2.billing.payments`, `routes.appV2.billing.quotes`, `routes.appV2.billing.compensi`, `routes.appV2.billing.tariffario` | si | legacy/stato modulo non attivo | stessi gate flag/routing + test dominio |
| Notifiche dispositivo | `routes.appV2.notifications.mobilePush` | si, API push | canale non attivo | `tests/test_push_notifications.py` |
| Legal Skills | `routes.appV2.legalSkills.catalog`, `routes.appV2.legalSkills.profile`, `routes.appV2.legalSkills.run`, `routes.appV2.legalSkills.reviewQueue` | si, API `/api/v1/legal-skills/*` | rollback esplicito via flag | `tests/test_legal_skills_engine.py`, `frontend/scripts/check-legal-skills.mjs` |
| Alias compatibilita | `routes.appV2.docsPanel`, `routes.appV2.commsDeposits`, `routes.appV2.uploadClassification`, `routes.appV2.deadlines`, `routes.appV2.agenda`, `routes.appV2.caseFiles`, `notifications.mobilePush` | risolti verso canonico | come flag canonico | `tests/test_feature_flags.py` |

## Come aggiungere un nuovo Feature Flag

1. Definire il flag in `web/services/feature_flags.py`; usare default `False` finche' la superficie non e' verificata come operativa.
2. Aggiungere alias solo se serve compatibilita esplicita.
3. Aggiornare `frontend/src/lib/featureFlags.ts`.
4. Collegare route/menu/sidebar e no-fetch flag-off.
5. Applicare enforcement backend se la route o l'endpoint sono sensibili.
6. Aggiungere test flag off/on.
7. Rigenerare registry e documenti.
8. Documentare rollout e rollback.

## Rollback rapido

Spegnere il flag via env o JSON, riavviare app e worker web. Non serve migrazione dati.

## Registro fase 4

Il mapping pagina/flag/routing e' ora censito in `docs/app-v2-page-registry.md`,
`docs/frontend-app-v2-pages.md` e `docs/legacy-to-app-v2-routing-map.md`, tutti
generato da `scripts/react-migration/generate_app_v2_page_registry.py`. Le
route App V2 mantengono fallback flag-off documentato e default coerente con lo
stato operativo; per ogni riga sono documentati protezione frontend, backend, redirect
strategy, deep link, query params e test on/off. Le route ufficiali gia'
`react_operational_full` restano governate dal manifest e dal route gate quando
non entrano nella shell App V2.


## Procedure Completion Engine

| Flag | Default | Nota |
|---|---|---|
| `lex.procedureCompletion.enabled` | ON | Engine, API `/api/v1/ui/procedure-completion/*` e tool Lex; OFF = 403 fail-closed. |
| `routes.appV2.procedureCompletion.home` | ON | Pagina `/procedure-completion` nella shell App V2. |
| `lex.procedureCompletion.voiceRead.enabled` | OFF | Lettura vocale della scheda (TTS locale browser, opt-in). |
| `lex.procedureCompletion.voiceRead.localOnly` | ON | Vincola la lettura al solo TTS locale, nessun provider esterno. |

Override ambiente: `IUSENTRA_FF_LEX_PROCEDURECOMPLETION_ENABLED=0` e analoghi.
