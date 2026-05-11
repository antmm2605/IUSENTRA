"""Catalogo versionato dei codici oggetto PST usati dalle pratiche collegate."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "pratiche_collegate_catalog.json"


def _text(value: Any) -> str:
    return str(value or "").strip()


@lru_cache(maxsize=1)
def load_pratiche_collegate_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _walk_items(items: list[dict[str, Any]], *, area: str, area_label: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in items:
        codice = _text(item.get("codice"))
        label = _text(item.get("label"))
        children = item.get("children") if isinstance(item.get("children"), list) else []
        if children:
            for child in children:
                child_code = _text(child.get("codice"))
                child_label = _text(child.get("label"))
                if child_code and child_label:
                    out.append(
                        {
                            "codice": child_code,
                            "descrizione": child_label,
                            "area": area,
                            "area_label": area_label,
                            "parent_codice": codice,
                            "parent_label": label,
                        }
                    )
            continue
        if codice and label:
            out.append(
                {
                    "codice": codice,
                    "descrizione": label,
                    "area": area,
                    "area_label": area_label,
                    "parent_codice": "",
                    "parent_label": "",
                }
            )
    return out


@lru_cache(maxsize=1)
def list_codici_oggetto_pst() -> tuple[dict[str, str], ...]:
    catalog = load_pratiche_collegate_catalog()
    rows: list[dict[str, str]] = []
    for area in catalog.get("areas") or []:
        if not isinstance(area, dict):
            continue
        rows.extend(
            _walk_items(
                area.get("items") if isinstance(area.get("items"), list) else [],
                area=_text(area.get("area")),
                area_label=_text(area.get("label")),
            )
        )
    return tuple(rows)


@lru_cache(maxsize=1)
def _codici_index() -> dict[str, dict[str, str]]:
    return {row["codice"]: row for row in list_codici_oggetto_pst()}


def codice_oggetto_pst_entry(codice: Any) -> dict[str, str] | None:
    return _codici_index().get(_text(codice))


def codice_oggetto_pst_payload(codice: Any) -> dict[str, str]:
    entry = codice_oggetto_pst_entry(codice)
    if not entry:
        return {
            "codice_oggetto_pst": "",
            "fonte_codice_oggetto": "",
            "file_fonte_codice_oggetto": "",
        }
    catalog = load_pratiche_collegate_catalog()
    fonte = catalog.get("fonte") if isinstance(catalog.get("fonte"), dict) else {}
    return {
        "codice_oggetto_pst": entry["codice"],
        "fonte_codice_oggetto": _text(fonte.get("tipo")) or "PST_XSD",
        "file_fonte_codice_oggetto": _text(fonte.get("fileFontePrevalente")) or "tipi-base.xsd",
    }
