from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.template_atti_master_catalog import REQUIRED_TEMPLATE_FIELDS, load_catalogo_master, load_split_catalogs


def main() -> int:
    master = load_catalogo_master()
    templates = list(master.get("template") or [])
    ids = [item["id"] for item in templates]
    split = load_split_catalogs()
    total_split = sum(int(payload.get("totale_template") or 0) for payload in split.values())
    errors: list[str] = []
    if len(templates) != 420:
        errors.append(f"Attesi 420 template master, trovati {len(templates)}.")
    if len(set(ids)) != len(ids):
        errors.append("Sono presenti ID duplicati nel master.")
    if total_split != len(templates):
        errors.append(f"Gli split sommano {total_split}, master {len(templates)}.")
    for item in templates:
        missing = [field for field in REQUIRED_TEMPLATE_FIELDS if field not in item]
        if missing:
            errors.append(f"{item.get('id')}: mancano {', '.join(missing)}")
        if not item.get("prefill_bindings"):
            errors.append(f"{item.get('id')}: prefill_bindings assente")
        if not item.get("cartabia_profile"):
            errors.append(f"{item.get('id')}: cartabia_profile assente")
    if errors:
        print(json.dumps({"ok": False, "errors": errors[:50], "error_count": len(errors)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "template_totali": len(templates), "split_totale": total_split}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

