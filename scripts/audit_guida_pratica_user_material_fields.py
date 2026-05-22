from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lex.retrieval.sources.guida_pratica import _guidance_content  # noqa: E402
from pct.guida_pratica.service import GuidaPraticaService, normalize_codice_materia  # noqa: E402


MODULES_DIR = ROOT / "pct" / "data" / "legal_knowledge_base_modules"
DEFAULT_REPORT = ROOT / "artifacts" / "guida-pratica" / "guida-pratica-user-material-field-audit.json"
DEFAULT_CSV = ROOT / "artifacts" / "guida-pratica" / "guida-pratica-user-material-field-audit.csv"
FRONTEND_COMPONENT = ROOT / "frontend" / "src" / "components" / "GuidaPraticaSidebar.tsx"

USER_MODULE_PATTERNS = (
    "kb_98_top9_codici_frequenti_dettaglio_massimo.json",
    "kb_98_top9_set2_parte1.json",
    "kb_98_top9_set2_parte2.json",
    "kb_98_top9_set3_parte1.json",
    "kb_98_top9_set3_parte2.json",
    "kb_98_top9_set4_parte1.json",
    "kb_98_top9_set4_parte2.json",
)

CONTROLLED_FIELDS: dict[str, list[list[str]]] = {
    "denominazione": [["denominazione"]],
    "categoria": [["categoria"]],
    "sottocategoria": [["sottocategoria"]],
    "rito": [["rito"]],
    "competenza": [["competenza"]],
    "uffici_destinatari": [["uffici_destinatari"]],
    "tipologie_di_intervento": [["tipologie_di_intervento"]],
    "presupposti_sostanziali": [["presupposti_sostanziali"], ["presupposti_sostanziali_gmo"]],
    "legittimati_attivi": [["legittimati_attivi"], ["atto_principale", "legittimati_attivi"]],
    "obbligo_mediazione": [["obbligo_mediazione"], ["obbligo_mediazione_o_negoziazione_assistita"]],
    "adempimenti_propedeutici": [["adempimenti_propedeutici"]],
    "richiesta_provvedimenti_urgenti": [["richiesta_provvedimenti_urgenti"], ["atto_principale", "richiesta_provvedimenti_urgenti"]],
    "avvertimenti_obbligatori": [["avvertimenti_obbligatori"], ["atto_principale", "avvertimenti_obbligatori"]],
    "allegati_obbligatori": [["allegati_obbligatori"]],
    "termini_processuali": [["termini_processuali"]],
    "esiti_processuali_tipici": [["esiti_processuali_tipici"], ["esiti_processuali_attesi"]],
    "normativa": [["normativa"]],
    "atto_principale": [["atto_principale"]],
}

SCALAR_VALUE_FIELDS = {"denominazione", "categoria", "sottocategoria", "rito", "competenza"}

FIELD_LABELS_FOR_LEX = {
    "denominazione": "Guida pratica interna facoltativa",
    "categoria": "Categoria",
    "sottocategoria": "Sottocategoria",
    "rito": "Rito",
    "competenza": "Competenza",
    "uffici_destinatari": "Uffici destinatari",
    "tipologie_di_intervento": "Tipologie di intervento",
    "presupposti_sostanziali": "Presupposti sostanziali",
    "legittimati_attivi": "Legittimati attivi",
    "obbligo_mediazione": "Obbligo mediazione",
    "adempimenti_propedeutici": "Adempimenti propedeutici",
    "richiesta_provvedimenti_urgenti": "Richiesta provvedimenti urgenti",
    "avvertimenti_obbligatori": "Avvertimenti obbligatori",
    "allegati_obbligatori": "Allegati obbligatori",
    "termini_processuali": "Termini processuali",
    "esiti_processuali_tipici": "Esiti processuali tipici",
    "normativa": "Normativa letta dalla scheda",
    "atto_principale": "Atto principale",
}

STANDARD_TOP_LEVEL = {
    "$schema",
    "codice",
    "codice_logico",
    "codice_originale_ricevuto",
    "codici_ufficiali_correlati_da_valutare",
    "denominazione",
    "categoria",
    "sottocategoria",
    "rito",
    "competenza",
    "uffici_destinatari",
    "registro_sicid",
    "normativa",
    "tipologie_di_intervento",
    "presupposti_sostanziali",
    "presupposti_sostanziali_gmo",
    "legittimati_attivi",
    "obbligo_mediazione",
    "obbligo_mediazione_o_negoziazione_assistita",
    "adempimenti_propedeutici",
    "richiesta_provvedimenti_urgenti",
    "avvertimenti_obbligatori",
    "allegati_obbligatori",
    "termini_processuali",
    "esiti_processuali_tipici",
    "esiti_processuali_attesi",
    "atto_principale",
    "adempimenti_fiscali",
    "adempimenti_fiscali_telematici",
    "avvertenze_redazionali",
    "atti_collegati",
    "quick_help",
    "coverage",
    "catalogo_xsd",
    "codice_deposito",
    "fascicolo_context",
    "_source_file",
    "_source_files",
    "_macro_area_id",
    "_macro_area_denominazione",
    "_registro",
    "_quality_hint",
    "_curation_source",
}


@dataclass(frozen=True)
class SourceItem:
    module_name: str
    module_macro: str
    item: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _has_content(value: Any, *, key_exists: bool = True) -> bool:
    if not key_exists:
        return False
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (str, int, float)):
        return bool(str(value).strip())
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return True


def _value_at(payload: dict[str, Any], path: list[str]) -> tuple[bool, Any]:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _first_present(payload: dict[str, Any], paths: list[list[str]]) -> tuple[bool, Any, str]:
    for path in paths:
        exists, value = _value_at(payload, path)
        if _has_content(value, key_exists=exists):
            return True, value, ".".join(path)
    return False, None, ".".join(paths[0])


def _iter_module_items(path: Path) -> list[SourceItem]:
    payload = _load_json(path)
    macro = _clean(payload.get("macro_area_id") or payload.get("denominazione") or path.stem)
    out: list[SourceItem] = []
    for item in _as_list(payload.get("codici_materia")):
        if isinstance(item, dict):
            out.append(SourceItem(path.name, macro, item))
    for section in _as_list(payload.get("sezioni")):
        if not isinstance(section, dict):
            continue
        section_macro = _clean(section.get("macro_area_riferimento") or section.get("sezione") or macro)
        for item in _as_list(section.get("codici_materia")):
            if isinstance(item, dict):
                out.append(SourceItem(path.name, section_macro, item))
    return out


def _source_files() -> list[Path]:
    paths = [MODULES_DIR / name for name in USER_MODULE_PATTERNS]
    return [path for path in paths if path.exists()]


def _steps(value: Any) -> list[str]:
    steps: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict) and _clean(item.get("step")):
            steps.append(_clean(item.get("step")))
    return sorted(set(steps), key=lambda item: (len(item), item))


def _scalar_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return ""
    if isinstance(value, bool):
        return "sì" if value else "no"
    return _clean(value)


def _field_ui_supported(field: str, component_text: str) -> bool:
    if field.startswith("specialistica:"):
        return "extraGuidaFields" in component_text and "Voci specialistiche della scheda" in component_text
    if field in {"denominazione", "categoria", "sottocategoria", "rito", "competenza", "uffici_destinatari"}:
        return True
    if field in {"normativa", "atto_principale"}:
        return True
    if field == "obbligo_mediazione":
        return "obbligo_mediazione" in component_text or "obbligo_mediazione_o_negoziazione_assistita" in component_text
    return field in component_text


def _audit_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    service = GuidaPraticaService()
    full_index = service._kb_index  # audit interno: confronta il KB caricato dal servizio.
    component_text = FRONTEND_COMPONENT.read_text(encoding="utf-8") if FRONTEND_COMPONENT.exists() else ""

    rows: list[dict[str, Any]] = []
    source_items: list[SourceItem] = []
    for path in _source_files():
        source_items.extend(_iter_module_items(path))

    for source in source_items:
        item = source.item
        codice = normalize_codice_materia(item.get("codice") or item.get("codice_logico"))
        full_item = full_index.get(codice, {})
        try:
            service_guidance = service.get_guidance(codice)
        except Exception as exc:  # pragma: no cover - report operativo.
            service_guidance = {}
            service_error = str(exc)
        else:
            service_error = ""
        lex_content = _guidance_content(service_guidance, matched_by="audit") if service_guidance else ""

        fields = dict(CONTROLLED_FIELDS)
        for key, value in item.items():
            if key in STANDARD_TOP_LEVEL or key.startswith("_") or not _has_content(value):
                continue
            fields[f"specialistica:{key}"] = [[key]]

        for field, paths in fields.items():
            source_present, source_value, source_path = _first_present(item, paths)
            full_present, _, full_path = _first_present(full_item, paths)
            service_present, service_value, service_path = _first_present(service_guidance, paths)

            source_steps = _steps(source_value) if field == "adempimenti_propedeutici" else []
            service_steps = _steps(service_value) if field == "adempimenti_propedeutici" else []
            missing_steps = [step for step in source_steps if step not in service_steps]
            source_scalar = _scalar_value(source_value) if field in SCALAR_VALUE_FIELDS else ""
            service_scalar = _scalar_value(service_value) if field in SCALAR_VALUE_FIELDS else ""
            value_changed = bool(source_scalar and service_scalar and source_scalar != service_scalar)

            lex_supported = True
            if field in FIELD_LABELS_FOR_LEX:
                label = FIELD_LABELS_FOR_LEX[field]
                lex_supported = label in lex_content or (field == "obbligo_mediazione" and "Obbligo mediazione o negoziazione" in lex_content)
                if field == "avvertimenti_obbligatori":
                    lex_supported = "Avvertimenti obbligatori della guida" in lex_content or "Avvertimenti redazionali obbligatori" in lex_content
            elif field.startswith("specialistica:"):
                lex_supported = source_present and service_present

            lost = source_present and (not full_present or not service_present or bool(missing_steps))
            rows.append(
                {
                    "module": source.module_name,
                    "macro_area": source.module_macro,
                    "codice": codice,
                    "denominazione": _clean(item.get("denominazione")),
                    "field": field,
                    "source_path": source_path,
                    "full_path": full_path,
                    "service_path": service_path,
                    "source_present": source_present,
                    "full_kb_present": full_present,
                    "service_present": service_present,
                    "ui_supported": _field_ui_supported(field, component_text),
                    "lex_supported": lex_supported,
                    "source_steps": ",".join(source_steps),
                    "service_steps": ",".join(service_steps),
                    "missing_steps_in_service": ",".join(missing_steps),
                    "source_value": source_scalar,
                    "service_value": service_scalar,
                    "value_changed_in_service": value_changed,
                    "service_error": service_error,
                    "status": "lost_from_software" if lost else "ok",
                }
            )
    summary = {
        "generated_at": _utc_now(),
        "modules_checked": [path.name for path in _source_files()],
        "records_checked": len(source_items),
        "rows": len(rows),
        "source_fields_present": sum(1 for row in rows if row["source_present"]),
        "lost_from_software": sum(1 for row in rows if row["status"] == "lost_from_software"),
        "missing_full_kb_when_source_present": sum(1 for row in rows if row["source_present"] and not row["full_kb_present"]),
        "missing_service_when_source_present": sum(1 for row in rows if row["source_present"] and not row["service_present"]),
        "missing_ui_support_when_source_present": sum(1 for row in rows if row["source_present"] and not row["ui_supported"]),
        "missing_lex_support_when_source_present": sum(1 for row in rows if row["source_present"] and not row["lex_supported"]),
        "scalar_values_changed_in_service": sum(1 for row in rows if row.get("value_changed_in_service")),
        "fields_checked": list(CONTROLLED_FIELDS),
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit voce per voce dei file guida pratica inviati dall'utente.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--fail-on-loss", action="store_true")
    args = parser.parse_args()

    rows, summary = _audit_rows()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0].keys()) if rows else [
            "module",
            "macro_area",
            "codice",
            "denominazione",
            "field",
            "status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.fail_on_loss and summary["lost_from_software"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
