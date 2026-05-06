#!/usr/bin/env bash
set -euo pipefail

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
ENV_FILE="${IUSENTRA_ENV_FILE:-${IUSENTRA_HOME}/.env.hetzner}"
if [[ "${IUSENTRA_BACKUP_LOAD_ENV:-1}" != "0" && -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
DATA_DIR="${IUSENTRA_DATA_DIR:-${IUSENTRA_HOME}/data}"
BACKUP_DIR="${IUSENTRA_BACKUP_DIR:-${IUSENTRA_HOME}/backups}"
RETENTION_DAYS="${IUSENTRA_BACKUP_RETENTION_DAYS:-${BACKUP_RETENTION_DAYS:-30}}"
RETENTION_COUNT="${IUSENTRA_BACKUP_RETENTION_COUNT:-${BACKUP_RETENTION_COUNT:-7}}"
RETENTION_MIN_COUNT="${IUSENTRA_BACKUP_RETENTION_MIN_COUNT:-${BACKUP_RETENTION_MIN_COUNT:-2}}"
RETENTION_MAX_GIB="${IUSENTRA_BACKUP_RETENTION_MAX_GIB:-${BACKUP_RETENTION_MAX_GIB:-24}}"
ZSTD_LEVEL="${IUSENTRA_BACKUP_ZSTD_LEVEL:-${BACKUP_ZSTD_LEVEL:-19}}"
ZSTD_LONG_WINDOW="${IUSENTRA_BACKUP_ZSTD_LONG_WINDOW:-${BACKUP_ZSTD_LONG_WINDOW:-27}}"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/iusentra-data-${STAMP}.tar.zst"

mkdir -p "$BACKUP_DIR"

backup_find_args=(
  "$BACKUP_DIR"
  -maxdepth 1
  -type f
  \( -name "iusentra-data-*.tar.zst" -o -name "iusentra-data-*.tar.gz" \)
)

prune_by_total_size() {
  if ! [[ "$RETENTION_MAX_GIB" =~ ^[0-9]+$ ]] || (( RETENTION_MAX_GIB <= 0 )); then
    return
  fi
  if ! [[ "$RETENTION_MIN_COUNT" =~ ^[0-9]+$ ]] || (( RETENTION_MIN_COUNT < 1 )); then
    RETENTION_MIN_COUNT=1
  fi

  local max_bytes=$(( RETENTION_MAX_GIB * 1024 * 1024 * 1024 ))
  local total_bytes=0
  local backup_count=0
  local line
  local size
  local old_backup
  local timestamp
  local rows=()

  mapfile -t rows < <(find "${backup_find_args[@]}" -printf "%T@\t%s\t%p\n" | sort -n)
  for line in "${rows[@]}"; do
    IFS=$'\t' read -r timestamp size old_backup <<< "$line"
    total_bytes=$(( total_bytes + size ))
    backup_count=$(( backup_count + 1 ))
  done

  for line in "${rows[@]}"; do
    if (( total_bytes <= max_bytes || backup_count <= RETENTION_MIN_COUNT )); then
      break
    fi
    IFS=$'\t' read -r timestamp size old_backup <<< "$line"
    rm -f -- "$old_backup" "${old_backup}.sha256"
    total_bytes=$(( total_bytes - size ))
    backup_count=$(( backup_count - 1 ))
  done

  if (( total_bytes > max_bytes )); then
    echo "Attenzione: backup sopra tetto (${total_bytes} byte > ${max_bytes} byte) perche' restano ${backup_count} copie minime."
  fi
}

if command -v zstd >/dev/null 2>&1; then
  if ! [[ "$ZSTD_LEVEL" =~ ^[0-9]+$ ]] || (( ZSTD_LEVEL < 1 || ZSTD_LEVEL > 19 )); then
    ZSTD_LEVEL=19
  fi
  if ! [[ "$ZSTD_LONG_WINDOW" =~ ^[0-9]+$ ]] || (( ZSTD_LONG_WINDOW < 20 || ZSTD_LONG_WINDOW > 31 )); then
    ZSTD_LONG_WINDOW=27
  fi
  tar -cpf - -C "$DATA_DIR" . | zstd -T0 "-${ZSTD_LEVEL}" "--long=${ZSTD_LONG_WINDOW}" -o "$OUT"
else
  OUT="${BACKUP_DIR}/iusentra-data-${STAMP}.tar.gz"
  tar -czpf "$OUT" -C "$DATA_DIR" .
fi

sha256sum "$OUT" > "${OUT}.sha256"
sha256sum -c "${OUT}.sha256"

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && (( RETENTION_DAYS > 0 )); then
  find "${backup_find_args[@]}" \
    -mtime +"$RETENTION_DAYS" -print | while IFS= read -r old_backup; do
      rm -f -- "$old_backup" "${old_backup}.sha256"
    done
fi

if [[ "$RETENTION_COUNT" =~ ^[0-9]+$ ]] && (( RETENTION_COUNT > 0 )); then
  find "${backup_find_args[@]}" \
    -printf "%T@ %p\n" \
    | sort -rn \
    | awk -v keep="$RETENTION_COUNT" 'NR > keep {sub(/^[^ ]+ /, ""); print}' \
    | while IFS= read -r old_backup; do
        rm -f -- "$old_backup" "${old_backup}.sha256"
      done
fi

prune_by_total_size

echo "Retention backup applicata: giorni=${RETENTION_DAYS}, copie=${RETENTION_COUNT}, minimo=${RETENTION_MIN_COUNT}, spazio_max_gib=${RETENTION_MAX_GIB}"
echo "$OUT"
