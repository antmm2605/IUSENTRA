from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


api = read("web/blueprints/api_v1_react.py")
bridge = read("web/services/react_preventivi_bridge.py")
gate = read("web/bootstrap/react_route_gate.py")
manifest = json.loads(read("tools/react-migration/route-manifest.json"))
violations: list[str] = []

if '@api_v1_react.get("/preventivi/nuovo")' not in api:
    violations.append("GET /api/v1/ui/preventivi/nuovo assente.")
if '@api_v1_react.post("/preventivi/nuovo")' not in api:
    violations.append("POST /api/v1/ui/preventivi/nuovo assente.")
if "_puo_scrivere_preventivi" not in api or "_request_json_object" not in api:
    violations.append("permessi o JSON guard non rilevati nel POST preventivo.")
if "_CANONICAL_AMOUNT_FIELDS" not in bridge or "Importo o calcolo canonico non accettato" not in bridge:
    violations.append("bridge non rifiuta importi canonici frontend.")
if re.search(r'"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:', bridge, re.I):
    violations.append("bridge serializza campo sensibile.")
if "PDF" in bridge and "raw" in bridge.lower():
    violations.append("bridge sembra restituire documento raw.")
route = next((item for item in manifest["routes"] if item["route"] == "/preventivi/nuovo"), None)
if not route or route.get("status") != "react_operational_full":
    violations.append("manifest /preventivi/nuovo non operativo full.")
if 'lower.startswith("/preventivi/")' not in gate or '"/preventivi/nuovo"' not in gate:
    violations.append("gate preventivi non conserva sblocco mirato.")

if violations:
    print("Tranche 18A API non conforme:")
    print("\n".join(f"- {item}" for item in violations))
    sys.exit(1)

print("Tranche 18A preventivi/nuovo API OK (controlli statici; autenticazione Flask non avviata).")
