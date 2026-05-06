from __future__ import annotations

from pathlib import Path

from tests.test_operational_surfaces import _cfg_web, _seed_runtime, _write_studio_config
from web.app import create_app
from web.services.server_maintenance_surface import build_server_maintenance_surface, run_storage_compaction


def test_server_maintenance_surface_mostra_consumi_per_studio(tmp_path: Path):
    tenant_root = tmp_path / "tenants" / "studio-a"
    (tenant_root / "email" / "allegati" / "m1").mkdir(parents=True)
    (tenant_root / "backup" / "mirror" / "cliente" / "studio-a" / "run").mkdir(parents=True)
    (tenant_root / "email" / "allegati" / "m1" / "atto.pdf").write_bytes(b"a" * 8192)
    (tenant_root / "backup" / "snapshot.zip").write_bytes(b"b" * 8192)

    payload = build_server_maintenance_surface({"AUTH_DB": str(tmp_path / "auth" / "utenti.json")})

    assert payload["mock_fallback"] is False
    assert payload["tenants"]
    assert payload["tenants"][0]["slug"] == "studio-a"
    assert payload["tenants"][0]["email_bytes"] >= 8192
    assert payload["actions"]["apply_compaction"] == "/admin/server-manutenzione/compatta"


def test_server_maintenance_compatta_singolo_studio(tmp_path: Path):
    tenant_root = tmp_path / "tenants" / "studio-a" / "backup"
    mirror_root = tenant_root / "mirror" / "cliente" / "studio-a" / "run"
    mirror_root.mkdir(parents=True)
    (tenant_root / "snapshot.zip").write_bytes(b"x" * 8192)
    (mirror_root / "snapshot.zip").write_bytes(b"x" * 8192)

    result = run_storage_compaction(apply=True, data_root=tmp_path, tenant_slug="studio-a")

    assert result["tenant_slug"] == "studio-a"
    assert result["physical_duplicate_files"] == 1
    assert result["hardlinked_files"] == 1
    assert result["bytes_reclaimed"] == 8192
    assert (tenant_root / "snapshot.zip").samefile(mirror_root / "snapshot.zip")

    post_result = run_storage_compaction(apply=False, data_root=tmp_path, tenant_slug="studio-a")

    assert post_result["duplicate_files"] == 1
    assert post_result["physical_duplicate_files"] == 0
    assert post_result["already_hardlinked_files"] == 1
    assert post_result["bytes_reclaimable"] == 0


def test_superadmin_server_manutenzione_renderizza(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    _seed_runtime(cfg)
    tenant_root = tmp_path / "tenants" / "studio-a" / "email" / "allegati" / "m1"
    tenant_root.mkdir(parents=True)
    (tenant_root / "atto.pdf").write_bytes(b"a" * 8192)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "superadmin-operativo", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200
        response = client.get("/admin/server-manutenzione", follow_redirects=True)

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Server e manutenzione" in html
    assert "Consumi per studio" in html
    assert "Compatta" in html
