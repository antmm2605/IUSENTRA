from pathlib import Path
from types import SimpleNamespace

from pct.auth import GestioneUtenti, RuoloUtente
from pct.compilatore_atti import render_compiled_act
from pct.studio_timbro import StudioTimbro, StudioTimbroRepository
from pct.template_atti_master_catalog import load_catalogo_master, load_split_catalogs
from pct.template_atti_prefill import resolve_template_prefill
from web.app import create_app
from web.blueprints.template_atti import template_atti_ui_label


def _app_cfg(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "REDACTION_ASSISTANT_DB": str(tmp_path / "assistente_redazionale.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "editor_layout.json"),
        "CONFIG_STUDIO_DB": str(tmp_path / "config" / "studio.json"),
        "STUDIO_TIMBRO_DB": str(tmp_path / "config" / "studio_timbro.db"),
        "STUDIO_NOME": "Studio Test",
        "STUDIO_AVVOCATO": "Avv. Test",
        "STUDIO_CF": "TSTTST80A01H501A",
        "STUDIO_PIVA": "12345678901",
    }


def test_catalogo_cartabia_schema_prefill_link_e_split():
    master = load_catalogo_master()
    templates = master["template"]
    split = load_split_catalogs()

    assert master["versione"] == "1.2.0"
    assert len(templates) == 420
    assert sum(payload["totale_template"] for payload in split.values()) == 420
    assert len({item["id"] for item in templates}) == 420
    assert all(item.get("cartabia_profile") for item in templates)
    assert all(item.get("prefill_bindings") for item in templates)
    assert all(item.get("link_compilatore_code") for item in templates)


def test_template_famiglia_adr_e_deposito_hanno_controlli_governati():
    templates = load_catalogo_master()["template"]
    famiglia = [item for item in templates if item["processo_area"] == "famiglia_minori"]
    adr = [item for item in templates if item["processo_area"] == "adr"]
    depositabili = [item for item in templates if item["depositabile"]]

    assert famiglia
    assert all({"figli_minori", "documentazione_reddituale", "piano_genitoriale"} <= set(item["required_prefill_fields"]) for item in famiglia)
    assert adr
    assert all("tipo_adr" in item["required_prefill_fields"] and item["condizioni_procedibilita"] for item in adr)
    assert depositabili
    assert all({"pdfa", "firma_digitale"} <= set(item["controlli_deposito"]) for item in depositabili if item["canale_telematico"] in {"PST", "PST_GDP", "PST_CONCORSUALE", "PAT", "PTT", "PDP"})
    assert all("dati_atto_xml" in item["controlli_deposito"] for item in depositabili if item["canale_telematico"] in {"PST", "PST_GDP", "PST_CONCORSUALE"})


def test_timbro_studio_dinamico_e_inserito_prima_del_titolo(tmp_path: Path):
    payload = {
        "studio_nome": "Studio Legale Dinamico",
        "professionista_nome": "Avv. Dinamico",
        "codice_fiscale": "DNMPLA80A01H501A",
        "partita_iva": "10987654321",
        "pec": "studio@example.test",
    }
    timbro = StudioTimbro.from_payload(payload)
    repo = StudioTimbroRepository(str(tmp_path / "studio_timbro.db"))
    saved = repo.save_payload(payload)

    searched_files = [
        path
        for root in ("pct", "web", "frontend/src", "scripts")
        for path in Path(root).rglob("*")
        if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".json", ".html", ".css", ".md"}
    ]
    assert not any("Montagnese" in path.read_text(encoding="utf-8", errors="ignore") for path in searched_files)
    assert saved["studio_nome"] == "Studio Legale Dinamico"
    assert timbro.to_lines()[0]["text"] == "STUDIO LEGALE DINAMICO"

    rendered = render_compiled_act(
        "CIV_CIT_001",
        {
            "_studio_timbro": timbro.to_payload(),
            "recipient_or_court": "Tribunale di Test",
            "client_or_sender": "Cliente Test",
            "counterparty_or_recipient": "Controparte Test",
            "lawyer": "Avv. Dinamico",
            "subject": "Domanda di test",
            "facts": "Fatti di test",
            "requests_or_conclusions": "Conclusioni di test",
            "document_date": "2026-05-12",
        },
    )
    assert rendered.splitlines()[0] == "STUDIO LEGALE DINAMICO"
    assert rendered.index("STUDIO LEGALE DINAMICO") < rendered.index("TRIBUNALE DI TEST")


def test_prefill_resolver_usa_fascicolo_cliente_studio_utente_e_missing_reason():
    cliente = SimpleNamespace(nome_completo="Cliente Alfa")
    fascicolo = SimpleNamespace(
        tribunale="Tribunale di Roma",
        rg_completo="1234/2026",
        titolo="Recupero credito",
        controparte="Beta S.r.l.",
        documenti=[SimpleNamespace(nome="Procura.pdf")],
    )
    utente = SimpleNamespace(nome_completo="Avv. Curatrice")
    timbro = StudioTimbro.from_payload({"studio_nome": "Studio Alfa", "pec": "pec@example.test", "codice_fiscale": "CFSTUDIO"})

    resolved = resolve_template_prefill(
        model_code="CIV_CIT_001",
        required_fields=["cliente", "ufficio_giudiziario", "rg", "pec_studio", "dato_assente"],
        fascicolo=fascicolo,
        cliente=cliente,
        utente=utente,
        studio_timbro=timbro,
        config={"STUDIO_AVVOCATO": "Avv. Config"},
    )

    assert resolved["fields"]["cliente"]["value"] == "Cliente Alfa"
    assert resolved["fields"]["ufficio_giudiziario"]["source"] == "fascicolo"
    assert resolved["fields"]["rg"]["confidence"] == "high"
    assert resolved["fields"]["pec_studio"]["value"] == "pec@example.test"
    assert resolved["fields"]["dato_assente"]["missing_reason"]


def test_compilatore_non_espone_marker_demo_da_dati_storici():
    label = template_atti_ui_label("Procedimento penale demo - fonte repository")

    assert "demo" not in label.lower()
    assert "repository" not in label.lower()
    assert "Procedimento penale di prova" in label
    assert "fonte archivio" in label


def test_endpoint_timbro_studio_e_catalogo_cartabia(tmp_path: Path):
    cfg = _app_cfg(tmp_path)
    GestioneUtenti(db_path=cfg["AUTH_DB"], audit_path=cfg["AUDIT_DB"], secret_key="test").crea(
        username="configuratore",
        password="Admin12345!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="configuratore@example.com",
    )
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "configuratore", "password": "Admin12345!"})
        get_response = client.get("/api/v1/ui/studio/timbro")
        post_response = client.post(
            "/api/v1/ui/studio/timbro",
            json={"timbro": {"studio_nome": "Studio Legale API", "pec": "api@example.test"}},
        )
        catalog_response = client.get("/template-atti/catalogo/data")
        filters_response = client.get("/template-atti/catalogo/filters")
        compliance_response = client.get("/template-atti/CIV_ORD_001/compliance")
        verify_response = client.post("/template-atti/CIV_ORD_001/verifica-deposito", json={"dati": {}, "allegati": {}})

    assert get_response.status_code == 200
    assert get_response.get_json()["ok"] is True
    assert post_response.status_code == 200
    assert post_response.get_json()["preview"]["lines"][0]["text"] == "STUDIO LEGALE API"
    catalog_payload = catalog_response.get_json()
    assert catalog_payload["suite"]["totale_catalogo"] == 612
    assert catalog_payload["suite"]["template_con_cartabia_profile"] == 420
    assert all("cartabia_profile" in item for item in catalog_payload["templates"] if item["fonte_catalogo"] == "master")
    assert "stato_conformita" in filters_response.get_json()["filters"]
    assert compliance_response.get_json()["cartabia"]["stato_conformita"] == "cartabia_review_required"
    assert verify_response.get_json()["cartabia"]["controlli_bloccanti"]
