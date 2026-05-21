#!/usr/bin/env python3
"""Compatibilità: importa codici oggetto PST dagli XSD/XLSX ministeriali.

Questo wrapper mantiene il nome operativo usato nella prima bozza della patch e
riusa il parser canonico `pct.guida_pratica.xsd_catalog_importer`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica.xsd_catalog_importer import (  # noqa: E402
    build_catalog_payload,
    load_kb_records,
    parse_xsd_bytes,
    records_from_path,
)

DEFAULT_OUTPUT = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst.json"
DEFAULT_KB = ROOT / "pct" / "data" / "legal_knowledge_base.json"


def parse_xsd_file(path: str | Path):
    path = Path(path)
    return [record.to_json() for record in parse_xsd_bytes(path.read_bytes(), file_name=path.name, package_key="local", package_label="File locale")]


def merge_records(records):
    from pct.guida_pratica.xsd_catalog_importer import CatalogRecord

    converted = []
    for row in records:
        if isinstance(row, CatalogRecord):
            converted.append(row)
        elif isinstance(row, dict):
            converted.append(
                CatalogRecord(
                    codice=str(row.get("codice") or ""),
                    descrizione=str(row.get("descrizione") or ""),
                    area=str(row.get("area") or row.get("area_label") or ""),
                    codicePadre=str(row.get("codicePadre") or row.get("parent_codice") or ""),
                    descrizionePadre=str(row.get("descrizionePadre") or row.get("parent_label") or ""),
                    registri=row.get("registri") if isinstance(row.get("registri"), list) else [str(row.get("registri") or "")],
                    fileFonte=str(row.get("fileFonte") or row.get("file_fonte") or ""),
                )
            )
    payload = build_catalog_payload(converted, source_label="wrapper")
    return payload["records"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--kb", default=str(DEFAULT_KB))
    parser.add_argument("--source-file", "--source", action="append", default=[])
    parser.add_argument("--source-url", action="append", default=[], help="Non scaricato da questo wrapper; usare scripts/update_pst_xsd_catalog.py --download per il manifest ufficiale.")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--fail-if-empty", action="store_true")
    args = parser.parse_args()

    records = []
    for source in args.source_file:
        records.extend(records_from_path(source))
    records.extend(load_kb_records(args.kb))
    payload = build_catalog_payload(records, source_label="PST/XSD ministeriali + legal KB")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": bool(payload["records"]), "output": str(output), "records": len(payload["records"])}, ensure_ascii=False, indent=2))
    if args.fail_if_empty and not payload["records"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
