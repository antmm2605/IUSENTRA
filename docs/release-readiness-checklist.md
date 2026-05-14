# Release readiness checklist

Aggiornato: 2026-05-14, fase 14 `fasereact`.

Questa checklist e' operativa: non va marcata completa nel repository. Ogni
release deve copiarla nel ticket/release note e spuntarla con esiti reali.

## Esito fase 14 - 2026-05-14

Decisione: GO WITH WARNINGS per `2.235.1`.

| Voce | Stato | Evidenza |
| --- | --- | --- |
| CI local equivalent | PASS | Workflow YAML parse OK, Python baseline, governance, Ruff, mypy, flake8 e gate locali eseguiti. |
| Backend tests | PASS | Smoke/release/OpenAPI/packaging 28/28; auth/security/tenant/flags/routing 70/70; release-readiness, quality-overlay, e2e-smoke e coverage-critical verdi. |
| Frontend tests | PASS | `npm --prefix frontend run test`. |
| Frontend typecheck/build | PASS | `npm --prefix frontend run typecheck`; `npm --prefix frontend run build`. |
| OpenAPI validation | PASS | `python scripts\validate_openapi.py docs\openapi.yaml`. |
| Provider verification | PASS | 182 auth-error, 27 success sample, 1 guardrail backend security. |
| RBAC tests | PASS | Pytest locali pass; smoke readonly autenticato BLOCKED per credenziali mancanti. |
| Tenant isolation tests | PASS | Pytest locali pass; cross-tenant smoke autenticato BLOCKED per assenza API key/profili. |
| Feature Flag tests | PASS | Flag App V2 con default rollout operativo, route flag registrati e rollback esplicito. |
| Routing tests | PASS | No open redirect negli smoke; fallback coerenti. |
| Smoke scripts | PASS | Help/py_compile, contracts locale PASS=7, post-deploy locale PASS=76 FAIL=0. |
| Browser reale | PASS | Desktop/mobile su `/app-v2/messaggi/nuovo`: nessun blocco "Funzione non attiva", redirect login corretto, console pulita. |
| SAST/security | PASS/BLOCKED | `pip-audit`, `npm audit` e secret scan high-confidence PASS; `gitleaks` non installato localmente. |
| Storybook/UI/VRT | PASS/BLOCKED | UI coverage leggera PASS; Storybook/VRT non presenti e non dichiarati passati. |
| Docs validation | PASS | Link e comandi docs validati. |
| Secrets scan | PASS | 5213 file, 0 finding high-confidence. |
| Rollback | PASS | Procedura in `docs/final-release-report.md` e `docs/release-rollout.md`. |
| Rischi residui | PASS con warning | Solo gap ambiente/tool: smoke autenticati, VRT/Storybook, GitHub Actions post-push. |

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
- [ ] Feature Flag rollout/rollback verificato.
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
