from __future__ import annotations

import sqlite3

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.legal_coverage_surface import build_repository


def test_ai_pipeline_full_genera_review_pubblica_e_aggiorna_il_db(tmp_path):
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

        detail_response = client.get(f"/admin/copertura-ai/api/drafts/{draft_id}")
        assert detail_response.status_code == 200
        detail = detail_response.get_json()
        assert detail["retrieval_examples_json"] is not None
        assert "autopublish_policy" in detail
        assert "ai_governance" in detail

        approve_response = client.post(
            f"/admin/copertura-ai/api/drafts/{draft_id}/approve",
            json={
                "reviewer": "review-e2e",
                "review_reason": "Bozza validata, completata e pronta per il catalogo SQL.",
                "review_signature": "Avv. E2E",
            },
        )
        assert approve_response.status_code == 200
        assert approve_response.get_json()["ok"] is True

        approved_detail = client.get(f"/admin/copertura-ai/api/drafts/{draft_id}")
        assert approved_detail.status_code == 200
        approved_payload = approved_detail.get_json()
        assert "summary" in approved_payload["review_diff_json"]

        publish_response = client.post(
            f"/admin/copertura-ai/api/drafts/{draft_id}/publish",
            json={
                "reviewer": "review-e2e",
                "review_reason": "Publish confermato dopo ultimo controllo strutturato.",
                "review_signature": "Avv. E2E",
            },
        )
        assert publish_response.status_code == 200
        publish_payload = publish_response.get_json()
        assert publish_payload["ok"] is True
        assert publish_payload["result"]["published_total"] == 1

    with app.app_context():
        repository = build_repository(app)
        draft = repository.get_draft(draft_id)
        history = repository.list_published_history(limit=10)
        review_history = repository.list_review_history(draft_id)

    assert draft is not None
    assert draft["status"] == "published"
    assert draft["review_signature"] == "Avv. E2E"
    assert history
    assert int(history[0]["draft_id"]) == draft_id
    assert any(str(row.get("review_action") or "") == "published" for row in review_history)

    conn = sqlite3.connect(str(tmp_path / "studio.db"))
    try:
        procedures = conn.execute("SELECT COUNT(*) FROM legal_procedures").fetchone()[0]
        published = conn.execute("SELECT COUNT(*) FROM published_procedure_history").fetchone()[0]
        audit_rows = conn.execute("SELECT COUNT(*) FROM coverage_review_audit_log").fetchone()[0]
    finally:
        conn.close()

    assert procedures >= 1
    assert published >= 1
    assert audit_rows >= 2
