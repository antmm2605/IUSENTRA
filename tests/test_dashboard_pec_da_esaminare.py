"""Panoramica: «PEC da esaminare» esclude ricevute e comunicazioni già prese in carico dal presidio (31/10/2026)."""

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from pct.email_client import StatoEmail
from web.blueprints import api_v1_react


def test_pec_da_esaminare_esclude_le_gia_presidiate(monkeypatch):
    posta = [
        SimpleNamespace(id="A", stato=StatoEmail.NON_LETTA, timestamp="2026-10-30T10:00:00", oggetto="ACCETTAZIONE"),
        SimpleNamespace(id="B", stato=StatoEmail.NON_LETTA, timestamp="2026-10-30T11:00:00", oggetto="Comunicazione"),
        SimpleNamespace(id="C", stato=StatoEmail.LETTA, timestamp="2026-10-30T12:00:00", oggetto="Letta"),
    ]
    monkeypatch.setattr(api_v1_react, "gestore_panoramica", lambda factory: SimpleNamespace(tutte=lambda cartella: posta))
    monkeypatch.setattr(api_v1_react, "_email_manager", lambda: None)
    monkeypatch.setattr(api_v1_react, "_ordinary_email_manager", lambda: None)
    monkeypatch.setattr(api_v1_react, "_id_email_presidiate", lambda: {"A"})
    with Flask(__name__).app_context():
        _pec, _mail, da_esaminare = api_v1_react._email_rows()
    assert da_esaminare == 1
    etichette = {m["id"]: m["label"] for m in api_v1_react._metrics(
        urgent_actions=0, pec_unread=1, client_messages=0, expiring_quotes=0, missing_engagements_count=0)}
    assert etichette["pec"] == "PEC da esaminare"


def test_id_email_gia_presidiate_senza_archivio(tmp_path):
    from web.services.react_email_bridge import id_email_gia_presidiate

    assert id_email_gia_presidiate(str(tmp_path / "email" / "casella.json")) == set()
