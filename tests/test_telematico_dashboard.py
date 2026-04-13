import sqlite3
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.telematico_workflow import TelematicoWorkflowRepository
from web.app import create_app


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
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
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
    }


def _seed_pat_fascicolo(cfg: dict) -> str:
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="admin-telematico",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    clienti = GestioneClienti(db_path=cfg["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Alfa S.r.l.",
        partita_iva="12345678901",
        email="info@alfa.example",
    )

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        titolo="Ricorso amministrativo demo",
        tipo=TipoFascicolo.AMMINISTRATIVO,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="TAR Lazio",
        numero_rg="876",
        anno_rg=2026,
        sezione="I",
        giudice="Cons. Demo",
        oggetto="Appalto servizi",
        avvocato_referente="Avv. Demo",
        tipo_procedimento="RICORSO",
    )
    fascicoli.aggiorna(
        fascicolo.id,
        source="PAT",
        source_external_id="TAR-LAZIO:876:2026:RICORSO",
        last_sync_at="2026-04-12T11:58:00",
        sync_status="SINCRONIZZATO",
        document_sync_enabled=False,
    )
    fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PAT",
        id_deposito_esterno="PAT-DEP-001",
        tipo_atto="Ricorso",
        data_deposito="2026-04-10",
        mittente="Avv. Demo",
        documenti_portale=[
            {
                "id_documento": "PAT-DOC-001",
                "nome": "ricorso_introduttivo.pdf.p7m",
                "tipo": "RICORSO",
                "data_deposito": "2026-04-10",
                "mittente": "Avv. Demo",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "PAT-DEP-001",
                "tipo_atto": "Ricorso",
            }
        ],
        registrato_da="admin-telematico",
        stato="IMPORTATO_DA_PORTALE",
        servizio_portale="DocumentiFascicolo",
    )
    return fascicolo.id


def test_dashboard_telematico_renderizza_canali_e_backfill(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    fasc_id = _seed_pat_fascicolo(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-telematico", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get("/telematico", follow_redirects=True)
        html = page.get_data(as_text=True)

    assert page.status_code == 200
    assert "Cabina Telematica" in html
    assert "PST / PolisWeb" in html
    assert "PAT / SIGA" in html
    assert "Acquisizione guidata" in html

    repo = TelematicoWorkflowRepository(cfg["TELEMATICO_DB"])
    try:
        cases = repo.list_cases(practice_id=fasc_id)
        assert len(cases) == 1
        assert cases[0]["service_code"] == "pat_siga"
        assert cases[0]["documents_count"] == 1
    finally:
        repo.close()


def test_api_telematico_connection_status_restituisce_quattro_canali(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_pat_fascicolo(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-telematico", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        response = client.get("/api/telematico/connection-status")
        payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert len(payload["cards"]) == 4
    labels = {row["label"] for row in payload["cards"]}
    assert {"PST / PolisWeb", "PDP Penale", "PAT Amministrativo", "PTT Tributario"} <= labels


def test_api_portali_acquisizione_status_risponde_per_tutti_i_canali(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_pat_fascicolo(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-telematico", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        for portale in ("pst", "pdp", "pat", "ptt"):
            response = client.get(f"/api/portali/{portale}/acquisizione/status")
            payload = response.get_json()

            assert response.status_code == 200
            assert payload["ok"] is True
            assert payload["status"]["portale"] == portale
            assert payload["status"]["spec"]["id"] == portale


def test_dashboard_telematico_resta_disponibile_se_sqlite_segnala_spazio_pieno(tmp_path: Path, monkeypatch):
    cfg = _cfg_web(tmp_path)
    _seed_pat_fascicolo(cfg)
    app = create_app(cfg)

    def broken_case_stats(self):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(TelematicoWorkflowRepository, "case_stats", broken_case_stats)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-telematico", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get("/telematico", follow_redirects=True)
        html = page.get_data(as_text=True)

    assert page.status_code == 200
    assert "Cabina Telematica" in html
    assert "Archivio telematico temporaneamente non disponibile" in html


def test_dashboard_telematico_resta_disponibile_se_backfill_fallisce(tmp_path: Path, monkeypatch):
    cfg = _cfg_web(tmp_path)
    _seed_pat_fascicolo(cfg)
    app = create_app(cfg)

    def broken_upsert_case(self, **fields):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(TelematicoWorkflowRepository, "upsert_case", broken_upsert_case)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-telematico", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get("/telematico", follow_redirects=True)
        html = page.get_data(as_text=True)

    assert page.status_code == 200
    assert "Cabina Telematica" in html
    assert "Allineamento parziale" in html
