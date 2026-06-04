"""Resolver centrale di precompilazione per Template Atti.

Ogni campo risolto mantiene valore, fonte, affidabilità, editabilità e motivi
di assenza. Il servizio accetta oggetti dominio o dict per restare utilizzabile
da compilatore, Jinja e test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date
from typing import Any


CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CORE_CONTEXT_FIELDS = [
    "destinatario_ufficio_giudiziario",
    "cliente_mittente",
    "controparte",
    "counterparty_or_recipient",
    "pratica_collegata",
    "practice_reference",
    "practice_number",
    "practice_subject",
    "practice_data",
    "matter",
    "recipient_or_court",
    "autore",
]

SOURCE_LABELS = {
    "studio_timbro": "timbro studio",
    "studio": "dati studio",
    "utente": "utente corrente",
    "cliente": "cliente",
    "fascicolo": "fascicolo",
    "parti": "parti del fascicolo",
    "documenti": "documenti fascicolo",
    "today": "data odierna",
    "legacy": "dati già presenti",
}

FIELD_LABELS = {
    "recipient_or_court": "Destinatario / ufficio giudiziario",
    "destinatario_ufficio_giudiziario": "Destinatario / ufficio giudiziario",
    "client_or_sender": "Cliente / mittente",
    "cliente_mittente": "Cliente / mittente",
    "counterparty_or_recipient": "Controparte / destinatario",
    "controparte": "Controparte",
    "lawyer": "Difensore",
    "difensore": "Difensore",
    "author_user_id": "Autore",
    "autore": "Autore",
    "case_reference_display": "Riferimento pratica",
    "case_id": "Pratica collegata",
    "pratica_collegata": "Pratica collegata",
    "practice_reference": "Riferimento pratica",
    "practice_number": "Numero / R.G. pratica",
    "practice_subject": "Oggetto pratica",
    "practice_data": "Dati pratica",
    "matter": "Materia",
    "title": "Titolo atto",
    "subject": "Oggetto",
    "oggetto": "Oggetto",
    "facts": "Esposizione dei fatti",
    "attachments_list": "Allegati",
    "documents_offered": "Documenti offerti",
    "supporting_documents": "Documenti a supporto",
    "case_value": "Valore causa",
    "dispute_value": "Valore controversia",
    "court_name": "Ufficio giudiziario",
    "competent_court": "Ufficio giudiziario competente",
    "competent_tar": "TAR competente",
    "competent_tax_court": "Corte di Giustizia Tributaria competente",
    "proceeding_authority": "Autorità procedente",
    "competent_authority": "Autorità competente",
    "plaintiff": "Parte ricorrente",
    "claimant": "Parte istante",
    "applicant": "Parte richiedente",
    "assisted_person": "Assistito",
    "defendant": "Resistente / convenuto",
    "debtor": "Debitore",
    "respondent": "Resistente",
    "tax_authority_or_resistant_party": "Ente impositore / resistente",
    "respondent_administration": "Amministrazione resistente",
    "document_date": "Data atto",
    "signature": "Firma",
    "place": "Luogo",
    "_lawyer_pec": "PEC difensore",
    "_lawyer_tax_id": "Codice fiscale difensore",
    "_studio_address": "Indirizzo studio",
}

DEFAULT_PREFILL_BINDINGS: dict[str, list[str]] = {
    "model_code": ["legacy.model_code"],
    "title": ["legacy.title"],
    "area": ["legacy.area"],
    "act_type": ["legacy.act_type"],
    "case_id": ["fascicolo.id", "legacy.case_id"],
    "pratica_collegata": ["fascicolo.id", "fascicolo.codice", "fascicolo.numero", "legacy.case_id"],
    "practice_id": ["fascicolo.id", "legacy.case_id"],
    "practice_reference": ["fascicolo.practice_reference_display", "fascicolo.rg_completo", "fascicolo.numero_rg", "fascicolo.numero", "fascicolo.id", "legacy.case_reference_display", "legacy.case_id"],
    "practice_number": ["fascicolo.rg_completo", "fascicolo.numero_rg", "fascicolo.numero", "fascicolo.codice", "fascicolo.id"],
    "practice_subject": ["fascicolo.practice_subject_display", "fascicolo.titolo", "fascicolo.oggetto", "legacy.subject"],
    "practice_data": ["fascicolo.titolo", "fascicolo.oggetto", "fascicolo.note", "legacy.subject"],
    "author_user_id": ["studio.avvocato_titolare", "studio.avvocato_nome", "utente.nome_completo", "utente.username", "utente.id", "legacy.author_user_id"],
    "autore": ["studio.avvocato_titolare", "studio.avvocato_nome", "utente.nome_completo", "utente.username", "legacy.author_user_id"],
    "cliente": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.client_or_sender"],
    "cliente_mittente": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.client_or_sender"],
    "controparte": ["parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.counterparty_or_recipient"],
    "difensore": ["studio.avvocato_titolare", "studio.avvocato_nome", "utente.nome_completo", "utente.username", "legacy.lawyer"],
    "ufficio_giudiziario": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.recipient_or_court"],
    "destinatario_ufficio_giudiziario": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "fascicolo.autorita", "legacy.recipient_or_court"],
    "rg": ["fascicolo.rg_completo", "fascicolo.numero_rg", "legacy.case_reference_display"],
    "oggetto": ["fascicolo.titolo", "fascicolo.oggetto", "legacy.subject"],
    "data_atto": ["today", "legacy.document_date"],
    "pec_studio": ["studio_timbro.pec", "studio.pec", "legacy._lawyer_pec"],
    "codice_fiscale_studio": ["studio_timbro.codice_fiscale", "studio.codice_fiscale", "legacy._lawyer_tax_id"],
    "partita_iva_studio": ["studio_timbro.partita_iva", "studio.partita_iva"],
    "recipient_or_court": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "fascicolo.autorita", "legacy.recipient_or_court"],
    "client_or_sender": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.client_or_sender"],
    "counterparty_or_recipient": ["parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.counterparty_or_recipient"],
    "lawyer": ["studio.avvocato_titolare", "studio.avvocato_nome", "utente.nome_completo", "utente.username", "legacy.lawyer"],
    "case_reference_display": ["fascicolo.practice_reference_display", "fascicolo.rg_completo", "fascicolo.numero_rg", "fascicolo.numero", "legacy.case_reference_display"],
    "matter": ["fascicolo.materia", "fascicolo.tipo.value", "fascicolo.tipo", "fascicolo.area", "fascicolo.branca", "legacy.matter"],
    "subject": ["fascicolo.practice_subject_display", "fascicolo.oggetto", "fascicolo.titolo", "legacy.subject"],
    "facts": ["fascicolo.note", "legacy.facts"],
    "document_date": ["today", "legacy.document_date"],
    "signature": ["studio.avvocato_titolare", "studio.avvocato_nome", "utente.nome_completo", "utente.username", "legacy.signature"],
    "attachments_list": ["documenti.nomi", "legacy.attachments_list"],
    "place": ["studio.indirizzo", "studio_timbro.indirizzo_riga", "legacy.place"],
    "_lawyer_pec": ["studio_timbro.pec", "studio.pec", "legacy._lawyer_pec"],
    "_lawyer_tax_id": ["studio_timbro.codice_fiscale", "studio.codice_fiscale", "legacy._lawyer_tax_id"],
    "_studio_address": ["studio_timbro.indirizzo_riga", "studio.indirizzo", "legacy._studio_address"],
    "court_name": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.court_name", "legacy.recipient_or_court"],
    "competent_court": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.competent_court", "legacy.recipient_or_court"],
    "proceeding_authority": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.proceeding_authority", "legacy.recipient_or_court"],
    "competent_authority": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.competent_authority", "legacy.recipient_or_court"],
    "competent_tar": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.competent_tar", "legacy.recipient_or_court"],
    "competent_tax_court": ["fascicolo.tribunale", "fascicolo.ufficio_giudiziario", "legacy.competent_tax_court", "legacy.recipient_or_court"],
    "plaintiff": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.plaintiff", "legacy.client_or_sender"],
    "claimant": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.claimant", "legacy.client_or_sender"],
    "applicant": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.applicant", "legacy.client_or_sender"],
    "assisted_person": ["parti.assistito_principale.nome_completo", "cliente.nome_completo", "legacy.assisted_person", "legacy.client_or_sender"],
    "defendant": ["parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.defendant", "legacy.counterparty_or_recipient"],
    "debtor": ["parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.debtor", "legacy.counterparty_or_recipient"],
    "respondent": ["parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.respondent", "legacy.counterparty_or_recipient"],
    "tax_authority_or_resistant_party": ["fascicolo.ente_impositore", "parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.tax_authority_or_resistant_party"],
    "respondent_administration": ["fascicolo.amministrazione_resistente", "parti.controparte_principale.nome_completo", "fascicolo.controparte", "legacy.respondent_administration"],
    "documents_offered": ["documenti.nomi", "legacy.documents_offered", "legacy.attachments_list"],
    "supporting_documents": ["documenti.nomi", "legacy.supporting_documents", "legacy.attachments_list"],
    "case_value": ["fascicolo.valore_causa", "legacy.case_value"],
    "dispute_value": ["fascicolo.valore_causa", "legacy.dispute_value", "legacy.case_value"],
}

LEGACY_CAMPI_BINDINGS = {
    "cliente": "cliente",
    "controparte": "controparte",
    "difensore": "difensore",
    "ufficio_giudiziario": "ufficio_giudiziario",
    "destinatario / ufficio giudiziario": "destinatario_ufficio_giudiziario",
    "destinatario ufficio giudiziario": "destinatario_ufficio_giudiziario",
    "cliente / mittente": "cliente_mittente",
    "cliente mittente": "cliente_mittente",
    "pratica collegata": "pratica_collegata",
    "autore": "autore",
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
    required: bool = False
    missing_reason: str = ""
    warnings: list[str] | None = None
    alternatives: list[dict[str, Any]] | None = None
    conflict: bool = False
    privacy_level: str = "studio"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = data["warnings"] or []
        data["alternatives"] = data["alternatives"] or []
        return data


def _clean(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_clean(item) for item in value if _clean(item))
    return " ".join(str(value or "").split()).strip()


def _display_value_for_field(name: str, value: Any) -> Any:
    if isinstance(value, list):
        return value
    cleaned = _clean(value)
    if name != "matter" or not cleaned:
        return cleaned
    known_matters = {
        "CIVILE": "Civile",
        "PENALE": "Penale",
        "AMMINISTRATIVO": "Amministrativo",
        "TRIBUTARIO": "Tributario",
        "LAVORO": "Lavoro",
        "PRIVACY": "Privacy",
    }
    mapped = known_matters.get(cleaned.upper())
    if mapped:
        return mapped
    if cleaned.isupper():
        return cleaned[:1].upper() + cleaned[1:].lower()
    return cleaned


def _field_label(name: str) -> str:
    key = str(name or "").strip()
    if not key:
        return "Dato richiesto"
    try:
        from pct.compilatore_atti import campi_catalogo

        catalog_label = _clean((campi_catalogo().get(key) or {}).get("label"))
        if catalog_label:
            return catalog_label
    except Exception:
        pass
    direct = FIELD_LABELS.get(key) or FIELD_LABELS.get(key.lower())
    if direct:
        return direct
    cleaned = key.replace("_", " ").replace("-", " ").strip()
    return cleaned[:1].upper() + cleaned[1:]


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


def _config_path_value(config: Any, path: str) -> Any:
    current = config
    for part in path.split("."):
        current = _value(current, part)
        if current is None:
            return None
    return current


def _first_config_value(config: Any, *paths: str) -> str:
    for path in paths:
        value = _config_path_value(config, path)
        if not _is_empty(value):
            return _clean(value)
    return ""


def _studio_payload(config: Any | None) -> dict[str, Any]:
    config = config or {}
    avvocato = _first_config_value(
        config,
        "studio.avvocato",
        "avvocato",
        "STUDIO_AVVOCATO",
        "PCT_STUDIO_AVVOCATO",
    )
    return {
        "nome": _first_config_value(config, "studio.nome", "STUDIO_NOME"),
        "avvocato_titolare": avvocato,
        "avvocato_nome": avvocato,
        "indirizzo": _first_config_value(config, "studio.indirizzo", "STUDIO_INDIRIZZO"),
        "codice_fiscale": _first_config_value(config, "studio.cf", "STUDIO_CF"),
        "partita_iva": _first_config_value(config, "studio.piva", "STUDIO_PIVA"),
        "pec": _first_config_value(config, "pec.indirizzo", "PCT_STUDIO_PEC", "SMTP_FROM"),
    }


def _timbro_payload(studio_timbro: Any) -> dict[str, Any]:
    if hasattr(studio_timbro, "to_payload"):
        return studio_timbro.to_payload()
    if isinstance(studio_timbro, dict):
        return dict(studio_timbro)
    return {}


class _FascicoloPrefillContext(dict):
    """Espone valori calcolati senza perdere gli attributi originali del fascicolo."""

    def __init__(self, original: Any, computed: dict[str, Any]):
        super().__init__(computed)
        self._original = original

    def get(self, name: str, default: Any = None) -> Any:
        if name in self:
            return super().get(name, default)
        value = _value(self._original, name)
        return default if value is None else value


def _rg_reference_value(fascicolo: Any) -> str:
    raw = _clean(
        _value(fascicolo, "rg_completo")
        or _value(fascicolo, "numero_rg")
        or _value(fascicolo, "numero")
        or _value(fascicolo, "codice")
    )
    if not raw:
        return ""
    raw = re.sub(r"(?i)^r\.?\s*g\.?\s*", "", raw).strip()
    raw = re.sub(r"(?i)\s*r\.?\s*g\.?$", "", raw).strip()
    return raw


def _party_display_name(parti: Any, role: str) -> str:
    party = _value(parti, role)
    return _clean(_value(party, "nome_completo") or _value(party, "nome") or party)


def _practice_reference_display(fascicolo: Any, parti: Any = None) -> str:
    assisted = _party_display_name(parti, "assistito_principale") or _clean(
        _value(fascicolo, "nome_cliente")
        or _value(fascicolo, "cliente")
        or _value(fascicolo, "attore_principale")
    )
    counterparty = _party_display_name(parti, "controparte_principale") or _clean(_value(fascicolo, "controparte"))
    parties_title = f"{assisted} c/ {counterparty}" if assisted and counterparty else ""
    title = parties_title or _practice_subject_display(fascicolo, parti)
    rg_value = _rg_reference_value(fascicolo)
    if title and rg_value:
        return f"{title} - {rg_value}"
    return title or rg_value or _clean(_value(fascicolo, "id"))


def _practice_subject_display(fascicolo: Any, parti: Any = None) -> str:
    assisted = _party_display_name(parti, "assistito_principale") or _clean(
        _value(fascicolo, "nome_cliente")
        or _value(fascicolo, "cliente")
        or _value(fascicolo, "attore_principale")
    )
    counterparty = _party_display_name(parti, "controparte_principale") or _clean(_value(fascicolo, "controparte"))
    if assisted and counterparty:
        return f"{assisted} c/ {counterparty}"
    return _clean(_value(fascicolo, "titolo") or _value(fascicolo, "oggetto"))


def _fascicolo_context(fascicolo: Any, parti: Any = None) -> Any:
    if fascicolo is None:
        return None
    return _FascicoloPrefillContext(
        fascicolo,
        {
            "practice_reference_display": _practice_reference_display(fascicolo, parti),
            "practice_subject_display": _practice_subject_display(fascicolo, parti),
        },
    )


def build_prefill_context(
    *,
    fascicolo: Any = None,
    cliente: Any = None,
    utente: Any = None,
    config: Any = None,
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
        "fascicolo": _fascicolo_context(fascicolo, parti),
        "parti": parti or {},
        "documenti": list(documenti or []),
        "legacy": legacy_payload or {},
    }


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, list) or isinstance(right, list):
        return _clean(left) == _clean(right)
    return _clean(left).casefold() == _clean(right).casefold()


def _privacy_level(source: str) -> str:
    if source in {"cliente", "parti", "fascicolo", "documenti", "legacy"}:
        return "riservato_studio"
    if source in {"studio_timbro", "studio", "utente"}:
        return "studio"
    return "operativo"


def resolve_field(name: str, candidates: list[str], context: dict[str, Any], *, required: bool = False) -> PrefillField:
    alternatives: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in candidates:
        value = _path_value(context, path)
        source = _source_from_path(path)
        if _is_empty(value):
            continue
        normalized_value = _display_value_for_field(name, value)
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
        high_conflict = any(
            alt.get("confidence") == CONFIDENCE_HIGH
            and selected.get("confidence") == CONFIDENCE_HIGH
            and not _same_value(alt.get("value"), selected.get("value"))
            for alt in alternatives[1:]
        )
        if high_conflict:
            warnings.append("Sono presenti dati discordanti in archivi affidabili: conferma il valore prima di usare l'atto.")
        elif alternatives[1:]:
            warnings.append("Sono presenti piu' fonti possibili: verifica il dato prima del deposito.")
        return PrefillField(
            value=selected["value"],
            source=selected["source"],
            source_label=selected["source_label"],
            confidence=selected["confidence"],
            editable=True,
            required=required,
            warnings=warnings,
            alternatives=alternatives[1:],
            conflict=high_conflict,
            privacy_level=_privacy_level(selected["source"]),
        )
    return PrefillField(
        value="",
        source="",
        source_label="",
        confidence=CONFIDENCE_LOW,
        editable=True,
        required=required,
        missing_reason=f"Da completare: {_field_label(name)} non è presente nei dati già disponibili.",
        warnings=[],
        alternatives=[],
        conflict=False,
        privacy_level="riservato_studio" if required else "studio",
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
            normalized_key = str(key).strip()
            if normalized_key in {*CORE_CONTEXT_FIELDS, "author_user_id", "lawyer", "difensore", "signature"}:
                base_candidates = list(DEFAULT_PREFILL_BINDINGS.get(normalized_key, []))
                resolved[normalized_key] = list(dict.fromkeys([*base_candidates, *candidates]))
            else:
                resolved[normalized_key] = candidates
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
    config: Any = None,
    studio_timbro: Any = None,
    parti: Any = None,
    legacy_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_bindings = normalize_prefill_bindings(bindings, legacy_campi=legacy_campi)
    all_required = list(dict.fromkeys([*CORE_CONTEXT_FIELDS, *(required_fields or [])]))
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
        result = resolve_field(field_name, candidates, context, required=field_name in all_required).to_dict()
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


def merge_prefill_values(
    user_values: dict[str, Any] | None,
    resolved_values: dict[str, Any] | None,
    field_sources: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Unisce prefill e input utente senza sovrascrivere valori digitati."""
    user_values = dict(user_values or {})
    resolved_values = dict(resolved_values or {})
    field_sources = field_sources or {}
    merged = dict(resolved_values)
    preserved_user_inputs: list[str] = []
    applied_prefill: list[str] = []
    for key, value in resolved_values.items():
        if _is_empty(user_values.get(key)):
            applied_prefill.append(key)
        else:
            merged[key] = user_values[key]
            preserved_user_inputs.append(key)
    for key, value in user_values.items():
        if key not in merged:
            merged[key] = value
            if not _is_empty(value):
                preserved_user_inputs.append(key)
    missing_reasons = {
        key: data.get("missing_reason")
        for key, data in field_sources.items()
        if _is_empty(merged.get(key)) and data.get("missing_reason")
    }
    return {
        "values": merged,
        "applied_prefill": sorted(set(applied_prefill)),
        "preserved_user_inputs": sorted(set(preserved_user_inputs)),
        "missing_reasons": missing_reasons,
    }


__all__ = [
    "DEFAULT_PREFILL_BINDINGS",
    "PrefillField",
    "build_prefill_context",
    "merge_prefill_values",
    "normalize_prefill_bindings",
    "resolve_field",
    "resolve_template_prefill",
]
