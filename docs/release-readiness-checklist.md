# Release readiness checklist

Aggiornato: 2026-05-14, fase 13 `fasereact`.

Questa checklist e' operativa: non va marcata completa nel repository. Ogni
release deve copiarla nel ticket/release note e spuntarla con esiti reali.

## Pre-release

- [ ] CI verde.
- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Frontend build pass.
- [ ] OpenAPI validation pass.
- [ ] Provider verification pass.
- [ ] RBAC tests pass.
- [ ] Tenant isolation tests pass.
- [ ] Feature Flag tests pass.
- [ ] Security/SAST pass o gap documentato.
- [ ] Storybook/UI tests pass se presenti; se assenti, gap dichiarato.
- [ ] Smoke local pass o blocchi documentati.
- [ ] Smoke staging pass prima rollout.
- [ ] Feature Flag default off verificato.
- [ ] Rollback verificato.
- [ ] Docs aggiornate.

## Pre-rollout 1%

- [ ] Feature Flag target configurato.
- [ ] `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only` pass.
- [ ] Metriche baseline raccolte.
- [ ] Alert attivi o monitoraggio manuale definito.
- [ ] Responsabile rollback definito.

## Rollout 10/50/100

- [ ] Error rate ok.
- [ ] 401/403/404 non anomali.
- [ ] `policy_denied` non anomalo.
- [ ] `cross_tenant_denied` non anomalo.
- [ ] p95 ok.
- [ ] Smoke pass.
- [ ] Nessun ticket critico.

## Rollback

- [ ] Spegnere flag.
- [ ] Disabilitare redirect.
- [ ] Tornare legacy.
- [ ] Rieseguire smoke.
- [ ] Verificare metriche.
- [ ] Documentare incident.
