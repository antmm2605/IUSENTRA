"""Contratti API su registri controllati, non accettazione nel browser reale."""
from types import SimpleNamespace
import sqlite3
from uuid import uuid4

import pytest
from flask import Flask, g

from pct.ctu import GestioneCtu
from pct.ctu_repository import CtuRepository
from web.bootstrap.ctu_routes import register_ctu_routes
from web.bootstrap.ctu_compensi_routes import register_ctu_compensi_routes


@pytest.fixture
def api(tmp_path):
    source = tmp_path / "ctu.json"
    manager = GestioneCtu(str(source))
    incarico = manager.nuovo(fascicolo_id="F1", nome_ctu="Tecnico di prova")
    app = Flask(__name__)
    user = SimpleNamespace(ha_permesso=lambda permission: True)
    audits = []
    core = {
        "get_ctu": lambda: GestioneCtu(str(source)),
        "get_fascicoli": lambda: SimpleNamespace(get=lambda key: object() if key in {"F1", "F2"} else None),
        "get_scadenziario": lambda: pytest.fail("Non deve essere aperto lo scadenziario di un altro fascicolo"),
        "audit": lambda *args, **kwargs: audits.append(args),
    }

    @app.before_request
    def identity():
        g.utente_corrente = user

    register_ctu_routes(app, core)
    return app.test_client(), source, incarico.id, core, user, audits


@pytest.mark.parametrize("action,body", [
    ("aggiorna", {"nomeCtu": "Non deve essere scritto"}),
    ("ctp", {"nome": "Non deve essere aggiunto"}),
    ("proponi-scadenze", {}),
])
def test_fascicolo_estraneo_non_scrive(api, action, body):
    client, source, key, core, user, audits = api
    before = source.read_bytes()
    response = client.post(f"/fascicoli/F2/ctu/{key}/{action}", json=body)
    assert response.status_code == 404
    assert source.read_bytes() == before
    assert audits == []


def test_fascicolo_assente_non_crea_incarico(api):
    client, source, key, core, user, audits = api
    before = source.read_bytes()
    response = client.post("/fascicoli/ASSENTE/ctu/nuovo", json={"nomeCtu": "Prova"})
    assert response.status_code == 404
    assert source.read_bytes() == before and audits == []


def test_errore_archivio_non_diventa_elenco_vuoto(api):
    client, source, key, core, user, audits = api
    source.write_text("contenuto non JSON", encoding="utf-8")
    response = client.get("/api/v1/ui/fascicoli/F1/ctu")
    assert response.status_code == 503
    assert response.json["ok"] is False
    assert "incarichi" not in response.json
    assert source.read_text(encoding="utf-8") == "contenuto non JSON"


def test_lettura_non_autorizzata_non_apre_archivio(api):
    client, source, key, core, user, audits = api
    user.ha_permesso = lambda permission: permission != "fascicoli.leggi"
    core["get_ctu"] = lambda: pytest.fail("Archivio non autorizzato")
    response = client.get("/api/v1/ui/fascicoli/F1/ctu")
    assert response.status_code == 403 and "incarichi" not in response.json


def test_elenco_valido_e_fascicolo_mancante_distinti(api):
    client, source, key, core, user, audits = api
    response = client.get("/api/v1/ui/fascicoli/F1/ctu")
    assert response.status_code == 200 and response.json["ok"] is True
    assert response.json["incarichi"][0]["id"] == key
    assert response.json["writeProtocol"]["persistentCommands"] is False
    assert client.get("/api/v1/ui/fascicoli/F2/ctu").json["incarichi"] == []
    assert client.get("/api/v1/ui/fascicoli/ASSENTE/ctu").status_code == 404


def test_consegna_scadenze_fallita_non_conferma_esito_e_non_espone_dettagli(api, monkeypatch):
    client, source, key, core, user, audits = api
    before = source.read_bytes()

    def fail(*args, **kwargs):
        raise RuntimeError("Dettaglio interno da non esporre")

    monkeypatch.setattr(GestioneCtu, "proponi_scadenze", fail)
    response = client.post(f"/fascicoli/F1/ctu/{key}/proponi-scadenze", json={})
    assert response.status_code == 503
    assert response.json["ok"] is False
    assert response.json["code"] == "outcome_not_confirmed"
    assert "Dettaglio interno" not in response.json["message"]
    assert source.read_bytes() == before and audits == []


@pytest.mark.parametrize("body", ["[]", "null", "false", '"testo"', "{non valido"])
def test_json_non_strutturato_non_scrive_o_crea_incarico(api, body):
    client, source, key, core, user, audits = api
    before = source.read_bytes()
    response = client.post("/fascicoli/F1/ctu/nuovo", data=body, content_type="application/json")
    assert response.status_code == 400 and response.json["ok"] is False
    assert source.read_bytes() == before and audits == []


def test_route_sql_replay_conflitto_audit_e_intento_immutabile(tmp_path):
    conn = sqlite3.connect(tmp_path / "ctu.db")
    db = SimpleNamespace(conn=conn)
    repo = CtuRepository(db, "prova", actor_key="avvocato")
    repo.ensure_schema()
    conn.execute("CREATE TABLE audit_log (id TEXT PRIMARY KEY,timestamp TEXT,id_utente TEXT,username TEXT,"
                 "azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT)")
    conn.commit()
    repo.initialize({}, source_sha256="a" * 64, backup_reference="controllato")
    app = Flask(__name__)

    @app.before_request
    def identity():
        g.utente_corrente = SimpleNamespace(ha_permesso=lambda permission: True)

    core = {
        "get_ctu": lambda: GestioneCtu(str(tmp_path / "NON_LEGGERE.json"), repository=CtuRepository(db, "prova", actor_key="avvocato")),
        "get_fascicoli": lambda: SimpleNamespace(get=lambda key: object() if key == "F1" else None),
        "get_scadenziario": lambda: pytest.fail("Non richiesto"),
        "audit": lambda *args, **kwargs: pytest.fail("L'audit SQL deve essere atomico, non duplicato dalla route"),
    }
    register_ctu_routes(app, core)
    register_ctu_compensi_routes(app, core)
    try:
        client = app.test_client()
        missing = client.post("/fascicoli/F1/ctu/nuovo", json={"nomeCtu": "Controllato"})
        assert missing.status_code == 428 and missing.json["code"] == "precondition_required"
        assert conn.execute("SELECT COUNT(*) FROM ctu_records").fetchone()[0] == 0
        body = {"nomeCtu": "Controllato", "commandKey": str(uuid4()), "expectedRevision": 0}
        first = client.post("/fascicoli/F1/ctu/nuovo", json=body)
        assert first.status_code == 200
        receipt = first.json["confirmedCommand"]
        assert receipt == {"scope": core["get_ctu"]().write_protocol["scope"], "commandKey": body["commandKey"],
                           "fascicoloId": "F1", "incaricoId": first.json["incarico"]["id"], "committedRevision": 1}
        assert client.post("/fascicoli/F1/ctu/nuovo", json=body).json == first.json
        assert conn.execute("SELECT COUNT(*) FROM ctu_records").fetchone()[0] == 1
        assert client.post("/fascicoli/F1/ctu/nuovo", json={**body, "nomeCtu": "Diverso"}).status_code == 400
        stale = {**body, "commandKey": str(uuid4())}
        conflict = client.post("/fascicoli/F1/ctu/nuovo", json=stale)
        assert conflict.status_code == 409
        assert conflict.json["rejectedCommand"]["commandKey"] == stale["commandKey"]
        assert conflict.json["rejectedCommand"]["status"] == "rejected"
        iid = first.json["incarico"]["id"]
        update = {"stato": "GIURAMENTO", "commandKey": str(uuid4()), "expectedRevision": 1}
        response = client.post(f"/fascicoli/F1/ctu/{iid}/aggiorna", json=update)
        assert response.status_code == 200 and response.json["incarico"]["stato"] == "GIURAMENTO"
        assert client.post(f"/fascicoli/F1/ctu/{iid}/aggiorna", json=update).json == response.json
        assert conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 2
        assert client.post("/fascicoli/F1/ctu/nuovo", json=stale).json == conflict.json
        assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE esito='RIFIUTATO'").fetchone()[0] == 1
        base = f"/fascicoli/F1/ctu/{iid}"
        operation = {"data": "2026-10-09", "minuti": 120, "commandKey": str(uuid4()), "expectedRevision": 2}
        assert client.post(f"{base}/operazioni", json=operation).status_code == 200
        assert client.post(f"{base}/operazioni", json=operation).status_code == 200
        payload = client.get("/api/v1/ui/fascicoli/F1/ctu").json["incarichi"][0]
        assert len(payload["operazioni"]) == 1
        calc = {"modalita": "vacazioni", "iva_perc": 0, "commandKey": str(uuid4()), "expectedRevision": 3}
        original_calc = client.post(f"{base}/compenso", json=calc)
        assert original_calc.status_code == 200 and original_calc.json["onorario"] == 14.68
        remove = {"commandKey": str(uuid4()), "expectedRevision": 4}
        url = f"{base}/operazioni/{payload['operazioni'][0]['id']}/rimuovi"
        assert client.post(url, json=remove).status_code == 200
        assert client.post(url, json=remove).status_code == 200
        # Anche dopo la rimozione, il replay conserva le vacazioni e l'esito originali.
        assert client.post(f"{base}/compenso", json=calc).json == original_calc.json
        assert original_calc.json["confirmedCommand"]["committedRevision"] == 4
        assert client.post("/fascicoli/F1/ctu/nuovo", json=body).json["confirmedCommand"] == receipt
        assert conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 5
        missing_operation = {"commandKey": str(uuid4()), "expectedRevision": 5}
        denied = client.post(url, json=missing_operation)
        assert denied.status_code == 400 and denied.json["rejectedCommand"]["status"] == "rejected"
        assert client.post(url, json=missing_operation).json == denied.json
        assert conn.execute("SELECT COUNT(*) FROM ctu_commands").fetchone()[0] == 5
        assert not (tmp_path / "NON_LEGGERE.json").exists()
        from pct.scadenziario_sql_writer import COLUMNS
        conn.execute("CREATE TABLE scadenze (" + ','.join(name + " TEXT" + (" PRIMARY KEY" if name == "id" else "") for name in COLUMNS) + ")")
        conn.commit()
        dates = {"termineOsservazioni": "2026-12-01", "commandKey": str(uuid4()), "expectedRevision": 5}
        assert client.post(f"{base}/aggiorna", json=dates).status_code == 200
        delivery = {"commandKey": str(uuid4()), "expectedRevision": 6}
        delivered = client.post(f"{base}/proponi-scadenze", json=delivery)
        assert delivered.status_code == 200 and delivered.json["creati"] == 1
        assert delivered.json["confirmedCommand"]["committedRevision"] == 7
        assert conn.execute("SELECT COUNT(*) FROM scadenze").fetchone()[0] == 1
        assert client.post(f"{base}/aggiorna", json={"nomeCtu": "Aggiornato", "commandKey": str(uuid4()), "expectedRevision": 7}).status_code == 200
        assert client.post(f"{base}/proponi-scadenze", json=delivery).json == delivered.json
        assert conn.execute("SELECT COUNT(*) FROM scadenze").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE azione='ctu.consegna_interna'").fetchone()[0] == 1
    finally:
        conn.close()
