"""Runtime helpers for deposit catalog selections."""
from __future__ import annotations

from typing import Any

from pct.deposito_telematico_catalogo import resolve_deposit_type_payload


def deposito_catalogo_entry(form_like: Any) -> tuple[dict[str, Any] | None, str]:
    key = str(form_like.get("tipo_deposito_telematico_key", "") or "").strip()
    if not key:
        return None, ""
    entry = resolve_deposit_type_payload(key)
    if not entry:
        return None, "Tipo deposito non trovato nel catalogo backend."
    return entry, ""


def deposito_catalogo_apply(entry: dict[str, Any] | None, tipo_atto: str, codice_registro: str) -> tuple[str, str]:
    if not entry:
        return tipo_atto, codice_registro
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    return (
        str(payload.get("tipo_atto") or tipo_atto).strip() or tipo_atto,
        str(payload.get("codice_registro") or codice_registro).strip() or codice_registro,
    )


def deposito_catalogo_datiatto_hint(entry: dict[str, Any] | None) -> dict[str, Any]:
    if not entry:
        return {}
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    schema = entry.get("schema") if isinstance(entry.get("schema"), dict) else {}
    return {
        "datiatto_generator_class": str(
            payload.get("datiatto_generator_class") or schema.get("generatorClass") or ""
        ).strip(),
        "datiatto_root_name": str(payload.get("datiatto_root_name") or schema.get("ministerialRoot") or "").strip(),
        "datiatto_studio_variable": str(
            payload.get("datiatto_studio_variable") or schema.get("studioVariable") or ""
        ).strip(),
        "datiatto_generator_mode": str(
            payload.get("datiatto_generator_mode") or schema.get("generatorMode") or ""
        ).strip(),
        "datiatto_required_data": list(schema.get("requiredData") or []),
    }


def deposito_catalogo_blocker(entry: dict[str, Any] | None, *, require_real_package: bool) -> str:
    if not entry:
        return ""
    rules = entry.get("rules") if isinstance(entry.get("rules"), dict) else {}
    if not bool(rules.get("can_prepare_in_pct_panel", True)):
        return str(
            rules.get("real_send_blocker")
            or "Questo tipo appartiene a un canale diverso dal deposito PCT civile."
        )
    if require_real_package and not bool(rules.get("real_send_allowed_from_pct_panel", True)):
        return str(
            rules.get("real_send_blocker")
            or "Questo tipo deposito non può essere inviato dal pannello PCT corrente."
        )
    return ""
