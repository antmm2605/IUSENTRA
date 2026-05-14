# Release notes tecniche App V2

Aggiornato: 2026-05-14, fase 13 `fasereact`.

## Sintesi

Le fasi `fasereact` 1-13 hanno consolidato la governance App V2: registro pagine, priorita, feature flag default-off, routing sicuro, backend security, OpenAPI/provider verification, frontend gates, requisiti area, UI regression leggera, test plan, CI/CD gates, documentazione handover e smoke operativi post-deploy.

## Aree impattate

- React/App V2 shell e route censite.
- API `/api/v1/ui/*` e contratti OpenAPI.
- Feature flag `routes.appV2.*`.
- CI GitHub Actions e smoke manuali.
- Orchestrator smoke fase 13 e report JSON redatti.
- Documentazione operativa, sicurezza e release.

## Smoke readiness 2.234.0

- `scripts/smoke_app_v2_all.py` supporta `--suite post-deploy --read-only`,
  output JSON, exit code affidabile e alias storici `--subset`.
- `scripts/smoke_lib.py` centralizza HTTP, redaction, severity e summary.
- `.github/workflows/smoke-staging.yml` produce artifact `smoke-report.json`.
- `docs/smoke-tests.md` e `docs/release-readiness-checklist.md` sono le fonti operative.

## Feature flag

Tutti i flag App V2 sperimentali restano default-off. L'accensione avviene per ambiente/tenant controllato, con rollback spegnendo il flag e riavviando app/worker.

## Sicurezza

- Backend auth/RBAC/tenant restano autoritativi.
- Parametri server-controlled dal client sono bloccati sulle API React.
- Denial e audit non devono includere segreti o payload sensibili.
- Smoke autenticati richiedono secrets dedicate, non presenti nel repository.

## API contracts

OpenAPI e mappa endpoint sono governate da:

```powershell
python scripts\react-migration\generate_api_contracts.py --check
python scripts\validate_openapi.py docs\openapi.yaml
python scripts\verify_openapi_provider.py
```

## Test e CI

Gate principali:

- backend security/RBAC/tenant;
- OpenAPI/provider verification;
- registry/test plan generated checks;
- frontend test/typecheck/build;
- coverage-critical;
- e2e-smoke;
- supply-chain audit.

Storybook, VRT e Playwright/Cypress non sono presenti e non vengono dichiarati passati.

## Rollout

Usare [release-rollout](release-rollout.md). Progressione consigliata: 1%, 10%, 50%, 100%, con smoke post-deploy e monitoraggio errori/denial/p95.

## Rollback

Rollback preferito: spegnere il flag App V2 coinvolto, riavviare app/worker, verificare `/api/v1/ui/feature-flags`, `/api/pronto` e smoke. Se il bug non e' isolabile da flag, revertire il commit e ridistribuire.

## Known issues

1. Smoke autenticati bloccati da assenza env/secrets dedicate.
2. VRT/screenshot regression non presente.
3. Provider success-body full ancora da estendere su endpoint parametrici/upload.
4. Servizi telematici ministeriali non parificati restano blocked/legacy-first.

## Pending items

Vedere [handover-next-prs](handover-next-prs.md) e [risk-register](risk-register.md).
