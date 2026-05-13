#!/usr/bin/env bash
set -euo pipefail

env_file="/opt/iusentra/.env.hetzner"
force=0
print_secrets=0

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
    --force)
      force=1
      shift
      ;;
    --print-secrets)
      print_secrets=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Uso: bash deploy/hetzner/configure_web_push.sh [--env-file /percorso/file] [--force] [--print-secrets]

Configura Web Push in /opt/iusentra/.env.hetzner senza stampare la chiave privata nei log normali.
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
example_file="$repo_root/deploy/hetzner/env.hetzner.example"
python_bin="${PYTHON_BIN:-python3}"

mkdir -p "$(dirname "$env_file")"
if [ ! -f "$env_file" ]; then
  if [ -f "$example_file" ]; then
    cp "$example_file" "$env_file"
    echo "Creato $env_file dal template Hetzner."
  else
    : > "$env_file"
    echo "Creato $env_file vuoto."
  fi
fi

"$python_bin" - "$env_file" "$force" "$print_secrets" "$repo_root" <<'PY'
from __future__ import annotations

import os
import re
import sys
import importlib.util
from pathlib import Path

env_path = Path(sys.argv[1])
force = sys.argv[2] == "1"
print_secrets = sys.argv[3] == "1"
repo_root = Path(sys.argv[4])

module_path = repo_root / "pct" / "notifications" / "generate_vapid.py"
spec = importlib.util.spec_from_file_location("iusentra_generate_vapid", module_path)
if spec is None or spec.loader is None:
    raise RuntimeError("Modulo generazione VAPID non disponibile.")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
DEFAULT_VAPID_SUBJECT = module.DEFAULT_VAPID_SUBJECT
generate_vapid_key_pair = module.generate_vapid_key_pair

ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse_env(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        match = ASSIGNMENT.match(line)
        if not match:
            continue
        raw = match.group(2).strip()
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
        values[match.group(1)] = raw
    return values


def normalize_subject(values: dict[str, str]) -> str:
    current = values.get("IUSENTRA_VAPID_SUBJECT", "").strip()
    if current:
        return current
    acme_email = values.get("ACME_EMAIL", "").strip()
    if acme_email:
        return acme_email if acme_email.startswith("mailto:") else f"mailto:{acme_email}"
    return DEFAULT_VAPID_SUBJECT


def write_env(lines: list[str], updates: dict[str, str]) -> None:
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = ASSIGNMENT.match(line)
        if not match or match.group(1) not in updates:
            output.append(line.rstrip("\n"))
            continue
        key = match.group(1)
        if key in seen:
            continue
        output.append(f"{key}={updates[key]}")
        seen.add(key)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.chmod(env_path, 0o600)


lines = env_path.read_text(encoding="utf-8").splitlines()
values = parse_env(lines)
subject = normalize_subject(values)
public_key = values.get("IUSENTRA_VAPID_PUBLIC_KEY", "").strip()
private_key = values.get("IUSENTRA_VAPID_PRIVATE_KEY", "").strip()
generated = force or not public_key or not private_key
if generated:
    pair = generate_vapid_key_pair()
    public_key = pair.public_key
    private_key = pair.private_key

updates = {
    "IUSENTRA_WEB_PUSH_ENABLED": "1",
    "IUSENTRA_VAPID_PUBLIC_KEY": public_key,
    "IUSENTRA_VAPID_PRIVATE_KEY": private_key,
    "IUSENTRA_VAPID_SUBJECT": subject,
}
write_env(lines, updates)

print("Web Push abilitato")
print("Public key presente")
print("Private key presente")
print("Subject configurato")
print("Chiavi VAPID rigenerate" if generated else "Chiavi VAPID gia' presenti")
if print_secrets:
    for key, value in updates.items():
        print(f"{key}={value}")
else:
    print("Private key non stampata. Usare --print-secrets solo per debug manuale.")
print("Riavviare/deployare IUSENTRA")
PY

chmod 600 "$env_file" || true
echo "Configurazione aggiornata senza creare backup."
