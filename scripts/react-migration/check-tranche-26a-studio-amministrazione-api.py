from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def main() -> int:
    failures: list[str] = []
    api = read("web/blueprints/api_v1_react.py")
    studio_bridge = read("web/services/react_studio_bridge.py")
    admin_bridge = read("web/services/react_amministrazione_bridge.py")
    manifest = json.loads(read("tools/react-migration/route-manifest.json"))
    routes = {item["route"]: item for item in manifest.get("routes", [])}

    if '@api_v1_react.get("/studio")' not in api:
        fail("Manca GET /api/v1/ui/studio.", failures)
    if '@api_v1_react.get("/amministrazione")' not in api:
        fail("Manca GET /api/v1/ui/amministrazione.", failures)
    if "@_richiedi_auth" not in api[api.find('@api_v1_react.get("/studio")'):api.find('@api_v1_react.get("/amministrazione")')]:
        fail("GET /studio deve usare _richiedi_auth.", failures)
    if "if not _session_user_can(\"utenti.leggi\")" not in api:
        fail("GET /amministrazione deve controllare utenti.leggi.", failures)
    for name, source in (("studio", studio_bridge), ("amministrazione", admin_bridge)):
        if not re.search(r"['\"]ok['\"]\s*:\s*True", source):
            fail(f"Payload {name} deve restituire ok true.", failures)
        if not re.search(r"['\"]writes['\"]\s*:\s*['\"]none['\"]", source):
            fail(f"Payload {name} deve dichiarare writes none.", failures)
        if not re.search(r"['\"]operational['\"]\s*:\s*True", source):
            fail(f"Payload {name} deve dichiarare operational true.", failures)
        if not re.search(r"['\"]secrets_exposed['\"]\s*:\s*False", source):
            fail(f"Payload {name} deve dichiarare secrets_exposed false.", failures)
        if re.search(r"['\"](password|api_key|access_token|refresh_token|password_hash|provider_secret|webhook_secret|stack_trace|traceback)['\"]\s*:", source, re.I):
            fail(f"Payload {name} contiene chiavi sensibili.", failures)
    for path in ("/studio", "/amministrazione"):
        row = routes.get(path, {})
        if row.get("status") != "react_operational_full" or row.get("unlockFromGate") is not True:
            fail(f"{path} non e' react_operational_full/unlockFromGate true nel manifest.", failures)
    for path in ("/impostazioni", "/impostazioni-studio", "/sincronizzazione-calendari"):
        row = routes.get(path, {})
        if row.get("status") != "legacy_operational" or row.get("unlockFromGate") is not False:
            fail(f"{path} deve restare legacy_operational/unlockFromGate false.", failures)

    if failures:
        print("Tranche 26a API check FAILED:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("Tranche 26a studio/amministrazione API OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
