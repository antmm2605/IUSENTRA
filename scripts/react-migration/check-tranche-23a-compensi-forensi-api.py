from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
api = (ROOT / "web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
bridge = (ROOT / "web/services/react_compensi_forensi_bridge.py").read_text(encoding="utf-8")
gate = (ROOT / "web/bootstrap/react_route_gate.py").read_text(encoding="utf-8")

failures: list[str] = []

for marker in ['@api_v1_react.get("/compensi-forensi")', '@api_v1_react.post("/compensi-forensi/calcola")']:
    if marker not in api:
        failures.append(f"Endpoint mancante: {marker}")
for marker in ["_richiedi_auth", "_request_json_object", "_puo_leggere_fatturazione"]:
    if marker not in api:
        failures.append(f"Controllo API mancante: {marker}")
for marker in ['"writes": "json_api"', '"canonical_calculation": "backend"', '"dm55_calculation": "backend"']:
    if marker not in bridge:
        failures.append(f"Contratto bridge mancante: {marker}")
for forbidden in ['"totale"', '"risultato"', '"compenso_calcolato"', '"iva"', '"cassa"', '"ritenuta"']:
    if forbidden not in bridge:
        failures.append(f"Validazione campi canonici mancante: {forbidden}")
for forbidden in ["api_key", "access_token", "refresh_token", "stack_trace", "traceback"]:
    if forbidden in bridge:
        failures.append(f"Bridge compensi contiene marker sensibile: {forbidden}")
if 'lower.startswith("/compensi-forensi/")' not in gate:
    failures.append("Gate non protegge /compensi-forensi/*.")

if failures:
    raise SystemExit("Tranche 23A API KO\n- " + "\n- ".join(failures))

print("Tranche 23A API static OK (harness autenticato non disponibile: controlli statici eseguiti).")
