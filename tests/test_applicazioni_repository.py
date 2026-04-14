from __future__ import annotations

from flask import Flask

from pct.applicazioni_repository import (
    GestioneApplicazioniRepository,
    derive_applicazioni_access_json_path,
    derive_applicazioni_catalog_json_path,
    derive_applicazioni_featured_json_path,
    derive_applicazioni_repository_json_path,
    derive_applicazioni_section_kinds_json_path,
    derive_applicazioni_sections_json_path,
    derive_applicazioni_statistics_json_path,
    derive_applicazioni_status_json_path,
)
from web.services.assistente_studio_context import _applicazioni_lines


def _build_repository(tmp_path) -> GestioneApplicazioniRepository:
    db_path = str(tmp_path / "applicazioni_repository.db")
    repository = GestioneApplicazioniRepository(
        db_path,
        json_path=derive_applicazioni_repository_json_path(db_path),
        sections_json_path=derive_applicazioni_sections_json_path(db_path),
        catalog_json_path=derive_applicazioni_catalog_json_path(db_path),
        statuses_json_path=derive_applicazioni_status_json_path(db_path),
        access_json_path=derive_applicazioni_access_json_path(db_path),
        section_kinds_json_path=derive_applicazioni_section_kinds_json_path(db_path),
        featured_json_path=derive_applicazioni_featured_json_path(db_path),
        statistics_json_path=derive_applicazioni_statistics_json_path(db_path),
    )
    repository.synchronize_runtime(export_json=True)
    return repository


def test_applicazioni_repository_sync_and_export(tmp_path):
    repository = _build_repository(tmp_path)

    stats = repository.storage_stats()
    assert stats["applicazioni_catalog_repository"] > 0
    assert stats["applicazioni_sections_repository"] > 0
    assert stats["applicazioni_status_repository"] > 0
    assert stats["applicazioni_access_repository"] > 0
    assert stats["applicazioni_featured_repository"] > 0

    payload = repository.load_repository_payload()
    assert payload["counts"]["catalog"] == stats["applicazioni_catalog_repository"]
    assert any(row["app_id"] == "calcolo_preventivo" for row in payload["catalog"])
    assert any(row["section_id"] == "atti_giudiziari" for row in payload["sections"])

    paths = repository.export_split_jsons(str(tmp_path / "export"))
    assert "repository" in paths
    assert "catalog" in paths
    assert "sections" in paths
    assert "featured" in paths
    assert "statistics" in paths


def test_applicazioni_repository_route_selects_best_workspace(tmp_path):
    repository = _build_repository(tmp_path)

    route = repository.resolve_workspace_for_request("voglio fare un calcolo preventivo")

    assert route["route_scope"] == "workspace_registry"
    assert route["best_app"] is not None
    assert route["best_app"]["app_id"] == "calcolo_preventivo"
    assert route["direct_endpoint"] == "preventivi.wizard"
    assert route["requires_guided_flow"] is False
    assert route["related_apps"]


def test_applicazioni_lines_use_workspace_registry(tmp_path):
    app = Flask(__name__)
    app.config["STUDIO_CONFIG"] = str(tmp_path / "config" / "studio.json")

    with app.app_context():
        lines, sources = _applicazioni_lines("aprimi la fatturazione")

    assert any("Workspace registry applicazioni" in line for line in lines)
    assert any("Routing workspace:" in line for line in lines)
    assert any("Modulo consigliato:" in line for line in lines)
    assert any(row.get("id") == "applicazioni:repository" for row in sources)
    assert any(str(row.get("id") or "").startswith("applicazione:") for row in sources)
