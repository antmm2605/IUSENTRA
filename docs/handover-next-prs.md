# Handover e prossime PR

Aggiornato: 2026-05-14, fase 12 `fasereact`.

## Stato finale corrente

Completato:

- Registry App V2, feature flag default-off, routing sicuro, backend security, OpenAPI/provider verification, frontend App V2 gates, requisiti area, UI coverage leggera, test plan, CI/CD gates e documentazione handover.
- Deploy Hetzner manuale governato e smoke anonimi documentati.
- Documenti principali indicizzati in [index](index.md).

Pending:

- Smoke autenticati tenant A/B/readonly in ambiente con secrets dedicati.
- Provider verification success-body completa per endpoint parametrici/upload/mutazioni.
- VRT/browser screenshot regression stabile.

Blocked:

- Servizi telematici non parificati: portali ministeriali, download, allegati, export e workflow tecnici restano legacy/protetti finche' non hanno parita React completa.

## Prossime PR consigliate

| PR | Titolo | Obiettivo | Priorita | File/Aree | Criteri Accettazione |
| --- | --- | --- | --- | --- | --- |
| 1 | Smoke autenticati staging App V2 | Configurare account smoke admin, tenant A, tenant B e readonly in environment protetto e rendere ripetibile `smoke-staging.yml`. | P0 | `.github/workflows/smoke-staging.yml`, `scripts/smoke_app_v2_*`, docs smoke | Workflow manuale verde con `require_credentials=true`, nessun segreto nei log, tenant cross-check documentato. |
| 2 | Provider fixture P0 parametrici | Estendere provider verification success-body su endpoint P0 con path parametrici e upload sicuri. | P0 | `scripts/verify_openapi_provider.py`, fixture test, `docs/api-*` | Endpoint scelti passano 200 autenticato con fixture tenant-safe; OpenAPI e test verdi. |
| 3 | Visual regression leggera | Aggiungere Playwright screenshot o runner equivalente per pagine P0 rappresentative. | P1 | frontend test, CI, `docs/ui-regression-and-storybook.md` | Baseline desktop/tablet/mobile, comando CI reale, nessuna PII nei fixture. |
| 4 | Servizi telematici App V2 tranche | Parificare una sola superficie telematica alla volta, partendo da workflow non ministeriale ad alto valore. | P1 | `frontend/src/components/TelematicoSurfacePage.tsx`, API telematiche, docs/specs | Dati reali, RBAC, tenant, Local Signer, browser smoke e rollback legacy. |
| 5 | Osservabilita rollout | Collegare metriche p95/error rate/denial a dashboard o export operativo. | P2 | monitoring, docs osservabilita, runbook | Metriche visibili senza PII e smoke post-deploy con report allegabile. |

## Regole per le PR

- Una responsabilita per PR.
- Nessuna mega PR.
- Ogni PR deve indicare rollback.
- Ogni PR che tocca UI deve includere browser check se user-facing.
- Ogni PR che tocca API deve aggiornare OpenAPI/provider verification o dichiarare limite motivato.
- Ogni PR che tocca dati deve documentare tenant isolation e migrazione/rollback.
