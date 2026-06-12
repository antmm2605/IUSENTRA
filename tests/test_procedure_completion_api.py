"""Endpoint /api/v1/ui/procedure-completion: flusso reale via test client."""
from __future__ import annotations

import pytest

from tests.test_applicazioni import _cfg_web
from web.app import create_app


@pytest.fixture()
def app(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["PROCEDURE_COMPLETION_DB"] = str(tmp_path / "intelligence" / "procedure_completion.sqlite")
    cfg["TEMPLATE_ATTI_REPOSITORY_DB"] = str(tmp_path / "template_atti" / "repository.db")
    return create_app(cfg)


def _login(client):
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)


def test_endpoints_richiedono_autenticazione(app):
    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/procedure-completion")
        assert risposta.status_code == 401


def test_dashboard_preview_dettaglio_e_workflow(app):
    with app.test_client() as client:
        _login(client)
        dashboard = client.get("/api/v1/ui/procedure-completion").get_json()
        assert dashboard["ok"] is True
        assert dashboard["enabled"] is True
        assert "procedure_completion.leggi" in dashboard["permissions"]

        anteprima = client.post(
            "/api/v1/ui/procedure-completion/preview",
            json={"codice": "010003", "denominazione": "Procedimento di ingiunzione ante causam"},
        ).get_json()
        assert anteprima["ok"] is True, anteprima
        card = anteprima["card"]
        assert card["codice"] == "010003"
        assert card["sources"]
        assert card["citations"]

        dettaglio = client.get(f"/api/v1/ui/procedure-completion/cards/{card['id']}").get_json()
        assert dettaglio["ok"] is True
        assert dettaglio["draftBanner"] == "Bozza per revisione avvocato"

        inviata = client.post(
            f"/api/v1/ui/procedure-completion/cards/{card['id']}/submit-review",
            json={"reason": "verifica fonti"},
        ).get_json()
        assert inviata["ok"] is True
        assert inviata["card"]["status"] == "needs_review"

        approvata = client.post(
            f"/api/v1/ui/procedure-completion/cards/{card['id']}/approve",
            json={"reason": "fonti verificate"},
        ).get_json()
        assert approvata["ok"] is True, approvata
        assert approvata["card"]["status"] == "approved"
        assert approvata["card"]["review_avvocato"]["reviewer"]

        pubblicata = client.post(
            f"/api/v1/ui/procedure-completion/cards/{card['id']}/publish", json={}
        ).get_json()
        assert pubblicata["ok"] is True, pubblicata
        assert pubblicata["card"]["status"] == "published"

        gaps = client.get("/api/v1/ui/procedure-completion/gaps").get_json()
        assert gaps["ok"] is True


def test_publish_senza_approvazione_bloccata(app):
    with app.test_client() as client:
        _login(client)
        card = client.post(
            "/api/v1/ui/procedure-completion/preview",
            json={"codice": "010003", "denominazione": "Procedimento di ingiunzione"},
        ).get_json()["card"]
        esito = client.post(f"/api/v1/ui/procedure-completion/cards/{card['id']}/publish", json={}).get_json()
        assert esito["ok"] is False
        assert "approved" in esito["errore"].lower() or "bloccata" in esito["errore"].lower()


def test_codice_512075_needs_review_via_api(app):
    with app.test_client() as client:
        _login(client)
        esito = client.post(
            "/api/v1/ui/procedure-completion/preview",
            json={
                "codice": "512075",
                "denominazione": "Accordo di ristrutturazione dei debiti (artt. 57-64 D.Lgs. 14/2019 CCII)",
            },
        ).get_json()
        assert esito["ok"] is True
        assert esito["card"]["status"] == "needs_review"
        approvazione = client.post(
            f"/api/v1/ui/procedure-completion/cards/{esito['card']['id']}/approve", json={}
        ).get_json()
        assert approvazione["ok"] is False


def test_card_inesistente_404(app):
    with app.test_client() as client:
        _login(client)
        risposta = client.get("/api/v1/ui/procedure-completion/cards/card_inesistente")
        assert risposta.status_code == 404
