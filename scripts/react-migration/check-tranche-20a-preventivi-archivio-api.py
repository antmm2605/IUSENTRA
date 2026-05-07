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

for marker in [
    '@api_v1_react.get("/preventivi")',
    '@api_v1_react.get("/preventivi/<id_preventivo>")',
    '@api_v1_react.post("/preventivi/<id_preventivo>/stato")',
]:
    if marker not in api:
        violations.append(f"endpoint assente: {marker}")
if "build_react_preventivo_detail_payload" not in bridge or "update_react_preventivo_status" not in bridge:
    violations.append("bridge archivio preventivi non espone dettaglio/stato JSON.")
if re.search(r'"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:', bridge, re.I):
    violations.append("bridge serializza campo sensibile.")
if "writes" not in bridge or "json_api" not in bridge:
    violations.append("bridge non dichiara scritture json_api.")
route = next((item for item in manifest["routes"] if item["route"] == "/preventivi"), None)
if not route or route.get("status") != "react_operational_full":
    violations.append("manifest /preventivi non operativo full.")
if 'lower.startswith("/preventivi/")' not in gate or '"/preventivi/wizard"' not in gate:
    violations.append("gate preventivi non conserva protezione subpath.")

if violations:
    print("Tranche 20A API non conforme:")
    print("\n".join(f"- {item}" for item in violations))
    sys.exit(1)

print("Tranche 20A preventivi archivio API OK (controlli statici; autenticazione Flask non avviata).")
