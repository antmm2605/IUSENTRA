"""Confronta i namespace del decompilato Studio Telematico con IUSENTRA e gli XSD."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.busta import (  # noqa: E402
    CASSAZIONE_ALLEGATI_NS,
    CASSAZIONE_ATTI_NS,
    DATIATTO_ATTI_NS_BY_GENERATOR_CLASS,
    DATIATTO_ROOT_NS_BY_GENERATOR_CLASS,
    DATIATTO_V7_ATTI_GENERATOR_CLASSES,
    MINISTERIAL_ALLEGATI_NS,
    MINISTERIAL_ALLEGATI_V2_NS,
    MINISTERIAL_ATTI_NS,
    MINISTERIAL_ATTI_V7_NS,
    SIGP_ALLEGATI_NS,
    SIGP_ATTI_NS,
)
from pct.datiatto_unep import ALLEGATI_NS as UNEP_ALLEGATI_NS  # noqa: E402
from pct.datiatto_unep import ATTI_NS as UNEP_ATTI_NS  # noqa: E402
from pct.datiatto_unep import ROOT_NS as UNEP_ROOT_NS  # noqa: E402


ANNOTATION_NAMESPACE_RE = re.compile(
    r'Namespace\s*=\s*"(http://schemi\.processotelematico\.giustizia\.it/[^"]+)"'
)
XML_ROOT_NAMESPACE_RE = re.compile(
    r'\[XmlRoot\(Namespace\s*=\s*"(http://schemi\.processotelematico\.giustizia\.it/[^"]+)"'
)
ASSEMBLY_VERSION_RE = re.compile(r'AssemblyFileVersion\("([^"]+)"\)')
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "deposito-telematico"
    / "audit-schema-studio-telematico-2026-08-13.json"
)


def _default_decompiled_root() -> Path:
    configured = str(os.environ.get("IUSENTRA_STUDIO_TELEMATICO_DECOMPILED") or "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path("D:/tmp/qo-decomp-codex-20260812"),
        Path(os.environ.get("TEMP") or ".") / "quickorganizer_decompiled_full",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Decompilato Studio Telematico non trovato. Usa --decompiled-root con la cartella estratta."
    )


def _source_digest(source_files: list[Path], base: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(source_files):
        digest.update(path.relative_to(base).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _xsd_namespace_index() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in (ROOT / "docs" / "specs" / "ministero").rglob("*.xsd"):
        try:
            target = str(etree.parse(str(path)).getroot().get("targetNamespace") or "").strip()
        except (OSError, etree.XMLSyntaxError):
            continue
        if target:
            result.setdefault(target, []).append(path.relative_to(ROOT).as_posix())
    return {namespace: sorted(paths) for namespace, paths in result.items()}


def _iusentra_atti_namespace(generator_class: str) -> str:
    if generator_class in DATIATTO_ATTI_NS_BY_GENERATOR_CLASS:
        return DATIATTO_ATTI_NS_BY_GENERATOR_CLASS[generator_class]
    if generator_class in DATIATTO_V7_ATTI_GENERATOR_CLASSES:
        return MINISTERIAL_ATTI_V7_NS
    return MINISTERIAL_ATTI_NS


def _iusentra_allegati_namespace(atti_namespace: str) -> str:
    if atti_namespace == SIGP_ATTI_NS:
        return SIGP_ALLEGATI_NS
    if atti_namespace == CASSAZIONE_ATTI_NS:
        return CASSAZIONE_ALLEGATI_NS
    if atti_namespace == MINISTERIAL_ATTI_V7_NS:
        return MINISTERIAL_ALLEGATI_V2_NS
    return MINISTERIAL_ALLEGATI_NS


def audit_schema_namespaces(decompiled_root: Path) -> dict[str, Any]:
    source_files = sorted(decompiled_root.rglob("*.cs"))
    if not source_files:
        raise FileNotFoundError(f"Nessun sorgente C# trovato in {decompiled_root}.")

    namespaces_by_family: dict[str, set[str]] = {}
    root_namespaces_by_family: dict[str, set[str]] = {}
    all_namespaces: set[str] = set()
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        family = path.relative_to(decompiled_root).parts[0]
        namespaces = set(ANNOTATION_NAMESPACE_RE.findall(text))
        root_namespaces = set(XML_ROOT_NAMESPACE_RE.findall(text))
        namespaces_by_family.setdefault(family, set()).update(namespaces)
        root_namespaces_by_family.setdefault(family, set()).update(root_namespaces)
        all_namespaces.update(namespaces)

    xsd_index = _xsd_namespace_index()
    namespace_checks = [
        {
            "namespace": namespace,
            "presente": namespace in xsd_index,
            "xsd": xsd_index.get(namespace, []),
        }
        for namespace in sorted(all_namespaces)
    ]

    family_checks: list[dict[str, Any]] = []
    for generator_class, expected_root in sorted(DATIATTO_ROOT_NS_BY_GENERATOR_CLASS.items()):
        studio_roots = sorted(root_namespaces_by_family.get(generator_class, set()))
        studio_namespaces = namespaces_by_family.get(generator_class, set())
        expected_atti = _iusentra_atti_namespace(generator_class)
        expected_allegati = _iusentra_allegati_namespace(expected_atti)
        errors: list[str] = []
        if expected_root not in studio_roots:
            errors.append("namespace radice diverso dal decompilato")
        if expected_atti not in studio_namespaces:
            errors.append("namespace tipi/atti diverso dal decompilato")
        if expected_allegati not in studio_namespaces:
            errors.append("namespace tipi/allegati diverso dal decompilato")
        family_checks.append(
            {
                "famiglia": generator_class,
                "radice_iusentra": expected_root,
                "radici_studio_telematico": studio_roots,
                "atti_iusentra": expected_atti,
                "allegati_iusentra": expected_allegati,
                "ok": not errors,
                "errori": errors,
            }
        )

    unep_namespaces = namespaces_by_family.get("Atti_UNEP", set())
    unep_roots = root_namespaces_by_family.get("Atti_UNEP", set())
    unep_errors: list[str] = []
    if UNEP_ROOT_NS not in unep_roots:
        unep_errors.append("namespace radice UNEP diverso dal decompilato")
    if UNEP_ATTI_NS not in unep_namespaces:
        unep_errors.append("namespace tipi/atti UNEP diverso dal decompilato")
    if UNEP_ALLEGATI_NS not in unep_namespaces:
        unep_errors.append("namespace tipi/allegati UNEP diverso dal decompilato")
    family_checks.append(
        {
            "famiglia": "UNEP",
            "radice_iusentra": UNEP_ROOT_NS,
            "radici_studio_telematico": sorted(unep_roots),
            "atti_iusentra": UNEP_ATTI_NS,
            "allegati_iusentra": UNEP_ALLEGATI_NS,
            "ok": not unep_errors,
            "errori": unep_errors,
        }
    )

    assembly_info = decompiled_root / "Properties" / "AssemblyInfo.cs"
    assembly_text = assembly_info.read_text(encoding="utf-8", errors="ignore") if assembly_info.exists() else ""
    version_match = ASSEMBLY_VERSION_RE.search(assembly_text)
    missing_xsd = [row["namespace"] for row in namespace_checks if not row["presente"]]
    family_errors = [row for row in family_checks if not row["ok"]]
    return {
        "ok": not missing_xsd and not family_errors,
        "data_verifica": datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M"),
        "fonte_verita": "Studio Telematico decompilato",
        "versione_studio_telematico": version_match.group(1) if version_match else "non rilevata",
        "decompilato_sha256": _source_digest(source_files, decompiled_root),
        "sorgenti_cs": len(source_files),
        "namespace_annotati": len(namespace_checks),
        "namespace_con_xsd": sum(1 for row in namespace_checks if row["presente"]),
        "namespace_senza_xsd": missing_xsd,
        "famiglie_datiatto_verificate": len(family_checks),
        "famiglie_con_differenze": [row["famiglia"] for row in family_errors],
        "famiglie": family_checks,
        "schemi": namespace_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decompiled-root", default="")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    decompiled_root = Path(args.decompiled_root) if args.decompiled_root else _default_decompiled_root()
    report = audit_schema_namespaces(decompiled_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"famiglie", "schemi"}},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
