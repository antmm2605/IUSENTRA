#!/usr/bin/env bash
set -euo pipefail

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
REPO_DIR="${REPO_DIR:-${IUSENTRA_HOME}/repo}"
REPO_URL="${REPO_URL:-https://github.com/antmm2605/IUSENTRA.git}"
BRANCH="${BRANCH:-Codex/legal-electronic-filing-kIxcV}"
ENV_FILE="${IUSENTRA_ENV_FILE:-${IUSENTRA_HOME}/.env.hetzner}"

if [ ! -f "$ENV_FILE" ]; then
  echo "File ambiente mancante: $ENV_FILE" >&2
  echo "Copia deploy/hetzner/env.hetzner.example in $ENV_FILE e compila dominio e secrets." >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${IUSENTRA_DOMAIN:?Impostare IUSENTRA_DOMAIN in $ENV_FILE}"
: "${ACME_EMAIL:?Impostare ACME_EMAIL in $ENV_FILE}"
: "${PCT_SECRET_KEY:?Impostare PCT_SECRET_KEY in $ENV_FILE}"

mkdir -p "$IUSENTRA_HOME/data" "$IUSENTRA_HOME/backups" "$IUSENTRA_HOME/caddy_data" "$IUSENTRA_HOME/caddy_config"

if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
else
  git -C "$REPO_DIR" fetch origin "$BRANCH"
  git -C "$REPO_DIR" checkout "$BRANCH"
  git -C "$REPO_DIR" reset --hard "origin/$BRANCH"
fi

cd "$REPO_DIR"

docker compose \
  --env-file "$ENV_FILE" \
  -f deploy/hetzner/docker-compose.hetzner.yml \
  up -d --build --remove-orphans

docker compose \
  --env-file "$ENV_FILE" \
  -f deploy/hetzner/docker-compose.hetzner.yml \
  ps

echo "Deploy completato. Health: https://${IUSENTRA_DOMAIN}/api/pronto"
