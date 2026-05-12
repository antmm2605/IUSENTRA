from tests.test_applicazioni import _cfg_web
from web.app import create_app


def test_calendar_demo_api_connect_sync_and_hide_credentials(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    headers = {"X-API-Key": "react-test-key"}

    with app.test_client() as client:
        connected = client.post("/api/v1/ui/calendari/demo/connect", json={}, headers=headers)
        assert connected.status_code == 200
        connected_payload = connected.get_json()
        assert connected_payload["ok"] is True
        account_id = connected_payload["accounts"][0]["id"]

        listed = client.get("/api/v1/ui/calendari/accounts", headers=headers)
        assert listed.status_code == 200
        listed_payload = listed.get_json()
        raw = listed.get_data(as_text=True)
        assert listed_payload["accounts"][0]["id"] == account_id
        assert "encrypted_credentials" not in raw
        assert "access_token" not in raw
        assert "refresh_token" not in raw

        synced = client.post(f"/api/v1/ui/calendari/accounts/{account_id}/sync", json={}, headers=headers)
        assert synced.status_code == 200
        assert synced.get_json()["ok"] is True
