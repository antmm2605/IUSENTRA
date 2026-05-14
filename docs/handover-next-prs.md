# Handover e prossime PR

Aggiornato: 2026-05-14, fase 14 `fasereact`.

## Stato finale corrente

Completato:

- Registry App V2, feature flag default-off, routing sicuro, backend security, OpenAPI/provider verification, frontend App V2 gates, requisiti area, UI coverage leggera, test plan, CI/CD gates e documentazione handover.
- Deploy Hetzner manuale governato e smoke anonimi documentati.
- Documenti principali indicizzati in [index](index.md).

Pending:

- Smoke orchestrator fase 13 disponibile e rieseguito in fase 14; restano da configurare profili smoke tenant A/B/readonly in environment con secrets dedicati.
- Provider verification success-body completa per endpoint parametrici/upload/mutazioni.
- VRT/browser screenshot regression stabile.

Blocked:

- Servizi telematici non parificati: portali ministeriali, download, allegati, export e workflow tecnici restano legacy/protetti finche' non hanno parita React completa.

## Prossima PR consigliata

| Titolo | Obiettivo | Priorita | File/Aree | Criteri Accettazione | Test | Rollback |
| --- | --- | --- | --- | --- | --- | --- |
| Credenziali smoke staging App V2 | Configurare account smoke admin, tenant A, tenant B, readonly, API key smoke e ID documento sintetico in environment protetto, senza segreti nel repository. | P0 | `.github/workflows/smoke-staging.yml`, environment/secrets GitHub, `docs/smoke-tests.md` | Workflow manuale verde con `--require-credentials`; nessun segreto nei log; denial readonly/admin, tenant cross-check e download documento sintetico documentati. | `python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --require-credentials --base-url <staging>` e workflow manuale GitHub. | Rimuovere secrets/profili smoke dall'environment e tornare agli smoke read-only anonimi. |

Le altre idee restano backlog nel risk register: provider fixture parametriche, VRT leggera, osservabilita rollout e tranche telematiche dedicate. Non sono la PR immediata consigliata dalla chiusura fase 14.

## Regole per le PR

- Una responsabilita per PR.
- Nessuna mega PR.
- Ogni PR deve indicare rollback.
- Ogni PR che tocca UI deve includere browser check se user-facing.
- Ogni PR che tocca API deve aggiornare OpenAPI/provider verification o dichiarare limite motivato.
- Ogni PR che tocca dati deve documentare tenant isolation e migrazione/rollback.
