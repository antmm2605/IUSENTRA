from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.test_applicazioni import _crea_operatore, _login  # noqa: E402
from tests.test_web_bootstrap import _cfg_web, _write_studio_config  # noqa: E402
from web.app import create_app  # noqa: E402


OPENAPI = REPO_ROOT / "docs" / "openapi.yaml"

SUCCESS_SAMPLES = [
    "/api/v1/ui/feature-flags",
    "/api/v1/ui/bootstrap",
    "/api/v1/ui/dashboard",
    "/api/v1/ui/fascicoli",
    "/api/v1/ui/clienti",
    "/api/v1/ui/soggetti",
    "/api/v1/ui/agenda",
    "/api/v1/ui/scadenziario",
    "/api/v1/ui/messaggi",
    "/api/v1/ui/email",
    "/api/v1/ui/email-ordinaria",
    "/api/v1/ui/template-atti",
    "/api/v1/ui/impostazioni",
    "/api/v1/ui/admin/database",
    "/api/v1/ui/audit",
    "/api/v1/ui/utenti",
    "/api/v1/ui/profili",
    "/api/v1/ui/studio",
    "/api/v1/ui/telematico",
    "/api/v1/ui/legal-intelligence",
    "/api/v1/ui/legal-intelligence/mediazione/organismi/11/sedi",
    "/api/v1/ui/giurisprudenza",
    "/api/v1/ui/ricerca-legale",
    "/api/v1/ui/fatturazione",
    "/api/v1/ui/preventivi",
    "/api/v1/ui/incassi-pagamenti",
    "/api/v1/ui/compensi-forensi",
    "/api/v1/ui/tariffario",
    "/api/v1/ui/client-portal/dashboard",
    "/api/v1/ui/client-portal/studio/settings",
]

RESERVED_RESPONSE_KEYS = {
    "tenant_id",
    "tenant_slug",
    "studio_id",
    "studio_slug",
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "password_hash",
    "root_path",
}


def _load_openapi() -> dict[str, Any]:
    payload = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("docs/openapi.yaml non e' un oggetto YAML.")
    return payload


def _sample_path(path: str) -> str:
    samples = {
        "id_fasc": "FASCICOLO_TEST",
        "id_doc": "DOC_TEST",
        "id_email": "EMAIL_TEST",
        "id_evento": "EVENTO_TEST",
        "id_utente": "operatore",
        "id_pagamento": "PAGAMENTO_TEST",
        "id_documento": "DOC_ECON_TEST",
        "id_preventivo": "PREV_TEST",
        "id_conferimento": "CONF_TEST",
        "id_cliente": "CLIENTE_TEST",
        "id_soggetto": "SOGGETTO_TEST",
        "id_voce": "VOCE_TEST",
        "id_contatto": "CONTATTO_TEST",
        "id_prenotazione": "PRENOTAZIONE_TEST",
        "page_id": "1",
        "revision_id": "1",
        "asset_id": "1",
        "job_id": "1",
        "article_id": "1",
        "news_id": "1",
        "profile_id": "PROFILO_TEST",
        "account_id": "ACCOUNT_TEST",
        "calendar_id": "CALENDAR_TEST",
        "conflict_id": "CONFLICT_TEST",
        "slot_key": "atto_principale",
        "deposito_id": "DEPOSITO_TEST",
        "model_code": "CIV_CIT_001",
        "module_id": "documenti",
        "surface": "checklist",
        "test_id": "smtp",
        "id_sessione": "SESSIONE_TEST",
        "n": "1",
        "number": "11",
        "pack_id": "commercial_legal",
        "skill_id": "contract_review",
        "run_id": "RUN_TEST",
        "agent_id": "regulatory_monitor",
        "invite_id": "INVITO_TEST",
        "token": "cp1.token-non-valido",
        "signature_id": "FIRMA_TEST",
        "appointment_id": "APPUNTAMENTO_TEST",
        "notification_id": "NOTIFICA_TEST",
        "questionnaire_id": "QUESTIONARIO_TEST",
    }
    result = path
    for name, value in samples.items():
        result = result.replace("{" + name + "}", value)
    return result


def _assert_error_payload(payload: Any, *, path: str, status: int) -> None:
    if not isinstance(payload, dict):
        raise AssertionError(f"{path}: errore {status} non JSON object.")
    has_message = any(isinstance(payload.get(key), str) and payload.get(key) for key in ("message", "errore", "error"))
    has_code = any(payload.get(key) is not None for key in ("code", "codice", "error"))
    if not has_message or not has_code:
        raise AssertionError(f"{path}: errore {status} senza message/code compatibile: {payload!r}")
    raw = repr(payload)
    if ":\\" in raw or "/data/" in raw or "\\data\\" in raw:
        raise AssertionError(f"{path}: errore {status} espone path interno.")


def _assert_success_payload(payload: Any, *, path: str) -> None:
    if not isinstance(payload, dict):
        raise AssertionError(f"{path}: risposta 200 non JSON object.")
    leaked = sorted(key for key in RESERVED_RESPONSE_KEYS if key in payload)
    if leaked:
        raise AssertionError(f"{path}: risposta 200 espone chiavi riservate top-level: {leaked}")


def _operation_items(document: dict[str, Any]):
    for path, path_item in sorted((document.get("paths") or {}).items()):
        if not isinstance(path_item, dict):
            continue
        for method, operation in sorted(path_item.items()):
            if method in {"get", "post", "put", "patch", "delete"} and isinstance(operation, dict):
                yield path, method.upper(), operation


def _request(client, *, method: str, target: str):
    if method == "GET":
        return client.get(target)
    if method == "DELETE":
        return client.delete(target, json={})
    return client.open(target, method=method, json={})


def verify_provider() -> tuple[int, int, int, int]:
    document = _load_openapi()
    with tempfile.TemporaryDirectory(prefix="iusentra-openapi-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        _write_studio_config(root / "config" / "studio.json")
        app = create_app(_cfg_web(root))
        app.config["API_KEY"] = "provider-contract-key"
        _crea_operatore(app)

        auth_errors = 0
        safe_public_errors = 0
        success = 0
        with app.test_client() as client:
            for path, method, operation in _operation_items(document):
                target = _sample_path(path)
                response = _request(client, method=method, target=target)
                provider = operation.get("x-provider-verification")
                if provider in {"client-token-error", "public-safe-error"}:
                    if response.status_code not in {400, 401, 403, 404, 410, 422}:
                        raise AssertionError(
                            f"{method} {target}: atteso errore cliente sicuro, ottenuto {response.status_code}."
                        )
                    _assert_error_payload(response.get_json(silent=True), path=target, status=response.status_code)
                    safe_public_errors += 1
                    continue
                if response.status_code != 401:
                    raise AssertionError(f"{method} {target}: atteso 401 anonimo, ottenuto {response.status_code}.")
                _assert_error_payload(response.get_json(silent=True), path=target, status=response.status_code)
                auth_errors += 1

            _login(client)
            for target in SUCCESS_SAMPLES:
                response = client.get(target)
                if response.status_code != 200:
                    raise AssertionError(f"GET {target}: atteso 200 autenticato, ottenuto {response.status_code}.")
                if not response.is_json:
                    raise AssertionError(f"GET {target}: atteso JSON, content-type={response.content_type}.")
                _assert_success_payload(response.get_json(silent=True), path=target)
                success += 1

            guard = client.get(
                "/api/v1/ui/fascicoli?tenant_id=studio-b",
                headers={"X-API-Key": "provider-contract-key"},
            )
            if guard.status_code != 400:
                raise AssertionError(f"guardrail tenant_id: atteso 400, ottenuto {guard.status_code}.")
            guard_payload = guard.get_json(silent=True)
            _assert_error_payload(guard_payload, path="/api/v1/ui/fascicoli?tenant_id=studio-b", status=400)
            if guard_payload.get("code") != "backend_security_control_param":
                raise AssertionError("guardrail tenant_id senza code backend_security_control_param.")
            guard_checks = 1

    return auth_errors, safe_public_errors, success, guard_checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider verification OpenAPI con Flask test client.")
    parser.parse_args()

    auth_errors, safe_public_errors, success, guard_checks = verify_provider()
    print(
        "OK | provider verification | "
        f"auth-error={auth_errors} | public-safe={safe_public_errors} | success={success} | backend-security={guard_checks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
