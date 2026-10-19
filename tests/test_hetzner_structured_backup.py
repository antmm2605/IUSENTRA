from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from deploy.hetzner.backup_structured import create_structured_backup


def _create_database(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE records (value TEXT NOT NULL)")
        connection.execute("INSERT INTO records(value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def test_structured_backup_is_consistent_and_rotates_to_one_copy(tmp_path: Path) -> None:
    source_root = tmp_path / "tenants"
    backup_dir = tmp_path / "backups"
    _create_database(source_root / "studio-a" / "studio.db", "prima")
    _create_database(source_root / "studio-b" / "studio.db", "seconda")
    backup_dir.mkdir()
    legacy = backup_dir / "studio-legale-prova-studio-20260801-1200.db"
    legacy.write_bytes(b"vecchio")
    legacy.with_suffix(".db.sha256").write_text("vecchio", encoding="utf-8")

    first = create_structured_backup(
        source_root=source_root,
        backup_dir=backup_dir,
        retention_count=1,
        min_free_gib=0,
        prune_legacy_single_db=True,
    )
    assert first["ok"] is True
    assert first["source_of_truth"] == "sqlite"
    assert first["database_count"] == 2
    assert not legacy.exists()
    assert not legacy.with_suffix(".db.sha256").exists()

    snapshots = sorted(backup_dir.glob("iusentra-structured-*"))
    assert len(snapshots) == 1
    manifest = json.loads((snapshots[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_of_truth"] == "sqlite"
    assert manifest["scope"] == "tenant_studio_databases"
    assert manifest["database_count"] == 2
    assert manifest["backup_bytes"] == sum(entry["backup_bytes"] for entry in manifest["entries"])
    assert manifest["retention_count"] == 1
    assert {entry["tenant_id"] for entry in manifest["entries"]} == {"studio-a", "studio-b"}
    assert {entry["quick_check"] for entry in manifest["entries"]} == {"ok"}

    with closing(sqlite3.connect(snapshots[0] / "studio-a" / "studio.db")) as connection:
        assert connection.execute("SELECT value FROM records").fetchone()[0] == "prima"

    with closing(sqlite3.connect(source_root / "studio-a" / "studio.db")) as connection:
        connection.execute("INSERT INTO records(value) VALUES ('aggiornata')")
        connection.commit()

    second = create_structured_backup(
        source_root=source_root,
        backup_dir=backup_dir,
        retention_count=1,
        min_free_gib=0,
    )
    assert second["ok"] is True
    snapshots = sorted(backup_dir.glob("iusentra-structured-*"))
    assert len(snapshots) == 1
    with closing(sqlite3.connect(snapshots[0] / "studio-a" / "studio.db")) as connection:
        values = [row[0] for row in connection.execute("SELECT value FROM records ORDER BY rowid")]
    assert values == ["prima", "aggiornata"]


def test_structured_backup_rejects_empty_tenant_root(tmp_path: Path) -> None:
    source_root = tmp_path / "tenants"
    backup_dir = tmp_path / "backups"
    source_root.mkdir()

    try:
        create_structured_backup(
            source_root=source_root,
            backup_dir=backup_dir,
            min_free_gib=0,
        )
    except RuntimeError as exc:
        assert "Nessun database tenant studio.db" in str(exc)
    else:
        raise AssertionError("Il backup senza database tenant doveva fallire chiuso")


def test_structured_backup_failure_preserves_last_valid_snapshot(tmp_path: Path) -> None:
    source_root = tmp_path / "tenants"
    backup_dir = tmp_path / "backups"
    database = source_root / "studio-a" / "studio.db"
    _create_database(database, "valida")

    create_structured_backup(
        source_root=source_root,
        backup_dir=backup_dir,
        retention_count=1,
        min_free_gib=0,
    )
    previous = next(backup_dir.glob("iusentra-structured-*"))
    database.write_bytes(b"database non valido")

    try:
        create_structured_backup(
            source_root=source_root,
            backup_dir=backup_dir,
            retention_count=1,
            min_free_gib=0,
        )
    except sqlite3.DatabaseError:
        pass
    else:
        raise AssertionError("Il backup corrotto doveva fallire chiuso")

    assert previous.is_dir()
    assert list(backup_dir.glob("iusentra-structured-*")) == [previous]
    assert not list(backup_dir.glob(".iusentra-structured-*"))


def test_deploy_workflow_runs_structured_backup_on_push() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "deploy-hetzner.yml").read_text(
        encoding="utf-8"
    )

    assert "default: false" in workflow
    no_backup_line = next(line for line in workflow.splitlines() if "NO_BACKUP_REQUESTED:" in line)
    assert "github.event_name == 'push'" not in no_backup_line
    assert "inputs.skip_backup" in no_backup_line
    assert "[no-backup]" in no_backup_line
    assert "deploy/hetzner/backup_structured.py" in workflow
    assert "timeout 290 python3 /tmp/iusentra-backup-structured.py" in workflow
    assert "--retention-count 1" in workflow
    assert "--prune-legacy-single-db" in workflow


def test_rotation_preserves_supplemental_evidence_and_its_hashes(tmp_path):
    import hashlib

    source = tmp_path / "tenants"
    backups = tmp_path / "backups"
    _create_database(source / "studio-a" / "studio.db", "dato")
    first = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    extra = first / "supplemental-technical"
    extra.mkdir()
    (extra / "technical.tar.zst").write_bytes(b"prova originale compressa")
    (extra / "manifest.json").write_text('{"sha":"originale"}', encoding="utf-8")
    second = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    assert not first.exists()
    preserved = list((second / "supplemental-technical").rglob("technical.tar.zst"))
    assert len(preserved) == 1 and preserved[0].read_bytes() == b"prova originale compressa"
    manifest = json.loads((second / "manifest.json").read_text())
    evidence = manifest["supplemental_technical"]
    assert evidence["files"] == 2
    index = second / evidence["index"]
    assert hashlib.sha256(index.read_bytes()).hexdigest() == evidence["index_sha256"]
    for row in json.loads(index.read_text())["files"]:
        assert hashlib.sha256((second / row["stored"]).read_bytes()).hexdigest() == row["sha256"]
    third = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    assert len(list(backups.glob("iusentra-structured-*"))) == 1
    assert [p.read_bytes() for p in (third / "supplemental-technical").rglob("technical.tar.zst")] == [
        b"prova originale compressa"
    ]


def test_corrupt_technical_copy_stops_retention(tmp_path, monkeypatch):
    import deploy.hetzner.backup_structured as module

    source = tmp_path / "tenants"
    backups = tmp_path / "backups"
    _create_database(source / "studio-a" / "studio.db", "dato")
    first = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    extra = first / "supplemental-technical"
    extra.mkdir()
    file = extra / "audit.json"
    file.write_text("originale")
    monkeypatch.setattr(
        module, "_copy_technical_file", lambda source, destination: Path(destination).write_text("corrotto")
    )
    import pytest

    with pytest.raises(RuntimeError, match="non verificata"):
        create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)
    assert first.exists() and file.read_text() == "originale"
    assert list(backups.glob("iusentra-structured-*")) == [first]


def test_new_evidence_during_backup_stops_retention(tmp_path, monkeypatch):
    import deploy.hetzner.backup_structured as module
    import pytest

    source = tmp_path / "tenants"
    backups = tmp_path / "backups"
    _create_database(source / "studio-a" / "studio.db", "dato")
    first = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    extra = first / "supplemental-technical"
    extra.mkdir()
    (extra / "audit.json").write_text("originale")
    original = module._backup_sqlite

    def changed(*args):
        result = original(*args)
        (extra / "arrivato-dopo.json").write_text("nuova prova")
        return result

    monkeypatch.setattr(module, "_backup_sqlite", changed)
    with pytest.raises(RuntimeError, match="Contenuti tecnici cambiati"):
        create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)
    assert first.exists() and (extra / "arrivato-dopo.json").exists()


def test_retention_never_deletes_new_snapshot_for_old_future_mtime(tmp_path):
    import os
    import time

    source = tmp_path / "tenants"
    backups = tmp_path / "backups"
    _create_database(source / "studio-a" / "studio.db", "dato")
    first = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    os.utime(first, (time.time() + 86400, time.time() + 86400))
    second = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    assert second.exists() and not first.exists()


def test_maintenance_lock_stops_a_second_backup(tmp_path):
    import pytest
    from deploy.hetzner.backup_structured import _maintenance_lock

    source = tmp_path / "tenants"
    backups = tmp_path / "backups"
    backups.mkdir()
    _create_database(source / "studio-a" / "studio.db", "dato")
    with _maintenance_lock(backups):
        with pytest.raises(RuntimeError, match="già in corso"):
            create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)
    assert not list(backups.glob("iusentra-structured-*"))


def test_space_budget_includes_technical_evidence(tmp_path, monkeypatch):
    import shutil
    import pytest
    import deploy.hetzner.backup_structured as module

    source = tmp_path / "tenants"
    backups = tmp_path / "backups"
    _create_database(source / "studio-a" / "studio.db", "dato")
    first = Path(create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)["snapshot"])
    extra = first / "supplemental-technical"
    extra.mkdir()
    (extra / "audit.bin").write_bytes(b"a" * 4096)
    available = (source / "studio-a" / "studio.db").stat().st_size + 4095
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(available, 0, available))
    with pytest.raises(RuntimeError, match="Spazio insufficiente"):
        create_structured_backup(source_root=source, backup_dir=backups, min_free_gib=0)
    assert first.exists() and (extra / "audit.bin").read_bytes() == b"a" * 4096
