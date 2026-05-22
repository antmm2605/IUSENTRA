from __future__ import annotations

from pathlib import Path

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
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
    assert catalogo_payload["summary"]["catalogoSize"] >= 1058
    assert catalogo_payload["summary"]["coverage"]["curata"] == catalogo_payload["summary"]["catalogoSize"]
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
        nome_cliente="Cliente Studio",
        controparte="Controparte Test",
        tribunale="Tribunale di Palmi",
        valore_causa=25000,
        valore_preventivato=1200,
        compenso_pattuito=1500,
        data_prossima_udienza="2026-06-15",
        note="Nota operativa del fascicolo",
        codice_oggetto_pst="010001",
        fonte_codice_oggetto="PST_XSD",
        file_fonte_codice_oggetto="tipi-base.xsd",
    )
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "procura alle liti.pdf",
        TipoDocumento.PROCURA,
        b"%PDF-1.4\n% procura\n%%EOF",
        note="Procura caricata",
    )

    with app.test_client() as client:
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/guida-pratica", headers=headers)

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["fascicolo"]["codice_oggetto_pst"] == "010001"
    assert payload["fascicolo"]["cliente"] == "Cliente Studio"
    assert payload["fascicolo"]["preventivo"]["presente"] is True
    assert payload["fascicolo"]["conferimento_incarico"]["presente"] is True
    assert payload["fascicolo"]["procura_delega"]["presente"] is True
    assert payload["fascicolo"]["documenti_count"] == 1
    assert payload["fascicolo"]["scadenze"][0]["tipo"] == "prossima_udienza"
    assert payload["guida"]["codice"] == "010001"
    assert payload["guida"]["coverage"]["level"] == "curata"
    assert payload["guida"]["codice_deposito"]["depositabile"] is True
    assert payload["checklist"]["codice_deposito"]["depositabile"] is True
    assert payload["bloccaLavoro"] is False
    assert payload["documentPlan"]["enabled"] is True
    assert payload["documentPlan"]["import"]["enabled"] is True
    assert "Word" in payload["documentPlan"]["import"]["formats"]


def test_guida_pratica_api_fascicolo_react_legge_stesso_fascicolo_json_legacy(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "guida-test-key"}
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Licenziamento GMO",
        TipoFascicolo.LAVORO,
        codice_oggetto_pst="220101",
        fonte_codice_oggetto="PST_XSD",
        file_fonte_codice_oggetto="tipi-base.xsd",
    )

    with app.test_client() as client:
        dettaglio = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}", headers=headers)
        guida = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/guida-pratica", headers=headers)

    dettaglio_payload = dettaglio.get_json()
    guida_payload = guida.get_json()

    assert dettaglio.status_code == 200
    assert dettaglio_payload.get("notFound", False) is False
    assert dettaglio_payload["fascicolo"]["id"] == fascicolo.id
    assert dettaglio_payload["fascicolo"]["codiceOggettoPst"] == "220101"
    assert guida.status_code == 200
    assert guida_payload["ok"] is True
    assert guida_payload["fascicolo"]["id"] == fascicolo.id
    assert guida_payload["guida"]["codice"] == "220101"


def test_guida_pratica_api_fascicolo_senza_codice_propone_scheda_facoltativa_da_oggetto(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "guida-test-key"}
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Risarcimento davanti al Giudice di Pace",
        TipoFascicolo.CIVILE,
        oggetto="Azioni di competenza del Giudice di Pace in materia di risarcimento danno",
        codice_oggetto_pst="",
    )

    with app.test_client() as client:
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/guida-pratica", headers=headers)

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["guidaPraticaFacoltativa"] is True
    assert payload["guidaPraticaDisponibile"] is True
    assert payload["bloccaLavoro"] is False
    assert payload["guida"]["codice"] == "145009"
    assert payload["guida"]["coverage"]["level"] == "curata"
    assert payload["matchedFromFascicolo"]["confirmation_required"] is True
    assert "deposito" not in payload["message"].casefold()
    assert "Scheda pratica suggerita dall'oggetto del fascicolo" not in payload["message"]
    assert "Scheda pratica individuata dall'oggetto del fascicolo" not in payload["message"]
    assert "Guida pratica facoltativa suggerita" in payload["message"]
    assert payload["checklist"]["blocca_lavoro"] is False
    assert not any(blocker.get("type") == "codice_oggetto_da_confermare" for blocker in payload["checklist"]["blockers"])

    ui_source = Path("frontend/src/components/GuidaPraticaSidebar.tsx").read_text(encoding="utf-8")
    assert "Scheda pratica suggerita dall'oggetto del fascicolo" not in ui_source
    assert "Scheda pratica individuata dall'oggetto del fascicolo" not in ui_source
    assert "'Ora'" in ui_source


def test_guida_pratica_api_fascicolo_senza_codice_resta_facoltativa_e_non_blocca(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "guida-test-key"}
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Fascicolo senza materia",
        TipoFascicolo.CIVILE,
        oggetto="",
        codice_oggetto_pst="",
    )

    with app.test_client() as client:
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/guida-pratica", headers=headers)

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["guidaPraticaFacoltativa"] is True
    assert payload["guidaPraticaDisponibile"] is False
    assert payload["bloccaLavoro"] is False
    assert payload["code"] == "guida_pratica_facoltativa_non_collegata"
    assert "Puoi continuare a lavorare" in payload["message"]
    assert "deposito" not in payload["message"].casefold()
