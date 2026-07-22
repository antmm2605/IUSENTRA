"""Coalescenza conservativa tra presidio fascicolo legacy e presidio PEC avanzato."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping


_PROJECTION_KEY = "__legal_notification_projection"
_SOURCE_MARKER_RE = re.compile(
    r"(?:PEC_AUDIT|PEC_SOURCE|SOURCE_MESSAGE_ID|PEC_MESSAGE_ID|AUDIT_ID)\s*[:=]\s*([^\s,;]+)",
    re.IGNORECASE,
)
_CONTAINER_SUFFIXES = (".zip", ".p7m", ".p7s", ".smime")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _document_source_name(value: Any) -> str:
    """Normalizza solo contenitori/firme, senza confondere documenti diversi."""

    name = Path(_text(value).replace("\\", "/")).name.casefold()
    name = re.sub(r"\s+", " ", name).strip()
    changed = True
    while name and changed:
        changed = False
        for suffix in _CONTAINER_SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)].rstrip()
                changed = True
                break
    return name


def _source_ids_from_text(value: Any) -> set[str]:
    return {
        match.group(1).strip().strip("<>[]()\"'").casefold()
        for match in _SOURCE_MARKER_RE.finditer(_text(value))
        if match.group(1).strip()
    }


def _stage(item: Mapping[str, Any]) -> str:
    return _text(item.get("id")).rsplit(":", 1)[-1].casefold()


def _case_family(value: Any) -> str:
    text = _text(value).casefold()
    if any(token in text for token in ("judgment", "sentenza")):
        return "sentenza"
    if any(token in text for token in ("ordinanza", "order")):
        return "ordinanza"
    if any(token in text for token in ("decreto", "decree")):
        return "decreto"
    return ""


def _document_value(document: Any, *keys: str) -> Any:
    if isinstance(document, Mapping):
        for key in keys:
            value = document.get(key)
            if value not in (None, ""):
                return value
        return ""
    for key in keys:
        value = getattr(document, key, "")
        if value not in (None, ""):
            return value
    return ""


def enrich_legacy_projection(
    item: Mapping[str, Any],
    *,
    fascicolo: Any,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Aggiunge impronte interne usando solo i documenti che hanno generato il presidio."""

    monitored = [row for row in (payload.get("documents") or []) if isinstance(row, Mapping)]
    office_monitored = [row for row in monitored if _text(row.get("kind")) == "documento_ufficio"]
    source_monitored = office_monitored or monitored
    monitored_ids = {_text(row.get("id")) for row in source_monitored if _text(row.get("id"))}
    documents = list(getattr(fascicolo, "documenti", []) or [])
    relevant_documents = [
        document
        for document in documents
        if _text(_document_value(document, "id", "documento_id", "uuid")) in monitored_ids
    ]

    names: set[str] = set()
    document_groups: list[list[str]] = []
    source_ids: set[str] = set()
    case_texts: list[str] = []
    for document in relevant_documents:
        document_names: set[str] = set()
        for keys in (
            ("nome", "name", "filename"),
            ("nome_originale", "original_filename"),
            ("nome_portale", "portal_name"),
        ):
            value = _document_value(document, *keys)
            normalized = _document_source_name(value)
            if normalized:
                names.add(normalized)
                document_names.add(normalized)
        if document_names:
            document_groups.append(sorted(document_names))
        direct_source_id = _document_value(
            document,
            "source_message_id",
            "sourceMessageId",
            "pec_message_id",
            "pec_audit_id",
            "pec_id",
            "audit_id",
        )
        if _text(direct_source_id):
            source_ids.add(_text(direct_source_id).strip("<>").casefold())
        note = _document_value(document, "note", "notes", "descrizione", "description")
        source_ids.update(_source_ids_from_text(note))
        case_texts.extend(
            _text(_document_value(document, key))
            for key in ("nome", "tipo", "tipo_atto_portale", "classificazione_portale", "note")
        )

    # Alcuni modelli espongono nel payload il nome professionale ma non il
    # documento grezzo. È utilizzabile solo se resta una fonte univoca.
    if not document_groups:
        for row in source_monitored:
            normalized = _document_source_name(row.get("name") or row.get("nome"))
            if normalized:
                names.add(normalized)
                document_groups.append([normalized])

    for release in payload.get("releasedDocuments") or []:
        if not isinstance(release, Mapping):
            continue
        source_id = _text(release.get("pecId") or release.get("sourceMessageId"))
        if source_id:
            source_ids.add(source_id.strip("<>").casefold())
        normalized = _document_source_name(release.get("nome") or release.get("name"))
        if normalized:
            names.add(normalized)

    enriched = dict(item)
    enriched[_PROJECTION_KEY] = {
        "kind": "legacy",
        "stage": _stage(item),
        "fascicolo_id": _text(item.get("fascicoloId")),
        "source_message_ids": sorted(source_ids),
        "source_document_names": sorted(names),
        "source_document_groups": document_groups,
        "case_family": _case_family(" ".join(case_texts)),
    }
    return enriched


def enrich_advanced_projection(
    item: Mapping[str, Any],
    *,
    notification_case: Any,
) -> dict[str, Any]:
    enriched = dict(item)
    source_message_id = _text(item.get("sourceMessageId")).strip("<>").casefold()
    source_document_name = _document_source_name(item.get("sourceDocumentName"))
    enriched[_PROJECTION_KEY] = {
        "kind": "advanced",
        "stage": _stage(item),
        "fascicolo_id": _text(item.get("fascicoloId")),
        "source_message_ids": [source_message_id] if source_message_id else [],
        "source_document_names": [source_document_name] if source_document_name else [],
        "source_document_groups": [[source_document_name]] if source_document_name else [],
        "case_family": _case_family(notification_case),
    }
    return enriched


def _same_source(legacy: Mapping[str, Any], advanced: Mapping[str, Any]) -> bool:
    compared = False
    legacy_ids = set(legacy.get("source_message_ids") or [])
    advanced_ids = set(advanced.get("source_message_ids") or [])
    if legacy_ids and advanced_ids:
        compared = True
        if legacy_ids.isdisjoint(advanced_ids):
            return False

    legacy_names = set(legacy.get("source_document_names") or [])
    advanced_names = set(advanced.get("source_document_names") or [])
    if legacy_names and advanced_names:
        compared = True
        # Più documenti sorgente nel legacy possono rappresentare più atti:
        # in quel caso non si elimina mai l'aggregato in modo automatico.
        legacy_groups = [set(group or []) for group in legacy.get("source_document_groups") or []]
        if len(legacy_groups) != 1 or legacy_groups[0].isdisjoint(advanced_names):
            return False
    return compared


def _same_projection(legacy: Mapping[str, Any], advanced: Mapping[str, Any]) -> bool:
    if not legacy.get("fascicolo_id") or legacy.get("fascicolo_id") != advanced.get("fascicolo_id"):
        return False
    if not legacy.get("stage") or legacy.get("stage") != advanced.get("stage"):
        return False
    legacy_case = _text(legacy.get("case_family"))
    advanced_case = _text(advanced.get("case_family"))
    if legacy_case and advanced_case and legacy_case != advanced_case:
        return False
    return _same_source(legacy, advanced)


def coalesce_legal_notification_projections(
    legacy_items: Iterable[Mapping[str, Any]],
    advanced_items: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Mantiene l'avanzato e sopprime solo il legacy provatamente equivalente."""

    advanced = [dict(item) for item in advanced_items]
    kept_legacy: list[dict[str, Any]] = []
    suppressed = 0
    for item in legacy_items:
        legacy = dict(item)
        legacy_projection = legacy.get(_PROJECTION_KEY) or {}
        duplicate = any(
            _same_projection(legacy_projection, candidate.get(_PROJECTION_KEY) or {})
            for candidate in advanced
        )
        if duplicate:
            suppressed += 1
        else:
            kept_legacy.append(legacy)

    def _clean(item: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != _PROJECTION_KEY}

    return [_clean(item) for item in (*kept_legacy, *advanced)], suppressed
