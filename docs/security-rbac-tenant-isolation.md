# Sicurezza RBAC e isolamento tenant

Aggiornato: 2026-05-13.

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

## Punti da estendere nelle fasi successive

- denial cross-tenant espliciti per ogni endpoint P0/P1;
- provider verification OpenAPI su 401/403/404/409/422;
- smoke CLI tenant A/B con credenziali da env;
- report finale su permessi mancanti per singola pagina App V2.
