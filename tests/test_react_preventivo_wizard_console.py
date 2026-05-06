from __future__ import annotations

from pathlib import Path

from pct.clienti import GestioneClienti, TipoCliente
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app
from web.helpers import get_preventivi


def _logged_client(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    client = app.test_client()
    _login(client)
    return app, client


def _amministrazione_sostegno(payload: dict) -> dict:
    practices = payload["catalog"]["practices"]
    if isinstance(practices, dict):
        iterable = practices.values()
    else:
        iterable = practices
    return next(
        practice
        for practice in iterable
        if practice["label"] == "Amministrazione di sostegno"
    )


def _calculation_payload(practice: dict, **overrides) -> dict:
    payload = {
        "id_pratica": practice["id"],
        "oggetto": "Preventivo professionale per amministrazione di sostegno",
        "valore": "0",
        "complessita": "media",
        "grado": practice.get("grado_default") or "Giudice tutelare",
        "regola_tariffaria": "",
        "fasi": [*practice.get("fasi_default_keys", []), "compenso_unico"],
        "compenso_unico": True,
        "spese_generali": True,
        "perc_spese_generali": "15",
        "applica_cpa": True,
        "applica_iva": True,
        "anticipazioni": "0",
        "tariffa_oraria": "0",
        "ore_stimate": "0",
        "voci_bozza": [
            {
                "id": "manuale-test",
                "descrizione": "Voce manuale di verifica",
                "tipo": "Onorario",
                "importo": "12,50",
                "source": "manuale",
            }
        ],
        "note": "Nota professionale di verifica.",
        "clausola": {
            "attiva": True,
            "modello": "TUTELA_CLIENTE_CONSUMATORE",
            "testo": "Clausola controversie verificata nel wizard React.",
            "trattativa_individuale": True,
        },
        "opzioni_finali": {
            "genera_conferimento": False,
            "apri_fascicolo_guidato": False,
            "informativa_art13_resa": True,
        },
    }
    payload.update(overrides)
    return payload


def test_preventivo_wizard_react_bootstrap_console_operativa(tmp_path: Path):
    app, client = _logged_client(tmp_path)
    cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Ada",
        cognome="Sostegno",
        email="ada@example.it",
    )

    response = client.get("/api/v1/ui/preventivi/wizard")

    assert response.status_code == 200
    payload = response.get_json()
    practice = _amministrazione_sostegno(payload)
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["route_owner"] == "react_shell"
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["clients"][0]["id"] == cliente.id
    assert practice["motore_label"]
    assert practice["fasi_default_keys"]
    assert payload["options"]["defaultClause"]["defaultText"]
    assert payload["support"]["references"]


def test_preventivo_wizard_react_e_fallback_legacy_smoke(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)

    react_response = client.get("/preventivi/wizard")
    legacy_response = client.get("/preventivi/wizard?_legacy=1")

    assert react_response.status_code == 200
    react_html = react_response.get_data(as_text=True)
    assert '<html lang="it" class="react-shell-document">' in react_html
    assert 'id="root"' in react_html
    assert legacy_response.status_code == 200
    legacy_html = legacy_response.get_data(as_text=True)
    assert "Preventivo guidato" in legacy_html
    assert 'id="root"' not in legacy_html


def test_preventivo_wizard_react_calcola_ads_con_voci_manuali_e_accessori(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    practice = _amministrazione_sostegno(page)

    response = client.post(
        "/api/v1/ui/preventivi/wizard/calculate",
        json=_calculation_payload(practice),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["profile"]["id"] == practice["id"]
    assert payload["economic"]["totale"] > 0
    descriptions = [row["descrizione"] for row in payload["rows"]]
    assert any("Compenso professionale" in item for item in descriptions)
    assert any("Spese generali" in item for item in descriptions)
    assert "Voce manuale di verifica" in descriptions
    assert payload["economic"]["cpa"] > 0
    assert payload["economic"]["iva"] > 0


def test_preventivo_wizard_react_create_crea_preventivo_reale_con_cliente_potenziale_e_clausola(tmp_path: Path):
    app, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    practice = _amministrazione_sostegno(page)
    request_payload = _calculation_payload(
        practice,
        cliente_rapido_attivo=True,
        cliente_rapido={
            "tipo": "PERSONA_FISICA",
            "nome": "Laura",
            "cognome": "Potenziale",
            "email": "laura.potenziale@example.it",
            "telefono": "3331234567",
            "codice_fiscale": "PNTLRA80A41H501Q",
        },
    )

    response = client.post("/api/v1/ui/preventivi/wizard/create", json=request_payload)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["id_preventivo"]
    assert payload["detail_url"].startswith("/preventivi/")
    with app.app_context():
        preventivo = get_preventivi().get_preventivo(payload["id_preventivo"])
    assert preventivo is not None
    assert preventivo.id_pratica == practice["id"]
    assert preventivo.clausola_controversie_attiva is True
    assert preventivo.clausola_controversie_testo == "Clausola controversie verificata nel wizard React."
    assert any(voce.descrizione == "Voce manuale di verifica" for voce in preventivo.voci)


def test_preventivo_wizard_react_api_richiede_auth(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    assert client.get("/api/v1/ui/preventivi/wizard").status_code == 401
    assert client.post("/api/v1/ui/preventivi/wizard/calculate", json={}).status_code == 401
    assert client.post("/api/v1/ui/preventivi/wizard/create", json={}).status_code == 401
