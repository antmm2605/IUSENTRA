from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
api = (ROOT / "web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
bridge = (ROOT / "web/services/react_audit_bridge.py").read_text(encoding="utf-8")
gate = (ROOT / "web/bootstrap/react_route_gate.py").read_text(encoding="utf-8")

failures: list[str] = []

for marker in [
    '@api_v1_react.get("/audit")',
    '@api_v1_react.get("/registro-attivita")',
    '@api_v1_react.get("/audit/<id_evento>")',
]:
    if marker not in api:
        failures.append(f"Endpoint mancante: {marker}")
for marker in ["_richiedi_auth", "_puo_leggere_audit"]:
    if marker not in api:
        failures.append(f"Controllo API mancante: {marker}")
for marker in ['"writes": "json_api"', '"sensitive_payloads_redacted": True', "_redact_payload", "_details_payload"]:
    if marker not in bridge:
        failures.append(f"Sanificazione/contratto audit mancante: {marker}")
if "dangerouslySetInnerHTML" in (ROOT / "frontend/src/components/AuditPage.tsx").read_text(encoding="utf-8"):
    failures.append("AuditPage usa dangerouslySetInnerHTML.")
if '"/audit"' not in gate or '"/registro-attivita"' not in gate:
    failures.append("Gate non espone le route exact React audit/registro.")

if failures:
    raise SystemExit("Tranche 25A API KO\n- " + "\n- ".join(failures))

print("Tranche 25A API static OK (harness autenticato non disponibile: controlli statici eseguiti).")
