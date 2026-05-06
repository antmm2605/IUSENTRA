from __future__ import annotations

import os
from pathlib import Path

from pct.email_attachments import deduplicate_attachment_tree, discover_email_attachment_roots
from pct.email_client import GestioneEmailRicevute


def _disk_usage(path: Path) -> int:
    total = 0
    seen: set[tuple[int, int]] = set()
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        stat = item.stat()
        key = (stat.st_dev, stat.st_ino)
        if key in seen:
            continue
        seen.add(key)
        total += stat.st_size
    return total


def test_salva_allegato_riusa_file_identico_nella_stessa_email(tmp_path: Path) -> None:
    gestore = GestioneEmailRicevute(str(tmp_path / "email" / "casella.json"))

    first = gestore._salva_allegato("MAIL-1", "atto.pdf", b"contenuto identico")
    second = gestore._salva_allegato("MAIL-1", "atto.pdf", b"contenuto identico")

    assert first["percorso_rel"] == "MAIL-1/atto.pdf"
    assert second["percorso_rel"] == first["percorso_rel"]
    assert first["sha256"] == second["sha256"]
    assert len(list((tmp_path / "email" / "allegati" / "MAIL-1").iterdir())) == 1


def test_salva_allegato_con_nome_uguale_e_contenuto_diverso_crea_suffix(tmp_path: Path) -> None:
    gestore = GestioneEmailRicevute(str(tmp_path / "email" / "casella.json"))

    first = gestore._salva_allegato("MAIL-1", "atto.pdf", b"prima versione")
    second = gestore._salva_allegato("MAIL-1", "atto.pdf", b"seconda versione")

    assert first["percorso_rel"] == "MAIL-1/atto.pdf"
    assert second["percorso_rel"] == "MAIL-1/atto_1.pdf"
    assert first["sha256"] != second["sha256"]


def test_deduplicate_attachment_tree_dry_run_non_modifica_file(tmp_path: Path) -> None:
    root = tmp_path / "email" / "allegati"
    (root / "MAIL-1").mkdir(parents=True)
    (root / "MAIL-2").mkdir(parents=True)
    (root / "MAIL-1" / "atto.pdf").write_bytes(b"x" * 4096)
    (root / "MAIL-2" / "atto-copia.pdf").write_bytes(b"x" * 4096)
    before = _disk_usage(root)

    report = deduplicate_attachment_tree(root, dry_run=True)

    assert report.files_scanned == 2
    assert report.duplicate_groups == 1
    assert report.duplicate_files == 1
    assert report.physical_duplicate_files == 1
    assert report.already_hardlinked_files == 0
    assert report.bytes_reclaimable == 4096
    assert report.bytes_reclaimed == 0
    assert _disk_usage(root) == before
    assert report.manifest_path is not None
    assert Path(report.manifest_path).exists()


def test_deduplicate_attachment_tree_apply_hardlinka_file_identici(tmp_path: Path) -> None:
    root = tmp_path / "email" / "allegati"
    (root / "MAIL-1").mkdir(parents=True)
    (root / "MAIL-2").mkdir(parents=True)
    canonical = root / "MAIL-1" / "atto.pdf"
    duplicate = root / "MAIL-2" / "atto-copia.pdf"
    canonical.write_bytes(b"x" * 4096)
    duplicate.write_bytes(b"x" * 4096)

    report = deduplicate_attachment_tree(root, dry_run=False)

    assert report.physical_duplicate_files == 1
    assert report.hardlinked_files == 1
    assert report.bytes_reclaimed == 4096
    assert duplicate.read_bytes() == b"x" * 4096
    assert os.path.samefile(canonical, duplicate)

    post_report = deduplicate_attachment_tree(root, dry_run=True, write_manifest=False)

    assert post_report.duplicate_files == 1
    assert post_report.physical_duplicate_files == 0
    assert post_report.already_hardlinked_files == 1
    assert post_report.bytes_reclaimable == 0


def test_discover_email_attachment_roots_trova_globali_e_tenant(tmp_path: Path) -> None:
    global_root = tmp_path / "email" / "allegati"
    tenant_root = tmp_path / "tenants" / "tenant-a" / "email" / "allegati"
    global_root.mkdir(parents=True)
    tenant_root.mkdir(parents=True)

    roots = discover_email_attachment_roots(tmp_path)

    assert global_root.resolve() in roots
    assert tenant_root.resolve() in roots
