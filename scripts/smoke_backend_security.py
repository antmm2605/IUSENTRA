from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeResult:
    label: str
    path: str
    status: int
    ok: bool
    note: str = ""


def _request(base_url: str, path: str, *, headers: dict[str, str] | None = None, timeout: float = 12.0) -> tuple[int, str]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return int(response.status), body
    except HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        return int(exc.code), body
    except URLError as exc:
        raise RuntimeError(f"{path}: endpoint non raggiungibile ({exc.reason})") from exc


def _json_body(body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _check_status(label: str, path: str, status: int, expected: set[int], body: str = "") -> SmokeResult:
    leak_markers = {"Traceback", "tenant-b", "studio-b", "api_key", "access_token"}
    leaked = sorted(marker for marker in leak_markers if marker in body)
    if leaked:
        return SmokeResult(label, path, status, False, f"dettagli sensibili in risposta: {', '.join(leaked)}")
    return SmokeResult(label, path, status, status in expected, f"atteso {sorted(expected)}")


def run_smoke(base_url: str, *, api_key: str = "", tenant_slug: str = "", require_credentials: bool = False) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    status, body = _request(base_url, "/api/pronto", headers={"Accept": "application/json"})
    ready = _json_body(body)
    results.append(SmokeResult("readiness", "/api/pronto", status, status == 200 and ready.get("ok") is True, str(ready.get("versione") or "")))

    for path in (
        "/api/v1/ui/fascicoli",
        "/api/v1/ui/audit",
        "/api/v1/ui/admin/database",
        "/api/v1/ui/utenti",
        "/api/v1/ui/impostazioni",
    ):
        status, body = _request(base_url, path, headers={"Accept": "application/json"})
        results.append(_check_status("anonimo bloccato", path, status, {401, 403}, body))

    if require_credentials and not api_key:
        results.append(SmokeResult("cred app", "/api/v1/ui/fascicoli?tenant_id=studio-b", 0, False, "IUSENTRA_SMOKE_API_KEY mancante"))
        return results
    if not api_key:
        results.append(SmokeResult("cred app", "/api/v1/ui/fascicoli?tenant_id=studio-b", 0, True, "saltato: nessuna chiave smoke in env"))
        return results

    headers = {"Accept": "application/json", "X-API-Key": api_key}
    if tenant_slug:
        headers["X-Tenant-Slug"] = tenant_slug
    status, body = _request(base_url, "/api/v1/ui/fascicoli?tenant_id=studio-b&q=rossi", headers=headers)
    parsed = _json_body(body)
    expected_code = parsed.get("code") == "backend_security_control_param"
    ok = status == 400 and expected_code and "studio-b" not in body
    results.append(SmokeResult("tenant forzato bloccato", "/api/v1/ui/fascicoli?tenant_id=studio-b&q=rossi", status, ok, str(parsed.get("code") or "")))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke sicurezza backend fase 5.")
    parser.add_argument("--base-url", default=os.getenv("IUSENTRA_BASE_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--api-key", default=os.getenv("IUSENTRA_SMOKE_API_KEY", ""))
    parser.add_argument("--tenant-slug", default=os.getenv("IUSENTRA_SMOKE_TENANT_SLUG", ""))
    parser.add_argument("--require-credentials", action="store_true")
    args = parser.parse_args()

    try:
        results = run_smoke(
            args.base_url,
            api_key=args.api_key,
            tenant_slug=args.tenant_slug,
            require_credentials=args.require_credentials,
        )
    except RuntimeError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 2

    failed = [item for item in results if not item.ok]
    for item in results:
        status = "OK" if item.ok else "KO"
        print(f"{status} | {item.label} | {item.status} | {item.path} | {item.note}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
