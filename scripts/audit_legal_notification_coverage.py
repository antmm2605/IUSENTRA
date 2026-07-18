from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.notifiche_legali import (
    PUBLIC_PEC_REGISTERS,
    UNEP_NOTIFICATION_TYPES,
    UNEP_REQUEST_TYPES,
    normalise_public_register,
    public_register_capability,
)
from pct.uffici_giudiziari import get_gestore, indirizzi_telematici_ufficio
from web.services.react_notifiche_legali_bridge import _unep_office_catalog


EXPECTED_UNEP_SCHEMAS = {
    "Atti_UNEP::AttoCivileAPagamento",
    "Atti_UNEP::AttoPenaleAPagamento",
    "Atti_UNEP::AttoCivileDebito",
    "Atti_UNEP::AttoPenaleDebito",
    "Atti_UNEP::AttoEsenteLavoro",
    "Atti_UNEP::PagamentoRichiestaNotifica",
    "Atti_UNEP::RichiestaPignoramentoMobiliare",
    "Atti_UNEP::RichiestaPignoramentoMobiliareADebito",
    "Atti_UNEP::RichiestaPignoramentoMobiliareMateriaLavoro",
    "Atti_UNEP::RichiestaPignoramentoImmobiliare",
    "Atti_UNEP::RichiestaPignoramentoImmobiliareADebito",
    "Atti_UNEP::RichiestaPignoramentoImmobiliareMateriaLavoro",
    "Atti_UNEP::RichiestaPignoramentoPressoTerzi",
    "Atti_UNEP::RichiestaPignoramentoPressoTerziADebito",
    "Atti_UNEP::RichiestaPignoramentoPressoTerziMateriaLavoro",
    "Atti_UNEP::PagamentoRichiestaPignoramento",
    "Atti_UNEP::RichiestaRicercaBeni",
    "Atti_UNEP::RichiestaRestituzioneSomme",
}


def _duplicate_values(rows: list[dict[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        value = str(row.get(field) or "").strip().lower()
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def run_audit() -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    manager = get_gestore()
    offices = [row for row in manager.carica() if str(row.get("tipo") or "").upper() == "UNEP"]
    ui_offices = _unep_office_catalog()
    source_by_code = {
        str(row.get("codice_ministero") or row.get("codice") or "").strip(): row
        for row in offices
    }
    ui_by_code = {str(row.get("codice") or "").strip(): row for row in ui_offices}

    missing_codes = sorted(set(source_by_code) - set(ui_by_code))
    extra_codes = sorted(set(ui_by_code) - set(source_by_code))
    if missing_codes or extra_codes:
        failures.append({
            "check": "catalogo_ui_unep",
            "missingCodes": missing_codes,
            "extraCodes": extra_codes,
        })

    incomplete: list[dict[str, str]] = []
    wrong_usage: list[dict[str, str]] = []
    mismatches: list[dict[str, str]] = []
    for code, office in source_by_code.items():
        name = str(office.get("nome") or office.get("descrizione_ministero") or "").strip()
        pec = str(office.get("pec") or office.get("pec_ministero") or "").strip().lower()
        if not code or not name or not pec or "@" not in pec:
            incomplete.append({"codice": code, "nome": name, "pec": pec})
        addresses = indirizzi_telematici_ufficio(office)
        if not addresses or str(addresses[0].get("uso") or "") != "richiesta_unep":
            wrong_usage.append({"codice": code, "nome": name})
        ui_row = ui_by_code.get(code) or {}
        if ui_row and (
            str(ui_row.get("nome") or "").strip() != name
            or str(ui_row.get("pec") or "").strip().lower() != pec
        ):
            mismatches.append({
                "codice": code,
                "sourceName": name,
                "uiName": str(ui_row.get("nome") or ""),
                "sourcePec": pec,
                "uiPec": str(ui_row.get("pec") or ""),
            })
    if incomplete:
        failures.append({"check": "campi_obbligatori_uffici_unep", "rows": incomplete})
    if wrong_usage:
        failures.append({"check": "uso_pec_unep", "rows": wrong_usage})
    if mismatches:
        failures.append({"check": "corrispondenza_ui_catalogo_unep", "rows": mismatches})

    duplicate_codes = _duplicate_values(ui_offices, "codice")
    duplicate_pec = _duplicate_values(ui_offices, "pec")
    if duplicate_codes:
        failures.append({"check": "codici_unep_univoci", "duplicates": duplicate_codes})
    if duplicate_pec:
        failures.append({"check": "pec_unep_univoche", "duplicates": duplicate_pec})

    actual_schemas = {str(item.get("schema") or "") for item in UNEP_REQUEST_TYPES.values()}
    if actual_schemas != EXPECTED_UNEP_SCHEMAS:
        failures.append({
            "check": "tipi_richiesta_unep",
            "missingSchemas": sorted(EXPECTED_UNEP_SCHEMAS - actual_schemas),
            "extraSchemas": sorted(actual_schemas - EXPECTED_UNEP_SCHEMAS),
        })
    expected_channels = {"mani", "posta", "estero", "telematica"}
    if set(UNEP_NOTIFICATION_TYPES) != expected_channels:
        failures.append({
            "check": "canali_notifica_unep",
            "missingChannels": sorted(expected_channels - set(UNEP_NOTIFICATION_TYPES)),
            "extraChannels": sorted(set(UNEP_NOTIFICATION_TYPES) - expected_channels),
        })

    required_examples = {
        "08004302238": "unep.tribunale.locri@civile.ptel.giustiziacert.it",
        "08005702237": "unep.tribunale.palmi@civile.ptel.giustiziacert.it",
        "02411602235": "unep.tribunale.vicenza@civile.ptel.giustiziacert.it",
    }
    missing_examples = {
        code: expected
        for code, expected in required_examples.items()
        if str(ui_by_code.get(code, {}).get("pec") or "").lower() != expected
    }
    if missing_examples:
        failures.append({"check": "casi_reali_unep", "mismatches": missing_examples})

    expected_register_modes = {
        "reginde": ("authenticated_service", True, True),
        "registro_ppaa": ("assisted_browser", False, True),
        "ini_pec": ("assisted_browser", False, True),
        "registro_imprese": ("assisted_browser", False, True),
        "inad": ("assisted_browser", False, True),
        "anpr": ("not_notification_register", False, False),
        "altro_pubblico_elenco": ("documented_manual", False, True),
    }
    register_mismatches: list[dict[str, Any]] = []
    for source, (mode, automatic, valid) in expected_register_modes.items():
        capability = public_register_capability(source)
        if (
            capability["verification_mode"] != mode
            or capability["automatic"] is not automatic
            or capability["valid_for_notification"] is not valid
        ):
            register_mismatches.append({"source": source, "capability": capability})
        if mode == "assisted_browser" and not capability["official_url"]:
            register_mismatches.append({"source": source, "error": "official_url_missing"})
    if set(PUBLIC_PEC_REGISTERS) != set(expected_register_modes):
        register_mismatches.append({
            "error": "register_catalog_mismatch",
            "missing": sorted(set(expected_register_modes) - set(PUBLIC_PEC_REGISTERS)),
            "extra": sorted(set(PUBLIC_PEC_REGISTERS) - set(expected_register_modes)),
        })
    if normalise_public_register("IPA") != "ipa" or normalise_public_register("IPA") in PUBLIC_PEC_REGISTERS:
        register_mismatches.append({"error": "ipa_must_not_alias_registro_ppaa"})
    if register_mismatches:
        failures.append({"check": "pubblici_elenchi_notifica", "rows": register_mismatches})

    return {
        "ok": not failures,
        "sourceOfTruth": "catalogo_uffici_pst",
        "counts": {
            "ufficiUnep": len(offices),
            "ufficiUnepUi": len(ui_offices),
            "tipiRichiestaUnep": len(UNEP_REQUEST_TYPES),
            "canaliNotificaUnep": len(UNEP_NOTIFICATION_TYPES),
            "pubbliciElenchi": len(PUBLIC_PEC_REGISTERS),
        },
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica catalogo, canali e tipi di richiesta del flusso UNEP.",
    )
    parser.add_argument("--output", type=Path, help="Scrive anche il risultato in un file JSON.")
    args = parser.parse_args(argv)
    result = run_audit()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
