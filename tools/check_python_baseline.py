from pathlib import Path
import sys


def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    print(f"[OK] {message}")


pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
setup_py = Path("setup.py").read_text(encoding="utf-8")
dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

require('target-version = "py312"' in pyproject, "Ruff allineato a Python 3.12")
require('python_version = "3.12"' in pyproject, "mypy allineato a Python 3.12")
require('python_requires=">=3.12"' in setup_py, "setup.py richiede Python >= 3.12")
require("python:3.12-slim" in dockerfile, "Dockerfile allineato a Python 3.12")

print("Python baseline aligned to 3.12")
