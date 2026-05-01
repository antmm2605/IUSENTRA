#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${1:-}"
IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
DATA_DIR="${IUSENTRA_DATA_DIR:-${IUSENTRA_HOME}/data}"
REPO_DIR="${REPO_DIR:-${IUSENTRA_HOME}/repo}"
ENV_FILE="${IUSENTRA_ENV_FILE:-${IUSENTRA_HOME}/.env.hetzner}"

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  echo "Uso: restore_data.sh /percorso/iusentra-data.tar.zst|tar.gz|zip" >&2
  exit 1
fi

mkdir -p "$DATA_DIR"

if [ -f "${ARCHIVE}.sha256" ]; then
  sha256sum -c "${ARCHIVE}.sha256"
fi

if [ -d "$REPO_DIR/.git" ]; then
  cd "$REPO_DIR"
  docker compose --env-file "$ENV_FILE" -f deploy/hetzner/docker-compose.hetzner.yml down
fi

case "$ARCHIVE" in
  *.tar.zst)
    tar --zstd -xpf "$ARCHIVE" -C "$DATA_DIR"
    ;;
  *.tar.gz|*.tgz)
    tar -xzpf "$ARCHIVE" -C "$DATA_DIR"
    ;;
  *.zip)
    if ! command -v unzip >/dev/null 2>&1; then
      apt-get update && apt-get install -y unzip
    fi
    unzip -o "$ARCHIVE" -d "$DATA_DIR"
    ;;
  *)
    echo "Formato archivio non supportato: $ARCHIVE" >&2
    exit 1
    ;;
esac

chmod -R u+rwX,go-rwx "$DATA_DIR"
echo "Restore completato in $DATA_DIR. Rilanciare deploy.sh."
