from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
api = (ROOT / "web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
bridge = (ROOT / "web/services/react_tariffario_bridge.py").read_text(encoding="utf-8")
gate = (ROOT / "web/bootstrap/react_route_gate.py").read_text(encoding="utf-8")

failures: list[str] = []

for marker in [
    '@api_v1_react.get("/tariffario")',
    '@api_v1_react.post("/tariffario/calcola")',
    '@api_v1_react.get("/tariffario/<id_voce>")',
]:
    if marker not in api:
        failures.append(f"Endpoint mancante: {marker}")
for marker in ["_richiedi_auth", "_request_json_object", "_puo_leggere_fatturazione"]:
    if marker not in api:
        failures.append(f"Controllo API mancante: {marker}")
for marker in ['"writes": "json_api"', '"canonical_tariff": "backend"', '"canonical_calculation": "backend"', '"dm55_calculation": "backend"']:
    if marker not in bridge:
        failures.append(f"Contratto bridge mancante: {marker}")
for marker in ['"result"', '"risultato"', '"totale"', '"scaglioni"']:
    if marker not in bridge:
        failures.append(f"Validazione fonte canonica mancante: {marker}")
for forbidden in ["api_key", "access_token", "refresh_token", "stack_trace", "traceback"]:
    if forbidden in bridge:
        failures.append(f"Bridge tariffario contiene marker sensibile: {forbidden}")
if 'lower.startswith("/tariffario/")' not in gate:
    failures.append("Gate non protegge /tariffario/*.")

if failures:
    raise SystemExit("Tranche 24A API KO\n- " + "\n- ".join(failures))

print("Tranche 24A API static OK (harness autenticato non disponibile: controlli statici eseguiti).")
