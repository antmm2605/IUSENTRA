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
  local protected_refs_file
  active_ids_file="$(mktemp)"
  protected_refs_file="$(mktemp)"
  trap "rm -f '$active_ids_file' '$protected_refs_file'" EXIT

  docker ps -q | xargs -r docker inspect --format '{{.Image}}' | sort -u > "$active_ids_file"
  docker ps --format '{{.Image}}' | sort -u > "$protected_refs_file"

  protect_release_tag() {
    local sha="${1:-}"
    local repo
    if [[ "$sha" =~ ^[0-9a-f]{40}$ ]]; then
      for repo in $IMAGE_REPOSITORIES; do
        printf '%s:%s\n' "$repo" "$sha" >> "$protected_refs_file"
      done
    fi
  }

  protect_release_tag "${EXPECTED_SHA:-}"
  protect_release_tag "${GITHUB_SHA:-}"
  protect_release_tag "${RELEASE_SHA:-}"

  local repo_dir
  local head_sha
  repo_dir="${IUSENTRA_REPO_DIR:-$(pwd)}"
  if command -v git >/dev/null 2>&1 && [ -d "$repo_dir/.git" ]; then
    head_sha="$(git -C "$repo_dir" rev-parse HEAD 2>/dev/null || true)"
    protect_release_tag "$head_sha"
  fi
  sort -u -o "$protected_refs_file" "$protected_refs_file"

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
    if grep -qx "$reference" "$protected_refs_file"; then
      skipped=$((skipped + 1))
      continue
    fi

    if docker image rm "$reference"; then
      removed=$((removed + 1))
    else
      echo "Attenzione: immagine non rimossa: $reference" >&2
    fi
  done < <(docker images --format '{{.Repository}}\t{{.Tag}}\t{{.ID}}')

  docker image prune --force >/dev/null || echo "Attenzione: pulizia immagini dangling non completata." >&2
  docker builder prune --all --force || echo "Attenzione: pulizia cache build Docker non completata." >&2

  echo "Pulizia immagini IUSENTRA: rimosse=${removed}, conservate=${skipped}"
}

main "$@"
