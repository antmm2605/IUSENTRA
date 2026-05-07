from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


api = read("web/blueprints/api_v1_react.py")
bridge = read("web/services/react_fatturazione_bridge.py")
actions = read("web/services/react_fatturazione_archive_actions.py")
gate = read("web/bootstrap/react_route_gate.py")
manifest = json.loads(read("tools/react-migration/route-manifest.json"))
violations: list[str] = []

for marker in [
    '@api_v1_react.get("/fatturazione")',
    '@api_v1_react.get("/fatturazione/<id_documento>")',
    '@api_v1_react.post("/fatturazione/<id_documento>/stato")',
    '@api_v1_react.post("/fatturazione/<id_documento>/annulla")',
    '@api_v1_react.post("/fatturazione/<id_documento>/segna-pagata")',
]:
    if marker not in api:
        violations.append(f"endpoint assente: {marker}")
if "build_react_fatturazione_detail_payload" not in bridge or "update_react_fatturazione_status" not in bridge:
    violations.append("bridge fatturazione non riesporta dettaglio/stato JSON.")
if re.search(r'"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:', bridge + actions, re.I):
    violations.append("payload fatturazione serializza campo sensibile.")
if "writes" not in bridge or "json_api" not in bridge:
    violations.append("bridge non dichiara scritture json_api.")
route = next((item for item in manifest["routes"] if item["route"] == "/fatturazione"), None)
if not route or route.get("status") != "react_operational_full":
    violations.append("manifest /fatturazione non operativo full.")
if 'lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova"' not in gate:
    violations.append("gate fatturazione non conserva protezione subpath.")

if violations:
    print("Tranche 21A API non conforme:")
    print("\n".join(f"- {item}" for item in violations))
    sys.exit(1)

print("Tranche 21A fatturazione archivio API OK (controlli statici; autenticazione Flask non avviata).")
