from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_backup_script_applica_tetto_spazio_e_compressione_alta():
    script = (REPO_ROOT / "deploy" / "hetzner" / "backup.sh").read_text(encoding="utf-8")

    assert "IUSENTRA_BACKUP_RETENTION_MAX_GIB" in script
    assert "IUSENTRA_BACKUP_RETENTION_MIN_COUNT" in script
    assert "prune_by_total_size" in script
    assert "IUSENTRA_BACKUP_ZSTD_LEVEL" in script
    assert "IUSENTRA_BACKUP_EXCLUDE_PATHS" in script
    assert "BACKUP_EXCLUDE_PATHS:-./ollama" in script
    assert "zstd -T0" in script
    assert "--long=" in script
    assert "source \"$ENV_FILE\"" in script


def test_env_hetzner_documenta_guardrail_backup():
    env_example = (REPO_ROOT / "deploy" / "hetzner" / "env.hetzner.example").read_text(encoding="utf-8")

    assert "IUSENTRA_BACKUP_DIR=/opt/iusentra/backups" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_DAYS=14" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_COUNT=3" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_MAX_GIB=8" in env_example
    assert "IUSENTRA_BACKUP_RETENTION_MIN_COUNT=2" in env_example
    assert "IUSENTRA_BACKUP_ZSTD_LEVEL=19" in env_example
    assert "IUSENTRA_BACKUP_ZSTD_LONG_WINDOW=27" in env_example
    assert "IUSENTRA_BACKUP_EXCLUDE_PATHS=./ollama" in env_example
