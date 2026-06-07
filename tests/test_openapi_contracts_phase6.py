from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI = REPO_ROOT / "docs" / "openapi.yaml"


def _openapi() -> dict:
    payload = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_api_contracts_generati_e_allineati():
    result = subprocess.run(
        [sys.executable, "scripts/react-migration/generate_api_contracts.py", "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_openapi_validazione_strutturale():
    result = subprocess.run(
        [sys.executable, "scripts/validate_openapi.py", "docs/openapi.yaml"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_openapi_copre_endpoint_p0_p1_con_sicurezza():
    document = _openapi()
    operations = []
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                operations.append((path, method.upper(), operation))

    assert len(operations) >= 180
    p0_p1 = [operation for _path, _method, operation in operations if operation["x-priority"] in {"P0", "P1"}]
    assert len(p0_p1) >= 90
    assert all(operation["x-tenant-scope"] == "current_tenant" for operation in p0_p1)
    assert all(operation.get("x-rbac-permission") for operation in p0_p1)
    assert all(
        operation.get("x-provider-verification")
        in {"auth-error", "success+auth-error", "client-token-error", "public-safe-error"}
        for operation in p0_p1
    )

    documented_paths = set(document["paths"])
    assert "/api/v1/ui/fascicoli" in documented_paths
    assert "/api/v1/ui/fascicoli/{id_fasc}" in documented_paths
    assert "/api/v1/ui/impostazioni" in documented_paths
    assert "/api/v1/ui/utenti/{id_utente}/ruolo" in documented_paths
    assert "/api/v1/ui/sito-studio/builder/assets/upload" in documented_paths
    assert "/api/v1/ui/client-portal/dashboard" in documented_paths
    assert "/api/v1/ui/client-portal/public/invites/{token}" in documented_paths


def test_openapi_provider_verification_reale():
    result = subprocess.run(
        [sys.executable, "scripts/verify_openapi_provider.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "auth-error=" in result.stdout
    assert "public-safe=" in result.stdout
    assert "success=" in result.stdout
    assert "backend-security=1" in result.stdout


def test_openapi_error_schema_documenta_formato_reale_e_normalizzato():
    document = _openapi()
    error_schema = document["components"]["schemas"]["ErrorResponse"]
    properties = error_schema["properties"]
    for field in ("error", "message", "code", "errore", "codice", "request_id", "details"):
        assert field in properties
    for response_name in ("BadRequest", "Unauthorized", "Forbidden", "NotFound", "ValidationError"):
        response = document["components"]["responses"][response_name]
        assert response["content"]["application/json"]["schema"]["$ref"].startswith("#/components/schemas/")
