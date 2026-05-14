from __future__ import annotations

import sqlite3

from flask import Flask, g

from integrations.sigp.registry import get_active_sigp_schema
from integrations.sigp.repository import SigpRepository
from integrations.sigp.routes import sigp_bp
from integrations.sigp.service import get_sigp_status, prepara_deposito_sigp
from integrations.sigp.xml_builder import build_sigp_xml


def _valid_payload() -> dict:
    return {
        "ufficio": "Ufficio del Giudice di Pace di Palmi",
        "ambiente": "test",
        "procedimento": "RITO ORDINARIO",
        "tipo_atto": "Citazione",
        "difensore": {
            "nome": "Roberto Montagnese",
            "codice_fiscale": "MNTRRT64L01L063H",
            "pec": "roberto.montagnese@example.pec.it",
        },
        "parti": [
            {"ruolo": "Attore", "nome": "ROBERTINO ALESSI", "codice_fiscale": ""},
        ],
        "allegati": [],
    }


def test_sigp_registry_punta_a_professionista_xsd_ufficiale():
    schema = get_active_sigp_schema()

    assert schema.version == "2024-08-27"
    assert schema.main_xsd == "Professionista.xsd"
    assert "ACC3460" in schema.fonte


def test_sigp_service_blocca_predeposito_se_mancano_campi():
    result = prepara_deposito_sigp({})

    assert result["ok"] is False
    assert result["fase"] == "predeposito"
    assert "Ufficio Giudice di Pace mancante." in result["errors"]
    assert "Tipo atto mancante." in result["errors"]


def test_sigp_service_genera_xml_e_restituisce_errore_xsd_mancante():
    result = prepara_deposito_sigp(_valid_payload())

    assert result["ok"] is False
    assert result["fase"] == "validazione_xsd"
    assert result["validation_code"] == "SIGP_XSD_MANCANTE"
    assert "<Professionista" in result["xml"]
    assert "Ufficio del Giudice di Pace di Palmi" in result["xml"]


def test_sigp_xml_builder_include_parti_difensore_e_allegati():
    payload = _valid_payload()
    payload["allegati"] = [{"nome": "atto.pdf", "tipo": "atto_principale", "sha256": "abc"}]

    xml = build_sigp_xml(payload).decode("utf-8")

    assert "<TipoAtto>Citazione</TipoAtto>" in xml
    assert "<CodiceFiscale>MNTRRT64L01L063H</CodiceFiscale>" in xml
    assert 'nome="atto.pdf"' in xml


def test_sigp_repository_crea_schema_sqlite(tmp_path):
    db_path = tmp_path / "sigp.db"
    repo = SigpRepository(db_path)

    repo.ensure_schema()
    versions = repo.list_schema_versions()

    assert versions[0]["version"] == "2024-08-27"
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert "sigp_depositi" in tables
    assert "sigp_validazioni" in tables


def test_sigp_blueprint_api_prepara_deposito():
    app = Flask(__name__)
    app.secret_key = "test"

    @app.before_request
    def _login_test_user():
        g.utente_corrente = object()

    app.register_blueprint(sigp_bp)
    client = app.test_client()

    status_response = client.get("/sigp/status")
    assert status_response.status_code == 200
    assert status_response.get_json()["status"]["module_name"] == "Percorso PST unico"

    response = client.post("/sigp/depositi/prepara", json=_valid_payload())
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["fase"] == "validazione_xsd"
    assert payload["validation_code"] == "SIGP_XSD_MANCANTE"


def test_sigp_status_espone_fonti_e_ambienti():
    status = get_sigp_status()

    assert status["ambienti"]["test"]["codice_gestore_locale"] == "GLMV"
    assert any("27/08/2024" in source["label"] for source in status["sources"])
