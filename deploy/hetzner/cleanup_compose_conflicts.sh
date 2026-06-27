#!/usr/bin/env bash
# Rimuove i container temporanei lasciati da Docker Compose durante recreate
# interrotti. Non tocca i container canonici (iusentra-app-1, redis, postgres,
# audit-worm) e non cancella volumi o dati applicativi.
set -euo pipefail

PROJECT="${IUSENTRA_COMPOSE_PROJECT:-iusentra}"
ALLOW_RUNNING="${IUSENTRA_CLEANUP_RUNNING_TEMP:-1}"

is_allowed_temporary_service() {
  local name="$1"
  [[ "$name" =~ ^[0-9a-f]{8,64}_${PROJECT}-(app|scheduler-worker|ocr-worker|caddy|audit-worm-init)-[0-9]+$ ]]
}

removed=0

while IFS=$'\t' read -r container_id container_name container_state; do
  [ -n "${container_id:-}" ] || continue
  [ -n "${container_name:-}" ] || continue

  if ! is_allowed_temporary_service "$container_name"; then
    continue
  fi

  if [[ "$container_state" == "running" && ! "$ALLOW_RUNNING" =~ ^(1|true|yes|on)$ ]]; then
    echo "Container temporaneo Compose mantenuto perche' running: ${container_name} (${container_id})"
    continue
  fi

  echo "Rimuovo container temporaneo Compose: ${container_name} (${container_id}, state=${container_state})"
  docker rm -f "$container_id"
  removed=1
done < <(docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.State}}')

if [ "$removed" -eq 0 ]; then
  echo "Nessun container temporaneo Compose da rimuovere."
fi
