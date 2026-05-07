from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "react-migration"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_contains(source: str, expected: str, label: str, failures: list[str]) -> None:
    if expected not in source:
        failures.append(f"{label}: manca {expected!r}")


def main() -> int:
    failures: list[str] = []
    api = read("web/blueprints/api_v1_react.py")
    bridge = read("web/services/react_fatturazione_bridge.py")
    security = read("web/services/security_runtime.py")
    auth = read("pct/auth.py")

    check_contains(api, '@api_v1_react.get("/fatturazione/nuova")', "GET JSON nuova fatturazione", failures)
    check_contains(api, '@api_v1_react.post("/fatturazione/nuova")', "POST JSON nuova fatturazione", failures)
    check_contains(api, "def fatturazione_nuova_crea", "handler POST nuova fatturazione", failures)
    check_contains(api, "@_richiedi_auth", "autenticazione API React", failures)
    check_contains(api, "_request_json_object()", "POST accetta solo JSON", failures)
    check_contains(api, "_puo_scrivere_fatturazione()", "permesso backend scrittura", failures)
    check_contains(api, "create_react_fattura(", "riuso servizio bridge operativo", failures)
    check_contains(api, "get_utenti=get_utenti", "audit manager disponibile", failures)
    check_contains(api, "current_app.logger.exception", "errori server loggati senza stack nel JSON", failures)
    check_contains(security, '"api_v1_react.fatturazione_nuova_crea"', "CSRF endpoint React fatturazione", failures)
    check_contains(auth, '"fatturazione.leggi"', "permesso lettura fatturazione", failures)
    check_contains(auth, '"fatturazione.scrivi"', "permesso scrittura fatturazione", failures)

    check_contains(bridge, "def create_react_fattura", "servizio creazione React", failures)
    check_contains(bridge, "manager.crea(", "servizio riusa GestioneFatturazione.crea", failures)
    check_contains(bridge, "VoceParcella", "servizio riusa voce backend", failures)
    check_contains(bridge, "_CANONICAL_AMOUNT_FIELDS", "rifiuto importi canonici frontend", failures)
    check_contains(bridge, "_reject_canonical_fields(payload, errors)", "validazione importi canonici top-level", failures)
    check_contains(bridge, "_unknown_fields(payload, _TOP_LEVEL_FIELDS)", "rifiuto campi ignoti top-level", failures)
    check_contains(bridge, "_unknown_fields(raw_options, _FISCAL_OPTION_FIELDS)", "rifiuto opzioni fiscali ignote", failures)
    check_contains(bridge, "_unknown_fields(raw_item, _VOICE_FIELDS)", "rifiuto campi ignoti voce", failures)
    check_contains(bridge, "_audit_create", "audit creazione preservato", failures)
    check_contains(bridge, "registra_evento", "audit manager chiamato", failures)
    check_contains(bridge, '"writes": "json_api"', "contratto writes json_api", failures)
    check_contains(bridge, '"canonical_calculation": "backend"', "contratto calcolo canonico backend", failures)

    forbidden_generation = [
        "send_file(",
        "response.blob",
        "URL.createObjectURL",
        "new Blob",
        "genera_pdf",
        "genera_xml",
        "generatePdf",
        "generateXml",
    ]
    create_block = bridge[bridge.find("def create_react_fattura") :]
    for pattern in forbidden_generation:
        if pattern in create_block:
            failures.append(f"create_react_fattura non deve generare o restituire documenti: trovato {pattern!r}")

    for field in ["totale", "iva", "cassa_forense", "ritenuta", "netto_a_pagare", "imponibile", "base_iva"]:
        if field not in bridge:
            failures.append(f"campo canonico non presidiato nel reject set: {field}")

    body = [f"- {item}" for item in failures] if failures else ["API JSON nuova fatturazione verificata."]
    md = "\n".join([
        "# Check tranche 17A API nuova fatturazione",
        "",
        f"Generato: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Violazioni: {len(failures)}",
        "",
        *body,
        "",
    ])
    (ARTIFACT_DIR / "tranche-17a-fatturazione-nuova-api.md").write_text(md, encoding="utf-8")

    if failures:
        print(md)
        return 1
    print("Tranche 17A fatturazione nuova API OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
