"""Guardrail del completamento SQL collettivo, senza dati degli studi."""

import json
from datetime import date
from types import SimpleNamespace

import pytest
from flask import Flask, g

from pct.controllo_studio.completamento import completa_scadute
from pct.storage import StudioDB
from web.bootstrap.controllo_studio_routes import register_controllo_studio_routes


@pytest.fixture
def db(tmp_path):
    database = StudioDB(str(tmp_path / "studio.db"))
    yield database
    database.chiudi()


def inserisci(db, sid, giorno="2026-09-01", stato="APERTO"):
    payload = {"id": sid, "titolo": "Prova controllata", "data_scadenza": giorno, "stato": stato,
               "tipo": "ADEMPIMENTO", "note": "Nota originale", "metadato_origine": {"conservare": True}}
    db.conn.execute("INSERT INTO scadenze (id,tipo,titolo,data_scadenza,stato,note,dati_json) VALUES (?,?,?,?,?,?,?)",
                    (sid, "ADEMPIMENTO", payload["titolo"], giorno, stato, payload["note"], json.dumps(payload)))
    db.conn.execute("COMMIT")


def test_completa_1222_in_una_transazione_preservando_futuro_metadata_e_mirror(db, tmp_path):
    ids = [f"prova-{n}" for n in range(1222)]
    def aggiungi(conn, sid):
        payload = {"id": sid, "tipo": "ADEMPIMENTO", "titolo": "Prova", "metadato_origine": "conservare"}
        conn.execute("INSERT INTO scadenze (id,tipo,titolo,data_scadenza,stato,note,dati_json) VALUES (?,?,?,?,?,?,?)",
                     (sid, "ADEMPIMENTO", "Prova", "2026-09-01", "APERTO", "Nota", json.dumps(payload)))
    db.salva_tabella("scadenze", ids, aggiungi)
    inserisci(db, "futura", "2026-10-01")
    mirror = tmp_path / "scadenze.json"
    risultato = completa_scadute(db, mirror, ids + [ids[0]], oggi=date(2026, 9, 30), attore="operatore-prova")
    assert len(risultato["completate"]) == 1222
    assert risultato["mirror_allineato"]
    assert db.conn.execute("SELECT stato FROM scadenze WHERE id = ?", ("futura",)).fetchone()["stato"] == "APERTO"
    riga = dict(db.conn.execute("SELECT * FROM scadenze WHERE id = ?", (ids[-1],)).fetchone())
    assert riga["stato"] == "COMPLETATO"
    assert "operatore-prova" in riga["note"]
    assert riga["completata_il"].endswith("+02:00")
    assert json.loads(riga["dati_json"])["metadato_origine"] == "conservare"
    assert json.loads(mirror.read_text(encoding="utf-8"))[ids[-1]]["stato"] == "COMPLETATO"
    ripetuta = completa_scadute(db, mirror, ids, oggi=date(2026, 9, 30))
    assert ripetuta["completate"] == [] and ripetuta["gia_completate"] == 1222
    assert dict(db.conn.execute("SELECT * FROM scadenze WHERE id = ?", (ids[-1],)).fetchone()) == riga


@pytest.mark.parametrize("altro,giorno,stato", [("inesistente", None, None), ("oggi", "2026-09-30", "APERTO"),
                                              ("futuro", "2026-10-01", "APERTO"), ("bozza", "2026-09-01", "BOZZA")])
def test_selezione_obsoleta_non_completa_neppure_la_prima_scadenza(db, tmp_path, altro, giorno, stato):
    inserisci(db, "scaduta")
    if giorno:
        inserisci(db, altro, giorno, stato)
    with pytest.raises(ValueError):
        completa_scadute(db, tmp_path / "scadenze.json", ["scaduta", altro], oggi=date(2026, 9, 30))
    assert db.conn.execute("SELECT stato FROM scadenze WHERE id = ?", ("scaduta",)).fetchone()["stato"] == "APERTO"


def test_id_di_un_altro_tenant_non_viene_trovato(db, tmp_path):
    altra = StudioDB(str(tmp_path / "altro-studio.db"))
    try:
        inserisci(altra, "altro-tenant")
        with pytest.raises(ValueError):
            completa_scadute(db, tmp_path / "scadenze.json", ["altro-tenant"])
        assert altra.conn.execute("SELECT stato FROM scadenze").fetchone()["stato"] == "APERTO"
    finally:
        altra.chiudi()


def test_endpoint_richiede_permesso_e_conferma_e_registra_intero_insieme(monkeypatch, db, tmp_path):
    import web.helpers as helpers
    monkeypatch.setattr(helpers, "_studio_db", lambda _: db)
    monkeypatch.setattr(helpers, "_cfg", lambda _: str(tmp_path / "scadenze.json"))
    audit = []
    app = Flask(__name__)
    register_controllo_studio_routes(app, {"audit": lambda *args, **kwargs: audit.append((args, kwargs))})
    permesso = False
    @app.before_request
    def utente():
        g.utente_corrente = SimpleNamespace(username="prova", ha_permesso=lambda _: permesso)
    inserisci(db, "scaduta", "2020-01-01")
    client = app.test_client()
    endpoint = "/api/v1/ui/controllo-studio/scadenze/completa-scadute"
    assert client.post(endpoint, json={"ids": ["scaduta"], "conferma_adempimento": True}).status_code == 403
    permesso = True
    assert client.post(endpoint, json={"ids": ["scaduta"]}).status_code == 400
    assert client.post(endpoint, json={"ids": ["scaduta"], "conferma_adempimento": True}).json["ok"]
    assert json.loads(audit[0][1]["dettagli"])["ids"] == ["scaduta"]
