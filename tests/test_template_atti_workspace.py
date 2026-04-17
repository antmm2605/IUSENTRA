import tempfile
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.compilatore_atti import MODEL_INDEX
from pct.template_atti import GestioneTemplateAtti
from web.app import create_app


def _cfg_web(tmp_path):
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
    }


def _login_client(client):
    client.post(
        "/login",
        data={"username": "avvocato", "password": "Avv12345!"},
        follow_redirects=True,
    )


def _bootstrap_app(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    return cfg, create_app(cfg)


def test_catalogo_builtin_supera_cento_modelli_e_contiene_atti_richiesti(tmp_path):
    cfg, _ = _bootstrap_app(tmp_path)
    gt = GestioneTemplateAtti(db_path=cfg["TEMPLATE_ATTI_DB"])
    builtins = [t for t in gt.tutti() if t.builtin]
    compiler_codes = {code for code in MODEL_INDEX}
    covered_codes = {t.link_compilatore_code for t in builtins if t.link_compilatore_code}
    collections = {t.collezione for t in builtins if t.collezione}

    assert len(builtins) >= len(compiler_codes)
    assert all(t.link_compilatore_code for t in builtins)
    assert all(t.link_compilatore_code in MODEL_INDEX for t in builtins)
    assert covered_codes == compiler_codes
    assert "Societario" in collections
    assert "Immigrazione e cittadinanza" in collections

    by_title = {t.titolo: t for t in builtins}
    assert "Procura speciale per ricorso monitorio" in by_title
    assert "Nomina domiciliatario" in by_title
    assert "Atto di citazione" in by_title
    assert "Ricorso per separazione giudiziale" in by_title
    assert "Ricorso lavoro" in by_title
    assert "Reclamo" in by_title
    assert "Ricorso ex legge Pinto" in by_title
    assert "Diffida stragiudiziale collegata al fascicolo" in by_title
    assert "Nomina del difensore di fiducia" in by_title
    assert "Parere Societario" in by_title
    assert "Ricorso Protezione Internazionale" in by_title
    assert by_title["Atto di citazione"].link_compilatore_code == "CIV_CIT_001"
    assert by_title["Atto di citazione"].campi_guidati
    assert by_title["Atto di citazione"].branca == "Civile ordinario"


def test_workspace_template_atti_renderizza_filtri_e_card_principali(tmp_path):
    _, app = _bootstrap_app(tmp_path)
    with app.test_client() as client:
        _login_client(client)
        response = client.get("/template-atti/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Workspace atti e modelli" in html
    assert "Catalogo built-in con generazione reale" in html
    assert "Solo modelli con compilatore" in html
    assert "Atto di citazione" in html
    assert "Ricorso per decreto ingiuntivo" in html
    assert "Nomina del difensore di fiducia" in html
    assert "Societario" in html
    assert "Immigrazione e cittadinanza" in html
    assert "Parere Societario" in html
    assert "Ricorso Protezione Internazionale" in html


def test_scheda_modello_builtin_espone_metadati_e_campi_guidati(tmp_path):
    cfg, app = _bootstrap_app(tmp_path)
    gt = GestioneTemplateAtti(db_path=cfg["TEMPLATE_ATTI_DB"])
    modello = next(t for t in gt.tutti() if t.titolo == "Atto di precetto")

    with app.test_client() as client:
        _login_client(client)
        response = client.get(f"/template-atti/scheda/{modello.id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Scheda modello" in html
    assert "Metadati operativi" in html
    assert "Titolo esecutivo" in html
    assert "Atto di precetto" in html
    assert "CIV_PREC_001" in html or "TMP-ESE-001" in html


def test_generazione_builtin_con_campi_guidati_restituisce_anteprima(tmp_path):
    cfg, app = _bootstrap_app(tmp_path)
    gt = GestioneTemplateAtti(db_path=cfg["TEMPLATE_ATTI_DB"])
    modello = next(t for t in gt.tutti() if t.titolo == "Atto di citazione")

    with app.test_client() as client:
        _login_client(client)
        response = client.post(
            f"/template-atti/{modello.id}/usa",
            data={
                "autorita_competente": "Tribunale di Milano",
                "oggetto_atto": "Risarcimento danni da inadempimento",
                "controparte_nome": "Beta S.r.l.",
                "fatti_rilevanti": "In data 12/04/2026 la controparte non ha adempiuto.",
                "motivi_in_diritto": "Violazione degli articoli 1218 e 1453 c.c.",
                "domande_conclusioni": "Accertare l'inadempimento e condannare al risarcimento.",
            },
            follow_redirects=True,
        )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Anteprima" in html
    assert "Risarcimento danni da inadempimento" in html
    assert "Beta S.r.l." in html
    assert "Violazione degli articoli 1218 e 1453 c.c." in html


def test_compilatore_alias_builtin_apre_wizard_specifico(tmp_path):
    _, app = _bootstrap_app(tmp_path)
    with app.test_client() as client:
        _login_client(client)
        response_procura = client.get("/template-atti/compila/CIV_PROC_001")
        response_querela = client.get("/template-atti/compila/PEN_BLT_001")

    assert response_procura.status_code == 200
    assert response_querela.status_code == 200
    html_procura = response_procura.get_data(as_text=True)
    html_querela = response_querela.get_data(as_text=True)
    assert "Procura alle liti" in html_procura
    assert "Querela" in html_querela
