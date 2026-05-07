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

if '@api_v1_react.get("/preventivi/conferimento/nuovo")' not in api:
    violations.append("GET /api/v1/ui/preventivi/conferimento/nuovo assente.")
if '@api_v1_react.post("/preventivi/conferimento/nuovo")' not in api:
    violations.append("POST /api/v1/ui/preventivi/conferimento/nuovo assente.")
if "_puo_scrivere_preventivi" not in api or "_request_json_object" not in api:
    violations.append("permessi o JSON guard non rilevati nel POST conferimento.")
if "create_react_conferimento" not in bridge or "document_generation" not in bridge:
    violations.append("bridge conferimento operativo non rilevato.")
if re.search(r'"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:', bridge, re.I):
    violations.append("bridge serializza campo sensibile.")
if re.search(r"generatePdf|generateDOCX|new Blob|URL\.createObjectURL", bridge):
    violations.append("bridge contiene generazione documento frontend.")
route = next((item for item in manifest["routes"] if item["route"] == "/preventivi/conferimento/nuovo"), None)
if not route or route.get("status") != "react_operational_full":
    violations.append("manifest /preventivi/conferimento/nuovo non operativo full.")
if 'lower.startswith("/preventivi/")' not in gate or '"/preventivi/conferimento/nuovo"' not in gate:
    violations.append("gate preventivi non conserva sblocco mirato conferimento.")

if violations:
    print("Tranche 19A API non conforme:")
    print("\n".join(f"- {item}" for item in violations))
    sys.exit(1)

print("Tranche 19A conferimento API OK (controlli statici; autenticazione Flask non avviata).")
