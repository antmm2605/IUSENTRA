"""Small helpers for fascicolo document signature options."""

from __future__ import annotations

from typing import Any


FIRMA_VISIBILE_MODE_LABELS = {
    "laterale": "Laterale verticale",
    "basso_sinistra": "In basso a sinistra",
    "basso_destra": "In basso a destra",
}

FIRMA_VISIBILE_DATETIME_LABELS = {
    "data_ora": "Data e ora",
    "solo_data": "Solo data",
    "nessuna": "Nessuna data",
}


def resolve_pkcs11_runtime_config(cfg_firma: Any, slot_raw: Any) -> Any:
    from dataclasses import replace as _dc_replace

    slot = None
    if slot_raw is not None:
        try:
            slot = int(slot_raw)
        except (ValueError, TypeError):
            slot = None
    elif cfg_firma:
        slot_cfg = getattr(cfg_firma, "pkcs11_slot", "")
        if str(slot_cfg).strip().isdigit():
            slot = int(slot_cfg)
    label = getattr(cfg_firma, "pkcs11_label", "") if cfg_firma else None

    cfg_runtime = _dc_replace(cfg_firma, pkcs11_slot=str(slot)) if slot is not None else cfg_firma
    if label:
        cfg_runtime = _dc_replace(cfg_runtime, pkcs11_label=label)
    return cfg_runtime


def normalizza_data_ora_firma_visibile(value: Any) -> str:
    try:
        from visible_signature import normalize_visible_signature_datetime_mode

        return normalize_visible_signature_datetime_mode(value)
    except Exception:
        raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if raw in {"solo_data", "data", "date"}:
            return "solo_data"
        if raw in {"nessuna", "nessuno", "none", "off", "senza_data"}:
            return "nessuna"
        return "data_ora"


def nota_con_firma_visibile(
    note: str,
    mode: str,
    place: str = "",
    datetime_mode: str = "data_ora",
) -> str:
    base = str(note or "Versione firmata per deposito").strip()
    marker = "posizione firma visibile:"
    marker_at = base.casefold().rfind(marker)
    if marker_at >= 0 and "\n" not in base[:marker_at]:
        base = base[:marker_at].rstrip(" .;")
    label = FIRMA_VISIBILE_MODE_LABELS.get(str(mode or "").strip(), FIRMA_VISIBILE_MODE_LABELS["laterale"])
    dettagli = [f"Posizione firma visibile: {label}"]
    place = str(place or "").strip()
    if place:
        dettagli.append(f"Luogo firma: {place}")
    datetime_label = FIRMA_VISIBILE_DATETIME_LABELS.get(
        normalizza_data_ora_firma_visibile(datetime_mode),
        FIRMA_VISIBILE_DATETIME_LABELS["data_ora"],
    )
    dettagli.append(f"Data/ora firma visibile: {datetime_label}")
    return f"{base.rstrip('. ')}. {'; '.join(dettagli)}."
