from __future__ import annotations

from flask import Flask

from pct.legal_intelligence import GestioneLegalIntelligence
from web.services.assistente_studio_context import _ricerca_legale_lines


class DummyResponse:
    def __init__(self, content: bytes, status_code: int = 200, url: str = "https://example.test") -> None:
        self.content = content
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}


def _build_gestore(tmp_path) -> GestioneLegalIntelligence:
    return GestioneLegalIntelligence(
        str(tmp_path / "legal_intelligence.json"),
        normative_db_path=str(tmp_path / "tabelle_normative.json"),
    )


def test_legal_intelligence_repository_sync_and_export(tmp_path):
    gestore = _build_gestore(tmp_path)

    stats = gestore.statistiche_repository()
    assert stats["legal_sources_repository"] > 0
    assert stats["legal_engines_repository"] > 0
    assert stats["legal_keyword_to_engine"] > 0
    assert stats["legal_keyword_to_source"] > 0
    assert stats["legal_operational_repository"] > 0

    payload = gestore.repository_payload()
    assert payload["counts"]["sources"] == stats["legal_sources_repository"]
    assert any(row["source_id"] == "normattiva" for row in payload["sources"])
    assert any(row["engine_id"] == "giurisprudenza_orientamenti" for row in payload["engines"])
    assert any(row["keyword"] == "cassazione" for row in payload["keyword_to_source"])

    paths = gestore.export_legal_repositories(str(tmp_path / "export"))
    assert "sources" in paths
    assert "engines" in paths
    assert "keyword_to_engine" in paths
    assert "keyword_to_source" in paths
    assert "engine_source_edges" in paths
    assert "operational" in paths


def test_legal_intelligence_route_uses_repository_for_giurisprudenza_and_telematico(tmp_path):
    gestore = _build_gestore(tmp_path)

    giurisprudenza_route = gestore.resolve_lex_legal_route("ultime sentenze Cassazione civile")
    assert "giurisprudenza_orientamenti" in giurisprudenza_route["engine_ids"]
    assert "cassazione" in giurisprudenza_route["source_ids"]
    assert giurisprudenza_route["route_scope"] == "giurisprudenza"

    telematico_route = gestore.resolve_lex_legal_route("PST servizi web XSD SICI")
    assert "procedurale_telematico" in telematico_route["engine_ids"]
    assert any(source_id.startswith("pst_") for source_id in telematico_route["source_ids"])
    assert telematico_route["route_scope"] == "telematico"


def test_ricerca_legale_lines_uses_repository_and_monitoring(tmp_path):
    gestore = _build_gestore(tmp_path)
    gestore.monitor_source(
        "normattiva",
        request_get=lambda *args, **kwargs: DummyResponse(b"versione-1", url="https://www.normattiva.it/"),
    )

    app = Flask(__name__)
    app.config["LEGAL_INTELLIGENCE_DB"] = gestore.db_path
    app.config["NORMATIVE_TABLES_DB"] = gestore.normative_db_path
    app.config["FASCICOLI_DB"] = str(tmp_path / "fascicoli.json")
    app.config["FASCICOLI_DOCS"] = str(tmp_path / "docs")
    app.config["FASCICOLI_ARCH"] = str(tmp_path / "arch")
    app.config["CLIENTI_DB"] = str(tmp_path / "clienti.json")
    app.config["AGENDA_DB"] = str(tmp_path / "agenda.json")
    app.config["SCADENZIARIO_DB"] = str(tmp_path / "scadenze.json")
    app.config["PORTALE_DB"] = str(tmp_path / "portali.json")
    app.config["PORTALE_UPLOADS"] = str(tmp_path / "uploads")

    with app.app_context():
        lines, sources = _ricerca_legale_lines("normattiva aggiornata")

    assert any("Repository legale strutturato" in line for line in lines)
    assert any("Cockpit Motori Legali:" in line for line in lines)
    assert any("Routing deterministico:" in line for line in lines)
    assert any("Fonti ufficiali prioritarie:" in line for line in lines)
    assert any("Stato monitoraggio:" in line for line in lines)

    repository_source = next(row for row in sources if row.get("id") == "legal-intelligence:repository")
    assert repository_source["title"] == "Repository legale"

    dashboard_source = next(
        row for row in sources if row.get("id") == "legal-intelligence:dashboard-headline"
    )
    assert dashboard_source["title"] == "Dashboard Motori Legali"
    assert dashboard_source["headline"]["motori_attivi"] >= 1
    assert dashboard_source["headline"]["riferimenti_normativi"] >= 8

    normattiva_source = next(row for row in sources if row.get("id") == "fonte:normattiva")
    assert normattiva_source["official_url"] == "https://www.normattiva.it/"
    assert normattiva_source["status"] == "ok"
