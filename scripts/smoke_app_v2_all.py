from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.smoke_lib import (  # noqa: E402
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    STATUS_BLOCKED,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_SKIP,
    STATUS_WARNING,
    SmokeCheck,
    SmokeHttpClient,
    SmokeReport,
    configured_profiles,
    http_status_check,
    make_check,
    missing_profile_env,
    parse_json_object,
    print_report,
    redact,
    run_python_command,
    utc_now,
    write_json_report,
)

from scripts.smoke_app_v2_workflows import WORKFLOWS  # noqa: E402
from web.services.app_v2_routing import build_app_v2_path, should_redirect_to_app_v2  # noqa: E402
from web.services.feature_flags import (  # noqa: E402
    APP_V2_DEFAULT_OFF_FLAGS,
    APP_V2_DEFAULT_ON_FLAGS,
    APP_V2_ROUTE_FLAGS,
    FEATURE_FLAG_CANONICAL_BY_ALIAS,
    FEATURE_FLAG_DEFINITIONS,
    resolve_feature_flags,
)

HEALTH_PATHS = (
    ("readiness", "/api/pronto", (200,), SEVERITY_CRITICAL),
    ("home-shell", "/", (200, 302, 303), SEVERITY_HIGH),
)

SENSITIVE_API_PATHS = (
    "/api/v1/ui/fascicoli",
    "/api/v1/ui/audit",
    "/api/v1/ui/admin/database",
    "/api/v1/ui/utenti",
    "/api/v1/ui/impostazioni",
)

ROUTING_TARGETS = (
    ("api-pronta", "/api/pronto", (200,), SEVERITY_CRITICAL),
    ("feature-flags", "/api/v1/ui/feature-flags", (200, 302, 303, 401, 403), SEVERITY_HIGH),
    ("legacy-fascicoli", "/fascicoli?q=smoke", (200, 302, 303), SEVERITY_HIGH),
    ("app-v2-documenti", "/app-v2/documenti", (200, 302, 303, 403), SEVERITY_HIGH),
    ("open-redirect", "/app-v2?next=https://evil.example", (200, 302, 303, 403), SEVERITY_CRITICAL),
)

PAGE_TARGETS = (
    ("app-v2-home", "/app-v2", (200, 302, 303, 403), SEVERITY_HIGH),
    ("app-v2-documenti", "/app-v2/documenti", (200, 302, 303, 403), SEVERITY_HIGH),
    ("app-v2-fascicoli", "/app-v2/fascicoli", (200, 302, 303, 403), SEVERITY_HIGH),
    ("impostazioni", "/impostazioni", (200, 302, 303), SEVERITY_MEDIUM),
)

DOCUMENT_TARGETS = (
    ("documenti", "/documenti", (200, 302, 303, 403), SEVERITY_MEDIUM),
    ("redazione-atti", "/redazione-atti", (200, 302, 303, 403), SEVERITY_MEDIUM),
    ("template-atti", "/template-atti", (200, 302, 303, 403), SEVERITY_MEDIUM),
    ("api-template", "/api/v1/ui/template-atti", (200, 401, 403), SEVERITY_HIGH),
)

ADMIN_TARGETS = (
    ("utenti", "/utenti", (200, 302, 303, 403), SEVERITY_HIGH),
    ("profili", "/profili", (200, 302, 303, 403), SEVERITY_HIGH),
    ("database", "/database", (200, 302, 303, 403), SEVERITY_HIGH),
    ("api-admin-db", "/api/v1/ui/admin/database", (200, 401, 403), SEVERITY_CRITICAL),
)

SEARCH_TARGETS = (
    ("ricerca-studio", "/ricerca-studio", (200, 302, 303, 403), SEVERITY_MEDIUM),
    ("ricerca-legale", "/ricerca-legale", (200, 302, 303, 403), SEVERITY_MEDIUM),
    ("api-ricerca-legale", "/api/v1/ui/ricerca-legale", (200, 401, 403), SEVERITY_HIGH),
)

NOTIFICATION_TARGETS = (
    ("notifiche", "/notifiche", (200, 302, 303, 403), SEVERITY_MEDIUM),
    ("notifiche-legali", "/notifiche-legali", (200, 302, 303, 403), SEVERITY_MEDIUM),
    ("push-public-key", "/api/push/public-key", (200, 401, 403, 404), SEVERITY_MEDIUM),
)

SUITE_ORDER = (
    "health",
    "auth",
    "flags",
    "rbac",
    "tenant",
    "routing",
    "api",
    "pages",
    "workflows",
    "documents",
    "admin",
    "search",
    "notifications",
)

POST_DEPLOY_ORDER = (
    "health",
    "auth",
    "flags",
    "rbac",
    "tenant",
    "routing",
    "api",
    "pages",
    "workflows",
    "documents",
    "admin",
    "search",
    "notifications",
)

LEGACY_SUBSETS = {
    "inventory": "inventory",
    "security": "auth",
    "contracts": "api",
}


class Runner:
    def __init__(
        self,
        *,
        base_url: str,
        timeout: int,
        read_only: bool,
        require_credentials: bool,
        fail_on_warning: bool,
        expected_env: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.read_only = read_only
        self.require_credentials = require_credentials
        self.fail_on_warning = fail_on_warning
        self.expected_env = expected_env
        self.client = SmokeHttpClient(self.base_url, timeout=timeout)

    def _blocked_or_fail(self, suite: str, name: str, message: str, *, severity: str = SEVERITY_MEDIUM) -> SmokeCheck:
        status = STATUS_FAIL if self.require_credentials else STATUS_BLOCKED
        fail_severity = SEVERITY_HIGH if self.require_credentials else severity
        return make_check(suite, name, status, fail_severity, message)

    def _get_check(self, suite: str, name: str, path: str, expected: tuple[int, ...], severity: str) -> SmokeCheck:
        try:
            response = self.client.get(path, allow_redirects=False)
        except RuntimeError as exc:
            return make_check(suite, name, STATUS_FAIL, severity, str(exc), path=path)
        return http_status_check(suite, name, response, expected, severity=severity, path=path)

    def suite_health(self) -> list[SmokeCheck]:
        checks: list[SmokeCheck] = []
        for name, path, expected, severity in HEALTH_PATHS:
            check = self._get_check("health", name, path, expected, severity)
            if name == "readiness" and check.status == STATUS_PASS:
                payload = parse_json_object(self.client.get(path).body)
                if payload.get("ok") is not True:
                    check = make_check("health", name, STATUS_FAIL, SEVERITY_CRITICAL, "Payload readiness senza ok=true.", path=path)
                elif payload.get("versione"):
                    check = make_check(
                        "health",
                        name,
                        STATUS_PASS,
                        SEVERITY_CRITICAL,
                        f"Readiness OK versione {payload.get('versione')}.",
                        http_status=200,
                        path=path,
                    )
            checks.append(check)
        return checks

    def suite_auth(self) -> list[SmokeCheck]:
        checks: list[SmokeCheck] = []
        for path in SENSITIVE_API_PATHS:
            checks.append(self._get_check("auth", f"anonimo-negato:{path}", path, (401, 403), SEVERITY_CRITICAL))

        invalid = SmokeHttpClient(self.base_url, timeout=self.timeout)
        try:
            invalid.post_form("/login", {"username": "iusentra-smoke-invalid", "password": "invalid-password"})
            response = invalid.get("/api/v1/ui/fascicoli")
            checks.append(
                http_status_check(
                    "auth",
                    "credenziali-invalide-non-autenticano",
                    response,
                    (401, 403),
                    severity=SEVERITY_CRITICAL,
                    path="/api/v1/ui/fascicoli",
                )
            )
        except RuntimeError as exc:
            checks.append(make_check("auth", "credenziali-invalide", STATUS_FAIL, SEVERITY_CRITICAL, str(exc)))

        profiles = configured_profiles()
        if not profiles:
            checks.append(
                self._blocked_or_fail(
                    "auth",
                    "profili-autenticati",
                    "Credenziali smoke non configurate; impostare IUSENTRA_ADMIN/TENANT_A/TENANT_B/READONLY *_USER/*_PASSWORD.",
                    severity=SEVERITY_MEDIUM,
                )
            )
            return checks

        for profile, (username, password) in profiles.items():
            session = SmokeHttpClient(self.base_url, timeout=self.timeout)
            try:
                session.get("/login")
                session.post_form("/login", {"username": username, "password": password})
                response = session.get("/api/v1/ui/feature-flags")
            except RuntimeError as exc:
                checks.append(make_check("auth", f"login:{profile}", STATUS_FAIL, SEVERITY_CRITICAL, str(exc)))
                continue
            checks.append(
                http_status_check(
                    "auth",
                    f"login:{profile}",
                    response,
                    (200, 403),
                    severity=SEVERITY_HIGH,
                    path="/api/v1/ui/feature-flags",
                    message="Profilo autenticato verificato senza stampare segreti.",
                )
            )
        return checks

    def suite_flags(self) -> list[SmokeCheck]:
        checks: list[SmokeCheck] = []
        app_v2_defs = [
            definition
            for definition in FEATURE_FLAG_DEFINITIONS
            if definition.key.startswith("routes.appV2.") and definition.key not in FEATURE_FLAG_CANONICAL_BY_ALIAS
        ]
        defaults = {definition.key: bool(definition.default) for definition in FEATURE_FLAG_DEFINITIONS}
        unknown_policy = sorted(
            definition.key
            for definition in app_v2_defs
            if definition.key not in APP_V2_DEFAULT_ON_FLAGS and definition.key not in APP_V2_DEFAULT_OFF_FLAGS
        )
        default_drift = sorted(
            [key for key in APP_V2_DEFAULT_ON_FLAGS if defaults.get(key) is not True]
            + [key for key in APP_V2_DEFAULT_OFF_FLAGS if defaults.get(key) is not False]
        )
        checks.append(
            make_check(
                "flags",
                "rollout-defaults-source",
                STATUS_FAIL if unknown_policy or default_drift else STATUS_PASS,
                SEVERITY_CRITICAL,
                "Policy flag non coerente: " + ", ".join(unknown_policy + default_drift)
                if unknown_policy or default_drift
                else (
                    f"{len(APP_V2_DEFAULT_ON_FLAGS)} flag App V2 operativi attivi di default; "
                    f"{len(APP_V2_DEFAULT_OFF_FLAGS)} flag protetti restano spenti."
                ),
            )
        )
        known = {definition.key for definition in FEATURE_FLAG_DEFINITIONS}
        missing_route_flags = sorted({flag for _, flag in APP_V2_ROUTE_FLAGS if flag not in known})
        checks.append(
            make_check(
                "flags",
                "route-flags-registrati",
                STATUS_FAIL if missing_route_flags else STATUS_PASS,
                SEVERITY_CRITICAL,
                "Flag route mancanti: " + ", ".join(missing_route_flags) if missing_route_flags else "Tutte le route App V2 puntano a flag registrati.",
            )
        )
        resolved = resolve_feature_flags({})
        rollout_drift = sorted(
            [key for key in APP_V2_DEFAULT_ON_FLAGS if resolved.get(key) is not True]
            + [key for key in APP_V2_DEFAULT_OFF_FLAGS if resolved.get(key) is not False]
        )
        checks.append(
            make_check(
                "flags",
                "resolver-rollout-defaults",
                STATUS_FAIL if rollout_drift else STATUS_PASS,
                SEVERITY_CRITICAL,
                "Resolver flag non coerente: " + ", ".join(rollout_drift)
                if rollout_drift
                else "Resolver senza config apre le superfici operative e mantiene protette quelle non parificate.",
            )
        )

        runtime = self._get_check("flags", "runtime-endpoint-protetto", "/api/v1/ui/feature-flags", (200, 302, 303, 401, 403), SEVERITY_HIGH)
        checks.append(runtime)
        expected_raw = os.getenv("IUSENTRA_FEATURE_FLAGS_EXPECTED", "").strip()
        if expected_raw:
            checks.extend(self._check_expected_flags(expected_raw))
        return checks

    def _check_expected_flags(self, raw: str) -> list[SmokeCheck]:
        try:
            expected = json.loads(raw)
        except json.JSONDecodeError:
            expected = {}
            for part in raw.split(","):
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                expected[key.strip()] = value.strip().lower() in {"1", "true", "yes", "on"}
        if not isinstance(expected, dict):
            return [make_check("flags", "expected-flags", STATUS_FAIL, SEVERITY_HIGH, "IUSENTRA_FEATURE_FLAGS_EXPECTED non e' un oggetto valido.")]
        try:
            response = self.client.get("/api/v1/ui/feature-flags")
        except RuntimeError as exc:
            return [make_check("flags", "expected-flags", STATUS_FAIL, SEVERITY_HIGH, str(exc))]
        if response.status != 200:
            return [
                make_check(
                    "flags",
                    "expected-flags",
                    STATUS_BLOCKED,
                    SEVERITY_MEDIUM,
                    f"Endpoint flag non leggibile senza profilo autenticato: HTTP {response.status}.",
                    http_status=response.status,
                    path="/api/v1/ui/feature-flags",
                )
            ]
        flags = parse_json_object(response.body).get("flags", {})
        mismatches = [key for key, value in expected.items() if bool(flags.get(key)) != bool(value)]
        return [
            make_check(
                "flags",
                "expected-flags",
                STATUS_FAIL if mismatches else STATUS_PASS,
                SEVERITY_HIGH,
                "Flag inattesi: " + ", ".join(mismatches) if mismatches else "Flag runtime coerenti con IUSENTRA_FEATURE_FLAGS_EXPECTED.",
            )
        ]

    def suite_rbac(self) -> list[SmokeCheck]:
        profiles = configured_profiles()
        checks: list[SmokeCheck] = []
        if "readonly" not in profiles:
            checks.append(
                self._blocked_or_fail(
                    "rbac",
                    "readonly-admin-denied",
                    "Profilo readonly non configurato; impossibile verificare denial admin autenticato.",
                    severity=SEVERITY_MEDIUM,
                )
            )
            return checks
        username, password = profiles["readonly"]
        session = SmokeHttpClient(self.base_url, timeout=self.timeout)
        try:
            session.get("/login")
            session.post_form("/login", {"username": username, "password": password})
            response = session.get("/api/v1/ui/admin/database")
        except RuntimeError as exc:
            checks.append(make_check("rbac", "readonly-admin-denied", STATUS_FAIL, SEVERITY_CRITICAL, str(exc)))
            return checks
        checks.append(
            http_status_check(
                "rbac",
                "readonly-admin-denied",
                response,
                (401, 403),
                severity=SEVERITY_CRITICAL,
                path="/api/v1/ui/admin/database",
                message="Readonly non accede ad admin/database.",
            )
        )
        if self.read_only or os.getenv("IUSENTRA_ENABLE_MUTATING_SMOKE", "false").lower() not in {"1", "true", "yes", "on"}:
            checks.append(
                make_check(
                    "rbac",
                    "mutating-smoke",
                    STATUS_SKIP,
                    SEVERITY_LOW,
                    "Mutating smoke disattivati: nessuna modifica ruolo/settings/documenti eseguita.",
                )
            )
        return checks

    def suite_tenant(self) -> list[SmokeCheck]:
        checks = [self._get_check("tenant", f"anonimo-tenant-safe:{path}", path, (401, 403), SEVERITY_CRITICAL) for path in ("/api/v1/ui/fascicoli", "/api/v1/ui/impostazioni")]
        api_key = os.getenv("IUSENTRA_SMOKE_API_KEY", "")
        tenant_slug = os.getenv("IUSENTRA_SMOKE_TENANT_SLUG", "")
        if not api_key:
            checks.append(
                self._blocked_or_fail(
                    "tenant",
                    "tenant-id-forzato-auth",
                    "IUSENTRA_SMOKE_API_KEY non configurata; controllo cross-tenant autenticato non eseguibile.",
                    severity=SEVERITY_MEDIUM,
                )
            )
            return checks
        headers = {"Accept": "application/json", "X-API-Key": api_key}
        if tenant_slug:
            headers["X-Tenant-Slug"] = tenant_slug
        try:
            response = self.client.get("/api/v1/ui/fascicoli?tenant_id=studio-b&q=smoke", headers=headers)
        except RuntimeError as exc:
            checks.append(make_check("tenant", "tenant-id-forzato-auth", STATUS_FAIL, SEVERITY_CRITICAL, str(exc)))
            return checks
        payload = parse_json_object(response.body)
        ok = response.status == 400 and payload.get("code") == "backend_security_control_param" and "studio-b" not in response.body
        checks.append(
            make_check(
                "tenant",
                "tenant-id-forzato-auth",
                STATUS_PASS if ok else STATUS_FAIL,
                SEVERITY_CRITICAL,
                "tenant_id client bloccato senza leakage." if ok else f"HTTP {response.status}, code={payload.get('code')}",
                duration_ms=response.duration_ms,
                http_status=response.status,
                path="/api/v1/ui/fascicoli?tenant_id=studio-b&q=smoke",
            )
        )
        return checks

    def suite_routing(self) -> list[SmokeCheck]:
        checks: list[SmokeCheck] = []
        safe = build_app_v2_path(
            "/fascicoli",
            {
                "q": "Rossi",
                "next": "https://evil.example",
                "redirect": "//evil.example",
                "tenant_id": "tenant-b",
                "token": "secret",
            },
        )
        checks.append(
            make_check(
                "routing",
                "query-whitelist",
                STATUS_PASS if safe == "/app-v2/fascicoli?q=Rossi" else STATUS_FAIL,
                SEVERITY_CRITICAL,
                f"Query sanificata: {safe}",
            )
        )
        decision = should_redirect_to_app_v2(
            "/documenti",
            {"tab": "template"},
            config={"FEATURE_FLAGS": {"routes.appV2.documents.list": False}},
        )
        checks.append(
            make_check(
                "routing",
                "flag-off-fail-closed",
                STATUS_PASS if (not decision.allowed and decision.flag_key == "routes.appV2.documents.list") else STATUS_FAIL,
                SEVERITY_CRITICAL,
                f"Decisione flag-off: allowed={decision.allowed}, flag={decision.flag_key}",
            )
        )
        for name, path, expected, severity in ROUTING_TARGETS:
            checks.append(self._get_check("routing", name, path, expected, severity))
        return checks

    def suite_api(self) -> list[SmokeCheck]:
        checks = [
            run_python_command(["scripts/validate_openapi.py", "docs/openapi.yaml"], cwd=REPO_ROOT, timeout=self.timeout),
            run_python_command(["scripts/verify_openapi_provider.py"], cwd=REPO_ROOT, timeout=self.timeout),
        ]
        for path in SENSITIVE_API_PATHS:
            checks.append(self._get_check("api", f"api-protetta:{path}", path, (401, 403), SEVERITY_CRITICAL))
        return checks

    def suite_pages(self) -> list[SmokeCheck]:
        return [self._get_check("pages", name, path, expected, severity) for name, path, expected, severity in PAGE_TARGETS]

    def suite_workflows(self) -> list[SmokeCheck]:
        checks: list[SmokeCheck] = []
        for target in WORKFLOWS:
            checks.append(self._get_check("workflows", f"{target.area}:legacy", target.legacy_path, (200, 302, 303, 403), SEVERITY_HIGH if target.priority == "P0" else SEVERITY_MEDIUM))
            checks.append(self._get_check("workflows", f"{target.area}:api", target.api_path, (200, 401, 403), SEVERITY_HIGH if target.priority == "P0" else SEVERITY_MEDIUM))
            checks.append(self._get_check("workflows", f"{target.area}:app-v2", target.app_path, (200, 302, 303, 403), SEVERITY_HIGH if target.priority == "P0" else SEVERITY_MEDIUM))
        if not configured_profiles():
            checks.append(
                self._blocked_or_fail(
                    "workflows",
                    "profili-autenticati",
                    "Workflow autenticati non eseguiti: credenziali smoke dedicate assenti.",
                    severity=SEVERITY_MEDIUM,
                )
            )
        return checks

    def suite_documents(self) -> list[SmokeCheck]:
        checks = [self._get_check("documents", name, path, expected, severity) for name, path, expected, severity in DOCUMENT_TARGETS]
        if not any(os.getenv(name, "") for name in ("IUSENTRA_TEST_DOCUMENT_ID", "IUSENTRA_TENANT_A_DOCUMENT_ID")):
            checks.append(make_check("documents", "download-documento-test", STATUS_BLOCKED, SEVERITY_MEDIUM, "ID documento test non configurato; download cross-tenant non eseguito."))
        return checks

    def suite_admin(self) -> list[SmokeCheck]:
        return [self._get_check("admin", name, path, expected, severity) for name, path, expected, severity in ADMIN_TARGETS]

    def suite_search(self) -> list[SmokeCheck]:
        checks = [self._get_check("search", name, path, expected, severity) for name, path, expected, severity in SEARCH_TARGETS]
        if not configured_profiles():
            checks.append(make_check("search", "ricerca-tenant-auth", STATUS_BLOCKED, SEVERITY_MEDIUM, "Ricerca tenant-safe autenticata non eseguita senza profili smoke."))
        return checks

    def suite_notifications(self) -> list[SmokeCheck]:
        checks = [self._get_check("notifications", name, path, expected, severity) for name, path, expected, severity in NOTIFICATION_TARGETS]
        checks.append(make_check("notifications", "invio-reale", STATUS_SKIP, SEVERITY_LOW, "Nessuna PEC, push o notifica reale inviata in smoke read-only."))
        return checks


def _script(name: str) -> str:
    return str(REPO_ROOT / "scripts" / name)


def _run_inventory(timeout: int) -> list[SmokeCheck]:
    checks: list[SmokeCheck] = []
    for script, label in (
        ("smoke_app_v2_pages.py", "pagine App V2"),
        ("smoke_app_v2_routing.py", "routing App V2"),
        ("smoke_app_v2_workflows.py", "workflow App V2"),
    ):
        print(f"\n== {label} ==")
        command = [sys.executable, _script(script), "--list"]
        print(" ".join(["python", f"scripts/{script}", "--list"]))
        result = subprocess.run(command, cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(redact(result.stderr.rstrip()), file=sys.stderr)
        checks.append(
            make_check(
                "inventory",
                script,
                STATUS_PASS if result.returncode == 0 else STATUS_FAIL,
                SEVERITY_INFO,
                "Inventario completato." if result.returncode == 0 else f"exit {result.returncode}",
            )
        )
    return checks


def _suite_names(requested: str) -> tuple[str, ...]:
    requested = LEGACY_SUBSETS.get(requested, requested)
    if requested == "all":
        return SUITE_ORDER
    if requested == "post-deploy":
        return POST_DEPLOY_ORDER
    return (requested,)


def _run_suites(runner: Runner, names: tuple[str, ...]) -> list[SmokeCheck]:
    checks: list[SmokeCheck] = []
    for name in names:
        method = getattr(runner, f"suite_{name.replace('-', '_')}", None)
        if not callable(method):
            checks.append(make_check(name, "suite", STATUS_FAIL, SEVERITY_HIGH, f"Suite sconosciuta: {name}"))
            continue
        checks.extend(method())
    return checks


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke orchestrator App V2 fase 13.")
    parser.add_argument("--base-url", default=os.getenv("IUSENTRA_BASE_URL", "http://127.0.0.1:8080"))
    parser.add_argument(
        "--suite",
        choices=(
            "all",
            "health",
            "auth",
            "flags",
            "rbac",
            "tenant",
            "routing",
            "api",
            "pages",
            "workflows",
            "documents",
            "admin",
            "search",
            "notifications",
            "post-deploy",
            "inventory",
        ),
        default=None,
    )
    parser.add_argument(
        "--subset",
        choices=("all", "inventory", "security", "pages", "routing", "workflows", "contracts"),
        default=None,
        help="Alias storico fase 10; preferire --suite.",
    )
    parser.add_argument("--read-only", action="store_true", help="Blocca mutazioni reali e documenta gli smoke mutating come SKIP.")
    parser.add_argument("--staging", action="store_true", help="Marca il report come staging se IUSENTRA_EXPECTED_ENV non e' impostato.")
    parser.add_argument("--require-credentials", action="store_true", help="Fallisce le suite bloccate da credenziali mancanti.")
    parser.add_argument("--json-output", default=os.getenv("IUSENTRA_SMOKE_JSON_OUTPUT", ""))
    parser.add_argument("--timeout", type=int, default=240, help="Timeout per chiamata o sotto-comando in secondi.")
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    requested = args.suite or args.subset or "all"
    environment = os.getenv("IUSENTRA_EXPECTED_ENV") or ("staging" if args.staging else "local")
    read_only = bool(args.read_only or environment in {"staging", "prod", "production"} or os.getenv("IUSENTRA_ENABLE_MUTATING_SMOKE", "false").lower() not in {"1", "true", "yes", "on"})
    report = SmokeReport(started_at=utc_now(), base_url=args.base_url.rstrip("/"), environment=environment, read_only=read_only)

    if requested == "inventory":
        report.checks.extend(_run_inventory(args.timeout))
    else:
        runner = Runner(
            base_url=args.base_url,
            timeout=args.timeout,
            read_only=read_only,
            require_credentials=args.require_credentials,
            fail_on_warning=args.fail_on_warning,
            expected_env=environment,
        )
        report.checks.extend(_run_suites(runner, _suite_names(requested)))

    if args.require_credentials and missing_profile_env():
        report.checks.append(
            make_check(
                "auth",
                "env-completezza",
                STATUS_FAIL,
                SEVERITY_HIGH,
                "Credenziali richieste mancanti: " + ", ".join(missing_profile_env()),
            )
        )
    report.finish()
    print_report(report)

    if requested == "inventory":
        print("\nSmoke App V2 fase 10 completato.")
    print("\nSmoke App V2 fase 13 completato." if not report.has_failure(fail_on_warning=args.fail_on_warning) else "\nSmoke App V2 fase 13 fallito.")

    if args.json_output:
        write_json_report(report, Path(args.json_output))
        print(f"Report JSON scritto: {args.json_output}")

    return 1 if report.has_failure(fail_on_warning=args.fail_on_warning) else 0


if __name__ == "__main__":
    raise SystemExit(main())
