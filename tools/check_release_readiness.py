from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "docs/OBSERVABILITY_GUIDELINES.md",
    "docs/RELEASE_TRAIN.md",
    "docs/MULTI_TENANT_GUIDELINES.md",
    "ops/release_checklist.md",
]


def main() -> int:
    missing = [p for p in REQUIRED_PATHS if not (REPO_ROOT / p).exists()]
    if missing:
        print("Release readiness FAILED")
        for item in missing:
            print(f"- manca {item}")
        return 1
    print("Release readiness OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
