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
    assert "Catalogo master versionato" in html
    assert "420 template master" in html
    assert "CIV_ORD_001" in html
    assert "PST_GDP" in html
    assert "PST_CONCORSUALE" in html


def test_catalogo_master_stats_espone_file_e_gruppi():
    stats = catalogo_master_stats()

    assert stats["totale_template"] == 420
    assert stats["gruppi"] == {"advanced": 186, "core": 122, "specialist": 92, "studio_interno": 20}
    assert stats["canali"]["PDP"] == 25
    assert stats["canali"]["PST_GDP"] == 16
