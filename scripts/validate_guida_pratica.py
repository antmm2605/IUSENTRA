#!/usr/bin/env python3
"""Valida la Guida Pratica e la copertura dei codici ufficiali PST/XSD."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica import GuidaPraticaService  # noqa: E402
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry, list_codici_oggetto_pst  # noqa: E402


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=str(ROOT / "pct" / "data" / "legal_knowledge_base.full.json"))
    parser.add_argument("--fail-on-generated", action="store_true", help="Fallisce se esistono codici ufficiali senza guida curata.")
    parser.add_argument("--require-official-curated", action="store_true", help="Richiede copertura curata al 100%% dei codici ufficiali PST/XSD.")
    parser.add_argument("--report", default="", help="Scrive il report JSON dell'audit.")
    parser.add_argument("--missing-guidance-csv", default="", help="Scrive il CSV dei codici ufficiali senza guida curata.")
    args = parser.parse_args()

    service = GuidaPraticaService(kb_path=args.kb)
    catalog = service.list_guidance(limit=20000)
    official_codes = {str(row.get("codice") or "").strip() for row in list_codici_oggetto_pst()}
    summary: dict[str, int] = {}
    missing_required: list[str] = []
    generated_official: list[dict[str, object]] = []
    partial: list[str] = []
    aliases_or_internal: list[dict[str, object]] = []
    deposit_incoherent: list[dict[str, object]] = []

    for row in catalog:
        coverage = row.get("coverage") if isinstance(row.get("coverage"), dict) else {}
        level = str(coverage.get("level") or "sconosciuta")
        summary[level] = summary.get(level, 0) + 1
        codice = str(row.get("codice") or "")
        guida = service.get_guidance(codice)
        atto = guida.get("atto_principale") if isinstance(guida.get("atto_principale"), dict) else {}
        deposit = guida.get("codice_deposito") if isinstance(guida.get("codice_deposito"), dict) else {}
        official = codice_oggetto_pst_entry(codice)
        depositabile = bool(deposit.get("depositabile"))

        if not atto.get("campi_obbligatori"):
            missing_required.append(codice)
        if level == "curata_parziale":
            partial.append(codice)
        if official and level != "curata":
            generated_official.append(
                {
                    "codice": codice,
                    "descrizione": official.get("descrizione") or guida.get("denominazione") or row.get("denominazione") or "",
                    "coverage": level,
                    "area": official.get("area_label") or official.get("area") or "",
                    "parent_codice": official.get("parent_codice") or "",
                    "parent_label": official.get("parent_label") or "",
                    "file_fonte": official.get("file_fonte") or row.get("file_fonte") or "",
                }
            )
        if not official:
            aliases_or_internal.append(
                {
                    "codice": codice,
                    "denominazione": guida.get("denominazione") or row.get("denominazione") or "",
                    "coverage": level,
                    "depositabile": depositabile,
                }
            )
        if bool(official) != depositabile:
            deposit_incoherent.append(
                {
                    "codice": codice,
                    "nel_catalogo_ministeriale": bool(official),
                    "marcato_depositabile": depositabile,
                    "denominazione": guida.get("denominazione") or row.get("denominazione") or "",
                }
            )

    kb_codes = {str(row.get("codice") or "") for row in catalog}
    official_missing_from_service = sorted(official_codes - kb_codes)
    report = {
        "ok": not missing_required and not deposit_incoherent and not official_missing_from_service and not generated_official,
        "coverage": summary,
        "catalog_size": service.catalog_size(),
        "official_catalog_size": service.official_catalog_size(),
        "missing_required": missing_required[:100],
        "official_coverage": {
            "total_official_codes": len(official_codes),
            "official_codes_curated": len(official_codes) - len(generated_official) - len(official_missing_from_service),
            "official_codes_without_curated_guidance": len(generated_official) + len(official_missing_from_service),
            "official_without_curated_guidance_details": generated_official,
            "official_missing_from_service": official_missing_from_service,
        },
        "deposit_code_coherence": {
            "ok": not deposit_incoherent,
            "incoherent": deposit_incoherent,
            "aliases_or_internal_count": len(aliases_or_internal),
            "aliases_or_internal": aliases_or_internal,
        },
        "partial_count": len(partial),
    }

    if args.report:
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.missing_guidance_csv:
        csv_path = Path(args.missing_guidance_csv)
        if not csv_path.is_absolute():
            csv_path = ROOT / csv_path
        _write_csv(
            csv_path,
            generated_official,
            ["codice", "descrizione", "coverage", "area", "parent_codice", "parent_label", "file_fonte"],
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if missing_required:
        return 2
    if deposit_incoherent or official_missing_from_service:
        return 4
    if generated_official and (args.fail_on_generated or args.require_official_curated):
        return 3
    if generated_official:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
