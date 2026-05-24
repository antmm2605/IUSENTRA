from __future__ import annotations

from html import unescape
from pathlib import Path

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from tests.test_applicazioni import _crea_operatore, _login
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
        codice_rest = client.get("/api/guida/B02001", headers=headers)
        checklist_alias = client.post("/api/v1/ui/guida-pratica/ESEC_MOB_001/checklist", json={}, headers=headers)
        checklist_rest = client.post("/api/guida/ESEC_MOB_001/checklist", json={}, headers=headers)

    catalogo_payload = catalogo.get_json()
    codice_payload = codice.get_json()
    codice_rest_payload = codice_rest.get_json()
    alias_payload = checklist_alias.get_json()
    checklist_rest_payload = checklist_rest.get_json()

    assert catalogo.status_code == 200
    assert catalogo_payload["summary"]["catalogoSize"] >= 1058
    assert catalogo_payload["summary"]["coverage"]["curata"] == catalogo_payload["summary"]["catalogoSize"]
    assert codice.status_code == 200
    assert codice_rest.status_code == 200
    assert codice_payload["guida"]["coverage"]["level"] == "curata"
    assert codice_rest_payload["guida"]["codice"] == codice_payload["guida"]["codice"]
    assert codice_payload["guida"]["codice_deposito"]["depositabile"] is True
    assert codice_payload["guida"]["fonti_verifica_web"]
    assert codice_payload["guida"]["presidi_operativi_integrativi"]["deposito"]["depositabile_dalla_scheda"] is True
    assert codice_payload["guida"]["arricchimento_iusentra"]["non_bloccante"] is True
    assert codice_payload["checklist"]["codice_deposito"]["depositabile"] is True
    assert checklist_alias.status_code == 200
    assert checklist_rest.status_code == 200
    assert alias_payload["checklist"]["codice_deposito"]["depositabile"] is False
    assert checklist_rest_payload["checklist"]["codice_deposito"]["depositabile"] is False
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


def test_template_filtrato_da_guida_pratica_espone_anteprima_operativa(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Opposizione a sanzione amministrativa",
        TipoFascicolo.CIVILE,
        nome_cliente="Crocitti Giovanni",
        tribunale="Giudice di Pace di Palmi",
        codice_oggetto_pst="140011",
        fonte_codice_oggetto="PST_XSD",
    )

    with app.test_client() as client:
        _login(client)
        response = client.get(
            f"/api/v1/ui/template-atti/compila/GDP_001"
            f"?id_fascicolo={fascicolo.id}&guida_pratica=140011&origine=guida_pratica",
        )

    payload = response.get_json()
    preview = payload["guidePreview"]

    assert response.status_code == 200
    assert payload["ok"] is True
    assert preview["enabled"] is True
    assert preview["title"] == "Editor documento con impaginazione modello"
    assert preview["template"]["code"].startswith("GDP_")
    assert preview["template"]["autoLoad"] is True
    assert preview["uploadEndpoint"] == f"/fascicoli/{fascicolo.id}/documenti/carica"
    assert preview["previewPdfHref"] == f"/template-atti/compila/{payload['model']['code']}/pdf"
    assert preview["steps"][4]["label"] == "5 Anteprima modifica"
    assert preview["steps"][4]["state"] == "active"
    assert any(check["label"] == "Timbro studio" for check in preview["layoutChecks"])


def test_template_guida_gdp_risarcimento_non_carica_modello_famiglia(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Azioni di competenza del Giudice di Pace in materia di risarcimento danno",
        TipoFascicolo.CIVILE,
        oggetto="Azioni di competenza del Giudice di Pace in materia di risarcimento danno",
        nome_cliente="Crocitti Giovanni",
        controparte="Comune di Taurianova",
        tribunale="Giudice di Pace di Palmi",
        valore_causa=1500,
        note="Verbale impugnato e domanda risarcitoria da sviluppare.",
        codice_oggetto_pst="",
    )

    with app.test_client() as client:
        _login(client)
        response = client.get(
            f"/api/v1/ui/template-atti/compila/FAM_AFF_001"
            f"?id_fascicolo={fascicolo.id}&guida_pratica=145009&origine=guida_pratica",
        )

    payload = response.get_json()
    fields = payload["baseFields"] + payload["extraFields"]
    field_names = {field["name"] for field in fields}
    court_field = next(field for field in fields if field["name"] == "court_name")

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["model"]["code"] == "GDP_002"
    assert "FAM_AFF_001" != payload["model"]["code"]
    assert payload["guidePreview"]["template"]["code"] == "GDP_002"
    assert "family_court" not in field_names
    assert "children" not in field_names
    assert court_field["type"] == "select"
    assert any("Giudice di Pace di Palmi" in option["label"] for option in court_field["options"])
    assert "Giudice di Pace" in payload["guidePreview"]["initialText"]
    assert "Tribunale per i Minorenni" not in payload["guidePreview"]["initialText"]


def test_template_guida_mantiene_modello_esplicito_coerente_con_la_guida(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Opposizione a decreto",
        TipoFascicolo.CIVILE,
        oggetto="Opposizione a decreto ingiuntivo",
        nome_cliente="Rossi Mario",
        controparte="Bianchi S.r.l.",
        tribunale="Tribunale di Palmi",
        codice_oggetto_pst="100002",
        fonte_codice_oggetto="PST_XSD",
    )

    with app.test_client() as client:
        _login(client)
        response = client.get(
            f"/api/v1/ui/template-atti/compila/CIV_OPPDI_001"
            f"?id_fascicolo={fascicolo.id}&guida_pratica=100002&origine=guida_pratica",
        )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["model"]["code"] == "CIV_OPPDI_001"
    assert payload["guidePreview"]["template"]["code"] == "CIV_OPPDI_001"
    assert "MON_012" not in payload["guidePreview"]["template"]["code"]


def test_template_guida_anteprima_render_e_salvataggio_non_bloccati_da_pst_mancante(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Risarcimento davanti al Giudice di Pace",
        TipoFascicolo.CIVILE,
        oggetto="Risarcimento danni da fatto illecito",
        nome_cliente="Crocitti Giovanni",
        controparte="Comune di Taurianova",
        tribunale="Giudice di Pace di Palmi",
        valore_causa=1500,
        note="Il cliente chiede il risarcimento del danno subito.",
        codice_oggetto_pst="",
    )
    form = {
        "_react_return": "1",
        "id_fascicolo": fascicolo.id,
        "case_id": fascicolo.id,
        "guida_pratica": "145009",
        "title": "Atto di citazione davanti al Giudice di Pace",
        "area": "CIVILE",
        "act_type": "atto introduttivo",
        "matter": "Risarcimento danni",
        "recipient_or_court": "Giudice di Pace di Palmi",
        "client_or_sender": "Crocitti Giovanni",
        "counterparty_or_recipient": "Comune di Taurianova",
        "court_name": "Giudice di Pace di Palmi",
        "plaintiff": "Crocitti Giovanni",
        "defendant": "Comune di Taurianova",
        "claim_subject": "Risarcimento danni da fatto illecito",
        "facts": "Il cliente chiede il risarcimento del danno subito.",
        "legal_arguments": "Responsabilità civile e prova del danno.",
        "requests_or_conclusions": "Accertare la responsabilità e condannare al risarcimento.",
        "evidence_means": "Documenti e prova testimoniale.",
        "documents_offered": "documenti già presenti nel fascicolo",
        "case_value": "1500",
        "testo_generato": "Testo modificato nell'anteprima prima del deposito.",
        "requested_draft": "working_draft",
        "confirmed_warning": "1",
    }

    with app.test_client() as client:
        _login(client)
        preview = client.post(
            f"/template-atti/compila/GDP_002/guida-pratica/anteprima"
            f"?id_fascicolo={fascicolo.id}&guida_pratica=145009&origine=guida_pratica",
            data=form,
        )
        saved = client.post(
            f"/template-atti/compila/GDP_002/guida-pratica/salva"
            f"?id_fascicolo={fascicolo.id}&guida_pratica=145009&origine=guida_pratica",
            data=form,
        )

    preview_payload = preview.get_json()
    saved_payload = saved.get_json()

    assert preview.status_code == 200
    assert preview_payload["ok"] is True
    assert "Giudice di Pace" in preview_payload["testo_generato"]
    assert saved.status_code == 200
    assert saved_payload["ok"] is True
    assert saved_payload["created_as"] == "working_draft"
    assert "Codice oggetto PST mancante" not in saved_payload["message"]


def test_template_guida_word_export_accetta_layout_editor_vuoto(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/template-atti/compila/CIV_OPPDI_001/word",
            data={
                "title": "Ricorso in opposizione",
                "testo_generato": "Testo modificato dall'avvocato nell'anteprima.",
                "testo_generato__editor_layout": "",
            },
        )

    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "application/msword"
    assert "Testo modificato dall'avvocato nell'anteprima." in unescape(body)
    assert "Firmato digitalmente" not in body


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
    assert "Fonti ufficiali verificate" in ui_source
    assert "Presidi operativi integrativi" in ui_source


def test_guida_pratica_ui_fascicolo_restante_nel_rail_operativo():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    sidebar_css = Path("frontend/src/components/GuidaPraticaSidebar.css").read_text(encoding="utf-8")
    layout_css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")

    detail_grid_pos = source.index('className="iu-fas-detail-grid iu-fas-detail-grid--with-guide"')
    guide_column_pos = source.index('<aside className="iu-fas-guide-column"', detail_grid_pos)
    guida_pos = source.index("<GuidaPraticaSidebar", guide_column_pos)
    main_pos = source.index('<div className="iu-fas-detail-main">', guida_pos)
    rail_pos = source.index('<aside className="iu-fas-detail-side">', main_pos)
    gestione_pos = source.index('<DetailSection id="gestione"', rail_pos)

    assert detail_grid_pos < guide_column_pos < guida_pos < main_pos < rail_pos < gestione_pos
    assert ".iu-fas-guide-column > .iu-guida-pratica" in sidebar_css
    assert ".iu-fas-detail-grid--with-guide .iu-fas-detail-side > .iu-guida-pratica" in layout_css
    assert "grid-template-columns:64px minmax(0,1fr) !important" in layout_css
    assert "grid-template-columns:minmax(700px,760px) minmax(0,1fr) !important" in layout_css
    assert "iu-guida-pratica--viewport-pinned" in layout_css
    assert "iu-shell--guide-open" in Path("frontend/src/App.tsx").read_text(encoding="utf-8")


def test_guida_pratica_api_fascicolo_associa_guida_per_codice_separato_non_deposito(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "guida-test-key"}
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "RG 2048/2025 - Opposizione a decreto",
        TipoFascicolo.CIVILE,
        nome_cliente="Rossi Mario",
        oggetto="Opposizione a decreto",
        codice_oggetto_pst="",
        codice_guida_pratica="100002",
    )

    with app.test_client() as client:
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/guida-pratica", headers=headers)

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["guidaPraticaDisponibile"] is True
    assert payload["bloccaLavoro"] is False
    assert payload["fascicolo"]["codice_oggetto_pst"] == ""
    assert payload["fascicolo"]["codice_guida_pratica"] == "100002"
    assert payload["guida"]["codice"] == "100002"
    assert payload["guida"]["denominazione"] == "Opposizione a decreto ingiuntivo (art. 645 c.p.c.)"
    assert payload["guida"]["codice_deposito"]["depositabile"] is False
    assert "matchedFromFascicolo" not in payload


def test_guida_pratica_api_fascicolo_opposizione_decreto_abbreviato_propone_codice_guida(tmp_path: Path):
    app = _app(tmp_path)
    headers = {"X-API-Key": "guida-test-key"}
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "RG 2048/2025 - Opposizione a decreto",
        TipoFascicolo.CIVILE,
        nome_cliente="Rossi Mario",
        oggetto="Opposizione a decreto",
        codice_oggetto_pst="",
    )

    with app.test_client() as client:
        response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/guida-pratica", headers=headers)

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["guidaPraticaDisponibile"] is True
    assert payload["bloccaLavoro"] is False
    assert payload["guida"]["codice"] == "100002"
    assert payload["matchedFromFascicolo"]["matched_by"] == "alias guida pratica"
    assert payload["matchedFromFascicolo"]["guide_only"] is True
    assert payload["fascicolo"]["codice_guida_pratica_suggerito"] == "100002"
    assert "codice_oggetto_pst_suggerito" not in payload["fascicolo"]
    assert "Opposizione a decreto ingiuntivo" in payload["guida"]["denominazione"]
    assert "Nessuna scheda pratica collegata" not in payload["message"]


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
