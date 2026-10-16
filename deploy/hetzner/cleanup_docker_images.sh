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
  local images_file
  active_ids_file="$(mktemp)"
  protected_refs_file="$(mktemp)"
  images_file="$(mktemp)"
  trap "rm -f '$active_ids_file' '$protected_refs_file' '$images_file'" EXIT

  docker ps -aq | xargs -r docker inspect --format '{{.Image}}' | sort -u > "$active_ids_file"
  docker ps --format '{{.Image}}' | sort -u > "$protected_refs_file"
  for reference in ${IUSENTRA_DOCKER_KEEP_REFS:-}; do
    printf '%s\n' "$reference" >> "$protected_refs_file"
  done

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
  local failed=0

  if ! docker images --format '{{.Repository}}\t{{.Tag}}\t{{.ID}}' --no-trunc > "$images_file"; then
    echo "Errore: inventario immagini Docker non disponibile; nessuna pulizia eseguita." >&2
    return 1
  fi

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

    # Un alias hot/WIP non dimostra che i sorgenti siano consolidati altrove.
    if ! [[ "$tag" =~ ^[0-9a-f]{10,40}$ ]]; then
      echo "Conservata immagine senza tag di release: $reference" >&2
      skipped=$((skipped + 1))
      continue
    fi

    if docker image rm "$reference"; then
      removed=$((removed + 1))
    else
      echo "Errore: immagine non rimossa: $reference" >&2
      failed=1
    fi
  done < "$images_file"

  docker image prune --force >/dev/null || { echo "Errore: pulizia immagini dangling non completata." >&2; failed=1; }
  docker builder prune --all --force || { echo "Errore: pulizia cache build Docker non completata." >&2; failed=1; }

  echo "Pulizia immagini IUSENTRA: rimosse=${removed}, conservate=${skipped}"
  return "$failed"
}

main "$@"
