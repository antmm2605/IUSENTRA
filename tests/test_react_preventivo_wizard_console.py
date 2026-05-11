from __future__ import annotations

from pathlib import Path

from pct.clienti import GestioneClienti, TipoCliente
from pct.preventivi import StatoPreventivo
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
    return _practice_by_label(payload, "Amministrazione di sostegno")


def _practice_by_label(payload: dict, label: str) -> dict:
    practices = payload["catalog"]["practices"]
    if isinstance(practices, dict):
        iterable = practices.values()
    else:
        iterable = practices
    return next(
        practice
        for practice in iterable
        if practice["label"] == label
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


def _cliente_conferimento_pronto(app) -> str:
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Ada",
        cognome="Accettazione",
        codice_fiscale="RSSMRA80A01H501U",
    )
    clienti.aggiorna_recapiti(cliente.id, email="ada.accettazione@example.it")
    clienti.aggiorna_indirizzo(
        cliente.id,
        "residenza",
        via="Via Roma",
        civico="1",
        cap="00100",
        comune="Roma",
        provincia="RM",
    )
    return cliente.id


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
    assert len(response.get_data()) < 1_200_000
    payload = response.get_json()
    practice = _amministrazione_sostegno(payload)
    assert payload["source"] == "repository_reali"
    assert payload["contracts"]["route_owner"] == "react_shell"
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["clients"][0]["id"] == cliente.id
    assert practice["motore_label"]
    assert practice["fasi_default_keys"]
    assert payload["catalog"]["grouped"] == {}
    assert payload["catalog"]["taxonomyRows"] == []
    assert payload["options"]["defaultClause"]["defaultText"]
    assert payload["support"]["references"]


def test_preventivi_archivio_collega_preventivo_guidato():
    source = Path("frontend/src/components/PreventiviPage.tsx").read_text(encoding="utf-8")

    assert 'href="/preventivi/wizard"' in source
    assert "Preventivo guidato" in source


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


def test_preventivo_wizard_react_calcola_ads_per_fasi_senza_compenso_unico(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    practice = _amministrazione_sostegno(page)

    response = client.post(
        "/api/v1/ui/preventivi/wizard/calculate",
        json=_calculation_payload(
            practice,
            fasi=practice.get("fasi_default_keys", []),
            compenso_unico=False,
            voci_bozza=[],
            manual_lines=[],
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["compenso_base"] > 0
    assert payload["economic"]["totale"] > 0
    assert "compenso_unico" not in payload["state"]["fasi"]
    assert set(payload["fasi"]) == {"Studio", "Introduttiva", "Decisionale"}
    assert "ripartito in quote operative" in payload["audit"]["log_calcolo"]


def test_preventivo_wizard_react_calcola_ads_compenso_unico_solo_se_flag_attivo(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    practice = _amministrazione_sostegno(page)

    per_fasi = client.post(
        "/api/v1/ui/preventivi/wizard/calculate",
        json=_calculation_payload(
            practice,
            fasi=["studio"],
            compenso_unico=False,
            voci_bozza=[],
            manual_lines=[],
            spese_generali=False,
            applica_cpa=False,
            applica_iva=False,
        ),
    ).get_json()
    unico = client.post(
        "/api/v1/ui/preventivi/wizard/calculate",
        json=_calculation_payload(
            practice,
            fasi=["studio", "compenso_unico"],
            compenso_unico=True,
            voci_bozza=[],
            manual_lines=[],
            spese_generali=False,
            applica_cpa=False,
            applica_iva=False,
        ),
    ).get_json()

    assert per_fasi["ok"] is True
    assert unico["ok"] is True
    assert set(per_fasi["fasi"]) == {"Studio"}
    assert set(unico["fasi"]) == {"Compenso unico"}
    assert 0 < per_fasi["compenso_base"] < unico["compenso_base"]
    assert "compenso_unico" not in per_fasi["state"]["fasi"]
    assert "compenso_unico" in unico["state"]["fasi"]


def test_preventivo_wizard_react_calcola_tutte_le_voci_area_pratica_aggiunte(tmp_path: Path):
    _app_obj, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    appello_civile = _practice_by_label(page, "Appello civile")
    appello_famiglia = _practice_by_label(page, "Appello famiglia / minori")
    appello_lavoro = _practice_by_label(page, "Appello in materia di lavoro")

    response = client.post(
        "/api/v1/ui/preventivi/wizard/calculate",
        json=_calculation_payload(
            appello_lavoro,
            fasi=["studio", "introduttiva", "decisionale"],
            compenso_unico=False,
            voci_bozza=[],
            manual_lines=[],
            classificazioni_tassonomiche=[
                {"tipologia_pratica_id": appello_civile["id"], "tipologia_pratica_label": appello_civile["label"]},
                {"tipologia_pratica_id": appello_famiglia["id"], "tipologia_pratica_label": appello_famiglia["label"]},
                {"tipologia_pratica_id": appello_lavoro["id"], "tipologia_pratica_label": appello_lavoro["label"]},
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    descriptions = [row["descrizione"] for row in payload["rows"]]
    assert any("Compenso professionale per Appello civile" in item for item in descriptions)
    assert any("Compenso professionale per Appello famiglia / minori" in item for item in descriptions)
    assert any("Compenso professionale per Appello in materia di lavoro" in item for item in descriptions)
    assert sum(1 for item in descriptions if item.startswith("Compenso professionale per Appello")) == 3
    compensation_rows = [row for row in payload["rows"] if row["descrizione"].startswith("Compenso professionale per Appello")]
    assert all(row["importo"] > 0 for row in compensation_rows)
    assert any(item.startswith("Appello civile - Studio") for item in payload["fasi"])
    assert any(item.startswith("Appello famiglia / minori - Decisionale") for item in payload["fasi"])
    assert not any("Istruttoria" in item for item in payload["fasi"])
    assert payload["economic"]["totale"] > sum(row["importo"] for row in compensation_rows)


def test_preventivo_wizard_react_create_crea_preventivo_reale_con_cliente_potenziale_e_clausola(tmp_path: Path):
    app, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    practice = _amministrazione_sostegno(page)
    request_payload = _calculation_payload(
        practice,
        codice_oggetto_pst="014001",
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
    assert preventivo.codice_oggetto_pst == "014001"
    assert preventivo.fonte_codice_oggetto == "PST_XSD"
    assert preventivo.clausola_controversie_attiva is True
    assert preventivo.clausola_controversie_testo == "Clausola controversie verificata nel wizard React."
    assert any(voce.descrizione == "Voce manuale di verifica" for voce in preventivo.voci)


def test_preventivo_wizard_react_rifiuta_codice_oggetto_non_ufficiale(tmp_path: Path):
    _app, client = _logged_client(tmp_path)

    response = client.post("/api/v1/ui/preventivi/wizard/create", json={"codice_oggetto_pst": "IUSENTRA-BOZZA"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is False
    assert any(warning["code"] == "codice_oggetto_pst_non_valido" for warning in payload["warnings"])


def test_preventivo_wizard_react_non_genera_conferimento_senza_accettazione_cliente(tmp_path: Path):
    app, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    practice = _amministrazione_sostegno(page)
    request_payload = _calculation_payload(
        practice,
        id_cliente=_cliente_conferimento_pronto(app),
        codice_oggetto_pst="014001",
        voci_bozza=[],
        manual_lines=[],
        opzioni_finali={
            "preventivo_accettato": False,
            "genera_conferimento": True,
            "apri_fascicolo_guidato": True,
            "informativa_art13_resa": True,
        },
    )

    response = client.post("/api/v1/ui/preventivi/wizard/create", json=request_payload)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["id_preventivo"]
    assert payload.get("id_conferimento", "") == ""
    assert any(warning["code"] == "conferimento_dopo_accettazione" for warning in payload["warnings"])
    with app.app_context():
        preventivo = get_preventivi().get_preventivo(payload["id_preventivo"])
        conferimento = get_preventivi().get_conferimento_principale_preventivo(payload["id_preventivo"])
    assert preventivo is not None
    assert preventivo.stato == StatoPreventivo.BOZZA
    assert not preventivo.accettato_il
    assert conferimento is None


def test_preventivo_wizard_react_genera_conferimento_solo_dopo_accettazione_cliente(tmp_path: Path):
    app, client = _logged_client(tmp_path)
    page = client.get("/api/v1/ui/preventivi/wizard").get_json()
    practice = _amministrazione_sostegno(page)
    request_payload = _calculation_payload(
        practice,
        id_cliente=_cliente_conferimento_pronto(app),
        codice_oggetto_pst="014001",
        voci_bozza=[],
        manual_lines=[],
        opzioni_finali={
            "preventivo_accettato": True,
            "genera_conferimento": True,
            "apri_fascicolo_guidato": False,
            "informativa_art13_resa": True,
        },
    )

    response = client.post("/api/v1/ui/preventivi/wizard/create", json=request_payload)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["id_preventivo"]
    assert payload["id_conferimento"]
    with app.app_context():
        gp = get_preventivi()
        preventivo = gp.get_preventivo(payload["id_preventivo"])
        conferimento = gp.get_conferimento(payload["id_conferimento"])
    assert preventivo is not None
    assert conferimento is not None
    assert preventivo.accettato_il
    assert preventivo.stato == StatoPreventivo.CONVERTITO
    assert conferimento.id_preventivo == preventivo.id
    assert conferimento.codice_oggetto_pst == "014001"
    assert conferimento.fonte_codice_oggetto == "PST_XSD"


def test_preventivo_wizard_react_api_richiede_auth(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()

    assert client.get("/api/v1/ui/preventivi/wizard").status_code == 401
    assert client.post("/api/v1/ui/preventivi/wizard/calculate", json={}).status_code == 401
    assert client.post("/api/v1/ui/preventivi/wizard/create", json={}).status_code == 401
