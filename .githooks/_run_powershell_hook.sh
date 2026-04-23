#!/bin/sh
set -eu

hook_name="$1"
shift || true

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
helper="$repo_root/scripts/git_branch_autosync.ps1"

if [ ! -f "$helper" ]; then
  exit 0
fi

if command -v pwsh >/dev/null 2>&1; then
  exec pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$helper" -HookName "$hook_name"
fi

if command -v powershell.exe >/dev/null 2>&1; then
  exec powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$helper" -HookName "$hook_name"
fi

if command -v powershell >/dev/null 2>&1; then
  exec powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$helper" -HookName "$hook_name"
fi

echo "Hook $hook_name: runtime PowerShell non disponibile, salto autosync branch." >&2
exit 0
