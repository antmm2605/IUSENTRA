from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask, g

import web.blueprints.api_v1_sentenza_economic as bp
from pct.sentenza_economic_repository import SentenzaEconomicRepository
from web.blueprints.api_v1_sentenza_economic import api_v1_sentenza_economic
from web.services.sentenza_economic_runtime import run_analysis


CU_TIERS = [(1100.0, 43.0), (5200.0, 98.0), (26000.0, 237.0)]

SENT_DISTRAZIONE = """TRIBUNALE ORDINARIO DI MILANO
Sezione Prima Civile - R.G. 1234/2025
definitivamente pronunciando, accoglie la domanda proposta da Mario Rossi contro Beta S.r.l.;
condanna la parte convenuta al pagamento delle spese di lite, che liquida in complessivi euro 4.200,00
oltre spese generali, con distrazione in favore del procuratore antistatario avv. Bianchi."""


def _fasc(**kw):
    base = dict(id="F1", numero_rg="1234", anno_rg=2025, nome_cliente="Mario Rossi",
                tribunale="Tribunale di Milano", controparte="Beta S.r.l.")
    base.update(kw)
    return SimpleNamespace(**base)


def test_run_analysis_persiste_audit_eventi_e_decisione(tmp_path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    res = run_analysis(
        fascicolo=_fasc(), testo=SENT_DISTRAZIONE, repo=repo, cu_tiers=CU_TIERS,
        tenant_id="studio-a", actor_id="avv", documento_id="D1", document_hash_sha256="hh",
    )
    assert res["ok"] is True
    assert res["audit"]["safe_to_attach"] is True
    assert "apri_credito_avvocato_antistatario" in [e["event_type"] for e in res["eventi"]]
    # persistenza + registro firmato integro
    assert repo.list_sentenza_audits("studio-a", fascicolo_id="F1")
    assert repo.verify_decisions() is True
    # isolamento tenant
    assert repo.list_sentenza_audits("studio-b", fascicolo_id="F1") == []


def _client(monkeypatch, *, authed: bool, payloads: dict):
    app = Flask(__name__)
    app.register_blueprint(api_v1_sentenza_economic, url_prefix="/api/v1/ui/sentenza-economic")

    @app.before_request
    def _auth():
        g.utente_corrente = SimpleNamespace(id="u1", tenant_slug="studio-a") if authed else None

    monkeypatch.setattr(bp, "api_key_valid_for_request", lambda: False)
    monkeypatch.setattr(bp, "build_sentenza_economic_payload", lambda fid="": payloads.get("list", {"ok": True}))
    monkeypatch.setattr(bp, "analyze_fascicolo_document", lambda p: payloads.get("analyze", {"ok": True}))
    monkeypatch.setattr(bp, "confirm_economic_action", lambda p: payloads.get("confirm", {"ok": True}))
    return app.test_client()


def test_api_richiede_autenticazione(monkeypatch):
    client = _client(monkeypatch, authed=False, payloads={})
    assert client.get("/api/v1/ui/sentenza-economic").status_code == 401


def test_api_list_ok(monkeypatch):
    client = _client(monkeypatch, authed=True, payloads={"list": {"ok": True, "audits": [], "eventi": []}})
    resp = client.get("/api/v1/ui/sentenza-economic")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_api_feature_disabled_mappa_403(monkeypatch):
    client = _client(monkeypatch, authed=True, payloads={"list": {"ok": False, "code": "feature_disabled"}})
    assert client.get("/api/v1/ui/sentenza-economic").status_code == 403


def test_api_analyze_validation_mappa_422(monkeypatch):
    client = _client(monkeypatch, authed=True, payloads={"analyze": {"ok": False, "code": "validation_error"}})
    resp = client.post("/api/v1/ui/sentenza-economic/analyze", json={"fascicoloId": ""})
    assert resp.status_code == 422
