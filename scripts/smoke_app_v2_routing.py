from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

try:
    import requests
except ImportError:  # pragma: no cover - runtime minimali
    requests = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from web.services.app_v2_routing import (  # noqa: E402
    LEGACY_TO_APP_V2_TARGETS,
    build_app_v2_path,
    should_redirect_to_app_v2,
)


@dataclass(frozen=True)
class RoutingSmokeTarget:
    label: str
    path: str
    expected_status: tuple[int, ...]
    allow_unauthenticated_redirect: bool = True


DEFAULT_TARGETS = (
    RoutingSmokeTarget("API pronta", "/api/pronto", (200,), False),
    RoutingSmokeTarget("API feature flag", "/api/v1/ui/feature-flags", (200, 302, 303, 401)),
    RoutingSmokeTarget("Legacy fascicoli", "/fascicoli?q=smoke", (200, 302, 303)),
    RoutingSmokeTarget("App V2 flag-off", "/app-v2/documenti", (403, 200, 302, 303)),
    RoutingSmokeTarget("Open redirect bloccato", "/app-v2?next=https://evil.example", (403, 200, 302, 303)),
)


def _external_location(location: str) -> bool:
    if not location:
        return False
    split = urlsplit(location)
    return bool(split.scheme or split.netloc or location.startswith("//"))


def _list_targets() -> int:
    print(f"Mapping legacy -> App V2: {len(LEGACY_TO_APP_V2_TARGETS)}")
    print("Esempi mapping:")
    for legacy, target in list(sorted(LEGACY_TO_APP_V2_TARGETS.items()))[:20]:
        print(f"- {legacy} -> {target}")
    print("Smoke HTTP:")
    for item in DEFAULT_TARGETS:
        print(f"- {item.label}: {item.path} atteso {','.join(str(code) for code in item.expected_status)}")
    print("Query unsafe verificate: next, redirect, return_url, tenant_id, user_id, token")
    return 0


def _session_with_login(base_url: str, username: str, password: str):
    if requests is None:
        raise RuntimeError("requests non installato")
    session = requests.Session()
    login_url = urljoin(base_url.rstrip("/") + "/", "login")
    session.get(login_url, timeout=20)
    response = session.post(
        login_url,
        data={"username": username, "password": password},
        timeout=30,
        allow_redirects=True,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Login smoke non riuscito: HTTP {response.status_code}")
    return session


def _run_static_checks() -> list[str]:
    errors: list[str] = []
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
    if safe != "/app-v2/fascicoli?q=Rossi":
        errors.append(f"Query whitelist non coerente: {safe}")
    decision = should_redirect_to_app_v2("/documenti", {"tab": "template"}, config={})
    if decision.allowed or decision.flag_key != "routes.appV2.documents.list":
        errors.append("Decisione flag-off non fail-closed per /documenti")
    return errors


def _run_http_smoke(base_url: str, username: str, password: str, *, require_credentials: bool) -> int:
    static_errors = _run_static_checks()
    if static_errors:
        print("Smoke statico fallito:\n- " + "\n- ".join(static_errors), file=sys.stderr)
        return 1
    if requests is None:
        print("Modulo requests non disponibile: smoke HTTP saltato.", file=sys.stderr)
        return 2 if require_credentials else 0

    if username and password:
        session = _session_with_login(base_url, username, password)
    else:
        if require_credentials:
            print(
                "Credenziali smoke non impostate: usare IUSENTRA_SMOKE_USERNAME e IUSENTRA_SMOKE_PASSWORD.",
                file=sys.stderr,
            )
            return 2
        print("Credenziali smoke non impostate: eseguo controlli anonimi e statici.")
        session = requests.Session()

    failed: list[str] = []
    for target in DEFAULT_TARGETS:
        url = urljoin(base_url.rstrip("/") + "/", target.path.lstrip("/"))
        response = session.get(url, timeout=45, allow_redirects=False)
        print(f"{response.status_code} {target.path} - {target.label}")
        if response.status_code not in target.expected_status:
            failed.append(f"{target.path}: HTTP {response.status_code}, atteso {target.expected_status}")
        location = response.headers.get("Location", "")
        if _external_location(location):
            failed.append(f"{target.path}: redirect esterno non sicuro verso {location}")
        login_redirect = location.startswith("/login?next=")
        if "evil.example" in location and not login_redirect:
            failed.append(f"{target.path}: parametro unsafe preservato nel redirect")

    if failed:
        print("Smoke routing App V2 fallito:\n- " + "\n- ".join(failed), file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke routing sicuro legacy/App V2.")
    parser.add_argument("--list", action="store_true", help="Mostra mapping e target senza HTTP.")
    parser.add_argument("--base-url", default=os.getenv("IUSENTRA_BASE_URL", "http://localhost:8080"))
    parser.add_argument("--username", default=os.getenv("IUSENTRA_SMOKE_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("IUSENTRA_SMOKE_PASSWORD", ""))
    parser.add_argument("--require-credentials", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        return _list_targets()
    return _run_http_smoke(
        args.base_url,
        args.username,
        args.password,
        require_credentials=args.require_credentials,
    )


if __name__ == "__main__":
    raise SystemExit(main())
