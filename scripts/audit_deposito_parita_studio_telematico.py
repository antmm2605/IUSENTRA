"""Confronto nominativo dei 270 tipi con Studio Telematico decompilato."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generate_quickorganizer_analysis_artifacts import FORM, extract_datiatto

from pct.deposito_telematico_catalogo import list_deposit_catalog_entries


DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "deposito-telematico"
    / "audit-parita-studio-telematico-270-2026-08-11.json"
)


def _json_marker(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _root_pairs(values: list[Any]) -> list[list[str]]:
    roots: set[tuple[str, str]] = set()
    for value in values:
        if isinstance(value, dict):
            type_name = str(value.get("type") or "")
            variable = str(value.get("variable") or "")
        else:
            parts = [part for part in str(value).split(".") if part]
            type_name = parts[-2] if len(parts) >= 2 else (parts[0] if parts else "")
            variable = parts[-1] if len(parts) >= 2 else ""
        roots.add((type_name.split(".")[-1], variable))
    return [list(item) for item in sorted(roots)]


def _source_for(entry: dict[str, Any], source_by_key: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    aliases = entry.get("quickOrganizer", {}).get("aliases", [])
    for key in [entry.get("key"), *aliases]:
        candidate = str(key or "")
        if candidate in source_by_key:
            return candidate, source_by_key[candidate]
    return "", None


def audit_parity() -> dict[str, Any]:
    _, _, source_by_key = extract_datiatto()
    entries = list(list_deposit_catalog_entries())
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for entry in entries:
        key = str(entry.get("key") or "")
        schema = entry.get("schema") if isinstance(entry.get("schema"), dict) else {}
        rules = entry.get("rules") if isinstance(entry.get("rules"), dict) else {}
        source_key, source = _source_for(entry, source_by_key)
        differences: list[str] = []
        if source is None:
            differences.append("chiave non risolta nel decompilato")
        else:
            comparisons = {
                "metodi DatiAtto": (
                    sorted(set(schema.get("evidenceMethods") or [])),
                    sorted(set(source.get("methods") or [])),
                ),
                "radici DatiAtto": (
                    _root_pairs(schema.get("evidenceRoots") or []),
                    _root_pairs(source.get("saved_roots") or []),
                ),
                "dati richiesti": (
                    sorted(set(schema.get("quickRequiredData") or [])),
                    sorted(set(source.get("required_data") or [])),
                ),
                "flag percorso": (
                    schema.get("quickDepositFlags") or {},
                    source.get("flags") or {},
                ),
                "codici oggetto fissi": (
                    schema.get("quickFixedObjectCodes") or [],
                    source.get("fixed_object_codes") or [],
                ),
                "controlli sorgente": (
                    schema.get("quickControls") or [],
                    source.get("controls") or [],
                ),
                "combo sorgente": (
                    schema.get("quickComboSources") or [],
                    source.get("combo_sources") or [],
                ),
                "assegnazioni sorgente": (
                    schema.get("quickAssignments") or [],
                    source.get("assignments") or [],
                ),
            }
            for label, (actual, expected) in comparisons.items():
                if _json_marker(actual) != _json_marker(expected):
                    differences.append(label)

        channel = str(rules.get("channel_kind") or "")
        expected_transport = {
            "indice_busta_mode": "interno_datiatto",
            "document_signature_profile": "pdf_pades_non_pdf_cades",
            "datiatto_signature_profile": "cades_bes_sha256_signing_certificate_v2",
            "mime_disposition": "attachment",
            "requires_atto_enc": True,
            "server_smtp_allowed": False,
        }
        for field, expected in expected_transport.items():
            if rules.get(field) != expected:
                differences.append(f"trasporto {field}")

        if differences:
            errors.append(f"{key}: " + ", ".join(differences))
        results.append(
            {
                "key": key,
                "source_key": source_key,
                "macroarea": entry.get("macro"),
                "categoria": entry.get("category"),
                "canale": channel,
                "metodo_datiatto": list(schema.get("evidenceMethods") or []),
                "radice_ministeriale": schema.get("ministerialRoot"),
                "profilo_firma_documenti": rules.get("document_signature_profile"),
                "profilo_firma_datiatto": rules.get("datiatto_signature_profile"),
                "indice_busta": rules.get("indice_busta_mode"),
                "parita": not differences,
                "differenze": differences,
            }
        )

    area_counts = dict(Counter(str(entry.get("macro") or "") for entry in entries))
    channel_counts = dict(Counter(str(entry.get("rules", {}).get("channel_kind") or "") for entry in entries))
    return {
        "ok": len(entries) == 270 and not errors,
        "data_verifica": datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M"),
        "fonte_verita": "Studio Telematico 2026 Rel. 021 - FormSentMailBee.cs decompilato",
        "fonte_sha256": hashlib.sha256(FORM.read_bytes()).hexdigest(),
        "totale": len(entries),
        "macroaree": area_counts,
        "canali": channel_counts,
        "tipi_con_parita": sum(1 for result in results if result["parita"]),
        "tipi_con_differenze": sum(1 for result in results if not result["parita"]),
        "errori": errors,
        "tipi": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    report = audit_parity()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "tipi"}, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
