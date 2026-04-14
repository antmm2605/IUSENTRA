from __future__ import annotations

from flask import Flask

from pct.legal_intelligence import GestioneLegalIntelligence
from web.services.assistente_studio_context import _telematico_lines


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


def test_telematico_repository_sync_and_export(tmp_path):
    gestore = _build_gestore(tmp_path)

    stats = gestore.statistiche_telematico_repository()
    assert stats["telematico_methods_repository"] > 0
    assert stats["telematico_xsd_channels_repository"] > 0
    assert stats["telematico_sources_repository"] > 0
    assert stats["telematico_capabilities_repository"] > 0
    assert stats["telematico_actions_repository"] > 0

    payload = gestore.telematico_repository_payload()
    assert payload["counts"]["methods"] == stats["telematico_methods_repository"]
    assert payload["catalog_snapshot"]["catalog_version"]
    assert any(row["source_id"] == "pst_giustizia" for row in payload["sources"])
    assert any(row["action_id"] == "file_civil_deposit" for row in payload["actions"])

    paths = gestore.export_telematico_repositories(str(tmp_path / "export"))
    assert "repository" in paths
    assert "methods" in paths
    assert "xsd_channels" in paths
    assert "actions" in paths
    assert "monitoring" in paths


def test_telematico_route_distinguishes_import_validation_and_penale(tmp_path):
    gestore = _build_gestore(tmp_path)

    route_import = gestore.resolve_telematico_route("PolisWeb importa fascicolo PST")
    assert route_import["topic"] == "importazione"
    assert route_import["channel"] == "PolisWeb / PST"
    assert route_import["action"] == "import_pst_case"

    route_validation = gestore.resolve_telematico_route("errore T003 busta telematica")
    assert route_validation["topic"] == "validazione"
    assert any("T003" in (row.get("rule_text") or "") for row in route_validation["rule_rows"])

    route_penale = gestore.resolve_telematico_route("deposito penale PDP querela")
    assert route_penale["topic"] == "deposito_penale"
    assert route_penale["channel"] == "PDP"
    assert route_penale["action"] == "file_criminal_deposit"


def test_telematico_lines_use_repository_and_monitoring(tmp_path):
    gestore = _build_gestore(tmp_path)
    gestore.monitor_source(
        "pst_servizi_web",
        request_get=lambda *args, **kwargs: DummyResponse(
            b"<html><body>Documentazione servizi web esposti (versione 1.69)</body></html>",
            url="https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571",
        ),
    )

    app = Flask(__name__)
    app.config["LEGAL_INTELLIGENCE_DB"] = gestore.db_path
    app.config["NORMATIVE_TABLES_DB"] = gestore.normative_db_path

    with app.app_context():
        lines, sources = _telematico_lines("errore T003 su deposito PST")

    assert any("Repository telematico strutturato" in line for line in lines)
    assert any("Routing telematico:" in line for line in lines)
    assert any("Regole tecniche attive:" in line for line in lines)
    assert any(row.get("id") == "telematico:repository" for row in sources)
    assert any(str(row.get("id") or "").startswith("telematico-fonte:") for row in sources)
