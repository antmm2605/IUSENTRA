"""CLI per generare chiavi VAPID Web Push senza scriverle nel repository."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
module_path = repo_root / "pct" / "notifications" / "generate_vapid.py"
spec = importlib.util.spec_from_file_location("iusentra_generate_vapid", module_path)
if spec is None or spec.loader is None:  # pragma: no cover
    raise RuntimeError("Modulo generazione VAPID non disponibile.")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

main = module.main


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
