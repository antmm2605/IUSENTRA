#!/usr/bin/env python3
"""Aggiorna `pct/data/cataloghi/codici_oggetto_pst.json` da XSD/PST ministeriali.

Compatibile con la documentazione Guida Pratica:

    python scripts/update_pst_xsd_catalog.py --download
    python scripts/update_pst_xsd_catalog.py --no-download --source ./XSD_SICI_20260116.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import ssl
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica.xsd_catalog_importer import (  # noqa: E402
    build_catalog_payload,
    load_kb_records,
    parse_xsd_bytes,
    records_from_zip_bytes,
)

DEFAULT_MANIFEST = ROOT / "pct" / "data" / "cataloghi" / "pst_xsd_sources.json"
DEFAULT_OUTPUT = ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst.json"
DEFAULT_KB = ROOT / "pct" / "data" / "legal_knowledge_base.json"
DEFAULT_DOWNLOAD_DIR = ROOT / "data" / "pst_xsd_downloads"
USER_AGENT = "IUSENTRA-PST-XSD-Updater/1.0"


def load_manifest(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"sources": []}
    return [row for row in payload.get("sources", []) if isinstance(row, dict) and row.get("download_url")]


def download(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / (Path(url.split("?", 1)[0]).name or "pst_xsd.bin")
    if target.exists() and target.stat().st_size:
        return target
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream,*/*"})
    with urlopen(req, timeout=60, context=ssl.create_default_context()) as response:  # noqa: S310 - URL ufficiali/configurati.
        target.write_bytes(response.read())
    return target


def parse_source(path: Path, *, package_key: str, package_label: str):
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return records_from_zip_bytes(data, archive_name=path.name, package_key=package_key, package_label=package_label)
    if suffix in {".xsd", ".xml"}:
        return parse_xsd_bytes(data, file_name=path.name, package_key=package_key, package_label=package_label)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Scarica le sorgenti del manifest PST.")
    parser.add_argument("--no-download", action="store_true", help="Non scarica dal manifest; usa solo --source e KB.")
    parser.add_argument("--source", action="append", default=[], help="ZIP/XSD/XML locale già scaricato; ripetibile.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--kb", default=str(DEFAULT_KB))
    parser.add_argument("--download-dir", default=str(DEFAULT_DOWNLOAD_DIR))
    parser.add_argument("--fail-if-empty", action="store_true")
    args = parser.parse_args()

    records = []
    diagnostics = []
    manifest_sources = load_manifest(Path(args.manifest))
    input_sources: list[tuple[Path, str, str]] = []
    for idx, source in enumerate(args.source, start=1):
        input_sources.append((Path(source), f"local_{idx}", Path(source).name))

    if args.download and not args.no_download:
        for row in manifest_sources:
            try:
                path = download(str(row["download_url"]), Path(args.download_dir))
                input_sources.append((path, str(row.get("id") or path.stem), str(row.get("label") or path.name)))
                diagnostics.append({"source": row.get("label"), "downloaded": True, "path": str(path)})
            except Exception as exc:
                diagnostics.append({"source": row.get("label"), "downloaded": False, "error": str(exc)})

    for path, key, label in input_sources:
        if not path.exists():
            diagnostics.append({"source": str(path), "records": 0, "error": "file non trovato"})
            continue
        parsed = parse_source(path, package_key=key, package_label=label)
        records.extend(parsed)
        diagnostics.append({"source": str(path), "records": len(parsed)})

    kb_records = load_kb_records(args.kb)
    records.extend(kb_records)
    diagnostics.append({"source": str(args.kb), "records": len(kb_records), "kind": "legal_kb"})

    payload = build_catalog_payload(records, source_label="PST/XSD ministeriali + legal KB")
    payload["diagnostics"] = diagnostics
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": bool(payload["records_count"]), "output": str(output), "records": payload["records_count"], "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    if args.fail_if_empty and not payload["records_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
