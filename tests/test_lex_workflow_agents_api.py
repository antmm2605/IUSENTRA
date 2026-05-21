from pathlib import Path

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path, *, enabled: bool = True, write_actions: bool = False):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["FEATURE_FLAGS"] = {
        "lex.workflowAgents.enabled": enabled,
        "lex.workflowAgents.writeActions": write_actions,
        "routes.appV2.workflowAgents.home": True,
        "routes.appV2.workflowAgents.reviewQueue": True,
    }
    app = create_app(cfg)
    app.config["API_KEY"] = "workflow-agents-test-key"
    return app


def test_api_preview_bloccata_se_flag_spento(tmp_path):
    app = _app(tmp_path, enabled=False)
    headers = {"X-API-Key": "workflow-agents-test-key"}

    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/workflow-agents/preview",
            json={"workflow_code": "triage_giornaliero"},
            headers=headers,
        )

    assert response.status_code == 403
    assert response.get_json()["code"] == "feature_disabled"


def test_api_preview_salva_run_con_proposte_e_blocca_approve_se_scritture_spente(tmp_path):
    app = _app(tmp_path, enabled=True, write_actions=False)
    headers = {"X-API-Key": "workflow-agents-test-key"}

    with app.test_client() as client:
        preview = client.post(
            "/api/v1/ui/workflow-agents/preview",
            json={"workflow_code": "triage_giornaliero"},
            headers=headers,
        )
        assert preview.status_code == 200
        run = preview.get_json()["run"]
        assert run["status"] == "needs_approval"
        assert run["proposals"]

        approve = client.post(
            f"/api/v1/ui/workflow-agents/runs/{run['id']}/approve",
            json={"approved_step_ids": [run["proposals"][0]["step_id"]]},
            headers=headers,
        )

    assert approve.status_code == 403
    assert approve.get_json()["code"] == "feature_disabled"


def test_api_backend_security_blocca_tenant_id_client(tmp_path):
    app = _app(tmp_path, enabled=True)
    headers = {"X-API-Key": "workflow-agents-test-key"}

    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/workflow-agents/preview",
            json={"workflow_code": "triage_giornaliero", "tenant_id": "altro-studio"},
            headers=headers,
        )

    assert response.status_code == 400
    assert response.get_json()["code"] == "backend_security_control_param"

