from __future__ import annotations

import sqlite3

from flask import Flask, g

from integrations.sigp.routes import sigp_bp
from integrations.sigp.sync_mapper import normalize_sigp_sync_payload
from integrations.sigp.sync_policy import get_sigp_sync_policy
from integrations.sigp.sync_repository import SigpSyncRepository
from integrations.sigp.sync_service import import_authorized_sigp_payload
from integrations.sigp_sync.routes import sigp_sync_bp


def _payload_reale_gdp_palmi(documenti: int = 16) -> dict:
    return {
        "fascicolo": {
            "ufficio_codice": "0800570152",
            "ufficio": "Ufficio del Giudice di Pace di Palmi",
            "registro": "GDP",
            "numero_rg": "466",
            "anno_rg": "2023",
            "atto_introduttivo": "Citazione",
            "rito": "RITO ORDINARIO",
            "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
            "materia": "Responsabilita extracontrattuale",
            "oggetto": "Azioni di competenza del Giudice di Pace in materia di risarcimento danno",
            "giudice": "CARUSO GIUSEPPE",
            "sezione": "SEZIONE UNICA PALMI",
            "data_iscrizione": "23/02/2023",
            "data_prima_comparizione": "01/03/2023",
            "data_ultima_udienza": "19/04/2023 12:00",
            "stato": "PROCEDIMENTO DEFINITO",
        },
        "parti": [
            {
                "ruolo": "Attore principale",
                "denominazione": "ROBERTINO ALESSI",
                "difensore": "MONTAGNESE ROBERTO",
            },
            {
                "ruolo": "Convenuto principale",
                "denominazione": "ZURICH ASS.NI",
                "difensore": "FOTI ALFREDO",
            },
        ],
        "eventi": [
            {"id": f"EVT-{idx}", "tipo": "Evento di cancelleria", "data": f"{idx:02d}/03/2023"}
            for idx in range(1, 6)
        ],
        "udienze": [
            {"id": f"UD-{idx}", "data": f"{idx:02d}/04/2023", "ora": "12:00", "tipo": "Udienza"}
            for idx in range(1, 5)
        ],
        "documenti": [
            {
                "id_documento": f"DOC-{idx:03d}",
                "idDeposito": f"DEP-{idx:03d}",
                "nomeFile": f"atto_reale_{idx:03d}.pdf",
                "tipoAtto": "Citazione" if idx == 1 else "Allegato",
                "classificazione": "Atto principale" if idx == 1 else "Allegato",
                "sezione": "DocumentiFascicolo",
                "dataDeposito": "23/02/2023",
                "depositante": "MONTAGNESE ROBERTO",
                "mimeType": "application/pdf",
                "dimensioneBytes": 1024 + idx,
            }
            for idx in range(1, documenti + 1)
        ],
        "provvedimenti": [
            {
                "id_documento": "PROV-001",
                "nomeFile": "sentenza.pdf",
                "tipoAtto": "Sentenza",
                "dataDeposito": "19/04/2023",
            }
        ],
        "comunicazioni": [
            {
                "msg_id": "COM-001",
                "tipo": "Comunicazione di cancelleria",
                "oggetto": "Avviso deposito provvedimento",
                "data": "19/04/2023",
                "mittente": "Cancelleria GDP Palmi",
            }
        ],
    }


def test_sigp_sync_policy_vieta_scraping_e_pin_salvato():
    policy = get_sigp_sync_policy()

    assert policy["sicurezza"]["scraping_html"] is False
    assert policy["sicurezza"]["pin_salvato"] is False
    assert policy["sicurezza"]["certificato_sul_pc_studio"] is True
    assert {c["id"] for c in policy["canali"]} == {
        "pst_pubblico",
        "punto_accesso_autorizzato",
        "model_office_sigp",
    }


def test_sigp_sync_mapper_non_taglia_documenti_reali_gdp():
    normalized = normalize_sigp_sync_payload(_payload_reale_gdp_palmi(documenti=31))

    assert normalized["fascicolo"]["numero_rg"] == "466"
    assert normalized["fascicolo"]["anno_rg"] == "2023"
    assert normalized["fascicolo"]["registro"] == "GDP"
    assert len(normalized["documenti"]) == 32
    assert len(normalized["eventi"]) == 5
    assert len(normalized["udienze"]) == 4
    assert normalized["documenti"][0]["tags"] == ["DocumentiFascicolo", "Atto principale", "Citazione"]
    assert normalized["documenti"][-1]["sezione"] == "Provvedimenti"


def test_sigp_sync_repository_persistenza_snapshot_completo(tmp_path):
    db_path = tmp_path / "sigp_sync.db"
    result = import_authorized_sigp_payload(
        _payload_reale_gdp_palmi(documenti=20),
        db_path=db_path,
        fascicolo_locale_id="FASC-466-2023",
    )

    assert result["ok"] is True
    assert result["conteggi"]["documenti"] == 21
    snapshot = SigpSyncRepository(db_path).get_snapshot(result["sigp_fascicolo_id"])
    assert snapshot is not None
    assert snapshot["fascicolo"]["fascicolo_locale_id"] == "FASC-466-2023"
    assert len(snapshot["documenti"]) == 21
    assert len(snapshot["eventi"]) == 5
    assert len(snapshot["udienze"]) == 4

    with sqlite3.connect(db_path) as conn:
        log_count = conn.execute("SELECT COUNT(*) FROM sigp_sync_log").fetchone()[0]
    assert log_count == 1


def test_sigp_sync_route_importa_payload_autorizzato(tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["SIGP_SYNC_DB_PATH"] = str(tmp_path / "sigp_sync.db")

    @app.before_request
    def _login_test_user():
        g.utente_corrente = object()

    app.register_blueprint(sigp_bp)
    client = app.test_client()

    status_response = client.get("/sigp/sync/status")
    assert status_response.status_code == 200
    assert status_response.get_json()["policy"]["sicurezza"]["scraping_html"] is False

    response = client.post(
        "/sigp/sync/importa-payload",
        json={
            "fascicolo_locale_id": "FASC-466-2023",
            "payload": _payload_reale_gdp_palmi(documenti=12),
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["conteggi"]["documenti"] == 13


def test_sigp_sync_ui_patch_usa_payload_reale_e_non_fixture(tmp_path):
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["SIGP_SYNC_DB_PATH"] = str(tmp_path / "sigp_sync.db")

    @app.before_request
    def _login_test_user():
        g.utente_corrente = object()

    app.register_blueprint(sigp_sync_bp)
    client = app.test_client()

    page = client.get("/sigp-sync/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Importa payload reale" in html
    assert "Import test" not in html
    assert "fixture" not in html.lower()

    schema_response = client.post("/sigp-sync/api/schema/ensure")
    assert schema_response.status_code == 200
    assert schema_response.get_json()["ok"] is True

    import_response = client.post(
        "/sigp-sync/api/fascicoli/importa-payload",
        json={
            "fascicolo_locale_id": "FASC-466-2023",
            "payload": _payload_reale_gdp_palmi(documenti=9),
        },
    )
    imported = import_response.get_json()
    assert import_response.status_code == 200
    assert imported["ok"] is True
    assert imported["conteggi"]["documenti"] == 10

    list_response = client.get("/sigp-sync/api/fascicoli")
    items = list_response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["numero_rg"] == "466"

    snapshot_response = client.get(f"/sigp-sync/api/fascicoli/{imported['sigp_fascicolo_id']}")
    snapshot = snapshot_response.get_json()["snapshot"]
    assert len(snapshot["documenti"]) == 10
    assert len(snapshot["udienze"]) == 4
    assert len(snapshot["log"]) == 1

    missing_fixture = client.post("/sigp-sync/api/fascicoli/importa-fixture")
    assert missing_fixture.status_code == 404
