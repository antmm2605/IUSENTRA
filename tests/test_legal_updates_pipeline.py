from __future__ import annotations

from pathlib import Path

from lex.contracts import LexRequest
from lex.retrieval.sources.legal_updates import LegalUpdatesSource
from web.app import create_app

from pct.auth import GestioneUtenti, RuoloUtente
from pct.legal_update_pipeline import build_legal_update_pipeline
from pct.tenant import GestioneTenant
from web.services.legal_update_surface import (
    build_legal_update_pipeline_runtime,
    build_legal_update_surface,
)


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


def _write_named_studio_config(path: Path, studio_name: str) -> None:
    _write_studio_config(path)
    payload = path.read_text(encoding="utf-8")
    path.write_text(payload.replace("Studio Update", studio_name), encoding="utf-8")


def _cfg_web(tmp_path: Path) -> dict[str, str]:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "BOOTSTRAP_ADMIN_PASSWORD": "Admin1234!",
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


def _seed_platform_superadmin(app) -> tuple[str, str]:
    password = "Admin1234!"
    with app.app_context():
        utenti = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            crea_admin_se_vuoto=False,
            bootstrap_admin_password=app.config.get("BOOTSTRAP_ADMIN_PASSWORD", ""),
            bootstrap_admin_credentials_path=app.config.get("BOOTSTRAP_ADMIN_CREDENTIALS_PATH", ""),
        )
        user = utenti.ensure_platform_superadmin()
        if user is None:
            utenti.crea(
                "admin",
                password,
                RuoloUtente.SUPERADMIN,
                tenant_slug="",
                must_change_password=False,
            )
    return "admin", password


def _normativa_html() -> str:
    return """
    <html><body>
      <article>
        <a href="/atti/decreto-legge-38-2026">Decreto-legge 27 marzo 2026, n. 38 - Credito d'imposta per investimenti</a>
        <p>Pubblicato il 27/03/2026. Il decreto-legge n. 38/2026 aggiorna il regime applicativo del credito d'imposta e integra il quadro precedente.</p>
      </article>
    </body></html>
    """


def _cassazione_page(page: int, total_pages: int = 4, items_per_page: int = 15) -> str:
    links = []
    start = (page - 1) * items_per_page + 1
    for number in range(start, start + items_per_page):
        links.append(
            f"""
            <article>
              <a href="/doc/{number}">Sentenza civile n. {number} del 2026 - Sezione prima</a>
              <p>Pubblicata il {number:02d}/04/2026 con massima e sintesi operativa.</p>
            </article>
            """
        )
    pager = "\n".join(
        f'<script>parametriUrl("pager_link_{page_no}", "{page_no}")</script>'
        for page_no in range(2, total_pages + 1)
    )
    return f"<html><body>{''.join(links)}{pager}</body></html>"


def _cassazione_page_with_navigation_noise(
    page: int,
    *,
    total_pages: int = 3,
    items_per_page: int = 20,
) -> str:
    nav_links = "".join(
        f'<a href="/nav/{idx}">Navigazione servizio {idx}</a>'
        for idx in range(1, 25)
    )
    cards = []
    start = (page - 1) * items_per_page + 1
    for number in range(start, start + items_per_page):
        cards.append(
            f"""
            <article>
              <a href="/doc/{number}">Sentenza civile n. {number} del 2026 - Prima Sezione</a>
              <p>Pubblicata il {((number - 1) % 28) + 1:02d}/04/2026 con abstract operativo.</p>
              <a href="/doc/{number}#full">Vai al documento {number}</a>
            </article>
            """
        )
    pager = "\n".join(
        f'<script>parametriUrl("pager_link_{page_no}", "{page_no}")</script>'
        for page_no in range(2, total_pages + 1)
    )
    return f"<html><body>{nav_links}{''.join(cards)}{pager}</body></html>"


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


def test_legal_update_autopubblica_senza_reinserire_contenuti_gia_presenti(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    first = pipeline.run_cycle(
        source_codes=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
        auto_publish=True,
    )
    second = pipeline.run_cycle(
        source_codes=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
        auto_publish=True,
    )
    snapshot = pipeline.dashboard_snapshot()
    queue = pipeline.repository.list_review_queue(limit=10)

    with pipeline.repository._connect() as conn:
        versions = int(conn.execute("SELECT COUNT(*) FROM normative_versions").fetchone()[0])

    assert first["autopublished"]["count"] == 1
    assert second["autopublished"]["count"] == 0
    assert snapshot["headline"]["published_normative"] == 1
    assert snapshot["headline"]["published_news"] == 1
    assert versions == 1
    assert queue[0]["proposed_action"] == "DUPLICATE"
    assert queue[0]["status"] == "closed"


def test_legal_update_giurisprudenza_gia_pubblicata_diventa_duplicate(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    pipeline.repository.upsert_sources(
        [
            {
                "name": "Cassazione Massimario Test",
                "code": "cassazione_massimario_test",
                "category": "giurisprudenza",
                "base_url": "https://www.cortedicassazione.it/",
                "source_type": "web",
                "trust_class": "A",
                "is_official": True,
                "enabled": True,
                "polling_minutes": 180,
                "parser_type": "html",
                "notes": "",
            }
        ]
    )
    source = pipeline.repository.get_source_by_code("cassazione_massimario_test")
    first = pipeline.process_document(
        source,
        {
            "external_id": "cass-9173-a",
            "source_url": "https://www.cortedicassazione.it/doc/9173",
            "title": "Sentenza civile n. 9173 del 2026 - Prima Sezione",
            "published_at": "2026-04-11",
            "raw_html": "",
            "raw_text": "Corte di Cassazione sentenza n. 9173/2026 in materia di responsabilita civile.",
            "content_hash": "hash-9173-a",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )
    pipeline.publish_review(int(first["review"]["id"]), reviewer="system")

    second = pipeline.process_document(
        source,
        {
            "external_id": "cass-9173-b",
            "source_url": "https://www.cortedicassazione.it/massimario/9173",
            "title": "Ordinanza della Cassazione n. 9173/2026",
            "published_at": "2026-04-12",
            "raw_html": "",
            "raw_text": "Cassazione ordinanza n. 9173 del 2026 sulla responsabilita civile.",
            "content_hash": "hash-9173-b",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )

    assert pipeline.dashboard_snapshot()["headline"]["published_jurisprudence"] == 1
    assert second["review"]["proposed_action"] == "DUPLICATE"
    assert second["review"]["status"] == "closed"


def test_legal_update_cleanup_accorpa_duplicati_archivio(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    with pipeline.repository._connect() as conn:
        conn.execute(
            """
            INSERT INTO jurisprudence (
                title, slug, court_name, decision_number, decision_year, decision_date,
                publication_date, summary, full_text, source_url, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "Sentenza Cassazione n. 9173/2026",
                "sentenza-cassazione-9173-2026",
                "Corte di Cassazione",
                "9173",
                "2026",
                "2026-04-11",
                "2026-04-11",
                "Sintesi A",
                "Testo A",
                "https://www.cortedicassazione.it/doc/9173",
            ),
        )
        conn.execute(
            """
            INSERT INTO jurisprudence (
                title, slug, court_name, decision_number, decision_year, decision_date,
                publication_date, summary, full_text, source_url, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "Ordinanza Cassazione 9173/2026",
                "ordinanza-cassazione-9173-2026",
                "Cassazione",
                "9173",
                "2026",
                "2026-04-11",
                "2026-04-12",
                "Sintesi B",
                "Testo B",
                "https://www.cortedicassazione.it/massimario/9173",
            ),
        )
        conn.commit()

    before = pipeline.repository.archive_duplicate_summary()
    cleanup = pipeline.repository.deduplicate_archive(performed_by="test")
    after = pipeline.repository.archive_duplicate_summary()

    assert before["duplicate_items"] == 1
    assert cleanup["removed"] == 1
    assert after["duplicate_items"] == 0
    assert pipeline.dashboard_snapshot()["headline"]["published_jurisprudence"] == 1


def test_legal_update_repository_espone_evidenze_lex_da_sql(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    normative = pipeline.repository.create_or_update_normative(
        {
            "title": "Decreto credito imposta investimenti 2026",
            "slug": "decreto-credito-imposta-investimenti-2026",
            "norm_type": "decreto-legge",
            "norm_number": "38",
            "norm_year": "2026",
            "issuer": "Gazzetta Ufficiale",
            "publication_date": "2026-03-27",
            "effective_date": "2026-03-28",
            "status": "vigente",
            "matter_slug": "diritto_tributario",
            "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00038/sg",
            "text_official": "Credito d'imposta per investimenti produttivi.",
            "text_current": "Credito d'imposta per investimenti produttivi.",
            "summary": "Aggiorna il regime del credito d'imposta.",
            "notes": "Rilevante per imprese e societa.",
        },
        performed_by="test",
    )
    pipeline.repository.create_or_update_news(
        {
            "title": "Credito d'imposta investimenti 2026",
            "short_summary": "Pubblicato aggiornamento sul credito d'imposta.",
            "content": "Il decreto aggiorna il quadro per gli investimenti produttivi.",
            "news_type": "normativa",
            "matter_slug": "diritto_tributario",
            "related_normative_id": normative["id"],
            "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00038/sg",
            "publication_status": "published",
            "published_at": "2026-03-27",
        },
        performed_by="test",
    )

    rows = pipeline.repository.search_lex_sources("credito imposta investimenti", limit=5)

    assert rows
    assert rows[0]["repository"] == "legal_updates_sql"
    assert rows[0]["db_path"].endswith("legal_updates.db")
    assert not rows[0]["db_path"].endswith(".json")
    assert any(row["type"] == "normativa" for row in rows)
    assert any("gazzettaufficiale.it" in row.get("official_url", "") for row in rows)


def test_legal_update_pipeline_non_scrive_export_json_di_default(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    pipeline.run_cycle(
        source_codes=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
        auto_publish=False,
    )

    assert not Path(pipeline.repository.json_path).exists()


def test_lex_legal_updates_source_legge_database_sql_condiviso(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.app_context():
        pipeline = build_legal_update_pipeline(app.config["LEGAL_INTELLIGENCE_DB"])
        pipeline.repository.create_or_update_news(
            {
                "title": "Privacy e data breach: aggiornamento Garante",
                "short_summary": "Aggiornamento operativo sulle comunicazioni di data breach.",
                "content": "La fonte istituzionale aggiorna il presidio privacy sui data breach.",
                "news_type": "privacy",
                "matter_slug": "privacy_protezione_dati",
                "source_url": "https://www.garanteprivacy.it/",
                "publication_status": "published",
                "published_at": "2026-05-03",
            },
            performed_by="test",
        )
        request = LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="aggiornamenti privacy data breach",
        )
        evidences = LegalUpdatesSource().search(["aggiornamenti privacy data breach"], request, {})

    assert evidences
    assert evidences[0].metadata["repository"] == "legal_updates_sql"
    assert evidences[0].source_type == "legal_updates"
    assert evidences[0].official_url == "https://www.garanteprivacy.it/"


def test_publish_review_supporta_needs_review_giurisprudenza_con_revisione_umana(tmp_path: Path, monkeypatch):
    legacy_mirror_path = tmp_path / "intelligence" / "giurisprudenza.json"
    pipeline = build_legal_update_pipeline(
        str(tmp_path / "intelligence" / "motori.json"),
        giurisprudenza_db_path=str(legacy_mirror_path),
    )
    pipeline.repository.upsert_sources(
        [
            {
                "name": "Cassazione - Prima Sezione Civile",
                "code": "cassazione_prima_sezione",
                "category": "giurisprudenza",
                "base_url": "https://www.cortedicassazione.it/it/prima_sezione_civile.page",
                "source_type": "web",
                "trust_class": "A",
                "is_official": True,
                "enabled": True,
                "polling_minutes": 180,
                "parser_type": "html",
                "notes": "",
            }
        ]
    )
    source = pipeline.repository.get_source_by_code("cassazione_prima_sezione")

    def _fake_analyze_document(document, source_row, *, ai_base_url="", ai_model=""):
        return {
            "classification_type": "GIURISPRUDENZA",
            "confidence_score": 0.67,
            "impact_level": "medio",
            "matter_slug": "diritto_civile",
            "submatter_slug": "",
            "issuer": "",
            "norm_number": "",
            "norm_year": "",
            "norm_type": "",
            "decision_number": "9173",
            "decision_year": "",
            "court_name": "",
            "effective_date": "",
            "summary_short": "Ordinanza interlocutoria sulla riscossione dei canoni.",
            "summary_long": "Sintesi estesa dell'ordinanza interlocutoria.",
            "what_changes": "Chiarisce il perimetro applicativo del canone richiesto da Anas.",
            "extracted_entities_json": {},
            "proposed_action": "NEEDS_REVIEW",
            "target_entity_type": "",
            "target_entity_id": None,
        }

    monkeypatch.setattr("pct.legal_update_pipeline.analyze_document", _fake_analyze_document)

    processed = pipeline.process_document(
        source,
        {
            "external_id": "cass-9173",
            "source_url": "https://www.cortedicassazione.it/doc/9173",
            "title": "Ordinanza interlocutoria n. 9173 del 11/04/2026",
            "published_at": "2026-04-11",
            "raw_html": "",
            "raw_text": "Ordinanza interlocutoria n. 9173 del 11/04/2026 Demanio: Accesso alla strada statale e canoni.",
            "content_hash": "hash-9173",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )

    review = pipeline.repository.get_review_item(int(processed["review"]["id"]))

    assert review is not None
    assert review["proposed_action"] == "NEEDS_REVIEW"
    assert review["status"] == "pending"

    result = pipeline.publish_review(int(review["id"]), reviewer="superadmin")
    published_review = pipeline.repository.get_review_item(int(review["id"]))

    assert result["jurisprudence"]["id"] >= 1
    assert result["news"]["id"] >= 1
    assert published_review is not None
    assert published_review["status"] == "published"
    assert not legacy_mirror_path.exists()
    assert pipeline.repository.search_lex_sources("canone anas", limit=3)


def test_fetch_html_paginato_acquisisce_tutti_i_documenti_della_fonte(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = {
        "id": 999,
        "code": "cassazione_prima_sezione_test",
        "name": "Cassazione - Prima sezione civile",
        "base_url": "https://www.cortedicassazione.it/it/prima_sezione_civile.page",
    }

    pages = {
        source["base_url"]: DummyResponse(_cassazione_page(1), url=source["base_url"]),
        f'{source["base_url"]}?frame3_item=2': DummyResponse(_cassazione_page(2), url=f'{source["base_url"]}?frame3_item=2'),
        f'{source["base_url"]}?frame3_item=3': DummyResponse(_cassazione_page(3), url=f'{source["base_url"]}?frame3_item=3'),
        f'{source["base_url"]}?frame3_item=4': DummyResponse(_cassazione_page(4), url=f'{source["base_url"]}?frame3_item=4'),
    }

    def _fake_get(url, *args, **kwargs):
        return pages[str(url)]

    documents = pipeline._fetch_source(source, request_get=_fake_get)

    assert len(documents) == 60
    assert len({row["external_id"] for row in documents}) == 60


def test_fetch_html_non_si_ferma_ai_primi_anchor_e_acquisisce_tutti_i_documenti(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = {
        "id": 1000,
        "code": "cassazione_prima_sezione_rumore",
        "name": "Cassazione - Prima sezione civile",
        "base_url": "https://www.cortedicassazione.it/it/prima_sezione_civile.page",
    }

    pages = {
        source["base_url"]: DummyResponse(_cassazione_page_with_navigation_noise(1), url=source["base_url"]),
        f'{source["base_url"]}?frame3_item=2': DummyResponse(
            _cassazione_page_with_navigation_noise(2),
            url=f'{source["base_url"]}?frame3_item=2',
        ),
        f'{source["base_url"]}?frame3_item=3': DummyResponse(
            _cassazione_page_with_navigation_noise(3),
            url=f'{source["base_url"]}?frame3_item=3',
        ),
    }

    def _fake_get(url, *args, **kwargs):
        return pages[str(url)]

    documents = pipeline._fetch_source(source, request_get=_fake_get)

    assert len(documents) == 60
    assert len({row["external_id"] for row in documents}) == 60


def test_news_page_storica_redirige_al_canonico_ricerca_legale(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    username, password = _seed_platform_superadmin(app)

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
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302

        response = client.get("/legal-intelligence/news?_legacy=1", follow_redirects=False)

        assert response.status_code == 301
        assert "/ricerca-legale/news" in response.headers["Location"]
        canonical = client.get(response.headers["Location"], follow_redirects=True)

    html = canonical.get_data(as_text=True)
    assert canonical.status_code == 200
    assert "IUSENTRA" in html


def test_superadmin_vede_i_link_del_motore_in_sidebar_e_motori_legali(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302

        dashboard = client.get("/")
        motori = client.get("/legal-intelligence/?_legacy=1", follow_redirects=False)
        news = client.get("/legal-intelligence/news?_legacy=1", follow_redirects=False)
        motori_canonico = client.get(motori.headers["Location"], follow_redirects=True)
        news_canonica = client.get(news.headers["Location"], follow_redirects=True)

    motori_html = motori_canonico.get_data(as_text=True)
    news_html = news_canonica.get_data(as_text=True)

    assert dashboard.status_code == 200
    assert motori.status_code == 301
    assert news.status_code == 301
    assert "/ricerca-legale" in motori.headers["Location"]
    assert "/ricerca-legale/news" in news.headers["Location"]
    assert motori_canonico.status_code == 200
    assert news_canonica.status_code == 200
    assert "IUSENTRA" in motori_html
    assert "IUSENTRA" in news_html
    assert "IUSENTRA" in dashboard.get_data(as_text=True)


def test_admin_surfaces_renderizzano_fonti_staging_analisi_e_archivio(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    username, password = _seed_platform_superadmin(app)

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
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
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


def test_pagina_fonti_mostra_guida_campi_ed_esempi_pronti(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302

        response = client.get("/admin/aggiornamenti-legali/fonti")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Come compilare correttamente una fonte" in html
    assert "devono riferirsi allo stesso ente" in html
    assert "cassazione_terza_sezione_civile" in html
    assert "https://www.cortecostituzionale.it/" in html
    assert "A primaria, B istituzionale, C editoriale" in html


def test_admin_api_espone_staging_analisi_archivi_e_audit(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    username, password = _seed_platform_superadmin(app)

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
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
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
    username, password = _seed_platform_superadmin(app)

    with app.app_context():
        pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        calls: dict[str, list[int]] = {"fetch": [], "analyze": []}

        def _fake_runtime(*args, **kwargs):
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
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302

        response_fetch = client.post(f"/admin/aggiornamenti-legali/fonti/{source_id}/fetch", data={"_csrf_token": "test"})
        response_analyze = client.post(f"/admin/aggiornamenti-legali/staging/{raw_id}/analizza", data={"_csrf_token": "test"})

    assert response_fetch.status_code == 302
    assert response_analyze.status_code == 302
    assert calls["fetch"] == [source_id]
    assert calls["analyze"] == [raw_id]


def test_update_intelligence_usa_archivio_condiviso_anche_con_studio_selezionato(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Legale Montagnese", "antonella-mammola", db_config={"mode": "SQLITE"})
    _write_named_studio_config(Path(tm.percorsi_dati(studio.slug)["CONFIG_STUDIO_DB"]), "Studio Legale Montagnese")
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.app_context():
        root_pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        root_pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *args, **kwargs: DummyResponse(
                _normativa_html(),
                url="https://www.gazzettaufficiale.it/",
            ),
            auto_publish=False,
        )

        payload = build_legal_update_surface(app, tenant_slug=studio.slug)
        tenant_pipeline = build_legal_update_pipeline_runtime(app, tenant_slug=studio.slug)

    assert payload["runtime"]["tenant_slug"] == ""
    assert payload["runtime"]["storage_scope"] == "shared_platform"
    assert payload["runtime"]["db_backend_label"] == "Archivio legale condiviso"
    assert tenant_pipeline.repository.db_path == root_pipeline.repository.db_path
    assert payload["headline"]["raw_documents"] >= 1
    assert Path(tenant_pipeline.repository.db_path).is_file()
    assert tenant_pipeline.repository.list_raw_documents(limit=5)


def test_dashboard_update_intelligence_mostra_presidio_condiviso_senza_selezione_studio(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Legale Montagnese", "antonella-mammola", db_config={"mode": "SQLITE"})
    _write_named_studio_config(Path(tm.percorsi_dati(studio.slug)["CONFIG_STUDIO_DB"]), "Studio Legale Montagnese")
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.app_context():
        root_pipeline = build_legal_update_pipeline(
            app.config["LEGAL_INTELLIGENCE_DB"],
            giurisprudenza_db_path=app.config["GIURISPRUDENZA_DB"],
        )
        root_pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *args, **kwargs: DummyResponse(
                _normativa_html(),
                url="https://www.gazzettaufficiale.it/",
            ),
            auto_publish=False,
        )

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302

        response = client.get(f"/admin/aggiornamenti-legali?tenant_slug={studio.slug}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Archivio legale condiviso da tutti gli studi" in html
    assert "confronta ogni contenuto" in html
    assert 'name="tenant_slug"' not in html
    assert "Studio attivo:" not in html


def test_dashboard_update_intelligence_ignora_nome_tenant_divergente_per_il_presidio_condiviso(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Antonella Mammola", "antonella-mammola", db_config={"mode": "SQLITE"})
    _write_named_studio_config(
        Path(tm.percorsi_dati(studio.slug)["CONFIG_STUDIO_DB"]),
        "Studio Legale Montagnese",
    )
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.app_context():
        payload = build_legal_update_surface(app, tenant_slug=studio.slug)

    assert payload["runtime"]["tenant_registry_name"] == ""
    assert payload["runtime"]["tenant_configured_name"] == ""
    assert payload["runtime"]["tenant_name_mismatch"] is False
    assert payload["runtime"]["tenant_name"] == ""
    assert payload["runtime"]["tenant_count"] == 1

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302

        response = client.get(f"/admin/aggiornamenti-legali?tenant_slug={studio.slug}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Archivio legale condiviso da tutti gli studi" in html
    assert "Studio attivo:" not in html
    assert "Configurazione interna studio" not in html
