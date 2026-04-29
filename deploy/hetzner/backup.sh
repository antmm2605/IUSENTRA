#!/usr/bin/env bash
set -euo pipefail

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
DATA_DIR="${IUSENTRA_DATA_DIR:-${IUSENTRA_HOME}/data}"
BACKUP_DIR="${IUSENTRA_BACKUP_DIR:-${IUSENTRA_HOME}/backups}"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/iusentra-data-${STAMP}.tar.zst"

mkdir -p "$BACKUP_DIR"

if command -v zstd >/dev/null 2>&1; then
  tar --zstd -cpf "$OUT" -C "$DATA_DIR" .
else
  OUT="${BACKUP_DIR}/iusentra-data-${STAMP}.tar.gz"
  tar -czpf "$OUT" -C "$DATA_DIR" .
fi

sha256sum "$OUT" > "${OUT}.sha256"
echo "$OUT"
