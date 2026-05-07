from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
api = (ROOT / "web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
bridge = (ROOT / "web/services/react_incassi_pagamenti_bridge.py").read_text(encoding="utf-8")
gate = (ROOT / "web/bootstrap/react_route_gate.py").read_text(encoding="utf-8")

failures: list[str] = []

required = [
    '@api_v1_react.get("/incassi-pagamenti")',
    '@api_v1_react.post("/incassi-pagamenti/incasso")',
    '@api_v1_react.post("/incassi-pagamenti/<id_pagamento>/stato")',
    '@api_v1_react.post("/incassi-pagamenti/<id_pagamento>/collega")',
    '@api_v1_react.post("/incassi-pagamenti/<id_pagamento>/link-pagamento")',
]
for marker in required:
    if marker not in api:
        failures.append(f"Endpoint mancante: {marker}")

for marker in ["_richiedi_auth", "_request_json_object", "_puo_scrivere_fatturazione", "_puo_leggere_fatturazione"]:
    if marker not in api:
        failures.append(f"Controllo API mancante: {marker}")

if '"writes": "json_api"' not in bridge:
    failures.append("Bridge incassi non dichiara writes json_api.")
for forbidden in ["provider_secret", "webhook_secret", "client_secret", "api_key", "access_token", "refresh_token"]:
    if forbidden in bridge:
        failures.append(f"Bridge incassi contiene marker sensibile: {forbidden}")

if 'lower.startswith("/incassi-pagamenti/")' not in gate:
    failures.append("Gate non protegge /incassi-pagamenti/*.")
if '"/impostazioni/pagamenti"' not in gate:
    failures.append("Gate non mantiene legacy /impostazioni/pagamenti.")

if failures:
    raise SystemExit("Tranche 22A API KO\n- " + "\n- ".join(failures))

print("Tranche 22A API static OK (harness autenticato non disponibile: controlli statici eseguiti).")
