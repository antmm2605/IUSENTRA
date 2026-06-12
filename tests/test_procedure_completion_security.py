"""Sicurezza: tenant server-side, RBAC, chiavi client vietate, audit sanificato."""
from __future__ import annotations

import json

import pytest

from pct.auth import GestioneUtenti, RuoloUtente
from pct.procedure_completion.schema import forbidden_keys_in_payload
from tests.test_applicazioni import _cfg_web
from web.app import create_app


@pytest.fixture()
def app(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["PROCEDURE_COMPLETION_DB"] = str(tmp_path / "intelligence" / "procedure_completion.sqlite")
    return create_app(cfg)


def _crea_segreteria(app) -> None:
    with app.app_context():
        gestore = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
            bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
        )
        if not any(user.username == "segreteria" for user in gestore.tutti()):
            gestore.crea(
                username="segreteria",
                password="Segreteria123!",
                ruolo=RuoloUtente.SEGRETERIA,
                email="segreteria@example.it",
                nome_completo="Segreteria Test",
                must_change_password=False,
            )


def test_tenant_id_dal_client_rifiutato(app):
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        for chiave in ("tenant_id", "studio_id", "user_id", "token", "trust_score"):
            risposta = client.post(
                "/api/v1/ui/procedure-completion/preview",
                json={"codice": "010003", "denominazione": "Procedimento di ingiunzione", chiave: "iniettato"},
            )
            assert risposta.status_code == 400, chiave
            payload = risposta.get_json()
            assert payload["code"] == "backend_security_control_param"


def test_chiavi_vietate_anche_annidate():
    assert forbidden_keys_in_payload({"dati": {"tenant_id": "x"}}) == ["tenant_id"]
    assert forbidden_keys_in_payload({"elenco": [{"Token": "y"}]}) == ["Token"]
    assert forbidden_keys_in_payload({"codice": "010003"}) == []


def test_utente_senza_permesso_riceve_403(app):
    _crea_segreteria(app)
    with app.test_client() as client:
        client.post("/login", data={"username": "segreteria", "password": "Segreteria123!"}, follow_redirects=True)
        lettura = client.get("/api/v1/ui/procedure-completion")
        assert lettura.status_code == 403
        scrittura = client.post(
            "/api/v1/ui/procedure-completion/preview",
            json={"codice": "010003", "denominazione": "Procedimento di ingiunzione"},
        )
        assert scrittura.status_code == 403


def test_feature_flag_spento_blocca_tutto(app, monkeypatch):
    monkeypatch.setenv("IUSENTRA_FF_LEX_PROCEDURECOMPLETION_ENABLED", "0")
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        risposta = client.get("/api/v1/ui/procedure-completion")
        assert risposta.status_code == 403
        assert "non attivo" in risposta.get_json()["errore"]


def test_audit_runtime_non_contiene_pii(app, tmp_path):
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        client.post(
            "/api/v1/ui/procedure-completion/preview",
            json={
                "codice": "010003",
                "denominazione": "Procedimento di ingiunzione",
                "note": "Cliente mario.rossi@example.com CF RSSMRA70B10G288K IBAN IT60X0542811101000000123456",
            },
        )
    from pct.procedure_completion.repository import ProcedureCompletionRepository

    repo = ProcedureCompletionRepository(app.config["PROCEDURE_COMPLETION_DB"])
    audit = json.dumps(repo.list_audit_log(), ensure_ascii=False)
    assert "mario.rossi@example.com" not in audit
    assert "RSSMRA70B10G288K" not in audit
    assert "IT60X0542811101000000123456" not in audit
    with repo.connect() as conn:
        runs = conn.execute("SELECT request_json FROM procedure_completion_runs").fetchall()
    testo_runs = " ".join(row["request_json"] for row in runs)
    assert "mario.rossi@example.com" not in testo_runs
    assert "RSSMRA70B10G288K" not in testo_runs
