from __future__ import annotations

import json
from pathlib import Path

from scripts.compact_iusentra_storage import discover_backup_roots, main


def test_discover_backup_roots_include_root_e_tenant(tmp_path: Path):
    root_backup = tmp_path / "backup"
    tenant_backup = tmp_path / "tenants" / "studio" / "backup"
    root_backup.mkdir(parents=True)
    tenant_backup.mkdir(parents=True)

    roots = discover_backup_roots(tmp_path)

    assert roots == sorted([root_backup.resolve(), tenant_backup.resolve()], key=lambda item: str(item))


def test_compact_storage_deduplica_backup_mirror(tmp_path: Path, capsys):
    backup_root = tmp_path / "tenants" / "studio" / "backup"
    mirror_root = backup_root / "mirror" / "cliente" / "studio" / "20260506_010000"
    backup_root.mkdir(parents=True)
    mirror_root.mkdir(parents=True)
    content = b"x" * 8192
    primary = backup_root / "snapshot.zip"
    duplicate = mirror_root / "snapshot.zip"
    primary.write_bytes(content)
    duplicate.write_bytes(content)

    exit_code = main(["--data-root", str(tmp_path), "--apply", "--min-size-bytes", "1"])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["physical_duplicate_files"] == 1
    assert captured["hardlinked_files"] == 1
    assert captured["already_hardlinked_files"] == 0
    assert captured["bytes_reclaimed"] == len(content)
    assert primary.samefile(duplicate)

    exit_code = main(["--data-root", str(tmp_path), "--min-size-bytes", "1"])
    captured = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["duplicate_files"] == 1
    assert captured["physical_duplicate_files"] == 0
    assert captured["already_hardlinked_files"] == 1
    assert captured["bytes_reclaimable"] == 0
