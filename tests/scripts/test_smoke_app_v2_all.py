from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.smoke_app_v2_all import _suite_names

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "scripts" / "smoke_app_v2_all.py"


def _run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("IUSENTRA_"):
            env.pop(key)
    return subprocess.run(
        [sys.executable, str(SMOKE), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def test_subset_aliases_restano_compatibili() -> None:
    assert _suite_names("security") == ("auth",)
    assert _suite_names("contracts") == ("api",)
    assert _suite_names("post-deploy")[0] == "health"


def test_inventory_json_output_non_richiede_credenziali(tmp_path: Path) -> None:
    output = tmp_path / "smoke-report.json"
    result = _run("--subset", "inventory", "--json-output", str(output))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Smoke App V2 fase 10 completato" in result.stdout
    assert "Smoke App V2 fase 13 completato" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["pass"] >= 3
    assert payload["summary"]["fail"] == 0
    assert payload["checks"]


def test_require_credentials_fallisce_se_mancano_env() -> None:
    result = _run("--suite", "auth", "--require-credentials")

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "Credenziali richieste mancanti" in output
    assert "IUSENTRA_ADMIN_PASSWORD" in output
