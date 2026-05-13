#!/usr/bin/env bash
# Configura audit probatorio reale su Hetzner: Postgres indice, MinIO Object Lock
# e firma JWS con chiave custodita in /opt/iusentra/data, fuori dal repository.
set -euo pipefail

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
ENV_FILE="${IUSENTRA_ENV_FILE:-${IUSENTRA_HOME}/.env.hetzner}"
DATA_DIR="${IUSENTRA_DATA_DIR:-${IUSENTRA_HOME}/data}"
BUCKET="${AUDIT_WORM_BUCKET:-iusentra-audit-worm}"
KID="${AUDIT_SIGNING_KID:-iusentra-hetzner-audit-jws}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl non disponibile: installarlo prima di configurare la firma audit." >&2
  exit 1
fi

mkdir -p "$(dirname "$ENV_FILE")" "$DATA_DIR/audit/keys"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE" || true

set_env_value() {
  local key="$1"
  local value="$2"
  python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8", errors="ignore").splitlines() if path.exists() else []
prefix = f"{key}="
updated = False
out = []
for line in lines:
    if line.startswith(prefix):
        out.append(f"{key}={value}")
        updated = True
    else:
        out.append(line)
if not updated:
    out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

get_env_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d= -f2- || true
}

secret_hex() {
  openssl rand -hex "$1"
}

add_compose_profile() {
  local profile="$1"
  local current
  current="$(get_env_value COMPOSE_PROFILES)"
  python3 - "$current" "$profile" <<'PY'
import sys
current = sys.argv[1]
profile = sys.argv[2]
items = [item.strip() for item in current.split(",") if item.strip()]
if profile not in items:
    items.append(profile)
print(",".join(items))
PY
}

PRIVATE_KEY="$DATA_DIR/audit/keys/audit_jws_private.pem"
PUBLIC_KEY="$DATA_DIR/audit/keys/audit_jws_public.pem"
if [ ! -f "$PRIVATE_KEY" ]; then
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$PRIVATE_KEY" >/dev/null 2>&1
  chmod 600 "$PRIVATE_KEY"
fi
if [ ! -f "$PUBLIC_KEY" ]; then
  openssl pkey -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY" >/dev/null 2>&1
  chmod 644 "$PUBLIC_KEY"
fi
FINGERPRINT="$(openssl pkey -pubin -in "$PUBLIC_KEY" -outform DER 2>/dev/null | openssl dgst -sha256 -r | awk '{print $1}')"

AUDIT_WORM_ACCESS_KEY_VALUE="$(get_env_value AUDIT_WORM_ACCESS_KEY)"
[ -n "$AUDIT_WORM_ACCESS_KEY_VALUE" ] || AUDIT_WORM_ACCESS_KEY_VALUE="iusentraaudit$(secret_hex 8)"
AUDIT_WORM_SECRET_KEY_VALUE="$(get_env_value AUDIT_WORM_SECRET_KEY)"
[ -n "$AUDIT_WORM_SECRET_KEY_VALUE" ] || AUDIT_WORM_SECRET_KEY_VALUE="$(secret_hex 32)"
AUDIT_POSTGRES_PASSWORD_VALUE="$(get_env_value AUDIT_POSTGRES_PASSWORD)"
[ -n "$AUDIT_POSTGRES_PASSWORD_VALUE" ] || AUDIT_POSTGRES_PASSWORD_VALUE="$(secret_hex 32)"

set_env_value COMPOSE_PROFILES "$(add_compose_profile audit-worm)"
set_env_value AUDIT_ENABLED true
set_env_value AUDIT_ENV production
set_env_value AUDIT_REQUIRE_WORM true
set_env_value AUDIT_REQUIRE_SIGNATURE true
set_env_value AUDIT_REQUIRE_TSA_FOR_SNAPSHOT false
set_env_value AUDIT_RETENTION_YEARS 10
set_env_value AUDIT_CANONICALIZATION RFC8785-JCS
set_env_value AUDIT_HASH_ALG SHA-256
set_env_value AUDIT_POSTGRES_DB iusentra_audit
set_env_value AUDIT_POSTGRES_USER iusentra_audit
set_env_value AUDIT_POSTGRES_PASSWORD "$AUDIT_POSTGRES_PASSWORD_VALUE"
set_env_value AUDIT_DATABASE_URL "postgresql://iusentra_audit:${AUDIT_POSTGRES_PASSWORD_VALUE}@audit-postgres:5432/iusentra_audit"
set_env_value AUDIT_WORM_ENDPOINT_URL "http://audit-worm:9000"
set_env_value AUDIT_WORM_REGION eu-central-1
set_env_value AUDIT_WORM_BUCKET "$BUCKET"
set_env_value AUDIT_WORM_ACCESS_KEY "$AUDIT_WORM_ACCESS_KEY_VALUE"
set_env_value AUDIT_WORM_SECRET_KEY "$AUDIT_WORM_SECRET_KEY_VALUE"
set_env_value AUDIT_WORM_RETENTION_YEARS 10
set_env_value AUDIT_WORM_MODE COMPLIANCE
set_env_value AUDIT_WORM_REQUIRE_OBJECT_LOCK true
set_env_value AUDIT_SIGNING_MODE JWS
set_env_value AUDIT_SIGNING_KID "$KID"
set_env_value AUDIT_SIGNING_ALG RS256
set_env_value AUDIT_SIGNING_KEY_SOURCE KEY_VAULT_FILE
set_env_value AUDIT_SIGNING_KEY_SEALED true
set_env_value AUDIT_SIGNING_PRIVATE_KEY_FILE /data/audit/keys/audit_jws_private.pem
set_env_value AUDIT_SIGNING_PUBLIC_KEY_FILE /data/audit/keys/audit_jws_public.pem
set_env_value AUDIT_SIGNING_CERT_FINGERPRINT "$FINGERPRINT"

echo "Audit WORM/firma configurati in $ENV_FILE."
echo "Chiave privata audit fuori repository: $PRIVATE_KEY"
echo "Prossimo passo: cd ${IUSENTRA_HOME}/repo && bash deploy/hetzner/deploy.sh"
