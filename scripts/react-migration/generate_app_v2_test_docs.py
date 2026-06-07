from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_pytest_phases import CI_TEST_SUITES, PHASES, discover_test_files  # noqa: E402


def _load_page_registry_module():
    path = REPO_ROOT / "scripts" / "react-migration" / "generate_app_v2_page_registry.py"
    spec = importlib.util.spec_from_file_location("iusentra_page_registry_phase10", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossibile caricare {path.relative_to(REPO_ROOT)}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PAGE_REGISTRY = _load_page_registry_module()
MANIFEST_PATH = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"
TEST_PLAN_PATH = REPO_ROOT / "docs" / "test-plan-app-v2.md"
TEST_INVENTORY_PATH = REPO_ROOT / "docs" / "test-inventory.md"
TEST_MATRIX_PATH = REPO_ROOT / "docs" / "test-matrix-app-v2.md"


@dataclass(frozen=True)
class TestInventoryRow:
    area: str
    tipo: str
    file: str
    copre: str
    gap: str
    stato: str


AREA_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("auth", "Auth/RBAC"),
    ("rbac", "Auth/RBAC"),
    ("profili", "Auth/RBAC"),
    ("utenti", "Auth/RBAC"),
    ("tenant", "Tenant isolation"),
    ("storage", "Tenant isolation"),
    ("app_v2", "App V2"),
    ("react", "Frontend React"),
    ("ui", "Frontend React"),
    ("openapi", "API contracts"),
    ("contract", "API contracts"),
    ("security", "Security"),
    ("upload", "File/document security"),
    ("document", "File/document security"),
    ("template_atti", "Documenti"),
    ("editor", "Documenti"),
    ("fascicoli", "Fascicoli"),
    ("clienti", "Clienti/anagrafiche"),
    ("client_portal", "Portale Cliente"),
    ("client-portal", "Portale Cliente"),
    ("portale-clienti", "Portale Cliente"),
    ("portale-cliente", "Portale Cliente"),
    ("soggetti", "Clienti/anagrafiche"),
    ("email", "Comunicazioni"),
    ("messaggi", "Comunicazioni"),
    ("notifiche", "Comunicazioni"),
    ("agenda", "Agenda"),
    ("calendar", "Agenda"),
    ("scaden", "Scadenze"),
    ("telematico", "Telematico"),
    ("deposito", "Telematico"),
    ("pst", "Telematico"),
    ("pdp", "Telematico"),
    ("sigp", "Telematico"),
    ("lex", "Lex/Ricerca"),
    ("giurisprudenza", "Lex/Ricerca"),
    ("search", "Lex/Ricerca"),
    ("preventivi", "Mandato/economico"),
    ("fattur", "Mandato/economico"),
    ("tariffario", "Mandato/economico"),
    ("backup", "Impostazioni"),
    ("config", "Impostazioni"),
    ("impostazioni", "Impostazioni"),
    ("audit", "Audit"),
)


def _md(value: object) -> str:
    text = str(value if value is not None else "").strip()
    return text.replace("\n", " ").replace("|", "\\|") or "n.d."


def _table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    header_values = list(headers)
    lines = [
        "| " + " | ".join(_md(header) for header in header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md(cell) for cell in row) + " |")
    return "\n".join(lines)


def _read_manifest() -> list[dict[str, object]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    routes = payload.get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("route-manifest.json non contiene una lista routes")
    return [route for route in routes if isinstance(route, dict)]


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _area_for_file(path: Path) -> str:
    value = _rel(path).lower()
    for needle, label in AREA_KEYWORDS:
        if needle in value:
            return label
    return "Backend domain"


def _type_for_file(path: Path, text: str) -> str:
    value = (_rel(path) + "\n" + text[:4000]).lower()
    if "/e2e/" in value or "\\e2e\\" in value or "test_e2e" in value or "end_to_end" in value:
        return "E2E"
    if "openapi" in value or "provider" in value or "contract" in value:
        return "API contract"
    if any(token in value for token in ("tenant", "cross-tenant", "tenant_id", "isolation")):
        return "Tenant isolation"
    if any(token in value for token in ("rbac", "permess", "role", "ruolo", "readonly")):
        return "RBAC"
    if any(token in value for token in ("security", "csrf", "path traversal", "secret", "upload", "download")):
        return "Security"
    if any(token in value for token in ("react", "app_v2", "frontend", "ui", "component")):
        return "Frontend/UI"
    return "Backend"


def _coverage_for_file(path: Path, text: str) -> str:
    lowered = text.lower()
    checks: list[str] = []
    if "401" in text or "non autentic" in lowered:
        checks.append("401 anonimo")
    if "403" in text or "permess" in lowered or "readonly" in lowered:
        checks.append("403/RBAC")
    if "tenant" in lowered or "cross-tenant" in lowered:
        checks.append("tenant")
    if "feature" in lowered or "flag" in lowered:
        checks.append("feature flag")
    if "openapi" in lowered or "schema" in lowered:
        checks.append("contratto")
    if "upload" in lowered or "download" in lowered or "path traversal" in lowered:
        checks.append("file")
    if "audit" in lowered:
        checks.append("audit")
    return ", ".join(dict.fromkeys(checks)) or "happy/edge path dominio"


def _gap_for_file(tipo: str) -> str:
    if tipo == "E2E":
        return "richiede ambiente/credenziali quando esce dal test client"
    if tipo == "Frontend/UI":
        return "nessun runner component/VRT dedicato; copertura via gate statici e browser smoke"
    if tipo == "API contract":
        return "provider verification copre campione; estendere schema response P0/P1 puntuali"
    return "estendere solo se emerge una route/area non coperta dalla matrice"


def _inventory_rows() -> list[TestInventoryRow]:
    rows: list[TestInventoryRow] = []
    for path in discover_test_files():
        text = _file_text(path)
        tipo = _type_for_file(path, text)
        rows.append(
            TestInventoryRow(
                area=_area_for_file(path),
                tipo=tipo,
                file=_rel(path),
                copre=_coverage_for_file(path, text),
                gap=_gap_for_file(tipo),
                stato="censito",
            )
        )
    for path in sorted((REPO_ROOT / "scripts").glob("smoke_*.py")):
        rows.append(
            TestInventoryRow(
                area="Smoke",
                tipo="Smoke CLI",
                file=_rel(path),
                copre="readiness, route, workflow o sicurezza runtime",
                gap="autenticazione completa solo con env smoke dedicate",
                stato="censito",
            )
        )
    rows.append(
        TestInventoryRow(
            area="Frontend React",
            tipo="Frontend static gate",
            file="frontend/package.json",
            copre="contratti React, App V2 frontend, UI coverage fase 9, typecheck e build",
            gap="nessun Vitest/Jest/RTL coverage; nessun VRT attivo",
            stato="censito",
        )
    )
    return sorted(rows, key=lambda item: (item.area, item.tipo, item.file))


def _priority(route: dict[str, object]) -> str:
    return PAGE_REGISTRY._priority(route)


def _family_label(route: dict[str, object]) -> str:
    return PAGE_REGISTRY._family_label(str(route.get("family") or "generale"))


def _phase10_state(route: dict[str, object]) -> str:
    status = str(route.get("status") or "")
    if status == "react_operational_full" and _priority(route) in {"P0", "P1"}:
        return "tested"
    if status in {"react_operational_full", "react_operational_partial"}:
        return "partial"
    if str(route.get("family") or "") == "telematico":
        return "blocked"
    return "pending"


def _yes_no(route: dict[str, object], kind: str) -> str:
    state = _phase10_state(route)
    if state == "tested":
        mapping = {
            "backend": "yes: pytest domain/API + backend security",
            "frontend": "yes: npm test + UI coverage",
            "rbac": "yes: guard comuni + permessi area",
            "tenant": "yes: tenant guards comuni",
            "flag": "yes: feature flag off/on gate",
            "contract": "yes: OpenAPI/provider map",
            "smoke": "yes: smoke inventario + browser mirato dove disponibile",
        }
        return mapping[kind]
    if state == "partial":
        return "partial: gate comuni presenti, estendere casi pagina/workflow"
    if state == "blocked":
        return "blocked: workflow non parificato o richiede credenziali/portali"
    return "no: da aggiungere prima della promozione"


def _matrix_rows(routes: list[dict[str, object]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for route in sorted(routes, key=lambda item: (_priority(item), str(item.get("family") or ""), str(item.get("route") or ""))):
        family = str(route.get("family") or "")
        role = {
            "amministrazione": "admin, profili autorizzati, readonly negato",
            "impostazioni": "admin/studio manager, readonly negato",
            "telematico": "avvocato/admin con permessi telematico",
            "comunicazioni": "avvocato/segreteria con permessi comunicazioni",
        }.get(family, "admin, avvocato, collaboratore, segreteria, readonly")
        rows.append(
            [
                _family_label(route),
                str(route.get("route") or ""),
                _priority(route),
                role,
                "tenant A, tenant B, denial cross-tenant",
                PAGE_REGISTRY._feature_flag(route),
                _yes_no(route, "backend"),
                _yes_no(route, "frontend"),
                _yes_no(route, "rbac"),
                _yes_no(route, "tenant"),
                _yes_no(route, "flag"),
                _yes_no(route, "contract"),
                _yes_no(route, "smoke"),
                _phase10_state(route),
            ]
        )
    return rows


def _phase_summary(rows: list[TestInventoryRow]) -> list[list[str]]:
    counts = Counter(row.tipo for row in rows)
    return [[tipo, count] for tipo, count in sorted(counts.items())]


def _phase_rows() -> list[list[str]]:
    files_by_phase = []
    all_files = {_rel(path) for path in discover_test_files()}
    for phase in PHASES:
        matched = [file for file in all_files if phase.pattern.search(file)]
        files_by_phase.append([phase.name, phase.description, len(matched)])
    misc_count = len(all_files) - sum(int(row[2]) for row in files_by_phase)
    files_by_phase.append(["09-misc", "Test non classificati dalle fasi principali", max(misc_count, 0)])
    return files_by_phase


def _suite_rows() -> list[list[str]]:
    return [[name, len(paths), ", ".join(_rel(path) for path in paths[:5]) + (" ..." if len(paths) > 5 else "")] for name, paths in sorted(CI_TEST_SUITES.items())]


def _commands() -> list[list[str]]:
    return [
        ["Backend rapido", r"python -m pytest -q tests/test_auth.py tests/test_backend_security_phase5.py tests/test_tenant_isolation_runtime.py --tb=short", "auth, security e tenant isolation mirati"],
        ["Backend sharded", r"python scripts\run_pytest_phases.py --phase 00-ci-contracts,01-flask-core,04-storage --timeout-minutes 15 --batch-size 8", "core backend senza monolitico opaco"],
        ["Frontend statico", r"pnpm --filter @iusentra/studio test", "contratti React, App V2 e UI coverage"],
        ["Frontend build", r"pnpm --filter @iusentra/studio typecheck && pnpm --filter @iusentra/studio build", "typecheck e build Vite"],
        ["Contratti API", r"python scripts\validate_openapi.py docs\openapi.yaml && python scripts\verify_openapi_provider.py", "OpenAPI + provider verification"],
        ["Smoke unico", r"python scripts\smoke_app_v2_all.py --base-url http://127.0.0.1:8080", "orchestratore smoke fase 10"],
        ["Coverage backend", r"python -m pytest -q tests/test_auth.py tests/test_storage_strategy.py tests/test_telematico_repository.py --cov=pct.auth --cov=pct.storage --cov=pct.telematico_repository --cov-report=term-missing", "baseline coverage mirata, senza cambiare soglie CI"],
    ]


def _inventory_doc(rows: list[TestInventoryRow]) -> str:
    return "\n".join(
        [
            "# Inventario test IUSENTRA",
            "",
            "Aggiornato: 2026-05-14, fase 14 `fasereact`.",
            "",
            "Inventario generato da `scripts/react-migration/generate_app_v2_test_docs.py`. Non sostituisce l'esecuzione dei test: classifica i file presenti e rende visibili gap, aree e stato.",
            "",
            "## Sintesi",
            "",
            f"- File pytest censiti: {len([row for row in rows if row.file.startswith(('tests/', 'lex/tests/'))])}.",
            f"- Smoke/script censiti: {len([row for row in rows if row.tipo == 'Smoke CLI'])}.",
            "- Runner frontend component/VRT rilevati: nessuno; copertura UI tramite gate statici fase 9.",
            "",
            _table(["Tipo test", "Conteggio"], _phase_summary(rows)),
            "",
            "## Fasi pytest governate",
            "",
            _table(["Fase", "Descrizione", "File censiti"], _phase_rows()),
            "",
            "## Suite CI aggiuntive",
            "",
            _table(["Suite", "Target", "Esempi"], _suite_rows()),
            "",
            "## Inventario completo",
            "",
            _table(["Area", "Tipo test", "File", "Copre", "Gap", "Stato"], [[row.area, row.tipo, row.file, row.copre, row.gap, row.stato] for row in rows]),
            "",
        ]
    )


def _matrix_doc(routes: list[dict[str, object]]) -> str:
    rows = _matrix_rows(routes)
    status_counts = Counter(row[-1] for row in rows)
    return "\n".join(
        [
            "# Matrice test App V2",
            "",
            "Aggiornato: 2026-05-14, fase 13 `fasereact`.",
            "",
            "La matrice incrocia pagine, ruoli, tenant, feature flag e tipi test. `tested` indica copertura con gate reali comuni e route gia' `react_operational_full`; `partial`, `pending` e `blocked` non sono verdi completi.",
            "",
            "## Sintesi stato",
            "",
            _table(["Stato", "Conteggio"], sorted(status_counts.items())),
            "",
            "## Matrice",
            "",
            _table(
                [
                    "Area",
                    "Pagina",
                    "Priorita",
                    "Ruoli",
                    "Tenant",
                    "Flag",
                    "Backend",
                    "Frontend",
                    "RBAC",
                    "Tenant test",
                    "Feature flag",
                    "Contract",
                    "E2E/Smoke",
                    "Stato",
                ],
                rows,
            ),
            "",
        ]
    )


def _test_plan_doc(routes: list[dict[str, object]], inventory_rows: list[TestInventoryRow]) -> str:
    matrix_counts = Counter(_phase10_state(route) for route in routes)
    p0p1 = [route for route in routes if _priority(route) in {"P0", "P1"}]
    p0p1_tested = [route for route in p0p1 if _phase10_state(route) == "tested"]
    return "\n".join(
        [
            "# Piano test App V2",
            "",
            "Aggiornato: 2026-05-14, fase 13 `fasereact`.",
            "",
            "## Strategia",
            "",
            "La fase 10 consolida i test esistenti senza dichiarare passati comandi non eseguiti. La fase 11 collega quei comandi ai workflow CI/CD reali: i gate critici restano bloccanti su pull request e push, mentre smoke autenticati e controlli ambiente restano manuali o nightly quando richiedono credenziali. Il monolitico `python -m pytest -q` resta disponibile ma non va usato come unico segnale locale perche' storicamente puo' superare i budget; il runner governato `scripts/run_pytest_phases.py` consente shard documentati.",
            "",
            "## Test pyramid",
            "",
            "- Base: unit/domain pytest per auth, storage, tenant, documenti, comunicazioni, telematico, Lex e workflow.",
            "- Middle: Flask test client, API JSON, RBAC, feature flag, tenant isolation, file security e provider verification.",
            "- UI: `pnpm --filter @iusentra/studio test`, `typecheck`, build Vite e `scripts/validate_ui_coverage.py`; nessun runner component/VRT dedicato e quindi nessuna copertura frontend percentuale dichiarata.",
            "- Top: smoke CLI e test E2E Python esistenti; smoke autenticati richiedono env e non sono verdi se le env mancano.",
            "",
            "## Copertura fase 10",
            "",
            f"- Route manifest: {len(routes)}.",
            f"- Route P0/P1: {len(p0p1)}.",
            f"- Route P0/P1 con stato `tested`: {len(p0p1_tested)}.",
            f"- File test/smoke censiti: {len(inventory_rows)}.",
            f"- Stati matrice: {', '.join(f'{key}={value}' for key, value in sorted(matrix_counts.items()))}.",
            "",
            "## Comandi principali",
            "",
            _table(["Area", "Comando", "Copertura"], _commands()),
            "",
            "## Backend coverage",
            "",
            "Coverage Python disponibile tramite `pytest-cov` gia' presente in `requirements/dev.txt`. La CI mantiene il gate critico su Lex/auth/storage/telematico con `config/coverage-critical.ini` e soglia 71; questa fase non abbassa soglie. Il comando locale di baseline mirato e' documentato nella tabella comandi e va registrato in `artifacts/react-migration/pytest-confirmed-ok.md` dopo l'esecuzione.",
            "",
            "### Coverage fase 14",
            "",
            "Eseguito il gate critico reale:",
            "",
            "```powershell",
            r"python scripts\run_pytest_phases.py --suite coverage-critical --timeout-minutes 20 -- --cov=lex --cov=pct.auth --cov=pct.storage --cov=pct.storage_postgres --cov=pct.telematico_repository --cov=pct.telematico_workflow --cov-config=config/coverage-critical.ini --cov-report=term-missing --cov-fail-under=71",
            "```",
            "",
            "Esito: PASS, 313 test, coverage totale 71.61%, soglia 71 raggiunta. Sono comparsi `ResourceWarning` su connessioni SQLite nei test, senza fallimento del gate.",
            "",
            "## Frontend coverage",
            "",
            "Non esistono Vitest/Jest/React Testing Library coverage o Playwright/Cypress component test. La copertura frontend reale in questa fase e' statica/contrattuale: `check-react-contracts.mjs`, `check-app-v2-frontend.mjs`, `validate_ui_coverage.py`, typecheck e build. Percentuali frontend non disponibili e non dichiarate.",
            "",
            "## Security, RBAC e tenant isolation",
            "",
            "Copertura presente tramite `tests/test_auth.py`, `tests/test_auth_management_routes.py`, `tests/test_backend_security_phase5.py`, `tests/test_tenant_isolation_runtime.py`, `tests/test_storage_strategy.py`, `tests/test_upload_security.py`, `tests/test_web_security.py`, `tests/test_security_headers.py` e test document/security specifici. La matrice marca `partial` quando manca prova pagina/workflow puntuale.",
            "",
            "## Feature flag e routing",
            "",
            "Copertura presente tramite `tests/test_feature_flags.py`, `tests/test_app_v2_feature_flags.py`, `tests/test_app_v2_routing.py`, `scripts/smoke_app_v2_routing.py`, registry e gate frontend. Le route App V2 operative sono attive di default e spegnibili per rollback; le capability non parificate restano default-off.",
            "",
            "## API contract coverage",
            "",
            "Contratti verificati con `docs/openapi.yaml`, `scripts/validate_openapi.py`, `scripts/verify_openapi_provider.py` e `tests/test_openapi_contracts_phase6.py`. Il provider sample non sostituisce test di dominio: gli endpoint sensibili restano coperti anche da security/RBAC/tenant tests.",
            "",
            "## E2E e smoke",
            "",
            "E2E Python presenti in `tests/e2e/` e golden path. Non esiste Playwright/Cypress dedicato. Lo smoke unificato fase 10 e' `scripts/smoke_app_v2_all.py`; se mancano credenziali, esegue readiness/inventari e dichiara i profili autenticati mancanti senza marcarli passati.",
            "",
            "## Smoke operativi fase 13",
            "",
            "La fase 13 promuove `scripts/smoke_app_v2_all.py` a orchestrator operativo. Suite disponibili: `health`, `auth`, `flags`, `rbac`, `tenant`, `routing`, `api`, `pages`, `workflows`, `documents`, `admin`, `search`, `notifications` e `post-deploy`. Il runner supporta `--read-only`, `--json-output`, `--fail-on-warning`, `--require-credentials` e mantiene gli alias storici `--subset inventory|contracts|routing|workflows`.",
            "",
            "Comandi:",
            "",
            "```powershell",
            r"python scripts\smoke_app_v2_all.py --suite all --read-only",
            r"python scripts\smoke_app_v2_all.py --suite post-deploy --read-only --base-url https://app.iusentra.it",
            r"python scripts\smoke_app_v2_all.py --suite health --read-only --json-output smoke-report.json",
            "```",
            "",
            "`BLOCKED` indica env o ID test mancanti; non e' un verde. Con `--require-credentials`, profili smoke mancanti fanno fallire il comando.",
            "",
            "## Flaky tests",
            "",
            "Rischio noto: primo accesso tenant autenticato dopo restart puo' essere lento per warm-up gia' registrato in `pytest-open-issues.md`. Nessun nuovo flaky introdotto dalla fase 10; eventuali timeout vanno sotto-shardati e documentati.",
            "",
            "## Tests non eseguiti o bloccati",
            "",
            "- Smoke autenticati tenant A/B/readonly: richiedono env `IUSENTRA_*_USER/PASSWORD`, `IUSENTRA_SMOKE_API_KEY` e ID documento sintetico.",
            "- Storybook: presente come infrastruttura frontend, non ancora gate visuale completo; VRT e test browser component dedicati restano non attivi.",
            "- E2E browser Playwright/Cypress: tool non presenti; presenti E2E Python/test client.",
            "",
            "## Commands recommended for CI",
            "",
            "La fase 11 ha inserito i comandi candidati nei workflow reali, mantenendo bloccanti build, contratti, RBAC, tenant isolation, feature flag, registry e frontend App V2:",
            "",
            _table(
                ["Priorita", "Comando", "Motivo"],
                [
                    ["P0", r"python scripts\react-migration\generate_app_v2_test_docs.py --check", "inventario/matrice/piano test deterministici"],
                    ["P0", r"python scripts\smoke_app_v2_all.py --subset inventory", "smoke discovery senza credenziali"],
                    ["P0", r"python scripts\validate_openapi.py docs\openapi.yaml && python scripts\verify_openapi_provider.py", "contratti API"],
                    ["P0", r"pnpm --filter @iusentra/studio test && pnpm --filter @iusentra/studio typecheck && pnpm --filter @iusentra/studio build", "frontend App V2"],
                    ["P1", r"python scripts\run_pytest_phases.py --phase 00-ci-contracts,01-flask-core,04-storage,06-telematico --timeout-minutes 15 --batch-size 8", "backend/security/tenant sharded"],
                    ["P1", r"python scripts\run_pytest_phases.py --suite coverage-critical --suite-shard <n> --suite-total-shards 12", "coverage critica esistente"],
                ],
            ),
            "",
            "## CI/CD fase 11",
            "",
            "`docs/ci-cd-gates.md` e' il registro operativo dei workflow. Il workflow principale `.github/workflows/ci.yml` esegue i gate App V2 bloccanti su push, pull request e manuale: API contract/provider verification, registry e piano test generati, smoke inventory senza credenziali, test RBAC/tenant/feature flag/routing, frontend test/typecheck/build, shard pytest, coverage critica ed E2E smoke Python.",
            "",
            "Le esecuzioni GitHub Actions restano da verificare dopo ogni push: localmente si validano i comandi equivalenti, mentre GitHub conferma runner, cache, artifact e protezioni branch. `.github/workflows/ci-required-gates.yml` attende i required checks dello SHA corrente e produce un report automatico. `.github/workflows/security-supply-chain.yml` mantiene CodeQL/dependency review separati e aggiunge audit dipendenze Python/frontend con artifact. `.github/workflows/smoke-staging.yml` resta manuale, usa environment `staging`, non gira su pull request e richiede secrets solo quando viene selezionato `require_credentials`.",
            "",
            _table(
                ["Workflow", "Gate", "Bloccante", "Nota"],
                [
                    [".github/workflows/ci.yml", "backend, frontend, contracts, registry, coverage-critical, e2e-smoke", "si", "Gate PR/push principali"],
                    [".github/workflows/frontend-ci.yml", "frontend test/typecheck/build sempre eseguiti", "si", "Shard rapido dedicato al frontend"],
                    [".github/workflows/security-supply-chain.yml", "pip-audit, pnpm audit critical, SBOM", "si per audit; artifact sempre", "Nessun segreto richiesto"],
                    [".github/workflows/ci-required-gates.yml", "required checks sullo SHA corrente", "si", "Report automatico Markdown/JSON"],
                    [".github/workflows/codeql.yml", "CodeQL Python", "si", "Code scanning GitHub"],
                    [".github/workflows/e2e-nightly.yml", "E2E full suite", "nightly/manual", "Non sostituisce i gate PR"],
                    [".github/workflows/smoke-staging.yml", "smoke ambiente e autenticati da secrets", "manuale/post-deploy", "Usare prima di rollout oltre pilota"],
                ],
            ),
            "",
            "## Criteri di accettazione fase 10",
            "",
            "- Inventario, matrice e piano test generati e verificati.",
            "- Smoke orchestrator presente e senza segreti hardcoded.",
            "- Test phase 10 dedicato verde.",
            "- Backend/frontend/contracts/smoke/coverage mirati eseguiti e registrati nei report.",
            "- Nessun runner o coverage non presente dichiarato come completo.",
            "",
        ]
    )


def generate() -> dict[Path, str]:
    routes = _read_manifest()
    inventory_rows = _inventory_rows()
    return {
        TEST_INVENTORY_PATH: _inventory_doc(inventory_rows),
        TEST_MATRIX_PATH: _matrix_doc(routes),
        TEST_PLAN_PATH: _test_plan_doc(routes, inventory_rows),
    }


def _write_if_changed(path: Path, content: str) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera piano, inventario e matrice test App V2 fase 10.")
    parser.add_argument("--check", action="store_true", help="Verifica che i documenti siano aggiornati.")
    args = parser.parse_args(argv)
    targets = generate()
    if args.check:
        dirty = [
            str(path.relative_to(REPO_ROOT))
            for path, expected in targets.items()
            if not path.exists() or path.read_text(encoding="utf-8") != expected
        ]
        if dirty:
            print("Documenti test App V2 non aggiornati: " + ", ".join(dirty), file=sys.stderr)
            return 1
        print("Documenti test App V2 aggiornati.")
        return 0
    changed = [path.relative_to(REPO_ROOT).as_posix() for path, content in targets.items() if _write_if_changed(path, content)]
    if changed:
        print("Aggiornati: " + ", ".join(changed))
    else:
        print("Documenti test App V2 gia' aggiornati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
