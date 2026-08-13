"""Estrae le tabelle ufficio/registro/rito usate da Studio Telematico.

La fonte e' ``ListaUfficiGiudiziari.xml`` distribuita con QuickOrganizer.
Il risultato non contiene dati di pratiche o clienti: conserva soltanto le
tabelle pubbliche necessarie a verificare la destinazione di una busta.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lxml import etree


SOURCE_CANDIDATES = (
    Path(r"D:\QuickOrganizer\ListaUfficiGiudiziari.xml"),
    Path(r"C:\QuickOrganizer\ListaUfficiGiudiziari.xml"),
)
QC_CANDIDATES = (
    Path(r"D:\QuickOrganizer\QC_Uffici.xml"),
    Path(r"C:\QuickOrganizer\QC_Uffici.xml"),
)


def _first_existing(candidates: tuple[Path, ...]) -> Path:
    return next((path for path in candidates if path.exists()), candidates[0])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(node: etree._Element, localname: str) -> str:
    result = node.xpath(f"string(./*[local-name()='{localname}'])")
    return str(result or "").strip()


def _unique_dicts(rows: list[dict[str, str]], keys: tuple[str, ...]) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    result: list[dict[str, str]] = []
    for row in rows:
        marker = tuple(str(row.get(key) or "") for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(row)
    return result


def extract(source: Path, qc_source: Path | None = None) -> dict[str, Any]:
    root = etree.parse(str(source)).getroot()
    offices: list[dict[str, Any]] = []
    for office in root.xpath("//*[local-name()='return']"):
        services: list[str] = []
        registries: list[dict[str, str]] = []
        rites: list[dict[str, str]] = []
        for service in office.xpath("./*[local-name()='servizi']"):
            service_code = _text(service, "codice").upper()
            if service_code and service_code not in services:
                services.append(service_code)
            for registry in service.xpath("./*[local-name()='registri']"):
                registries.append(
                    {
                        "service": service_code,
                        "code": _text(registry, "codice").upper(),
                        "application": _text(registry, "codiceApplicazione").lower(),
                        "label": _text(registry, "descrizione"),
                    }
                )
            for rite in service.xpath("./*[local-name()='serviziAtti']"):
                rites.append(
                    {
                        "service": service_code,
                        "rite": _text(rite, "rito"),
                        "grade": _text(rite, "grado"),
                        "activation_date": _text(rite, "dataDecreto"),
                    }
                )
        if not services:
            continue
        offices.append(
            {
                "code": _text(office, "codiceUfficio"),
                "name": _text(office, "descrizione"),
                "type": _text(office, "tipoUfficio").upper(),
                "pec": _text(office, "indirizzoPec").lower(),
                "city": _text(office, "comune"),
                "district": _text(office, "distretto"),
                "services": services,
                "registries": _unique_dicts(registries, ("service", "code", "application")),
                "rites": _unique_dicts(rites, ("service", "rite", "grade")),
            }
        )
    offices.sort(key=lambda item: (item["code"], item["name"]))

    qc_rows = 0
    qc_codes: set[str] = set()
    if qc_source and qc_source.exists():
        qc_root = etree.parse(str(qc_source)).getroot()
        for row in qc_root.xpath("//*[local-name()='row']"):
            qc_rows += 1
            for prop in row.xpath("./*[local-name()='property']"):
                if str(prop.get("name") or "").upper() == "CODICEUFFICIO":
                    value = str(prop.get("value") or prop.text or "").strip()
                    if value:
                        qc_codes.add(value)

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "path": str(source),
            "sha256": _sha256(source),
            "size_bytes": source.stat().st_size,
        },
        "qc_source": {
            "path": str(qc_source or ""),
            "sha256": _sha256(qc_source) if qc_source and qc_source.exists() else "",
            "size_bytes": qc_source.stat().st_size if qc_source and qc_source.exists() else 0,
            "rows": qc_rows,
            "unique_office_codes": len(qc_codes),
        },
        "counts": {
            "offices_with_services": len(offices),
            "offices_with_deposit_service": sum("DEPOT" in row["services"] for row in offices),
            "offices_with_pec": sum(bool(row["pec"]) for row in offices),
            "registry_rows": sum(len(row["registries"]) for row in offices),
            "rite_rows": sum(len(row["rites"]) for row in offices),
        },
        "offices": offices,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(_first_existing(SOURCE_CANDIDATES)))
    parser.add_argument("--qc-source", default=str(_first_existing(QC_CANDIDATES)))
    parser.add_argument(
        "--output",
        default="pct/data/cataloghi/studio_telematico_uffici_deposito.json",
    )
    args = parser.parse_args()
    payload = extract(Path(args.source), Path(args.qc_source))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output.resolve()), **payload["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
