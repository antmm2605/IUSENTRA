#!/usr/bin/env bash
# ci_local_gate.sh — replica locale dei gate bloccanti della CI GitHub.
#
# REGOLA OBBLIGATORIA (CLAUDE.md): nessun push senza questo script verde.
# Rispecchia i job "Lint + syntax" (ci.yml) e "Frontend React CI"
# (frontend-ci.yml): se la CI aggiunge un gate, aggiungerlo anche qui.
#
# Uso:
#   bash scripts/ci_local_gate.sh            # batteria completa
#   bash scripts/ci_local_gate.sh --fast     # salta pytest lenti (solo check statici)
set -uo pipefail

cd "$(dirname "$0")/.."
FAST=0
[ "${1:-}" = "--fast" ] && FAST=1

PASS=0
FAIL=0
FAILED_STEPS=()

step() {
  local name="$1"; shift
  printf '\n\033[1m== %s ==\033[0m\n' "$name"
  if "$@"; then
    PASS=$((PASS + 1))
    printf '\033[32mOK\033[0m %s\n' "$name"
  else
    FAIL=$((FAIL + 1))
    FAILED_STEPS+=("$name")
    printf '\033[31mFAIL\033[0m %s\n' "$name"
  fi
}

# ---------------------------------------------------------------------------
# 0. Lint statico Python — replica del job "Lint + syntax" (ci.yml).
#    Questi gate (Ruff/Flake8/py_compile) NON erano replicati localmente:
#    e' la causa storica di CI rossa su errori che il gate locale non vedeva
#    (es. F821 undefined-name). Targets identici a .python-targets della CI.
# ---------------------------------------------------------------------------
PYTHON_TARGETS=(core pct web lex tests worker.py gunicorn.conf.py visible_signature.py wsgi.py)
for f in tools/*.py; do PYTHON_TARGETS+=("$f"); done
# Filtra solo i path esistenti (shopt nullglob non garantito in ogni shell)
EXISTING_TARGETS=()
for t in "${PYTHON_TARGETS[@]}"; do [ -e "$t" ] && EXISTING_TARGETS+=("$t"); done

ensure_pytool() {
  # Installa il linter se assente, cosi' il gate non lo salta mai in silenzio.
  python3 -c "import $1" >/dev/null 2>&1 && return 0
  pip install -q "$2" >/dev/null 2>&1
}

ruff_ci() {
  ensure_pytool ruff "ruff>=0.6.0"
  python3 -m ruff check --output-format=concise --select E9,F63,F7,F82 "${EXISTING_TARGETS[@]}"
}
ruff_governed() {
  ensure_pytool ruff "ruff>=0.6.0"
  python3 -m ruff check --config pyproject.toml \
    packaging_manifest.py docker/entrypoint.py tools/sync_packaging_files.py \
    pct/giurisprudenza_corpus.py lex/http_bounded_bridge.py lex/context/studio_context.py \
    lex/retrieval lex/formatting/answer_builder.py \
    tests/test_packaging_consistency.py tests/test_docker_entrypoint.py
}
flake8_ci() {
  ensure_pytool flake8 "flake8>=7.0.0"
  python3 -m flake8 "${EXISTING_TARGETS[@]}"
}
pycompile_ci() {
  python3 - <<'PY'
import compileall, py_compile, sys
from pathlib import Path
ok = True
for d in (Path("pct"), Path("web"), Path("lex"), Path("tests")):
    if d.exists():
        ok = compileall.compile_dir(str(d), quiet=1) and ok
paths = sorted(Path("tools").glob("*.py"))
paths += [Path(f) for f in ("worker.py", "gunicorn.conf.py", "visible_signature.py", "wsgi.py") if Path(f).exists()]
# local_signer_mod non e' nei target CI ma lo compiliamo: e' distribuito ai client
paths += sorted(Path("local_signer_mod").glob("*.py"))
for p in paths:
    try:
        py_compile.compile(str(p), doraise=True)
    except py_compile.PyCompileError as exc:
        print(exc); ok = False
sys.exit(0 if ok else 1)
PY
}

step "Ruff (E9,F63,F7,F82)"   ruff_ci
step "Ruff governed modules"  ruff_governed
step "Flake8"                 flake8_ci
step "Compile Python"         pycompile_ci

# ---------------------------------------------------------------------------
# 1. Artefatti generati (i piu' frequenti colpevoli di CI rossa)
# ---------------------------------------------------------------------------
step "Packaging sync"            python3 tools/sync_packaging_files.py --check
step "API contracts + openapi"   python3 scripts/react-migration/generate_api_contracts.py --check
step "OpenAPI valido"            python3 scripts/validate_openapi.py docs/openapi.yaml
step "Backend security map"      python3 scripts/react-migration/generate_backend_security_map.py --check
step "App V2 page registry"      python3 scripts/react-migration/generate_app_v2_page_registry.py --check
step "App V2 test docs"          python3 scripts/react-migration/generate_app_v2_test_docs.py --check
step "App V2 area requirements"  python3 scripts/react-migration/generate_app_v2_area_requirements.py --check
step "Governance repo"           python3 tools/check_repo_governance.py

# ---------------------------------------------------------------------------
# 2. Gate frontend — la CI esegue TUTTI questi script, non solo i contratti
#    (pnpm --filter @iusentra/studio test)
# ---------------------------------------------------------------------------
step "React contracts"           node frontend/scripts/check-react-contracts.mjs
step "UI preset sequence"        node scripts/react-migration/audit-ui-preset-sequence.mjs
step "Design system governance"  node scripts/react-migration/check-design-system-governance.mjs
step "App V2 frontend"           node frontend/scripts/check-app-v2-frontend.mjs
step "Legal skills"              node frontend/scripts/check-legal-skills.mjs
step "UI coverage"               python3 scripts/validate_ui_coverage.py
step "TypeScript typecheck"      npm --prefix frontend run typecheck --silent
step "Vite build"                npm --prefix frontend run build:vite --silent

# ---------------------------------------------------------------------------
# 3. Pytest dei gate (salta con --fast)
# ---------------------------------------------------------------------------
if [ "$FAST" -eq 0 ]; then
  step "Pytest contratti openapi"  python3 -m pytest -q tests/test_openapi_contracts_phase6.py --tb=short
  step "Pytest registry/gates"     python3 -m pytest -q tests/test_app_v2_page_registry.py tests/test_app_v2_test_plan_phase10.py tests/test_ci_cd_gates_phase11.py --tb=short
  step "Pytest security fase 5"    python3 -m pytest -q tests/test_backend_security_phase5.py --tb=short
  step "Pytest area requirements"  python3 -m pytest -q tests/test_app_v2_area_requirements_phase8.py tests/test_ui_coverage_phase9.py --tb=short
fi

# ---------------------------------------------------------------------------
# Esito
# ---------------------------------------------------------------------------
printf '\n\033[1m================ ESITO GATE LOCALE ================\033[0m\n'
printf 'Passati: %d  Falliti: %d\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf '\033[31mGate falliti:\033[0m\n'
  for s in "${FAILED_STEPS[@]}"; do printf '  - %s\n' "$s"; done
  printf '\n\033[31mNON PUSHARE: correggi i gate falliti e rilancia.\033[0m\n'
  exit 1
fi
printf '\033[32mTutti i gate verdi: push consentito.\033[0m\n'
