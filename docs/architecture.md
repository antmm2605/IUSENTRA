# Architettura IUSENTRA

Aggiornato: 2026-05-14, fase 12 `fasereact`.

Questo documento e' l'handover tecnico corrente. Per dettagli storici e moduli verticali vedere anche [ARCHITETTURA](ARCHITETTURA.md).

## Stack

- Backend: Python 3.12, Flask, blueprint modulari in `web/blueprints`, bootstrap in `web/bootstrap`.
- Dominio: package `pct`, moduli `lex`, repository e servizi dedicati.
- Frontend: React 19 + Vite in `frontend`, shell compilata in `web/static/react`, UI IUSENTRA/shadcn compatibile.
- Persistenza: JSON tenant-aware sotto data root, SQLite locale per repository strutturati, PostgreSQL tenant-aware dove configurato.
- Runtime: Docker Compose locale e profilo Hetzner con app, scheduler worker, OCR worker, Redis, Caddy, audit WORM e Ollama.
- CI: GitHub Actions con gate backend/frontend/security/supply-chain descritti in [ci-cd-gates](ci-cd-gates.md).

## Flusso richiesta App V2

```text
Browser React/App V2
  -> bootstrap sessione e feature flag
  -> guard frontend RBAC/flag
  -> API client JSON
  -> Flask /api/v1/ui/*
  -> auth sessione o API key tenant-aware
  -> backend security guard
  -> tenant context fail-closed
  -> RBAC dominio
  -> service/repository layer
  -> storage tenant-safe
  -> audit/denial log quando necessario
```

## Backend Flask

`web/app.py` resta entrypoint compatibile, ma la registrazione reale vive in:

- `web/bootstrap/flask_app_factory.py`: factory, configurazione e registrazione blueprint.
- `web/bootstrap/react_route_gate.py`: gate route React/legacy.
- `web/bootstrap/runtime_bundle.py`: servizi runtime condivisi.
- `web/blueprints/api_v1_react.py`: API JSON React/App V2.
- `web/blueprints/react_shell.py`: shell React e route App V2.

Regola: ogni endpoint operativo legge il tenant dalla sessione/request context o da API key tenant-aware; il client non puo' scegliere `tenant_id` o `studio_id`.

## Frontend React/App V2

Il frontend e' in `frontend/src`. Le route sperimentali App V2 sono censite in `frontend/src/app/routes.ts`; le superfici React ufficiali convivono con le route Flask storiche.

Documenti collegati:

- [app-v2](app-v2.md)
- [app-v2-page-registry](app-v2-page-registry.md)
- [frontend-app-v2-pages](frontend-app-v2-pages.md)
- [app-v2-area-requirements](app-v2-area-requirements.md)

## Feature flag

I flag App V2 sono default-off e definiti in `web/services/feature_flags.py`. Il frontend usa la mappa compatibile in `frontend/src/lib/featureFlags.ts`. I flag servono a rollout controllato della shell `/app` e `/app-v2`; non spengono le route operative React gia' promosse nel manifest.

## Routing legacy/App V2

Il redirect legacy -> App V2 passa solo da `web/services/app_v2_routing.py`:

- target interno `/app` o `/app-v2`;
- mapping esplicito;
- query whitelistata;
- parametri `next`, `redirect`, `tenant_id`, `studio_id`, token e ruoli rimossi;
- fallback legacy o stato flag-off se il flag non e' attivo.

La mappa e' in [legacy-to-app-v2-routing-map](legacy-to-app-v2-routing-map.md).

## Sicurezza

Layer principali:

- `pct/auth.py`: utenti, ruoli e permessi.
- `web/services/auth_runtime.py`: sessione utente.
- `web/services/tenant_api_auth.py`: API key tenant-aware.
- `web/services/tenant_paths.py`: path tenant-safe.
- `web/services/tenant_isolation_runtime.py`: fail-closed multi-studio.
- `web/services/backend_security.py`: blocco parametri server-controlled sulle API React.
- `audit/`: audit WORM, chain, proof e integrazioni.

Runbook: [SECURITY](../SECURITY.md) e [security-rbac-tenant-isolation](security-rbac-tenant-isolation.md).

## API layer

La specifica e' [openapi.yaml](openapi.yaml), generata/validata con:

```powershell
python scripts\react-migration\generate_api_contracts.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
```

La mappa endpoint/pagine e' [api-endpoint-contract-map](api-endpoint-contract-map.md).

## Test strategy

La strategia e' sharded, non monolitica:

- pytest mirati per dominio, auth, tenant, security e API;
- provider verification per contratti;
- npm test/typecheck/build per frontend;
- smoke CLI per routing/workflow/security;
- CI coverage-critical con soglia esistente.

Dettagli: [test-plan-app-v2](test-plan-app-v2.md) e [ci-cd-gates](ci-cd-gates.md).

## Deploy

Il deploy produzione corrente e' manuale/governato su Hetzner CPX42:

```bash
cd /opt/iusentra/repo
IUSENTRA_SKIP_BACKUP_CRON=1 bash deploy/hetzner/deploy.sh
```

Il deploy deve essere seguito da `/api/pronto`, container healthy e smoke. Vedere [release-rollout](release-rollout.md), [DEPLOY_HETZNER_CPX42](DEPLOY_HETZNER_CPX42.md) e [deploy/hetzner README](../deploy/hetzner/README.md).
