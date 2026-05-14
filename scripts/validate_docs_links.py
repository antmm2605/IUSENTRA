from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    "README.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/index.md",
    "docs/documentation-audit.md",
    "docs/architecture.md",
    "docs/app-v2.md",
    "docs/feature-flags.md",
    "docs/legacy-to-app-v2-routing-map.md",
    "docs/security-rbac-tenant-isolation.md",
    "docs/api-contracts.md",
    "docs/test-plan-app-v2.md",
    "docs/ci-cd-gates.md",
    "docs/ui-regression-and-storybook.md",
    "docs/release-rollout.md",
    "docs/troubleshooting.md",
    "docs/risk-register.md",
    "docs/handover-next-prs.md",
    "docs/observability-and-logs.md",
    "docs/database-and-migrations.md",
    "docs/release-notes-app-v2.md",
]

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _is_external(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https", "mailto", "tel"}


def _clean(target: str) -> str:
    target = target.strip().strip("<>")
    target = target.split("#", 1)[0]
    target = target.split("?", 1)[0]
    return unquote(target)


def main() -> int:
    errors: list[str] = []
    checked = 0
    for rel in DOCS:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"missing document: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in LINK_RE.finditer(text):
            raw = match.group(1)
            if _is_external(raw):
                continue
            target = _clean(raw)
            if not target:
                continue
            if target.startswith("#"):
                continue
            candidate = (path.parent / target).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                errors.append(f"{rel}: link escapes repository: {raw}")
                continue
            if not candidate.exists():
                errors.append(f"{rel}: broken local link: {raw}")
            checked += 1
    if errors:
        print("Document link validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Document link validation OK: {len(DOCS)} documents, {checked} local links checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
