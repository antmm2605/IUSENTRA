from __future__ import annotations

import re
from pathlib import Path

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app


def _logged_client(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    client = app.test_client()
    _login(client)
    return app, client


def test_tariffario_react_payload_console_operativa(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)

    response = client.get("/api/v1/ui/tariffario")

    assert response.status_code == 200
    assert len(response.get_data()) < 800_000
    payload = response.get_json()
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["route_owner"] == "react_shell"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["stats"]["profiles"] >= 50
    assert payload["stats"]["rules"] >= 100
    assert payload["stats"]["tables"] >= 8
    assert payload["catalog"]["materiaOptions"]
    assert all("regole_tariffarie" not in practice for practice in payload["catalog"]["practices"].values())
    assert payload["state"]["materia"] == "Civile di cognizione"
    assert payload["state"]["grado"] == "Giudice di Pace"
    assert payload["result"]["table"]["rows"]
    assert payload["result"]["included"]
    assert payload["result"]["economic"]["rows"]
    assert payload["result"]["actions"]["preventivo"].startswith("/preventivi/wizard")
    assert payload["result"]["actions"]["parcella"].startswith("/fatturazione/nuova")
    warning_messages = {warning["message"] for warning in payload["warnings"]}
    assert "Creazione preventivo, parcella e flussi fiscali restano sulle route Flask esistenti." not in warning_messages
    assert "Il motore tariffario canonico resta nel backend Python." not in warning_messages
    assert payload["support"]["auditRows"]
    assert payload["support"]["tables"]
    assert payload["support"]["references"]


def test_tariffario_react_e_legacy_smoke(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)

    react_response = client.get("/tariffario")
    legacy_response = client.get("/tariffario?_legacy=1")

    assert react_response.status_code == 200
    react_html = react_response.get_data(as_text=True)
    assert '<html lang="it" class="react-shell-document">' in react_html
    assert 'id="root"' in react_html
    assert legacy_response.status_code == 200
    legacy_html = legacy_response.get_data(as_text=True)
    assert "Tariffario Forense" in legacy_html
    assert "iusentra-react-root" not in legacy_html


def test_tariffario_riepilogo_realtime_sticky_sul_wrapper():
    root = Path(__file__).resolve().parents[1]
    page = (root / "frontend/src/components/TariffarioPage.tsx").read_text(encoding="utf-8")
    css = (root / "frontend/src/components/TariffarioPage.css").read_text(encoding="utf-8")

    assert 'className="iu-tar-summary-dock"' in page
    assert "position: 'fixed'" in page
    assert "window.addEventListener('resize', schedule)" in page
    assert 'className="iu-tar-realtime iu-tar-summary-sticky"' not in page
    assert ".iu-tar-summary-dock {" in css
    assert ".iu-tar-sidebar {" in css
    dock_block = re.search(r"\.iu-tar-summary-dock\s*\{(?P<body>[^}]+)\}", css)
    floating_block = re.search(r"\.iu-tar-summary-holder\.is-floating\s*\{(?P<body>[^}]+)\}", css)
    sidebar_blocks = [
        match.group("body")
        for match in re.finditer(r"\.iu-tar-sidebar\s*\{(?P<body>[^}]+)\}", css)
    ]
    layout_block = re.search(r"\.iu-tar-layout\s*\{(?P<body>[^}]+)\}", css)
    assert dock_block and floating_block and sidebar_blocks and layout_block
    sidebar_body = next(block for block in sidebar_blocks if "align-self: stretch;" in block)
    assert "position: sticky;" not in css
    assert "align-items: stretch;" in layout_block.group("body")
    assert "align-self: stretch;" in sidebar_body
    assert "position: sticky;" not in sidebar_body
    assert "max-height:" not in sidebar_body
    assert "overflow-y: auto;" not in sidebar_body


def test_tariffario_react_post_calcolo_gdp_valore_zero(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/tariffario").get_json()
    state = dict(page["state"])
    state.update(
        {
            "materia": "Civile di cognizione",
            "grado": "Giudice di Pace",
            "valore": "0",
            "complessita": "media",
            "fasi": ["Studio", "Introduttiva", "Istruttoria / Istruzione", "Decisionale"],
            "spese_generali": True,
            "perc_spese_generali": "15",
            "bonus_telematico": False,
        }
    )

    response = client.post("/api/v1/ui/tariffario/calcola", json=state)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["state"]["grado"] == "Giudice di Pace"
    assert payload["profile"]["practiceId"] == "atto_citazione"
    assert payload["result"]["selectedLevel"] == "base"
    assert payload["result"]["selectedTotal"] == "€ 397,90"
    metadata = {item["label"]: item["value"] for item in payload["result"]["metadata"]}
    assert metadata["Materia"] == "Civile di cognizione"
    assert metadata["Grado"] == "Giudice di Pace"
    assert metadata["Scaglione"] == "Fino a € 1.100"


def test_tariffario_react_spese_manuale_mediazione_e_cta(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/tariffario").get_json()
    state = dict(page["state"])
    state.update(
        {
            "accessori": ["mediazione_generale"],
            "esborsi": ["atto_citazione:0", "atto_citazione:2"],
            "mediazione_odm_attiva": True,
            "mediazione_odm_regime": "volontaria",
            "mediazione_odm_esito": "primo_incontro_senza_accordo",
            "manual_lines": [
                {
                    "id": "manuale_test",
                    "descrizione": "Anticipazione concordata",
                    "tipo": "Anticipazione art. 15",
                    "importo": "12,50",
                    "fiscale": "anticipazione art. 15",
                    "inclusa": True,
                }
            ],
        }
    )

    response = client.post("/api/v1/ui/tariffario/calcola", json=state)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    descriptions = [item["descrizione"] for item in payload["result"]["included"]]
    assert any("Contributo Unificato" in item for item in descriptions)
    assert any("Diritti di segreteria" in item for item in descriptions)
    assert any("mediazione" in item.lower() for item in descriptions)
    assert "Anticipazione concordata" in descriptions
    assert payload["result"]["actions"]["preventivo"].startswith("/preventivi/wizard")
    assert payload["result"]["actions"]["parcella"].startswith("/fatturazione/nuova")


def test_tariffario_react_variazioni_adr_e_art15_incidono_sul_totale(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/tariffario").get_json()
    state = dict(page["state"])
    state.update(
        {
            "accessori": ["mediazione_generale"],
            "mediazione_odm_attiva": True,
            "mediazione_odm_regime": "volontaria",
            "mediazione_odm_esito": "primo_incontro_con_accordo",
            "adr_accordo": True,
            "var_attivazione": "50",
            "manual_lines": [
                {
                    "id": "manuale_art15",
                    "descrizione": "Anticipazione art. 15 test",
                    "tipo": "Anticipazione art. 15",
                    "importo": "100,00",
                    "fiscale": "anticipazione_art15",
                    "inclusa": True,
                }
            ],
        }
    )
    base_state = {**state, "var_attivazione": "", "adr_accordo": False}

    base_payload = client.post("/api/v1/ui/tariffario/calcola", json=base_state).get_json()
    changed_payload = client.post("/api/v1/ui/tariffario/calcola", json=state).get_json()

    assert changed_payload["ok"] is True
    assert changed_payload["state"]["var_attivazione"] == "50"
    base_mediazione = next(
        item["importo"]
        for item in base_payload["result"]["included"]
        if item["id"] == "accessorio:mediazione_generale"
    )
    changed_mediazione = next(
        item["importo"]
        for item in changed_payload["result"]["included"]
        if item["id"] == "accessorio:mediazione_generale"
    )
    assert changed_mediazione > base_mediazione
    economic_rows = {row["id"]: row["value"] for row in changed_payload["result"]["economic"]["rows"]}
    assert economic_rows["anticipazioni_art15"] != "€ 0,00"
    assert any("Costi organismo mediazione" in item["descrizione"] for item in changed_payload["result"]["included"])
