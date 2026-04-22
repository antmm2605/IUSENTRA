from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


RUNTIME_HEADER = """# requirements.txt - file flat generato da requirements/base.txt
# Non modificare a mano: usare requirements/*.txt e tools/sync_packaging_files.py
"""

DEV_HEADER = """# requirements-dev.txt - file flat generato da requirements/dev.txt
# Non modificare a mano: usare requirements/*.txt e tools/sync_packaging_files.py
"""


def _target_payloads() -> dict[Path, str]:
    from packaging_manifest import dev_requirements, render_flat_requirements, runtime_requirements

    return {
        REPO_ROOT / "requirements.txt": render_flat_requirements(RUNTIME_HEADER, runtime_requirements()),
        REPO_ROOT / "requirements-dev.txt": render_flat_requirements(DEV_HEADER, dev_requirements()),
    }


def _check(targets: dict[Path, str]) -> int:
    dirty: list[str] = []
    for path, expected in targets.items():
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != expected:
            dirty.append(str(path.relative_to(REPO_ROOT)))
    if dirty:
        print("Packaging non sincronizzato:", ", ".join(dirty), file=sys.stderr)
        return 1
    print("Packaging sincronizzato.")
    return 0


def _write(targets: dict[Path, str]) -> int:
    for path, payload in targets.items():
        path.write_text(payload, encoding="utf-8")
        print(f"Aggiornato {path.relative_to(REPO_ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sincronizza i file packaging flat dal manifest requirements.")
    parser.add_argument("--check", action="store_true", help="Verifica senza scrivere.")
    args = parser.parse_args(argv)
    targets = _target_payloads()
    return _check(targets) if args.check else _write(targets)


if __name__ == "__main__":
    raise SystemExit(main())
