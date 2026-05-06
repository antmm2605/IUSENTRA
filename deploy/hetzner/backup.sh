#!/usr/bin/env bash
set -euo pipefail

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
DATA_DIR="${IUSENTRA_DATA_DIR:-${IUSENTRA_HOME}/data}"
BACKUP_DIR="${IUSENTRA_BACKUP_DIR:-${IUSENTRA_HOME}/backups}"
RETENTION_DAYS="${IUSENTRA_BACKUP_RETENTION_DAYS:-${BACKUP_RETENTION_DAYS:-30}}"
RETENTION_COUNT="${IUSENTRA_BACKUP_RETENTION_COUNT:-${BACKUP_RETENTION_COUNT:-7}}"
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
sha256sum -c "${OUT}.sha256"

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && (( RETENTION_DAYS > 0 )); then
  find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "iusentra-data-*.tar.zst" -o -name "iusentra-data-*.tar.gz" \) \
    -mtime +"$RETENTION_DAYS" -print | while IFS= read -r old_backup; do
      rm -f -- "$old_backup" "${old_backup}.sha256"
    done
fi

if [[ "$RETENTION_COUNT" =~ ^[0-9]+$ ]] && (( RETENTION_COUNT > 0 )); then
  find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "iusentra-data-*.tar.zst" -o -name "iusentra-data-*.tar.gz" \) \
    -printf "%T@ %p\n" \
    | sort -rn \
    | awk -v keep="$RETENTION_COUNT" 'NR > keep {sub(/^[^ ]+ /, ""); print}' \
    | while IFS= read -r old_backup; do
        rm -f -- "$old_backup" "${old_backup}.sha256"
      done
fi

echo "Retention backup applicata: giorni=${RETENTION_DAYS}, copie=${RETENTION_COUNT}"
echo "$OUT"
