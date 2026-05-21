#!/usr/bin/env python3
"""Genera una base guida per tutti i codici caricati nel catalogo PST/XSD.

Il file risultante contiene:
- guide curate già presenti in `legal_knowledge_base.full.json`;
- guide generate per gli altri codici del catalogo, marcate con `needs_reviewer`.

Non sostituisce la revisione normativa dell'avvocato: serve a dare copertura UI
immediata e a creare una coda di completamento ordinata per codice.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica import GuidaPraticaService  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_catalog_records(catalog_path: Path) -> list[dict[str, Any]]:
    try:
        from pct.pratiche_collegate_catalog import list_codici_oggetto_pst  # type: ignore
        return [dict(row) for row in list_codici_oggetto_pst()]
    except Exception:
        pass
    payload = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    rows = payload.get("records") if isinstance(payload.get("records"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "codice": _text(row.get("codice")),
                "descrizione": _text(row.get("descrizione")),
                "area": _text(row.get("area")),
                "area_label": _text(row.get("area_label") or row.get("area")),
                "parent_codice": _text(row.get("parent_codice") or row.get("codicePadre")),
                "parent_label": _text(row.get("parent_label") or row.get("descrizionePadre")),
                "registri": ", ".join(row.get("registri") or []) if isinstance(row.get("registri"), list) else _text(row.get("registri")),
                "file_fonte": _text(row.get("file_fonte") or row.get("fileFonte")),
            }
        )
    return [row for row in out if row["codice"]]


def _copy_entry_for_kb(guida: dict[str, Any]) -> dict[str, Any]:
    blocked = {"coverage", "quick_help", "catalogo", "source", "generatedAt", "checklist"}
    entry = {key: value for key, value in guida.items() if key not in blocked}
    coverage = guida.get("coverage") if isinstance(guida.get("coverage"), dict) else {}
    if coverage.get("needs_reviewer"):
        entry["review_status"] = "bozza_generata_da_catalogo_xsd"
        entry["needs_reviewer"] = True
        entry["avvertenze_redazionali"] = list(entry.get("avvertenze_redazionali") or [])
        warning = "Guida generata automaticamente dal catalogo PST/XSD: completare riferimenti normativi, presupposti e avvertimenti specifici prima dell'uso definitivo."
        if warning not in entry["avvertenze_redazionali"]:
            entry["avvertenze_redazionali"].append(warning)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=str(ROOT / "pct" / "data" / "legal_knowledge_base.full.json"))
    parser.add_argument("--catalog", default=str(ROOT / "pct" / "data" / "cataloghi" / "codici_oggetto_pst.json"))
    parser.add_argument("--output", default=str(ROOT / "pct" / "data" / "legal_knowledge_base.generated_profiles.json"))
    parser.add_argument("--overwrite", action="store_true", help="Consente di scrivere direttamente sul file --kb.")
    parser.add_argument("--limit", type=int, default=0, help="Limite per test; 0 = tutti.")
    args = parser.parse_args()

    kb_path = Path(args.kb)
    payload = json.loads(kb_path.read_text(encoding="utf-8")) if kb_path.exists() else {"codici_materia": []}
    records = _load_catalog_records(Path(args.catalog))
    if args.limit:
        records = records[: args.limit]
    service = GuidaPraticaService(kb_path=kb_path, catalog_records=records)

    existing = {str(item.get("codice") or "").strip(): item for item in payload.get("codici_materia") or [] if isinstance(item, dict)}
    entries: list[dict[str, Any]] = []
    for row in records:
        codice = str(row.get("codice") or "").strip()
        if not codice:
            continue
        guida = service.get_guidance(codice)
        if codice in existing and not guia_needs_review(guida):
            entries.append(existing[codice])
        else:
            entries.append(_copy_entry_for_kb(guida))

    present = {str(item.get("codice") or "").strip() for item in entries}
    for codice, entry in sorted(existing.items()):
        if codice not in present:
            entries.append(entry)

    out_payload = dict(payload)
    out_payload["version"] = str(out_payload.get("version") or "1.0.0")
    out_payload["ultimo_aggiornamento"] = _now()[:10]
    out_payload["note_versione"] = "Base guida estesa a tutti i codici caricati nel catalogo PST/XSD; le voci generate richiedono revisione normativa."
    out_payload["codici_materia"] = sorted(entries, key=lambda item: str(item.get("codice") or ""))

    output = kb_path if args.overwrite else Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    generated_count = sum(1 for item in entries if item.get("needs_reviewer"))
    print(json.dumps({"ok": True, "output": str(output), "total": len(entries), "generated_needs_reviewer": generated_count}, ensure_ascii=False, indent=2))
    return 0


def guia_needs_review(guida: dict[str, Any]) -> bool:
    coverage = guida.get("coverage") if isinstance(guida.get("coverage"), dict) else {}
    return bool(coverage.get("needs_reviewer"))


if __name__ == "__main__":
    raise SystemExit(main())
