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


def test_backup_script_applica_tetto_spazio_e_budget_server():
    script = (REPO_ROOT / "deploy" / "hetzner" / "backup.sh").read_text(encoding="utf-8")

    assert "IUSENTRA_BACKUP_RETENTION_MAX_GIB" in script
    assert "IUSENTRA_BACKUP_RETENTION_MIN_COUNT" in script
    assert "RETENTION_MAX_COUNT=3" in script
    assert "prune_by_total_size" in script
    assert "IUSENTRA_BACKUP_ZSTD_LEVEL" in script
    assert "IUSENTRA_BACKUP_ZSTD_THREADS" in script
    assert "IUSENTRA_BACKUP_NICE" in script
    assert "IUSENTRA_BACKUP_IONICE_CLASS" in script
    assert "IUSENTRA_BACKUP_REQUIRED_FREE_PERCENT" in script
    assert "IUSENTRA_BACKUP_MIN_FREE_GIB" in script
    assert "ensure_backup_free_space" in script
    assert "low_priority_command tar" in script
    assert "low_priority_command zstd" in script
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
    assert "zstd -T0" not in script
    assert 'zstd -T"${ZSTD_THREADS}"' in script
    assert 'ZSTD_LEVEL="${IUSENTRA_BACKUP_ZSTD_LEVEL:-${BACKUP_ZSTD_LEVEL:-6}}"' in script
    assert "--long=" in script
    assert "source \"$ENV_FILE\"" in script
    assert "run_tar_zstd_backup" in script
    assert 'pipeline_statuses=("${PIPESTATUS[@]}")' in script
    assert 'tar_status="${pipeline_statuses[0]:-1}"' in script
    assert 'zstd_status="${pipeline_statuses[1]:-1}"' in script
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
    assert "IUSENTRA_BACKUP_ZSTD_LEVEL=6" in env_example
    assert "IUSENTRA_BACKUP_ZSTD_THREADS=2" in env_example
    assert "IUSENTRA_BACKUP_NICE=19" in env_example
    assert "IUSENTRA_BACKUP_IONICE_CLASS=3" in env_example
    assert "IUSENTRA_BACKUP_REQUIRED_FREE_PERCENT=65" in env_example
    assert "IUSENTRA_BACKUP_MIN_FREE_GIB=4" in env_example
    assert "IUSENTRA_BACKUP_ZSTD_LONG_WINDOW=27" in env_example
    assert "IUSENTRA_BACKUP_EXCLUDE_PATHS=./ollama,./intelligence/downloads/ollama,./tenants/*/intelligence/downloads/ollama" in env_example


def test_deploy_pulisce_container_compose_temporanei_senza_toccare_dati():
    deploy_script = (REPO_ROOT / "deploy" / "hetzner" / "deploy.sh").read_text(encoding="utf-8")
    cleanup_script = (REPO_ROOT / "deploy" / "hetzner" / "cleanup_compose_conflicts.sh").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy-hetzner.yml").read_text(encoding="utf-8")

    assert "cleanup_compose_conflict_containers" in deploy_script
    assert "compose_up_with_cleanup" in deploy_script
    assert "pulisco container temporanei e riprovo una volta" in deploy_script
    assert "cleanup_compose_conflicts.sh" in workflow
    assert "IUSENTRA_CLEANUP_RUNNING_TEMP=1" in workflow
    assert "docker rm -f \"$container_id\"" in cleanup_script
    assert "docker ps -a --format" in cleanup_script
    assert "^[0-9a-f]{8,64}_${PROJECT}-(app|scheduler-worker|ocr-worker|caddy|audit-worm-init)-[0-9]+$" in cleanup_script
    assert "audit-postgres" not in cleanup_script
    assert "volume" not in cleanup_script.lower().replace("volumi", "")


def test_cleanup_compose_conflicts_rimuove_solo_hashati_ammessi(tmp_path: Path):
    if not shutil.which("bash"):
        pytest.skip("bash non disponibile")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "docker-rm.log"
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "ps" ]]; then
  printf 'keep1\\tiusentra-app-1\\trunning\\n'
  printf 'temp1\\t17d5ff216ae5_iusentra-app-1\\texited\\n'
  printf 'temp2\\t9abc12345678_iusentra-scheduler-worker-1\\tcreated\\n'
  printf 'unsafe\\tdf82231833bc_iusentra-audit-postgres-1\\texited\\n'
  exit 0
fi
if [[ "${1:-}" == "rm" && "${2:-}" == "-f" ]]; then
  printf '%s\\n' "$3" >> "${DOCKER_RM_LOG}"
  exit 0
fi
echo "unexpected docker call: $*" >&2
exit 64
""",
        encoding="utf-8",
        newline="\n",
    )
    fake_docker.chmod(0o755)
    subprocess.run(["bash", "-lc", f"chmod +x {shlex.quote(_bash_path(fake_docker))}"], check=True)

    script = REPO_ROOT / "deploy" / "hetzner" / "cleanup_compose_conflicts.sh"
    command = " ".join(
        [
            f"PATH={shlex.quote(f'{_bash_path(bin_dir)}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')}",
            f"DOCKER_RM_LOG={shlex.quote(_bash_path(log_path))}",
            "IUSENTRA_COMPOSE_PROJECT=iusentra",
            "IUSENTRA_CLEANUP_RUNNING_TEMP=0",
            f"bash {shlex.quote(_bash_path(script))}",
        ]
    )
    result = subprocess.run(["bash", "-lc", command], text=True, capture_output=True, check=True)
    removed = log_path.read_text(encoding="utf-8").splitlines()

    assert removed == ["temp1", "temp2"]
    assert "keep1" not in result.stdout
    assert "audit-postgres" not in result.stdout


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
