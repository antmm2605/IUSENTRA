from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.config_studio import GestioneConfigStudio
from web.app import create_app


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


def _client(tmp_path: Path):
    cfg = _app_cfg(tmp_path)
    GestioneConfigStudio(config_path=cfg["CONFIG_STUDIO_DB"]).aggiorna_sezione(
        "studio",
        {"nome": "Studio Test", "avvocato": "Avv. Test", "cf": "TSTTST80A01H501A", "piva": "12345678901"},
    )
    GestioneUtenti(db_path=cfg["AUTH_DB"], audit_path=cfg["AUDIT_DB"], secret_key="test").crea(
        username="configuratore",
        password="Admin12345!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="configuratore@example.com",
    )
    app = create_app(cfg)
    client = app.test_client()
    client.post("/login", data={"username": "configuratore", "password": "Admin12345!"})
    return client


def test_api_template_atti_strict_inventory_prefill_cartabia_timbro(tmp_path: Path):
    client = _client(tmp_path)

    inventory = client.get("/template-atti/inventory/data")
    catalog = client.get("/template-atti/catalogo/data")
    filters = client.get("/template-atti/catalogo/filters")
    prefill = client.get("/template-atti/CIV_ORD_001/prefill")
    resolved = client.post("/template-atti/CIV_ORD_001/prefill/resolve", json={"values": {}})
    merged = client.post(
        "/template-atti/CIV_ORD_001/prefill/merge",
        json={"values": {"client_or_sender": "Cliente scritto dall'utente"}},
    )
    compliance = client.get("/template-atti/CIV_ORD_001/cartabia-compliance")
    cartabia = client.post("/template-atti/CIV_ORD_001/verifica-cartabia", json={"values": {}})
    complete = client.post("/template-atti/CIV_ORD_001/verifica-completa", json={"values": {}, "allegati": {}})
    timbro_get = client.get("/api/v1/ui/studio/timbro")
    timbro_preview = client.get("/api/v1/ui/studio/timbro/preview")
    timbro_post = client.post("/api/v1/ui/studio/timbro", json={"timbro": {"studio_nome": "Studio API"}})

    assert inventory.status_code == 200
    assert inventory.get_json()["stats"]["expected_total"] == 1320
    assert catalog.status_code == 200
    assert filters.status_code == 200
    assert "stato_conformita" in filters.get_json()["filters"]
    assert prefill.status_code == 200
    assert prefill.get_json()["prefill"]["fields"]
    for field_name in ("destinatario_ufficio_giudiziario", "cliente_mittente", "pratica_collegata", "autore"):
        assert field_name in prefill.get_json()["prefill"]["fields"]
    assert prefill.get_json()["prefill"]["fields"]["autore"]["value"] == "Avv. Test"
    assert prefill.get_json()["prefill"]["fields"]["autore"]["source"] == "studio"
    assert resolved.status_code == 200
    assert merged.status_code == 200
    assert "client_or_sender" in merged.get_json()["merge"]["preserved_user_inputs"]
    assert compliance.status_code == 200
    assert compliance.get_json()["cartabia"]["source_evidence_ids"]
    assert cartabia.status_code == 200
    assert "cartabia" in cartabia.get_json()
    assert complete.status_code == 200
    assert complete.get_json()["stato"] in {"verificato", "richiede_revisione"}
    assert timbro_get.status_code == 200
    assert timbro_preview.status_code == 200
    assert timbro_post.status_code == 200
    assert timbro_post.get_json()["preview"]["lines"][0]["align"] == "left"
