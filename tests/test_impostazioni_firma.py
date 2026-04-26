from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.config_studio import ConfigFirma, GestioneConfigStudio
from web.app import create_app


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "MULTI_TENANT": False,
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
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
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
    }


def _crea_avvocato(cfg: dict) -> None:
    utenti = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    utenti.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )


def test_config_firma_pkcs11_locale_resta_canale_operativo():
    cfg = ConfigFirma(backend_preferito="pkcs11")

    assert cfg.backend_firma_effettivo_safe == "nessuno"
    assert cfg.pkcs11_canale_locale is True
    assert cfg.backend_firma_operativo_safe == "pkcs11"


def test_impostazioni_firma_pkcs11_non_mostra_falso_errore_server(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    studio_cfg = Path(cfg["STUDIO_CONFIG"])
    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "MNTRRT64L01063H"
    gs.aggiorna(studio)
    _crea_avvocato(cfg)

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/impostazioni?tab=firma", follow_redirects=True)

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "PKCS#11 selezionato ma libreria/token non disponibili." not in html
    assert "Configurazione guidata" in html
    assert "La verifica reale di libreria, token e certificato avviene tramite Local Signer sul PC locale" in html
    assert 'name="firma_visible_signature_mode"' in html
    assert "In basso a sinistra" in html


def test_impostazioni_firma_salva_posizione_firma_visibile(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _crea_avvocato(cfg)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/impostazioni",
            data={
                "_tab": "firma",
                "firma_formato": "pkcs11",
                "firma_cf_avvocato": "MNTRRT64L01063H",
                "firma_visible_signature_mode": "basso_sinistra",
            },
            follow_redirects=True,
        )

    assert response.status_code == 200
    salvata = GestioneConfigStudio(cfg["STUDIO_CONFIG"]).config
    assert salvata.firma.visible_signature_mode == "basso_sinistra"


def test_script_impostazioni_firma_verifica_local_signer_sul_pc_locale():
    root = Path(__file__).resolve().parents[1]
    script = (root / "web/static/js/impostazioni-firma.js").read_text(encoding="utf-8")

    assert "const LOCAL_SIGNER_BASE = 'http://127.0.0.1:27272';" in script
    assert "LOCAL_SIGNER_BASE + '/ping'" in script
    assert "/api/firma/pkcs11/status" not in script
