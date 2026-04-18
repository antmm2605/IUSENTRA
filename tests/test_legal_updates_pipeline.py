from __future__ import annotations

from pathlib import Path

from web.app import create_app

from pct.legal_update_pipeline import build_legal_update_pipeline


class DummyResponse:
    def __init__(self, html: str, *, status_code: int = 200, url: str = "https://example.test") -> None:
        self.text = html
        self.content = html.encode("utf-8")
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}


def _write_studio_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
        {
          "studio": {
            "nome": "Studio Update",
            "avvocato": "Avv. Update",
            "indirizzo": "Via Roma 20",
            "city": "Taurianova",
            "province": "RC",
            "telefono": "0966 654321",
            "email": "studio.update@example.it"
          },
          "pec": {
            "indirizzo": "studio.update@pec.example.it",
            "password": "segreta",
            "smtp_host": "smtp.pec.aruba.it",
            "smtp_port": 465,
            "imap_host": "imaps.pec.aruba.it",
            "imap_port": 993,
            "use_ssl": true
          },
          "smtp": {
            "host": "smtp.office365.com",
            "port": 587,
            "username": "studio.update@example.it",
            "from_address": "studio.update@example.it",
            "from_name": "Studio Update",
            "use_tls": true
          }
        }
        """,
        encoding="utf-8",
    )


def _cfg_web(tmp_path: Path) -> dict[str, str]:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(tmp_path / "auth" / "bootstrap_admin.json"),
        "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(tmp_path / "clienti" / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "SEARCH_INDEX": str(tmp_path / "search" / "index.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "soggetti" / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "import_pst"),
        "VALIDATION_RUNS_DB": str(tmp_path / "intelligence" / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(tmp_path / "intelligence" / "workspace_intelligence.json"),
        "TEMPLATE_ATTI_DB": str(tmp_path / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(tmp_path / "template_atti" / "editor_layout.json"),
        "PREVENTIVI_DB": str(tmp_path / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(tmp_path / "fatturazione" / "parcelle.json"),
        "TIMESHEET_DB": str(tmp_path / "timesheet" / "entries.json"),
        "LOCAL_AI_DB": str(tmp_path / "intelligence" / "local_ai.db"),
        "LOCAL_AI_POLICY": str(Path(__file__).resolve().parents[1] / "config" / "ai-policy.json"),
        "LOCAL_AI_MODELS_DIR": str(tmp_path / "intelligence" / "models"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "PORTALE_DB": str(tmp_path / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(tmp_path / "portale" / "uploads"),
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
    }


def _normativa_html() -> str:
    return """
    <html><body>
      <article>
        <a href="/atti/decreto-legge-38-2026">Decreto-legge 27 marzo 2026, n. 38 - Credito d'imposta per investimenti</a>
        <p>Pubblicato il 27/03/2026. Il decreto-legge n. 38/2026 aggiorna il regime applicativo del credito d'imposta e integra il quadro precedente.</p>
      </article>
    </body></html>
    """


def test_legal_update_cycle_crea_review_normativa(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    report = pipeline.run_cycle(
        source_codes=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
        auto_publish=False,
    )

    queue = pipeline.repository.list_review_queue(limit=20)

    assert report["ok"] is True
    assert queue
    assert queue[0]["classification_type"].startswith("NORMATIVA")
    assert queue[0]["proposed_action"] in {"NEW_NORMATIVE", "UPDATE_NORMATIVE"}


def test_legal_update_publish_crea_normativa_e_news(tmp_path: Path):
    pipeline = build_legal_update_pipeline(
        str(tmp_path / "intelligence" / "motori.json"),
        giurisprudenza_db_path=str(tmp_path / "intelligence" / "giurisprudenza.json"),
    )
    pipeline.run_cycle(
        source_codes=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
        auto_publish=False,
    )
    review = pipeline.repository.list_review_queue(limit=10)[0]

    pipeline.approve_review(int(review["id"]), reviewer="superadmin")
    result = pipeline.publish_review(int(review["id"]), reviewer="superadmin")
    snapshot = pipeline.dashboard_snapshot()

    assert result["normative"]["id"] >= 1
    assert result["news"]["id"] >= 1
    assert snapshot["headline"]["published_normative"] == 1
    assert snapshot["headline"]["published_news"] == 1


def test_legal_update_duplicate_non_moltiplica_queue(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    for _ in range(2):
        pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
            auto_publish=False,
        )

    queue = pipeline.repository.list_review_queue(limit=20)

    assert len(queue) == 1


def test_news_page_renderizza_contenuto_pubblicato(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
            auto_publish=False,
        )
        review = pipeline.repository.list_review_queue(limit=10)[0]
        pipeline.approve_review(int(review["id"]), reviewer="superadmin")
        pipeline.publish_review(int(review["id"]), reviewer="superadmin")

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302

        response = client.get("/legal-intelligence/news")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "News giuridiche strutturate" in html
    assert "Credito d&#39;imposta per investimenti" in html


def test_superadmin_vede_i_link_del_motore_in_sidebar_e_motori_legali(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302

        dashboard = client.get("/")
        motori = client.get("/legal-intelligence/")
        news = client.get("/legal-intelligence/news")

    dashboard_html = dashboard.get_data(as_text=True)
    motori_html = motori.get_data(as_text=True)
    news_html = news.get_data(as_text=True)

    assert dashboard.status_code == 200
    assert motori.status_code == 200
    assert news.status_code == 200
    assert "Update Intelligence" in dashboard_html
    assert "Apri console aggiornamenti" in motori_html
    assert "Console operativa aggiornamenti" in motori_html
    assert "Fonti ufficiali" in motori_html
    assert "Acquisizione" in motori_html
    assert "Analisi AI" in motori_html
    assert "Coda revisioni" in motori_html
    assert "Archivio strutturato" in motori_html
    assert "Ingressi rapidi del motore" in news_html
    assert "Fonti ufficiali" in news_html
    assert "Acquisizione" in news_html


def test_admin_surfaces_renderizzano_fonti_staging_analisi_e_archivio(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
            auto_publish=False,
        )
        review = pipeline.repository.list_review_queue(limit=10)[0]
        pipeline.approve_review(int(review["id"]), reviewer="superadmin")
        pipeline.publish_review(int(review["id"]), reviewer="superadmin")

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302

        routes = {
            "/admin/aggiornamenti-legali": "Motore di aggiornamento normativo e giurisprudenziale",
            "/admin/aggiornamenti-legali/fonti": "Gestore fonti",
            "/admin/aggiornamenti-legali/staging": "Area di acquisizione documenti",
            "/admin/aggiornamenti-legali/analisi": "Analisi AI",
            "/admin/aggiornamenti-legali/archivio": "Archivio strutturato",
        }

        for path, needle in routes.items():
            response = client.get(path)
            assert response.status_code == 200, path
            assert needle in response.get_data(as_text=True)


def test_admin_api_espone_staging_analisi_archivi_e_audit(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
            auto_publish=False,
        )
        review = pipeline.repository.list_review_queue(limit=10)[0]
        pipeline.approve_review(int(review["id"]), reviewer="superadmin")
        pipeline.publish_review(int(review["id"]), reviewer="superadmin")
        raw_id = int(pipeline.repository.list_raw_documents(limit=1)[0]["id"])
        analysis_id = int(pipeline.repository.list_analyses(limit=1)[0]["id"])
        normative_id = int(pipeline.repository.list_published_normative(limit=1)[0]["id"])

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302

        checks = [
            "/admin/aggiornamenti-legali/api/sources",
            "/admin/aggiornamenti-legali/api/raw-documents",
            f"/admin/aggiornamenti-legali/api/raw-documents/{raw_id}",
            f"/admin/aggiornamenti-legali/api/analysis/{analysis_id}",
            "/admin/aggiornamenti-legali/api/normative",
            f"/admin/aggiornamenti-legali/api/normative/{normative_id}/versions",
            "/admin/aggiornamenti-legali/api/news",
            "/admin/aggiornamenti-legali/api/audit",
        ]

        for path in checks:
            response = client.get(path)
            assert response.status_code == 200, path
            payload = response.get_json()
            assert payload["ok"] is True


def test_form_fetch_e_rianalisi_attivano_il_popolamento(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        calls: dict[str, list[int]] = {"fetch": [], "analyze": []}

        def _fake_runtime():
            return pipeline

        def _fake_fetch(source_id: int, *, auto_publish: bool = True):
            calls["fetch"].append(source_id)
            return {"documents_found": 1, "processed": 1, "autopublished": {"count": 0}}

        def _fake_analyze(raw_document_id: int):
            calls["analyze"].append(raw_document_id)
            return {"raw": {"id": raw_document_id}}

        pipeline.repository.upsert_sources(
            [
                {
                    "name": "Fonte test",
                    "code": "fonte_test",
                    "category": "news",
                    "base_url": "https://example.test",
                    "source_type": "web",
                    "trust_class": "C",
                    "is_official": False,
                    "enabled": True,
                    "polling_minutes": 120,
                    "parser_type": "html",
                    "notes": "",
                }
            ]
        )
        source_id = int(pipeline.repository.get_source_by_code("fonte_test")["id"])
        staging = pipeline.process_document(
            pipeline.repository.get_source_by_id(source_id),
            {
                "external_id": "test-1",
                "source_url": "https://example.test/doc",
                "title": "Documento test",
                "published_at": "2026-04-18",
                "raw_html": "",
                "raw_text": "Documento di test per rianalisi",
                "content_hash": "hash-test",
                "fetch_status": "fetched",
                "http_status": 200,
            },
        )
        raw_id = int(staging["raw"]["id"])

    monkeypatch.setattr("web.blueprints.legal_updates_admin.build_legal_update_pipeline_runtime", _fake_runtime)
    monkeypatch.setattr(pipeline, "fetch_source_by_id", _fake_fetch)
    monkeypatch.setattr(pipeline, "analyze_raw_document", _fake_analyze)

    with app.test_client() as client:
        login = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
        assert login.status_code == 302

        response_fetch = client.post(f"/admin/aggiornamenti-legali/fonti/{source_id}/fetch", data={"_csrf_token": "test"})
        response_analyze = client.post(f"/admin/aggiornamenti-legali/staging/{raw_id}/analizza", data={"_csrf_token": "test"})

    assert response_fetch.status_code == 302
    assert response_analyze.status_code == 302
    assert calls["fetch"] == [source_id]
    assert calls["analyze"] == [raw_id]
