"""Resolver centrale di precompilazione per Template Atti.

Ogni campo risolto mantiene valore, fonte, affidabilita', editabilita' e motivi
di assenza. Il servizio accetta oggetti dominio o dict per restare utilizzabile
da compilatore, Jinja e test.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any


CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

SOURCE_LABELS = {
    "studio_timbro": "timbro studio",
    "studio": "dati studio",
    "utente": "utente corrente",
    "cliente": "cliente",
    "fascicolo": "fascicolo",
    "parti": "parti del fascicolo",
    "documenti": "documenti fascicolo",
    "today": "data odierna",
    "legacy": "precompilazione esistente",
}

DEFAULT_PREFILL_BINDINGS: dict[str, list[str]] = {
    "cliente": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.client_or_sender"],
    "controparte": ["parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.counterparty_or_recipient"],
    "difensore": ["utente.nome_completo", "studio.avvocato_nome", "legacy.lawyer"],
    "ufficio_giudiziario": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.recipient_or_court"],
    "rg": ["fascicolo.rg_completo", "fascicolo.numero_rg", "legacy.case_reference_display"],
    "oggetto": ["fascicolo.titolo", "fascicolo.oggetto", "legacy.subject"],
    "data_atto": ["today", "legacy.document_date"],
    "pec_studio": ["studio_timbro.pec", "studio.pec", "legacy._lawyer_pec"],
    "codice_fiscale_studio": ["studio_timbro.codice_fiscale", "studio.codice_fiscale", "legacy._lawyer_tax_id"],
    "partita_iva_studio": ["studio_timbro.partita_iva", "studio.partita_iva"],
    "client_or_sender": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.client_or_sender"],
    "counterparty_or_recipient": ["parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.counterparty_or_recipient"],
    "lawyer": ["utente.nome_completo", "studio.avvocato_nome", "legacy.lawyer"],
    "recipient_or_court": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.recipient_or_court"],
    "case_reference_display": ["fascicolo.rg_completo", "fascicolo.numero_rg", "fascicolo.numero", "legacy.case_reference_display"],
    "matter": ["fascicolo.tipo.value", "fascicolo.materia", "legacy.matter"],
    "subject": ["fascicolo.oggetto", "fascicolo.titolo", "legacy.subject"],
    "facts": ["fascicolo.note", "legacy.facts"],
    "document_date": ["today", "legacy.document_date"],
    "signature": ["utente.nome_completo", "studio.avvocato_nome", "legacy.signature"],
    "attachments_list": ["documenti.nomi", "legacy.attachments_list"],
    "place": ["studio.indirizzo", "studio_timbro.indirizzo_riga", "legacy.place"],
    "_lawyer_pec": ["studio_timbro.pec", "studio.pec", "legacy._lawyer_pec"],
    "_lawyer_tax_id": ["studio_timbro.codice_fiscale", "studio.codice_fiscale", "legacy._lawyer_tax_id"],
    "_studio_address": ["studio_timbro.indirizzo_riga", "studio.indirizzo", "legacy._studio_address"],
}

LEGACY_CAMPI_BINDINGS = {
    "cliente": "cliente",
    "controparte": "controparte",
    "difensore": "difensore",
    "ufficio_giudiziario": "ufficio_giudiziario",
    "rg": "rg",
    "oggetto": "oggetto",
    "data_atto": "data_atto",
}


@dataclass
class PrefillField:
    value: Any = ""
    source: str = ""
    source_label: str = ""
    confidence: str = CONFIDENCE_LOW
    editable: bool = True
    missing_reason: str = ""
    warnings: list[str] | None = None
    alternatives: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = data["warnings"] or []
        data["alternatives"] = data["alternatives"] or []
        return data


def _clean(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_clean(item) for item in value if _clean(item))
    return " ".join(str(value or "").split()).strip()


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return not bool(value)
    return _clean(value) == ""


def _value(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _path_value(context: dict[str, Any], path: str) -> Any:
    if path == "today":
        return date.today().isoformat()
    current: Any = context
    for part in path.split("."):
        if part == "nomi" and isinstance(current, list):
            return [_clean(_value(item, "nome") or _value(item, "filename") or item) for item in current if _clean(_value(item, "nome") or _value(item, "filename") or item)]
        current = _value(current, part)
        if current is None:
            return None
    return current


def _source_from_path(path: str) -> str:
    if path == "today":
        return "today"
    return path.split(".", 1)[0]


def _confidence(source: str, value: Any) -> str:
    if source in {"studio_timbro", "cliente", "fascicolo", "parti", "utente", "today"} and not _is_empty(value):
        return CONFIDENCE_HIGH
    if source in {"studio", "documenti"} and not _is_empty(value):
        return CONFIDENCE_MEDIUM
    if source == "legacy" and not _is_empty(value):
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def _studio_payload(config: dict[str, Any] | None) -> dict[str, Any]:
    config = config or {}
    return {
        "nome": config.get("STUDIO_NOME", ""),
        "avvocato_nome": config.get("STUDIO_AVVOCATO", ""),
        "indirizzo": config.get("STUDIO_INDIRIZZO", ""),
        "codice_fiscale": config.get("STUDIO_CF", ""),
        "partita_iva": config.get("STUDIO_PIVA", ""),
        "pec": config.get("PCT_STUDIO_PEC", "") or config.get("SMTP_FROM", ""),
    }


def _timbro_payload(studio_timbro: Any) -> dict[str, Any]:
    if hasattr(studio_timbro, "to_payload"):
        return studio_timbro.to_payload()
    if isinstance(studio_timbro, dict):
        return dict(studio_timbro)
    return {}


def build_prefill_context(
    *,
    fascicolo: Any = None,
    cliente: Any = None,
    utente: Any = None,
    config: dict[str, Any] | None = None,
    studio_timbro: Any = None,
    parti: Any = None,
    legacy_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    documenti = _value(fascicolo, "documenti") or []
    return {
        "studio_timbro": _timbro_payload(studio_timbro),
        "studio": _studio_payload(config),
        "utente": utente,
        "cliente": cliente,
        "fascicolo": fascicolo,
        "parti": parti or {},
        "documenti": list(documenti or []),
        "legacy": legacy_payload or {},
    }


def resolve_field(name: str, candidates: list[str], context: dict[str, Any]) -> PrefillField:
    alternatives: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in candidates:
        value = _path_value(context, path)
        source = _source_from_path(path)
        if _is_empty(value):
            continue
        normalized_value = value if isinstance(value, list) else _clean(value)
        if alternatives:
            warnings.append("Sono presenti piu' fonti possibili: verifica il dato prima del deposito.")
        alternatives.append(
            {
                "value": normalized_value,
                "source": source,
                "source_label": SOURCE_LABELS.get(source, source.replace("_", " ")),
                "confidence": _confidence(source, normalized_value),
            }
        )
    if alternatives:
        selected = alternatives[0]
        return PrefillField(
            value=selected["value"],
            source=selected["source"],
            source_label=selected["source_label"],
            confidence=selected["confidence"],
            editable=True,
            warnings=warnings,
            alternatives=alternatives[1:],
        )
    return PrefillField(
        value="",
        source="",
        source_label="",
        confidence=CONFIDENCE_LOW,
        editable=True,
        missing_reason="Dato non presente negli archivi selezionati.",
        warnings=[],
        alternatives=[],
    )


def normalize_prefill_bindings(
    bindings: dict[str, list[str]] | None = None,
    *,
    legacy_campi: list[str] | None = None,
) -> dict[str, list[str]]:
    resolved = {key: list(value) for key, value in DEFAULT_PREFILL_BINDINGS.items()}
    for field in legacy_campi or []:
        key = LEGACY_CAMPI_BINDINGS.get(_clean(field).lower(), _clean(field).lower().replace(" ", "_"))
        if key and key in DEFAULT_PREFILL_BINDINGS:
            resolved.setdefault(key, list(DEFAULT_PREFILL_BINDINGS[key]))
    for key, value in (bindings or {}).items():
        candidates = [str(item).strip() for item in (value if isinstance(value, list) else [value]) if str(item).strip()]
        if candidates:
            resolved[str(key).strip()] = candidates
    return resolved


def resolve_template_prefill(
    *,
    model_code: str = "",
    bindings: dict[str, list[str]] | None = None,
    required_fields: list[str] | None = None,
    optional_fields: list[str] | None = None,
    legacy_campi: list[str] | None = None,
    fascicolo: Any = None,
    cliente: Any = None,
    utente: Any = None,
    config: dict[str, Any] | None = None,
    studio_timbro: Any = None,
    parti: Any = None,
    legacy_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_bindings = normalize_prefill_bindings(bindings, legacy_campi=legacy_campi)
    all_required = list(dict.fromkeys(required_fields or []))
    all_optional = list(dict.fromkeys(optional_fields or []))
    for key in normalized_bindings:
        if key not in all_required and key not in all_optional:
            all_optional.append(key)
    context = build_prefill_context(
        fascicolo=fascicolo,
        cliente=cliente,
        utente=utente,
        config=config,
        studio_timbro=studio_timbro,
        parti=parti,
        legacy_payload=legacy_payload,
    )
    fields: dict[str, dict[str, Any]] = {}
    values: dict[str, Any] = {}
    for field_name in list(dict.fromkeys(all_required + all_optional)):
        candidates = normalized_bindings.get(field_name) or DEFAULT_PREFILL_BINDINGS.get(field_name) or [f"legacy.{field_name}"]
        result = resolve_field(field_name, candidates, context).to_dict()
        fields[field_name] = result
        if not _is_empty(result.get("value")):
            values[field_name] = result["value"]
    required_missing = [field for field in all_required if _is_empty(fields.get(field, {}).get("value"))]
    optional_missing = [field for field in all_optional if field not in all_required and _is_empty(fields.get(field, {}).get("value"))]
    sources = sorted(
        {
            data.get("source_label")
            for data in fields.values()
            if data.get("source_label") and not _is_empty(data.get("value"))
        }
    )
    return {
        "model_code": model_code,
        "bindings": normalized_bindings,
        "values": values,
        "fields": fields,
        "required_fields": all_required,
        "optional_fields": all_optional,
        "required_missing": required_missing,
        "optional_missing": optional_missing,
        "available_count": len(values),
        "missing_count": len(required_missing) + len(optional_missing),
        "sources": sources,
        "complete": not required_missing,
        "warnings": [
            warning
            for field_data in fields.values()
            for warning in (field_data.get("warnings") or [])
            if warning
        ],
    }


__all__ = [
    "DEFAULT_PREFILL_BINDINGS",
    "PrefillField",
    "build_prefill_context",
    "normalize_prefill_bindings",
    "resolve_field",
    "resolve_template_prefill",
]

