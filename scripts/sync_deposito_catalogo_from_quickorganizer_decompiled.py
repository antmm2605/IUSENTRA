"""Sincronizza le evidenze dei 270 depositi dal decompilato Studio Telematico.

Il catalogo menu resta quello estratto da QuickOrganizer.mdb. Questo script
aggiorna esclusivamente i campi governati dal codice decompilato: metodo
DatiAtto, radice XML salvata, dati letti, flag del percorso e codice oggetto.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from generate_quickorganizer_analysis_artifacts import clean, extract_datiatto


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "pct" / "data" / "cataloghi" / "quickorganizer_depositi_studio_telematico.json"

SOURCE_KEY_REPAIRS = {
    "Professionista_ESECUZIONI_SIECIC::Progett369oDistribuzione": (
        "Professionista_ESECUZIONI_SIECIC::ProgettoDistribuzione"
    ),
}
CURATORE_SOURCE_KEY = "Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale"


def _source_key_for(entry: dict[str, Any]) -> str:
    key = str(clean(entry.get("key") or "")).strip()
    if key in SOURCE_KEY_REPAIRS:
        return SOURCE_KEY_REPAIRS[key]
    if (
        not key
        and str(clean(entry.get("macro") or "")).strip() == "Procedimenti concorsuali"
        and str(clean(entry.get("categoria") or "")).strip() == "Atti del Curatore"
    ):
        return CURATORE_SOURCE_KEY
    return key


def sync_catalog() -> dict[str, Any]:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    _, _, source_by_key = extract_datiatto()
    if len(entries) != 270:
        raise RuntimeError(f"Catalogo inatteso: {len(entries)} tipi invece di 270")

    missing: list[str] = []
    changed: list[str] = []
    for entry in entries:
        source_key = _source_key_for(entry)
        source = source_by_key.get(source_key)
        if source is None:
            missing.append(source_key or "<chiave vuota>")
            continue
        replacements = {
            "datiatto_methods": source.get("methods") or [],
            "datiatto_roots": source.get("saved_roots") or [],
            "datiatto_required_data": source.get("required_data") or [],
            "deposit_menu_flags": source.get("flags") or {},
            "deposit_fixed_object_codes": source.get("fixed_object_codes") or [],
            "deposit_controls": source.get("controls") or [],
            "deposit_combo_sources": source.get("combo_sources") or [],
            "deposit_assignments": source.get("assignments") or [],
        }
        if any(entry.get(field) != value for field, value in replacements.items()):
            changed.append(source_key)
        entry.update(replacements)

    if missing:
        raise RuntimeError("Tipi non risolti nel decompilato: " + ", ".join(missing))

    payload["source_evidence_synced_at"] = datetime.now(ZoneInfo("Europe/Rome")).strftime(
        "%d/%m/%Y %H:%M (Europe/Rome)"
    )
    payload["source_evidence_contract"] = {
        "entries": 270,
        "source": "FormSentMailBee.cs decompilato da Studio Telematico 2026 Rel. 021",
        "fields": [
            "datiatto_methods",
            "datiatto_roots",
            "datiatto_required_data",
            "deposit_menu_flags",
            "deposit_fixed_object_codes",
            "deposit_controls",
            "deposit_combo_sources",
            "deposit_assignments",
        ],
    }
    CATALOG.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"total": len(entries), "changed": len(changed), "changed_keys": changed}


if __name__ == "__main__":
    print(json.dumps(sync_catalog(), ensure_ascii=False, indent=2))
