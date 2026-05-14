# Smoke test IUSENTRA

Aggiornato: 2026-05-14, fase 13 `fasereact`.

## Overview

Lo smoke operativo principale e' `scripts/smoke_app_v2_all.py`. Il runner e'
read-only di default in staging/produzione, non invia PEC, push o comunicazioni
reali, non crea dati permanenti e redige password, token e API key nei messaggi
e nei report JSON.

Comando base:

```powershell
python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url https://app.iusentra.it
```

## Inventario script

| Script | Scopo | Env richieste | Locale | Staging | Distruttivo | Exit Code | Stato |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `scripts/smoke_app_v2_all.py` | Orchestratore unico fase 13: health, auth, flag, RBAC, tenant, routing, API, pagine, workflow, documenti, admin, ricerca, notifiche e post-deploy. | `IUSENTRA_BASE_URL`; credenziali solo per suite autenticate. | si | si | no in `--read-only` | non-zero su FAIL | ready |
| `scripts/smoke_lib.py` | Libreria comune per HTTP, redaction, risultato, summary e JSON report. | nessuna | si | si | no | usata dal runner | ready |
| `scripts/smoke_backend_security.py` | Readiness, API sensibili anonime bloccate e `tenant_id` forzato con API key smoke se disponibile. | opzionali `IUSENTRA_SMOKE_API_KEY`, `IUSENTRA_SMOKE_TENANT_SLUG` | si | si | no | non-zero su KO | ready |
| `scripts/smoke_app_v2_pages.py` | Inventario manifest e smoke pagine App V2 storico. | opzionali `IUSENTRA_SMOKE_USERNAME`, `IUSENTRA_SMOKE_PASSWORD` | si | si | no | non-zero su KO | consolidated |
| `scripts/smoke_app_v2_routing.py` | Routing, whitelist query, open redirect e flag-off storico. | opzionali `IUSENTRA_SMOKE_USERNAME`, `IUSENTRA_SMOKE_PASSWORD` | si | si | no | non-zero su KO | consolidated |
| `scripts/smoke_app_v2_workflows.py` | Inventario e smoke P0/P1 per profili configurati. | `IUSENTRA_ADMIN_*`, `IUSENTRA_TENANT_A_*`, `IUSENTRA_TENANT_B_*`, `IUSENTRA_READONLY_*` per auth completo | si | si | no | non-zero su KO | consolidated |
| `scripts/validate_docs_links.py` | Link locali documentazione. | nessuna | si | si | no | non-zero su link rotto | ready |
| `scripts/validate_docs_commands.py` | Comandi/path documentati contro file reali e npm scripts. | nessuna | si | si | no | non-zero su comando non valido | ready |
| `scripts/validate_openapi.py` | Validazione OpenAPI. | nessuna | si | si | no | non-zero su schema invalido | ready |
| `scripts/verify_openapi_provider.py` | Provider verification OpenAPI con fixture locali tenant-safe. | nessuna | si | CI | no | non-zero su contratto rotto | ready |
| `scripts/validate_ui_coverage.py` | Copertura UI leggera App V2. | nessuna | si | CI | no | non-zero su regressione | ready |
| `scripts/audit_smoke_test.py` | Smoke audit probatorio dedicato. | env audit locale se richiesta dal runtime | si | no generico | no se read-only | non-zero su KO | ready |

## Suite orchestrator

| Suite | Cosa verifica | Severita critica | Env richieste | Stato |
| --- | --- | --- | --- | --- |
| `health` | `/api/pronto`, shell base, assenza 500/stack trace. | app non raggiungibile | `IUSENTRA_BASE_URL` | ready |
| `auth` | anonimo negato, credenziali invalide, login profili se env presenti. | bypass auth | profili `IUSENTRA_*_USER/PASSWORD` opzionali | ready, auth completo blocked senza env |
| `flags` | default-off da sorgente, route flag registrate, endpoint flag protetto. | flag off bypass o flag mancante | opzionale `IUSENTRA_FEATURE_FLAGS_EXPECTED` | ready |
| `rbac` | readonly negato su admin se profilo disponibile, mutating smoke saltato in read-only. | admin/RBAC bypass | `IUSENTRA_READONLY_*` per check auth | ready, blocked senza env |
| `tenant` | anonimo bloccato, `tenant_id` forzato con API key se disponibile. | leakage cross-tenant | opzionali `IUSENTRA_SMOKE_API_KEY`, `IUSENTRA_SMOKE_TENANT_SLUG` | ready, auth cross-tenant blocked senza env |
| `routing` | whitelist query, flag-off fail-closed, redirect esterni negati. | open redirect | `IUSENTRA_BASE_URL` | ready |
| `api` | OpenAPI, provider verification, API sensibili protette. | API P0/contratto rotto | nessuna | ready |
| `pages` | App V2 e pagine rappresentative raggiungibili o redirect/403 coerenti. | P0 irraggiungibile con stato inatteso | `IUSENTRA_BASE_URL` | ready |
| `workflows` | legacy/API/App V2 P0/P1 senza 500; auth completo se profili presenti. | workflow P0 500 | profili opzionali | ready |
| `documents` | documenti/redazione/template/API template; download test se ID presente. | download cross-tenant consentito | opzionali `IUSENTRA_TEST_DOCUMENT_ID`, `IUSENTRA_TENANT_A_DOCUMENT_ID` | ready, download blocked senza ID |
| `admin` | utenti/profili/database e API admin database. | admin API esposta | `IUSENTRA_BASE_URL` | ready |
| `search` | ricerca studio/legale/API ricerca; tenant-safe auth se profili presenti. | ricerca cross-tenant sospetta | profili opzionali | ready |
| `notifications` | pagine notifiche e public-key push senza invio reale. | private key/leakage | nessuna | ready |
| `post-deploy` | tutte le suite read-only da usare dopo deploy. | qualunque FAIL critico | env ambiente, credenziali opzionali | ready |

## Comandi principali

```powershell
python scripts\smoke_app_v2_all.py --help
python scripts\smoke_app_v2_all.py --suite all --read-only
python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url https://app.iusentra.it
python scripts\smoke_app_v2_all.py --suite rbac --read-only
python scripts\smoke_app_v2_all.py --suite tenant --read-only
python scripts\smoke_app_v2_all.py --suite health --read-only --json-output smoke-report.json
```

Alias storici ancora validi:

```powershell
python scripts\smoke_app_v2_all.py --subset inventory
python scripts\smoke_app_v2_all.py --subset contracts
python scripts\smoke_app_v2_all.py --subset routing
python scripts\smoke_app_v2_all.py --subset workflows
```

## Env supportate

| Env | Uso |
| --- | --- |
| `IUSENTRA_BASE_URL` | Base URL se non passato con `--base-url`. |
| `IUSENTRA_ADMIN_USER`, `IUSENTRA_ADMIN_PASSWORD` | Profilo admin smoke. |
| `IUSENTRA_TENANT_A_USER`, `IUSENTRA_TENANT_A_PASSWORD` | Profilo tenant A. |
| `IUSENTRA_TENANT_B_USER`, `IUSENTRA_TENANT_B_PASSWORD` | Profilo tenant B. |
| `IUSENTRA_READONLY_USER`, `IUSENTRA_READONLY_PASSWORD` | Profilo sola lettura. |
| `IUSENTRA_SMOKE_API_KEY`, `IUSENTRA_SMOKE_TENANT_SLUG` | API key tenant-aware a basso privilegio per cross-tenant guard. |
| `IUSENTRA_ENABLE_MUTATING_SMOKE` | Deve essere `true` per future mutazioni test; default spento. |
| `IUSENTRA_EXPECTED_ENV` | `local`, `staging`, `demo`, `prod`. |
| `IUSENTRA_SMOKE_JSON_OUTPUT` | Path report JSON se non passato da CLI. |
| `IUSENTRA_FEATURE_FLAGS_EXPECTED` | JSON o lista `flag=true/false` per aspettative runtime. |
| `IUSENTRA_TEST_DOCUMENT_ID`, `IUSENTRA_TENANT_A_DOCUMENT_ID`, `IUSENTRA_TENANT_B_DOCUMENT_ID` | ID test non sensibili per download/tenant smoke. |

## Exit code e severita

- Exit `0`: nessun `FAIL`; eventuali `BLOCKED`/`SKIP` sono dichiarati e non
  spacciati per verde.
- Exit `1`: almeno un controllo `FAIL`, oppure `WARNING` con `--fail-on-warning`.
- `critical`: auth, RBAC, tenant isolation, open redirect, flag off, secret
  leakage, API P0 500.
- `high`: workflow P0, routing P0, provider/API contract.
- `medium/low`: gap ambiente, ID test mancanti, smoke non distruttivi saltati.

## Output JSON

Il report JSON contiene solo metadati diagnostici redatti:

```powershell
python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --json-output artifacts\smoke\post-deploy.json
```

Campi: `started_at`, `finished_at`, `base_url`, `environment`, `summary`,
`checks`. Non contiene password, token, API key, contenuti documenti o payload
operativi completi.

## Smoke non eseguibili senza env

- Login admin/tenant A/tenant B/readonly: richiede profili smoke dedicati.
- RBAC readonly autenticato: richiede `IUSENTRA_READONLY_*`.
- Cross-tenant con API key: richiede `IUSENTRA_SMOKE_API_KEY`.
- Download documento test: richiede ID documento test sintetico e tenant-safe.
- Mutating smoke: disattivato salvo `IUSENTRA_ENABLE_MUTATING_SMOKE=true` in
  ambiente controllato con cleanup.

## Troubleshooting rapido

1. `BASE_URL` non raggiungibile: verificare `/api/pronto`, DNS, proxy e container.
2. Login fallisce: controllare account smoke e non stampare credenziali.
3. 403 inatteso: distinguere flag spento, RBAC e tenant.
4. Tenant smoke blocked: configurare API key smoke o ID test sintetici.
5. JSON report non scritto: controllare directory e permessi.
6. Timeout: aumentare `--timeout`, verificare warm-up tenant gia' documentato.
7. TLS locale: usare HTTP locale o certificato fidato; non disabilitare TLS in staging/prod.

## Rollback se smoke fallisce

Stop rollout immediato se falliscono auth, RBAC, tenant isolation, open redirect,
flag-off, API P0 o secret leakage. Mitigazione:

1. spegnere il feature flag coinvolto;
2. disabilitare redirect App V2 se pertinente;
3. riavviare app/worker;
4. rieseguire `--suite post-deploy --read-only`;
5. aprire incident con output redatto e commit SHA;
6. revertire il commit solo se il flag non isola il difetto.
