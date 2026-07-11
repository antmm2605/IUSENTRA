"""Runtime helpers for deposit catalog selections."""
from __future__ import annotations

import json
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
        "datiatto_catalog_key": str(entry.get("key") or "").strip(),
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
        "contributo_unificato_richiesto": bool(schema.get("contributionRequired")),
        "contributo_unificato_xml_mode": str(schema.get("contributionXmlMode") or "").strip(),
    }


def deposito_catalogo_busta_metadata(
    hint: dict[str, Any],
    extra: dict[str, Any],
) -> dict[str, Any]:
    """Return the catalog fields consumed directly by ``DatiBusta``."""

    return {
        "datiatto_generator_class": hint.get("datiatto_generator_class", ""),
        "datiatto_root_name": hint.get("datiatto_root_name", ""),
        "datiatto_studio_variable": hint.get("datiatto_studio_variable", ""),
        "datiatto_catalog_key": hint.get("datiatto_catalog_key", ""),
        "datiatto_generator_mode": hint.get("datiatto_generator_mode", ""),
        "datiatto_required_data": hint.get("datiatto_required_data", []),
        "datiatto_extra": extra,
    }


def _field_text(form_like: Any, key: str) -> str:
    try:
        value = form_like.get(key, "")
    except Exception:
        value = ""
    return str(value or "").strip()


def _json_field(form_like: Any, *keys: str) -> Any:
    for key in keys:
        raw = _field_text(form_like, key)
        if not raw:
            continue
        try:
            return json.loads(raw)
        except Exception as exc:
            raise ValueError(f"Campo {key} non leggibile: deve essere JSON valido.") from exc
    return None


def deposito_catalogo_datiatto_extra(form_like: Any) -> dict[str, Any]:
    """Estrae i dati specialistici usati dai generatori ministeriali dedicati."""

    extra: dict[str, Any] = {}
    parsed = _json_field(form_like, "datiatto_extra", "dati_atto_extra", "dati_deposito_specifici")
    if isinstance(parsed, dict):
        extra.update(parsed)
    elif parsed is not None:
        raise ValueError("I dati specifici deposito devono essere un oggetto JSON.")

    scalar_fields = (
        "parte_codice_fiscale",
        "avvocato_codice_fiscale",
        "procedente_codice_fiscale",
        "debitore_codice_fiscale",
        "tipo_pignoramento",
        "data_consegna_pignoramento",
        "importo_precetto",
        "data_pignoramento",
        "data_notifica_precetto",
        "stima_diritto",
        "data_citazione",
        "data_notifica_pignoramento",
        "cronologico_pignoramento",
        "deposito_progetto",
        "data_notifica_citazione",
        "precedente_provvedimento_numero",
        "precedente_provvedimento_anno",
        "precedente_fascicolo_numero",
        "precedente_fascicolo_anno",
        "data_precedente_provvedimento",
        "decreto_numero",
        "decreto_anno",
        "decreto_data",
        "decreto_causa_numero",
        "decreto_causa_anno",
        "credito_capitale",
        "credito_importo",
        "credito_data_decorrenza",
        "credito_data_aggiornamento",
        "lotto_numero",
        "tipo_ricorso_cassazione",
        "data_richiesta_notifica_cassazione",
        "data_effettiva_notifica_cassazione",
        "materia_ricorso_cassazione",
        "parole_chiave_cassazione",
        "inizio_primo_grado_anno",
        "inizio_primo_grado_ufficio",
    )
    for field in scalar_fields:
        value = _field_text(form_like, field)
        if value:
            extra[field] = value

    json_fields = {
        "beni_pignorati": ("beni_pignorati", "beni_pignorati_json"),
        "titolo": ("titolo", "titolo_json"),
        "custode": ("custode", "custode_json"),
        "terzo": ("terzo", "terzo_json"),
        "terzi": ("terzi", "terzi_json"),
        "provvedimento_impugnato": ("provvedimento_impugnato", "provvedimento_impugnato_json"),
        "motivi_cassazione": ("motivi_cassazione", "motivi_cassazione_json"),
        "contromotivi_cassazione": ("contromotivi_cassazione", "contromotivi_cassazione_json"),
    }
    for target, aliases in json_fields.items():
        value = _json_field(form_like, *aliases)
        if value is not None:
            extra[target] = value
    return extra


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
