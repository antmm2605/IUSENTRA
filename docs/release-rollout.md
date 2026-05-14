# Release rollout App V2

Aggiornato: 2026-05-14.

## Strategia

Le nuove capability App V2 partono con flag spento. Dalla fase 3 il flag e'
per pagina/famiglia (`routes.appV2.<area>.<pagina>`): backend, menu frontend e
fetch usano lo stesso valore. Ogni rollout richiede metriche di salute, smoke
mirato e possibilita di spegnimento entro 2 ore.

## Percentuali

| Step | Azione | Osservare |
| --- | --- | --- |
| 1% | abilita su uno studio interno o tenant pilota | errori 4xx/5xx, tempi route, console browser |
| 10% | abilita su pochi studi operativi | ticket utente, denial RBAC, payload incompleti |
| 50% | abilita su studi rappresentativi | carico API, latenza bootstrap, worker e notifiche |
| 100% | abilita come comportamento ordinario | regressioni, fallback legacy, tempi post-deploy |

## Metriche

- `/api/pronto` 200 e versione attesa;
- container app, worker, Redis, Caddy/Nginx healthy;
- tempi route rappresentative sotto baseline documentata;
- nessun errore console sulle pagine toccate;
- nessun testo tecnico vietato nella UI;
- nessun accesso cross-tenant nei log/test.

## Alert

Aprire incidente se compaiono:

- 500 su API App V2;
- 403 inattesi per ruoli ammessi;
- payload con dati di altro tenant;
- chiamate Web Push quando `notifications.mobilePush` e' spento;
- peggioramento evidente del primo contenuto React su percorsi caldi.

## Rollback entro 2 ore

1. Spegnere il flag env o `IUSENTRA_FEATURE_FLAGS`.
2. Riavviare app e worker web.
3. Verificare `/api/v1/ui/feature-flags`.
4. Ripetere smoke browser sulla pagina interessata.
5. Se il bug riguarda codice non isolabile da flag, revertire il commit della fase e ridistribuire.

## Smoke post deploy

Comandi minimi:

```bash
curl -fsS https://app.iusentra.it/api/pronto
curl -fsS https://app.iusentra.it/api/v1/ui/feature-flags
```

Per Web Push, autenticarsi con sessione tenant e verificare che `/api/push/public-key` non esponga mai private key.

Fase 3 usa lo smoke parametrico senza segreti in repository:

```bash
IUSENTRA_BASE_URL=https://app.iusentra.it \
IUSENTRA_SMOKE_USERNAME="$IUSENTRA_SMOKE_USERNAME" \
IUSENTRA_SMOKE_PASSWORD="$IUSENTRA_SMOKE_PASSWORD" \
python scripts/smoke_app_v2_pages.py --require-credentials
```

Senza credenziali e' consentito solo l'inventario:

```bash
python scripts/smoke_app_v2_pages.py --list
```

La risposta `403` su `/app-v2` o `/app-v2/documenti` e' corretta quando il flag
del tenant e' spento; la risposta `200` e' corretta solo per tenant/ambienti
abilitati esplicitamente.

Fase 13 consolida il comando post-deploy unico:

```powershell
python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url https://app.iusentra.it --json-output artifacts\smoke\post-deploy.json
```

Il comando deve restituire exit `0` senza `FAIL`. Eventuali `BLOCKED` vanno
letti come blocchi reali di ambiente, ad esempio credenziali smoke o ID
documento test mancanti, e non come controlli passati.

## Runbook Hetzner fase 12

Pre-release minima:

```powershell
python tools\sync_packaging_files.py --check
python scripts\validate_docs_links.py
python scripts\validate_docs_commands.py
python scripts\react-migration\generate_app_v2_page_registry.py --check
python scripts\react-migration\generate_app_v2_area_requirements.py --check
python scripts\react-migration\generate_app_v2_test_docs.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Deploy operativo senza aggiornare cron backup:

```bash
cd /opt/iusentra/repo
IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh
```

Smoke post-deploy:

```powershell
python scripts\smoke_backend_security.py --base-url https://app.iusentra.it
python scripts\smoke_app_v2_all.py --base-url https://app.iusentra.it --subset routing
python scripts\smoke_app_v2_all.py --base-url https://app.iusentra.it --subset workflows
```

Verifiche obbligatorie: commit server uguale al commit pushato, container app/scheduler/OCR/Redis/audit/Ollama healthy o up secondo servizio, `/api/pronto` 200 con versione attesa.

Escalation: raccogliere commit SHA, output deploy, `docker compose ps`, risposta `/api/pronto`, subset smoke fallito, request id/log redatti, stato feature flag e tenant impattato in forma redatta.

## Backend security fase 5

Ogni deploy della fase 5 deve includere lo smoke senza segreti:

```bash
python scripts/smoke_backend_security.py --base-url https://app.iusentra.it
```

Con una API key di studio fornita da ambiente, lo smoke verifica anche che una
richiesta autenticata con `tenant_id` forzato venga bloccata:

```bash
IUSENTRA_SMOKE_API_KEY="$IUSENTRA_SMOKE_API_KEY" \
IUSENTRA_SMOKE_TENANT_SLUG="$IUSENTRA_SMOKE_TENANT_SLUG" \
python scripts/smoke_backend_security.py --base-url https://app.iusentra.it --require-credentials
```

Metriche da osservare durante il rollout: 401/403 attesi sulle API sensibili
anonime, 400 `backend_security_control_param` sui tentativi di parametri
riservati, log `policy_denied.backend_security`, assenza di valori tenant/token
nelle risposte e nessun aumento dei 500.

## API contracts fase 6

Ogni modifica a endpoint React P0/P1 deve aggiornare OpenAPI, mappa contratti e
provider verification prima del deploy:

```bash
python scripts/react-migration/generate_api_contracts.py --check
python scripts/validate_openapi.py docs/openapi.yaml
python scripts/verify_openapi_provider.py
python -m pytest -q tests/test_openapi_contracts_phase6.py --tb=short
```

Il gate fallisce se un endpoint manca da `docs/openapi.yaml`, se una route P0/P1
non dichiara RBAC/tenant scope/errori, o se la risposta reale 401/400/200
campionata non rispetta il contratto documentato.

## Frontend App V2 fase 7

Ogni modifica alla shell App V2, al menu, alle route frontend o al bootstrap
utente deve eseguire il gate comune:

```bash
npm --prefix frontend run test:app-v2
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run build
python -m pytest -q tests/test_app_v2_frontend_phase7.py --tb=short
```

Il rollout resta default-off: una pagina appare nella navigazione App V2 solo
se il flag e' acceso e l'utente ha almeno un permesso coerente con l'area. I
percorsi App V2 non censiti devono mostrare 404 sicura e non devono caricare la
dashboard o chiamate dati laterali. Le route `partial` o `pending` registrate in
`docs/frontend-app-v2-pages.md` non sono promosse finche' API, mutazioni,
stati UI, browser smoke e RBAC non sono parificati.

## Requisiti e workflow fase 8

Ogni rollout App V2 deve consultare `docs/app-v2-area-requirements.md` prima
di accendere flag area per area. Monitorare per ciascuna area:

- error rate 4xx/5xx sugli endpoint indicati nel registro;
- 403/404 anomali rispetto al ruolo utente atteso;
- eventi `policy_denied` e `cross_tenant_denied`;
- tempi di primo contenuto React e latenza API dell'area;
- assenza di PII, segreti o path interni nei payload e nella UI.

Gate post-deploy fase 8:

```bash
python scripts/react-migration/generate_app_v2_area_requirements.py --check
python scripts/smoke_app_v2_workflows.py --list
python -m pytest -q tests/test_app_v2_area_requirements_phase8.py --tb=short
```

Con credenziali di ambiente:

```bash
IUSENTRA_BASE_URL=https://app.iusentra.it \
IUSENTRA_ADMIN_USER="$IUSENTRA_ADMIN_USER" \
IUSENTRA_ADMIN_PASSWORD="$IUSENTRA_ADMIN_PASSWORD" \
IUSENTRA_TENANT_A_USER="$IUSENTRA_TENANT_A_USER" \
IUSENTRA_TENANT_A_PASSWORD="$IUSENTRA_TENANT_A_PASSWORD" \
IUSENTRA_TENANT_B_USER="$IUSENTRA_TENANT_B_USER" \
IUSENTRA_TENANT_B_PASSWORD="$IUSENTRA_TENANT_B_PASSWORD" \
IUSENTRA_READONLY_USER="$IUSENTRA_READONLY_USER" \
IUSENTRA_READONLY_PASSWORD="$IUSENTRA_READONLY_PASSWORD" \
python scripts/smoke_app_v2_workflows.py --require-credentials
```

Rollback entro 2 ore: spegnere solo i flag `routes.appV2.*` dell'area
coinvolta, riavviare app/worker, verificare `/api/v1/ui/feature-flags`,
rieseguire lo smoke workflow in inventario e confermare che il fallback legacy
resti accessibile. Se il difetto non e' isolabile da flag, revertire il commit
della fase e ridistribuire.

## UI regression fase 9

Prima di attivare un flag App V2 su P0/P1 verificare anche la copertura UI:

```bash
python scripts/validate_ui_coverage.py
python -m pytest -q tests/test_ui_coverage_phase9.py --tb=short
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Checklist visuale pre-release:

- la riga in `docs/frontend-app-v2-pages.md` deve essere `ui_tested` solo se la
  route e' gia' `react_operational_full`;
- Storybook resta `non introdotto` e VRT resta `non attivo` finche' non esiste
  un comando reale eseguito;
- fixture e mock devono usare solo dati fittizi sotto `example.invalid`,
  segreti mascherati e tenant non reali;
- gli stati loading, empty, error, forbidden, flag-off, readonly e responsive
  devono restare documentati per desktop/tablet/mobile;
- se compare una regressione UI, spegnere il flag pagina, verificare lo stato
  flag-off e aprire correzione prima di aggiornare eventuali baseline future.

## Piano test fase 10

Prima del deploy App V2 eseguire o consultare il piano test generato:

```bash
python scripts/react-migration/generate_app_v2_test_docs.py --check
python scripts/smoke_app_v2_all.py --subset inventory
python scripts/smoke_app_v2_all.py --subset contracts
python -m pytest -q tests/test_app_v2_test_plan_phase10.py --tb=short
```

Per smoke completi autenticati usare solo credenziali da ambiente:

```bash
IUSENTRA_BASE_URL=https://app.iusentra.it \
IUSENTRA_ADMIN_USER="$IUSENTRA_ADMIN_USER" \
IUSENTRA_ADMIN_PASSWORD="$IUSENTRA_ADMIN_PASSWORD" \
IUSENTRA_TENANT_A_USER="$IUSENTRA_TENANT_A_USER" \
IUSENTRA_TENANT_A_PASSWORD="$IUSENTRA_TENANT_A_PASSWORD" \
IUSENTRA_TENANT_B_USER="$IUSENTRA_TENANT_B_USER" \
IUSENTRA_TENANT_B_PASSWORD="$IUSENTRA_TENANT_B_PASSWORD" \
IUSENTRA_READONLY_USER="$IUSENTRA_READONLY_USER" \
IUSENTRA_READONLY_PASSWORD="$IUSENTRA_READONLY_PASSWORD" \
python scripts/smoke_app_v2_all.py --require-credentials
```

`docs/test-plan-app-v2.md`, `docs/test-inventory.md` e
`docs/test-matrix-app-v2.md` sono la fonte operativa per distinguere test
eseguiti, gap dichiarati e smoke bloccati da credenziali mancanti.

## CI/CD e rollout safety fase 11

Prima di promuovere una release App V2 devono essere verdi i gate GitHub
documentati in `docs/ci-cd-gates.md`: `CI`, `Frontend React CI`,
`Security Supply Chain`, `CodeQL` e `Dependency Review` sulle pull request,
piu' `CI Release Overlay` quando si prepara un tag o deploy operativo.

Gate pre-release minimi:

```bash
python scripts/react-migration/generate_app_v2_test_docs.py --check
python scripts/react-migration/generate_app_v2_page_registry.py --check
python scripts/smoke_app_v2_all.py --subset inventory
python scripts/smoke_app_v2_all.py --subset contracts
python -m pytest -q tests/test_ci_cd_gates_phase11.py --tb=short
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Lo smoke ambiente vive in `.github/workflows/smoke-staging.yml` ed e' solo
manuale: usa `workflow_dispatch`, environment `staging`, artifact sanitizzati e
secrets GitHub solo quando viene selezionato `require_credentials`. Non
esegue deploy produzione e non legge segreti da pull request.

Rollout dopo deploy:

1. verificare `/api/pronto`, commit e versione container;
2. eseguire smoke anonimi `security`, `routing` e `workflows`;
3. se presenti credenziali smoke dedicate, eseguire il workflow manuale con
   `require_credentials=true`;
4. abilitare flag `routes.appV2.*` a 1%, poi 10%, 50%, 100%;
5. osservare 401/403 attesi, `policy_denied`, `cross_tenant_denied`, p95 route
   calde e assenza di testi tecnici visibili;
6. in caso di regressione spegnere il flag interessato entro 2 ore, riavviare
   app/worker e rieseguire smoke.

## Redirect legacy -> App V2 fase 4

I redirect non sono attivati globalmente. Per abilitarne uno pagina per pagina:

1. Verificare che la pagina sia in `docs/legacy-to-app-v2-routing-map.md` con
   stato `App V2 redirect ready`.
2. Accendere solo il flag `routes.appV2.*` della pagina interessata.
3. Usare `should_redirect_to_app_v2(...)` nella route legacy specifica, dopo
   autenticazione e contesto tenant, mai da un catch-all generico.
4. Preservare solo query whitelistate dal helper; `next`, `redirect`,
   `return_url`, tenant, user e token restano bloccati.
5. Eseguire smoke autenticato:

```bash
IUSENTRA_BASE_URL=https://app.iusentra.it \
IUSENTRA_SMOKE_USERNAME="$IUSENTRA_SMOKE_USERNAME" \
IUSENTRA_SMOKE_PASSWORD="$IUSENTRA_SMOKE_PASSWORD" \
python scripts/smoke_app_v2_routing.py --require-credentials
```

Rollback entro 2 ore: spegnere il flag pagina, riavviare i worker web e
verificare che la route legacy torni al template/fallback senza redirect.

## Rollback decision based on smoke failure

Stop rollout o rollback immediato se `smoke_app_v2_all.py` segnala `FAIL` su:

- autenticazione non funzionante;
- RBAC bypass o admin escalation;
- tenant isolation bypass o download cross-tenant consentito;
- secret leakage;
- open redirect critico;
- API P0 con 500;
- pagina App V2 P0 irraggiungibile con flag attivo;
- fallback flag-off rotto;
- provider/API contract P0 incoerente in modo critico.

Mitigazione rapida:

1. spegnere il feature flag `routes.appV2.*` coinvolto;
2. disabilitare redirect App V2 della pagina interessata;
3. tornare alla route legacy governata;
4. riavviare app/worker se il runtime usa env flag;
5. rieseguire `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only`;
6. monitorare `/api/pronto`, error rate, `policy_denied` e `cross_tenant_denied`;
7. aprire incident con log redatti e revertire il commit se il flag non isola il difetto.
