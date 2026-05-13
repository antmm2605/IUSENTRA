from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
except ImportError:  # pragma: no cover - gestito nei runtime minimali
    requests = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "tools" / "react-migration" / "route-manifest.json"
APP_ROUTES_PATH = REPO_ROOT / "frontend" / "src" / "app" / "routes.ts"


@dataclass(frozen=True)
class SmokeTarget:
    label: str
    path: str
    expected_status: tuple[int, ...] = (200,)


DEFAULT_TARGETS = (
    SmokeTarget("feature flag pubblici", "/api/v1/ui/feature-flags", (200,)),
    SmokeTarget("App V2 documenti flag-off", "/app-v2/documenti", (403, 200)),
    SmokeTarget("Regia App V2", "/app-v2", (200,)),
)


def _load_manifest() -> list[dict[str, object]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("routes", [])


def _list_targets() -> int:
    routes = _load_manifest()
    status_counts: dict[str, int] = {}
    for route in routes:
        status = str(route.get("status") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
    print(f"Manifest routes: {len(routes)}")
    for status, count in sorted(status_counts.items()):
        print(f"- {status}: {count}")
    print("Smoke targets:")
    for target in DEFAULT_TARGETS:
        print(f"- {target.label}: {target.path} atteso {','.join(str(code) for code in target.expected_status)}")
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


def _run_http_smoke(base_url: str, username: str, password: str, *, require_credentials: bool) -> int:
    if requests is None:
        print("Modulo requests non disponibile: smoke HTTP saltato.", file=sys.stderr)
        return 2 if require_credentials else 0
    if not username or not password:
        message = "Credenziali smoke non impostate: usare IUSENTRA_SMOKE_USERNAME e IUSENTRA_SMOKE_PASSWORD."
        if require_credentials:
            print(message, file=sys.stderr)
            return 2
        print(message + " Eseguo solo --list implicito.")
        return _list_targets()

    session = _session_with_login(base_url, username, password)
    failed: list[str] = []
    for target in DEFAULT_TARGETS:
        url = urljoin(base_url.rstrip("/") + "/", target.path.lstrip("/"))
        response = session.get(url, timeout=45)
        ok = response.status_code in target.expected_status
        print(f"{response.status_code} {target.path} - {target.label}")
        if not ok:
            failed.append(f"{target.path}: HTTP {response.status_code}, atteso {target.expected_status}")
        if target.path.endswith("/feature-flags") and response.status_code == 200:
            payload = response.json()
            flags = payload.get("flags", {})
            unsafe_enabled = [key for key, value in flags.items() if key.startswith("routes.appV2.") and value is True]
            if unsafe_enabled:
                print("Flag App V2 attivi nello smoke: " + ", ".join(sorted(unsafe_enabled)))
    if failed:
        print("Smoke App V2 fallito:\n- " + "\n- ".join(failed), file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke parametrico per pagine React/App V2.")
    parser.add_argument("--list", action="store_true", help="Mostra target e stato manifest senza chiamate HTTP.")
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
