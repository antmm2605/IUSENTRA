from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.template_atti import GestioneTemplateAtti
from pct.template_atti_catalogo import build_builtin_templates
from pct.template_atti_master_catalog import (
    REQUIRED_TEMPLATE_FIELDS,
    catalogo_master_stats,
    load_catalogo_master,
    load_split_catalogs,
)
from pct.template_catalog_service import build_template_catalog_page_context, get_template_catalog_item
from web.app import create_app


def test_catalogo_master_versionato_ha_schema_canali_e_id_governati():
    payload = load_catalogo_master()
    templates = list(payload["template"])
    ids = {item["id"] for item in templates}
    channels = {item["canale_telematico"] for item in templates}

    assert payload["versione"] == "1.1.0"
    assert len(templates) == payload["totale_template"] == 420
    assert len(ids) == len(templates)
    assert {"CIV_ORD_001", "GDP_001", "MON_001", "ESE_001", "FAM_001", "PEN_001", "TRI_001", "AMM_001"} <= ids
    assert {"PST", "PST_GDP", "PST_CONCORSUALE", "PDP", "PAT", "PTT", "NESSUNO"} <= channels
    assert all(set(REQUIRED_TEMPLATE_FIELDS) <= set(item) for item in templates)


def test_cataloghi_split_sommano_il_master_e_restano_versionati():
    master = load_catalogo_master()
    split = load_split_catalogs()
    total = sum(int(payload["totale_template"]) for payload in split.values())

    assert set(split) == {"core", "advanced", "specialist", "studio_interno"}
    assert total == master["totale_template"]
    assert split["core"]["totale_template"] == 122
    assert split["studio_interno"]["totale_template"] == 20
    assert all(payload["versione"] == master["versione"] for payload in split.values())


def test_template_builtin_include_master_senza_perdere_compilatore_legacy(tmp_path: Path):
    db_path = tmp_path / "template_atti" / "templates.json"
    gestore = GestioneTemplateAtti(str(db_path))
    builtins = [template for template in gestore.tutti() if template.builtin]
    by_id = {template.id: template for template in builtins}
    by_title = {template.titolo: template for template in builtins}
    stats = gestore.statistiche_repository()

    assert len(build_builtin_templates()) == len(builtins)
    assert "CIV_ORD_001" in by_id
    assert "PEN_001" in by_id
    assert by_id["CIV_ORD_001"].codice == "CIV_ORD_001"
    assert by_id["GDP_001"].canale_telematico == "PST_GDP"
    assert by_id["CONC_001"].canale_telematico == "PST_CONCORSUALE"
    assert by_id["CIV_ORD_001"].campi_guidati
    assert by_title["Atto di citazione"].link_compilatore_code == "CIV_CIT_001"
    assert stats["template_repository"] >= 700


def test_catalogo_template_route_mostra_master_versionato(tmp_path: Path):
    cfg = {
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
    }
    GestioneUtenti(db_path=cfg["AUTH_DB"], audit_path=cfg["AUDIT_DB"], secret_key="test").crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "avvocato", "password": "Avv12345!"})
        response = client.get("/template-atti/catalogo")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Suite professionale completa" in html
    assert "192 modelli operativi funzionanti" in html
    assert "420 modelli del catalogo professionale" in html
    assert "22 moduli professionali" in html
    assert "7 canali telematici" in html
    assert "Redazione guidata" in html
    assert "Controlli deposito" in html
    assert "Pre-verifica conformità" in html
    assert "Master professionale" not in html
    assert 'id="viewMasterCatalog"' not in html
    assert 'data-master-card="true"' not in html
    assert html.count('class="cat-card cat-template-card"') == 612
    assert "STR_DIFF_001" in html
    assert "CIV_CIT_001" in html
    assert "/template-atti/compila/STR_DIFF_001" in html
    assert "/template-atti/compila/CIV_CIT_001" in html
    assert "/template-atti/CIV_ORD_001/usa" not in html
    for codice in [
        "CIV_ORD_001",
        "GDP_001",
        "MON_001",
        "FAM_001",
        "VGS_001",
        "LOC_001",
        "PEN_001",
        "TRI_001",
        "AMM_001",
        "STD_001",
        "STD_002",
        "STD_003",
    ]:
        assert codice in html
    assert "Redigi atto" in html
    assert "Controlli deposito" in html
    assert "Riferimenti normativi" in html
    assert "PST_GDP" in html
    assert "PST / Procedure concorsuali" in html
    assert 'data-catalog-filter="materia"' in html
    assert 'data-catalog-filter="portale_deposito"' in html
    assert 'data-catalog-filter="categoria_suite"' in html
    assert 'data-catalog-filter="richiede_pdfa"' in html


def test_catalogo_master_stats_espone_file_e_gruppi():
    stats = catalogo_master_stats()

    assert stats["totale_template"] == 420
    assert stats["gruppi"] == {"advanced": 186, "core": 122, "specialist": 92, "studio_interno": 20}
    assert stats["canali"]["PDP"] == 25
    assert stats["canali"]["PST_GDP"] == 16


def test_catalogo_service_arricchisce_template_e_filtri():
    context = build_template_catalog_page_context()
    template_ids = {item["codice"] for item in context["template_suite"]}

    assert context["suite_summary"]["titolo"] == "Suite professionale completa"
    assert context["suite_summary"]["versione"] == "v1.1.0"
    assert context["suite_summary"]["totale_template"] == 420
    assert context["suite_summary"]["template_operativi"] == 192
    assert context["suite_summary"]["template_master"] == 420
    assert context["suite_summary"]["totale_catalogo"] == 612
    assert context["suite_summary"]["moduli_professionali"] == 22
    assert context["suite_summary"]["canali_governati"] == 7
    assert len(context["suite_groups"]) == 4
    assert {"materia", "categoria_suite", "portale_deposito", "canale_deposito", "rito", "fase", "stato"} <= set(context["template_filters"])
    assert {
        "STR_DIFF_001",
        "CIV_CIT_001",
        "CIV_ORD_001",
        "GDP_001",
        "MON_001",
        "FAM_001",
        "VGS_001",
        "LOC_001",
        "PEN_001",
        "TRI_001",
        "AMM_001",
        "STD_001",
        "STD_002",
        "STD_003",
    } <= template_ids

    civile = get_template_catalog_item("CIV_ORD_001")
    assert civile
    assert civile["portale_deposito"] == "PST / PCT Civile"
    assert civile["richiede_pdfa"] is True
    assert civile["richiede_firma_digitale"] is True
    assert civile["richiede_dati_atto_xml"] is True
    assert civile["controlli_deposito_disponibili"] > 0
    assert civile["link_compilatore_code"] == "CIV_CIT_001"

    operativo = get_template_catalog_item("STR_DIFF_001")
    assert operativo
    assert operativo["fonte_catalogo"] == "compilatore"
    assert operativo["link_compilatore_code"] == "STR_DIFF_001"

    master_items = [item for item in context["template_suite"] if item["fonte_catalogo"] == "master"]
    assert len(master_items) == 420
    assert all(item["link_compilatore_code"] for item in master_items)
    assert get_template_catalog_item("PEN_001")["link_compilatore_code"] == "PEN_NOM_001"
    assert get_template_catalog_item("TRI_001")["link_compilatore_code"] == "TRIB_RIC_001"
    assert get_template_catalog_item("AMM_001")["link_compilatore_code"] == "AMM_RIC_001"
    assert get_template_catalog_item("STD_001")["link_compilatore_code"] == "STR_INC_001"


def test_catalogo_endpoint_data_filters_e_compliance(tmp_path: Path):
    cfg = {
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
    }
    GestioneUtenti(db_path=cfg["AUTH_DB"], audit_path=cfg["AUDIT_DB"], secret_key="test").crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "avvocato", "password": "Avv12345!"})
        data_response = client.get("/template-atti/catalogo/data")
        filters_response = client.get("/template-atti/catalogo/filters")
        compliance_response = client.get("/template-atti/PEN_001/compliance")
        verify_response = client.post("/template-atti/TRI_001/verifica-deposito", json={"dati": {}, "allegati": {}})

    assert data_response.status_code == 200
    data_payload = data_response.get_json()
    assert data_payload["ok"] is True
    assert data_payload["suite"]["totale_template"] == 420
    assert data_payload["suite"]["template_operativi"] == 192
    assert data_payload["suite"]["totale_catalogo"] == 612
    assert len(data_payload["templates"]) == 612
    assert all(
        item["link_compilatore_code"]
        for item in data_payload["templates"]
        if item["fonte_catalogo"] == "master"
    )
    assert "Diritto civile" in data_payload["filters"]["materia"]
    assert "PDP Penale" in data_payload["filters"]["portale_deposito"]

    assert filters_response.status_code == 200
    filters_payload = filters_response.get_json()
    assert filters_payload["ok"] is True
    assert any(chip["label"] == "PDF/A obbligatorio" for chip in filters_payload["quick_filters"])

    assert compliance_response.status_code == 200
    compliance_payload = compliance_response.get_json()
    assert compliance_payload["ok"] is True
    assert compliance_payload["canale_deposito"] == "PDP"
    assert compliance_payload["portale_deposito"] == "PDP Penale"
    assert compliance_payload["controlli"]

    assert verify_response.status_code == 200
    verify_payload = verify_response.get_json()
    assert verify_payload["codice"] == "TRI_001"
    assert verify_payload["canale_deposito"] == "PTT"
    assert verify_payload["ruleset_version"]
