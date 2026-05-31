from __future__ import annotations

from pathlib import Path

from pct import __version__
from pct.installation_pack_repository import InstallationPackRepository
from pct.installation_packs import (
    SYSTEM_SERVICE_DEFINITIONS,
    bootstrap_pack_governance,
    ensure_installation_identity,
    ensure_studio_local_pack,
    resolve_system_pack_root,
)
from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.installation_pack_surface import (
    _runtime_dependency_cards,
    _service_runtime_cards,
    build_installation_pack_surface,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_manifest_servizi_usa_nome_iusentra():
    service_ids = [service["service_id"] for service in SYSTEM_SERVICE_DEFINITIONS]

    assert service_ids == [
        "iusentra-web",
        "iusentra-lex",
        "iusentra-embed",
        "iusentra-jobs",
        "iusentra-telematico",
        "iusentra-updater",
    ]
    assert all(not service_id.startswith("hacs-") for service_id in service_ids)


def test_bootstrap_pack_governance_crea_manifest_macchina_e_studio(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Pack", "studio-pack", db_config={"mode": "SQLITE"})

    result = bootstrap_pack_governance(
        app_root=REPO_ROOT,
        registry_path=cfg["TENANTS_REGISTRY"],
        app_version=__version__,
        tenant_manager=tm,
    )

    system_root = resolve_system_pack_root(cfg["TENANTS_REGISTRY"])
    studio_root = tm.data_dir(studio.slug)

    assert result.installation["installation_id"]
    assert result.product_pack["version"] == __version__
    assert result.update_pack["to_version"] == __version__
    assert (system_root / "product" / "manifests" / "product_pack.json").exists()
    assert (system_root / "updates" / "current_update_pack.json").exists()
    assert (studio_root / "config" / "studio_local_pack.json").exists()
    assert (studio_root / "studio_data" / "memory" / "facts").is_dir()
    assert (studio_root / "studio_data" / "vectors").is_dir()
    assert (system_root / "installation" / "keys" / "master.key").exists()


def test_installation_pack_repository_salva_snapshot_corrente(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    tm.crea("Studio Pack", "studio-pack", db_config={"mode": "SQLITE"})

    result = bootstrap_pack_governance(
        app_root=REPO_ROOT,
        registry_path=cfg["TENANTS_REGISTRY"],
        app_version=__version__,
        tenant_manager=tm,
    )
    repo = InstallationPackRepository.from_registry_path(cfg["TENANTS_REGISTRY"])
    repo.upsert_product_pack(result.product_pack)
    repo.upsert_update_pack(result.update_pack)
    for payload in result.studio_local_packs:
        repo.upsert_studio_local_pack(payload)

    snapshot = repo.load_snapshot()
    stats = repo.storage_stats()

    assert snapshot["product_pack"]["version"] == __version__
    assert snapshot["update_pack"]["to_version"] == __version__
    assert len(snapshot["studio_local_packs"]) == 1
    assert stats["product_packs"] == 1
    assert stats["studio_local_packs"] == 1
    assert stats["update_packs"] == 1


def test_studio_local_pack_non_riconcilia_storage_in_startup(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Pack", "studio-pack", db_config={"mode": "SQLITE"})
    identity = ensure_installation_identity(
        app_root=REPO_ROOT,
        registry_path=cfg["TENANTS_REGISTRY"],
        app_version=__version__,
    )

    def fail_reconcile(slug: str):
        raise AssertionError(f"reconcile_storage_aliases non deve girare in startup: {slug}")

    monkeypatch.setattr(tm, "reconcile_storage_aliases", fail_reconcile)

    payload = ensure_studio_local_pack(
        tenant_manager=tm,
        studio=studio,
        installation_identity=identity,
    )

    assert payload["studio_slug"] == studio.slug
    assert (tm._data_dir(studio.slug) / "config" / "studio_local_pack.json").exists()  # noqa: SLF001


def test_installation_pack_surface_e_route_admin_sono_accessibili_al_superadmin(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Pack", "studio-pack", db_config={"mode": "SQLITE"})
    app = create_app(cfg)

    with app.app_context():
        payload = build_installation_pack_surface(selected_slug=studio.slug)

    assert payload["installation"]["installation_id"]
    assert payload["product_pack"]["version"] == __version__
    assert payload["selected_studio_pack"]["studio_slug"] == studio.slug
    assert payload["headline"]["product_services"] >= 6

    with app.test_client() as client:
        client.get("/login")
        client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        page = client.get(f"/admin/installazione-pack/?slug={studio.slug}")
        api = client.get(f"/admin/installazione-pack/api?slug={studio.slug}")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Product Pack, Studio Local Pack e Update Pack" in html
    assert "Rigenera bootstrap e manifest" in html
    assert "Il SUPERADMIN installa il prodotto" in html
    assert "Bootstrap macchina" in html
    assert "Update Pack e repository SQL" in html
    assert "Dipendenze runtime locali" in html

    assert api.status_code == 200
    api_payload = api.get_json()
    assert api_payload["selected_studio_pack"]["studio_slug"] == studio.slug
    assert api_payload["headline"]["product_services"] >= 6
    assert api_payload["runtime_dependencies"]


def test_installation_pack_separa_lex_da_provider_ai_locale(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    product_pack = {
        "signature": "firma-test",
        "services": list(SYSTEM_SERVICE_DEFINITIONS),
    }
    observability = {
        "providers": {
            "local_ai": {
                "settings": {"enabled": True},
                "runtime": {
                    "status": "missing",
                    "api_base_url": "http://127.0.0.1:11434/api",
                    "last_error": "Ollama non raggiungibile",
                },
                "runtime_online": False,
                "counts": {
                    "chunks_total": 5,
                    "chunks_pending": 5,
                },
            }
        }
    }

    with app.app_context():
        services = _service_runtime_cards(product_pack, observability)
        dependencies = _runtime_dependency_cards(observability)

    lex_card = next(item for item in services if item["service_id"] == "iusentra-lex")
    local_ai_card = next(item for item in dependencies if item["dependency_id"] == "local_ai_provider")

    assert lex_card["status"] == "ok"
    assert "AI locale non ancora pronta" not in lex_card["detail"]
    assert local_ai_card["status"] == "warning"
    assert "Ollama non raggiungibile" in local_ai_card["detail"]
    assert "Chunk RAG: 5 pendenti su 5" in local_ai_card["meta"]
