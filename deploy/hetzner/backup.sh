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

BACKUP_DISABLED_FLAG="${IUSENTRA_DISABLE_BACKUP_JOBS:-1}"
if [[ "${BACKUP_DISABLED_FLAG,,}" =~ ^(1|true|yes|on)$ ]]; then
  echo "Backup disattivato da IUSENTRA_DISABLE_BACKUP_JOBS=1."
  exit 0
fi

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
DATA_DIR="${IUSENTRA_DATA_DIR:-${IUSENTRA_HOME}/data}"
BACKUP_DIR="${IUSENTRA_BACKUP_DIR:-${IUSENTRA_HOME}/backups}"
RETENTION_DAYS="${IUSENTRA_BACKUP_RETENTION_DAYS:-${BACKUP_RETENTION_DAYS:-14}}"
RETENTION_COUNT="${IUSENTRA_BACKUP_RETENTION_COUNT:-${BACKUP_RETENTION_COUNT:-3}}"
RETENTION_MIN_COUNT="${IUSENTRA_BACKUP_RETENTION_MIN_COUNT:-${BACKUP_RETENTION_MIN_COUNT:-2}}"
RETENTION_MAX_GIB="${IUSENTRA_BACKUP_RETENTION_MAX_GIB:-${BACKUP_RETENTION_MAX_GIB:-8}}"
RETENTION_MAX_COUNT=3
ZSTD_LEVEL="${IUSENTRA_BACKUP_ZSTD_LEVEL:-${BACKUP_ZSTD_LEVEL:-6}}"
ZSTD_THREADS="${IUSENTRA_BACKUP_ZSTD_THREADS:-${BACKUP_ZSTD_THREADS:-2}}"
ZSTD_LONG_WINDOW="${IUSENTRA_BACKUP_ZSTD_LONG_WINDOW:-${BACKUP_ZSTD_LONG_WINDOW:-27}}"
BACKUP_NICE="${IUSENTRA_BACKUP_NICE:-${BACKUP_NICE:-19}}"
BACKUP_IONICE_CLASS="${IUSENTRA_BACKUP_IONICE_CLASS:-${BACKUP_IONICE_CLASS:-3}}"
BACKUP_REQUIRED_FREE_PERCENT="${IUSENTRA_BACKUP_REQUIRED_FREE_PERCENT:-${BACKUP_REQUIRED_FREE_PERCENT:-65}}"
BACKUP_MIN_FREE_GIB="${IUSENTRA_BACKUP_MIN_FREE_GIB:-${BACKUP_MIN_FREE_GIB:-4}}"
BACKUP_ALLOW_LOW_SPACE="${IUSENTRA_BACKUP_ALLOW_LOW_SPACE:-${BACKUP_ALLOW_LOW_SPACE:-0}}"
BACKUP_EXCLUDE_PATHS="${IUSENTRA_BACKUP_EXCLUDE_PATHS:-${BACKUP_EXCLUDE_PATHS:-./ollama}}"
MANDATORY_REGENERABLE_EXCLUDES=(
  "./ollama"
  "./ollama/*"
  "./intelligence/downloads/ollama"
  "./intelligence/downloads/ollama/*"
  "./tenants/*/intelligence/downloads/ollama"
  "./tenants/*/intelligence/downloads/ollama/*"
)
STAMP="$(date -u +%Y%m%d_%H%M%S)"
FINAL_OUT="${BACKUP_DIR}/iusentra-data-${STAMP}.tar.zst"
OUT="${FINAL_OUT}.tmp"
BACKUP_COMPLETED=0

mkdir -p "$BACKUP_DIR"

if ! [[ "$RETENTION_COUNT" =~ ^[0-9]+$ ]] || (( RETENTION_COUNT < 1 )); then
  RETENTION_COUNT=3
fi
if (( RETENTION_COUNT > RETENTION_MAX_COUNT )); then
  RETENTION_COUNT="$RETENTION_MAX_COUNT"
fi
if ! [[ "$RETENTION_MIN_COUNT" =~ ^[0-9]+$ ]] || (( RETENTION_MIN_COUNT < 1 )); then
  RETENTION_MIN_COUNT=1
fi
if (( RETENTION_MIN_COUNT > RETENTION_MAX_COUNT )); then
  RETENTION_MIN_COUNT="$RETENTION_MAX_COUNT"
fi
if (( RETENTION_MIN_COUNT > RETENTION_COUNT )); then
  RETENTION_MIN_COUNT="$RETENTION_COUNT"
fi

cleanup_incomplete_backup() {
  if [[ "$BACKUP_COMPLETED" != "1" ]]; then
    rm -f -- "$OUT" "$FINAL_OUT" "${OUT}.sha256" "${FINAL_OUT}.sha256"
  fi
}
trap cleanup_incomplete_backup EXIT

tar_exclude_args=()
tar_exclude_seen="|"
add_tar_exclude() {
  local exclude_path="$1"
  exclude_path="$(echo "$exclude_path" | xargs)"
  if [[ -n "$exclude_path" && "$tar_exclude_seen" != *"|${exclude_path}|"* ]]; then
    tar_exclude_args+=("--exclude=${exclude_path}")
    tar_exclude_seen+="${exclude_path}|"
  fi
}

if [[ -n "$BACKUP_EXCLUDE_PATHS" ]]; then
  IFS=',' read -r -a configured_excludes <<< "$BACKUP_EXCLUDE_PATHS"
  for exclude_path in "${configured_excludes[@]}"; do
    add_tar_exclude "$exclude_path"
  done
fi
for exclude_path in "${MANDATORY_REGENERABLE_EXCLUDES[@]}"; do
  add_tar_exclude "$exclude_path"
done

list_backup_archive() {
  case "$OUT" in
    *.tar.zst)
      if command -v unzstd >/dev/null 2>&1; then
        tar --use-compress-program=unzstd -tf "$OUT"
      else
        zstd -dc "$OUT" | tar -tf -
      fi
      ;;
    *.tar.gz)
      tar -tzf "$OUT"
      ;;
    *)
      tar -tf "$OUT"
      ;;
  esac
}

verify_no_ollama_in_backup() {
  local found
  found="$(list_backup_archive | grep -E '(^|/)ollama(/|$)' | head -20 || true)"
  if [[ -n "$found" ]]; then
    echo "Errore: il backup contiene dati Ollama rigenerabili. Correggere le esclusioni prima di conservarlo." >&2
    echo "$found" >&2
    return 1
  fi
}

backup_find_args=(
  "$BACKUP_DIR"
  -maxdepth 1
  -type f
  \( -name "iusentra-data-*.tar.zst" -o -name "iusentra-data-*.tar.gz" \)
)

prune_legacy_backup_items() {
  find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "auth-before-migration-*.tgz" -o -name "hetzner-pre-*.tar.gz" -o -name "hetzner-pre-*.tar.gz.sha256" \) \
    -delete
  find "$BACKUP_DIR" -maxdepth 1 -type d -name "tenant-email-quarantine-*" \
    -exec rm -rf -- {} +
}

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

validate_runtime_budget() {
  if ! [[ "$ZSTD_THREADS" =~ ^[0-9]+$ ]] || (( ZSTD_THREADS < 1 || ZSTD_THREADS > 4 )); then
    ZSTD_THREADS=2
  fi
  if ! [[ "$BACKUP_NICE" =~ ^-?[0-9]+$ ]] || (( BACKUP_NICE < -20 || BACKUP_NICE > 19 )); then
    BACKUP_NICE=19
  fi
  if ! [[ "$BACKUP_IONICE_CLASS" =~ ^[0-3]$ ]]; then
    BACKUP_IONICE_CLASS=3
  fi
  if ! [[ "$BACKUP_REQUIRED_FREE_PERCENT" =~ ^[0-9]+$ ]] || (( BACKUP_REQUIRED_FREE_PERCENT < 10 || BACKUP_REQUIRED_FREE_PERCENT > 100 )); then
    BACKUP_REQUIRED_FREE_PERCENT=65
  fi
  if ! [[ "$BACKUP_MIN_FREE_GIB" =~ ^[0-9]+$ ]] || (( BACKUP_MIN_FREE_GIB < 1 )); then
    BACKUP_MIN_FREE_GIB=4
  fi
}

low_priority_command() {
  local prefix=()
  if command -v ionice >/dev/null 2>&1; then
    prefix+=(ionice -c "$BACKUP_IONICE_CLASS")
  fi
  if command -v nice >/dev/null 2>&1; then
    prefix+=(nice -n "$BACKUP_NICE")
  fi
  "${prefix[@]}" "$@"
}

ensure_backup_free_space() {
  local data_bytes
  local free_bytes
  local required_bytes
  local min_free_bytes
  data_bytes="$(du -sb "$DATA_DIR" 2>/dev/null | awk '{print $1}' || echo 0)"
  free_bytes="$(df -PB1 "$BACKUP_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || echo 0)"
  if ! [[ "$data_bytes" =~ ^[0-9]+$ ]]; then
    data_bytes=0
  fi
  if ! [[ "$free_bytes" =~ ^[0-9]+$ ]]; then
    free_bytes=0
  fi
  min_free_bytes=$(( BACKUP_MIN_FREE_GIB * 1024 * 1024 * 1024 ))
  required_bytes=$(( (data_bytes * BACKUP_REQUIRED_FREE_PERCENT / 100) + min_free_bytes ))
  if (( required_bytes > 0 && free_bytes < required_bytes )); then
    echo "Errore: spazio libero insufficiente per backup senza saturare il server." >&2
    echo "Dati stimati: ${data_bytes} byte; libero: ${free_bytes} byte; richiesto: ${required_bytes} byte (${BACKUP_REQUIRED_FREE_PERCENT}% dati + ${BACKUP_MIN_FREE_GIB} GiB margine)." >&2
    echo "Eseguire prima retention/manutenzione governata oppure impostare IUSENTRA_BACKUP_ALLOW_LOW_SPACE=1 solo per recovery presidiata." >&2
    if [[ "$BACKUP_ALLOW_LOW_SPACE" =~ ^(1|true|yes|on)$ ]]; then
      echo "Attenzione: procedo nonostante spazio basso per override esplicito." >&2
      return 0
    fi
    return 2
  fi
}

run_tar_zstd_backup() {
  local pipeline_statuses
  local tar_status
  local zstd_status

  set +e
  low_priority_command tar "${tar_exclude_args[@]}" --warning=no-file-changed -cpf - -C "$DATA_DIR" . \
    | low_priority_command zstd -T"${ZSTD_THREADS}" "-${ZSTD_LEVEL}" "--long=${ZSTD_LONG_WINDOW}" -o "$OUT"
  pipeline_statuses=("${PIPESTATUS[@]}")
  tar_status="${pipeline_statuses[0]:-1}"
  zstd_status="${pipeline_statuses[1]:-1}"
  set -e

  if (( zstd_status != 0 )); then
    return "$zstd_status"
  fi
  if (( tar_status > 1 )); then
    return "$tar_status"
  fi
  if (( tar_status == 1 )); then
    echo "Attenzione: alcuni file sono cambiati durante il backup; archivio conservato con snapshot best-effort dei dati leggibili." >&2
  fi
}

run_tar_gzip_backup() {
  local tar_status

  set +e
  tar "${tar_exclude_args[@]}" --warning=no-file-changed -czpf "$OUT" -C "$DATA_DIR" .
  tar_status=$?
  set -e

  if (( tar_status > 1 )); then
    return "$tar_status"
  fi
  if (( tar_status == 1 )); then
    echo "Attenzione: alcuni file sono cambiati durante il backup; archivio conservato con snapshot best-effort dei dati leggibili." >&2
  fi
}

if command -v zstd >/dev/null 2>&1; then
  if ! [[ "$ZSTD_LEVEL" =~ ^[0-9]+$ ]] || (( ZSTD_LEVEL < 1 || ZSTD_LEVEL > 19 )); then
    ZSTD_LEVEL=6
  fi
  if ! [[ "$ZSTD_LONG_WINDOW" =~ ^[0-9]+$ ]] || (( ZSTD_LONG_WINDOW < 20 || ZSTD_LONG_WINDOW > 31 )); then
    ZSTD_LONG_WINDOW=27
  fi
  validate_runtime_budget
  prune_legacy_backup_items
  prune_by_total_size
  ensure_backup_free_space
  run_tar_zstd_backup
else
  FINAL_OUT="${BACKUP_DIR}/iusentra-data-${STAMP}.tar.gz"
  OUT="${FINAL_OUT}.tmp"
  prune_legacy_backup_items
  prune_by_total_size
  ensure_backup_free_space
  run_tar_gzip_backup
fi

mv -f -- "$OUT" "$FINAL_OUT"
OUT="$FINAL_OUT"
verify_no_ollama_in_backup
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
prune_legacy_backup_items

echo "Retention backup applicata: giorni=${RETENTION_DAYS}, copie=${RETENTION_COUNT}, minimo=${RETENTION_MIN_COUNT}, spazio_max_gib=${RETENTION_MAX_GIB}"
echo "Budget backup: zstd_level=${ZSTD_LEVEL}, threads=${ZSTD_THREADS}, nice=${BACKUP_NICE}, ionice_class=${BACKUP_IONICE_CLASS}"
if [[ -n "$BACKUP_EXCLUDE_PATHS" ]]; then
  echo "Esclusioni backup rigenerabili: ${BACKUP_EXCLUDE_PATHS}, ${MANDATORY_REGENERABLE_EXCLUDES[*]}"
fi
echo "$OUT"
BACKUP_COMPLETED=1
trap - EXIT
