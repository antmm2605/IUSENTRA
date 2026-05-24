# CI/CD gates IUSENTRA

Aggiornato: 2026-05-24, branch protection e verifica CI reale sullo SHA corrente.

## Obiettivo

Questa mappa rende espliciti i gate che proteggono App V2, sicurezza backend,
contratti API, frontend React, coverage critica e rollout. I job indicati come
`Bloccante` devono fallire pull request o push quando il comando fallisce. I
job manuali o nightly non sostituiscono i gate PR: coprono verifiche pesanti,
ambiente esterno o credenziali smoke.

## Workflow inventory

| Workflow | Trigger | Job | Comando | Bloccante | Stato | Note |
| --- | --- | --- | --- | --- | --- | --- |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `Lint + syntax` | `tools/sync_packaging_files.py --check`, OpenAPI/provider, App V2 registry/test plan, RBAC tenant gates, frontend test/typecheck/build, ruff, flake8, compile | si | required | Gate principale PR/push. |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `Governance repo` | `python tools/check_repo_governance.py` | si | required | Blocca regressioni su confini e modularita. |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `Smoke test Flask` | import `create_app`, login smoke | si | required | Verifica bootstrap runtime senza scheduler web. |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `Smoke scheduler worker` | avvio `start_scheduler_worker(...)` con data root temporaneo | si | required | Verifica worker dedicato e job minimi. |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `Pytest core fase */10` | `python scripts/run_pytest_phases.py --core-shard ...` | si | required | Shard core senza monolitico opaco. |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `Coverage moduli critici parte */12` | `run_pytest_phases.py --suite coverage-critical --suite-shard ...` | si | required | Le 12 parti sono il gate richiesto; il vecchio aggregatore senza `parte` non è required. Artifact coverage shard. |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `E2E smoke` | `python scripts/run_pytest_phases.py --suite e2e-smoke` | si | required | Smoke Python stabile, non browser esterno. |
| `.github/workflows/ci.yml` | push, pull_request, workflow_dispatch | `Local Signer e PKCS#11` | `run_pytest_phases.py --suite signer` su Linux/Windows/macOS | si | required | Matrice cross-platform. |
| `.github/workflows/frontend-ci.yml` | push, pull_request, workflow_dispatch | `Frontend React contratti/typecheck/build` | `pnpm install --frozen-lockfile`, `pnpm --filter @iusentra/studio test`, `pnpm --filter @iusentra/studio typecheck`, `pnpm --filter @iusentra/studio build:vite` | si | required | Shard rapido dedicato al frontend, senza path filter: il check richiesto non può mancare. |
| `.github/workflows/ci_quality_overlay.yml` | push, pull_request, workflow_dispatch | `quality-gates` | governance, packaging, python baseline, Local Signer boundaries, Lex gates, performance budget | si | required | Overlay qualita mirato. |
| `.github/workflows/ci_quality_overlay.yml` | push, pull_request, workflow_dispatch | `targeted-tests` | `run_pytest_phases.py --suite quality-overlay` | si | required | Shard overlay. |
| `.github/workflows/ci-required-gates.yml` | push, pull_request, workflow_dispatch | `CI reale eseguita sul commit corrente` | `python tools/check_github_required_gates.py --wait ...` | si | required | Attende i check dello SHA corrente, fallisce su mancanti, in corso, failure, skipped/cancelled non ammessi e produce report JSON/Markdown automatico. |
| `.github/workflows/ci_release_overlay.yml` | workflow_dispatch | `release-readiness` | `tools/check_release_readiness.py`, `run_pytest_phases.py --suite release-readiness` | manuale | optional/manual | Da eseguire prima di tag o deploy operativo. |
| `.github/workflows/codeql.yml` | push, pull_request, schedule | `Analyze (python)` | CodeQL init/autobuild/analyze | si | required | SAST GitHub, policy High/Critical su code scanning. |
| `.github/workflows/dependency-review.yml` | pull_request | `Review dipendenze in ingresso` | `actions/dependency-review-action@v4` | si | required | Blocca dependency review configurata da GitHub. |
| `.github/workflows/security-supply-chain.yml` | push, pull_request, workflow_dispatch, schedule | `Audit dipendenze Python` | `pip-audit -r requirements.txt --format json --output pip-audit.json` | si | required | Report artifact, nessun segreto. |
| `.github/workflows/security-supply-chain.yml` | push, pull_request, workflow_dispatch, schedule | `Audit dipendenze frontend` | `pnpm --filter @iusentra/studio audit --audit-level=critical --prod --json` | si | required | Fallisce su critical production dependency. |
| `.github/workflows/security-supply-chain.yml` | push, pull_request, workflow_dispatch, schedule | `Generate SBOM` | `anchore/sbom-action@v0` | si | required | Artifact SBOM SPDX. |
| `.github/workflows/e2e-nightly.yml` | schedule, workflow_dispatch | `E2E full suite` | `run_pytest_phases.py --suite e2e-nightly` | no PR | nightly/manual | Verifica ampia non sostitutiva. |
| `.github/workflows/performance-nightly.yml` | schedule, workflow_dispatch | `Benchmark runtime leggero` | `tools/performance_smoke.py --strict` | no PR | nightly/manual | Artifact performance JSON. |
| `.github/workflows/smoke-staging.yml` | workflow_dispatch | `Smoke ambiente` | `smoke_app_v2_all.py --suite post-deploy --read-only --json-output artifacts/smoke/smoke-report.json` su ambiente indicato | manuale/post-deploy | optional/manual | Usa environment `staging`; credenziali solo da secrets se richieste; artifact JSON redatto. |
| `.github/workflows/deploy-hetzner.yml` | push branch operativi, workflow_dispatch | `Deploy su Hetzner CPX42` | `check_github_required_gates.py --wait`, poi deploy SSH e smoke `/api/pronto` | operativo post-CI | deploy required | Il deploy automatico non parte finché i required checks dello SHA corrente non sono verdi; `[no-backup]` salta solo il backup preventivo. |
| `.github/workflows/sync-claude-to-codex.yml` | push branch gemelli, workflow_dispatch | `sync-peer-branch` | `git push origin HEAD:<branch-gemello> --force` | operativo | required repo hygiene | Solo mirror branch ammessi, non quality gate. |

## Gate bloccanti

- Il processo operativo da seguire prima di dichiarare chiusa una consegna è in `docs/COMMIT_PUSH_REQUIRED_GATES.md`. La checklist comprende CodeQL, code scanning, dependency review, supply chain, governance, lint, smoke, Frontend React, Coverage 12/12, Pytest core shardato, Local Signer/PKCS#11 su macOS/Ubuntu/Windows e CI Quality Overlay su `push` e, quando esiste una PR, su `pull_request`.
- La fonte versionata dei required checks è `.github/required-checks.json`; `tools/check_github_required_gates.py` la usa sia per il report automatico sia per applicare/verificare branch protection sui due branch operativi.
- Il gate `CI Required Gates / CI reale eseguita sul commit corrente` non sostituisce gli shard: li attende e fallisce se un required check è assente, ancora in corso, fallito, skipped/cancelled o non eseguito sullo SHA corrente.
- La branch protection usa required checks stretti per merge/PR. `enforce_admins=false` resta intenzionale per compatibilità con il flusso operativo autorizzato di push diretto sui soli branch gemelli; la consegna resta vietata finché lo SHA pushato non supera il report automatico e il deploy post-CI.
- Gli aggregatori ancora presenti, come `CI / Pytest core` e `CI / Local Signer e PKCS#11`, sono riepiloghi: la diagnosi primaria è lo shard reale. Se qualcosa è `Skipped`, controllare prima `Lint + syntax`, `Governance repo` e smoke upstream.
- Il check aggregatore storico `CI / Coverage moduli critici` senza `parte` è stato eliminato e non deve essere reintrodotto come blocco PR, riepilogo canonico o required check: la coverage critica è governata dalle 12 parti `Coverage moduli critici parte */12`.
- Se un aggregatore legacy resta visibile per compatibilità di dashboard o storico GitHub, è solo advisory: va annotato nella memoria operativa con lo stato degli shard reali e non può guidare da solo diagnosi, branch protection o chiusura della consegna.
- Lo status esterno `Vercel` non è un gate di qualità IUSENTRA per questi branch: il deploy reale è Hetzner. Il report generato lo classifica come status esterno ignorato, separato dai check GitHub Actions e CodeQL/security. Se Vercel resta `failure`, non usare il combined status GitHub come diagnosi grezza senza questa separazione.

- Backend: install ripetibile Python, import/syntax, lint fatal, smoke Flask, scheduler worker, shard core pytest.
- Sicurezza backend: `tests/test_auth.py`, `tests/test_backend_security_phase5.py`, `tests/test_tenant_isolation_runtime.py`, `tests/test_app_v2_feature_flags.py`, `tests/test_app_v2_routing.py`.
- Contratti API: `generate_api_contracts.py --check`, `validate_openapi.py`, `verify_openapi_provider.py`, `smoke_app_v2_all.py --subset contracts`, `tests/test_openapi_contracts_phase6.py`.
- Frontend: `pnpm install --frozen-lockfile`, `pnpm --filter @iusentra/studio test`, `pnpm --filter @iusentra/studio typecheck`, `pnpm --filter @iusentra/studio build` o `build:vite`.
- Feature flag/registry: `generate_app_v2_page_registry.py --check`, `generate_app_v2_test_docs.py --check`, `generate_app_v2_area_requirements.py --check`, `validate_ui_coverage.py`.
- Coverage: `coverage-critical` shardata in 12 parti richieste; il vecchio report aggregato senza `parte` non deve tornare blocco PR.
- Pipeline lifecycle procedurale: quando si toccano inventario XSD/PST, mapping, fonti, schede, workflow, firma, deposito, ricevute, notifiche o audit, eseguire lo shard mirato `tests/test_procedure_inventory_importer.py tests/test_procedure_xsd_mapper.py tests/test_procedure_source_research.py tests/test_procedure_knowledge_pipeline.py tests/test_procedure_lifecycle.py tests/test_digital_signature_workflow.py tests/test_telematic_deposit_workflow.py tests/test_post_acceptance_obligations.py tests/test_notification_workflow.py tests/test_evidence_vault.py tests/test_procedure_coverage_ext.py tests/test_procedure_lifecycle_repository.py tests/test_procedure_lifecycle_edges.py` e la coverage dedicata `config/coverage-procedure-lifecycle.ini`.
- SAST/dependency: CodeQL, dependency review, `pip-audit`, `pnpm --filter @iusentra/studio audit --audit-level=critical`.

## Gate informativi, manuali e nightly

- `CI Release Overlay`: manuale, da usare prima di release o deploy operativo.
- `Smoke Staging`: manuale/post-deploy, usa l'orchestrator fase 13 in modalita read-only; richiede environment protetto e, per profili autenticati, secrets dedicati.
- `E2E Nightly`: nightly/manuale, copre flussi piu' lunghi.
- `Performance Nightly`: nightly/manuale, produce baseline runtime.
- Storybook: presente come infrastruttura frontend, non dichiarato gate visuale completo. VRT: non attivo.

## Artifact

| Artifact | Workflow | Contenuto | Retention | Sicurezza |
| --- | --- | --- | --- | --- |
| `coverage-critical-*` | `ci.yml` | frammenti `.coverage` per shard critici | default GitHub | Nessun dato runtime studio. |
| `pip-audit-report` | `security-supply-chain.yml` | report JSON audit Python | 14 giorni | Nessun segreto. |
| `frontend-pnpm-audit-report` | `security-supply-chain.yml` | report JSON audit pnpm production deps | 14 giorni | Nessun segreto. |
| `sbom` | `security-supply-chain.yml` | SBOM SPDX JSON | default GitHub | Inventario dipendenze, non contiene credenziali. |
| `current-sha-required-gates` | `ci-required-gates.yml` | Report Markdown/JSON dei required checks sullo SHA corrente | 14 giorni | Nomi check, esiti e URL GitHub; nessun dato cliente. |
| `performance-smoke` | `performance-nightly.yml` | tempi benchmark runtime leggero | default GitHub | Nessun dato cliente. |
| `smoke-staging-reports` | `smoke-staging.yml` | log sanitizzati e `smoke-report.json` ambiente | 14 giorni | Password/token redatti da `smoke_lib.py`; nessun contenuto documento o payload completo. |

## Required Secrets and Environment Variables

| Nome | Uso | PR/push | Manuale | Valore incluso | Note sicurezza |
| --- | --- | --- | --- | --- | --- |
| `IUSENTRA_BASE_URL` | URL smoke ambiente | no | si, input workflow | no | Default manuale: `https://app.iusentra.it`. |
| `IUSENTRA_ADMIN_USER` | smoke autenticato admin | no | opzionale | no | Solo environment GitHub protetto. |
| `IUSENTRA_ADMIN_PASSWORD` | smoke autenticato admin | no | opzionale | no | Mai stampare nei log. |
| `IUSENTRA_TENANT_A_USER` | smoke tenant A | no | opzionale | no | Usare account smoke dedicato. |
| `IUSENTRA_TENANT_A_PASSWORD` | smoke tenant A | no | opzionale | no | Mai usare credenziali personali. |
| `IUSENTRA_TENANT_B_USER` | smoke tenant B | no | opzionale | no | Serve a verificare tenant isolation. |
| `IUSENTRA_TENANT_B_PASSWORD` | smoke tenant B | no | opzionale | no | Mai stampare nei log. |
| `IUSENTRA_READONLY_USER` | smoke profilo sola lettura | no | opzionale | no | Verifica RBAC UI/API. |
| `IUSENTRA_READONLY_PASSWORD` | smoke profilo sola lettura | no | opzionale | no | Mai stampare nei log. |
| `IUSENTRA_SMOKE_API_KEY` | smoke API key tenant-aware | no | opzionale | no | Solo chiave smoke a basso privilegio. |
| `IUSENTRA_SMOKE_TENANT_SLUG` | tenant associato API key smoke | no | opzionale | no | Non abilita cross-tenant. |

I workflow su pull request non usano secrets sensibili e non usano
`pull_request_target`. Le smoke autenticate falliscono se richieste senza env:
questo evita falsi verdi.

## Rollout safety

Prima del rollout:

1. CI PR/push verde sui gate required.
2. `CI Release Overlay` manuale verde per release operative.
3. Deploy staging o produzione tramite procedura esistente, non automatica da PR.
4. `Smoke Staging` manuale almeno senza credenziali; con credenziali quando l'ambiente le espone.
5. Feature flag `routes.appV2.*` default-off.

Progressione consigliata:

| Step | Azione | Gate |
| --- | --- | --- |
| 1% | tenant pilota o studio interno | smoke post-deploy, error rate, p95 route rappresentative |
| 10% | pochi studi operativi | nessun 500, nessun 403 inatteso, nessun cross-tenant |
| 50% | studi rappresentativi | provider verification e log `policy_denied` coerenti |
| 100% | default operativo | CI e smoke ambiente verdi, rollback ancora possibile |

Rollback entro 2 ore:

1. spegnere il flag `routes.appV2.*` coinvolto;
2. riavviare app e worker;
3. verificare `/api/v1/ui/feature-flags` e `/api/pronto`;
4. rieseguire smoke routing/workflows;
5. se il difetto non e' isolabile da flag, revertire commit e ridistribuire.

## Recommended Required Checks

- `CI Required Gates / CI reale eseguita sul commit corrente`
- `CI / Lint + syntax`
- `CI / Governance repo`
- `CI / Smoke test Flask`
- `CI / Smoke scheduler worker`
- `CI / Pytest core`
- `CI / Coverage moduli critici parte 1/12` fino a `parte 12/12`
- `CI / E2E smoke`
- `CI / Local Signer e PKCS#11`
- `CI / Local Signer e PKCS#11 (macos-latest) parte 1/4` fino a `parte 4/4`
- `CI / Local Signer e PKCS#11 (ubuntu-latest) parte 1/4` fino a `parte 4/4`
- `CI / Local Signer e PKCS#11 (windows-latest) parte 1/4` fino a `parte 4/4`
- `Frontend React CI / Frontend React contratti`
- `Frontend React CI / Frontend React typecheck`
- `Frontend React CI / Frontend React build`
- `Frontend React CI / Frontend React CI`
- `CI Quality Overlay / quality-gates`
- `CI Quality Overlay / Targeted tests parte 1/3` fino a `parte 3/3`
- `CI Quality Overlay / Targeted tests`
- `CodeQL / Analyze (python)`
- `Code scanning results / CodeQL`
- `Dependency Review / Review dipendenze in ingresso`
- `Security Supply Chain / Audit dipendenze Python`
- `Security Supply Chain / Audit dipendenze frontend`
- `Security Supply Chain / Generate SBOM`

Manuali o nightly, non required PR:

- `CI Release Overlay / release-readiness`
- `Smoke Staging / Smoke ambiente`
- `E2E Nightly / E2E full suite`
- `Performance Nightly / Benchmark runtime leggero`

I gate da non disattivare senza incident review sono: RBAC/tenant isolation,
provider verification, OpenAPI validation, frontend build, backend security,
coverage-critical e dependency critical.

## Gap residui

1. Storybook è presente come infrastruttura, ma non è copertura visuale completa; VRT resta gap documentato, non gate fittizio.
2. Smoke autenticati richiedono secrets GitHub dedicati e account smoke reali.
3. `pip-audit` non ha baseline legacy: il job è bloccante su stato corrente e può richiedere triage se emergono CVE transitive.
4. Deploy produzione resta operativo post-push: non è un sostituto dei gate qualità e viene verificato dopo che lo SHA ha superato i check GitHub.

## Fase 12 - Documentazione e handover

La fase 12 aggiunge due gate locali leggeri per evitare drift documentale:

```powershell
python scripts\validate_docs_links.py
python scripts\validate_docs_commands.py
```

Questi comandi non sostituiscono CI, OpenAPI, provider verification o test: verificano solo che i link locali e i comandi/script citati nei documenti handover puntino a file reali e script frontend esistenti. Possono essere aggiunti a CI in una PR successiva se il rumore resta basso.

## Fase 13 - Smoke operativo

L'orchestrator operativo e' `scripts/smoke_app_v2_all.py`. Le suite principali
sono `health`, `auth`, `flags`, `rbac`, `tenant`, `routing`, `api`, `pages`,
`workflows`, `documents`, `admin`, `search`, `notifications` e `post-deploy`.
I vecchi `--subset inventory|contracts|routing|workflows` restano alias
compatibili.

Comando manuale consigliato:

```powershell
python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url https://app.iusentra.it --json-output artifacts\smoke\smoke-report.json
```

`BLOCKED` e `SKIP` non sono successi mascherati: indicano env o ID test assenti
e vanno riportati nella release. Con `--require-credentials` le suite bloccate
da credenziali mancanti falliscono.
