from __future__ import annotations

from pct.runtime_resilience import clear_runtime_circuit_breakers
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
    assert "thresholds" in payload
    assert "taxonomy" in payload
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
    codes = {alert["code"] for alert in payload["alerts"]}
    assert "LOCAL_AI_RUNTIME_DOWN" in codes
    assert "HTTP_5XX_BUCKET" in codes
    remediations = " ".join(alert["remediation"] for alert in payload["alerts"])
    operator_messages = " ".join(alert.get("operator_message") or "" for alert in payload["alerts"])
    assert "Controlla i log applicativi" in remediations
    assert "verifica il runtime Ollama" in remediations
    assert "Errore applicativo reale" in operator_messages
    assert "AI locale non disponibile" in operator_messages


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
    assert "Messaggio operatore" in html
    assert "Soglia operativa" in html


def test_admin_system_health_restituisce_json_azionabile(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/admin/system-health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] in {"ok", "degraded", "error"}
    assert payload["scheduler"] in {"ok", "degraded", "error"}
    assert payload["ocr"] in {"ok", "degraded", "error"}
    assert payload["ai"] in {"ok", "degraded", "error"}
    assert payload["db"] in {"ok", "degraded", "error"}
    assert "components" in payload
    assert "actions_required" in payload
    assert "error_taxonomy" in payload
    assert payload["error_taxonomy"]["catalog"]


def test_admin_system_health_traduce_alert_in_azioni(tmp_path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    class _FailingLocalAi:
        def monitoring_snapshot(self):
            return {
                "settings": {"enabled": True},
                "runtime": {"status": "error", "last_error": "Runtime Ollama non raggiungibile"},
                "runtime_online": False,
                "counts": {},
            }

    monkeypatch.setattr(
        "lex.providers.local_ai_service.get_local_ai_service",
        lambda: _FailingLocalAi(),
    )

    app.extensions["runtime_metrics"].observe_http(
        method="GET",
        endpoint="health-500",
        status_code=500,
        duration_ms=90.0,
    )

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        response = client.get("/admin/system-health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] in {"degraded", "error"}
    assert payload["ai"] in {"degraded", "error"}
    assert payload["actions_required"]
    active_codes = set(payload["error_taxonomy"]["active_codes"])
    assert "AI_MODEL_UNAVAILABLE" in active_codes


def test_runtime_metrics_endpoint_segnala_circuit_breaker_pec(tmp_path):
    from pct.imap_runtime import get_imap_circuit_breaker

    clear_runtime_circuit_breakers("pec_imap")
    breaker = get_imap_circuit_breaker()
    breaker.record_failure(RuntimeError("Server PEC non raggiungibile"))
    breaker.record_failure(RuntimeError("Server PEC non raggiungibile"))

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        response = client.get("/api/metriche/runtime")

    payload = response.get_json()
    active_codes = set(payload["error_taxonomy"]["active_codes"])
    assert "IMAP_CIRCUIT_OPEN" in active_codes
    assert any(alert["code"] == "IMAP_CIRCUIT_OPEN" for alert in payload["alerts"])


def test_runtime_metrics_endpoint_segnala_circuit_breaker_portali(tmp_path):
    from web.services.telematico_resilience import get_portale_circuit_breaker

    clear_runtime_circuit_breakers("portale:pst:search")
    breaker = get_portale_circuit_breaker("pst", operation="search")
    breaker.record_failure(RuntimeError("Proxy PST non raggiungibile"))
    breaker.record_failure(RuntimeError("Proxy PST non raggiungibile"))

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        response = client.get("/api/metriche/runtime")

    payload = response.get_json()
    active_codes = set(payload["error_taxonomy"]["active_codes"])
    assert "PORTAL_CIRCUIT_OPEN" in active_codes
    assert any(alert["code"] == "PORTAL_CIRCUIT_OPEN" for alert in payload["alerts"])
