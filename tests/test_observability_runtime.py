from __future__ import annotations

from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def test_runtime_metrics_endpoint_restituisce_payload_strutturato(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.get("/login")
        client.get("/api/health")
        response = client.get("/api/metriche/runtime")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["runtime"]["http"]["buckets"]
    assert "ocr" in payload
    assert "providers" in payload
    assert "product" in payload
    assert "summary" in payload
    assert "alerts" in payload
    assert payload["product"]["authorization_surfaces"] >= 1
    assert payload["product"]["capabilities"]
    assert payload["storage"]["default_mode"] == "SQLITE"
    assert payload["summary"]["status"] in {"ok", "degraded"}
    assert isinstance(payload["alerts"], list)


def test_runtime_metrics_endpoint_segnala_degradi_e_rimedi(tmp_path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    class _FailingLocalAi:
        def monitoring_snapshot(self):
            return {
                "settings": {"enabled": True, "auto_bootstrap": True},
                "runtime": {
                    "status": "error",
                    "api_base_url": "http://127.0.0.1:11434/api",
                    "chat_model": "gemma3:1b",
                    "embed_model": "embeddinggemma:300m",
                    "last_error": "Runtime Ollama non raggiungibile",
                    "updated_at": "2026-04-19T13:45:00",
                },
                "runtime_online": False,
                "counts": {"documents_total": 0},
            }

    monkeypatch.setattr(
        "lex.providers.local_ai_service.get_local_ai_service",
        lambda: _FailingLocalAi(),
    )

    app.extensions["runtime_metrics"].observe_http(
        method="GET",
        endpoint="test-observability-500",
        status_code=500,
        duration_ms=91.0,
    )

    with app.test_client() as client:
        response = client.get("/api/metriche/runtime")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["degraded"] is True
    titles = {alert["title"] for alert in payload["alerts"]}
    assert "Runtime AI locale non operativo" in titles
    assert "Endpoint con errori 5xx rilevati" in titles
    remediations = " ".join(alert["remediation"] for alert in payload["alerts"])
    assert "Controlla i log applicativi" in remediations
    assert "verifica il runtime Ollama" in remediations


def test_admin_osservabilita_page_e_accessibile_al_superadmin(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.get("/login")
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/admin/osservabilita")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Osservabilita runtime" in html
    assert "Pipeline OCR" in html
    assert "Capability di prodotto" in html
    assert "Segnali di degrado" in html


def test_admin_osservabilita_page_mostra_alert_operativi(tmp_path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    class _FailingLocalAi:
        def monitoring_snapshot(self):
            return {
                "settings": {"enabled": True},
                "runtime": {"status": "missing", "last_error": "Runtime AI non disponibile"},
                "runtime_online": False,
                "counts": {},
            }

    monkeypatch.setattr(
        "lex.providers.local_ai_service.get_local_ai_service",
        lambda: _FailingLocalAi(),
    )

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/admin/osservabilita")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Degradi rilevati" in html
    assert "Runtime AI locale non operativo" in html
    assert "Come intervenire" in html
