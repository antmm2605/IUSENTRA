from flask import Flask, g

from web.blueprints import api_v1_documenti_ai as documenti_ai_blueprint


def test_api_sovrascrive_catalogazione_con_payload_completo(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(documenti_ai_blueprint.api_v1_documenti_ai)

    @app.before_request
    def authenticated_user():
        g.utente_corrente = {"id": "avvocato-test"}

    captured: dict[str, object] = {}

    def override(fascicolo_id: str, documento_id: str, **kwargs):
        captured["fascicolo_id"] = fascicolo_id
        captured["documento_id"] = documento_id
        captured.update(kwargs)
        return {
            "id": "catalog-1",
            "document_id": documento_id,
            "status": "confirmed",
            "source_state": "manual_override",
            "document_label": kwargs["document_label"],
        }

    monkeypatch.setattr(documenti_ai_blueprint, "override_document_catalog_assignment", override)

    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/fascicoli/FASC-API/documenti-ai/DOC-API/catalogazione-documentale/sovrascrivi",
            json={
                "document_label": "Procura alle liti",
                "document_section": "procure",
                "document_nature": "procura",
                "deposit_role": "procura",
                "deposit_candidate": True,
                "note": "Confermata sul contenuto.",
            },
        )

    assert response.status_code == 200
    assert response.get_json()["assignment"]["source_state"] == "manual_override"
    assert captured == {
        "fascicolo_id": "FASC-API",
        "documento_id": "DOC-API",
        "document_label": "Procura alle liti",
        "document_section": "procure",
        "document_nature": "procura",
        "deposit_role": "procura",
        "deposit_candidate": True,
        "note": "Confermata sul contenuto.",
    }


def test_api_conferma_catalogazione_registra_la_lettura_delle_evidenze(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(documenti_ai_blueprint.api_v1_documenti_ai)

    @app.before_request
    def authenticated_user():
        g.utente_corrente = {"id": "avvocato-test"}

    captured: dict[str, object] = {}

    def resolve(fascicolo_id: str, documento_id: str, **kwargs):
        captured["fascicolo_id"] = fascicolo_id
        captured["documento_id"] = documento_id
        captured.update(kwargs)
        return {"id": "catalog-1", "document_id": documento_id, "status": "confirmed"}

    monkeypatch.setattr(documenti_ai_blueprint, "resolve_document_catalog_assignment", resolve)

    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/fascicoli/FASC-API/documenti-ai/DOC-API/catalogazione-documentale/revisione",
            json={"status": "confirmed", "evidence_acknowledged": True},
        )

    assert response.status_code == 200
    assert captured == {
        "fascicolo_id": "FASC-API",
        "documento_id": "DOC-API",
        "status": "confirmed",
        "note": "",
        "evidence_acknowledged": True,
    }
