#!/usr/bin/env bash
# deploy.sh — sincronizza branch, ricrea servizi, imposta cron backup.
# Eseguire come root in /opt/iusentra/repo o da qualsiasi path tramite REPO_DIR.
set -euo pipefail

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
REPO_DIR="${REPO_DIR:-${IUSENTRA_HOME}/repo}"
REPO_URL="${REPO_URL:-https://github.com/antmm2605/IUSENTRA.git}"
BRANCH="${BRANCH:-Codex/legal-electronic-filing-kIxcV}"
ENV_FILE="${IUSENTRA_ENV_FILE:-${IUSENTRA_HOME}/.env.hetzner}"
COMPOSE_FILE="deploy/hetzner/docker-compose.hetzner.yml"

# ---------------------------------------------------------------------------
# 1. Verifica file ambiente
# ---------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  echo "File ambiente mancante: $ENV_FILE" >&2
  echo "Copia deploy/hetzner/env.hetzner.example in $ENV_FILE e compila dominio e secrets." >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

: "${IUSENTRA_DOMAIN:?Impostare IUSENTRA_DOMAIN in $ENV_FILE}"
: "${ACME_EMAIL:?Impostare ACME_EMAIL in $ENV_FILE}"
: "${PCT_SECRET_KEY:?Impostare PCT_SECRET_KEY in $ENV_FILE}"
: "${SECRET_KEY:?Impostare SECRET_KEY in $ENV_FILE}"
: "${FERNET_PRIMARY_KEY:?Impostare FERNET_PRIMARY_KEY in $ENV_FILE}"
: "${AUDIT_HMAC_KEY:?Impostare AUDIT_HMAC_KEY in $ENV_FILE}"

# ---------------------------------------------------------------------------
# 2. Directory runtime
# ---------------------------------------------------------------------------
mkdir -p \
  "${IUSENTRA_DATA_DIR:-$IUSENTRA_HOME/data}" \
  "${IUSENTRA_BACKUP_DIR:-$IUSENTRA_HOME/backups}" \
  "${IUSENTRA_CADDY_DATA_DIR:-$IUSENTRA_HOME/caddy_data}" \
  "${IUSENTRA_CADDY_CONFIG_DIR:-$IUSENTRA_HOME/caddy_config}" \
  "$IUSENTRA_HOME/import" \
  /var/log/iusentra
chmod 750 \
  "${IUSENTRA_DATA_DIR:-$IUSENTRA_HOME/data}" \
  "${IUSENTRA_BACKUP_DIR:-$IUSENTRA_HOME/backups}" \
  "$IUSENTRA_HOME/import" || true

# ---------------------------------------------------------------------------
# 3. Sincronizza repository
# ---------------------------------------------------------------------------
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
else
  git -C "$REPO_DIR" fetch origin "$BRANCH"
  git -C "$REPO_DIR" checkout "$BRANCH"
  git -C "$REPO_DIR" reset --hard "origin/$BRANCH"
fi

DEPLOYED_COMMIT="$(git -C "$REPO_DIR" rev-parse --short HEAD)"
echo "Branch: $BRANCH — commit: $DEPLOYED_COMMIT"

cd "$REPO_DIR"

# ---------------------------------------------------------------------------
# 4. Profilo Docker Compose
# ---------------------------------------------------------------------------
# COMPOSE_PROFILES può essere impostato in .env.hetzner.
# Valore consigliato: "ai" per avviare il sidecar Ollama.
# Lasciare vuoto per disabilitare Ollama (PCT_LOCAL_AI_ENABLED=0).
PROFILES="${COMPOSE_PROFILES:-}"
PROFILE_ARGS=()
if [ -n "$PROFILES" ]; then
  IFS=',' read -r -a profile_list <<< "$PROFILES"
  for p in "${profile_list[@]}"; do
    p="$(echo "$p" | xargs)"
    [ -n "$p" ] && PROFILE_ARGS+=("--profile" "$p")
  done
fi

profile_enabled() {
  local wanted="$1"
  local p
  IFS=',' read -r -a profile_check_list <<< "${PROFILES:-}"
  for p in "${profile_check_list[@]}"; do
    p="$(echo "$p" | xargs)"
    [ "$p" = "$wanted" ] && return 0
  done
  return 1
}

wait_for_compose_services() {
  local timeout="${IUSENTRA_DEPLOY_HEALTH_TIMEOUT:-180}"
  if ! [[ "$timeout" =~ ^[0-9]+$ ]] || (( timeout < 30 )); then
    timeout=180
  fi

  local deadline=$((SECONDS + timeout))
  local container_ids=()
  local container_id
  local name
  local running
  local health
  local pending
  local status_lines=()
  local services=("$@")

  while true; do
    pending=0
    status_lines=()
    mapfile -t container_ids < <(docker compose \
      --env-file "$ENV_FILE" \
      -f "$COMPOSE_FILE" \
      "${PROFILE_ARGS[@]}" \
      ps -q "${services[@]}")

    if (( ${#container_ids[@]} == 0 )); then
      pending=1
      status_lines+=("nessun container rilevato")
    fi

    for container_id in "${container_ids[@]}"; do
      name="$(docker inspect --format '{{.Name}}' "$container_id" 2>/dev/null | sed 's#^/##' || true)"
      running="$(docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null || echo false)"
      health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" 2>/dev/null || echo unknown)"
      status_lines+=("${name:-$container_id}: running=${running}, health=${health}")

      if [[ "$running" != "true" ]]; then
        pending=1
      elif [[ "$health" == "starting" || "$health" == "unhealthy" || "$health" == "unknown" ]]; then
        pending=1
      fi
    done

    if (( pending == 0 )); then
      return 0
    fi

    if (( SECONDS >= deadline )); then
      printf 'Timeout health container dopo %ss:\n' "$timeout" >&2
      printf ' - %s\n' "${status_lines[@]}" >&2
      return 1
    fi

    sleep 5
  done
}

# ---------------------------------------------------------------------------
# 5. Build e avvio servizi
# ---------------------------------------------------------------------------
CORE_BOOT_SERVICES=(redis)
CORE_HEALTH_SERVICES=(redis app)
if profile_enabled audit-worm; then
  CORE_BOOT_SERVICES+=(audit-postgres audit-worm audit-worm-init)
  CORE_HEALTH_SERVICES+=(audit-postgres audit-worm)
fi
CORE_BOOT_SERVICES+=(app)

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  "${PROFILE_ARGS[@]}" \
  up -d --build --remove-orphans "${CORE_BOOT_SERVICES[@]}"

echo "Attendo health app..."
wait_for_compose_services "${CORE_HEALTH_SERVICES[@]}"

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  "${PROFILE_ARGS[@]}" \
  up -d --build --remove-orphans

# ---------------------------------------------------------------------------
# 6. Pull modello Ollama (solo se il sidecar è attivo)
# ---------------------------------------------------------------------------
AI_ENABLED="${PCT_LOCAL_AI_ENABLED:-1}"
if [ "$AI_ENABLED" != "0" ] && [ "$AI_ENABLED" != "false" ]; then
  OLLAMA_CHAT_MODEL="${PCT_LOCAL_AI_CHAT_MODEL:-gemma3:1b}"
  if [ -n "$OLLAMA_CHAT_MODEL" ] && docker compose \
       --env-file "$ENV_FILE" \
       -f "$COMPOSE_FILE" \
       "${PROFILE_ARGS[@]}" \
       ps --services 2>/dev/null | grep -q "^ollama$"; then
    echo "Verifico modello Ollama locale: $OLLAMA_CHAT_MODEL"
    docker compose \
      --env-file "$ENV_FILE" \
      -f "$COMPOSE_FILE" \
      "${PROFILE_ARGS[@]}" \
      exec -T ollama ollama pull "$OLLAMA_CHAT_MODEL" || \
      echo "Attenzione: pull modello Ollama non riuscito — verificare manualmente."
  fi
fi

# ---------------------------------------------------------------------------
# 7. Stato servizi
# ---------------------------------------------------------------------------
echo "Attendo health container..."
wait_for_compose_services

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  "${PROFILE_ARGS[@]}" \
  ps || true

# ---------------------------------------------------------------------------
# 8. Pulizia cache build Docker
# ---------------------------------------------------------------------------
echo "Pulizia cache build Docker rigenerabile..."
docker builder prune --all --force || echo "Attenzione: pulizia cache build Docker non completata."
if [ -d "$IUSENTRA_HOME/tmp-backup-snapshot" ]; then
  echo "Pulizia snapshot temporaneo non operativo..."
  rm -rf -- "$IUSENTRA_HOME/tmp-backup-snapshot" || echo "Attenzione: snapshot temporaneo non rimosso."
fi

# ---------------------------------------------------------------------------
# 9. Cron backup automatico (aggiornato ad ogni deploy, salvo opt-out)
# ---------------------------------------------------------------------------
if [[ "${IUSENTRA_SKIP_BACKUP_CRON:-0}" =~ ^(1|true|yes|on)$ ]]; then
  echo "Cron backup: non aggiornato (IUSENTRA_SKIP_BACKUP_CRON=1)"
else
  CRON_SCHEDULE="${IUSENTRA_BACKUP_CRON_SCHEDULE:-15 2 * * *}"
  CRON_CMD="${CRON_SCHEDULE} bash ${REPO_DIR}/deploy/hetzner/backup.sh >> /var/log/iusentra/backup.log 2>&1"
  CRONTAB_MARKER="# iusentra-backup"
  ( crontab -l 2>/dev/null | grep -v "$CRONTAB_MARKER" || true; echo "${CRON_CMD}  ${CRONTAB_MARKER}" ) | crontab -
  echo "Cron backup: ${CRON_SCHEDULE}"
fi

echo ""
echo "Deploy completato: commit=${DEPLOYED_COMMIT}  branch=${BRANCH}"
echo "Health: https://${IUSENTRA_DOMAIN}/api/pronto"
