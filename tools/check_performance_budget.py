from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    perf_file = REPO_ROOT / "tools" / "performance_smoke.py"
    if not perf_file.exists():
        print("[FAIL] tools/performance_smoke.py mancante")
        return 1

    text = perf_file.read_text(encoding="utf-8")
    checks = {
        "uses_monotonic": "monotonic" in text,
        "has_temp_config": "tempfile" in text,
        "imports_create_app": "create_app" in text,
        "imports_lex_context": "LexContextBuilder" in text,
        "imports_retrieval_orchestrator": "RetrievalOrchestrator" in text,
    }

    failed = [name for name, value in checks.items() if not value]
    for name, value in checks.items():
        print(f"[{'OK' if value else 'FAIL'}] {name}")

    payload = {
        "ok": not failed,
        "checks": checks,
        "recommendation": (
            "Integrare un benchmark numerico persistente JSON in CI"
            if not failed else
            "Ripristinare performance_smoke.py coerente con benchmark Lex/web"
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
