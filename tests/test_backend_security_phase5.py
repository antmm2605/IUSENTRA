from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.backend_security import collect_backend_control_violations


REPO_ROOT = Path(__file__).resolve().parents[1]


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def test_api_react_unauthenticated_security_params_restano_401(tmp_path: Path):
    app = _app(tmp_path)

    with app.test_client() as client:
        response = client.get("/api/v1/ui/fascicoli?tenant_id=studio-b")

    assert response.status_code == 401
    assert "studio-b" not in response.get_data(as_text=True)


def test_api_react_blocca_query_tenant_forzato_dopo_auth(tmp_path: Path):
    app = _app(tmp_path)

    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/fascicoli?tenant_id=studio-b&q=rossi",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    raw = response.get_data(as_text=True)
    assert response.status_code == 400
    assert payload["code"] == "backend_security_control_param"
    assert "tenant_id" in {item["key"] for item in payload["violations"]}
    assert "studio-b" not in raw
    assert str(tmp_path) not in raw


def test_api_react_lascia_passare_filtri_operativi_normali(tmp_path: Path):
    app = _app(tmp_path)

    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/fascicoli?q=rossi&page=1&page_size=25&status=aperto",
            headers={"X-API-Key": "react-test-key"},
        )

    assert response.status_code == 200
    assert response.is_json


def test_api_react_blocca_mass_assignment_tenant_nel_json(tmp_path: Path):
    app = _app(tmp_path)

    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/clienti/delete",
            json={"ids": [], "meta": {"studio_id": "studio-b"}},
            headers={"X-API-Key": "react-test-key"},
        )

    raw = response.get_data(as_text=True)
    assert response.status_code == 400
    assert response.get_json()["code"] == "backend_security_control_param"
    assert "studio-b" not in raw


def test_guardrail_non_blocca_ruolo_o_chiavi_provider_legittime():
    payload = {
        "role": "AMMINISTRATORE",
        "ruolo": "SEGRETERIA",
        "extraPermissions": ["utenti.leggi"],
        "sumup_api_key": "pk_test_non_redatta_nel_test",
        "twilio_token": "token_provider",
    }

    assert collect_backend_control_violations(payload, source="json") == []


def test_guardrail_blocca_path_filesystem_ma_non_path_applicativo():
    lecito = {"path": "/privacy/registro"}
    bloccato = {"path": "C:/studio-b/segreto.pdf"}

    assert collect_backend_control_violations(lecito, source="query") == []
    violazioni = collect_backend_control_violations(bloccato, source="query")
    assert {violazione.key for violazione in violazioni} == {"path"}


def test_portal_public_download_accetta_token_in_query(tmp_path: Path):
    """Il download pubblico del portale clienti deve poter ricevere ?token=... in query.

    Il middleware backend_security blocca 'token' come parametro server-only
    ovunque tranne su questa route specifica, perche' qui il token e' la chiave
    di autenticazione di sessione del portale (link condivisi via email/SMS).
    """
    app = _app(tmp_path)
    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/client-portal/public/documents/cpd_demo/download?token=cp1.fake-token",
        )
    # Non deve essere 400 con backend_security_control_param: la guardia deve
    # permettere il pass-through. La route puo' rispondere con altri codici
    # (es. 200 JSON di errore con codice di sessione non valida).
    assert response.status_code != 400 or response.get_json().get("code") != "backend_security_control_param"


def test_portal_public_token_resta_bloccato_su_altre_route(tmp_path: Path):
    """Su route che NON sono il download del documento, ?token= resta bloccato."""
    app = _app(tmp_path)
    with app.test_client() as client:
        # POST su signature/complete con token in query: deve essere bloccato.
        # Il portale pubblico usa header X-Client-Portal-Token o token nel body JSON,
        # non in query (eccetto per il download via <a href>).
        response = client.post(
            "/api/v1/ui/client-portal/public/signatures/sig_demo/complete?token=cp1.fake",
            json={},
        )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["code"] == "backend_security_control_param"
    assert "token" in {item["key"] for item in payload["violations"]}


def test_tutte_le_api_react_hanno_decorator_auth():
    source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    missing: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        route_decorators = [
            ast.unparse(decorator)
            for decorator in node.decorator_list
            if ast.unparse(decorator).startswith("api_v1_react.")
        ]
        if not route_decorators or node.name.startswith("_"):
            continue
        decorator_text = "\n".join(ast.unparse(decorator) for decorator in node.decorator_list)
        if "_richiedi_auth" not in decorator_text:
            missing.extend(f"{node.name}: {route}" for route in route_decorators)

    assert missing == []


def test_mappa_sicurezza_backend_generata_e_allineata():
    result = subprocess.run(
        [sys.executable, "scripts/react-migration/generate_backend_security_map.py", "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    document = Path("docs/backend-endpoint-security-map.md").read_text(encoding="utf-8")
    assert "Fase 5 Backend Security Review" in document
    assert "/api/v1/ui/fascicoli" in document
    assert "/api/v1/ui/audit" in document
    assert "tenant_id" in document
    assert "policy_denied.backend_security" in document
