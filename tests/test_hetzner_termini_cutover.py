"""Guardrail del drain prima dell'adozione; non sostituisce il deploy reale."""
import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).parents[1] / "deploy/hetzner/deploy.sh"
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "bash"


def _run(tmp_path, *, enabled="1", running="false", failure=""):
    source = SCRIPT.read_text(encoding="utf-8")
    function = source[source.index("adopt_termini_before_start() {"):source.index("\nCORE_BOOT_SERVICES=")]
    trace = tmp_path / "trace.txt"
    stub = r'''
docker() {
  printf '%s\n' "$*" >> "$CUTOVER_TRACE"
  case "$1" in
    ps) printf 'controlled-container\n' ;;
    inspect) printf '%s\n' "$CUTOVER_RUNNING" ;;
    compose)
      case " $* " in
        *" stop "*) [ "$CUTOVER_FAILURE" != stop ] || return 21 ;;
        *" run "*) [ "$CUTOVER_FAILURE" != migration ] || return 22 ;;
      esac ;;
  esac
}
ENV_FILE=/controlled/environment
COMPOSE_FILE=deploy/hetzner/docker-compose.hetzner.yml
PROFILE_ARGS=()
'''
    result = subprocess.run([BASH, "-euo", "pipefail", "-c", stub + function +
                             '\nadopt_termini_before_start\nprintf "release-start\\n" >> "$CUTOVER_TRACE"\n'],
                            capture_output=True, text=True,
                            env={**os.environ, "CUTOVER_TRACE": trace.as_posix(),
                                 "CUTOVER_RUNNING": running, "CUTOVER_FAILURE": failure,
                                 "IUSENTRA_DEPLOY_ADOPT_TERMINI": enabled})
    return result, trace.read_text(encoding="utf-8").splitlines()


def test_existing_deploy_does_not_adopt_without_explicit_activation(tmp_path):
    result, trace = _run(tmp_path, enabled="0")
    assert result.returncode == 0
    assert trace == ["release-start"]


def test_adoption_runs_only_after_all_producers_are_stopped(tmp_path):
    result, trace = _run(tmp_path)
    assert result.returncode == 0
    assert "stop app scheduler-worker ocr-worker" in trace[0]
    migration = next(i for i, line in enumerate(trace) if " run " in line)
    assert sum(line.startswith("inspect ") for line in trace[:migration]) == 3
    assert "--no-deps --rm --entrypoint python app -m scripts.migra_termini_sql --tenant all" in trace[migration]
    assert "--apply --writers-drained --initialize-missing" in trace[migration]
    assert trace[-1] == "release-start"


@pytest.mark.parametrize("running,failure,code", [("true", "", 1), ("false", "stop", 21), ("false", "migration", 22)])
def test_failed_drain_or_adoption_never_starts_release(tmp_path, running, failure, code):
    result, trace = _run(tmp_path, running=running, failure=failure)
    assert result.returncode == code
    assert "release-start" not in trace
    if running == "true" or failure == "stop":
        assert not any(" run " in line for line in trace)
