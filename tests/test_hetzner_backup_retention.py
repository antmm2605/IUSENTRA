from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _bash_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if os.name != "nt":
        return value
    if len(value) >= 3 and value[1:3] == ":/":
        return f"/mnt/{value[0].lower()}{value[2:]}"
    pytest.skip("conversione path bash non disponibile")


def test_backup_script_applica_tetto_spazio_e_compressione_alta():
    script = (REPO_ROOT / "deploy" / "hetzner" / "backup.sh").read_text(encoding="utf-8")

    assert "IUSENTRA_BACKUP_RETENTION_MAX_GIB" in script
    assert "IUSENTRA_BACKUP_RETENTION_MIN_COUNT" in script
    assert "prune_by_total_size" in script
    assert "IUSENTRA_BACKUP_ZSTD_LEVEL" in script
    assert "IUSENTRA_BACKUP_EXCLUDE_PATHS" in script
    assert "BACKUP_EXCLUDE_PATHS:-./ollama" in script
    assert "MANDATORY_REGENERABLE_EXCLUDES" in script
    assert "./intelligence/downloads/ollama" in script
    assert "./tenants/*/intelligence/downloads/ollama" in script
    assert "verify_no_ollama_in_backup" in script
    assert "grep -E '(^|/)ollama(/|$)'" in script
    assert "cleanup_incomplete_backup" in script
    assert 'OUT="${FINAL_OUT}.tmp"' in script
    assert "mv -f -- \"$OUT\" \"$FINAL_OUT\"" in script
    assert "zstd -T0" in script
    assert "--long=" in script
    assert "source \"$ENV_FILE\"" in script
    assert "run_tar_zstd_backup" in script
    assert "PIPESTATUS[0]" in script
    assert "tar_status > 1" in script
    assert "tar_status == 1" in script
    assert "snapshot best-effort" in script


def test_env_hetzner_documenta_guardrail_backup():
    env_example = (REPO_ROOT / "deploy" / "hetzner" / "env.hetzner.example").read_text(encoding="utf-8")

    assert "IUSENTRA_BACKUP_DIR=/opt/iusentra/backups" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_DAYS=14" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_COUNT=3" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_MAX_GIB=8" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_MIN_COUNT=2" in env_example
    assert "IUSENTRA_BACKUP_ZSTD_LEVEL=19" in env_example
    assert "IUSENTRA_BACKUP_ZSTD_LONG_WINDOW=27" in env_example
    assert "IUSENTRA_BACKUP_EXCLUDE_PATHS=./ollama,./intelligence/downloads/ollama,./tenants/*/intelligence/downloads/ollama" in env_example


def test_backup_script_non_archivia_ollama_rigenerabile(tmp_path: Path):
    if not shutil.which("bash"):
        pytest.skip("bash non disponibile")

    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    (data_dir / "fascicoli").mkdir(parents=True)
    (data_dir / "fascicoli" / "reale.txt").write_text("dato da conservare", encoding="utf-8")
    for relative in (
        "ollama/models/blob.bin",
        "intelligence/downloads/ollama/installer.exe",
        "tenants/studio-a/intelligence/downloads/ollama/model.bin",
    ):
        path = data_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("rigenerabile", encoding="utf-8")

    script = REPO_ROOT / "deploy" / "hetzner" / "backup.sh"
    command = " ".join(
        [
            "IUSENTRA_BACKUP_LOAD_ENV=0",
            f"IUSENTRA_DATA_DIR={shlex.quote(_bash_path(data_dir))}",
            f"IUSENTRA_BACKUP_DIR={shlex.quote(_bash_path(backup_dir))}",
            "IUSENTRA_BACKUP_RETENTION_DAYS=0",
            "IUSENTRA_BACKUP_RETENTION_COUNT=0",
            "IUSENTRA_BACKUP_RETENTION_MAX_GIB=0",
            "IUSENTRA_BACKUP_ZSTD_LEVEL=1",
            f"bash {shlex.quote(_bash_path(script))}",
        ]
    )
    result = subprocess.run(["bash", "-lc", command], text=True, capture_output=True, check=True)
    archive = next(line.strip() for line in result.stdout.splitlines() if line.strip().endswith((".tar.zst", ".tar.gz")))
    if archive.endswith(".tar.zst"):
        list_cmd = f"tar --use-compress-program=unzstd -tf {archive!r}"
    else:
        list_cmd = f"tar -tzf {archive!r}"
    listing = subprocess.run(["bash", "-lc", list_cmd], text=True, capture_output=True, check=True).stdout

    assert "./fascicoli/reale.txt" in listing
    assert "ollama" not in listing.lower()
