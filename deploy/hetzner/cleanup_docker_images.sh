#!/usr/bin/env bash
# Rimuove immagini Docker IUSENTRA obsolete senza toccare volumi o dati.
set -euo pipefail

IMAGE_REPOSITORIES="${IUSENTRA_DOCKER_IMAGE_REPOSITORIES:-iusentra-app iusentra-scheduler-worker iusentra-ocr-worker iusentra-frontend iusentra-presidi-frontend iusentra-frontend-audit}"

repository_allowed() {
  local candidate="$1"
  local repo
  for repo in $IMAGE_REPOSITORIES; do
    if [ "$candidate" = "$repo" ]; then
      return 0
    fi
  done
  return 1
}

main() {
  local active_ids_file
  active_ids_file="$(mktemp)"
  trap "rm -f '$active_ids_file'" EXIT

  docker ps -q | xargs -r docker inspect --format '{{.Image}}' | sort -u > "$active_ids_file"

  local repository
  local tag
  local image_id
  local reference
  local removed=0
  local skipped=0

  while IFS=$'\t' read -r repository tag image_id; do
    [ -n "${repository:-}" ] || continue
    [ -n "${tag:-}" ] || continue
    [ -n "${image_id:-}" ] || continue
    repository_allowed "$repository" || continue

    if grep -qx "$image_id" "$active_ids_file"; then
      skipped=$((skipped + 1))
      continue
    fi

    reference="${repository}:${tag}"
    if docker image rm "$reference"; then
      removed=$((removed + 1))
    else
      echo "Attenzione: immagine non rimossa: $reference" >&2
    fi
  done < <(docker images --format '{{.Repository}}\t{{.Tag}}\t{{.ID}}')

  docker image prune --force >/dev/null || echo "Attenzione: pulizia immagini dangling non completata." >&2
  docker builder prune --all --force || echo "Attenzione: pulizia cache build Docker non completata." >&2

  echo "Pulizia immagini IUSENTRA: rimosse=${removed}, attive_conservate=${skipped}"
}

main "$@"
