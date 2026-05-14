from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPSHandler, HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"
STATUS_BLOCKED = "BLOCKED"
STATUS_WARNING = "WARNING"

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
SEVERITY_INFO = "informational"

SECRET_ENV_MARKERS = ("PASSWORD", "TOKEN", "SECRET", "API_KEY", "PRIVATE_KEY", "CLIENT_SECRET")
FORBIDDEN_BODY_MARKERS = (
    "Traceback",
    "password_hash",
    "access_token",
    "refresh_token",
    "api_key",
    "private_key",
)


@dataclass(frozen=True)
class SmokeCheck:
    suite: str
    name: str
    status: str
    severity: str
    message: str
    duration_ms: int = 0
    http_status: int | None = None
    path: str = ""


@dataclass(frozen=True)
class SmokeResponse:
    status: int
    body: str
    headers: dict[str, str]
    duration_ms: int
    url: str


@dataclass
class SmokeReport:
    started_at: str
    base_url: str
    environment: str
    read_only: bool
    checks: list[SmokeCheck] = field(default_factory=list)
    finished_at: str = ""

    def finish(self) -> None:
        self.finished_at = utc_now()

    def summary(self) -> dict[str, int]:
        counts = {
            STATUS_PASS.lower(): 0,
            STATUS_FAIL.lower(): 0,
            STATUS_SKIP.lower(): 0,
            STATUS_BLOCKED.lower(): 0,
            STATUS_WARNING.lower(): 0,
        }
        for check in self.checks:
            counts[check.status.lower()] = counts.get(check.status.lower(), 0) + 1
        return counts

    def has_failure(self, *, fail_on_warning: bool = False) -> bool:
        for check in self.checks:
            if check.status == STATUS_FAIL:
                return True
            if fail_on_warning and check.status == STATUS_WARNING:
                return True
        return False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _secret_values(env: dict[str, str] | None = None) -> list[str]:
    source = env or os.environ
    values: list[str] = []
    for key, value in source.items():
        if not value or len(value) < 4:
            continue
        upper = key.upper()
        if any(marker in upper for marker in SECRET_ENV_MARKERS):
            values.append(value)
    return values


def redact(text: Any, *, env: dict[str, str] | None = None) -> str:
    clean = str(text)
    for value in sorted(_secret_values(env), key=len, reverse=True):
        clean = clean.replace(value, "[redacted]")
    clean = re.sub(r"(?i)(password|token|api[_-]?key|secret)=([^&\s]+)", r"\1=[redacted]", clean)
    clean = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+", r"\1[redacted]", clean)
    return clean


def build_url(base_url: str, path: str) -> str:
    split = urlsplit(path)
    if split.scheme or split.netloc:
        raise ValueError("Gli smoke accettano solo path relativi, non URL esterni.")
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def external_location(location: str) -> bool:
    if not location:
        return False
    split = urlsplit(location)
    return bool(split.scheme or split.netloc or location.startswith("//"))


def parse_json_object(body: str) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class SmokeHttpClient:
    def __init__(self, base_url: str, *, timeout: float = 20.0, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.cookie_jar = CookieJar()
        self.opener = build_opener(*self._handlers())

    def _handlers(self, *, allow_redirects: bool = True) -> list[Any]:
        handlers: list[Any] = [HTTPCookieProcessor(self.cookie_jar)]
        if not allow_redirects:
            handlers.append(_NoRedirectHandler())
        if not self.verify_tls:
            handlers.append(HTTPSHandler(context=ssl._create_unverified_context()))
        return handlers

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        max_body: int = 8192,
        allow_redirects: bool = True,
    ) -> SmokeResponse:
        url = build_url(self.base_url, path)
        request_headers = {"Accept": "application/json, text/html;q=0.9", **(headers or {})}
        req = Request(url, data=data, headers=request_headers, method=method)
        started = time.perf_counter()
        opener = self.opener if allow_redirects else build_opener(*self._handlers(allow_redirects=False))
        try:
            with opener.open(req, timeout=self.timeout) as response:
                body = response.read(max_body).decode("utf-8", errors="replace")
                return SmokeResponse(
                    status=int(response.status),
                    body=body,
                    headers=dict(response.headers.items()),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    url=url,
                )
        except HTTPError as exc:
            body = exc.read(max_body).decode("utf-8", errors="replace")
            return SmokeResponse(
                status=int(exc.code),
                body=body,
                headers=dict(exc.headers.items()),
                duration_ms=int((time.perf_counter() - started) * 1000),
                url=url,
            )
        except URLError as exc:
            raise RuntimeError(f"{path}: endpoint non raggiungibile ({exc.reason})") from exc

    def get(self, path: str, *, headers: dict[str, str] | None = None, allow_redirects: bool = True) -> SmokeResponse:
        return self.request(path, headers=headers, allow_redirects=allow_redirects)

    def post_form(self, path: str, fields: dict[str, str]) -> SmokeResponse:
        from urllib.parse import urlencode

        data = urlencode(fields).encode("utf-8")
        return self.request(
            path,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
        )


def make_check(
    suite: str,
    name: str,
    status: str,
    severity: str,
    message: str,
    *,
    duration_ms: int = 0,
    http_status: int | None = None,
    path: str = "",
) -> SmokeCheck:
    return SmokeCheck(
        suite=suite,
        name=name,
        status=status,
        severity=severity,
        message=redact(message),
        duration_ms=duration_ms,
        http_status=http_status,
        path=path,
    )


def http_status_check(
    suite: str,
    name: str,
    response: SmokeResponse,
    expected: Iterable[int],
    *,
    severity: str,
    path: str,
    message: str = "",
) -> SmokeCheck:
    expected_set = set(expected)
    if any(marker in response.body for marker in FORBIDDEN_BODY_MARKERS):
        return make_check(
            suite,
            name,
            STATUS_FAIL,
            severity,
            "La risposta contiene stack trace o marker sensibili.",
            duration_ms=response.duration_ms,
            http_status=response.status,
            path=path,
        )
    location = response.headers.get("Location", "")
    if external_location(location):
        return make_check(
            suite,
            name,
            STATUS_FAIL,
            SEVERITY_CRITICAL,
            f"Redirect esterno non sicuro verso {location}.",
            duration_ms=response.duration_ms,
            http_status=response.status,
            path=path,
        )
    if response.status not in expected_set:
        return make_check(
            suite,
            name,
            STATUS_FAIL,
            severity,
            f"HTTP {response.status}, atteso {sorted(expected_set)}. {message}".strip(),
            duration_ms=response.duration_ms,
            http_status=response.status,
            path=path,
        )
    return make_check(
        suite,
        name,
        STATUS_PASS,
        severity,
        message or f"HTTP {response.status} coerente.",
        duration_ms=response.duration_ms,
        http_status=response.status,
        path=path,
    )


def profile_env() -> dict[str, tuple[str, str]]:
    return {
        "admin": ("IUSENTRA_ADMIN_USER", "IUSENTRA_ADMIN_PASSWORD"),
        "tenant_a": ("IUSENTRA_TENANT_A_USER", "IUSENTRA_TENANT_A_PASSWORD"),
        "tenant_b": ("IUSENTRA_TENANT_B_USER", "IUSENTRA_TENANT_B_PASSWORD"),
        "readonly": ("IUSENTRA_READONLY_USER", "IUSENTRA_READONLY_PASSWORD"),
    }


def configured_profiles(env: dict[str, str] | None = None) -> dict[str, tuple[str, str]]:
    source = env or os.environ
    profiles: dict[str, tuple[str, str]] = {}
    for name, (user_var, pass_var) in profile_env().items():
        username = source.get(user_var, "").strip()
        password = source.get(pass_var, "")
        if username and password:
            profiles[name] = (username, password)
    return profiles


def missing_profile_env(env: dict[str, str] | None = None) -> list[str]:
    source = env or os.environ
    missing: list[str] = []
    for user_var, pass_var in profile_env().values():
        if not source.get(user_var, "").strip():
            missing.append(user_var)
        if not source.get(pass_var, ""):
            missing.append(pass_var)
    return missing


def run_python_command(args: list[str], *, cwd: Path, timeout: int) -> SmokeCheck:
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    output = redact((result.stdout + "\n" + result.stderr).strip())
    label = " ".join(args)
    if result.returncode != 0:
        return make_check(
            "api",
            label,
            STATUS_FAIL,
            SEVERITY_HIGH,
            f"exit {result.returncode}: {output[:1000]}",
            duration_ms=duration_ms,
        )
    safe_note = "Comando completato."
    if output:
        safe_note = f"Comando completato; output redatto ({len(output.splitlines())} righe)."
    return make_check("api", label, STATUS_PASS, SEVERITY_HIGH, safe_note, duration_ms=duration_ms)


def print_report(report: SmokeReport) -> None:
    for check in report.checks:
        extra = f" | HTTP {check.http_status}" if check.http_status is not None else ""
        path = f" | {check.path}" if check.path else ""
        print(f"{check.status} | {check.suite} | {check.name}{extra}{path} | {check.message}")
    summary = report.summary()
    print(
        "\nSmoke summary: "
        + ", ".join(f"{key.upper()}={value}" for key, value in summary.items())
        + f" | base_url={report.base_url} | env={report.environment}"
    )


def write_json_report(report: SmokeReport, path: Path) -> None:
    payload = {
        "started_at": report.started_at,
        "finished_at": report.finished_at or utc_now(),
        "base_url": report.base_url,
        "environment": report.environment,
        "read_only": report.read_only,
        "summary": report.summary(),
        "checks": [asdict(check) for check in report.checks],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
