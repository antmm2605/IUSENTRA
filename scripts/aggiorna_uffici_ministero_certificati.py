"""Arricchisce i riferimenti ministeriali con i metadati certificato PST.

Usa ListaUfficiGiudiziari.xml, la stessa fonte QuickOrganizer/PST già usata
per codice ministeriale, PEC e servizi, e copia nel registro IUSENTRA il nome
del certificato di cifratura quando il catalogo lo espone.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _text(node: ET.Element, tag: str) -> str:
    return (node.findtext(tag) or "").strip()


def _certificati_da_xml(path: Path) -> dict[str, dict[str, str]]:
    root = ET.parse(path).getroot()
    by_code: dict[str, dict[str, str]] = {}
    for return_node in root.iter("return"):
        codice = _text(return_node, "codiceUfficio")
        if not codice:
            continue
        by_code[codice] = {
            "nome_certificato_cifra": _text(return_node, "nomeCertificatoCifra"),
            "certificato_mimetype": _text(return_node, "certificatoMimetype"),
        }
    return by_code


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _update_records(records: Any, certs: dict[str, dict[str, str]]) -> dict[str, int]:
    updated = 0
    with_name = 0
    total = 0
    iterable = records.values() if isinstance(records, dict) else records
    for record in iterable:
        if not isinstance(record, dict):
            continue
        codice = str(record.get("codice_ministero") or record.get("codice") or "").strip()
        if not codice or codice not in certs:
            continue
        total += 1
        source = certs[codice]
        for key in ("nome_certificato_cifra", "certificato_mimetype"):
            value = source.get(key, "")
            if record.get(key) != value:
                record[key] = value
                updated += 1
        if source.get("nome_certificato_cifra"):
            with_name += 1
    return {"records": total, "updated_fields": updated, "with_name": with_name}


def aggiorna(
    *,
    input_xml: Path,
    riferimenti_json: Path,
    extra_json: Path,
) -> dict[str, Any]:
    certs = _certificati_da_xml(input_xml)
    riferimenti = _load_json(riferimenti_json)
    extra = _load_json(extra_json)

    main_stats = _update_records(riferimenti.get("uffici") or {}, certs)
    extra_stats = _update_records(extra.get("uffici") or [], certs)

    riferimenti["fonte_certificati"] = str(input_xml)
    extra["fonte_certificati"] = str(input_xml)
    _write_json(riferimenti_json, riferimenti)
    _write_json(extra_json, extra)

    return {
        "ok": True,
        "input": str(input_xml),
        "certificati_xml": len(certs),
        "riferimenti": main_stats,
        "extra": extra_stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=r"C:\QuickOrganizer\ListaUfficiGiudiziari.xml")
    parser.add_argument("--riferimenti", default="pct/data/uffici_ministero.json")
    parser.add_argument("--extra", default="pct/data/uffici_ministero_extra.json")
    args = parser.parse_args()
    result = aggiorna(
        input_xml=Path(args.input),
        riferimenti_json=Path(args.riferimenti),
        extra_json=Path(args.extra),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
