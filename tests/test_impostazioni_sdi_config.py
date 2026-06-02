from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pct.config_studio import ConfigSDI, ConfigStudio
from pct.impostazioni_config_repository import (
    VISIBLE_SETTINGS_SECTIONS,
    save_settings_config_snapshot,
    settings_config_rows_from_config,
)
from pct.storage import StudioDB
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def test_config_studio_sdi_roundtrip_e_snapshot_sql():
    cfg = ConfigStudio()
    cfg.sdi = ConfigSDI(
        abilitato=True,
        modalita="canale_accreditato",
        nome_intermediario="Servizio accreditato",
        codice_canale="ABC1234",
        endpoint_trasmissione="https://sdi.example.test/trasmissione",
        username="studio",
        password="segreta",
        pec_notifiche="sdi@pec.example.it",
        auto_invio_abilitato=True,
        note="Configurazione verificata dallo studio.",
    )

    rows = settings_config_rows_from_config(cfg)
    by_section = {row["section"]: row for row in rows}

    assert "sdi" in by_section
    assert by_section["sdi"]["dati"]["modalita"] == "canale_accreditato"
    assert by_section["sdi"]["dati"]["codice_canale"] == "ABC1234"
    assert "password" in by_section["sdi"]["secret_fields"]
    assert by_section["_manifest"]["dati"]["visible_sections"] == list(VISIBLE_SETTINGS_SECTIONS)


def test_settings_config_sqlite_scrive_tutte_le_sezioni_impostazioni(tmp_path: Path):
    db_path = tmp_path / "studio.db"
    studio_db = StudioDB.get(str(db_path))
    cfg = ConfigStudio()
    cfg.sdi = ConfigSDI(abilitato=True, modalita="intermediario", nome_intermediario="Intermediario test")

    written = save_settings_config_snapshot(
        studio_db,
        cfg,
        extra_sections={
            "pagamenti": {"canali": ["bonifico"]},
            "notifiche": {"clienti_con_numero": 2},
            "backup": {"status": {"completed": True}},
            "calendari": {"profile_count": 1},
        },
    )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM settings_config ORDER BY section").fetchall()
    sections = {row["section"] for row in rows}

    assert written >= 14
    assert {"studio", "pec", "firma", "smtp", "whatsapp", "scheduler", "ai", "sdi", "pagamenti", "notifiche", "backup", "calendari", "_manifest"} <= sections
    sdi = conn.execute("SELECT secret_fields_json, dati_json FROM settings_config WHERE section='sdi'").fetchone()
    assert "password" in json.loads(sdi["secret_fields_json"])
    assert json.loads(sdi["dati_json"])["nome_intermediario"] == "Intermediario test"


def test_react_impostazioni_sdi_payload_e_salvataggio_api(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    response = client.get("/api/v1/ui/impostazioni", headers={"X-API-Key": "react-test-key"})
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "sdi" in payload
    assert any(section["label"] == "Canali SdI" for section in payload["sections"])
    assert payload["sdi"]["password"]["present"] is False

    saved = client.post(
        "/api/v1/ui/impostazioni/sdi",
        json={
            "abilitato": True,
            "modalita": "intermediario",
            "nome_intermediario": "Intermediario FatturaPA",
            "codice_canale": "ABC1234",
            "indirizzo_servizio": "https://sdi.example.test/trasmissione",
            "username": "studio",
            "password": "segreta",
            "pec_notifiche": "sdi@pec.example.it",
            "auto_invio_abilitato": True,
            "note": "Configurazione da fonte accreditata.",
        },
        headers={"X-API-Key": "react-test-key"},
    )

    saved_payload = saved.get_json()
    assert saved.status_code == 200
    assert saved_payload["ok"] is True
    assert saved_payload["updated_section"] == "sdi"
    assert saved_payload["sdi"]["modalita"] == "intermediario"
    assert saved_payload["sdi"]["canale_configurato"] is True
    assert saved_payload["sdi"]["password"]["present"] is True
    assert any(source["id"] == "fatturapa_specifiche_formato" for source in saved_payload["sdi"]["fonti"])


def test_schema_settings_config_presente_per_sqlite_postgresql_e_frontend():
    sqlite_schema = Path("pct/sql/20260602_impostazioni_config.sql").read_text(encoding="utf-8")
    postgres_schema = Path("pct/sql/20260602_impostazioni_config_postgres.sql").read_text(encoding="utf-8")
    frontend_constants = Path("frontend/src/features/impostazioni/constants.ts").read_text(encoding="utf-8")
    frontend_types = Path("frontend/src/features/impostazioni/types.ts").read_text(encoding="utf-8")
    bridge = Path("web/services/react_impostazioni_bridge.py").read_text(encoding="utf-8")

    for schema in (sqlite_schema, postgres_schema):
        assert "CREATE TABLE IF NOT EXISTS settings_config" in schema
        assert "secret_fields_json" in schema
        assert "idx_settings_config_updated" in schema
    assert "{ id: 'sdi', label: 'Canali SdI'" in frontend_constants
    assert "| 'sdi'" in frontend_types
    assert '"sdi"' in bridge
    assert "ConfigSDI" in bridge
