#!/usr/bin/env python3
"""Valida il catalogo codici oggetto PST/XSD."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst.json"
CODE_RE = re.compile(r"^(?:\d{3,8}(?:_[A-Z0-9]{1,8})?|[A-Z][A-Z0-9_]{2,40})$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--min-records", type=int, default=1)
    args = parser.parse_args()
    path = Path(args.catalog)
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    seen = set()
    duplicates = []
    invalid = []
    missing_description = []
    for row in records:
        if not isinstance(row, dict):
            invalid.append("")
            continue
        code = str(row.get("codice") or "").strip()
        if code in seen:
            duplicates.append(code)
        seen.add(code)
        if not CODE_RE.match(code):
            invalid.append(code)
        if not str(row.get("descrizione") or "").strip():
            missing_description.append(code)
    ok = len(records) >= args.min_records and not duplicates and not invalid and not missing_description
    print(json.dumps({"ok": ok, "records": len(records), "duplicates": duplicates[:20], "invalid": invalid[:20], "missing_description": missing_description[:20]}, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
