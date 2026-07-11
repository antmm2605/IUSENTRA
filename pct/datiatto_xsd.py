"""Validazione di DatiAtto.xml sugli schemi ministeriali in esercizio."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from lxml import etree


_XSD_NS = "http://www.w3.org/2001/XMLSchema"
_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_ROOTS = (
    _ROOT / "docs" / "specs" / "ministero" / "xsd" / "2026-05-12-sici",
    _ROOT / "docs" / "specs" / "ministero" / "schema" / "sigp_v3",
    _ROOT / "docs" / "specs" / "ministero" / "parte" / "parte_v13",
)


@dataclass(frozen=True)
class DatiAttoXsdValidation:
    ok: bool
    root_namespace: str
    root_name: str
    schema_path: str
    errors: tuple[str, ...]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(_ROOT))
    except ValueError:
        return str(path)


def _schema_files() -> Iterable[Path]:
    for root in _SCHEMA_ROOTS:
        if root.exists():
            yield from root.rglob("*.xsd")


@lru_cache(maxsize=1)
def _global_element_index() -> dict[tuple[str, str], tuple[Path, ...]]:
    index: dict[tuple[str, str], list[Path]] = {}
    for path in _schema_files():
        try:
            schema_root = etree.parse(str(path)).getroot()
        except (OSError, etree.XMLSyntaxError):
            continue
        namespace = str(schema_root.get("targetNamespace") or "")
        for element in schema_root.findall(f"{{{_XSD_NS}}}element"):
            name = str(element.get("name") or "").strip()
            if name:
                index.setdefault((namespace, name), []).append(path)
    return {key: tuple(paths) for key, paths in index.items()}


@lru_cache(maxsize=256)
def _compiled_schema(path: Path) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(path)))


def validate_datiatto_xml(payload: bytes | str) -> DatiAttoXsdValidation:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    try:
        root = etree.fromstring(raw)
    except (TypeError, ValueError, etree.XMLSyntaxError) as exc:
        return DatiAttoXsdValidation(
            ok=False,
            root_namespace="",
            root_name="",
            schema_path="",
            errors=(f"XML non leggibile: {exc}",),
        )

    qname = etree.QName(root)
    namespace = str(qname.namespace or "")
    name = str(qname.localname or "")
    candidates = _global_element_index().get((namespace, name), ())
    if not candidates:
        return DatiAttoXsdValidation(
            ok=False,
            root_namespace=namespace,
            root_name=name,
            schema_path="",
            errors=("Nessuno schema ministeriale attivo dichiara questa radice e questo namespace.",),
        )

    best_path = candidates[0]
    best_errors: tuple[str, ...] = ()
    for path in candidates:
        try:
            schema = _compiled_schema(path)
        except (OSError, etree.XMLSchemaParseError, etree.XMLSyntaxError) as exc:
            errors = (f"Schema non compilabile: {exc}",)
        else:
            if schema.validate(root):
                return DatiAttoXsdValidation(
                    ok=True,
                    root_namespace=namespace,
                    root_name=name,
                    schema_path=_relative(path),
                    errors=(),
                )
            errors = tuple(entry.message for entry in schema.error_log)
        if not best_errors or len(errors) < len(best_errors):
            best_path = path
            best_errors = errors

    return DatiAttoXsdValidation(
        ok=False,
        root_namespace=namespace,
        root_name=name,
        schema_path=_relative(best_path),
        errors=best_errors or ("Il DatiAtto.xml non rispetta lo schema ministeriale.",),
    )


def clear_datiatto_xsd_caches() -> None:
    _compiled_schema.cache_clear()
    _global_element_index.cache_clear()
