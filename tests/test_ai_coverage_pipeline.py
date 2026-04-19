from __future__ import annotations

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def test_ai_coverage_pipeline_esegue_review_publish_con_audit_completo(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(
        {
            **_cfg_web(tmp_path),
            "STUDIO_DB": str(tmp_path / "studio.db"),
        }
    )

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code == 302

        for action in ("audit", "gaps", "drafts"):
            response = client.post(
                f"/admin/copertura-ai/esegui/{action}",
                data={},
                follow_redirects=True,
            )
            assert response.status_code == 200

        drafts_response = client.get("/admin/copertura-ai/api/drafts")
        assert drafts_response.status_code == 200
        drafts = drafts_response.get_json()
        assert drafts
        draft_id = int(drafts[0]["id"])

        approve_response = client.post(
            f"/admin/copertura-ai/api/drafts/{draft_id}/approve",
            json={
                "reviewer": "review-ui",
                "review_reason": "Bozza verificata, corretta e approvata per il catalogo.",
                "review_signature": "Avv. Test E2E",
            },
        )
        assert approve_response.status_code == 200
        assert approve_response.get_json()["ok"] is True

        draft_detail = client.get(f"/admin/copertura-ai/api/drafts/{draft_id}")
        assert draft_detail.status_code == 200
        payload = draft_detail.get_json()
        assert payload["review_reason"] == "Bozza verificata, corretta e approvata per il catalogo."
        assert payload["review_signature"] == "Avv. Test E2E"
        assert payload["review_history"]
        assert "summary" in payload["review_diff_json"]

        publish_response = client.post(
            f"/admin/copertura-ai/api/drafts/{draft_id}/publish",
            json={
                "reviewer": "review-ui",
                "review_reason": "Publish confermato dopo controllo finale del draft.",
                "review_signature": "Avv. Test E2E",
            },
        )
        assert publish_response.status_code == 200
        publish_payload = publish_response.get_json()
        assert publish_payload["ok"] is True
        assert publish_payload["result"]["published_total"] == 1
