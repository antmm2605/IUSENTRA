from __future__ import annotations

from pathlib import Path

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "guida-test-key"
    return app


def test_guida_pratica_api_catalogo_codice_e_checklist(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "guida-test-key"}

    with app.test_client() as client:
        catalogo = client.get("/api/v1/ui/guida-pratica/catalogo", headers=headers)
        codice = client.get("/api/v1/ui/guida-pratica/B02001", headers=headers)
        checklist_alias = client.post("/api/v1/ui/guida-pratica/ESEC_MOB_001/checklist", json={}, headers=headers)

    catalogo_payload = catalogo.get_json()
    codice_payload = codice.get_json()
    alias_payload = checklist_alias.get_json()

    assert catalogo.status_code == 200
    assert catalogo_payload["summary"]["catalogoSize"] == 1048
    assert catalogo_payload["summary"]["coverage"]["curata"] == 1048
    assert codice.status_code == 200
    assert codice_payload["guida"]["coverage"]["level"] == "curata"
    assert codice_payload["guida"]["codice_deposito"]["depositabile"] is True
    assert codice_payload["checklist"]["codice_deposito"]["depositabile"] is True
    assert checklist_alias.status_code == 200
    assert alias_payload["checklist"]["codice_deposito"]["depositabile"] is False
    assert alias_payload["checklist"]["pronto_per_generazione"] is False
    assert any(blocker["type"] == "codice_deposito_non_ufficiale" for blocker in alias_payload["checklist"]["blockers"])


def test_guida_pratica_api_agganciata_al_fascicolo(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "guida-test-key"}
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Ricorso monitorio",
        TipoFascicolo.CIVILE,
        codice_oggetto_pst="010001",
        fonte_codice_oggetto="PST_XSD",
        file_fonte_codice_oggetto="tipi-base.xsd",
    )

    with app.test_client() as client:
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/guida-pratica", headers=headers)

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["fascicolo"]["codice_oggetto_pst"] == "010001"
    assert payload["guida"]["codice"] == "010001"
    assert payload["guida"]["coverage"]["level"] == "curata"
    assert payload["guida"]["codice_deposito"]["depositabile"] is True
    assert payload["checklist"]["codice_deposito"]["depositabile"] is True
