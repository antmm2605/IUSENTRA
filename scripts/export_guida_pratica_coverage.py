#!/usr/bin/env python3
"""Esporta la copertura Guida Pratica in JSON o CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica import GuidaPraticaService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--output", default="guida_pratica_coverage.json")
    args = parser.parse_args()
    service = GuidaPraticaService()
    rows = service.list_guidance(limit=10000)
    output = Path(args.output)
    if args.format == "json":
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["codice", "denominazione", "area", "parent_codice", "coverage", "needs_reviewer", "file_fonte"])
            writer.writeheader()
            for row in rows:
                coverage = row.get("coverage") or {}
                writer.writerow({
                    "codice": row.get("codice", ""),
                    "denominazione": row.get("denominazione", ""),
                    "area": row.get("area", ""),
                    "parent_codice": row.get("parent_codice", ""),
                    "coverage": coverage.get("level", ""),
                    "needs_reviewer": coverage.get("needs_reviewer", False),
                    "file_fonte": row.get("file_fonte", ""),
                })
    print(f"Creato {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
