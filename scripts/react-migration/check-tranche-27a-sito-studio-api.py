from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    api = read("web/blueprints/api_v1_react.py")
    bridge = read("web/services/react_sito_studio_bridge.py")
    csrf = read("web/services/security_runtime.py")
    manifest = json.loads(read("tools/react-migration/route-manifest.json"))
    routes = {item["route"]: item for item in manifest.get("routes", [])}

    def require(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    require('@api_v1_react.get("/sito-studio")' in api, "Manca GET /api/v1/ui/sito-studio.")
    require('@api_v1_react.get("/sito-studio/contatti")' in api, "Manca GET /api/v1/ui/sito-studio/contatti.")
    require('@api_v1_react.get("/sito-studio/articoli/<int:article_id>/modifica")' in api, "Manca GET modifica articolo Sito Studio.")
    require('@api_v1_react.post("/sito-studio/articoli/<int:article_id>/modifica")' in api, "Manca POST modifica articolo Sito Studio.")
    require('@api_v1_react.post("/sito-studio/contatti/<id_contatto>/collega")' in api, "Manca POST collegamento contatto supportato.")
    require('@api_v1_react.post("/sito-studio/prenotazioni/<id_prenotazione>/stato")' in api, "Manca POST stato prenotazione supportato.")
    for unsupported in (
        '@api_v1_react.post("/sito-studio/contatti/<id_contatto>/stato")',
        '@api_v1_react.post("/sito-studio/contatti/<id_contatto>/archivia")',
        '@api_v1_react.post("/sito-studio/contatti/<id_contatto>/nota")',
        '@api_v1_react.post("/sito-studio/contatti/<id_contatto>/assegna")',
    ):
        require(unsupported not in api, f"Endpoint finto non supportato presente: {unsupported}.")
    require("_request_json_object()" in api, "POST Sito Studio devono accettare solo JSON.")
    require("sito_studio_contatto_collega" in csrf, "CSRF deve proteggere collegamento contatto.")
    require("sito_studio_prenotazione_stato" in csrf, "CSRF deve proteggere stato prenotazione.")
    require("sito_studio_articolo_modifica_salva" in csrf, "CSRF deve proteggere modifica articolo.")
    require(re.search(r"['\"]writes['\"]\s*:\s*['\"]none['\"]|writes\s*=\s*['\"]none['\"]", bridge) is not None, "Dashboard sito deve dichiarare writes none.")
    require(re.search(r"['\"]writes['\"]\s*:\s*['\"]json_api['\"]|writes\s*=\s*['\"]json_api['\"]", bridge) is not None, "Contatti sito devono dichiarare writes json_api.")
    require(re.search(r"['\"]operational['\"]\s*:\s*True", bridge) is not None, "Contratti sito devono dichiarare operational true.")
    require("create_lead_cliente_from_submission" in bridge, "Collegamento cliente deve riusare servizio legacy esistente.")
    require("audit_studio_site_action" in bridge, "Azioni supportate devono preservare audit legacy.")
    require("update_react_sito_articolo" in bridge, "Modifica articolo deve usare bridge React con salvataggio.")
    require("notifiche_non_introdotte" in bridge, "Payload deve dichiarare che non introduce notifiche.")
    require("automation" in bridge and "legacy_protected" in bridge, "Automazioni devono restare legacy protette.")
    require(routes.get("/sito-studio", {}).get("status") == "react_operational_full", "/sito-studio non e' react_operational_full.")
    require(routes.get("/sito-studio/contatti", {}).get("status") == "react_operational_full", "/sito-studio/contatti non e' react_operational_full.")
    require(routes.get("/sito-studio/articoli/:id/modifica", {}).get("status") == "react_operational_full", "/sito-studio/articoli/:id/modifica non e' react_operational_full.")
    builder = routes.get("/sito-studio/builder", {})
    require(builder.get("status") == "react_operational_full" and builder.get("unlockFromGate") is True, "/sito-studio/builder deve restare React operativo.")
    require(re.search(r"['\"](password|api_key|access_token|refresh_token|smtp_password|pec_password|password_hash|provider_secret|webhook_secret|stack_trace|traceback)['\"]\s*:", bridge, re.I) is None, "Bridge sito contiene chiavi sensibili.")

    if failures:
        print("Tranche 27a Sito Studio API check FAILED:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("Tranche 27a Sito Studio API OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
