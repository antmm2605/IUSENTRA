#!/usr/bin/env bash
set -euo pipefail

env_file="/opt/iusentra/.env.hetzner"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --env-file)
      if [ "$#" -lt 2 ]; then
        echo "Valore mancante per --env-file" >&2
        exit 2
      fi
      env_file="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Uso: bash deploy/hetzner/verify_web_push.sh [--env-file /percorso/file]

Verifica la configurazione Web Push senza stampare la chiave privata.
EOF
      exit 0
      ;;
    *)
      echo "Opzione non riconosciuta: $1" >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
compose_file="$repo_root/deploy/hetzner/docker-compose.hetzner.yml"
python_bin="${PYTHON_BIN:-python3}"

if [ ! -f "$env_file" ]; then
  echo "Web Push non configurato:"
  echo "- file ambiente non trovato: $env_file"
  echo "Esegui: bash deploy/hetzner/configure_web_push.sh"
  exit 1
fi

host_status="$("$python_bin" - "$env_file" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
assignment = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
values: dict[str, str] = {}
for line in path.read_text(encoding="utf-8").splitlines():
    match = assignment.match(line)
    if not match:
        continue
    raw = match.group(2).strip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1]
    values[match.group(1)] = raw
enabled = values.get("IUSENTRA_WEB_PUSH_ENABLED", "").strip() == "1"
public_key = bool(values.get("IUSENTRA_VAPID_PUBLIC_KEY", "").strip())
private_key = bool(values.get("IUSENTRA_VAPID_PRIVATE_KEY", "").strip())
subject = values.get("IUSENTRA_VAPID_SUBJECT", "").strip()
missing = []
if not enabled:
    missing.append("IUSENTRA_WEB_PUSH_ENABLED e' 0")
if not public_key:
    missing.append("IUSENTRA_VAPID_PUBLIC_KEY mancante")
if not private_key:
    missing.append("IUSENTRA_VAPID_PRIVATE_KEY mancante")
if not subject:
    missing.append("IUSENTRA_VAPID_SUBJECT mancante")
print(json.dumps({
    "enabled": enabled,
    "public_key": public_key,
    "private_key": private_key,
    "subject": subject,
    "configured": enabled and public_key and private_key and bool(subject),
    "missing": missing,
}, ensure_ascii=False))
PY
)"

"$python_bin" - "$host_status" <<'PY'
from __future__ import annotations

import json
import sys

status = json.loads(sys.argv[1])
if status["configured"]:
    print("Web Push status:")
    print(f"- enabled: {str(status['enabled']).lower()}")
    print("- public key: present")
    print("- private key: present")
    print(f"- subject: {status['subject']}")
else:
    print("Web Push non configurato:")
    for item in status["missing"]:
        print(f"- {item}")
PY

backend_configured="unknown"
if command -v docker >/dev/null 2>&1 && [ -f "$compose_file" ]; then
  set +e
  backend_json="$(docker compose --env-file "$env_file" -f "$compose_file" exec -T app python -m pct.notifications.web_push_diagnostics --json 2>/dev/null)"
  backend_rc=$?
  set -e
  if [ "$backend_rc" -eq 0 ] || [ -n "$backend_json" ]; then
    backend_configured="$("$python_bin" - "$backend_json" <<'PY'
from __future__ import annotations

import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception:
    print("false")
else:
    print("true" if payload.get("configured") else "false")
PY
)"
  fi
fi

"$python_bin" - "$host_status" "$backend_configured" <<'PY'
from __future__ import annotations

import json
import sys

status = json.loads(sys.argv[1])
backend = sys.argv[2]
if status["configured"]:
    if backend == "unknown":
        print("- backend configured: non verificato")
    else:
        print(f"- backend configured: {backend}")
else:
    print("Esegui: bash deploy/hetzner/configure_web_push.sh")
PY

"$python_bin" - "$host_status" "$backend_configured" <<'PY'
from __future__ import annotations

import json
import sys

status = json.loads(sys.argv[1])
backend = sys.argv[2]
if not status["configured"]:
    raise SystemExit(1)
if backend == "false":
    raise SystemExit(1)
raise SystemExit(0)
PY
