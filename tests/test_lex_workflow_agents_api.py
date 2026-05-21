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


def test_api_approve_con_flag_write_esegue_solo_step_approvati(tmp_path):
    app = _app(tmp_path, enabled=True, write_actions=True)
    headers = {"X-API-Key": "workflow-agents-test-key"}

    with app.test_client() as client:
        preview = client.post(
            "/api/v1/ui/workflow-agents/preview",
            json={"workflow_code": "triage_giornaliero"},
            headers=headers,
        )
        assert preview.status_code == 200
        run = preview.get_json()["run"]
        approved_step = run["proposals"][0]["step_id"]

        approve = client.post(
            f"/api/v1/ui/workflow-agents/runs/{run['id']}/approve",
            json={"approved_step_ids": [approved_step]},
            headers=headers,
        )

    assert approve.status_code == 200
    updated = approve.get_json()["run"]
    executed = [proposal for proposal in updated["proposals"] if proposal["status"] == "executed"]
    pending = [proposal for proposal in updated["proposals"] if proposal["status"] == "pending"]
    assert [proposal["step_id"] for proposal in executed] == [approved_step]
    assert pending
    assert updated["metrics"]["accepted_actions"] == 1


def test_api_approve_senza_step_blocca_scrittura(tmp_path):
    app = _app(tmp_path, enabled=True, write_actions=True)
    headers = {"X-API-Key": "workflow-agents-test-key"}

    with app.test_client() as client:
        preview = client.post(
            "/api/v1/ui/workflow-agents/preview",
            json={"workflow_code": "triage_giornaliero"},
            headers=headers,
        )
        run = preview.get_json()["run"]
        approve = client.post(
            f"/api/v1/ui/workflow-agents/runs/{run['id']}/approve",
            json={"approved_step_ids": []},
            headers=headers,
        )

    assert approve.status_code == 403
    assert approve.get_json()["code"] == "approval_required"


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
