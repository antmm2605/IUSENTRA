"""Validate Open Design support files and skill metadata."""

from __future__ import annotations

import json
from pathlib import Path
import sys


DESIGN_SECTIONS = [
    "Visual Theme & Atmosphere",
    "Color Palette & Roles",
    "Typography Rules",
    "Component Stylings",
    "Layout Principles",
    "Responsive Behavior",
    "Agent Prompt Guide",
]

SKILL_MARKERS = [
    "---",
    "name:",
    "description:",
    "triggers:",
    "Workflow",
]


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    print("ERRORE: impossibile determinare la root git.")
    sys.exit(1)


def load_policy(root: Path) -> dict:
    policy_path = root / "tools" / "codex_harness" / "policy.json"
    return json.loads(policy_path.read_text(encoding="utf-8"))


def main() -> int:
    root = repo_root()
    policy = load_policy(root)
    violations: list[str] = []

    print("Open Design support check")

    for relative in policy["open_design_required_files"]:
        path = root / relative
        if not path.exists():
            violations.append(f"File mancante: {relative}")

    design_path = root / "tools" / "open-design-support" / "IUSENTRA_DESIGN.md"
    if design_path.exists():
        design_text = design_path.read_text(encoding="utf-8")
        for section in DESIGN_SECTIONS:
            if section not in design_text:
                violations.append(f"Sezione design mancante: {section}")

    skills_root = root / "tools" / "open-design-support" / "skills"
    for skill_path in sorted(skills_root.glob("*/SKILL.md")):
        text = skill_path.read_text(encoding="utf-8")
        relative = skill_path.relative_to(root).as_posix()
        for marker in SKILL_MARKERS:
            if marker not in text:
                violations.append(f"Marker skill mancante in {relative}: {marker}")
        if not text.lstrip().startswith("---"):
            violations.append(f"Frontmatter non in apertura: {relative}")

    if violations:
        print("VIOLAZIONI:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("OK: Open Design support completo e coerente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
