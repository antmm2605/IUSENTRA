from __future__ import annotations

import json
from pathlib import Path

from lex.contracts import LexRequest
from lex.retrieval.sources.legal_updates import LegalUpdatesSource
from web.app import create_app

from pct.auth import GestioneUtenti, RuoloUtente
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS, build_legal_update_pipeline
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

    def iter_content(self, chunk_size: int = 65536):
        yield self.content


def test_fonti_default_includono_cartelle_openga_ufficiali():
    rows_by_code = {str(row["code"]): row for row in DEFAULT_SOURCE_ROWS}
    expected = {
        "openga_calendario_udienze",
        "openga_decreti",
        "openga_ordinanze",
        "openga_pareri",
        "openga_provvedimenti_pubblicati",
        "openga_ricorsi_definiti",
        "openga_ricorsi_pendenti",
        "openga_ricorsi_pervenuti",
        "openga_sentenze",
    }
    assert expected.issubset(rows_by_code)
    for code in expected:
        assert "package_search" in str(rows_by_code[code]["base_url"])
        assert "rows=200" in str(rows_by_code[code]["base_url"])


def test_fonti_default_includono_presidi_utili_per_studi_legali():
    codes = {str(row["code"]) for row in DEFAULT_SOURCE_ROWS}
    assert {
        "ministero_lavoro_interpelli",
        "garante_privacy",
        "anac_documenti",
        "inps_circolari",
        "inps_messaggi",
        "inps_sentenze",
        "curia_cgue_rss",
        "istat_prezzi",
        "mimit_incentivi",
        "agcm_bollettino",
        "agcom_provvedimenti",
        "banca_italia_normativa",
        "inail_istruzioni_operative",
        "pst_giustizia_download",
    }.issubset(codes)
    rows_by_code = {str(row["code"]): row for row in DEFAULT_SOURCE_ROWS}
    assert rows_by_code["inail_istruzioni_operative"]["enabled"] is False
    for code in ("inps_circolari", "inps_messaggi", "inps_sentenze", "curia_cgue_rss", "istat_prezzi"):
        assert rows_by_code[code]["parser_type"] == "feed"


def test_fonti_default_includono_codici_fondamentali_e_cassazione_verificata():
    rows_by_code = {str(row["code"]): row for row in DEFAULT_SOURCE_ROWS}
    expected = {
        "codice_civile",
        "codice_procedura_civile",
        "codice_penale",
        "codice_procedura_penale",
        "codice_processo_amministrativo",
        "codice_strada",
        "cassazione_citazioni_verificate",
    }

    assert expected.issubset(rows_by_code)
    for code in expected - {"cassazione_citazioni_verificate"}:
        row = rows_by_code[code]
        assert row["trust_class"] == "A"
        assert row["is_official"] is True
        assert "normattiva.it" in str(row["base_url"])
    assert "cortedicassazione.it" in str(rows_by_code["cassazione_citazioni_verificate"]["base_url"])


def test_fonti_default_includono_pagina_cassazione_ultime_sent_ord_e_questioni():
    rows_by_code = {str(row["code"]): row for row in DEFAULT_SOURCE_ROWS}
    row = rows_by_code["cassazione_ultime_sent_ord_questioni"]

    assert row["category"] == "giurisprudenza"
    assert row["base_url"] == "https://www.cortedicassazione.it/it/ultime_sent_ord_e_questioni.page"
    assert row["parser_type"] == "html"
    assert row["is_official"] is True
    assert row["enabled"] is True
    assert "allegati" in str(row["notes"]).lower()


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


def _seed_tenant_admin_for_updates(app) -> tuple[str, str, str]:
    username = "studio-update-admin"
    password = "PasswordSicura!123"
    with app.app_context():
        tenants = GestioneTenant(app.config["TENANTS_REGISTRY"])
        studio = tenants.get("studio-update") or tenants.crea(
            "Studio Update",
            "studio-update",
            db_config={"mode": "SQLITE"},
        )
        paths = tenants.percorsi_dati(studio.slug)
        utenti = GestioneUtenti(
            db_path=paths["AUTH_DB"],
            audit_path=paths["AUDIT_DB"],
            secret_key=app.secret_key,
            crea_admin_se_vuoto=False,
            studio_db=None,
        )
        if utenti.get_by_username(username) is None:
            utenti.crea(
                username,
                password,
                RuoloUtente.AMMINISTRATORE,
                tenant_slug=studio.slug,
                must_change_password=False,
            )
    return studio.slug, username, password


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


def test_legal_update_autopubblica_senza_reinserire_contenuti_gia_presenti(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": True,
            "reason": "Verifica pubblica completata con fonti coerenti.",
            "confirmation_count": 2,
            "official_confirmations": 1,
        },
    )

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
    assert second["reports"][0]["processed"] == 0
    assert second["reports"][0]["skipped_unchanged"] == 1
    assert snapshot["headline"]["published_normative"] == 1
    assert snapshot["headline"]["published_news"] == 1
    assert versions == 1
    assert len(queue) == 1
    assert queue[0]["status"] == "published"


def test_legal_update_autopubblica_attende_conferme_web(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": False,
            "reason": "Seconda conferma non trovata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
        },
    )

    report = pipeline.run_cycle(
        source_codes=["gazzetta_ufficiale"],
        request_get=lambda *args, **kwargs: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
        auto_publish=True,
    )
    queue = pipeline.repository.list_review_queue(limit=10)

    assert report["autopublished"]["count"] == 0
    assert queue[0]["status"] == "pending"
    assert "Verifica fonti insufficiente" in queue[0]["review_notes"]


def test_verifica_normativa_usa_archivi_locali_web_e_contesto(monkeypatch):
    from pct import legal_update_web_verification as verification

    review = {
        "proposed_action": "NEW_NORMATIVE",
        "title": "Decreto legislativo n. 55 del 2026 sulla mediazione obbligatoria",
        "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/05/10/26G00055/sg",
        "source_name": "Gazzetta Ufficiale",
        "classification_type": "NORMATIVA_NUOVA",
        "norm_type": "decreto legislativo",
        "norm_number": "55",
        "norm_year": "2026",
        "summary_short": "La norma aggiorna il quadro della mediazione obbligatoria.",
        "body_text": "Decreto legislativo n. 55 del 2026 sulla mediazione obbligatoria e il processo civile.",
    }
    source = {"name": "Gazzetta Ufficiale", "code": "gazzetta_ufficiale", "category": "normativa", "trust_class": "A", "is_official": True}

    monkeypatch.setattr(
        "lex.retrieval.official_sources_retriever.search_official_sources",
        lambda query, limit=5: [],
    )
    monkeypatch.setattr(
        "lex.retrieval.official_sources_retriever.search_normattiva",
        lambda query, limit=5: [
            {
                "titolo": "Decreto legislativo n. 55 del 2026 sulla mediazione obbligatoria",
                "testo": "Testo Normattiva: decreto legislativo n. 55 del 2026, mediazione obbligatoria e processo civile.",
                "url_origine": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2026;55",
                "fonte": "Normattiva",
            }
        ] if "55" in query or "mediazione" in query.lower() else [],
    )
    monkeypatch.setattr(
        "lex.retrieval.official_sources_retriever.search_gazzetta",
        lambda query, limit=5: [],
    )
    monkeypatch.setattr(
        "lex.retrieval.official_web.search_recognized_official_web",
        lambda query, source_ids=None, limit_results=5: [
            {
                "title": "Decreto legislativo n. 55 del 2026",
                "url": "https://www.gazzettaufficiale.it/eli/id/2026/05/10/26G00055/sg",
                "source_name": "Gazzetta Ufficiale",
                "excerpt": "",
            }
        ],
    )
    monkeypatch.setattr(
        verification.requests,
        "get",
        lambda *args, **kwargs: DummyResponse(
            "<html><body>Gazzetta Ufficiale decreto legislativo n. 55 del 2026 "
            "mediazione obbligatoria processo civile testo completo della fonte.</body></html>",
            url="https://www.gazzettaufficiale.it/eli/id/2026/05/10/26G00055/sg",
        ),
    )

    report = verification.verify_legal_update_against_public_sources(review, source, limit=3)

    assert report["ok"] is True
    assert report["confirmation_count"] >= 2
    assert report["searched"]["web_results"] >= 1
    assert len(report["searched"]["queries"]) >= 3
    assert any(row["origin"] == "archivio_normattiva" for row in report["confirmations"])
    assert any(row["origin"] == "ricerca_web_governata" and row["context_chars"] > 80 for row in report["confirmations"])


def test_verifica_web_legge_allegati_della_fonte_ufficiale(monkeypatch):
    from pct import legal_update_web_verification as verification

    review = {
        "proposed_action": "NEW_NORMATIVE",
        "title": "Decreto legislativo n. 56 del 2026 sulla conciliazione",
        "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/05/11/26G00056/sg",
        "source_name": "Gazzetta Ufficiale",
        "classification_type": "NORMATIVA_NUOVA",
        "norm_type": "decreto legislativo",
        "norm_number": "56",
        "norm_year": "2026",
        "summary_short": "Aggiorna la conciliazione giudiziale.",
    }
    source = {"name": "Gazzetta Ufficiale", "code": "gazzetta_ufficiale", "category": "normativa", "trust_class": "A", "is_official": True}

    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_official_sources", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_normattiva", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_gazzetta", lambda query, limit=5: [])
    monkeypatch.setattr(
        "lex.retrieval.official_web.search_recognized_official_web",
        lambda query, source_ids=None, limit_results=5: [
            {
                "title": "Scheda Gazzetta con allegato",
                "url": "https://www.gazzettaufficiale.it/scheda/26G00056",
                "source_name": "Gazzetta Ufficiale",
                "excerpt": "Scheda senza testo completo.",
            }
        ],
    )

    class _Response(DummyResponse):
        def __init__(self, body: str, *, content_type: str, url: str):
            super().__init__(body, url=url)
            self.headers = {"content-type": content_type, "content-length": str(len(self.content))}

    def _get(url, **kwargs):
        if str(url).endswith("testo.xml"):
            return _Response(
                "<atto><titolo>Decreto legislativo n. 56 del 2026 sulla conciliazione</titolo>"
                "<testo>conciliazione giudiziale e processo civile</testo></atto>",
                content_type="application/xml",
                url=str(url),
            )
        return _Response(
            '<html><body>Scheda ufficiale <a href="/allegati/testo.xml">Scarica testo XML</a></body></html>',
            content_type="text/html; charset=utf-8",
            url=str(url),
        )

    monkeypatch.setattr(verification.requests, "get", _get)

    report = verification.verify_legal_update_against_public_sources(review, source, limit=2)

    web_confirmations = [row for row in report["confirmations"] if row["origin"] == "ricerca_web_governata"]
    assert web_confirmations
    assert "conciliazione giudiziale" in web_confirmations[0]["excerpt"]
    assert web_confirmations[0]["context_chars"] > 80


def test_open_data_cataloghi_vengono_archiviati_senza_review_manuale(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("openga_giustizia_amministrativa")

    processed = pipeline.process_document(
        source,
        {
            "external_id": "openga-stat-2026",
            "source_url": "https://openga.giustizia-amministrativa.it/dataset/ricorsi-definiti",
            "title": "TAR Molise - Ricorsi definiti per tipo di decisione - 2026",
            "published_at": "2026-05-01",
            "raw_html": "",
            "raw_text": "Dataset statistico OpenGA con conteggi dei ricorsi definiti per tipo di decisione.",
            "content_hash": "hash-openga-stat-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )
    review = pipeline.repository.get_review_item(int(processed["review"]["id"]))

    assert review is not None
    assert review["proposed_action"] == "OUT_OF_SCOPE"
    assert review["status"] == "closed"


def test_atti_amministrativi_di_sola_liquidazione_non_diventano_news_legali(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("ministero_lavoro")
    assert source is not None

    monkeypatch.setattr(
        "pct.legal_update_pipeline.analyze_document",
        lambda *args, **kwargs: {
            "classification_type": "COMMENTO",
            "confidence_score": 0.94,
            "impact_level": "basso",
            "summary_short": "Atto amministrativo di liquidazione fattura.",
            "summary_long": "Atto amministrativo di liquidazione fattura per servizio già svolto.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )

    processed = pipeline.process_document(
        source,
        {
            "external_id": "calabria-atto-6258-2026",
            "source_url": "https://www.regione.calabria.it/wp-content/uploads/2026/04/Atto_Numero_6258_del_16-04-2026.pdf",
            "title": "Atto Numero 6258 del 16-04-2026 - liquidazione fattura",
            "published_at": "2026-04-16",
            "raw_html": "",
            "raw_text": (
                "Liquidazione fattura per servizio di collegamento, importo euro 45,20. "
                "Verifica DURC e pagamento al fornitore."
            ),
            "content_hash": "hash-calabria-6258-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )
    review = pipeline.repository.get_review_item(int(processed["review"]["id"]))

    assert review is not None
    assert review["proposed_action"] == "OUT_OF_SCOPE"
    assert review["status"] == "closed"


def test_autopublish_risolve_needs_review_ufficiale_in_notizia(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": True,
            "reason": "Fonte ufficiale confermata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
        },
    )

    source = pipeline.repository.get_source_by_code("cassazione_massimario")
    processed = pipeline.process_document(
        source,
        {
            "external_id": "cassazione-news-2026",
            "source_url": "https://www.cortedicassazione.it/doc/news-2026",
            "title": "Aggiornamento della Corte di Cassazione sul massimario civile",
            "published_at": "2026-05-01",
            "raw_html": "",
            "raw_text": "Nota ufficiale sul massimario civile senza numero di sentenza specifico.",
            "content_hash": "hash-cassazione-news-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )
    review_id = int(processed["review"]["id"])
    pipeline.repository.set_review_proposed_action(review_id, "NEEDS_REVIEW", reviewer="test")
    pipeline.repository.set_review_status(review_id, "pending", reviewer="test")

    report = pipeline.publish_auto_news(limit=10)
    review = pipeline.repository.get_review_item(review_id)

    assert report["reconciled"]["resolved_actions"] >= 1
    assert report["count"] == 1
    assert review is not None
    assert review["proposed_action"] == "NEWS_ONLY"
    assert review["status"] == "published"
    assert pipeline.repository.list_news(limit=5, include_drafts=False)


def test_normative_slug_duplicate_non_blocca_pubblicazione(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    first = pipeline.repository.create_or_update_normative(
        {
            "title": "Aggiornamento normativo",
            "slug": "Aggiornamento normativo",
            "norm_type": "",
            "norm_number": "",
            "norm_year": "",
            "issuer": "Fonte ufficiale",
            "publication_date": "2026-05-01",
            "source_url": "https://example.test/a",
            "text_official": "Primo testo.",
            "summary": "Primo aggiornamento.",
        },
        performed_by="test",
    )
    second = pipeline.repository.create_or_update_normative(
        {
            "title": "Aggiornamento normativo",
            "slug": "Aggiornamento normativo",
            "norm_type": "",
            "norm_number": "",
            "norm_year": "",
            "issuer": "Fonte ufficiale",
            "publication_date": "2026-05-02",
            "source_url": "https://example.test/b",
            "text_official": "Secondo testo.",
            "summary": "Secondo aggiornamento.",
        },
        performed_by="test",
    )

    with pipeline.repository._connect() as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM normative").fetchone()[0])

    assert first["slug"] == "aggiornamento-normativo"
    assert second["slug"] == "aggiornamento-normativo"
    assert count == 1


def test_openga_ckan_importa_risorse_json_per_lex(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("openga_calendario_udienze")
    assert source is not None

    ckan_payload = {
        "success": True,
        "result": {
            "packages": [
                {
                    "id": "pkg-cal-1",
                    "title": "Calendario udienze TAR Calabria",
                    "notes": "Dataset ufficiale OpenGA con calendario udienze.",
                    "metadata_modified": "2026-05-10T10:00:00",
                    "resources": [
                        {
                            "id": "res-json-1",
                            "name": "calendario-udienze.json",
                            "format": "JSON",
                            "url": "https://openga.giustizia-amministrativa.it/dataset/calendario-udienze.json",
                        }
                    ],
                }
            ]
        },
    }
    resource_payload = {"udienze": [{"sede": "TAR Calabria", "data": "2026-06-01"}]}

    def fake_get(url, **kwargs):
        if url.endswith(".json"):
            return DummyResponse(json.dumps(resource_payload), url=url)
        return DummyResponse(json.dumps(ckan_payload), url=url)

    docs = pipeline._fetch_source(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["resource_format"] == "JSON"
    assert "Contenuto JSON acquisito" in docs[0]["raw_text"]
    assert "TAR Calabria" in docs[0]["raw_text"]


def test_feed_xml_con_content_type_generico_importa_fonti_ufficiali(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("curia_cgue_rss")
    assert source is not None
    response = DummyResponse(
        """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
          <item>
            <title>Sentenza della Corte nella causa C-10/26</title>
            <link>https://curia.europa.eu/juris/document/document.jsf?text=&amp;docid=123</link>
            <pubDate>Fri, 15 May 2026 10:00:00 GMT</pubDate>
            <description>Decisione ufficiale della Corte di giustizia.</description>
          </item>
        </channel></rss>""",
        url="https://curia.europa.eu/site/rss.jsp?lang=it&secondLang=en",
    )
    response.headers = {"content-type": "text/html;charset=UTF-8"}

    docs = pipeline._fetch_source(source, request_get=lambda *args, **kwargs: response)

    assert len(docs) == 1
    assert docs[0]["title"] == "Sentenza della Corte nella causa C-10/26"
    assert docs[0]["published_at"] == "2026-05-15"


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


def test_publish_review_risolve_giurisprudenza_informativa_senza_revisione_obbligatoria(tmp_path: Path, monkeypatch):
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
    assert review["proposed_action"] == "NEWS_ONLY"
    assert review["status"] == "approved"

    result = pipeline.publish_review(int(review["id"]), reviewer="superadmin")
    published_review = pipeline.repository.get_review_item(int(review["id"]))

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
            "/admin/aggiornamenti-legali/analisi": "Analisi automatica",
            "/admin/aggiornamenti-legali/archivio": "Archivio strutturato",
        }

        for path, needle in routes.items():
            response = client.get(path)
            assert response.status_code == 200, path
            assert needle in response.get_data(as_text=True)

        dashboard_html = client.get("/admin/aggiornamenti-legali").get_data(as_text=True)
        assert "Dove finiscono i dati" in dashboard_html
        assert "Documenti letti" in dashboard_html
        assert "Schede pubblicate" in dashboard_html
        assert "Indice Normattiva" in dashboard_html
        assert "Indice Gazzetta" in dashboard_html
        assert 'href="/ricerca-legale' in dashboard_html


def test_admin_review_mostra_etichette_operative_senza_codici_grezzi(tmp_path: Path):
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

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302
        response = client.get("/admin/aggiornamenti-legali/review")
        staging_response = client.get("/admin/aggiornamenti-legali/staging")

    html = response.get_data(as_text=True)
    staging_html = staging_response.get_data(as_text=True)
    assert response.status_code == 200
    assert staging_response.status_code == 200
    assert "Nuova normativa" in html or "Aggiornamento normativo" in html
    assert "In verifica" in html or "Pronta alla pubblicazione" in html
    assert "NEW_NORMATIVE" not in html
    assert "UPDATE_NORMATIVE" not in html
    assert "NORMATIVA_AGGIORNAMENTO" not in html
    assert ">pending<" not in html
    assert "Da valutare" not in html
    assert "Da valutare" not in staging_html
    assert "Classificato" in staging_html or "Verifica fonti" in staging_html or "Pronto alla pubblicazione" in staging_html


def test_admin_studio_accede_review_aggiornamenti_legali_senza_403(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio_slug, username, password = _seed_tenant_admin_for_updates(app)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": username, "password": password, "studio_slug": studio_slug},
            follow_redirects=False,
        )
        assert login.status_code == 302
        response = client.get("/admin/aggiornamenti-legali/review")

    assert response.status_code == 200
    assert "Coda revisioni aggiornamenti" in response.get_data(as_text=True)


def test_pagina_fonti_mostra_catalogo_professionale_e_ciclo_giornaliero(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        assert login.status_code == 302

        response = client.get("/admin/aggiornamenti-legali/fonti")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Catalogo professionale delle fonti pubbliche" in html
    assert "Ciclo giornaliero" in html
    assert "23:00" in html
    assert "solo elementi nuovi o cambiati" in html
    assert "OpenGA - Sentenze" in html
    assert "INPS - circolari" in html
    assert "Curia - Corte di giustizia UE" in html
    assert "INAIL - istruzioni operative" in html
    assert "In osservazione" in html
    assert "Aggiunte IUSENTRA" in html
    assert "Agente" in html
    assert "Esegui agente" in html


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

        def _fake_analyze(raw_document_id: int, *, auto_publish: bool = True):
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
    assert "cabina tecnica del ciclo fonti" in html
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
