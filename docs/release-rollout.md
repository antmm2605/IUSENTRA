# Release rollout App V2

Aggiornato: 2026-05-13.

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
