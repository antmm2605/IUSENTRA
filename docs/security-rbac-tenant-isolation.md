# Sicurezza RBAC e isolamento tenant

Aggiornato: 2026-05-14, fase 12 `fasereact`.

## Regola operativa

Ogni endpoint che legge o scrive dati di studio deve risolvere utente, tenant e permesso prima di accedere a repository, file o indici. In multi-studio, l'assenza di contesto tenant valido blocca la richiesta.

## Layer coinvolti

- Auth e permessi: `pct/auth.py`.
- Runtime sessione/utente: `web/services/auth_runtime.py`.
- API key tenant-aware: `web/services/tenant_api_auth.py`.
- Path tenant-safe: `web/services/tenant_paths.py`.
- Isolamento request: `web/services/tenant_isolation_runtime.py`.
- Feature flag e denial: `web/services/feature_flags.py`.

## Policy denial

Un denial deve restituire errore controllato senza path, chiavi, stack trace o dettagli interni. Per capability flag-off viene registrato `policy_denied` con risorsa `feature_flag`.

## Matrice minima fase 1

| Area | Lettura | Scrittura | Tenant | Audit |
| --- | --- | --- | --- | --- |
| App V2 route sperimentali | sessione autenticata | n/a | sessione tenant | denial flag |
| Web Push | sessione autenticata | subscription/test | tenant_id + user_id | denial flag, log notifiche |
| Fascicoli/documenti | permessi dominio esistenti | API/route esistenti | repository tenant | audit dominio |
| Agenda/scadenze | permessi dominio esistenti | API/route esistenti | repository tenant | audit dominio |

## Test fase 1

- `tests/test_feature_flags.py`: default off, toggle audit, API flag e route `/app-v2/documenti` off/on.
- `tests/test_push_notifications.py`: Web Push resta operativo solo quando `notifications.mobilePush` e' esplicitamente attivo.

## Matrice fase 2

`docs/app-v2-page-registry.md` censisce per ogni route manifest i permessi RBAC
attesi, il rischio tenant e il rischio PII. Le route P0/P1 non full restano
bloccate finche' non hanno API JSON, test RBAC/tenant e smoke browser dedicati.

## Matrice fase 3

Ogni pagina App V2 ha un flag canonico `routes.appV2.<area>.<pagina>`
default-off. Il backend applica il controllo in `web/blueprints/react_shell.py`
tramite `app_v2_route_flag_for_path(...)`; il frontend usa la stessa mappa per
la shell sperimentale `/app-v2`/`/app`, nasconde il menu App V2 e rende lo stato
"Modulo non attivo" senza avviare fetch o lazy page della superficie protetta.
Le route operative storiche gia' full React non vengono spente da questi flag.

Alias fase 1 come `routes.appV2.docsPanel`, `routes.appV2.caseFiles` e
`notifications.mobilePush` restano equivalenti ai nuovi flag canonici per non
rompere ambienti gia' configurati, ma il registro ufficiale usa i nomi
canonici. I test `tests/test_feature_flags.py` e
`tests/test_app_v2_feature_flags.py` coprono default-off, alias, mapping route
dinamiche, isolamento tra configurazioni Flask e guard frontend.

## Matrice fase 4

Il passaggio legacy -> App V2 e' governato da `web/services/app_v2_routing.py`.
La decisione di redirect resta separata da auth/RBAC/tenant: una route legacy
deve verificare sessione, tenant e permessi prima di usarla. Il helper aggiunge
solo i presidi di routing:

- target interno obbligatorio sotto `/app-v2`;
- mapping esplicito, nessun target generato da input utente libero;
- query whitelistate e rimozione di `next`, `redirect`, `return_url`,
  `tenant_id`, `user_id`, ruoli, permessi e token;
- redirect consentito solo con feature flag pagina acceso;
- fallback legacy o 403 operativo quando il flag e' spento.

I test `tests/test_app_v2_routing.py` coprono open redirect, query sospette,
flag off/on, mapping con flag noto e protezione da cattura di `/api/*` e asset
statici.

## Fase 5 Backend Security Review

La fase 5 aggiunge un guardrail centrale per le API React in
`web/services/backend_security.py`, registrato come `before_request` del
blueprint `/api/v1/ui`. Il controllo scatta solo dopo autenticazione via
sessione o API key tenant-aware, cosi' una richiesta anonima continua a
ricevere 401/403 senza rivelare regole interne.

Parametri bloccati in query, JSON e form: `tenant_id`, `tenant_slug`,
`studio_id`, `studio_slug`, `user_id`, `api_key`, token generici,
`access_token`, `refresh_token`, `redirect`, `return_url`, `next` e path/root
di sistema. La risposta e' `400 backend_security_control_param`, non ripete i
valori ricevuti e scrive denial `policy_denied.backend_security`.

I campi amministrativi validi restano sui controlli dominio: `ruolo`, `role`,
`extraPermissions`, `deniedPermissions`, password temporanee e chiavi provider
specifiche come `sumup_api_key` o `twilio_token` non sono intercettati dal
guardrail centrale per non rompere i salvataggi RBAC/Impostazioni gia'
autorizzati e auditati.

| Area | Priorita | Presidio fase 5 |
| --- | --- | --- |
| Utenti, profili, audit, database, backup, impostazioni | P0 | auth obbligatoria, RBAC dedicato, tenant-aware, blocco mass assignment tenant/token |
| Fascicoli, email, telematico, fatturazione, preventivi, pagamenti | P0 | API key tenant-aware, repository tenant, denial controllati e test mirati |
| Clienti, soggetti, agenda, scadenziario, notifiche legali, sito studio | P1 | query operative consentite, campi contesto server bloccati |
| Shell App V2 sperimentale | P1 | feature flag backend/frontend e redirect fase 4 fail-closed |

La mappa completa e' in `docs/backend-endpoint-security-map.md`. I test fase 5
verificano 401 anonimo, 400 su `tenant_id`/`studio_id` forzati, filtri leciti
non bloccati, nessun eco di valori sensibili, auth decorator su tutte le API
React e documento generato allineato.

## Fase 6 API Security Contracts

La fase 6 rende verificabili i presidi di sicurezza dentro `docs/openapi.yaml`:
ogni endpoint React API documenta `x-rbac-permission`, `x-tenant-scope`,
priorita, feature flag quando applicabile, error schema e stato provider.

La provider verification in `scripts/verify_openapi_provider.py` usa Flask test
client e conferma 401 reale su tutti gli endpoint contrattualizzati, 200
autenticato su un campione P0/P1 rappresentativo e 400
`backend_security_control_param` quando il client prova a inviare `tenant_id`.

## Portale Cliente

Il Portale Cliente aggiunge un perimetro pubblico limitato senza indebolire il
tenant isolation:

- la console studio `/app/portale-clienti` usa sessione o API key
  tenant-aware;
- la vista cliente `/portale-cliente` usa token opaco firmato e risolto
  server-side;
- il token invito è salvato solo come hash, con scadenza e revoca;
- gli endpoint pubblici non accettano `tenant_id`, `studio_id`, path o ruoli;
- un token assente o non valido produce errore sicuro senza rivelare tenant,
  cliente o pratica;
- upload e download passano da storage tenant-aware e non espongono percorsi
  filesystem;
- Web Push e videocall restano dietro flag default-off.

Test collegati:

```powershell
python -m pytest tests/test_client_portal_repository.py tests/test_client_portal_api.py -q --tb=short
python scripts\verify_openapi_provider.py
```

## Fase 8 Requisiti specifici per area

La fase 8 aggiunge `docs/app-v2-area-requirements.md` come registro generato
dei requisiti per workflow reali. Ogni area presente nel manifest dichiara
workflow principali, RBAC, PII, endpoint, feature flag, test richiesti e stato
finale. Un'area non puo' essere `complete_tested` se contiene route legacy o
parziali: il gate `tests/test_app_v2_area_requirements_phase8.py` lo verifica
direttamente sul manifest.

Lo smoke `scripts/smoke_app_v2_workflows.py` copre l'inventario P0/P1
dashboard, fascicoli, documenti, comunicazioni, scadenze, agenda, ricerca,
admin, impostazioni e controlli atti. L'esecuzione autenticata usa solo
credenziali da ambiente (`IUSENTRA_ADMIN_*`, `IUSENTRA_TENANT_A_*`,
`IUSENTRA_TENANT_B_*`, `IUSENTRA_READONLY_*`) e non dichiara passati i profili
non configurati.

## Handover fase 12

Policy aggiuntive:

- PII: dati cliente, documenti, PEC/email, dati fiscali e segreti integrazione non devono comparire nei log o negli errori visibili.
- File/documenti: upload, preview, download, export e allegati devono passare da route backend tenant-safe e non accettare path client.
- Admin/settings: salvataggi di segreti devono redigere valori in risposta e auditare solo metadati.
- Report/export: generazione e download richiedono permesso dominio e repository tenant.
- Error handling: 401/403/404/422 devono essere controllati, in italiano per UI, senza stack trace.

Test minimi quando si tocca sicurezza/App V2:

```powershell
python -m pytest -q tests/test_auth.py tests/test_backend_security_phase5.py tests/test_tenant_isolation_runtime.py tests/test_app_v2_feature_flags.py tests/test_app_v2_routing.py --tb=short
python scripts\smoke_backend_security.py --base-url http://127.0.0.1:8080
```

## Punti da estendere nelle fasi successive

- smoke cross-tenant autenticati con credenziali tenant A/B da env;
- provider verification success-body completa su endpoint parametrici, upload e mutazioni distruttive;
- report finale su permessi mancanti per singola pagina App V2.
