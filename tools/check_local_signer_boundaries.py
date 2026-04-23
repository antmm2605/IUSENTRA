from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    for required in (
        "local_signer_mod/security.py",
        "local_signer_mod/ai_cache.py",
        "local_signer_mod/ai_handlers.py",
        "local_signer_mod/server_bootstrap.py",
    ):
        if not (REPO_ROOT / required).exists():
            failures.append(f"Manca {required}")

    signer_paths = (
        "local_signer.py",
        "tools/local_signer.py",
    )
    existing_signer = next((path for path in signer_paths if (REPO_ROOT / path).exists()), "")
    if existing_signer:
        text = _read(existing_signer)
        expected_snippets = (
            "from local_signer_mod.security import (",
            "from local_signer_mod.ai_handlers import LocalAiHandlerFacade",
            "from local_signer_mod.server_bootstrap import print_startup_banner",
        )
        for snippet in expected_snippets:
            if snippet not in text:
                failures.append(f"{existing_signer} non integra ancora: {snippet}")

    if failures:
        print("Local Signer boundary check FAILED")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Local Signer boundary check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
