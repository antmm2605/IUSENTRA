from __future__ import annotations

import os
from pathlib import Path

from scripts.purge_downloaded_mailboxes import purge_downloaded_mailboxes
from tests.test_operational_surfaces import _cfg_web, _seed_runtime, _write_studio_config
from web.app import create_app
from web.services import server_maintenance_surface as server_surface
from web.services.server_maintenance_surface import (
    backup_retention_settings,
    build_server_maintenance_surface,
    directory_size,
    run_backup_retention,
    run_normativa_global_cleanup,
    run_tenant_backup_retention,
    run_max_storage_optimization,
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
        "count": 1,
        "min_count": 1,
        "max_gib": 8,
    }


def test_backup_retention_non_supera_tre_copie():
    settings = backup_retention_settings(
        {
            "IUSENTRA_BACKUP_RETENTION_COUNT": 12,
            "IUSENTRA_BACKUP_RETENTION_MIN_COUNT": 9,
        }
    )

    assert settings["count"] == 3
    assert settings["min_count"] == 3


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
    (tenant_root / "preventivi").mkdir(parents=True)
    (tenant_root / "email" / "allegati" / "m1" / "atto.pdf").write_bytes(b"a" * 8192)
    (tenant_root / "backup" / "snapshot.zip").write_bytes(b"b" * 8192)
    (tenant_root / "preventivi" / "preventivi_repository.json").write_bytes(b"c" * 4096)

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
    assert payload["tenants"][0]["dominant_category"]["code"] in {"backup", "email"}
    assert payload["tenants"][0]["top_paths"]
    assert payload["tenants"][0]["largest_files"]
    assert all("repository" not in item.get("display_path", "") for item in payload["tenants"][0]["largest_files"])
    assert {item["code"] for item in payload["tenants"][0]["categories"]} >= {"email", "backup"}
    assert payload["actions"]["apply_compaction"] == "/admin/server-manutenzione/compatta"
    assert payload["summary"]["backup_external_size_label"] == "8.0 KiB"
    assert payload["summary"]["tenant_email_size_label"] == "8.0 KiB"
    assert payload["summary"]["tenant_backup_size_label"] == "8.0 KiB"
    assert payload["backup_retention"]["backup_archives_scanned"] == 2
    assert payload["backup_retention"]["tenant"]["backup_archives_scanned"] == 1


def test_server_maintenance_surface_separa_cartelle_legacy_da_studi_attivi(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    registry.write_text(
        '{"tenants": [{"slug": "studio-a", "storage_key": "tenant-a", "nome": "Studio A", "attivo": true}]}',
        encoding="utf-8",
    )
    active_root = tmp_path / "tenants" / "tenant-a"
    legacy_root = tmp_path / "tenants" / "studio-a"
    active_root.mkdir(parents=True)
    legacy_root.mkdir(parents=True)
    (active_root / "studio.db").write_bytes(b"a" * 4096)
    (legacy_root / "vecchio.json").write_bytes(b"b" * 4096)

    payload = build_server_maintenance_surface(
        {
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "TENANTS_REGISTRY": str(registry),
            "IUSENTRA_BACKUP_DIR": str(tmp_path / "external_backups"),
        }
    )

    assert [row["slug"] for row in payload["tenants"]] == ["tenant-a"]
    assert payload["summary"]["tenant_count"] == 1
    assert payload["summary"]["tenant_storage_dirs"] == 2
    assert payload["summary"]["inactive_tenant_dirs"] == 1
    assert payload["inactive_tenants"][0]["slug"] == "studio-a"
    assert payload["inactive_tenants"][0]["storage_status"] == "alias_legacy"


def test_tenant_backup_retention_conserva_solo_ultimo_completo_e_tmp(tmp_path: Path):
    import zipfile

    backup_root = tmp_path / "tenants" / "studio-a" / "backup"
    mirror_root = backup_root / "mirror" / "cliente"
    backup_root.mkdir(parents=True)
    mirror_root.mkdir(parents=True)

    old_complete = backup_root / "old.zip"
    new_complete = backup_root / "new.zip"
    temporary = backup_root / "running_tmp.zip"
    partial = backup_root / "partial.zip"
    for archive in (old_complete, new_complete, temporary):
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("fascicoli/documenti/atto.pdf", "contenuto")
    with zipfile.ZipFile(partial, "w") as handle:
        handle.writestr("registro.json", "{}")
    (mirror_root / "old.zip").write_bytes(b"mirror")
    for index, archive in enumerate((old_complete, partial, temporary, new_complete), start=1):
        mtime = 1_700_000_000 + index
        os.utime(archive, (mtime, mtime))

    analysis = run_tenant_backup_retention(apply=False, data_root=tmp_path)

    assert analysis["backup_archives_scanned"] == 4
    assert analysis["archives_to_delete"] == 3
    assert analysis["mirror_dirs_to_delete"] == 1
    assert analysis["kept_archives"][0]["name"] == "new.zip"

    applied = run_tenant_backup_retention(apply=True, data_root=tmp_path)

    assert applied["archives_deleted"] == 3
    assert new_complete.exists()
    assert not old_complete.exists()
    assert not temporary.exists()
    assert not partial.exists()
    assert not (backup_root / "mirror").exists()


def test_normativa_global_cleanup_rimuove_solo_backup(tmp_path: Path):
    normativa_root = tmp_path / "normativa"
    backup_root = normativa_root / "backups"
    index_root = normativa_root / "index"
    backup_root.mkdir(parents=True)
    index_root.mkdir(parents=True)
    db = normativa_root / "normattiva.sqlite"
    index = index_root / "normattiva_chunks.jsonl"
    db.write_bytes(b"db")
    index.write_text("{}\n", encoding="utf-8")
    (backup_root / "normattiva.sqlite").write_bytes(b"backup" * 1024)

    analysis = run_normativa_global_cleanup(
        apply=False,
        config={"NORMATTIVA_DB": str(db), "NORMATTIVA_JSONL": str(index)},
    )

    assert analysis["bytes_reclaimable"] > 0
    assert analysis["live_db_exists"] is True
    assert analysis["index_exists"] is True

    applied = run_normativa_global_cleanup(
        apply=True,
        config={"NORMATTIVA_DB": str(db), "NORMATTIVA_JSONL": str(index)},
    )

    assert applied["directories_deleted"] == 1
    assert not backup_root.exists()
    assert db.exists()
    assert index.exists()


def test_server_maintenance_surface_spiega_spazio_fuori_studi(tmp_path: Path, monkeypatch):
    host_root = tmp_path / "iusentra-host"
    data_root = host_root / "data"
    tenant_root = data_root / "tenants" / "studio-a" / "email" / "allegati"
    snapshot_root = host_root / "tmp-backup-snapshot"
    backup_dir = host_root / "backups"
    tenant_root.mkdir(parents=True)
    snapshot_root.mkdir(parents=True)
    backup_dir.mkdir(parents=True)
    (tenant_root / "atto.pdf").write_bytes(b"a" * 4096)
    (snapshot_root / "copia-temporanea.bin").write_bytes(b"b" * 8192)

    monkeypatch.setattr(
        server_surface,
        "docker_storage_summary",
        lambda: {
            "available": True,
            "source": "test",
            "error": "",
            "images_count": 3,
            "containers_count": 2,
            "volumes_count": 0,
            "build_cache_count": 5,
            "images_size_bytes": 128 * 1024**2,
            "containers_size_bytes": 0,
            "volumes_size_bytes": 0,
            "build_cache_size_bytes": 2 * 1024**3,
            "build_cache_reclaimable_bytes": 2 * 1024**3,
            "total_size_bytes": 2 * 1024**3 + 128 * 1024**2,
            "images_size_label": "128.0 MiB",
            "containers_size_label": "0 B",
            "volumes_size_label": "0 B",
            "build_cache_size_label": "2.0 GiB",
            "build_cache_reclaimable_label": "2.0 GiB",
            "total_size_label": "2.1 GiB",
        },
    )

    payload = build_server_maintenance_surface(
        {
            "AUTH_DB": str(data_root / "auth" / "utenti.json"),
            "IUSENTRA_BACKUP_DIR": str(backup_dir),
            "IUSENTRA_HOST_IUSENTRA_DIR": str(host_root),
        }
    )

    console = payload["host_console"]
    assert console["provider_name"] == "Hetzner CPX42"
    assert console["immediate_reclaimable_label"] == "2.0 GiB"
    assert any(item["label"] == "Cache costruzione servizi" for item in console["recovery_items"])
    assert any(item["code"] == "temporary_snapshot" and item["size_bytes"] >= 8192 for item in console["areas"])


def test_server_maintenance_surface_scansione_rapida_non_blocca_studio_grande(tmp_path: Path):
    tenant_root = tmp_path / "tenants" / "studio-a" / "email" / "allegati"
    tenant_root.mkdir(parents=True)
    for index in range(4):
        (tenant_root / f"allegato-{index}.pdf").write_bytes(bytes([index]) * 1024)

    payload = build_server_maintenance_surface(
        {
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "IUSENTRA_BACKUP_DIR": str(tmp_path / "external_backups"),
            "IUSENTRA_STORAGE_SCAN_MAX_FILES": 2,
            "IUSENTRA_STORAGE_SCAN_SECONDS": 10,
        }
    )

    tenant = payload["tenants"][0]
    assert tenant["scan_truncated"] is True
    assert tenant["scan_limit_reason"] == "limite file"
    assert tenant["file_count"] == 2
    assert payload["summary"]["scan_truncated"] is True
    assert any("Scansione rapida" in item for item in tenant["recommendations"])


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


def test_server_maintenance_ottimizzazione_massima_deduplica_e_compatta_archivi(tmp_path: Path):
    tenant_root = tmp_path / "tenants" / "studio-a"
    attachment_root = tenant_root / "email" / "allegati" / "m1"
    attachment_root.mkdir(parents=True)
    (attachment_root / "atto-a.pdf").write_bytes(b"x" * 8192)
    (attachment_root / "atto-b.pdf").write_bytes(b"x" * 8192)
    archive = tenant_root / "studio.json"
    archive.write_text(
        '{\n  "nome": "Studio A",\n  "voci": [\n    1,\n    2,\n    3\n  ]\n}\n',
        encoding="utf-8",
    )

    analysis = run_max_storage_optimization(apply=False, data_root=tmp_path, tenant_slug="studio-a")

    assert analysis["compaction"]["physical_duplicate_files"] == 1
    assert analysis["databases"]["optimized_files"] == 1
    assert analysis["bytes_reclaimable"] > 8192

    applied = run_max_storage_optimization(apply=True, data_root=tmp_path, tenant_slug="studio-a")

    assert applied["compaction"]["hardlinked_files"] == 1
    assert applied["databases"]["optimized_files"] == 1
    assert applied["bytes_reclaimed"] > 8192
    assert (attachment_root / "atto-a.pdf").samefile(attachment_root / "atto-b.pdf")
    assert "\n  " not in archive.read_text(encoding="utf-8")


def test_purge_downloaded_mailboxes_svuota_posta_senza_toccare_config(tmp_path: Path):
    email_dir = tmp_path / "tenants" / "studio-a" / "email"
    attachments = email_dir / "allegati" / "m1"
    attachments.mkdir(parents=True)
    (email_dir / "casella.json").write_text('{"pec": {"id": "pec"}}', encoding="utf-8")
    (email_dir / "ordinaria.json").write_text('{"mail": {"id": "mail"}}', encoding="utf-8")
    (attachments / "atto.pdf").write_bytes(b"x" * 8192)
    config = tmp_path / "tenants" / "studio-a" / "config" / "studio.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"pec": {"indirizzo": "studio@example.test"}}', encoding="utf-8")
    state = tmp_path / "tenants" / "studio-a" / "fascicoli" / "pec_cancelleria_state.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"last": "uid"}', encoding="utf-8")

    analysis = purge_downloaded_mailboxes(tmp_path, apply=False)
    assert analysis["bytes_reclaimed"] >= 8192

    result = purge_downloaded_mailboxes(tmp_path, apply=True)

    assert result["mail_roots"] == 1
    assert result["bytes_reclaimed"] >= 8192
    assert (email_dir / "casella.json").read_text(encoding="utf-8") == "{}\n"
    assert (email_dir / "ordinaria.json").read_text(encoding="utf-8") == "{}\n"
    assert (email_dir / "allegati").is_dir()
    assert not any((email_dir / "allegati").rglob("*"))
    assert not state.exists()
    assert config.exists()


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
    assert "Console Hetzner CPX42" in html
    assert "Sistema e piattaforma" in html
    assert "Consumi per studio" in html
    assert "Cartelle più pesanti" in html
    assert "File principali" in html
    assert "Compatta" in html
    assert "Ottimizza archivi studi" in html
    assert "Pulisci cache servizi" in html
    assert "Pulisci backup Normattiva" in html
    assert "retention backup" in html
