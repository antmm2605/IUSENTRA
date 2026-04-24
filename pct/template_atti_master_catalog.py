"""Catalogo master versionato per la suite professionale dei template atti."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any
import unicodedata

from pct.template_atti_compiler_bindings import compiler_binding_map_by_title


DATA_DIR = Path(__file__).with_name("template_atti_catalogo_data")
MASTER_CATALOG_PATH = DATA_DIR / "catalogo_master.json"
SPLIT_CATALOG_FILES = {
    "core": DATA_DIR / "core.json",
    "advanced": DATA_DIR / "advanced.json",
    "specialist": DATA_DIR / "specialist.json",
    "studio_interno": DATA_DIR / "studio_interno.json",
}

REQUIRED_TEMPLATE_FIELDS = (
    "id",
    "slug",
    "titolo",
    "famiglia",
    "area",
    "macro_area",
    "sottobranca",
    "procedimento",
    "fase",
    "autorita",
    "rito",
    "canale_telematico",
    "depositabile",
    "tags",
    "campi_precompila",
    "blocchi_guidati",
    "varianti",
    "allegati_essenziali",
    "checklist_conformita",
    "note_operative",
    "versione",
    "stato",
    "ordinamento",
)

PREFILL_LABELS = {
    "cliente": "Cliente / assistito",
    "controparte": "Controparte",
    "difensore": "Difensore",
    "ufficio_giudiziario": "Ufficio giudiziario",
    "rg": "Numero RG / riferimento",
    "oggetto": "Oggetto",
    "data_atto": "Data atto",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_master_cached() -> dict[str, Any]:
    payload = _read_json(MASTER_CATALOG_PATH)
    validate_catalog_payload(payload)
    return payload


def load_catalogo_master() -> dict[str, Any]:
    """Carica il catalogo master completo, restituendo una copia mutabile."""
    return deepcopy(_load_master_cached())


def load_master_templates() -> list[dict[str, Any]]:
    return list(load_catalogo_master().get("template") or [])


def load_split_catalogs() -> dict[str, dict[str, Any]]:
    catalogs: dict[str, dict[str, Any]] = {}
    for key, path in SPLIT_CATALOG_FILES.items():
        payload = _read_json(path)
        validate_catalog_payload(payload, require_master_meta=False)
        catalogs[key] = payload
    return catalogs


def validate_catalog_payload(payload: dict[str, Any], *, require_master_meta: bool = True) -> None:
    templates = list(payload.get("template") or [])
    if not templates:
        raise ValueError("Catalogo template atti vuoto o non valido.")
    if require_master_meta and int(payload.get("totale_template") or 0) != len(templates):
        raise ValueError("Conteggio catalogo master non coerente con le voci template.")
    ids = [str(item.get("id") or "") for item in templates]
    duplicates = [key for key, count in Counter(ids).items() if key and count > 1]
    if duplicates:
        raise ValueError(f"ID duplicati nel catalogo master: {', '.join(duplicates[:5])}")
    for item in templates:
        missing = [field for field in REQUIRED_TEMPLATE_FIELDS if field not in item]
        if missing:
            title = item.get("titolo") or item.get("id") or "template senza titolo"
            raise ValueError(f"Template '{title}' incompleto: mancano {', '.join(missing)}")


def catalogo_master_stats() -> dict[str, Any]:
    payload = load_catalogo_master()
    templates = list(payload.get("template") or [])
    channels = Counter(str(item.get("canale_telematico") or "NESSUNO") for item in templates)
    families = Counter(str(item.get("famiglia") or "Altro") for item in templates)
    split = load_split_catalogs()
    return {
        "suite": payload.get("suite", ""),
        "versione": payload.get("versione", ""),
        "totale_template": len(templates),
        "moduli": len(payload.get("moduli") or []),
        "canali": dict(sorted(channels.items())),
        "famiglie": dict(sorted(families.items())),
        "gruppi": {key: int(value.get("totale_template") or 0) for key, value in split.items()},
        "files": {
            "catalogo_master": str(MASTER_CATALOG_PATH),
            **{key: str(path) for key, path in SPLIT_CATALOG_FILES.items()},
        },
    }


def _slug_ascii(value: Any, *, fallback: str = "campo") -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").strip())
    ascii_text = raw.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_").lower()
    if not slug:
        slug = fallback
    if slug[0].isdigit():
        slug = f"{fallback}_{slug}"
    return slug


def _field_for_prefill(name: str) -> dict[str, Any]:
    clean_name = _slug_ascii(name)
    field_name = f"dato_{clean_name}"
    return {
        "name": field_name,
        "label": PREFILL_LABELS.get(clean_name, clean_name.replace("_", " ").title()),
        "type": "date" if clean_name.startswith("data") else "text",
        "placeholder": "Compila o lascia precompilare dal fascicolo",
        "section": "Dati pratica",
        "rows": 1,
        "help_text": "Campo governato dal catalogo master e utile alla precompilazione assistita.",
    }


def _field_for_block(block_name: str) -> dict[str, Any]:
    clean_name = _slug_ascii(block_name)
    return {
        "name": f"sezione_{clean_name}",
        "label": str(block_name or "Sezione").strip(),
        "type": "textarea",
        "placeholder": "Inserisci contenuto verificato, fonti e richieste operative.",
        "section": "Blocchi guidati",
        "rows": 4,
        "help_text": "Blocco redazionale previsto dal catalogo master del template.",
    }


def _master_fields(item: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(item.get("campi_precompila") or []):
        field = _field_for_prefill(str(raw))
        if field["name"] not in seen:
            fields.append(field)
            seen.add(field["name"])
    for raw in list(item.get("blocchi_guidati") or []):
        block = str(raw or "").strip()
        if not block or block.lower() in {"firma", "allegati"}:
            continue
        field = _field_for_block(block)
        if field["name"] not in seen:
            fields.append(field)
            seen.add(field["name"])
    return fields


def _derive_profile(item: dict[str, Any]) -> str:
    if not item.get("depositabile") or str(item.get("canale_telematico") or "").upper() == "NESSUNO":
        return "atto_interno"
    title = str(item.get("titolo") or "").lower()
    if any(token in title for token in ("appello", "cassazione", "reclamo", "opposizione")):
        return "impugnazione"
    if any(token in title for token in ("precetto", "pignoramento", "esecuzione", "assegnazione", "vendita")):
        return "atto_esecutivo"
    if any(token in title for token in ("memoria", "nota", "istanza", "osservazioni", "comparsa conclusionale")):
        return "atto_successivo"
    return "atto_introduttivo"


def _keywords(item: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    values = [
        item.get("famiglia"),
        item.get("area"),
        item.get("macro_area"),
        item.get("sottobranca"),
        item.get("procedimento"),
        item.get("rito"),
        item.get("canale_telematico"),
        item.get("titolo"),
        *list(item.get("tags") or []),
        *list(item.get("varianti") or []),
    ]
    for raw in values:
        value = " ".join(str(raw or "").split())
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def _body_for_master(item: dict[str, Any]) -> str:
    title = str(item.get("titolo") or "Template atto").strip()
    channel = str(item.get("canale_telematico") or "NESSUNO").strip()
    rite = str(item.get("rito") or "Rito da verificare").strip()
    authority = str(item.get("autorita") or "Autorita competente").strip()
    lines = [
        "{{ (dato_ufficio_giudiziario or '" + authority.replace("'", " ") + "') | upper }}",
        "",
        title.upper(),
        "",
        f"Canale telematico: {channel}",
        f"Rito / procedimento: {rite}",
        "",
        "{% if dato_cliente %}Cliente / assistito: {{ dato_cliente }}{% endif %}",
        "{% if dato_controparte %}Controparte: {{ dato_controparte }}{% endif %}",
        "{% if dato_rg %}Riferimento RG: {{ dato_rg }}{% endif %}",
        "{% if dato_oggetto %}Oggetto: {{ dato_oggetto }}{% endif %}",
        "",
    ]
    for block in list(item.get("blocchi_guidati") or []):
        block_title = str(block or "").strip()
        if not block_title:
            continue
        if block_title.lower() == "firma":
            continue
        var_name = f"sezione_{_slug_ascii(block_title)}"
        lines.extend([block_title.upper(), "{{ " + var_name + " or '___________________' }}", ""])
    lines.extend(
        [
            "{% if dato_data_atto %}Data atto: {{ dato_data_atto }}{% else %}Luogo e data: ___________________, {{ data_oggi }}{% endif %}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )
    return "\n".join(lines)


def build_master_builtin_templates(*, order_offset: int = 10000) -> list[dict[str, Any]]:
    """Converte il catalogo master JSON nel formato runtime del workspace Template Atti."""
    compiler_links = compiler_binding_map_by_title()
    templates: list[dict[str, Any]] = []
    for index, item in enumerate(load_master_templates(), start=1):
        title = str(item.get("titolo") or item.get("id") or "Template atto")
        binding = compiler_links.get(title)
        notes = list(item.get("note_operative") or [])
        description = (
            f"{title}: template del catalogo master {item.get('versione')} per {item.get('famiglia')}, "
            f"canale {item.get('canale_telematico')} e rito {item.get('rito')}."
        )
        templates.append(
            {
                "id": str(item.get("id")),
                "titolo": title,
                "categoria": str(item.get("famiglia") or "Catalogo master"),
                "corpo": _body_for_master(item),
                "codice": str(item.get("id") or ""),
                "note": " ".join(str(note) for note in notes) or description,
                "descrizione": description,
                "area": str(item.get("macro_area") or item.get("area") or "Operativo"),
                "branca": str(item.get("famiglia") or "Catalogo master"),
                "sottobranca": str(item.get("sottobranca") or item.get("procedimento") or "Template atti"),
                "microtema": str(item.get("procedimento") or ""),
                "fase": str(item.get("fase") or "standard"),
                "rito": str(item.get("rito") or ""),
                "grado": str(item.get("autorita") or "Tutti"),
                "canale_telematico": str(item.get("canale_telematico") or "NESSUNO"),
                "profilo_deposito": _derive_profile(item),
                "collezione": str(item.get("famiglia") or "Catalogo master"),
                "allegati_obbligatori": list(item.get("allegati_essenziali") or []),
                "controlli_conformita": list(item.get("checklist_conformita") or []),
                "parole_chiave": _keywords(item),
                "campi_guidati": _master_fields(item),
                "varianti": list(item.get("varianti") or []),
                "link_compilatore_code": binding["compiler_code"] if binding else "",
                "ordine": order_offset + index,
                "builtin": True,
            }
        )
    return templates


__all__ = [
    "DATA_DIR",
    "MASTER_CATALOG_PATH",
    "REQUIRED_TEMPLATE_FIELDS",
    "SPLIT_CATALOG_FILES",
    "build_master_builtin_templates",
    "catalogo_master_stats",
    "load_catalogo_master",
    "load_master_templates",
    "load_split_catalogs",
    "validate_catalog_payload",
]
