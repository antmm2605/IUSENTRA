"""Il deploy non adotta scadenze finché esiste un produttore attivo."""
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize('ready,running,failure,expected', [(0, '', '', 0), (2, '', '', 0),
                                                         (2, 'active', '', 1), (2, '', 'migration', 22)])
def test_drain_e_adozione_sono_bloccanti(tmp_path, ready, running, failure, expected):
    script = (Path(__file__).parents[1] / 'deploy/hetzner/deploy.sh').read_text(encoding='utf-8')
    function = script[script.index('prepare_scadenziario_before_start() {'):script.index('\nprepare_tracking_proposals_before_start()')]
    stub = r'''
docker() {
  printf '%s\n' "$*" >> "$TRACE"
  case "$1" in
    ps) [ -z "$RUNNING" ] || printf 'active\n' ;;
    compose)
      case " $* " in
        *" --check "*) return "$READY" ;;
        *" --writers-drained "*) [ "$FAILURE" != migration ] || return 22 ;;
      esac ;;
  esac
  return 0
}
ENV_FILE=/controlled/environment
COMPOSE_FILE=deploy/hetzner/docker-compose.hetzner.yml
PROFILE_ARGS=()
'''
    trace = tmp_path / 'trace.txt'
    bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else 'bash'
    result = subprocess.run([bash, '-euo', 'pipefail', '-c', stub + function + '\nprepare_scadenziario_before_start'],
                            capture_output=True, text=True,
                            env={**os.environ, 'TRACE': trace.as_posix(), 'READY': str(ready),
                                 'RUNNING': running, 'FAILURE': failure})
    assert result.returncode == expected, result.stderr
    lines = trace.read_text(encoding='utf-8').splitlines()
    if ready == 0:
        assert len(lines) == 1
    else:
        assert 'stop app scheduler-worker ocr-worker' in lines[1]
        migrations = [line for line in lines if '--writers-drained' in line]
        assert bool(migrations) == (not running)
    assert script.count('  prepare_scadenziario_before_start\n  prepare_client_case_index_before_start') == 2
