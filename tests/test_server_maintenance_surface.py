from __future__ import annotations

import os
from pathlib import Path

from tests.test_operational_surfaces import _cfg_web, _seed_runtime, _write_studio_config
from web.app import create_app
from web.services.server_maintenance_surface import (
    backup_retention_settings,
    build_server_maintenance_surface,
    directory_size,
    run_backup_retention,
    run_storage_compaction,
)


def test_directory_size_non_conta_due_volte_hardlink(tmp_path: Path):
    first = tmp_path / "a.bin"
    second = tmp_path / "nested" / "b.bin"
    second.parent.mkdir()
    first.write_bytes(b"x" * 8192)
    second.hardlink_to(first)

    assert directory_size(tmp_path) == 8192


def test_backup_retention_defaults_professionali():
    settings = backup_retention_settings({})

    assert settings == {
        "days": 14,
        "count": 3,
        "min_count": 2,
        "max_gib": 8,
    }


def test_backup_retention_elimina_solo_archivi_governati(tmp_path: Path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for index in range(4):
        archive = backup_dir / f"iusentra-data-20260506_090{index}00.tar.zst"
        archive.write_bytes(bytes([index]) * 4096)
        checksum = Path(f"{archive}.sha256")
        checksum.write_text("sha256  archive\n", encoding="utf-8")
        mtime = 1_700_000_000 + index
        archive.touch()
        checksum.touch()
        os.utime(archive, (mtime, mtime))
        os.utime(checksum, (mtime, mtime))
    legacy = backup_dir / "auth-before-migration-20260429162152.tgz"
    legacy.write_bytes(b"non gestito")

    analysis = run_backup_retention(
        apply=False,
        backup_dir=backup_dir,
        config={
            "IUSENTRA_BACKUP_RETENTION_COUNT": 2,
            "IUSENTRA_BACKUP_RETENTION_MIN_COUNT": 2,
            "IUSENTRA_BACKUP_RETENTION_MAX_GIB": 99,
            "IUSENTRA_BACKUP_RETENTION_DAYS": 99999,
        },
    )

    assert analysis["backup_archives_scanned"] == 4
    assert analysis["archives_to_delete"] == 2
    assert analysis["bytes_reclaimable"] >= 8192

    applied = run_backup_retention(
        apply=True,
        backup_dir=backup_dir,
        config={
            "IUSENTRA_BACKUP_RETENTION_COUNT": 2,
            "IUSENTRA_BACKUP_RETENTION_MIN_COUNT": 2,
            "IUSENTRA_BACKUP_RETENTION_MAX_GIB": 99,
            "IUSENTRA_BACKUP_RETENTION_DAYS": 99999,
        },
    )

    assert applied["archives_deleted"] == 2
    assert len(list(backup_dir.glob("iusentra-data-*.tar.zst"))) == 2
    assert legacy.exists()


def test_server_maintenance_surface_mostra_consumi_per_studio(tmp_path: Path):
    tenant_root = tmp_path / "tenants" / "studio-a"
    (tenant_root / "email" / "allegati" / "m1").mkdir(parents=True)
    (tenant_root / "backup" / "mirror" / "cliente" / "studio-a" / "run").mkdir(parents=True)
    (tenant_root / "email" / "allegati" / "m1" / "atto.pdf").write_bytes(b"a" * 8192)
    (tenant_root / "backup" / "snapshot.zip").write_bytes(b"b" * 8192)

    backup_dir = tmp_path / "external_backups"
    backup_dir.mkdir()
    (backup_dir / "iusentra-data-20260506_090000.tar.zst").write_bytes(b"c" * 8192)
    payload = build_server_maintenance_surface(
        {
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "IUSENTRA_BACKUP_DIR": str(backup_dir),
        }
    )

    assert payload["mock_fallback"] is False
    assert payload["tenants"]
    assert payload["tenants"][0]["slug"] == "studio-a"
    assert payload["tenants"][0]["email_bytes"] >= 8192
    assert payload["actions"]["apply_compaction"] == "/admin/server-manutenzione/compatta"
    assert payload["summary"]["backup_external_size_label"] == "8.0 KiB"
    assert payload["backup_retention"]["backup_archives_scanned"] == 1


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
    assert "retention backup" in html
