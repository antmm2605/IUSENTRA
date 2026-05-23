#!/usr/bin/env python3
"""Unisce i moduli JSON della Guida Pratica in un knowledge base full.

Caratteristiche v4:
- supporta `codici_materia` top-level e `sezioni[].codici_materia`;
- mantiene zero iniziali e codici logici legacy;
- non scarta i duplicati: li fonde in modo deterministico, con i moduli a priorità più alta
  (es. TOP9 iper-dettagliato) che integrano/rafforzano la scheda di base;
- traccia `_source_files`, `_duplicate_sources`, `_macro_area_id`, `_registro` e `_quality_hint`.

Uso dalla root del repository:
    python scripts/merge_legal_kb_modules.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "pct" / "data"
MODULES_DIR = DATA_DIR / "legal_knowledge_base_modules"
DEFAULT_OUTPUT = DATA_DIR / "legal_knowledge_base.full.json"


def text(value: Any, default: str = "") -> str:
    value = str(value if value is not None else default).strip()
    return value if value else default


def normalize_code(value: Any) -> str:
    raw = text(value)
    if not raw:
        return ""
    if re.search(r"[A-Za-z]", raw):
        return re.sub(r"[^A-Za-z0-9_-]+", "_", raw.upper()).strip("_")
    raw = re.sub(r"[^0-9]", "", raw)
    return raw.zfill(6) if len(raw) == 5 else raw


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def code_of(item: dict[str, Any]) -> str:
    return normalize_code(item.get("codice") or item.get("codice_logico") or item.get("codice_materia"))


def module_meta(path: Path, payload: dict[str, Any], section: dict[str, Any] | None = None) -> dict[str, str]:
    macro = payload.get("macro_area") if isinstance(payload.get("macro_area"), dict) else {}
    section = section if isinstance(section, dict) else {}
    return {
        "file": path.name,
        "macro_area_id": text(payload.get("macro_area_id") or section.get("macro_area_riferimento") or macro.get("codice") or path.stem),
        "denominazione": text(payload.get("denominazione") or section.get("sezione") or macro.get("label") or path.stem),
        "registro": text(payload.get("registro") or section.get("registro") or macro.get("registro") or macro.get("registro_sicid")),
        "rito_prevalente": text(payload.get("rito_prevalente") or payload.get("rito_base") or section.get("rito_prevalente") or macro.get("rito_base")),
        "competenza_prevalente": text(payload.get("competenza_prevalente") or section.get("competenza_prevalente") or macro.get("competenza")),
        "sezione": text(section.get("sezione")),
    }


def iter_items(path: Path, payload: dict[str, Any]) -> Iterable[tuple[dict[str, str], dict[str, Any]]]:
    meta = module_meta(path, payload)
    for raw in payload.get("codici_materia") or []:
        if isinstance(raw, dict):
            yield meta, raw
    for section in payload.get("sezioni") or []:
        if not isinstance(section, dict):
            continue
        section_meta = module_meta(path, payload, section)
        for raw in section.get("codici_materia") or []:
            if isinstance(raw, dict):
                yield section_meta, raw


def unique_list(items: Iterable[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def deep_merge(left: Any, right: Any) -> Any:
    if isinstance(left, dict) and isinstance(right, dict):
        out = deepcopy(left)
        for key, value in right.items():
            if key in out:
                out[key] = deep_merge(out[key], value)
            else:
                out[key] = deepcopy(value)
        return out
    if isinstance(left, list) and isinstance(right, list):
        return unique_list([*deepcopy(left), *deepcopy(right)])
    return deepcopy(right) if right not in (None, "", [], {}) else deepcopy(left)


def module_priority(path: Path) -> int:
    name = path.name.lower()
    if "kb_99" in name or "completamento_codici_ufficiali" in name:
        return 950
    if "top9" in name:
        return 980
    if "sfratti" in name or "kb_00" in name:
        return 800
    if "logiche_legacy" in name:
        return 100
    if "addendum" in name or "kb_15" in name:
        return 650
    return 500


def _drop_inherited_scaffold_for_curated_override(previous: dict[str, Any], path: Path, item: dict[str, Any]) -> dict[str, Any]:
    if "top9" not in path.name.lower() or item.get("eredita_da"):
        return previous
    cleaned = deepcopy(previous)
    cleaned.pop("differenze_rispetto_a_padre", None)
    return cleaned


def quality_hint(item: dict[str, Any]) -> str:
    atto = item.get("atto_principale") if isinstance(item.get("atto_principale"), dict) else {}
    has_fields = bool(
        atto.get("campi_chiave")
        or atto.get("campi_obbligatori")
        or item.get("allegati_obbligatori")
        or item.get("adempimenti_propedeutici")
    )
    if has_fields:
        return "operativa_curata"
    if item.get("normativa"):
        return "normativa_sintetica_da_arricchire"
    return "classificazione_base_da_arricchire"


def merge(modules_dir: Path, output: Path) -> dict[str, Any]:
    files = [path for path in sorted(modules_dir.glob("kb_*.json")) if path.name != "kb_index.json"] if modules_dir.exists() else []
    legacy = DATA_DIR / "legal_knowledge_base.json"
    if legacy.exists() and not any(path.name == "kb_00_sfratti.json" for path in files):
        files = [legacy, *files]
    files = sorted(files, key=lambda path: (module_priority(path), path.name))
    combined: dict[str, Any] = {
        "$schema": "iusentra/legal-knowledge-base/v1",
        "name": "IUSENTRA Legal Knowledge Base completa",
        "version": "4.0.4-kb-completa",
        "ultimo_aggiornamento": "2026-05-23",
        "description": "Knowledge base unificata dei moduli Guida Pratica con priorità top9, addendum, set7 e alias logici legacy.",
        "merge_policy": "deep_merge_with_high_priority_modules_overriding_sparse_base; no codice inventato per deposito; alias logici solo retrocompatibilità",
        "moduli": [],
        "codici_materia": [],
    }
    by_code: dict[str, dict[str, Any]] = {}
    duplicate_sources: dict[str, list[str]] = {}
    modules_added: set[str] = set()
    for path in files:
        payload = load_json(path)
        base_meta = module_meta(path, payload)
        if path.name not in modules_added:
            combined["moduli"].append(base_meta)
            modules_added.add(path.name)
        for meta, raw_item in iter_items(path, payload):
            codice = code_of(raw_item)
            if not codice:
                continue
            item = deepcopy(raw_item)
            item.setdefault("codice", codice)
            item.setdefault("categoria", meta["denominazione"])
            item.setdefault("_source_file", path.name)
            item.setdefault("_macro_area_id", meta["macro_area_id"])
            item.setdefault("_macro_area_denominazione", meta["denominazione"])
            item.setdefault("_registro", meta["registro"])
            if meta.get("sezione"):
                item.setdefault("_sezione_addendum", meta["sezione"])
            item.setdefault("_quality_hint", quality_hint(item))
            if codice in by_code:
                previous = by_code[codice]
                previous = _drop_inherited_scaffold_for_curated_override(previous, path, item)
                merged = deep_merge(previous, item)
                sources = unique_list([*(previous.get("_source_files") or [previous.get("_source_file")]), path.name])
                merged["_source_files"] = sources
                merged["_duplicate_sources"] = unique_list([*(previous.get("_duplicate_sources") or []), path.name])
                # Keep the final source file as the highest-priority contributor for traceability.
                merged["_source_file"] = path.name
                merged["_quality_hint"] = "operativa_curata" if quality_hint(merged) == "operativa_curata" else quality_hint(merged)
                by_code[codice] = merged
                duplicate_sources.setdefault(codice, []).append(path.name)
            else:
                item["_source_files"] = [path.name]
                by_code[codice] = item
    combined["codici_materia"] = [by_code[codice] for codice in sorted(by_code)]
    combined["n_codici"] = len(combined["codici_materia"])
    combined["duplicates_merged"] = {k: v for k, v in sorted(duplicate_sources.items())}
    combined["n_duplicates_merged"] = len(duplicate_sources)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output": str(output), "modules": len(files), "codes": combined["n_codici"], "duplicates_merged": len(duplicate_sources)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modules-dir", default=str(MODULES_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    report = merge(Path(args.modules_dir), Path(args.output))
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
