from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

try:
    import requests
except ImportError:  # pragma: no cover - runtime minimali
    requests = None  # type: ignore[assignment]


@dataclass(frozen=True)
class WorkflowTarget:
    area: str
    priority: str
    label: str
    app_path: str
    legacy_path: str
    api_path: str
    expected_api: tuple[int, ...] = (200, 403)
    expected_page: tuple[int, ...] = (200, 302, 303, 403)


WORKFLOWS: tuple[WorkflowTarget, ...] = (
    WorkflowTarget("panoramica", "P1", "Dashboard studio", "/app-v2", "/", "/api/v1/ui/dashboard"),
    WorkflowTarget("fascicoli", "P0", "Fascicoli e pratiche", "/app-v2/fascicoli", "/fascicoli", "/api/v1/ui/fascicoli"),
    WorkflowTarget("documenti", "P0", "Redazione e documenti", "/app-v2/documenti", "/redazione-atti", "/api/v1/ui/redazione-atti"),
    WorkflowTarget("comunicazioni", "P0", "PEC e comunicazioni", "/app-v2/comunicazioni", "/email", "/api/v1/ui/email"),
    WorkflowTarget("scadenze", "P1", "Scadenziario", "/app-v2/scadenziario", "/scadenziario", "/api/v1/ui/scadenziario"),
    WorkflowTarget("agenda", "P1", "Agenda e udienze", "/app-v2/agenda", "/agenda", "/api/v1/ui/agenda"),
    WorkflowTarget("ricerca", "P1", "Ricerca legale", "/app-v2/lex", "/ricerca-legale", "/api/v1/ui/ricerca-legale"),
    WorkflowTarget("amministrazione", "P0", "Utenti e permessi", "/app-v2/amministrazione", "/utenti", "/api/v1/ui/utenti"),
    WorkflowTarget("impostazioni", "P0", "Impostazioni studio", "/app-v2/impostazioni", "/impostazioni", "/api/v1/ui/impostazioni"),
    WorkflowTarget("telematico", "P0", "Controlli atti", "/app-v2/telematico", "/deposito/checklist", "/api/v1/ui/telematico/surface/checklist"),
)

PROFILE_ENV = {
    "admin": ("IUSENTRA_ADMIN_USER", "IUSENTRA_ADMIN_PASSWORD"),
    "tenant_a": ("IUSENTRA_TENANT_A_USER", "IUSENTRA_TENANT_A_PASSWORD"),
    "tenant_b": ("IUSENTRA_TENANT_B_USER", "IUSENTRA_TENANT_B_PASSWORD"),
    "readonly": ("IUSENTRA_READONLY_USER", "IUSENTRA_READONLY_PASSWORD"),
}


def _credentials() -> dict[str, tuple[str, str]]:
    profiles: dict[str, tuple[str, str]] = {}
    for name, (user_var, password_var) in PROFILE_ENV.items():
        username = os.getenv(user_var, "").strip()
        password = os.getenv(password_var, "")
        if username and password:
            profiles[name] = (username, password)
    return profiles


def _missing_env() -> list[str]:
    missing: list[str] = []
    for user_var, password_var in PROFILE_ENV.values():
        if not os.getenv(user_var, "").strip():
            missing.append(user_var)
        if not os.getenv(password_var, ""):
            missing.append(password_var)
    return missing


def _external_location(location: str) -> bool:
    if not location:
        return False
    split = urlsplit(location)
    return bool(split.scheme or split.netloc or location.startswith("//"))


def _print_inventory() -> None:
    print("Workflow App V2 censiti:")
    for target in WORKFLOWS:
        print(
            f"- {target.priority} {target.area}: {target.label} | "
            f"App V2 {target.app_path} | legacy {target.legacy_path} | API {target.api_path}"
        )
    print("Variabili ambiente supportate:")
    print("- IUSENTRA_BASE_URL")
    for user_var, password_var in PROFILE_ENV.values():
        print(f"- {user_var}")
        print(f"- {password_var}")


def _session_with_login(base_url: str, username: str, password: str):
    if requests is None:
        raise RuntimeError("Modulo requests non installato")
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
        raise RuntimeError(f"Login non riuscito per il profilo smoke: HTTP {response.status_code}")
    return session


def _get(session, base_url: str, path: str, expected: tuple[int, ...]) -> list[str]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    response = session.get(url, timeout=45, allow_redirects=False)
    print(f"{response.status_code} {path}")
    failures: list[str] = []
    if response.status_code not in expected:
        failures.append(f"{path}: HTTP {response.status_code}, atteso {expected}")
    location = response.headers.get("Location", "")
    if _external_location(location):
        failures.append(f"{path}: redirect esterno non sicuro verso {location}")
    if any(token in response.text.lower() for token in ("password_hash", "access_token", "refresh_token", "traceback")):
        failures.append(f"{path}: risposta contiene testo tecnico o segreto vietato")
    return failures


def _run_profile(base_url: str, profile: str, username: str, password: str) -> list[str]:
    assert requests is not None
    print(f"Profilo {profile}: login e workflow P0/P1")
    try:
        session = _session_with_login(base_url, username, password)
    except Exception as exc:  # pragma: no cover - dipende da ambiente esterno
        return [f"{profile}: {exc}"]

    failures: list[str] = []
    for target in WORKFLOWS:
        print(f"[{profile}] {target.priority} {target.label}")
        failures.extend(_get(session, base_url, target.legacy_path, target.expected_page))
        failures.extend(_get(session, base_url, target.api_path, target.expected_api))
        failures.extend(_get(session, base_url, target.app_path, target.expected_page))
    return failures


def _run(base_url: str, require_credentials: bool) -> int:
    if requests is None:
        print("Modulo requests non disponibile.", file=sys.stderr)
        return 2 if require_credentials else 0

    profiles = _credentials()
    if not profiles:
        print("Smoke workflow autenticato non eseguito: credenziali ambiente mancanti.")
        _print_inventory()
        if require_credentials:
            print("Mancano: " + ", ".join(_missing_env()), file=sys.stderr)
            return 2
        return 0

    missing = _missing_env()
    if missing and require_credentials:
        print("Credenziali incomplete: " + ", ".join(missing), file=sys.stderr)
        return 2
    if missing:
        print("Eseguo solo i profili configurati; profili mancanti non dichiarati passati.")

    failures: list[str] = []
    for profile, (username, password) in profiles.items():
        failures.extend(_run_profile(base_url, profile, username, password))

    if failures:
        print("Smoke workflow App V2 fallito:\n- " + "\n- ".join(failures), file=sys.stderr)
        return 1
    print("Smoke workflow App V2 completato per i profili configurati.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke workflow reali App V2 per area.")
    parser.add_argument("--list", action="store_true", help="Mostra inventario workflow senza chiamate HTTP.")
    parser.add_argument("--base-url", default=os.getenv("IUSENTRA_BASE_URL", "http://localhost:8080"))
    parser.add_argument("--require-credentials", action="store_true", help="Fallisce se mancano credenziali complete.")
    args = parser.parse_args(argv)
    if args.list:
        _print_inventory()
        return 0
    return _run(args.base_url, args.require_credentials)


if __name__ == "__main__":
    raise SystemExit(main())
