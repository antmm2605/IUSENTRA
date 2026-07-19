"""Bridge dati per le superfici React Fascicoli.

Il modulo normalizza repository, azioni e metadati del dominio Fascicoli:
lettura tramite API React, scritture demandate ai servizi Flask già auditati.
"""

from __future__ import annotations


from pct.formatting import format_euro_it
import json
import os
import re
import hashlib
import time
import threading
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context

from pct import __version__ as APP_VERSION
from pct.fascicoli import AvanzamentoPratica, EsitoAttivita, StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.fascicolo_workspace import build_fascicolo_workspace
from pct.deposito_telematico_catalogo import build_deposit_catalog_payload
from pct.deposito_simulazione import is_simulated_deposit, next_receipt_phase, receipt_steps
from pct.fascicolo_document_catalog import (
    DocumentCatalogClassification,
    classify_fascicolo_document,
    document_ai_texts_for_catalog,
)
from pct.fascicolo_document_presidio import (
    analyze_fascicolo_document_texts,
    duplicate_practice_groups,
    normalise_practice_duplicate_key,
)
from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio
from pct.notifiche_legali import office_notification_evidence_from_pec
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry, codice_oggetto_pst_payload
from pct.presidio_documentale_state import (
    build_marker as build_presidio_documentale_marker,
    marker_is_current as presidio_marker_is_current,
    marker_state as presidio_marker_state,
)
from pct.presidio_processuale_ruleset import is_pagopa_rt_contributo_xml, is_pagopa_rt_xml
from pct.document_signature_state import (
    document_bytes_have_real_digital_signature,
    document_has_real_digital_signature,
    document_has_signed_container,
)
from web.services.deposito_anagrafica_ministeriale import deposito_ministerial_readiness
from web.services.react_practice_engine_bridge import build_react_practice_engine_payload

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
ROME_TZ = ZoneInfo("Europe/Rome")
ECONOMIC_DOCUMENT_ANALYSIS_VERSION = "2026-07-13-cu-all-indexed-v5"

_FASCICOLI_LIST_BASE_TTL_SECONDS = max(
    0.0,
    float(os.getenv("IUSENTRA_REACT_FASCICOLI_BASE_TTL_SECONDS") or 90),
)
_FASCICOLI_LIST_BASE_MAX_ENTRIES = max(
    1,
    int(os.getenv("IUSENTRA_REACT_FASCICOLI_BASE_MAX_ENTRIES") or 64),
)
_FASCICOLI_LIST_BASE_CACHE_LOCK = threading.Lock()
_FASCICOLI_LIST_BASE_CACHE: OrderedDict[tuple, tuple[float, str]] = OrderedDict()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _current_tenant_id() -> str:
    try:
        from flask import g

        tenant = getattr(g, "tenant", None)
        value = (
            getattr(tenant, "id", "")
            or getattr(tenant, "slug", "")
            or getattr(g, "tenant_context_slug", "")
        )
        return _text(value)
    except Exception:
        return ""


def _current_cache_scope() -> str:
    tenant_id = _current_tenant_id()
    if tenant_id:
        return tenant_id.lower()
    if has_app_context():
        for key in ("DATA_ROOT", "FASCICOLI_DB", "CLIENTI_DB"):
            value = current_app.config.get(key)
            if value:
                return _text(value).strip().lower()
    return "default"


def clear_react_fascicoli_base_cache() -> None:
    """Svuota la base lista fascicoli usata per paginazione veloce."""

    with _FASCICOLI_LIST_BASE_CACHE_LOCK:
        _FASCICOLI_LIST_BASE_CACHE.clear()


def _current_user_cache_id() -> str:
    try:
        from flask import g

        user = getattr(g, "utente_corrente", None) or getattr(g, "user", None)
        return _text(
            getattr(user, "id", "")
            or getattr(user, "username", "")
            or getattr(user, "email", "")
            or "api"
        ).lower()
    except Exception:
        return "api"


def _fascicoli_base_cache_key(
    *,
    query: str,
    client_filter: str,
    rg_filter: str,
    type_filter: str,
    status_filter: str,
    court: str,
    sort: str,
    view: str,
    alerts_only: bool,
    payments_only: bool,
    missing_rg_only: bool,
    duplicates_only: bool,
    payment_filters: dict[str, str] | None,
) -> tuple | None:
    if _FASCICOLI_LIST_BASE_TTL_SECONDS <= 0:
        return None
    filters = tuple(
        sorted(
            (
                _normalise_payment_kind(kind) or _text(kind).lower(),
                _text(value).strip().lower(),
            )
            for kind, value in (payment_filters or {}).items()
        )
    )
    return (
        "fascicoli-list-base",
        _current_cache_scope(),
        _current_user_cache_id(),
        APP_VERSION,
        _text(query).strip().lower(),
        _text(client_filter).strip().lower(),
        _text(rg_filter).strip().lower(),
        _text(type_filter).strip().lower(),
        _text(status_filter).strip().lower(),
        _text(court).strip().lower(),
        _text(sort, "rg").strip().lower(),
        _text(view).strip().lower(),
        bool(alerts_only),
        bool(payments_only),
        bool(missing_rg_only),
        bool(duplicates_only),
        filters,
    )


def _fascicoli_base_cache_get(key: tuple | None) -> dict[str, Any] | None:
    if key is None:
        return None
    now = time.monotonic()
    with _FASCICOLI_LIST_BASE_CACHE_LOCK:
        entry = _FASCICOLI_LIST_BASE_CACHE.get(key)
        if entry is None:
            return None
        expires_at, payload_json = entry
        if expires_at < now:
            _FASCICOLI_LIST_BASE_CACHE.pop(key, None)
            return None
        _FASCICOLI_LIST_BASE_CACHE.move_to_end(key)
    try:
        payload = json.loads(payload_json)
    except Exception:
        with _FASCICOLI_LIST_BASE_CACHE_LOCK:
            _FASCICOLI_LIST_BASE_CACHE.pop(key, None)
        return None
    return payload if isinstance(payload, dict) else None


def _fascicoli_base_cache_set(key: tuple | None, payload: dict[str, Any]) -> None:
    if key is None or _FASCICOLI_LIST_BASE_TTL_SECONDS <= 0:
        return
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return
    expires_at = time.monotonic() + _FASCICOLI_LIST_BASE_TTL_SECONDS
    with _FASCICOLI_LIST_BASE_CACHE_LOCK:
        _FASCICOLI_LIST_BASE_CACHE[key] = (expires_at, payload_json)
        _FASCICOLI_LIST_BASE_CACHE.move_to_end(key)
        while len(_FASCICOLI_LIST_BASE_CACHE) > _FASCICOLI_LIST_BASE_MAX_ENTRIES:
            _FASCICOLI_LIST_BASE_CACHE.popitem(last=False)


def _current_tenant_catalog_ids() -> list[str]:
    values: list[str] = []
    try:
        from flask import g

        tenant = getattr(g, "tenant", None)
        for attr in ("slug", "storage_key", "id"):
            value = _text(getattr(tenant, attr, ""))
            if value and value not in values:
                values.append(value)
        for attr in ("tenant_context_slug", "api_tenant_slug"):
            value = _text(getattr(g, attr, ""))
            if value and value not in values:
                values.append(value)
    except Exception:
        pass
    current = _current_tenant_id()
    if current and current not in values:
        values.append(current)
    return values


def _short_hash(value: str) -> str:
    text = _text(value)
    return f"{text[:12]}...{text[-8:]}" if len(text) > 24 else text


def _audit_kind_label(kind: str) -> str:
    labels = {
        "ACT_GENERATED": "Atto generato",
        "PEC_SENT": "PEC inviata",
        "PEC_RECEIPT_ACQUIRED": "Ricevuta PEC acquisita",
        "DEPOSIT_ATTEMPT": "Tentativo deposito",
        "DEPOSIT_ACCEPTED": "Deposito accettato",
        "DEPOSIT_FAILED": "Deposito non riuscito",
        "DOC_VIEWED": "Documento consultato",
        "DOC_DOWNLOADED": "Documento scaricato",
        "INCIDENT_OPENED": "Incidente aperto",
        "INCIDENT_UPDATED": "Incidente aggiornato",
        "RECEIPT_ISSUED": "Ricevuta cliente emessa",
    }
    return labels.get(_text(kind).upper(), "Evento tracciato")


def _audit_kind_tone(kind: str) -> str:
    value = _text(kind).upper()
    if value in {"DEPOSIT_FAILED", "INCIDENT_OPENED", "INCIDENT_UPDATED"}:
        return "danger"
    if value in {"DEPOSIT_ACCEPTED", "PEC_RECEIPT_ACQUIRED", "RECEIPT_ISSUED"}:
        return "success"
    if value in {"DEPOSIT_ATTEMPT", "PEC_SENT"}:
        return "warning"
    return "primary"


def _audit_trail(fid: str) -> dict[str, Any]:
    tenant_id = _current_tenant_id()
    fallback = {
        "enabled": False,
        "available": False,
        "status": "not_configured",
        "message": "Presidio probatorio da configurare: scarico prova non disponibile.",
        "events": [],
        "summary": {
            "total": 0,
            "signed": 0,
            "worm": 0,
            "snapshotted": 0,
            "tsaVerified": 0,
        },
        "actions": {"bundle": ""},
    }
    if not tenant_id:
        return fallback
    try:
        from flask import current_app

        from audit.service import AuditService, audit_config_diagnostics

        diagnostics = audit_config_diagnostics(current_app.config)
        if not diagnostics.get("ready"):
            return {
                **fallback,
                "enabled": bool(diagnostics.get("enabled")),
                "status": "configuration_required",
                "message": "Presidio probatorio da configurare: scarico prova non disponibile finche' archiviazione immutabile e firma non sono attive.",
                "configuration": diagnostics,
            }
        service = current_app.extensions.get("legal_audit_service")
        if not isinstance(service, AuditService):
            if not current_app.config.get("AUDIT_ENABLED"):
                return fallback
            service = AuditService.from_config(current_app.config)
            current_app.extensions["legal_audit_service"] = service
        rows = service.repository.list_events(tenant_id=tenant_id, fascicolo_id=fid, limit=100)
    except Exception:
        return fallback
    events = []
    for row in sorted(rows, key=lambda item: (str(item.get("event_ts_utc") or ""), str(item.get("event_id") or "")), reverse=True):
        event_id = _text(row.get("event_id"))
        event_hash = _text(row.get("event_hash"))
        snapshot_id = _text(row.get("snapshot_id"))
        events.append(
            {
                "eventId": event_id,
                "kind": _text(row.get("kind")),
                "kindLabel": _audit_kind_label(_text(row.get("kind"))),
                "eventTsUtc": _text(row.get("event_ts_utc")),
                "eventHash": event_hash,
                "eventHashShort": _short_hash(event_hash),
                "prevEventHash": _text(row.get("prev_event_hash")),
                "signed": bool(_text(row.get("signature_alg")) and _text(row.get("signer_kid"))),
                "signatureAlg": _text(row.get("signature_alg")),
                "worm": bool(_text(row.get("worm_bucket")) and _text(row.get("worm_key")) and _text(row.get("worm_version_id"))),
                "snapshotId": snapshot_id,
                "inSnapshot": bool(snapshot_id),
                "tsaVerified": False,
                "tone": _audit_kind_tone(_text(row.get("kind"))),
                "proofHref": f"/registro/proof/{event_id}",
            }
        )
    return {
        "enabled": True,
        "available": True,
        "status": "ready",
        "message": "",
        "events": events,
        "summary": {
            "total": len(events),
            "signed": sum(1 for item in events if item["signed"]),
            "worm": sum(1 for item in events if item["worm"]),
            "snapshotted": sum(1 for item in events if item["inSnapshot"]),
            "tsaVerified": sum(1 for item in events if item["tsaVerified"]),
        },
        "actions": {"bundle": f"/registro/bundle/fascicolo/{quote(fid)}"},
    }


def _audit_trail_placeholder() -> dict[str, Any]:
    return {
        "enabled": True,
        "available": True,
        "status": "lazy_non_caricato",
        "message": "Apri la sezione Audit per caricare le evidenze del fascicolo.",
        "events": [],
        "summary": {
            "total": 0,
            "signed": 0,
            "worm": 0,
            "snapshotted": 0,
            "tsaVerified": 0,
        },
        "actions": {"bundle": ""},
    }


def _empty_notification_relata() -> dict[str, Any]:
    return {
        "status": "monitoraggio",
        "statusLabel": "Monitoraggio attivo",
        "tone": "neutral",
        "releaseDetected": False,
        "pendingPortalDocuments": 0,
        "portalDocuments": 0,
        "officeDocuments": 0,
        "relataDocuments": 0,
        "signedRelataDocuments": 0,
        "proofDocuments": 0,
        "acquisitionHref": "/portali/pst/acquisizione?focus=documenti",
        "prepareHref": "/notifiche-legali#notifica",
        "depositHref": "/notifiche-legali#deposito",
        "primaryHref": "/portali/pst/acquisizione?focus=documenti",
        "primaryLabel": "Verifica portale",
        "systemNotification": "Apri la sezione Relata notifica per caricare il presidio.",
        "releasedDocuments": [],
        "documents": [],
        "steps": [],
    }


def _signature_settings(get_config_studio: Callable[[], Any] | None) -> dict[str, str]:
    mode = "laterale"
    place = ""
    if not callable(get_config_studio):
        return {
            "visibleSignatureMode": mode,
            "visibleSignaturePlace": place,
            "visibleSignatureDatetimeMode": "data_ora",
        }
    try:
        from visible_signature import normalize_visible_signature_mode, resolve_visible_signature_place

        config = get_config_studio().config
        firma_cfg = getattr(config, "firma", None)
        studio_cfg = getattr(config, "studio", None)
        mode = normalize_visible_signature_mode(getattr(firma_cfg, "visible_signature_mode", mode))
        place = resolve_visible_signature_place(
            city=getattr(studio_cfg, "city", "") if studio_cfg else "",
            province=getattr(studio_cfg, "province", "") if studio_cfg else "",
            address=getattr(studio_cfg, "indirizzo", "") if studio_cfg else "",
        )
    except Exception:
        pass
    return {
        "visibleSignatureMode": mode,
        "visibleSignaturePlace": place,
        "visibleSignatureDatetimeMode": "data_ora",
    }


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _fascicolo_lookup_keys(fascicolo: Any) -> set[str]:
    fields = (
        "id",
        "id_pratica",
        "numero",
        "numero_interno",
        "numero_rg",
        "riferimento",
        "reference",
        "codice",
        "codice_fascicolo",
        "source_external_id",
        "import_log_id",
    )
    keys = {_text(getattr(fascicolo, field, "")) for field in fields}
    keys.update({_text(getattr(fascicolo, "id", "")).upper(), _text(getattr(fascicolo, "id", "")).lower()})
    return {key for key in keys if key}


_RG_PREFIXED_RE = re.compile(
    r"\b(?:r\s*\.?\s*g\s*\.?|rg|n\s*\.?\s*causa|numero\s+di\s+ruolo(?:\s+generale)?)"
    r"\s*[:#]?\s*(\d{1,7})\s*[/.-]\s*((?:19|20)\d{2})(?:\s*/\s*[A-Z]{1,8})?\b",
    re.IGNORECASE,
)
_RG_STANDALONE_RE = re.compile(
    r"^\s*(?:r\s*\.?\s*g\s*\.?|rg)?\s*[:#]?\s*(\d{1,7})\s*[/.-]\s*((?:19|20)\d{2})(?:\s*/\s*[A-Z]{1,8})?\s*$",
    re.IGNORECASE,
)


def _identity_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).casefold()).strip()


def _canonical_rg_reference(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    match = _RG_STANDALONE_RE.match(raw) or _RG_PREFIXED_RE.search(raw)
    if not match:
        return ""
    try:
        number = str(int(match.group(1)))
    except (TypeError, ValueError):
        number = match.group(1).lstrip("0") or match.group(1)
    return f"{number}/{match.group(2)}"


def _fascicolo_rg_key(fascicolo: Any) -> str:
    candidates = [
        _rg(fascicolo),
        getattr(fascicolo, "numero_rg", ""),
    ]
    numero = _text(getattr(fascicolo, "numero_rg", ""))
    anno = _text(getattr(fascicolo, "anno_rg", ""))
    if numero and anno:
        candidates.append(f"{numero}/{anno}")
    for candidate in candidates:
        rg = _canonical_rg_reference(candidate)
        if rg:
            return rg
    return ""


def _deadline_text_blob(scadenza: Any) -> str:
    fields = [
        getattr(scadenza, "id_fascicolo", ""),
        getattr(scadenza, "titolo", ""),
        getattr(scadenza, "descrizione", ""),
        getattr(scadenza, "note", ""),
        getattr(scadenza, "judicial_office_name", ""),
        getattr(scadenza, "remote_hearing_source", ""),
        getattr(scadenza, "remote_hearing_access_info", ""),
        getattr(scadenza, "trace_json", ""),
    ]
    return "\n".join(_text(field) for field in fields if _text(field))


def _deadline_rg_candidates(scadenza: Any) -> set[str]:
    values: set[str] = set()
    for field in (
        getattr(scadenza, "id_fascicolo", ""),
        getattr(scadenza, "titolo", ""),
        getattr(scadenza, "descrizione", ""),
        getattr(scadenza, "note", ""),
        getattr(scadenza, "trace_json", ""),
    ):
        raw = _text(field)
        if not raw:
            continue
        direct = _canonical_rg_reference(raw)
        if direct:
            values.add(direct)
        for match in _RG_PREFIXED_RE.finditer(raw):
            values.add(f"{int(match.group(1))}/{match.group(2)}")
    return values


def _fascicolo_party_values(fascicolo: Any) -> set[str]:
    values = [
        getattr(fascicolo, "nome_cliente", ""),
        getattr(fascicolo, "controparte", ""),
        _fascicolo_client_label(fascicolo),
        _fascicolo_party_from_title(fascicolo),
    ]
    snapshot = getattr(fascicolo, "source_snapshot", None)
    if isinstance(snapshot, dict):
        for key in ("parti", "controparti", "assistiti", "clienti"):
            raw = snapshot.get(key)
            if isinstance(raw, list):
                values.extend(_text(item) for item in raw)
            else:
                values.append(_text(raw))
        for key in ("parte", "controparte", "nome_cliente", "cliente"):
            values.append(_text(snapshot.get(key)))
    cleaned: set[str] = set()
    for value in values:
        text = re.sub(r"\s*\([^)]*da collegare[^)]*\)\s*$", "", _text(value), flags=re.IGNORECASE).strip()
        identity = _identity_key(text)
        if len(identity) >= 5 and identity not in {"cliente da collegare", "fascicolo"}:
            cleaned.add(text)
    return cleaned


def _deadline_mentions_fascicolo_party(scadenza: Any, fascicolo: Any) -> bool:
    blob = _identity_key(_deadline_text_blob(scadenza))
    if not blob:
        return False
    return any(_identity_key(value) in blob for value in _fascicolo_party_values(fascicolo))


def _rg_candidates_from_text(value: Any) -> set[str]:
    raw = _text(value)
    values: set[str] = set()
    direct = _canonical_rg_reference(raw)
    if direct:
        values.add(direct)
    for match in _RG_PREFIXED_RE.finditer(raw):
        values.add(f"{int(match.group(1))}/{match.group(2)}")
    return values


def _document_text_matches_fascicolo(fascicolo: Any, text: str) -> bool:
    rg = _fascicolo_rg_key(fascicolo)
    if rg and rg in _rg_candidates_from_text(text):
        return True
    blob = _identity_key(text)
    if not blob:
        return False
    return any(_identity_key(value) in blob for value in _fascicolo_party_values(fascicolo))


def _fascicolo_alias_index(fascicoli: Iterable[Any]) -> tuple[dict[str, set[str]], dict[str, list[Any]], set[str]]:
    aliases: dict[str, set[str]] = {}
    by_rg: dict[str, list[Any]] = {}
    ids: set[str] = set()
    for fascicolo in fascicoli:
        fid = _text(getattr(fascicolo, "id", ""))
        if not fid:
            continue
        ids.add(fid)
        keys = set(_fascicolo_lookup_keys(fascicolo))
        rg = _fascicolo_rg_key(fascicolo)
        if rg:
            keys.update({rg, f"RG {rg}", f"R.G. {rg}"})
            by_rg.setdefault(rg, []).append(fascicolo)
        for key in keys:
            normalized = _identity_key(key)
            if normalized:
                aliases.setdefault(normalized, set()).add(fid)
    return aliases, by_rg, ids


def _resolve_scadenza_fascicolo_ids(
    scadenza: Any,
    *,
    alias_index: dict[str, set[str]],
    by_rg: dict[str, list[Any]],
    known_ids: set[str],
) -> set[str]:
    fid = _text(getattr(scadenza, "id_fascicolo", ""))
    if fid in known_ids:
        return {fid}
    direct_aliases = alias_index.get(_identity_key(fid), set()) if fid else set()
    if len(direct_aliases) == 1:
        return set(direct_aliases)

    matched: set[str] = set()
    for rg in _deadline_rg_candidates(scadenza):
        candidates = by_rg.get(rg, [])
        if len(candidates) == 1:
            matched.add(_text(getattr(candidates[0], "id", "")))
            continue
        party_matches = [
            _text(getattr(fascicolo, "id", ""))
            for fascicolo in candidates
            if _deadline_mentions_fascicolo_party(scadenza, fascicolo)
        ]
        if len(set(party_matches)) == 1:
            matched.add(party_matches[0])
    return {item for item in matched if item}


def _resolve_fascicolo(repo: Any, requested_id: str) -> Any:
    direct = repo.get(requested_id)
    if direct:
        return direct
    wanted = _text(requested_id).casefold()
    if not wanted:
        return None
    for fascicolo in repo.tutti():
        if wanted in {key.casefold() for key in _fascicolo_lookup_keys(fascicolo)}:
            return fascicolo
    return None


def _looks_like_technical_user_label(value: str) -> bool:
    text = _text(value)
    if not text:
        return False
    if "@" in text:
        return True
    has_separator = any(separator in text for separator in (".", "_", "-"))
    has_space = any(ch.isspace() for ch in text)
    return has_separator and not has_space and text == text.lower()


def _humanize_technical_user_label(value: str) -> str:
    text = _text(value)
    if not _looks_like_technical_user_label(text):
        return text
    return " ".join(part.capitalize() for part in re.split(r"[._-]+", text) if part)


def _lead_lawyer_label(stored_value: Any, studio_avvocato_titolare: str = "") -> str:
    stored = _text(stored_value)
    studio = _text(studio_avvocato_titolare)
    if studio and (not stored or _looks_like_technical_user_label(stored)):
        return studio
    return _humanize_technical_user_label(stored) or studio


def _short(value: Any, limit: int = 120) -> str:
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _technical_filename(value: Any) -> bool:
    name = _text(value)
    return bool(re.fullmatch(r"\d{10,}(?:\.[A-Za-z0-9]{2,8})?", name))


def _clean_document_filename(value: Any) -> str:
    name = _text(value)
    if not name:
        return ""
    name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = re.sub(r"\s+", " ", name)
    return name


def _is_import_pratiche_marker(value: Any) -> bool:
    text = _text(value).casefold()
    return any(
        marker in text
        for marker in (
            "quickorganizer",
            "import quickorganizer",
            "import pratiche",
            "gestionale precedente",
            "pacchetto pratiche",
        )
    )


def _quickorganizer_name_from_note(note: Any) -> str:
    text = _text(note)
    if not re.match(r"^(?:import\s+quickorganizer|import\s+pratiche)\.", text, flags=re.IGNORECASE):
        return ""
    tail = text.split(".", 1)[1].strip() if "." in text else ""
    candidate = tail.split(" - ", 1)[0].strip()
    candidate = _clean_document_filename(candidate)
    if not candidate or _technical_filename(candidate):
        return ""
    return candidate


def _document_type_label(value: Any) -> str:
    raw = _enum_value(value).upper().replace(" ", "_")
    labels = {
        "ATTO_GIUDIZIARIO": "Atto giudiziario",
        "ATTO": "Atto",
        "RICORSO": "Ricorso",
        "CITAZIONE": "Atto di citazione",
        "COMPARSA": "Comparsa",
        "MEMORIA": "Memoria",
        "ISTANZA": "Istanza",
        "PROCURA": "Procura alle liti",
        "ALLEGATO": "Allegato",
        "SENTENZA": "Provvedimento - sentenza",
        "ORDINANZA": "Provvedimento - ordinanza",
        "DECRETO": "Provvedimento - decreto",
        "VERBALE": "Verbale",
        "COMUNICAZIONE": "Comunicazione",
        "PEC": "Comunicazione PEC",
    }
    if raw in labels:
        return labels[raw]
    return raw.replace("_", " ").title() if raw else "Documento"


def _source_label_for_document(doc: Any) -> str:
    source = _enum_value(getattr(doc, "fonte_documento", ""))
    portal_class = _text(getattr(doc, "classificazione_portale", ""))
    if source == "IMPORT_ESTERNO" and _is_import_pratiche_marker(portal_class):
        return "Importazione fascicolo"
    if source == "TEMPLATE_ATTI_COMPILATORE":
        return "Redazione atti"
    if source == "IMPORT_ESTERNO":
        return "Documento importato"
    if source in {"PORTALE_TELEMATICO", "PST", "POLISWEB"}:
        return "Portale Servizi"
    return _text(source, "Studio")


def _portal_class_for_document(doc: Any) -> str:
    portal_class = _text(getattr(doc, "classificazione_portale", ""))
    if _is_import_pratiche_marker(portal_class):
        return _document_type_label(getattr(doc, "tipo", ""))
    return portal_class


def _visible_document_tags(doc: Any, *, display_name: str, technical_name: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw_tag in getattr(doc, "tags", []) or []:
        tag = _italian_dates_in_text(raw_tag)
        key = tag.casefold().strip()
        if not key:
            continue
        if key.startswith("iusentra:"):
            continue
        if any(token in key for token in ("quickorganizer", "import_esterno", "backend", "frontend", "payload", "runtime", "legacy")):
            continue
        if key in {"email", "mail"}:
            tag = "Email"
        elif key == "pec":
            tag = "PEC"
        elif key in {"pst", "polisweb", "portale"}:
            tag = "Portale Servizi"
        dedupe = tag.casefold()
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append(tag)
    if technical_name and technical_name != display_name:
        out.append(f"Nome file originale: {technical_name}")
    return out[:6]


def _notification_document_haystack(doc: Any) -> str:
    return " ".join(
        _text(value).lower()
        for value in (
            getattr(doc, "nome", ""),
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome_portale", ""),
            getattr(doc, "tipo", ""),
            getattr(doc, "tipo_atto_portale", ""),
            getattr(doc, "classificazione_portale", ""),
            getattr(doc, "note", ""),
            " ".join(str(item) for item in (getattr(doc, "tags", []) or [])),
        )
    )


def _notification_context_present(text: str) -> bool:
    return any(
        token in text
        for token in (
            "notifica",
            "notificaz",
            "originale notificato",
            "legge n. 53",
            "legge 53",
            "l. 53",
            "notifica_id",
            "notificazione ai sensi",
        )
    )


def _notification_proof_kind_for_document(doc: Any) -> str:
    text = _notification_document_haystack(doc)
    has_context = _notification_context_present(text)
    if "relata" in text and has_context:
        return "relata"
    if "originale notificato" in text and any(
        token in text for token in ("ricorso", "citazione", "comparsa", "memoria", "istanza", "atto", "decreto")
    ):
        return "atto_notificato"
    if has_context and any(token in text for token in ("accettazione", "rac")):
        return "rac"
    if has_context and any(token in text for token in ("consegna", "rdac", "avvenuta consegna")):
        return "rdac"
    if has_context and any(token in text for token in ("pec inviata", "postacert", ".eml", "messaggio pec")):
        return "pec"
    if has_context and "attestazione di conform" in text:
        return "attestazione"
    if bool(getattr(doc, "prova_notifica", False)):
        return "atto_notificato"
    return ""


def _notification_kind_label(kind: str) -> str:
    return {
        "documento_ufficio": "Documento d'ufficio",
        "atto_notificato": "Atto notificato",
        "relata": "Relata",
        "pec": "PEC inviata",
        "rac": "RAC",
        "rdac": "RdAC",
        "attestazione": "Attestazione di conformità",
        "prova": "Prova notifica",
    }.get(kind, "Documento")


def _notification_status_label(status: str) -> str:
    return {
        "firmato": "firmato",
        "acquisito": "acquisito",
        "inviato": "inviato",
        "ricevuta_presente": "ricevuta presente",
        "documento_notificato": "notificato",
    }.get(status, status.replace("_", " "))


def _notification_proof_key(doc: Any, kind: str) -> str:
    text = _notification_document_haystack(doc)
    match = re.search(r"notifica[_\s-]*id[:_\s-]*([a-z0-9_-]+)", text, flags=re.IGNORECASE)
    if match:
        return f"{kind}|notifica:{match.group(1).casefold()}"
    digest = _text(getattr(doc, "hash_sha256", "")).lower()
    if digest:
        return f"{kind}|sha:{digest}"
    name = _normalise_office_document_name(
        getattr(doc, "nome", "") or getattr(doc, "nome_originale", "") or getattr(doc, "nome_portale", "")
    )
    return f"{kind}|nome:{name}"


def _notification_communication_documents(fascicolo: Any) -> list[Any]:
    """Documenti di notifica che appartengono alle comunicazioni, non a una nuova relata."""

    documents = list(getattr(fascicolo, "documenti", []) or [])
    communication_kinds = {"atto_notificato", "pec", "rac", "rdac", "attestazione"}
    out: list[Any] = []
    seen: set[str] = set()
    for doc in documents:
        kind = _notification_proof_kind_for_document(doc)
        if kind not in communication_kinds:
            continue
        key = _notification_proof_key(doc, kind)
        if key in seen:
            continue
        seen.add(key)
        out.append(doc)
    return out


def _professional_document_name(doc: Any, counters: Counter[str]) -> str:
    portal_name = _clean_document_filename(getattr(doc, "nome_portale", ""))
    original_name = _clean_document_filename(getattr(doc, "nome_originale", ""))
    stored_name = _clean_document_filename(getattr(doc, "nome", ""))
    path_name = _clean_document_filename(getattr(doc, "percorso", ""))
    note_name = _quickorganizer_name_from_note(getattr(doc, "note", ""))
    tags = {str(tag).casefold().strip() for tag in (getattr(doc, "tags", []) or [])}
    renamed_by_user = "iusentra:nome-personalizzato" in tags
    migrated_user_rename = bool(
        stored_name
        and path_name
        and stored_name.casefold() == path_name.casefold()
        and not _technical_filename(stored_name)
        and any(
            candidate and candidate.casefold() != stored_name.casefold() and _technical_filename(candidate)
            for candidate in (portal_name, original_name)
        )
    )
    if (renamed_by_user or migrated_user_rename) and stored_name:
        return stored_name
    signed_names = [
        candidate
        for candidate in (portal_name, note_name, original_name, stored_name, path_name)
        if candidate and candidate.lower().endswith(".p7m")
    ]
    if signed_names:
        for candidate in signed_names:
            if not _technical_filename(candidate):
                return candidate
        return signed_names[0]
    for candidate in (portal_name, note_name, original_name, stored_name):
        if candidate and not _technical_filename(candidate):
            return candidate
    label = _document_type_label(getattr(doc, "tipo", ""))
    counters[label] += 1
    suffix = f" {counters[label]}" if counters[label] > 1 else ""
    return f"{label}{suffix}"


def _document_name_with_signature_suffix(doc: Any, display_name: str, *candidate_names: Any) -> str:
    name = _clean_document_filename(display_name)
    if not name or name.lower().endswith((".p7m", ".sig", ".pkcs7")):
        return name
    if not document_has_signed_container(doc, name, *candidate_names):
        return name
    return f"{name}.p7m"


def _fascicolo_party_from_title(fascicolo: Any) -> str:
    snapshot = getattr(fascicolo, "source_snapshot", None)
    practice = ""
    if isinstance(snapshot, dict):
        practice = _text(snapshot.get("pratica") or snapshot.get("title") or snapshot.get("titolo"))
    title = practice or _text(getattr(fascicolo, "titolo", ""))
    match = re.split(r"\s+c(?:\.|ontro)?\s+", title, maxsplit=1, flags=re.IGNORECASE)
    candidate = match[0].strip(" -:") if match else title.strip(" -:")
    return candidate if candidate and candidate.casefold() != title.casefold() else candidate


def _fascicolo_client_label(fascicolo: Any) -> str:
    linked = _text(getattr(fascicolo, "nome_cliente", ""))
    if linked:
        return linked
    inferred = _fascicolo_party_from_title(fascicolo)
    if inferred:
        return f"{inferred} (da collegare in anagrafica)"
    return "Cliente da collegare"


def _codice_oggetto_label(fascicolo: Any) -> str:
    code = _text(getattr(fascicolo, "codice_oggetto_pst", ""))
    if code:
        return code
    object_text = _text(getattr(fascicolo, "oggetto", ""))
    if re.match(r"^\d{3,}\s*-", object_text):
        return object_text
    snapshot = getattr(fascicolo, "source_snapshot", None)
    if isinstance(snapshot, dict):
        snap_object = _text(snapshot.get("oggetto"))
        if re.match(r"^\d{3,}\s*-", snap_object):
            return snap_object
    return ""


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _text(value)
        if not raw:
            return None
        parsed = None
        for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
            try:
                parsed = datetime.fromisoformat(sample)
                break
            except ValueError:
                continue
        if parsed is None:
            for sample, fmt in (
                (raw[:19], "%d/%m/%Y %H:%M:%S"),
                (raw[:16], "%d/%m/%Y %H:%M"),
                (raw[:10], "%d/%m/%Y"),
            ):
                try:
                    parsed = datetime.strptime(sample, fmt)
                    break
                except ValueError:
                    continue
        if parsed is None:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(ROME_TZ).replace(tzinfo=None)
    return parsed


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.date()
    raw = _text(value)
    for sample, fmt in (
        (raw[:10], "%Y-%m-%d"),
        (raw[:10], "%d/%m/%Y"),
        (raw[:10], "%d-%m-%Y"),
        (raw[:10], "%d.%m.%Y"),
    ):
        try:
            return datetime.strptime(sample, fmt).date()
        except ValueError:
            continue
    return None


def _date_label(value: Any) -> str:
    parsed = _parse_date(value)
    if not parsed:
        return _text(value, "n.d.")
    return parsed.strftime("%d/%m/%Y")


def _date_label_optional(value: Any) -> str:
    if not _text(value):
        return ""
    return _date_label(value)


_ISO_DATE_IN_TEXT_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:[T\s]\d{2}:\d{2}(?::\d{2})?)?\b")


def _italian_dates_in_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""

    def _replace(match: re.Match[str]) -> str:
        year, month, day = match.group(1), match.group(2), match.group(3)
        try:
            return date(int(year), int(month), int(day)).strftime("%d/%m/%Y")
        except ValueError:
            return match.group(0)

    return _ISO_DATE_IN_TEXT_RE.sub(_replace, text)


def _closure_date_value(fascicolo: Any) -> str:
    direct = _text(getattr(fascicolo, "data_chiusura", ""))
    if direct:
        return direct
    archivio = getattr(fascicolo, "archivio", None)
    archived_at = _text(getattr(archivio, "data_archiviazione", "") if archivio else "")
    if archived_at:
        return archived_at
    closed_states = {StatoFascicolo.DEFINITO.value, StatoFascicolo.ARCHIVIATO.value}
    if _enum_value(getattr(fascicolo, "stato", "")) in closed_states:
        for step in reversed(getattr(fascicolo, "avanzamento", []) or []):
            if _enum_value(getattr(step, "stato_nuovo", "")) in closed_states:
                return _text(getattr(step, "data", ""))
    return ""


def _activity_is_hearing(activity: Any) -> bool:
    raw_type = _enum_value(getattr(activity, "tipo", "")).upper()
    title = _text(getattr(activity, "titolo", "")).upper()
    return "UDIENZA" in raw_type or "UDIENZA" in title


def _next_hearing_value(fascicolo: Any, apps: Iterable[Any] | None = None) -> str:
    direct = _text(getattr(fascicolo, "data_prossima_udienza", ""))
    if direct:
        return direct
    today = date.today()
    future_dates: list[date] = []
    past_dates: list[date] = []
    for activity in getattr(fascicolo, "attivita", []) or []:
        if not _activity_is_hearing(activity):
            continue
        parsed = _parse_date(getattr(activity, "data", ""))
        if not parsed:
            continue
        (future_dates if parsed >= today else past_dates).append(parsed)
    for app in apps or []:
        label = f"{_text(getattr(app, 'titolo', ''))} {_text(getattr(app, 'tipo', ''))}".upper()
        if "UDIENZA" not in label:
            continue
        parsed = _parse_date(getattr(app, "data_ora", "") or getattr(app, "data", ""))
        if not parsed:
            continue
        (future_dates if parsed >= today else past_dates).append(parsed)
    if future_dates:
        return min(future_dates).isoformat()
    if past_dates:
        return max(past_dates).isoformat()
    return ""


def _agenda_for_fascicolo(get_agenda: Callable[[], Any], fascicolo: Any) -> list[Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    source_external_id = _text(getattr(fascicolo, "source_external_id", ""))
    rg_key = _fascicolo_rg_key(fascicolo)
    terms = {
        value
        for value in (
            source_external_id,
            rg_key,
            f"RG {rg_key}" if rg_key else "",
            _text(getattr(fascicolo, "numero_rg", "")),
        )
        if value
    }
    snapshot = getattr(fascicolo, "source_snapshot", None)
    if isinstance(snapshot, dict):
        terms.add(_text(snapshot.get("external_id")))
        numero = _text(snapshot.get("numero"))
        anno = _text(snapshot.get("anno"))
        if numero and anno:
            terms.add(f"{numero}/{anno}")
            terms.add(f"RG {numero}/{anno}")
    normalized_terms = {_identity_key(term) for term in terms if _identity_key(term)}
    profile_id = f"fascicolo:{fid}" if fid else ""
    out: list[Any] = []
    seen: set[str] = set()
    for app in get_agenda().tutti():
        app_id = _text(getattr(app, "id", ""))
        direct_match = bool(
            profile_id and _text(getattr(app, "external_profile_id", "")) == profile_id
            or source_external_id and _text(getattr(app, "external_source_url", "")) == source_external_id
        )
        haystack = _identity_key(
            " ".join(
                _text(value)
                for value in (
                    getattr(app, "titolo", ""),
                    getattr(app, "note", ""),
                    getattr(app, "procedimento", ""),
                    getattr(app, "cliente", ""),
                    getattr(app, "tribunale", ""),
                    getattr(app, "external_source_url", ""),
                    getattr(app, "external_profile_id", ""),
                    getattr(app, "external_uid", ""),
                )
                if _text(value)
            )
        )
        if direct_match or any(term in haystack for term in normalized_terms):
            if app_id and app_id in seen:
                continue
            seen.add(app_id)
            out.append(app)
    return sorted(out, key=lambda item: _text(getattr(item, "data_ora", "")))


def _time_label(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%H:%M")


def _datetime_label(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return _text(value)
    return parsed.strftime("%d/%m/%Y %H:%M")


def _euro(value: Any) -> str:
    return format_euro_it(value)


PAYMENT_KINDS = (
    "contributo_unificato",
    "spese_esborsi",
    "fondo_spese",
    "liquidazione_giudice",
    "parcella",
)

PAYMENT_KIND_LABELS = {
    "contributo_unificato": "Contributo unificato",
    "spese_esborsi": "Spese/esborsi",
    "fondo_spese": "Spese/esborsi",
    "liquidazione_giudice": "Liquidazione giudice",
    "parcella": "Parcella",
}

PAYMENT_KIND_ALIASES = {
    "cu": "contributo_unificato",
    "contributo": "contributo_unificato",
    "contributo_unificato": "contributo_unificato",
    "contributo unificato": "contributo_unificato",
    "spese": "spese_esborsi",
    "esborsi": "spese_esborsi",
    "spese_esborsi": "spese_esborsi",
    "spese esborsi": "spese_esborsi",
    "fondo": "spese_esborsi",
    "fondo_spese": "spese_esborsi",
    "fondo spese": "spese_esborsi",
    "anticipazione": "spese_esborsi",
    "anticipazioni": "spese_esborsi",
    "liquidazione": "liquidazione_giudice",
    "liquidazione_giudice": "liquidazione_giudice",
    "liquidazione giudice": "liquidazione_giudice",
    "parcella": "parcella",
    "parcelle": "parcella",
}

PAYMENT_STATUS_LABELS = {
    "non_previsto": "Non previsto",
    "da_registrare": "Da registrare",
    "pagato": "Pagato",
    "parziale": "Parziale",
    "da_emettere": "Da emettere",
}

PAYMENT_STATUS_TONES = {
    "non_previsto": "neutral",
    "da_registrare": "warning",
    "pagato": "success",
    "parziale": "orange",
    "da_emettere": "warning",
}

PAYMENT_DEFAULT_STATUS = {
    "contributo_unificato": "da_registrare",
    "spese_esborsi": "non_previsto",
    "fondo_spese": "non_previsto",
    "liquidazione_giudice": "non_previsto",
    "parcella": "da_emettere",
}


def _normalise_payment_kind(value: Any) -> str:
    raw = _text(value).lower().replace("-", "_").replace(".", "_")
    raw = re.sub(r"\s+", " ", raw.replace("_", " ")).strip()
    compact = raw.replace(" ", "_")
    return PAYMENT_KIND_ALIASES.get(compact) or PAYMENT_KIND_ALIASES.get(raw) or ""


def _normalise_payment_status(value: Any, *, default: str = "") -> str:
    raw = _text(value).lower().replace("-", "_").replace(".", "_")
    raw = re.sub(r"\s+", "_", raw).strip("_")
    if raw in {"si", "sì", "yes", "true", "1", "paid", "pagata", "pagato", "saldata", "saldato"}:
        return "pagato"
    if raw in {"no", "false", "0", "non_pagato", "non_pagate", "non_pagata", "da_registrare", "mancante"}:
        return "da_registrare"
    if raw in {"non_previsto", "non_prevista", "non_previste", "escluso", "esclusa"}:
        return "non_previsto"
    if raw in {"parziale", "pagamento_parziale", "acconto"}:
        return "parziale"
    if raw in {"da_emettere", "emettere", "non_emessa", "non_emesso"}:
        return "da_emettere"
    return default


def _payment_amount_value(value: Any) -> float | None:
    if value is None:
        return None
    raw = _text(value)
    if raw == "":
        return None
    cleaned = raw.replace("EUR", "").replace("eur", "").replace("€", "").replace(" ", "").strip()
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        number = float(cleaned)
    except (TypeError, ValueError):
        return None
    return round(number, 2)


def _amount_label(value: float | None) -> str:
    return _euro(value) if value is not None else ""


def _request_cache(name: str) -> dict[str, Any] | None:
    if not has_app_context():
        return None
    try:
        from flask import g

        cache = getattr(g, name, None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(g, name, cache)
        return cache
    except Exception:
        return None


def _current_fascicoli_catalog_paths() -> tuple[Any, Any, Any]:
    fascicoli_db_path: Any = None
    storage_root: Any = None
    structured_db: Any = None
    try:
        from web.services.tenant_paths import tenant_data_path

        fascicoli_db_path = tenant_data_path("FASCICOLI_DB", require_tenant=True)
        storage_root = tenant_data_path("DOCUMENTI_AI_DIR", require_tenant=True)
    except Exception:
        if has_app_context():
            fascicoli_db_path = current_app.config.get("FASCICOLI_DB")
            storage_root = current_app.config.get("DOCUMENTI_AI_DIR")
    try:
        from web.services.storage_runtime import get_request_studio_db

        if fascicoli_db_path:
            structured_db = get_request_studio_db(fascicoli_db_path)
    except Exception:
        structured_db = None
    return fascicoli_db_path, storage_root, structured_db


def _document_id(doc: Any) -> str:
    return _text(getattr(doc, "id", "") or getattr(doc, "document_id", "") or getattr(doc, "documento_id", ""))


def _readable_document_source(value: Any, *, default: str = "Documento indicizzato del fascicolo") -> str:
    source = _text(value)
    if not source:
        return default
    marker = source.casefold()
    source_name = Path(source.replace("\\", "/")).name
    source_stem = Path(source_name).stem.casefold()
    if marker.startswith("sentenza_key:") or ("sentenza" in marker and "|" in marker):
        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", source)
        if date_match:
            return f"Sentenza del {_date_label(date_match.group(1))}"
        return "Sentenza indicizzata nel fascicolo"
    if re.fullmatch(r"\d{10,}", marker) or re.fullmatch(r"\d{10,}", source_stem):
        return default
    if marker.startswith(("document_id:", "documento_id:", "docai-", "docai_", "doc-", "doc_")):
        return default
    return source


def _document_candidates_for_hints(
    fascicolo: Any,
    matcher: Callable[[str, dict[str, Any]], bool],
    *,
    metadata_matcher: Callable[[dict[str, Any]], bool] | None = None,
    fallback_all: bool = False,
) -> list[Any]:
    documents = list(getattr(fascicolo, "documenti", []) or [])
    if not documents:
        return []
    selected = [
        doc
        for doc in documents
        if (
            metadata_matcher(_document_metadata_for_id(fascicolo, _document_id(doc)))
            if metadata_matcher is not None
            else matcher("", _document_metadata_for_id(fascicolo, _document_id(doc)))
        )
    ]
    if selected:
        return selected
    if fallback_all:
        return documents
    return []


def _document_ai_texts_for_fascicolo(fascicolo: Any, documents: Iterable[Any] | None = None) -> dict[str, str]:
    fid = _text(getattr(fascicolo, "id", ""))
    if not fid:
        return {}
    cache = _request_cache("_react_fascicoli_document_ai_texts")
    all_documents = documents is None
    documents_list = list(getattr(fascicolo, "documenti", []) or []) if all_documents else list(documents or [])
    doc_ids = sorted(_document_id(doc) for doc in documents_list if _document_id(doc))
    cache_key = f"{fid}::__all__" if all_documents else f"{fid}::{'|'.join(doc_ids)}"
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    if not all_documents and cache is not None:
        all_key = f"{fid}::__all__"
        all_cached = cache.get(all_key)
        if isinstance(all_cached, dict):
            wanted = set(doc_ids)
            return {key: value for key, value in all_cached.items() if key in wanted}
    if not documents_list:
        result: dict[str, str] = {}
    else:
        fascicoli_db_path, storage_root, structured_db = _current_fascicoli_catalog_paths()
        tenant_ids = _current_tenant_catalog_ids()
        result = _safe(
            "document_ai_texts_for_fascicolo",
            lambda: document_ai_texts_for_catalog(
                tenant_ids=tenant_ids,
                fascicolo_id=fid,
                documents=documents_list,
                fascicoli_db_path=fascicoli_db_path,
                structured_db=structured_db,
                storage_root=storage_root,
                allow_extracted_files_fallback=True,
            ),
            {},
    )
    cleaned = {str(key): str(value) for key, value in (result or {}).items() if str(value or "").strip()}
    if cache is not None:
        cache[cache_key] = cleaned
    return cleaned


def _cache_document_ai_texts_for_fascicolo(
    fascicolo: Any,
    documents: Iterable[Any],
    texts: dict[str, str],
) -> None:
    cache = _request_cache("_react_fascicoli_document_ai_texts")
    if cache is None:
        return
    fid = _text(getattr(fascicolo, "id", ""))
    documents_list = list(documents or [])
    doc_ids = sorted(_document_id(doc) for doc in documents_list if _document_id(doc))
    cleaned = {str(key): str(value) for key, value in (texts or {}).items() if str(value or "").strip()}
    cache[f"{fid}::{'|'.join(doc_ids)}"] = cleaned
    all_key = f"{fid}::__all__"
    all_cached = cache.get(all_key)
    if isinstance(all_cached, dict):
        merged = dict(all_cached)
        merged.update(cleaned)
        cache[all_key] = merged


def _ensure_economic_document_ai_texts_for_fascicolo(
    fascicolo: Any,
    documents: Iterable[Any],
) -> dict[str, str]:
    """Indicizza in modo mirato i documenti economici non ancora letti da Document AI."""

    fid = _text(getattr(fascicolo, "id", ""))
    documents_list = [doc for doc in list(documents or []) if _document_id(doc)]
    if not fid or not documents_list or not has_app_context():
        return {}
    max_docs = int(os.getenv("IUSENTRA_ECONOMIC_PRESIDIO_MAX_OCR_DOCUMENTS", "6") or 6)
    if max_docs <= 0:
        max_docs = 6
    documents_list = documents_list[:max_docs]
    wanted_ids = {_document_id(doc) for doc in documents_list if _document_id(doc)}
    if not wanted_ids:
        return {}
    try:
        from web.services.document_intelligence_runtime import (
            build_document_ai_service,
            collect_document_ai_sources_for_fascicolo,
            document_ai_tenant_id,
            document_ai_user_context,
        )

        tenant_id = document_ai_tenant_id()
        sources = [
            source
            for source in collect_document_ai_sources_for_fascicolo(fid, tenant_id=tenant_id)
            if _text(getattr(source, "source_id", "")) in wanted_ids
        ]
        if not sources:
            return {}
        service = build_document_ai_service()
        service.process_lex_indexing_sources(
            tenant_id,
            fid,
            sources,
            document_ai_user_context(),
            retry_errors=True,
        )
        fascicoli_db_path, storage_root, structured_db = _current_fascicoli_catalog_paths()
        refreshed = document_ai_texts_for_catalog(
            tenant_ids=_current_tenant_catalog_ids(),
            fascicolo_id=fid,
            documents=documents_list,
            fascicoli_db_path=fascicoli_db_path,
            structured_db=structured_db,
            storage_root=storage_root,
            allow_extracted_files_fallback=True,
        )
    except Exception:
        return {}
    cleaned = {
        str(key): str(value)
        for key, value in (refreshed or {}).items()
        if str(value or "").strip()
    }
    if cleaned:
        _cache_document_ai_texts_for_fascicolo(fascicolo, documents_list, cleaned)
    return cleaned


def _ensure_deadline_document_ai_texts_for_fascicolo(
    fascicolo: Any,
    documents: Iterable[Any],
) -> dict[str, str]:
    """Legge subito solo i documenti con possibili date processuali ancora mancanti."""

    fid = _text(getattr(fascicolo, "id", ""))
    documents_list = [doc for doc in list(documents or []) if _document_id(doc)]
    if not fid or not documents_list:
        return {}
    existing = _document_ai_texts_for_fascicolo(fascicolo, documents=documents_list)
    missing_documents = [
        doc
        for doc in documents_list
        if _document_id(doc) not in existing
    ]
    if not missing_documents or not has_app_context():
        return existing
    selected_documents = _rank_procedural_deadline_documents(fascicolo, missing_documents)
    wanted_ids = {_document_id(doc) for doc in selected_documents if _document_id(doc)}
    wanted_hashes = {
        _text(getattr(doc, "hash_sha256", "") or getattr(doc, "hash_contenuto_sha256", ""))
        for doc in selected_documents
        if _text(getattr(doc, "hash_sha256", "") or getattr(doc, "hash_contenuto_sha256", ""))
    }
    wanted_names = {
        _text(value).casefold()
        for doc in selected_documents
        for value in (
            getattr(doc, "nome", ""),
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome_portale", ""),
            Path(_text(getattr(doc, "percorso", ""))).name,
        )
        if _text(value)
    }
    if not wanted_ids:
        return existing
    try:
        from web.services.document_intelligence_runtime import (
            build_document_ai_service,
            collect_document_ai_sources_for_fascicolo,
            document_ai_tenant_id,
            document_ai_user_context,
        )

        tenant_id = document_ai_tenant_id()
        sources = [
            source
            for source in collect_document_ai_sources_for_fascicolo(fid, tenant_id=tenant_id)
            if (
                _text(getattr(source, "source_id", "")) in wanted_ids
                or _text(getattr(source, "sha256", "")) in wanted_hashes
                or _text(getattr(source, "filename", "")).casefold() in wanted_names
                or _text(getattr(source, "safe_filename", "")).casefold() in wanted_names
            )
        ]
        if not sources:
            return existing
        service = build_document_ai_service()
        service.process_lex_indexing_sources(
            tenant_id,
            fid,
            sources,
            document_ai_user_context(),
            retry_errors=True,
        )
        fascicoli_db_path, storage_root, structured_db = _current_fascicoli_catalog_paths()
        refreshed = document_ai_texts_for_catalog(
            tenant_ids=_current_tenant_catalog_ids(),
            fascicolo_id=fid,
            documents=documents_list,
            fascicoli_db_path=fascicoli_db_path,
            structured_db=structured_db,
            storage_root=storage_root,
            allow_extracted_files_fallback=True,
        )
    except Exception:
        return existing
    cleaned = {
        str(key): str(value)
        for key, value in (refreshed or {}).items()
        if str(value or "").strip()
    }
    if cleaned:
        _cache_document_ai_texts_for_fascicolo(fascicolo, documents_list, cleaned)
        return cleaned
    return existing


def _document_metadata_for_id(fascicolo: Any, document_id: str) -> dict[str, str]:
    wanted = _text(document_id)
    for doc in getattr(fascicolo, "documenti", []) or []:
        did = _text(getattr(doc, "id", ""))
        if did != wanted:
            continue
        filename = _text(
            getattr(doc, "nome_portale", "")
            or getattr(doc, "nome", "")
            or getattr(doc, "nome_originale", "")
            or getattr(doc, "filename", "")
        )
        return {
            "document_id": did,
            "documento_id": did,
            "filename": filename,
            "original_filename": _text(getattr(doc, "nome_originale", "")) or filename,
            "safe_filename": _text(getattr(doc, "nome", "")) or filename,
            "tipo_documento": _enum_value(getattr(doc, "tipo", "")),
            "classification": _text(getattr(doc, "classificazione_portale", "")),
            "sha256": _text(getattr(doc, "hash_sha256", "")),
            "fascicolo_id": _text(getattr(fascicolo, "id", "")),
            "data_documento": _text(getattr(doc, "data_documento", "")),
            "data_caricamento": _text(getattr(doc, "data_caricamento", "")),
            "data_deposito_portale": _text(getattr(doc, "data_deposito_portale", "")),
            "storage_path": _text(getattr(doc, "percorso", "")),
        }
    return {"document_id": wanted, "documento_id": wanted, "fascicolo_id": _text(getattr(fascicolo, "id", ""))}


def _fascicoli_documents_root() -> Path | None:
    try:
        from web.services.tenant_paths import tenant_data_path

        raw = tenant_data_path("FASCICOLI_DOCS", require_tenant=True)
    except Exception:
        raw = ""
        if has_app_context():
            raw = _text(current_app.config.get("FASCICOLI_DOCS"))
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except Exception:
        return None


def _resolve_fascicolo_document_path(fascicolo: Any, doc: Any) -> Path | None:
    root = _fascicoli_documents_root()
    raw = _text(getattr(doc, "percorso", ""))
    if not root or not raw:
        return None
    path = Path(raw)
    candidate = path if path.is_absolute() else root / path
    try:
        resolved = candidate.resolve()
    except Exception:
        return None
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    fid = _text(getattr(fascicolo, "id", ""))
    if fid and fid not in {part for part in resolved.parts}:
        return None
    return resolved


def _extract_native_pdf_text_for_presidio(path: Path) -> str:
    max_pages = int(os.getenv("IUSENTRA_ECONOMIC_PRESIDIO_MAX_PDF_PAGES", "12") or 12)
    if max_pages <= 0:
        max_pages = 12
    try:
        import pdfplumber  # type: ignore

        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:max_pages]:
                pages.append(page.extract_text() or "")
        text = "\n\n".join(part for part in pages if part.strip()).strip()
        if text:
            return text
    except Exception:
        pass
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        pages = []
        for page in list(reader.pages)[:max_pages]:
            pages.append(page.extract_text() or "")
        return "\n\n".join(part for part in pages if part.strip()).strip()
    except Exception:
        return ""


def _extract_presidio_text_from_physical_document(fascicolo: Any, doc: Any) -> str:
    path = _resolve_fascicolo_document_path(fascicolo, doc)
    if not path or not path.exists() or not path.is_file():
        return ""
    max_bytes = int(os.getenv("IUSENTRA_ECONOMIC_PRESIDIO_MAX_DOCUMENT_BYTES", "8000000") or 8000000)
    try:
        if path.stat().st_size > max_bytes:
            return ""
    except OSError:
        return ""
    suffix = path.suffix.lower().lstrip(".") or Path(_text(getattr(doc, "nome", ""))).suffix.lower().lstrip(".")
    if suffix == "pdf":
        text = _extract_native_pdf_text_for_presidio(path)
    elif suffix in {"txt", "xml", "json", "csv"}:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
    else:
        text = ""
    if len(text) < 40:
        return ""
    return text[:240000]


def _related_duplicate_fascicoli(fascicoli: Iterable[Any], fascicolo: Any) -> list[Any]:
    key = normalise_practice_duplicate_key(fascicolo)
    fid = _text(getattr(fascicolo, "id", ""))
    if not key:
        return []
    return [
        row
        for row in (fascicoli or [])
        if _text(getattr(row, "id", "")) != fid and normalise_practice_duplicate_key(row) == key
    ]


def _analysis_fascicoli_scope(fascicolo: Any, related_fascicoli: Iterable[Any] | None = None) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for row in [fascicolo, *(list(related_fascicoli or []))]:
        fid = _text(getattr(row, "id", ""))
        if not fid or fid in seen:
            continue
        seen.add(fid)
        out.append(row)
    return out


def _document_analysis_fingerprint(fascicolo: Any, related_fascicoli: Iterable[Any] | None = None) -> str:
    rows: list[dict[str, Any]] = []
    for source in _analysis_fascicoli_scope(fascicolo, related_fascicoli):
        source_id = _text(getattr(source, "id", ""))
        for doc in list(getattr(source, "documenti", []) or []):
            rows.append(
                {
                    "fascicolo": source_id,
                    "id": _document_id(doc),
                    "nome": _text(getattr(doc, "nome", "")),
                    "nome_originale": _text(getattr(doc, "nome_originale", "")),
                    "tipo": _enum_value(getattr(doc, "tipo", "")),
                    "sha256": _text(getattr(doc, "hash_sha256", "")),
                    "size": int(getattr(doc, "dimensione_bytes", 0) or 0),
                    "loaded": _text(getattr(doc, "data_caricamento", "")),
                    "portal": _text(getattr(doc, "id_documento_portale", "")),
                }
            )
    payload = json.dumps(
        {
            "analysis_version": ECONOMIC_DOCUMENT_ANALYSIS_VERSION,
            "documents": sorted(rows, key=lambda item: (item["fascicolo"], item["id"], item["nome"])),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _document_analysis_unresolved_reason(marker: dict[str, Any], unresolved_kinds: list[str]) -> str:
    if "contributo_unificato" in unresolved_kinds:
        return (
            "Presidio documentale eseguito: nei documenti correnti non risulta una ricevuta, "
            "un'autocertificazione di esenzione o un invito al pagamento del contributo unificato leggibile."
        )
    return _text(
        marker.get("reason"),
        "Presidio documentale eseguito: alcuni dati non risultano dai documenti correnti.",
    )


def _document_analysis_state(
    fascicolo: Any,
    related_fascicoli: Iterable[Any] | None = None,
    *,
    automatic: bool = False,
) -> dict[str, Any]:
    payments = getattr(fascicolo, "pagamenti", {}) if fascicolo is not None else {}
    marker = dict((payments or {}).get("_presidio_documentale") or {}) if isinstance(payments, dict) else {}
    fingerprint = _document_analysis_fingerprint(fascicolo, related_fascicoli)
    cached_fingerprint = _text(marker.get("fingerprint") or marker.get("documentFingerprint"))
    marker_status = _text(marker.get("status") or marker.get("stato")).casefold()
    related_count = len(_analysis_fascicoli_scope(fascicolo, related_fascicoli)) - 1
    unresolved_kinds = sorted(_presidio_documentale_unresolved_kinds(marker))
    if marker_status == "stale":
        status = "da_rianalizzare"
        label = "Da rianalizzare"
        reason = _text(marker.get("reason"), "Sono entrati nuovi documenti o è cambiato il fascicolo.")
    elif cached_fingerprint and cached_fingerprint == fingerprint and unresolved_kinds:
        status = "aggiornato_con_rilievi"
        label = "Documenti controllati"
        reason = _document_analysis_unresolved_reason(marker, unresolved_kinds)
    elif cached_fingerprint and cached_fingerprint == fingerprint:
        status = "aggiornato"
        label = "Aggiornato"
        reason = _text(marker.get("reason"), "Analisi allineata ai documenti presenti.")
    elif automatic:
        status = "aggiornato_provvisorio"
        label = "Aggiornato in lettura"
        reason = "Evidenze lette dai documenti per questa vista; consolidare dopo la riconciliazione dei dati."
    else:
        status = "da_analizzare"
        label = "Da analizzare"
        reason = "Nessuna impronta di analisi consolidata sui documenti correnti."
    return {
        "status": status,
        "statusLabel": label,
        "tone": "warning" if status in {"da_rianalizzare", "da_analizzare", "aggiornato_con_rilievi"} else "success",
        "reason": reason,
        "fingerprint": fingerprint,
        "lastAnalyzedAt": _text(marker.get("updated_at") or marker.get("updatedAt") or marker.get("lastAnalyzedAt")),
        "relatedDuplicateFascicoli": related_count,
        "unresolvedKinds": unresolved_kinds,
    }


def _document_analysis_marker_state(
    fascicolo: Any,
    related_fascicoli: Iterable[Any] | None = None,
) -> dict[str, Any]:
    payments = getattr(fascicolo, "pagamenti", {}) if fascicolo is not None else {}
    marker = dict((payments or {}).get("_presidio_documentale") or {}) if isinstance(payments, dict) else {}
    fingerprint = _document_analysis_fingerprint(fascicolo, related_fascicoli)
    related_count = len(list(related_fascicoli or []))
    return presidio_marker_state(marker, fingerprint, related_count=related_count)


def _presidio_documentale_marker_is_current(
    fascicolo: Any,
    payments: Any | None = None,
    related_fascicoli: Iterable[Any] | None = None,
) -> bool:
    if payments is None:
        payments = getattr(fascicolo, "pagamenti", {}) if fascicolo is not None else {}
    if not isinstance(payments, dict):
        return False
    marker = payments.get("_presidio_documentale")
    return presidio_marker_is_current(marker if isinstance(marker, dict) else {}, _document_analysis_fingerprint(fascicolo, related_fascicoli))


def _presidio_documentale_marker(payments: Any) -> dict[str, Any]:
    if not isinstance(payments, dict):
        return {}
    marker = payments.get("_presidio_documentale")
    return dict(marker) if isinstance(marker, dict) else {}


def _presidio_documentale_unresolved_kinds(marker: Any) -> set[str]:
    if not isinstance(marker, dict):
        return set()
    raw = marker.get("unresolvedKinds") or marker.get("unresolved_kinds") or marker.get("da_verificare") or []
    values: list[Any]
    if isinstance(raw, str):
        values = [item.strip() for item in re.split(r"[,;\s]+", raw) if item.strip()]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = []
    return {
        kind
        for kind in (_normalise_payment_kind(value) for value in values)
        if kind in PAYMENT_KINDS
    }


def _presidio_documentale_has_unresolved_kind(marker: Any, kind: str) -> bool:
    normalized_kind = _normalise_payment_kind(kind)
    return bool(normalized_kind and normalized_kind in _presidio_documentale_unresolved_kinds(marker))


def _presidio_documentale_metadata_rows(fascicolo: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in list(getattr(fascicolo, "documenti", []) or []):
        document_id = _document_id(doc)
        if document_id:
            rows.append(_document_metadata_for_id(fascicolo, document_id))
    return rows


def _build_presidio_documentale_marker(
    fascicolo: Any,
    *,
    actor: str,
    automatic_sources: dict[str, dict[str, Any]] | None = None,
    status: str = "aggiornato",
    reason: str = "Analisi documentale completata e salvata nel fascicolo.",
) -> dict[str, Any]:
    marker = build_presidio_documentale_marker(
        fingerprint=_document_analysis_fingerprint(fascicolo),
        actor=actor,
        document_count=len(list(getattr(fascicolo, "documenti", []) or [])),
        metadata_rows=_presidio_documentale_metadata_rows(fascicolo),
        automatic_sources=automatic_sources,
        readable_source=_readable_document_source,
        normalise_kind=_normalise_payment_kind,
        normalise_status=lambda value: _normalise_payment_status(value, default=""),
        status=status,
        reason=reason,
    )
    marker["analysisVersion"] = ECONOMIC_DOCUMENT_ANALYSIS_VERSION
    return marker


_ECONOMIC_AUTO_SOURCES_CACHE: OrderedDict[str, tuple[float, dict[str, dict[str, Any]]]] = OrderedDict()


def _economic_auto_cache_limits() -> tuple[int, float, float]:
    def _read_int(name: str, default: int) -> int:
        try:
            return int(str(os.getenv(name, default)).strip() or default)
        except Exception:
            return default

    max_entries = max(0, _read_int("IUSENTRA_ECONOMIC_AUTO_CACHE_MAX", 1024))
    ttl_seconds = max(0, _read_int("IUSENTRA_ECONOMIC_AUTO_CACHE_TTL_SECONDS", 1800))
    empty_ttl_seconds = max(0, _read_int("IUSENTRA_ECONOMIC_AUTO_CACHE_EMPTY_TTL_SECONDS", 180))
    return max_entries, float(ttl_seconds), float(empty_ttl_seconds)


def _economic_auto_cache_scope() -> str:
    tenant_id = _current_tenant_id()
    if tenant_id:
        return tenant_id
    if has_app_context():
        for key in ("FASCICOLI_DB", "CLIENTI_DB", "DATA_ROOT"):
            value = current_app.config.get(key)
            if value:
                return _text(value)
    return "default"


def _clone_automatic_sources(value: dict[str, dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        _text(kind): dict(source)
        for kind, source in value.items()
        if _text(kind) and isinstance(source, dict)
    }


def _economic_auto_cache_get(cache_key: str) -> dict[str, dict[str, Any]] | None:
    if not cache_key:
        return None
    max_entries, ttl_seconds, empty_ttl_seconds = _economic_auto_cache_limits()
    if max_entries <= 0:
        return None
    cached = _ECONOMIC_AUTO_SOURCES_CACHE.get(cache_key)
    if not cached:
        return None
    cached_at, value = cached
    now = time.monotonic()
    effective_ttl = ttl_seconds if value else empty_ttl_seconds
    if effective_ttl and now - cached_at > effective_ttl:
        _ECONOMIC_AUTO_SOURCES_CACHE.pop(cache_key, None)
        return None
    _ECONOMIC_AUTO_SOURCES_CACHE.move_to_end(cache_key)
    return _clone_automatic_sources(value)


def _economic_auto_cache_set(cache_key: str, value: dict[str, dict[str, Any]]) -> None:
    if not cache_key:
        return
    max_entries, _ttl_seconds, _empty_ttl_seconds = _economic_auto_cache_limits()
    if max_entries <= 0:
        return
    _ECONOMIC_AUTO_SOURCES_CACHE[cache_key] = (time.monotonic(), _clone_automatic_sources(value))
    _ECONOMIC_AUTO_SOURCES_CACHE.move_to_end(cache_key)
    while len(_ECONOMIC_AUTO_SOURCES_CACHE) > max_entries:
        _ECONOMIC_AUTO_SOURCES_CACHE.popitem(last=False)


def _clear_economic_auto_sources_cache_for_tests() -> None:
    _ECONOMIC_AUTO_SOURCES_CACHE.clear()


def _economic_auto_cache_key(
    fascicolo: Any,
    payments: Any,
    related_fascicoli: Iterable[Any] | None = None,
) -> str:
    payment_snapshot: dict[str, Any] = {}
    for kind in PAYMENT_KINDS:
        raw = _payment_source_for_kind(payments, kind)
        if raw:
            payment_snapshot[kind] = raw
    payload = {
        "scope": _economic_auto_cache_scope(),
        "fascicoloId": _text(getattr(fascicolo, "id", "")),
        "numero": _text(getattr(fascicolo, "numero", "")),
        "numeroRg": _text(getattr(fascicolo, "numero_rg", "")),
        "annoRg": _text(getattr(fascicolo, "anno_rg", "")),
        "cliente": _text(getattr(fascicolo, "nome_cliente", "")),
        "documentsFingerprint": _document_analysis_fingerprint(fascicolo, related_fascicoli),
        "payments": payment_snapshot,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _document_evidence_probe(text: str, metadata: dict[str, Any], *, limit: int = 40000) -> str:
    label = " ".join(
        _text(metadata.get(key))
        for key in ("filename", "original_filename", "safe_filename", "tipo_documento", "classification")
    )
    return f"{label} {str(text or '')[:limit]}".casefold()


def _document_metadata_probe(metadata: dict[str, Any]) -> str:
    return _document_evidence_probe("", metadata, limit=0)


def _document_metadata_is_xml_document(metadata: dict[str, Any]) -> bool:
    probe = " ".join(
        _text(metadata.get(key))
        for key in (
            "filename",
            "original_filename",
            "safe_filename",
            "storage_path",
            "file_type",
            "mime_type",
        )
    ).casefold()
    return bool(
        re.search(r"(^|[\\/])rt_[^\\/]+\.xml\b", probe, flags=re.IGNORECASE)
        or re.search(r"\.xml(?:$|[\s?#])", probe, flags=re.IGNORECASE)
        or "application/xml" in probe
    )


def _document_text_has_pagopa_rt_xml(text: str) -> bool:
    return is_pagopa_rt_xml(text)


def _document_metadata_may_contain_contributo_unificato(metadata: dict[str, Any]) -> bool:
    probe = _document_metadata_probe(metadata)
    if _document_metadata_is_xml_document(metadata):
        return True
    return any(
        token in probe
        for token in (
            "contributo",
            "contrib",
            "0702100ts",
            "rt_",
            "c.u.",
            " cu ",
            "esenzione cu",
            "esenzione contributo",
            "esenzione dal pagamento",
            "autocert",
            "dichiarazione sostitutiva",
            "reddito",
            "reddituale",
            "situazione reddituale",
            "isee",
            "iscrizione a ruolo",
            "spese di giustizia",
            "dpr 115",
            "d.p.r. 115",
            "art. 9",
            "art. 76",
            "pagopa",
            "pago pa",
            "iuv",
            "ricevuta",
            "ricevuta telematica",
            "pagamento",
            "versamento",
            "importototalepagato",
            "singoloimportopagato",
            "datispecificiriscossione",
            "f23",
            "f24",
        )
    )


def _document_metadata_may_contain_sentenza_economica(metadata: dict[str, Any]) -> bool:
    return "sentenza" in _document_metadata_probe(metadata)


def _document_candidate_datetime(doc: Any, metadata: dict[str, Any] | None = None) -> datetime | None:
    for value in (
        getattr(doc, "data_documento", ""),
        getattr(doc, "data_deposito_portale", ""),
        getattr(doc, "data_caricamento", ""),
    ):
        parsed = _parse_datetime(value)
        if parsed:
            return parsed
    probe = " ".join(
        _text(value)
        for value in (
            (metadata or {}).get("filename"),
            (metadata or {}).get("original_filename"),
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome", ""),
            getattr(doc, "percorso", ""),
        )
    )
    match = re.search(r"\b(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", probe)
    if match:
        try:
            return datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
                int(match.group(5)),
                int(match.group(6)),
            )
        except ValueError:
            return None
    return None


def _rank_sentenza_economica_documents(fascicolo: Any, documents: Iterable[Any]) -> list[Any]:
    max_docs = int(os.getenv("IUSENTRA_ECONOMIC_PRESIDIO_MAX_SENTENZA_DOCUMENTS", "4") or 4)
    if max_docs <= 0:
        max_docs = 4

    ranked: list[tuple[tuple[int, int, int, int, str], Any]] = []
    for index, doc in enumerate(documents or []):
        document_id = _document_id(doc)
        metadata = _document_metadata_for_id(fascicolo, document_id)
        probe = _document_metadata_probe(metadata)
        score = 100
        if "sentenza" in probe:
            score -= 60
        if _text(metadata.get("tipo_documento")).casefold() == "sentenza":
            score -= 20
        if "provvedimento" in probe:
            score -= 15
        if "definitiv" in probe or "p.q.m" in probe or "p. q. m" in probe:
            score -= 10
        if bool(getattr(doc, "ocr_estratto", False)):
            score -= 8
        filename = _text(metadata.get("filename") or metadata.get("safe_filename"))
        if filename.casefold().startswith("atto_") and "sentenza" not in probe:
            score += 25
        try:
            size = int(getattr(doc, "dimensione_bytes", 0) or 0)
        except Exception:
            size = 0
        if size > 8_000_000:
            score += 40
        dated = _document_candidate_datetime(doc, metadata)
        timestamp = int(dated.timestamp()) if dated else 0
        ranked.append(((score, -timestamp, size, index, filename.casefold()), doc))
    ranked.sort(key=lambda item: item[0])
    return [doc for _, doc in ranked[:max_docs]]


def _document_metadata_may_contain_procedural_deadline(metadata: dict[str, Any]) -> bool:
    probe = _document_metadata_probe(metadata)
    return any(
        token in probe
        for token in (
            "udienza",
            "termine",
            "scadenza",
            "fissazione",
            "decreto",
            "ordinanza",
            "provvedimento",
            "verbale",
            "comunicazione",
            "biglietto",
            "avviso",
            "rinvio",
            "trattazione",
            "comparizione",
            "calendario",
            "discussione",
            "convocazione",
            "citazione",
            "note scritte",
            "127-ter",
            "171-bis",
        )
    )


def _rank_procedural_deadline_documents(fascicolo: Any, documents: Iterable[Any]) -> list[Any]:
    max_docs = int(os.getenv("IUSENTRA_DEADLINE_PRESIDIO_MAX_OCR_DOCUMENTS", "4") or 4)
    if max_docs <= 0:
        max_docs = 4
    ranked: list[tuple[tuple[int, int, int, str], Any]] = []
    for index, doc in enumerate(documents or []):
        metadata = _document_metadata_for_id(fascicolo, _document_id(doc))
        probe = _document_metadata_probe(metadata)
        score = 100
        if "decreto" in probe or "ordinanza" in probe:
            score -= 60
        if "fissazione" in probe or "udienza" in probe or "termine" in probe:
            score -= 30
        if "verbale" in probe or "provvedimento" in probe or "comunicazione" in probe:
            score -= 15
        try:
            size = int(getattr(doc, "dimensione_bytes", 0) or 0)
        except (TypeError, ValueError):
            size = 0
        if size > 8_000_000:
            score += 30
        dated = _document_candidate_datetime(doc, metadata)
        timestamp = int(dated.timestamp()) if dated else 0
        filename = _text(metadata.get("filename") or metadata.get("safe_filename")).casefold()
        ranked.append(((score, -timestamp, index, filename), doc))
    ranked.sort(key=lambda item: item[0])
    return [doc for _, doc in ranked[:max_docs]]


def _document_may_contain_contributo_unificato(text: str, metadata: dict[str, Any]) -> bool:
    probe = _document_evidence_probe(text, metadata)
    if is_pagopa_rt_contributo_xml(text):
        return True
    if _document_text_has_pagopa_rt_xml(text):
        return any(
            token in probe
            for token in (
                "contribut",
                "contrib",
                "0702100ts",
                "ministero della giustizia",
                "spese di giustizia",
            )
        )
    return any(
        token in probe
        for token in (
            "contributo unificat",
            "contrib",
            "0702100ts",
            "c.u.",
            " c u ",
            " cu ",
            "esenzione cu",
            "esenzione contributo",
            "esenzione dal pagamento",
            "autocert",
            "dichiarazione sostitutiva",
            "reddito",
            "reddituale",
            "situazione reddituale",
            "isee",
            "iscrizione a ruolo",
            "spese di giustizia",
            "dpr 115",
            "d.p.r. 115",
            "art. 9",
            "art. 76",
            "pagopa",
            "pago pa",
            "iuv",
            "ricevuta pagamento",
            "ricevuta telematica",
            "avviso pagamento",
            "esito pagamento",
            "pagamento cu",
            "pagamento c.u",
            "importototalepagato",
            "singoloimportopagato",
            "datispecificiriscossione",
            "f23",
            "f24",
        )
    )


def _document_may_contain_sentenza_economica(text: str, metadata: dict[str, Any]) -> bool:
    probe = _document_evidence_probe(text, metadata)
    has_sentence = any(
        token in probe
        for token in (
            "sentenza",
            "provvedimento",
            "definitivamente pronunciando",
            "in nome del popolo italiano",
            "p.q.m",
            "p. q. m",
        )
    )
    if not has_sentence:
        return False
    return any(
        token in probe
        for token in (
            "liquid",
            "spese",
            "esbors",
            "compens",
            "onorari",
            "rifusione",
            "€",
            "eur",
            "euro",
        )
    )


def _document_may_contain_procedural_deadline(text: str, metadata: dict[str, Any]) -> bool:
    probe = _document_evidence_probe(text, metadata)
    return any(
        token in probe
        for token in (
            "udienza",
            "termine",
            "scadenza",
            "comparizione",
            "trattazione",
            "note scritte",
            "memorie",
            "opposizione",
            "deposito",
            "171-bis",
            "171 bis",
            "127-ter",
            "127 ter",
        )
    )


def _payment_date_from_document_text(text: str) -> str:
    compact = _text(text)
    for pattern in (
        r"<(?:[^>:]+:)?(?:dataEsitoSingoloPagamento|dataOraMessaggioRicevuta|dataPagamento)[^>]*>\s*(\d{4}-\d{2}-\d{2})",
        r"\bData(?:\s+(?:esito|pagamento|ricevuta))?\s*:\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"\bData/ora\s+Messaggio\s+Ricevuta\s*:\s*(\d{1,2}/\d{1,2}/\d{4})",
    ):
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if not match:
            continue
        parsed = _parse_date(match.group(1))
        if parsed:
            return parsed.isoformat()
    return ""


def _payment_date_from_document_metadata(metadata: dict[str, Any]) -> str:
    for key in ("data_documento", "data_deposito_portale", "data_caricamento"):
        parsed = _parse_date(_text(metadata.get(key)))
        if parsed:
            return parsed.isoformat()
    return ""


def _raw_payment_is_manual(raw: dict[str, Any]) -> bool:
    if not raw:
        return False
    if _payment_source_is_empty_placeholder(raw):
        return False
    automatic_markers = ("import", "automatic", "automatico", "document ai", "lex", "fascicolo", "scheduler")
    history = raw.get("history") or raw.get("storico")
    if isinstance(history, list):
        for entry in history:
            if not isinstance(entry, dict):
                return True
            evidence = " ".join(
                _text(entry.get(key)).casefold()
                for key in ("by", "updated_by", "origine", "origin", "note")
                if _text(entry.get(key))
            )
            if not evidence or not any(marker in evidence for marker in automatic_markers):
                return True
    updated_by = _text(raw.get("updated_by") or raw.get("updatedBy")).casefold()
    origin = _text(raw.get("origine") or raw.get("origin")).casefold()
    if updated_by and not any(marker in updated_by for marker in automatic_markers):
        return True
    if origin and not any(marker in origin for marker in automatic_markers):
        return True
    return False


def _payment_source_is_empty_placeholder(raw: dict[str, Any]) -> bool:
    if not raw:
        return True
    status = _normalise_payment_status(raw.get("status") or raw.get("stato"), default="")
    amount = _payment_amount_value(raw.get("importo") if "importo" in raw else raw.get("amount"))
    if amount is None and status in {"", "non_previsto", "da_registrare", "da_emettere", "parziale"}:
        return True
    if amount is not None and abs(float(amount)) <= 0.01 and status in {"", "da_registrare", "da_emettere", "parziale"}:
        return True
    return False


def _payment_source_evidence_text(raw: dict[str, Any]) -> str:
    if not raw:
        return ""
    return " ".join(
        _text(raw.get(field))
        for field in (
            "documento_fonte",
            "documentoFonte",
            "source",
            "fonte",
            "note",
            "label",
            "natura",
            "origine",
            "origin",
        )
        if _text(raw.get(field))
    )


def _payment_source_document_label(raw: dict[str, Any]) -> str:
    if not raw:
        return ""
    return _text(
        raw.get("documento_fonte")
        or raw.get("documentoFonte")
        or raw.get("source")
        or raw.get("fonte")
        or raw.get("label")
    )


def _merge_auto_payment_source(
    raw: dict[str, Any],
    automatic: dict[str, Any],
    *,
    kind: str,
    replace_automatic: bool = False,
) -> dict[str, Any]:
    if _raw_payment_is_manual(raw):
        return raw
    merged = dict(raw)
    raw_placeholder = _payment_source_is_empty_placeholder(raw)
    status = _normalise_payment_status(raw.get("status") or raw.get("stato"), default="")
    auto_status = _normalise_payment_status(automatic.get("status") or automatic.get("stato"), default="")
    raw_amount = _payment_amount_value(raw.get("importo") if "importo" in raw else raw.get("amount"))
    auto_amount = _payment_amount_value(automatic.get("importo") if "importo" in automatic else automatic.get("amount"))
    if replace_automatic:
        if auto_status:
            merged["status"] = auto_status
            merged["pagato"] = auto_status == "pagato"
            merged["previsto"] = auto_status != "non_previsto"
        if auto_amount is not None or auto_status == "non_previsto":
            merged["importo"] = auto_amount
        for field in (
            "label",
            "natura",
            "valuta",
            "data_pagamento",
            "note",
            "documento_fonte",
            "origine",
        ):
            if field in automatic and automatic.get(field) is not None:
                merged[field] = automatic.get(field)
        return merged
    should_override_status = (
        not status
        or status in {"non_previsto", "da_registrare", "da_emettere"}
        or (kind == "contributo_unificato" and auto_status == "pagato" and status != "pagato")
    )
    if should_override_status and auto_status:
        merged["status"] = auto_status
        merged["pagato"] = auto_status == "pagato"
        merged["previsto"] = auto_status != "non_previsto"
    if auto_amount is not None and (raw_amount is None or abs(float(raw_amount)) <= 0.01):
        merged["importo"] = auto_amount
    elif raw_placeholder and raw_amount is not None and abs(float(raw_amount)) <= 0.01 and kind == "contributo_unificato":
        merged["importo"] = None
    for field in (
        "label",
        "natura",
        "valuta",
        "data_pagamento",
        "note",
        "documento_fonte",
        "origine",
        "updated_by",
    ):
        value = automatic.get(field)
        if value not in {None, ""} and (raw_placeholder or merged.get(field) in {None, ""}):
            merged[field] = value
    return merged


def _payment_source_needs_automatic_value(payments: Any, kind: str) -> bool:
    raw = _payment_source_for_kind(payments, kind)
    if raw and not _payment_source_is_empty_placeholder(raw) and _raw_payment_is_manual(raw):
        return False
    status = _normalise_payment_status(raw.get("status") or raw.get("stato"), default="")
    if status == "non_previsto" and raw.get("previsto") is False:
        return False
    amount = _payment_amount_value(raw.get("importo") if "importo" in raw else raw.get("amount"))
    if amount is None:
        return True
    if abs(float(amount)) <= 0.01 and status in {"", "non_previsto", "da_registrare", "da_emettere", "parziale"}:
        return True
    return False


def _automatic_payment_sources_for_fascicolo(
    fascicolo: Any,
    payments: Any,
    *,
    related_fascicoli: Iterable[Any] | None = None,
    allow_full_document_scan: bool = True,
    allow_document_extraction: bool = True,
    force_revalidate_auto: bool = False,
) -> dict[str, dict[str, Any]]:
    raw_contributo = _payment_source_for_kind(payments, "contributo_unificato")
    need_contributo = _payment_source_needs_automatic_value(payments, "contributo_unificato") or (
        force_revalidate_auto and not _raw_payment_is_manual(raw_contributo)
    )
    need_sentenza = any(
        _payment_source_needs_automatic_value(payments, kind)
        for kind in ("spese_esborsi", "liquidazione_giudice", "parcella")
    )
    if not need_contributo and not need_sentenza:
        return {}
    auto: dict[str, dict[str, Any]] = {}
    try:
        from pct.fascicolo_sentenza_economica import (
            analyze_sentenza_tribunale_text,
            apply_contributo_unificato_pdf_evidence,
            extract_contributo_unificato_document_evidence,
            validate_sentenza_fascicolo_context,
        )
    except Exception:
        return {}

    cu_candidates: list[dict[str, Any]] = []
    cu_exemption_from_misclassified_payment = False
    if need_contributo:
        for kind in PAYMENT_KINDS:
            raw_payment = _payment_source_for_kind(payments, kind)
            if not raw_payment or not _payment_source_is_empty_placeholder(raw_payment):
                continue
            evidence_text = _payment_source_evidence_text(raw_payment)
            if not evidence_text:
                continue
            evidence = extract_contributo_unificato_document_evidence(
                evidence_text,
                {
                    "filename": _payment_source_document_label(raw_payment) or evidence_text,
                    "document_id": _text(raw_payment.get("document_id") or raw_payment.get("documento_id")),
                    "sha256": _text(raw_payment.get("sha256") or raw_payment.get("hash_sha256")),
                },
            )
            if not evidence:
                continue
            evidence = dict(evidence)
            evidence["filename"] = _payment_source_document_label(raw_payment) or evidence.get("filename") or evidence_text
            evidence["origine"] = "import_pratiche"
            cu_candidates.append(evidence)
            if kind != "contributo_unificato" and (
                evidence.get("esente") is True
                or _text(evidence.get("natura")) == "esenzione_contributo_unificato"
            ):
                cu_exemption_from_misclassified_payment = True

    scoped_texts: list[tuple[Any, str, str]] = []
    for source_fascicolo in _analysis_fascicoli_scope(fascicolo, related_fascicoli):
        payment_documents = (
            list(getattr(source_fascicolo, "documenti", []) or [])
            if allow_full_document_scan
            else _document_candidates_for_hints(
                source_fascicolo,
                lambda text, metadata: (
                    need_contributo and _document_may_contain_contributo_unificato(text, metadata)
                )
                or (need_sentenza and _document_may_contain_sentenza_economica(text, metadata)),
                metadata_matcher=lambda metadata: (
                    need_contributo and _document_metadata_may_contain_contributo_unificato(metadata)
                )
                or (need_sentenza and _document_metadata_may_contain_sentenza_economica(metadata)),
            )
        )
        texts = _document_ai_texts_for_fascicolo(source_fascicolo, documents=payment_documents)
        missing_ocr_documents: list[Any] = []
        for doc in payment_documents:
            document_id = _document_id(doc)
            if not document_id or _text(texts.get(document_id)):
                continue
            metadata = _document_metadata_for_id(source_fascicolo, document_id)
            if (
                (need_contributo and _document_metadata_may_contain_contributo_unificato(metadata))
                or (need_sentenza and _document_metadata_may_contain_sentenza_economica(metadata))
            ):
                missing_ocr_documents.append(doc)
        if missing_ocr_documents and allow_document_extraction:
            refreshed_texts = _ensure_economic_document_ai_texts_for_fascicolo(
                source_fascicolo,
                missing_ocr_documents,
            )
            if refreshed_texts:
                texts = {**texts, **refreshed_texts}
        physical_texts: dict[str, str] = {}
        if allow_document_extraction:
            for doc in payment_documents:
                document_id = _document_id(doc)
                if not document_id or _text(texts.get(document_id)):
                    continue
                extracted_text = _extract_presidio_text_from_physical_document(source_fascicolo, doc)
                if extracted_text:
                    physical_texts[document_id] = extracted_text
        if physical_texts:
            texts = {**texts, **physical_texts}
            _cache_document_ai_texts_for_fascicolo(source_fascicolo, payment_documents, texts)
        appended: set[str] = set()
        for document_id, text in texts.items():
            scoped_texts.append((source_fascicolo, document_id, text))
            appended.add(_text(document_id))
        for doc in payment_documents:
            document_id = _document_id(doc)
            if not document_id or document_id in appended:
                continue
            metadata = _document_metadata_for_id(source_fascicolo, document_id)
            if need_contributo and _document_metadata_may_contain_contributo_unificato(metadata):
                scoped_texts.append((source_fascicolo, document_id, _document_metadata_probe(metadata)))
                appended.add(document_id)
    if not scoped_texts and not cu_candidates:
        return {}

    for source_fascicolo, document_id, text in scoped_texts:
        metadata = _document_metadata_for_id(source_fascicolo, document_id)
        if not _document_may_contain_contributo_unificato(text, metadata):
            continue
        evidence = extract_contributo_unificato_document_evidence(text, metadata)
        if evidence:
            evidence = dict(evidence)
            evidence["data_pagamento"] = _payment_date_from_document_text(text) or _payment_date_from_document_metadata(metadata)
            if _text(getattr(source_fascicolo, "id", "")) != _text(getattr(fascicolo, "id", "")):
                evidence["filename"] = (
                    f"{_readable_document_source(evidence.get('filename') or evidence.get('document_id'))} "
                    f"(da pratica riconciliata {getattr(source_fascicolo, 'numero', '') or getattr(source_fascicolo, 'id', '')})"
                )
            cu_candidates.append(evidence)
    best_cu_evidence: dict[str, Any] = {}
    if cu_candidates:
        best_cu = sorted(
            cu_candidates,
            key=lambda item: (
                0 if _text(item.get("status")) == "pagato" and _payment_amount_value(item.get("importo")) is not None else 1,
                0 if item.get("esente") is True or _text(item.get("natura")) == "esenzione_contributo_unificato" else 1,
                0 if _payment_amount_value(item.get("importo")) is not None else 1,
                _text(item.get("filename")),
            ),
        )[0]
        best_cu_evidence = dict(best_cu)
        status = _text(best_cu.get("status")) or ("non_previsto" if best_cu.get("esente") is True else "pagato")
        natura = _text(best_cu.get("natura"))
        note = "Compilato automaticamente dalla ricevuta contributo unificato presente nel fascicolo."
        if status == "non_previsto" or best_cu.get("esente") is True or natura == "esenzione_contributo_unificato":
            note = "Esenzione o non debenza del contributo unificato letta automaticamente dal fascicolo."
        elif status == "da_registrare":
            note = "Richiesta di versamento del contributo unificato letta automaticamente dal fascicolo."
        auto["contributo_unificato"] = {
            "kind": "contributo_unificato",
            "label": _text(best_cu.get("label")) or "Contributo unificato",
            "natura": natura,
            "status": status,
            "previsto": status != "non_previsto",
            "pagato": status == "pagato",
            "importo": None if status == "non_previsto" else best_cu.get("importo"),
            "valuta": "EUR",
            "data_pagamento": best_cu.get("data_pagamento") or "",
            "documento_fonte": _readable_document_source(best_cu.get("filename") or best_cu.get("document_id")),
            "origine": "Document AI / fascicolo",
            "updated_by": "IUSENTRA automatico",
            "note": note,
        }
        if cu_exemption_from_misclassified_payment and _payment_source_needs_automatic_value(payments, "spese_esborsi"):
            auto["spese_esborsi"] = {
                "kind": "spese_esborsi",
                "label": "Spese/esborsi",
                "natura": "nessuna_spesa_documentale",
                "status": "non_previsto",
                "previsto": False,
                "pagato": False,
                "importo": None,
                "valuta": "EUR",
                "data_pagamento": "",
                "documento_fonte": "Autocertificazione riferita al contributo unificato",
                "origine": "IUSENTRA automatico",
                "updated_by": "IUSENTRA automatico",
                "note": "L'autocertificazione importata riguarda il contributo unificato: non viene trattata come spesa/esborso da registrare.",
            }

    for source_fascicolo, document_id, text in scoped_texts:
        metadata = _document_metadata_for_id(source_fascicolo, document_id)
        if not _document_may_contain_sentenza_economica(text, metadata):
            continue
        sentenza_metadata = dict(metadata)
        if best_cu_evidence:
            sentenza_metadata["contributo_unificato_pdf"] = dict(best_cu_evidence)
        extraction = analyze_sentenza_tribunale_text(text, sentenza_metadata)
        apply_contributo_unificato_pdf_evidence(extraction, sentenza_metadata)
        if not getattr(extraction, "found", False):
            continue
        context = validate_sentenza_fascicolo_context(
            text=text,
            extraction=extraction,
            fascicolo=fascicolo,
            metadata=sentenza_metadata,
            fascicolo_id=_text(getattr(fascicolo, "id", "")),
        )
        if not getattr(context, "ok", False):
            continue
        source_name = _readable_document_source(metadata.get("filename") or document_id)
        if _text(getattr(source_fascicolo, "id", "")) != _text(getattr(fascicolo, "id", "")):
            source_name = f"{source_name} (da pratica riconciliata {getattr(source_fascicolo, 'numero', '') or getattr(source_fascicolo, 'id', '')})"
        sentence_date = _text(getattr(extraction, "sentence_date", ""))
        if getattr(extraction, "liquidazione_importo", None) is not None:
            auto["liquidazione_giudice"] = {
                "kind": "liquidazione_giudice",
                "label": "Liquidazione",
                "status": "da_registrare",
                "previsto": True,
                "pagato": False,
                "importo": getattr(extraction, "liquidazione_importo", None),
                "valuta": "EUR",
                "data_pagamento": sentence_date,
                "documento_fonte": source_name,
                "origine": "Document AI / sentenza",
                "updated_by": "IUSENTRA automatico",
                "note": "Importo liquidato letto automaticamente dalla sentenza del fascicolo.",
            }
            auto.setdefault("parcella", {
                "kind": "parcella",
                "label": "Parcella",
                "status": "da_emettere",
                "previsto": True,
                "pagato": False,
                "importo": getattr(extraction, "liquidazione_importo", None),
                "valuta": "EUR",
                "data_pagamento": sentence_date,
                "documento_fonte": source_name,
                "origine": "Document AI / sentenza",
                "updated_by": "IUSENTRA automatico",
                "note": "Parcella proposta automaticamente sulla liquidazione letta in sentenza.",
            })
        spese_amount = getattr(extraction, "spese_esborsi_importo", None)
        if spese_amount is None:
            spese_amount = getattr(extraction, "fondo_spese_importo", None)
        if spese_amount is not None:
            auto["spese_esborsi"] = {
                "kind": "spese_esborsi",
                "label": "Spese/esborsi",
                "status": "da_registrare",
                "previsto": True,
                "pagato": False,
                "importo": spese_amount,
                "valuta": "EUR",
                "data_pagamento": sentence_date,
                "documento_fonte": source_name,
                "origine": "Document AI / sentenza",
                "updated_by": "IUSENTRA automatico",
                "note": "Spese o esborsi letti automaticamente dalla sentenza del fascicolo.",
            }
    return auto


def _payments_with_automatic_sources(
    fascicolo: Any,
    payments: Any,
    *,
    enabled: bool,
    related_fascicoli: Iterable[Any] | None = None,
) -> dict[str, Any]:
    base = dict(payments) if isinstance(payments, dict) else {}
    if not enabled:
        return base
    if _presidio_documentale_marker_is_current(fascicolo, base, related_fascicoli):
        return base
    cache_key = _economic_auto_cache_key(fascicolo, base, related_fascicoli)
    automatic_sources = _economic_auto_cache_get(cache_key)
    if automatic_sources is None:
        automatic_sources = _automatic_payment_sources_for_fascicolo(
            fascicolo,
            base,
            related_fascicoli=related_fascicoli,
        )
        _economic_auto_cache_set(cache_key, automatic_sources)
    for kind, automatic in automatic_sources.items():
        raw = _payment_source_for_kind(base, kind)
        base[kind] = _merge_auto_payment_source(raw, automatic, kind=kind)
    return base


def _payment_source_for_kind(payments: Any, kind: str) -> dict[str, Any]:
    if not isinstance(payments, dict):
        return {}
    matches: list[tuple[str, dict[str, Any]]] = []
    for key, value in payments.items():
        if _normalise_payment_kind(key) == kind and isinstance(value, dict):
            matches.append((_text(key), dict(value)))
    if not matches:
        return {}
    preferred = next((item for item in matches if item[0] == kind), matches[0])
    merged = dict(preferred[1])
    for key, value in matches:
        if key == preferred[0]:
            continue
        for field in (
            "status",
            "stato",
            "pagato",
            "previsto",
            "importo",
            "amount",
            "data_pagamento",
            "dataPagamento",
            "date",
            "metodo",
            "method",
            "note",
            "proforma_id",
            "proformaId",
            "documento_fonte",
            "documentSource",
            "origine",
            "origin",
            "updated_at",
            "updatedAt",
            "updated_by",
            "updatedBy",
        ):
            if field not in merged or merged.get(field) in {None, ""}:
                merged[field] = value.get(field)
        history = []
        for raw_history in (value.get("history") or value.get("storico") or [], merged.get("history") or merged.get("storico") or []):
            if isinstance(raw_history, list):
                history.extend(raw_history)
        if history:
            merged["history"] = history[-25:]
    if kind == "spese_esborsi":
        merged["label"] = "Spese/esborsi"
        merged["natura"] = _text(merged.get("natura") or "spese_esborsi")
    return merged


def _payment_history(raw: dict[str, Any]) -> list[dict[str, str]]:
    rows = raw.get("history") or raw.get("storico") or []
    out: list[dict[str, str]] = []
    if not isinstance(rows, list):
        return out
    for entry in rows[-8:]:
        if not isinstance(entry, dict):
            continue
        out.append(
            {
                "at": _text(entry.get("at") or entry.get("quando")),
                "by": _text(entry.get("by") or entry.get("operatore")),
                "fromStatus": _normalise_payment_status(entry.get("fromStatus") or entry.get("stato_precedente"), default=""),
                "toStatus": _normalise_payment_status(entry.get("toStatus") or entry.get("stato_nuovo"), default=""),
                "fromImporto": _amount_label(_payment_amount_value(entry.get("fromImporto") or entry.get("importo_precedente"))),
                "toImporto": _amount_label(_payment_amount_value(entry.get("toImporto") or entry.get("importo_nuovo"))),
                "note": _short(entry.get("note"), 160),
            }
        )
    return out


def _payment_item(kind: str, raw: dict[str, Any], fid: str) -> dict[str, Any]:
    default_status = PAYMENT_DEFAULT_STATUS[kind]
    label = _short(raw.get("label") or raw.get("etichetta"), 80) or PAYMENT_KIND_LABELS[kind]
    natura = _short(raw.get("natura") or raw.get("nature"), 80)
    status = _normalise_payment_status(raw.get("status") or raw.get("stato"), default="")
    if not status:
        if raw.get("previsto") is False or raw.get("prevista") is False:
            status = "non_previsto"
        elif raw.get("pagato") is True or raw.get("pagata") is True:
            status = "pagato"
        else:
            status = default_status
    if kind != "parcella" and status == "da_emettere":
        status = "da_registrare"
    amount = _payment_amount_value(raw.get("importo") if "importo" in raw else raw.get("amount"))
    if (
        amount is not None
        and abs(float(amount)) <= 0.01
        and status in {"non_previsto", "da_registrare", "da_emettere", "parziale"}
        and not _raw_payment_is_manual(raw)
    ):
        amount = None
    payment_date = _text(raw.get("data_pagamento") or raw.get("dataPagamento") or raw.get("date"))
    source_raw = _text(raw.get("documento_fonte") or raw.get("documentSource") or raw.get("documentoFonte"))
    source_visible = _readable_document_source(source_raw) if source_raw else ""
    if (
        kind == "contributo_unificato"
        and source_visible == "Documento indicizzato del fascicolo"
        and ("pagopa" in f"{label} {natura} {source_raw}".casefold() or "contributo" in f"{label} {natura}".casefold())
    ):
        source_visible = "Ricevuta pagoPA"
    return {
        "kind": kind,
        "label": label,
        "displayLabel": label,
        "natura": natura,
        "status": status,
        "statusLabel": PAYMENT_STATUS_LABELS[status],
        "tone": PAYMENT_STATUS_TONES[status],
        "pagato": status == "pagato",
        "previsto": status != "non_previsto",
        "importo": amount,
        "importoLabel": _amount_label(amount),
        "valuta": _text(raw.get("valuta") or raw.get("currency"), "EUR"),
        "dataPagamento": _date_label(payment_date) if payment_date else "",
        "dataPagamentoIso": payment_date,
        "metodo": _text(raw.get("metodo") or raw.get("method") or raw.get("metodo_pagamento")),
        "note": _italian_dates_in_text(raw.get("note")),
        "proformaId": _text(raw.get("proforma_id") or raw.get("proformaId")),
        "proformaNumber": _text(raw.get("proforma_number") or raw.get("proformaNumber")),
        "origine": _text(raw.get("origine") or raw.get("origin")),
        "documentoFonte": source_visible,
        "documentoFonteRaw": source_raw,
        "updatedAt": _text(raw.get("updated_at") or raw.get("updatedAt")),
        "updatedAtLabel": _date_label(raw.get("updated_at") or raw.get("updatedAt")) if _text(raw.get("updated_at") or raw.get("updatedAt")) else "",
        "updatedBy": _text(raw.get("updated_by") or raw.get("updatedBy")),
        "updateAction": f"/api/v1/ui/fascicoli/{quote(fid, safe='')}/pagamenti/{kind}",
        "history": _payment_history(raw),
    }


def _apply_document_analysis_to_payment_items(items: dict[str, dict[str, Any]], analysis: dict[str, Any]) -> None:
    unresolved = set(analysis.get("unresolvedKinds") or [])
    if "contributo_unificato" not in unresolved:
        return
    contributo = items.get("contributo_unificato")
    if not isinstance(contributo, dict):
        return
    if contributo.get("importo") is not None or contributo.get("status") != "da_registrare":
        return
    contributo["importoLabel"] = "Non trovato"
    if not _text(contributo.get("note")):
        contributo["note"] = _text(
            analysis.get("reason"),
            "Presidio documentale eseguito: ricevuta, autocertificazione o invito al pagamento non risultano leggibili nei documenti correnti.",
        )


def payment_summary_for_fascicolo(
    fascicolo: Any,
    *,
    automatic: bool = False,
    related_fascicoli: Iterable[Any] | None = None,
    parcelle: Iterable[Any] | None = None,
    duplicate_group: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    payments = _payments_with_automatic_sources(
        fascicolo,
        getattr(fascicolo, "pagamenti", {}) or {},
        enabled=automatic,
        related_fascicoli=related_fascicoli,
    )
    items = {
        kind: _payment_item(kind, _payment_source_for_kind(payments, kind), fid)
        for kind in PAYMENT_KINDS
    }
    analysis = _document_analysis_state(
        fascicolo,
        related_fascicoli,
        automatic=automatic,
    )
    _apply_document_analysis_to_payment_items(items, analysis)
    expected = [item for item in items.values() if item["previsto"]]
    missing = [item for item in expected if item["status"] in {"da_registrare", "da_emettere", "parziale"}]
    paid = [item for item in expected if item["status"] == "pagato"]
    if not expected:
        state = "non_previsto"
    elif not missing:
        state = "completo"
    elif paid:
        state = "parziale"
    else:
        state = "da_presidiare"
    total_registered = sum(
        float(item["importo"] or 0.0)
        for item in items.values()
        if item["status"] in {"pagato", "parziale"} and item["importo"] is not None
    )
    advances_to_recover = sum(
        float(item["importo"] or 0.0)
        for kind, item in items.items()
        if kind in {"contributo_unificato", "spese_esborsi"} and item["status"] in {"da_registrare", "parziale"} and item["importo"] is not None
    )
    latest = max((_text(item["updatedAt"]) for item in items.values()), default="")
    updated_by = ""
    if latest:
        updated_by = next((_text(item["updatedBy"]) for item in items.values() if _text(item["updatedAt"]) == latest), "")
    proforma_presidio = _proforma_presidio_for_fascicolo(
        fascicolo,
        items=items,
        parcelle=parcelle,
        duplicate_group=duplicate_group,
    )
    parcella_da_emettere = 1 if proforma_presidio.get("requiresAction") else 0
    state_labels = {
        "completo": "Completo",
        "parziale": "Parziale",
        "da_presidiare": "Da presidiare",
        "non_previsto": "Non previsto",
    }
    state_tones = {
        "completo": "success",
        "parziale": "orange",
        "da_presidiare": "warning",
        "non_previsto": "neutral",
    }
    return {
        "stato": state,
        "statoLabel": state_labels[state],
        "tone": state_tones[state],
        "totaleRegistrato": round(total_registered, 2),
        "totaleRegistratoLabel": _euro(total_registered),
        "anticipazioniDaRecuperare": round(advances_to_recover, 2),
        "anticipazioniDaRecuperareLabel": _euro(advances_to_recover),
        "parcelleDaEmettere": parcella_da_emettere,
        "mancanti": len(missing),
        "updatedAt": latest,
        "updatedAtLabel": _date_label(latest) if latest else "",
        "updatedBy": updated_by,
        "items": items,
        "proformaPresidio": proforma_presidio,
        "analysis": analysis,
    }


def payment_summary_for_fascicolo_fast(
    fascicolo: Any,
    *,
    related_fascicoli: Iterable[Any] | None = None,
    parcelle: Iterable[Any] | None = None,
    duplicate_group: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    raw_payments = getattr(fascicolo, "pagamenti", {}) or {}
    payments = dict(raw_payments) if isinstance(raw_payments, dict) else {}
    items = {
        kind: _payment_item(kind, _payment_source_for_kind(payments, kind), fid)
        for kind in PAYMENT_KINDS
    }
    analysis = _document_analysis_marker_state(
        fascicolo,
        related_fascicoli,
    )
    _apply_document_analysis_to_payment_items(items, analysis)
    expected = [item for item in items.values() if item["previsto"]]
    missing = [item for item in expected if item["status"] in {"da_registrare", "da_emettere", "parziale"}]
    paid = [item for item in expected if item["status"] == "pagato"]
    if not expected:
        state = "non_previsto"
    elif not missing:
        state = "completo"
    elif paid:
        state = "parziale"
    else:
        state = "da_presidiare"
    total_registered = sum(
        float(item["importo"] or 0.0)
        for item in items.values()
        if item["status"] in {"pagato", "parziale"} and item["importo"] is not None
    )
    advances_to_recover = sum(
        float(item["importo"] or 0.0)
        for kind, item in items.items()
        if kind in {"contributo_unificato", "spese_esborsi"} and item["status"] in {"da_registrare", "parziale"} and item["importo"] is not None
    )
    latest = max((_text(item["updatedAt"]) for item in items.values()), default="")
    updated_by = ""
    if latest:
        updated_by = next((_text(item["updatedBy"]) for item in items.values() if _text(item["updatedAt"]) == latest), "")
    proforma_presidio = _proforma_presidio_for_fascicolo(
        fascicolo,
        items=items,
        parcelle=parcelle,
        duplicate_group=duplicate_group,
    )
    parcella_da_emettere = 1 if proforma_presidio.get("requiresAction") else 0
    state_labels = {
        "completo": "Completo",
        "parziale": "Parziale",
        "da_presidiare": "Da presidiare",
        "non_previsto": "Non previsto",
    }
    state_tones = {
        "completo": "success",
        "parziale": "orange",
        "da_presidiare": "warning",
        "non_previsto": "neutral",
    }
    return {
        "stato": state,
        "statoLabel": state_labels[state],
        "tone": state_tones[state],
        "totaleRegistrato": round(total_registered, 2),
        "totaleRegistratoLabel": _euro(total_registered),
        "anticipazioniDaRecuperare": round(advances_to_recover, 2),
        "anticipazioniDaRecuperareLabel": _euro(advances_to_recover),
        "parcelleDaEmettere": parcella_da_emettere,
        "mancanti": len(missing),
        "updatedAt": latest,
        "updatedAtLabel": _date_label(latest) if latest else "",
        "updatedBy": updated_by,
        "items": items,
        "proformaPresidio": proforma_presidio,
        "analysis": analysis,
    }


def _enum_upper(value: Any) -> str:
    return _enum_value(value).upper()


def _fascicolo_is_defined(fascicolo: Any) -> bool:
    return _enum_upper(getattr(fascicolo, "stato", "")) in {"DEFINITO", "CHIUSO", "ARCHIVIATO"}


def _parcella_is_active(parcella: Any) -> bool:
    return _enum_upper(getattr(parcella, "stato", "")) != "ANNULLATA"


def _parcella_amount(parcella: Any) -> float:
    for attr in ("netto_a_pagare", "totale", "imponibile"):
        try:
            value = float(getattr(parcella, attr, 0.0) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        if value:
            return value
    return 0.0


def _parcella_document_label(parcelle: list[Any]) -> str:
    if not parcelle:
        return ""
    first = parcelle[0]
    number = _text(getattr(first, "numero", ""))
    state = _enum_upper(getattr(first, "stato", ""))
    label = number or _text(getattr(first, "id", ""))
    if state:
        label = f"{label} ({state.lower()})" if label else state.lower()
    if len(parcelle) > 1:
        label = f"{label} e altri {len(parcelle) - 1}"
    return label


def _proforma_presidio_for_fascicolo(
    fascicolo: Any,
    *,
    items: dict[str, dict[str, Any]],
    parcelle: Iterable[Any] | None = None,
    duplicate_group: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    encoded_fid = quote(fid, safe="")
    all_parcelle = list(parcelle or [])
    active_parcelle = [item for item in all_parcelle if _parcella_is_active(item)]
    existing_count = len(active_parcelle)
    existing_draft_count = sum(1 for item in active_parcelle if _enum_upper(getattr(item, "stato", "")) == "BOZZA")
    total = round(sum(_parcella_amount(item) for item in active_parcelle), 2)
    duplicate_count = int((duplicate_group or {}).get("count") or 0)
    is_defined = _fascicolo_is_defined(fascicolo)
    parcella_item = items.get("parcella") or {}
    liquidazione_item = items.get("liquidazione_giudice") or {}
    source = visible_source = ""
    for candidate in (parcella_item, liquidazione_item):
        source = _text(candidate.get("documentoFonte") or candidate.get("documento_fonte") or candidate.get("origine"))
        if source:
            visible_source = _readable_document_source(source)
            break
    if existing_count:
        if existing_draft_count:
            status_label = "Bozza proforma da visionare"
            tone = "warning"
            message = (
                f"Bozza proforma creata automaticamente: {_parcella_document_label(active_parcelle)}. "
                "L'avvocato deve visionarla e confermarla prima dell'emissione."
            )
        else:
            status_label = "Proforma presente"
            tone = "success"
            message = f"Documento economico già collegato: {_parcella_document_label(active_parcelle)}."
        return {
            "status": "presente",
            "statusLabel": status_label,
            "tone": tone,
            "message": message,
            "href": f"/fatturazione?id_fascicolo={encoded_fid}",
            "existingCount": existing_count,
            "existingDraftCount": existing_draft_count,
            "total": total,
            "totalLabel": _euro(total),
            "evidence": _parcella_document_label(active_parcelle),
            "requiresAction": False,
        }
    if duplicate_count > 1 and is_defined:
        return {
            "status": "doppione_da_riconciliare",
            "statusLabel": "Doppione da verificare",
            "tone": "warning",
            "message": "Fascicolo definito senza proforma: prima riconciliare le pratiche duplicate dello stesso cliente/RG.",
            "href": f"/fascicoli?rg={quote(_text(getattr(fascicolo, 'numero_rg', '')), safe='')}",
            "existingCount": 0,
            "existingDraftCount": 0,
            "total": 0.0,
            "totalLabel": _euro(0.0),
            "evidence": "cliente e RG duplicati",
            "requiresAction": True,
        }
    if is_defined:
        if parcella_item.get("importo") is not None or liquidazione_item.get("importo") is not None:
            amount = parcella_item.get("importo") if parcella_item.get("importo") is not None else liquidazione_item.get("importo")
            return {
                "status": "da_preparare",
                "statusLabel": "Proforma da preparare",
                "tone": "warning",
                "message": f"Fascicolo definito: prepara la proforma con importo letto {_amount_label(amount)}.",
                "href": f"/fatturazione/nuova?id_fascicolo={encoded_fid}",
                "existingCount": 0,
                "existingDraftCount": 0,
                "total": 0.0,
                "totalLabel": _euro(0.0),
                "evidence": visible_source,
                "requiresAction": True,
            }
        if visible_source:
            return {
                "status": "importi_da_confermare",
                "statusLabel": "Importi da confermare",
                "tone": "warning",
                "message": "Fascicolo definito: documento economico letto, ma importo da confermare prima della proforma.",
                "href": f"/fascicoli/{encoded_fid}#documenti",
                "existingCount": 0,
                "existingDraftCount": 0,
                "total": 0.0,
                "totalLabel": _euro(0.0),
                "evidence": visible_source,
                "requiresAction": True,
            }
        return {
            "status": "sentenza_da_acquisire",
            "statusLabel": "Sentenza da acquisire",
            "tone": "warning",
            "message": "Fascicolo definito senza proforma: acquisire o classificare la sentenza e poi preparare il documento economico.",
            "href": f"/fascicoli/{encoded_fid}#documenti",
            "existingCount": 0,
            "existingDraftCount": 0,
            "total": 0.0,
            "totalLabel": _euro(0.0),
            "evidence": "",
            "requiresAction": True,
        }
    if parcella_item.get("importo") is not None or _text(parcella_item.get("documentoFonte")):
        return {
            "status": "da_preparare",
            "statusLabel": "Proforma da preparare",
            "tone": "warning",
            "message": "Importo o fonte economica letta dal fascicolo: verifica se emettere la proforma.",
            "href": f"/fatturazione/nuova?id_fascicolo={encoded_fid}",
            "existingCount": 0,
            "existingDraftCount": 0,
            "total": 0.0,
            "totalLabel": _euro(0.0),
            "evidence": visible_source,
            "requiresAction": True,
        }
    return {
        "status": "non_applicabile",
        "statusLabel": "Non ancora dovuta",
        "tone": "neutral",
        "message": "",
        "href": f"/fatturazione/nuova?id_fascicolo={encoded_fid}",
        "existingCount": 0,
        "existingDraftCount": 0,
        "total": 0.0,
        "totalLabel": _euro(0.0),
        "evidence": "",
        "requiresAction": False,
    }


def _payment_date_iso(value: Any) -> tuple[str, str]:
    raw = _text(value)
    if not raw:
        return "", ""
    parsed = _parse_date(raw)
    if not parsed:
        return "", "Inserisci una data valida."
    return parsed.isoformat(), ""


def update_react_fascicolo_payment(
    *,
    get_fascicoli: Callable[[], Any],
    get_fatturazione: Callable[[], Any] | None = None,
    id_fasc: str,
    kind: str,
    payload: dict[str, Any],
    actor: str = "",
) -> tuple[dict[str, Any], int]:
    normalized_kind = _normalise_payment_kind(kind)
    if normalized_kind not in PAYMENT_KINDS:
        return {"ok": False, "message": "Voce economica non riconosciuta.", "errors": {"kind": "Voce economica non riconosciuta."}}, 400
    repo = get_fascicoli()
    fascicolo = _resolve_fascicolo(repo, id_fasc)
    if not fascicolo:
        return {"ok": False, "message": "Fascicolo non trovato.", "errors": {"fascicolo": "Fascicolo non trovato."}}, 404
    raw_status = _text(payload.get("status") or payload.get("stato"))
    status = _normalise_payment_status(raw_status, default="")
    if not status:
        status = PAYMENT_DEFAULT_STATUS[normalized_kind]
    if normalized_kind != "parcella" and status == "da_emettere":
        status = "da_registrare"
    amount = _payment_amount_value(payload.get("importo") if "importo" in payload else payload.get("amount"))
    if amount is not None and amount < 0:
        return {"ok": False, "message": "L'importo non può essere negativo.", "errors": {"importo": "L'importo non può essere negativo."}}, 400
    payment_nature = _short(payload.get("natura") or payload.get("nature"), 80)
    payment_nature_key = re.sub(r"[^a-z0-9]+", "_", payment_nature.casefold()).strip("_")
    if normalized_kind == "contributo_unificato":
        if any(marker in payment_nature_key for marker in ("esenzione", "non_dovuto", "non_debenza")):
            status = "non_previsto"
            amount = None
            payment_nature = payment_nature or "esenzione_contributo_unificato"
        elif "debito" in payment_nature_key or "prenot" in payment_nature_key:
            status = "pagato"
            payment_nature = payment_nature or "prenotazione_a_debito"
        elif status == "pagato":
            payment_nature = payment_nature or "pagamento_contributo_unificato"
        elif status == "non_previsto":
            payment_nature = payment_nature or "esenzione_contributo_unificato"
    date_iso, date_error = _payment_date_iso(payload.get("dataPagamento") or payload.get("data_pagamento") or payload.get("date"))
    if date_error:
        return {"ok": False, "message": date_error, "errors": {"dataPagamento": date_error}}, 400

    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    previous_raw = _payment_source_for_kind(payments, normalized_kind)
    previous = _payment_item(normalized_kind, previous_raw, _text(getattr(fascicolo, "id", id_fasc)))
    history = list(previous_raw.get("history") or previous_raw.get("storico") or [])
    now = _now()
    operator = _text(actor, "Operatore")
    history.append(
        {
            "at": now,
            "by": operator,
            "fromStatus": previous["status"],
            "toStatus": status,
            "fromImporto": previous.get("importo"),
            "toImporto": amount,
            "note": _short(payload.get("note"), 160),
        }
    )
    next_payment = dict(previous_raw)
    next_payment.update(
        {
            "kind": normalized_kind,
            "label": PAYMENT_KIND_LABELS[normalized_kind],
            "status": status,
            "previsto": status != "non_previsto",
            "pagato": status == "pagato",
            "importo": amount,
            "valuta": "EUR",
            "data_pagamento": date_iso,
            "metodo": _short(payload.get("metodo") or payload.get("method"), 80),
            "note": _short(payload.get("note"), 400),
            "updated_at": now,
            "updated_by": operator,
            "history": history[-25:],
        }
    )
    if payment_nature:
        next_payment["natura"] = payment_nature
    if "documento_fonte" in payload or "documentoFonte" in payload or "documentSource" in payload:
        next_payment["documento_fonte"] = _short(
            payload.get("documento_fonte") or payload.get("documentoFonte") or payload.get("documentSource"),
            240,
        )
    if "documento_id" in payload or "documentoId" in payload:
        next_payment["documento_id"] = _short(payload.get("documento_id") or payload.get("documentoId"), 80)
    for existing_key in list(payments.keys()):
        if existing_key != normalized_kind and _normalise_payment_kind(existing_key) == normalized_kind:
            payments.pop(existing_key, None)
    payments[normalized_kind] = next_payment
    linked_proforma = _sync_linked_proforma_payment(
        get_fatturazione=get_fatturazione,
        payment=next_payment,
        status=status,
        date_iso=date_iso,
    )
    fid = _text(getattr(fascicolo, "id", id_fasc))
    if hasattr(repo, "aggiorna"):
        fascicolo = repo.aggiorna(fid, pagamenti=payments)
    else:
        setattr(fascicolo, "pagamenti", payments)
        saver = getattr(repo, "_salva", None)
        if callable(saver):
            saver()
    summary = payment_summary_for_fascicolo(fascicolo)
    return {
        "ok": True,
        "message": f"{PAYMENT_KIND_LABELS[normalized_kind]} aggiornato.",
        "payment": summary["items"][normalized_kind],
        "paymentSummary": summary,
        "fascicolo": {"id": fid},
        "linkedProforma": linked_proforma,
    }, 200


def update_react_fascicolo_deposit_value(
    *,
    get_fascicoli: Callable[[], Any],
    id_fasc: str,
    payload: dict[str, Any],
    actor: str = "",
) -> tuple[dict[str, Any], int]:
    repo = get_fascicoli()
    fascicolo = _resolve_fascicolo(repo, id_fasc)
    if not fascicolo:
        return {"ok": False, "message": "Fascicolo non trovato.", "errors": {"fascicolo": "Fascicolo non trovato."}}, 404
    raw_value = payload.get("valore_causa") if "valore_causa" in payload else payload.get("value")
    value = _payment_amount_value(raw_value)
    raw_clean = _text(raw_value)
    if value is None and raw_clean not in {"0", "0,00", "0.00"}:
        return {
            "ok": False,
            "message": "Inserisci un valore della causa valido.",
            "errors": {"valore_causa": "Valore della causa non valido."},
        }, 400
    value = 0.0 if value is None else value
    fid = _text(getattr(fascicolo, "id", id_fasc))
    if not hasattr(repo, "aggiorna"):
        return {"ok": False, "message": "Aggiornamento del fascicolo non disponibile."}, 409
    repo.aggiorna(fid, valore_causa=value)
    return {
        "ok": True,
        "message": f"Valore della causa aggiornato a {format_euro_it(value)}.",
        "fascicolo": {"id": fid, "valoreCausa": value, "updatedBy": _text(actor, "Operatore")},
    }, 200


def _sync_linked_proforma_payment(
    *,
    get_fatturazione: Callable[[], Any] | None,
    payment: dict[str, Any],
    status: str,
    date_iso: str,
) -> dict[str, Any]:
    proforma_id = _text(payment.get("proforma_id") or payment.get("proformaId"))
    if status != "pagato" or not proforma_id or not callable(get_fatturazione):
        return {}
    try:
        from pct.fatturazione import StatoParcella

        manager = get_fatturazione()
        item = manager.get(proforma_id)
        if not item:
            return {"ok": False, "id": proforma_id, "message": "Proforma collegata non trovata."}
        manager.cambia_stato(
            proforma_id,
            StatoParcella.PAGATA,
            data_pagamento=date_iso or None,
            metodo_pagamento=_text(payment.get("metodo") or "Bonifico bancario"),
        )
        updated = manager.get(proforma_id)
        return {
            "ok": True,
            "id": proforma_id,
            "state": _enum_value(getattr(updated, "stato", "")),
            "number": _text(getattr(updated, "numero", "")),
        }
    except Exception:
        return {
            "ok": False,
            "id": proforma_id,
            "message": "Proforma collegata non aggiornata automaticamente.",
        }


def _parcelle_by_fascicolo(get_fatturazione: Callable[[], Any] | None) -> dict[str, list[Any]]:
    if not callable(get_fatturazione):
        return {}
    manager = _safe("fatturazione", get_fatturazione, None)
    if manager is None or not callable(getattr(manager, "tutte", None)):
        return {}
    rows = _safe("fatturazione_tutte", lambda: list(manager.tutte()), [])
    out: dict[str, list[Any]] = {}
    for item in rows:
        fid = _text(getattr(item, "id_fascicolo", ""))
        if fid:
            out.setdefault(fid, []).append(item)
    return out


def _fascicolo_auto_proforma_amount(fascicolo: Any) -> tuple[float | None, str]:
    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    for kind, label in (
        ("parcella", "importo Parcella confermato dall’avvocato"),
        ("liquidazione_giudice", "liquidazione del giudice confermata dall’avvocato"),
    ):
        source = _payment_source_for_kind(payments, kind)
        amount = _payment_amount_value(source.get("importo") if isinstance(source, dict) else None)
        if amount is not None and amount > 0:
            return float(amount), label
    for attr, label in (
        ("compenso_pattuito", "compenso pattuito nel fascicolo"),
        ("valore_preventivato", "valore preventivato nel fascicolo"),
    ):
        amount = _payment_amount_value(getattr(fascicolo, attr, None))
        if amount is not None and amount > 0:
            return float(amount), label
    return None, ""


def _requested_proforma_basis(payload: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(payload, dict) or "basis" not in payload:
        return None, ""
    raw = payload.get("basis")
    if not isinstance(raw, dict):
        return None, "La base economica indicata non è valida."
    kind = _normalise_payment_kind(raw.get("sourceKind") or raw.get("source_kind") or raw.get("kind"))
    if kind not in {"parcella", "liquidazione_giudice"}:
        return None, "Seleziona Parcella o Liquidazione giudice come fonte dell’importo."
    amount = _payment_amount_value(raw.get("importo") if "importo" in raw else raw.get("amount"))
    if amount is None or amount <= 0:
        return None, "Inserisci un importo maggiore di zero prima di generare la proforma."
    return {
        "kind": kind,
        "status": _normalise_payment_status(raw.get("status") or raw.get("stato"), default=PAYMENT_DEFAULT_STATUS[kind]),
        "importo": amount,
        "dataPagamento": _text(raw.get("dataPagamento") or raw.get("data_pagamento") or raw.get("date")),
        "metodo": _text(raw.get("metodo") or raw.get("method")),
        "note": _text(raw.get("note")),
    }, ""


def _create_review_proforma_from_fascicolo_amount(
    *,
    fascicoli_repository: Any,
    fatturazione_repository: Any,
    fascicolo: Any,
    amount: float,
    amount_source: str,
    actor: str,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    id_cliente = _text(getattr(fascicolo, "id_cliente", ""))
    if not fid or not id_cliente or amount <= 0:
        return {"created": False, "reason": "Base economica o cliente mancanti."}
    try:
        from pct.fatturazione import VoceParcella
    except Exception as exc:
        return {"created": False, "reason": f"Modulo fatturazione non disponibile: {type(exc).__name__}."}
    oggi = date.today()
    due = oggi + timedelta(days=30)
    title = _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "oggetto", "")) or _rg(fascicolo)
    data = {
        "document": {
            "tipo_documento": "TD01",
            "tipo_documento_label": "Proforma",
            "numero_documento": "",
            "data_documento": oggi.isoformat(),
            "causale_oggetto": f"Bozza proforma da verificare - {title}",
            "documento_operativo": "PROFORMA",
            "fascicolo_label": title,
            "revisione_avvocato_richiesta": True,
        },
        "payment": {
            "modalita_pagamento": "MP05",
            "modalita_pagamento_label": "Bonifico",
            "modalita_pagamento_codice": "MP05",
            "data_decorrenza": due.isoformat(),
            "giorni_termini": "30",
            "importo_pagamento": "",
        },
        "presidio_economico": {
            "origin": "presidio_economico_fascicolo_definito",
            "amount_source": amount_source,
            "created_at": _now(),
            "review_required": True,
            "taxes_to_review": True,
        },
    }
    creator = getattr(fatturazione_repository, "crea", None)
    if not callable(creator):
        return {"created": False, "reason": "Repository fatturazione non scrivibile."}
    proforma = creator(
        id_cliente=id_cliente,
        id_fascicolo=fid,
        voci=[
            VoceParcella(
                descrizione=f"Compenso professionale da verificare ({amount_source})",
                quantita=1.0,
                prezzo_unitario=amount,
                tipo="ONORARIO",
            )
        ],
        creato_da=_text(actor, "IUSENTRA"),
        data_emissione=oggi.isoformat(),
        data_scadenza=due.isoformat(),
        applica_iva=False,
        applica_cassa=False,
        applica_ritenuta=False,
        applica_bollo=False,
        percentuale_spese_generali=0.0,
        note=(
            "Bozza proforma generata automaticamente dal presidio economico; importo totale indicativo "
            "da visionare, completare fiscalmente e confermare dall'avvocato prima dell'emissione."
        ),
        origine="presidio_economico_fascicolo_definito",
        tipo_compenso="Bozza automatica da fascicolo definito",
        tipo_procedimento=_text(getattr(fascicolo, "tipo_procedimento", "")),
        valore_controversia=float(getattr(fascicolo, "valore_causa", 0.0) or 0.0),
        dati_personalizzati=data,
    )
    data["document"]["numero_documento"] = _text(getattr(proforma, "numero", ""))
    updater = getattr(fatturazione_repository, "aggiorna", None)
    if callable(updater):
        proforma = updater(_text(getattr(proforma, "id", "")), dati_personalizzati=data)
    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    payments["parcella"] = {
        "kind": "parcella",
        "label": "Parcella",
        "status": "da_emettere",
        "previsto": True,
        "pagato": False,
        "importo": amount,
        "valuta": "EUR",
        "data_pagamento": oggi.isoformat(),
        "documento_fonte": amount_source,
        "origine": "Presidio economico automatico",
        "updated_by": _text(actor, "IUSENTRA"),
        "proforma_id": _text(getattr(proforma, "id", "")),
        "proforma_number": _text(getattr(proforma, "numero", "")),
        "note": "Bozza proforma automatica da visionare prima dell'emissione.",
    }
    if callable(getattr(fascicoli_repository, "aggiorna", None)):
        fascicoli_repository.aggiorna(fid, pagamenti=payments)
    return {
        "created": True,
        "proformaId": _text(getattr(proforma, "id", "")),
        "proformaNumber": _text(getattr(proforma, "numero", "")),
        "amount": amount,
        "amountLabel": _euro(amount),
    }


def _ensure_auto_proforma_for_fascicolo(
    *,
    fascicoli_repository: Any,
    fatturazione_repository: Any,
    fascicolo: Any,
    actor: str = "IUSENTRA",
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    if not fid or not _fascicolo_is_defined(fascicolo):
        return {"status": "skipped", "reason": "Fascicolo non definito."}
    existing = [
        item
        for item in _safe("parcelle_fascicolo", lambda: list(fatturazione_repository.per_fascicolo(fid)), [])
        if _parcella_is_active(item)
    ]
    if existing:
        return {"status": "existing", "count": len(existing)}
    try:
        from pct.fascicolo_sentenza_economica import apply_sentenza_tribunale_automation
    except Exception:
        apply_sentenza_tribunale_automation = None
    if callable(apply_sentenza_tribunale_automation):
        payment_documents = _document_candidates_for_hints(
            fascicolo,
            lambda text, metadata: _document_may_contain_sentenza_economica(text, metadata),
            metadata_matcher=lambda metadata: _document_metadata_may_contain_sentenza_economica(metadata),
            fallback_all=False,
        )
        payment_documents = _rank_sentenza_economica_documents(fascicolo, payment_documents)
        texts = _document_ai_texts_for_fascicolo(fascicolo, documents=payment_documents)
        for doc in payment_documents:
            document_id = _document_id(doc)
            if not document_id or texts.get(document_id):
                continue
            extracted_text = _extract_presidio_text_from_physical_document(fascicolo, doc)
            if extracted_text:
                texts[document_id] = extracted_text
        for document_id, text in texts.items():
            metadata = _document_metadata_for_id(fascicolo, document_id)
            if not _document_may_contain_sentenza_economica(text, metadata):
                continue
            outcome = apply_sentenza_tribunale_automation(
                fascicoli_repository=fascicoli_repository,
                fatturazione_repository=fatturazione_repository,
                fascicolo_id=fid,
                text=text,
                document_metadata=metadata,
                actor=actor,
            )
            if _text(getattr(outcome, "proforma_id", "")):
                return {
                    "status": "created",
                    "source": "sentenza",
                    "proformaId": _text(getattr(outcome, "proforma_id", "")),
                    "proformaNumber": _text(getattr(outcome, "proforma_number", "")),
                    "message": _text(getattr(outcome, "message", "")),
                }
    amount, amount_source = _fascicolo_auto_proforma_amount(fascicolo)
    if amount is not None:
        created = _create_review_proforma_from_fascicolo_amount(
            fascicoli_repository=fascicoli_repository,
            fatturazione_repository=fatturazione_repository,
            fascicolo=fascicolo,
            amount=amount,
            amount_source=amount_source,
            actor=actor,
        )
        if created.get("created"):
            return {"status": "created", "source": "fascicolo", **created}
    return {"status": "missing_basis", "reason": "Nessuna sentenza/importo utile per creare una bozza proforma."}


def generate_react_fascicolo_proforma(
    *,
    get_fascicoli: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_utenti: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None,
    current_user: Any,
    id_fasc: str,
    payload: dict[str, Any] | None,
    config: dict[str, Any],
    actor: str = "IUSENTRA",
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    """Genera o riapre la proforma collegata usando i dati economici persistiti."""

    fascicoli_repository = get_fascicoli()
    fascicolo = _resolve_fascicolo(fascicoli_repository, id_fasc)
    if fascicolo is None:
        return {
            "ok": False,
            "message": "Fascicolo non trovato.",
            "errors": {"fascicolo": "Il fascicolo non è disponibile nello studio."},
        }, 404
    requested_basis, basis_error = _requested_proforma_basis(payload)
    if basis_error:
        return {
            "ok": False,
            "message": basis_error,
            "errors": {"importo": basis_error},
        }, 400
    amount, amount_source = _fascicolo_auto_proforma_amount(fascicolo)
    if amount is not None and requested_basis is not None:
        requested_amount = float(requested_basis["importo"])
        if abs(float(amount) - requested_amount) > 0.009:
            return {
                "ok": False,
                "message": "I dati economici sono cambiati mentre il pannello era aperto. Ricarica la pagina e controlla l’importo prima di creare la proforma.",
                "errors": {"importo": "Importo non allineato ai dati salvati del fascicolo."},
            }, 409
    if amount is None and requested_basis is not None:
        saved, saved_status = update_react_fascicolo_payment(
            get_fascicoli=lambda: fascicoli_repository,
            get_fatturazione=get_fatturazione,
            id_fasc=id_fasc,
            kind=_text(requested_basis.get("kind")),
            payload=requested_basis,
            actor=actor,
        )
        if not saved.get("ok"):
            return saved, saved_status
        fascicolo = _resolve_fascicolo(fascicoli_repository, id_fasc)
        amount, amount_source = _fascicolo_auto_proforma_amount(fascicolo)
    if amount is None or amount <= 0:
        return {
            "ok": False,
            "message": "Inserisci l’importo nella voce Parcella e salva per generare la proforma.",
            "errors": {"importo": "Importo Parcella obbligatorio."},
        }, 400

    from web.services.react_fatturazione_bridge import create_react_fascicolo_proforma

    result, status = create_react_fascicolo_proforma(
        get_fatturazione=get_fatturazione,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_utenti=get_utenti,
        get_preventivi=get_preventivi,
        current_user=current_user,
        fascicolo=fascicolo,
        amount=amount,
        amount_source=amount_source,
        config=config,
        ip_address=ip_address,
    )
    if not result.get("ok"):
        return result, status

    item = result.get("item") if isinstance(result.get("item"), dict) else {}
    proforma_id = _text(item.get("id"))
    proforma_number = _text(item.get("number"))
    if not proforma_id:
        return {
            "ok": False,
            "message": "Proforma non verificata nell’archivio fatturazione.",
            "errors": {"persistence": "Identificativo del documento mancante."},
        }, 500

    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    previous_raw = _payment_source_for_kind(payments, "parcella")
    previous = _payment_item("parcella", previous_raw, _text(getattr(fascicolo, "id", id_fasc)))
    history = list(previous_raw.get("history") or previous_raw.get("storico") or [])
    history.append({
        "at": _now(),
        "by": _text(actor, "Operatore"),
        "fromStatus": previous.get("status"),
        "toStatus": "da_emettere",
        "fromImporto": previous.get("importo"),
        "toImporto": amount,
        "note": f"Proforma {proforma_number or proforma_id} collegata.",
    })
    next_payment = dict(previous_raw)
    next_payment.update({
        "kind": "parcella",
        "label": "Parcella",
        "status": "da_emettere",
        "previsto": True,
        "pagato": False,
        "importo": amount,
        "valuta": "EUR",
        "documento_fonte": amount_source,
        "origine": "Controllo economico del fascicolo",
        "updated_at": _now(),
        "updated_by": _text(actor, "Operatore"),
        "proforma_id": proforma_id,
        "proforma_number": proforma_number,
        "history": history[-25:],
    })
    payments["parcella"] = next_payment
    try:
        if not callable(getattr(fascicoli_repository, "aggiorna", None)):
            raise RuntimeError("Repository fascicoli non scrivibile.")
        fascicolo = fascicoli_repository.aggiorna(
            _text(getattr(fascicolo, "id", id_fasc)),
            pagamenti=payments,
        )
    except Exception:
        if not result.get("existing"):
            try:
                get_fatturazione().elimina(proforma_id)
            except Exception:
                pass
        return {
            "ok": False,
            "message": "Proforma non collegata al fascicolo; l’operazione è stata annullata.",
            "errors": {"fascicolo": "Salvataggio del collegamento non riuscito."},
        }, 500

    parcelle = _safe(
        "parcelle_fascicolo",
        lambda: list(get_fatturazione().per_fascicolo(_text(getattr(fascicolo, "id", id_fasc)))),
        [],
    )
    summary = payment_summary_for_fascicolo(fascicolo, parcelle=parcelle)
    redirect_href = _text(result.get("redirect_href")) or f"/fatturazione?id_documento={quote(proforma_id, safe='')}"
    return {
        **result,
        "ok": True,
        "proformaId": proforma_id,
        "proformaNumber": proforma_number,
        "redirectHref": redirect_href,
        "paymentSummary": summary,
    }, 200


def _ensure_contributo_unificato_for_fascicolo(
    *,
    fascicoli_repository: Any,
    fascicolo: Any,
    actor: str = "IUSENTRA",
    persist: bool = True,
    force_revalidate: bool = False,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    if not fid:
        return {"status": "skipped", "reason": "Fascicolo senza ID."}
    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    raw_cu = _payment_source_for_kind(payments, "contributo_unificato")
    needs_cu_value = _payment_source_needs_automatic_value(payments, "contributo_unificato")
    marker = _presidio_documentale_marker(payments)
    marker_current = _presidio_documentale_marker_is_current(fascicolo, payments)
    force_revalidate_auto = force_revalidate or (
        _text(marker.get("analysisVersion") or marker.get("analysis_version"))
        != ECONOMIC_DOCUMENT_ANALYSIS_VERSION
        or not marker_current
    )
    if marker_current and not force_revalidate_auto:
        if not needs_cu_value:
            return {"status": "existing", "analysisUpdated": False}
        if _presidio_documentale_has_unresolved_kind(marker, "contributo_unificato"):
            return {"status": "missing_current", "analysisUpdated": False}
    scan_payments = dict(payments)
    for other_kind in ("spese_esborsi", "liquidazione_giudice", "parcella"):
        scan_payments.setdefault(other_kind, {"kind": other_kind, "status": "non_previsto", "previsto": False})
    automatic_sources = _automatic_payment_sources_for_fascicolo(
        fascicolo,
        scan_payments,
        allow_full_document_scan=True,
        allow_document_extraction=False,
        force_revalidate_auto=force_revalidate_auto,
    )
    automatic = automatic_sources.get("contributo_unificato") if isinstance(automatic_sources, dict) else None
    unresolved_kinds: list[str] = []
    if needs_cu_value and not automatic:
        unresolved_kinds.append("contributo_unificato")
    marker = _build_presidio_documentale_marker(
        fascicolo,
        actor=actor,
        automatic_sources=automatic_sources if isinstance(automatic_sources, dict) else {},
        status="aggiornato",
        reason="Presidio documentale eseguito: lettura, classificazione e dati salvati nel fascicolo.",
    )
    if unresolved_kinds:
        marker["unresolvedKinds"] = unresolved_kinds
        marker["reason"] = (
            "Presidio documentale eseguito: nei documenti correnti non risulta una ricevuta, "
            "un'autocertificazione di esenzione o un invito al pagamento del contributo unificato leggibile."
        )
    payments["_presidio_documentale"] = marker
    updater = getattr(fascicoli_repository, "aggiorna", None)
    if persist and not callable(updater):
        return {"status": "error", "reason": "Repository fascicoli non scrivibile.", "analysisUpdated": False}
    if not isinstance(automatic_sources, dict) or not automatic_sources:
        _apply_presidio_payments_to_fascicolo(fascicolo, payments)
        if persist:
            updater(fid, pagamenti=payments)
        return {"status": "missing" if unresolved_kinds else "marked", "analysisUpdated": True}
    updated_kinds: list[str] = []
    updated_payments: dict[str, dict[str, Any]] = {}
    for source_kind, automatic_payment in automatic_sources.items():
        kind = _normalise_payment_kind(source_kind)
        if kind not in PAYMENT_KINDS or not isinstance(automatic_payment, dict):
            continue
        raw_payment = _payment_source_for_kind(payments, kind)
        merged = _merge_auto_payment_source(
            raw_payment,
            automatic_payment,
            kind=kind,
            replace_automatic=force_revalidate_auto,
        )
        if merged == raw_payment:
            continue
        merged.setdefault("kind", kind)
        merged.setdefault("label", PAYMENT_KIND_LABELS.get(kind, kind.replace("_", " ").title()))
        merged["updated_by"] = _text(actor, "IUSENTRA")
        merged["updated_at"] = _now()
        history = list(raw_payment.get("history") or raw_payment.get("storico") or []) if isinstance(raw_payment, dict) else []
        history.append(
            {
                "at": merged["updated_at"],
                "by": _text(actor, "IUSENTRA"),
                "fromStatus": _normalise_payment_status(raw_payment.get("status") or raw_payment.get("stato"), default=""),
                "toStatus": _normalise_payment_status(merged.get("status") or merged.get("stato"), default=""),
                "fromImporto": raw_payment.get("importo") if isinstance(raw_payment, dict) else None,
                "toImporto": merged.get("importo"),
                "note": "Dato economico consolidato automaticamente dai documenti del fascicolo.",
                "origine": _text(merged.get("origine") or "Document AI / fascicolo"),
            }
        )
        merged["history"] = history[-25:]
        payments[kind] = merged
        updated_kinds.append(kind)
        updated_payments[kind] = merged
    if not updated_kinds:
        _apply_presidio_payments_to_fascicolo(fascicolo, payments)
        if persist:
            updater(fid, pagamenti=payments)
        return {"status": "existing", "analysisUpdated": True}
    _apply_presidio_payments_to_fascicolo(fascicolo, payments)
    if persist:
        updater(fid, pagamenti=payments)
    merged_cu = updated_payments.get("contributo_unificato") or _payment_source_for_kind(payments, "contributo_unificato")
    return {
        "status": "updated" if "contributo_unificato" in updated_kinds else "economic_updated",
        "amount": _payment_amount_value(merged_cu.get("importo")),
        "statusValue": _normalise_payment_status(merged_cu.get("status") or merged_cu.get("stato"), default=""),
        "source": _payment_source_document_label(merged_cu),
        "updatedKinds": updated_kinds,
        "analysisUpdated": True,
    }


def _apply_presidio_payments_to_fascicolo(fascicolo: Any, payments: dict[str, Any]) -> None:
    try:
        setattr(fascicolo, "pagamenti", payments)
        if hasattr(fascicolo, "modificato_il"):
            setattr(fascicolo, "modificato_il", datetime.now().isoformat())
    except Exception:
        pass


def _ensure_fascicolo_definito_from_economics(
    *,
    fascicoli_repository: Any,
    fascicolo: Any,
    actor: str = "IUSENTRA",
    persist: bool = True,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    if not fid:
        return {"updated": False, "reason": "Fascicolo senza ID."}
    current = _enum_upper(getattr(fascicolo, "stato", ""))
    if current not in {"APERTO", "IN_CORSO"}:
        return {"updated": False, "reason": "Stato non modificabile dal presidio economico."}
    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    liquidazione = _payment_item("liquidazione_giudice", _payment_source_for_kind(payments, "liquidazione_giudice"), fid)
    parcella = _payment_item("parcella", _payment_source_for_kind(payments, "parcella"), fid)
    if liquidazione.get("status") != "pagato" or parcella.get("status") != "da_emettere":
        return {"updated": False, "reason": "Regola economica non soddisfatta."}
    note = "Definito automaticamente: liquidazione pagata e parcella da emettere."
    if persist and hasattr(fascicoli_repository, "cambia_stato"):
        fascicoli_repository.cambia_stato(
            fid,
            StatoFascicolo.DEFINITO,
            note=note,
            avvocato=_text(actor, "IUSENTRA"),
        )
        return {"updated": True, "status": "definito"}
    previous = _enum_value(getattr(fascicolo, "stato", "")) or current
    try:
        setattr(fascicolo, "stato", StatoFascicolo.DEFINITO)
        if hasattr(fascicolo, "data_chiusura") and not _text(getattr(fascicolo, "data_chiusura", "")):
            setattr(fascicolo, "data_chiusura", date.today().isoformat())
        if hasattr(fascicolo, "avanzamento"):
            avanzamento = list(getattr(fascicolo, "avanzamento", []) or [])
            avanzamento.append(
                AvanzamentoPratica(
                    data=datetime.now().isoformat(),
                    descrizione=f"Stato cambiato da {previous} a {StatoFascicolo.DEFINITO.value}",
                    stato_precedente=previous,
                    stato_nuovo=StatoFascicolo.DEFINITO.value,
                    note=note,
                    avvocato=_text(actor, "IUSENTRA"),
                )
            )
            setattr(fascicolo, "avanzamento", avanzamento)
        if hasattr(fascicolo, "modificato_il"):
            setattr(fascicolo, "modificato_il", datetime.now().isoformat())
    except Exception:
        return {"updated": False, "reason": "Aggiornamento stato non riuscito."}
    return {"updated": True, "status": "definito"}


def run_react_fascicoli_economic_presidio(
    *,
    get_fascicoli: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    actor: str = "IUSENTRA",
    limit: int = 500,
) -> dict[str, Any]:
    fascicoli_repository = get_fascicoli()
    fatturazione_repository = get_fatturazione()
    fascicoli = _safe("fascicoli_presidio_economico", lambda: list(fascicoli_repository.tutti(archiviati=True)), [])

    def presidio_priority(item: Any) -> tuple[int, int, str, str]:
        payments = getattr(item, "pagamenti", {}) or {}
        marker = _presidio_documentale_marker(payments)
        marker_status = _text(marker.get("status") or marker.get("stato")).casefold()
        is_current = _presidio_documentale_marker_is_current(item, payments)
        return (
            1 if is_current else 0,
            0 if marker_status == "stale" else 1,
            _text(marker.get("updated_at") or marker.get("updatedAt")),
            _text(getattr(item, "id", "")),
        )

    # Un limite di batch non deve bloccare per sempre i fascicoli in fondo
    # all'elenco: i documenti nuovi o mai analizzati vengono sempre per primi.
    fascicoli = sorted(fascicoli, key=presidio_priority)
    document_analysis_candidates = sum(
        1
        for fascicolo in fascicoli
        if not _presidio_documentale_marker_is_current(
            fascicolo,
            getattr(fascicolo, "pagamenti", {}) or {},
        )
    )
    created: list[dict[str, Any]] = []
    existing = 0
    missing_basis = 0
    skipped = 0
    processed = 0
    contributi_checked = 0
    contributi_updated = 0
    contributi_missing = 0
    document_analysis_updated = 0
    status_defined_updated = 0
    batch_save_payments = callable(getattr(fascicoli_repository, "_salva", None))
    payments_save_pending = False
    for fascicolo in fascicoli:
        if limit and contributi_checked >= limit:
            break
        contributi_checked += 1
        cu_result = _ensure_contributo_unificato_for_fascicolo(
            fascicoli_repository=fascicoli_repository,
            fascicolo=fascicolo,
            actor=actor,
            persist=not batch_save_payments,
        )
        cu_status = _text(cu_result.get("status"))
        if cu_status == "updated":
            contributi_updated += 1
        elif cu_status == "missing":
            contributi_missing += 1
        if cu_result.get("analysisUpdated"):
            document_analysis_updated += 1
            payments_save_pending = payments_save_pending or batch_save_payments
        status_result = _ensure_fascicolo_definito_from_economics(
            fascicoli_repository=fascicoli_repository,
            fascicolo=fascicolo,
            actor=actor,
            persist=not batch_save_payments,
        )
        if status_result.get("updated"):
            status_defined_updated += 1
            payments_save_pending = payments_save_pending or batch_save_payments
        if payments_save_pending and batch_save_payments and (
            cu_status == "updated"
            or status_result.get("updated")
            or document_analysis_updated % 25 == 0
        ):
            getattr(fascicoli_repository, "_salva")()
            payments_save_pending = False
        if not _fascicolo_is_defined(fascicolo):
            skipped += 1
            continue
        processed += 1
        result = _ensure_auto_proforma_for_fascicolo(
            fascicoli_repository=fascicoli_repository,
            fatturazione_repository=fatturazione_repository,
            fascicolo=fascicolo,
            actor=actor,
        )
        status = _text(result.get("status"))
        if status == "created":
            created.append({
                "fascicoloId": _text(getattr(fascicolo, "id", "")),
                "ref": _rg(fascicolo),
                "client": _fascicolo_client_label(fascicolo),
                **result,
            })
        elif status == "existing":
            existing += 1
        elif status == "missing_basis":
            missing_basis += 1
        else:
            skipped += 1
    if payments_save_pending and batch_save_payments:
        getattr(fascicoli_repository, "_salva")()
    document_analysis_pending = sum(
        1
        for fascicolo in fascicoli
        if not _presidio_documentale_marker_is_current(
            fascicolo,
            getattr(fascicolo, "pagamenti", {}) or {},
        )
    )
    return {
        "ok": True,
        "source": "repository_reali",
        "generatedAt": _now(),
        "message": (
            f"Presidio economico completato: {len(created)} bozze proforma create, "
            f"{existing} fascicoli già coperti, {missing_basis} da integrare con sentenza/importo, "
            f"{contributi_updated} contributi unificati consolidati, "
            f"{status_defined_updated} fascicoli definiti dal controllo economico."
        ),
        "created": created,
        "createdCount": len(created),
        "existingCount": existing,
        "missingBasisCount": missing_basis,
        "processedDefined": processed,
        "contributiCheckedCount": contributi_checked,
        "contributiUpdatedCount": contributi_updated,
        "contributiMissingCount": contributi_missing,
        "documentAnalysisUpdatedCount": document_analysis_updated,
        "documentAnalysisCandidateCount": document_analysis_candidates,
        "documentAnalysisPendingCount": document_analysis_pending,
        "statusDefinedUpdatedCount": status_defined_updated,
        "skippedCount": skipped,
    }


# Stati modificabili inline dall'elenco fascicoli: chiave = valore frontend
# (lowercase), valore = enum di dominio. "da_archiviare" e' derivato e non
# viene accettato come target diretto.
_INLINE_STATUS_TARGETS = {
    "aperto": StatoFascicolo.APERTO,
    "in_corso": StatoFascicolo.IN_CORSO,
    "sospeso": StatoFascicolo.SOSPESO,
    "definito": StatoFascicolo.DEFINITO,
    "archiviato": StatoFascicolo.ARCHIVIATO,
}

_INLINE_STATUS_LABELS = {
    "aperto": "Aperto",
    "in_corso": "In corso",
    "sospeso": "Sospeso",
    "definito": "Definito",
    "archiviato": "Archiviato",
}


def update_react_fascicolo_status(
    *,
    get_fascicoli: Callable[[], Any],
    id_fasc: str,
    payload: dict[str, Any],
    actor: str = "",
) -> tuple[dict[str, Any], int]:
    raw = _text(payload.get("stato") or payload.get("status")).strip().lower().replace(" ", "_")
    target = _INLINE_STATUS_TARGETS.get(raw)
    if target is None:
        return {
            "ok": False,
            "message": "Stato fascicolo non riconosciuto.",
            "errors": {"stato": "Stato fascicolo non riconosciuto."},
        }, 400
    repo = get_fascicoli()
    fascicolo = _resolve_fascicolo(repo, id_fasc)
    if not fascicolo:
        return {"ok": False, "message": "Fascicolo non trovato.", "errors": {"fascicolo": "Fascicolo non trovato."}}, 404
    fid = _text(getattr(fascicolo, "id", id_fasc))
    previous = _status_for_filters(fascicolo)
    if previous == raw:
        return {
            "ok": True,
            "message": f"Stato già impostato su {_INLINE_STATUS_LABELS[raw]}.",
            "fascicolo": {"id": fid, "status": raw, "tone": _status_tone(target.value)},
        }, 200
    try:
        if hasattr(repo, "cambia_stato"):
            fascicolo = repo.cambia_stato(
                fid,
                target,
                note="Aggiornato dall'elenco fascicoli",
                avvocato=_text(actor, "Operatore"),
            )
        else:
            setattr(fascicolo, "stato", target)
            saver = getattr(repo, "_salva", None)
            if callable(saver):
                saver()
    except Exception as exc:  # pragma: no cover - dipende dal repository concreto
        if has_app_context():
            current_app.logger.warning("Cambio stato fascicolo non completato per %s: %s", fid, exc)
        return {
            "ok": False,
            "message": "Cambio stato non riuscito. Controlla il fascicolo e riprova.",
            "errors": {"stato": "Cambio stato non riuscito."},
        }, 400
    return {
        "ok": True,
        "message": f"Stato aggiornato a {_INLINE_STATUS_LABELS[raw]}.",
        "fascicolo": {
            "id": fid,
            "status": _status_for_filters(fascicolo),
            "tone": _status_tone(target.value),
        },
    }, 200


def _bytes_label(value: Any) -> str:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return ""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} KB"
    return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")


def _status_tone(status: str) -> str:
    status = status.upper()
    if status == StatoFascicolo.IN_CORSO.value:
        return "success"
    if status == StatoFascicolo.DEFINITO.value:
        return "info"
    if status == StatoFascicolo.ARCHIVIATO.value:
        return "neutral"
    if status == StatoFascicolo.SOSPESO.value:
        return "orange"
    return "primary"


def _activity_tone(result: str) -> str:
    result = result.upper()
    if result == EsitoAttivita.FAVOREVOLE.value:
        return "success"
    if result == EsitoAttivita.PARZIALE.value:
        return "warning"
    if result == EsitoAttivita.SFAVOREVOLE.value:
        return "danger"
    if result == EsitoAttivita.RINVIATO.value:
        return "info"
    if result == EsitoAttivita.ANNULLATO.value:
        return "neutral"
    return "primary"


def _deadline_tone(scadenza: Any) -> str:
    priority = _enum_value(getattr(scadenza, "priorita", "")).upper()
    raw_date = _parse_date(getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "data", ""))
    if raw_date and raw_date <= date.today():
        return "danger"
    if "CRITICA" in priority:
        return "danger"
    if "ALTA" in priority:
        return "warning"
    if "BASSA" in priority:
        return "success"
    return "primary"


def _status_for_filters(fascicolo: Any) -> str:
    stato = _enum_value(getattr(fascicolo, "stato", "")).upper()
    if stato == StatoFascicolo.DEFINITO.value and bool(getattr(fascicolo, "archivio_pronto", False)):
        return "da_archiviare"
    return stato.lower()


def _type_for_filters(fascicolo: Any) -> str:
    return _enum_value(getattr(fascicolo, "tipo", "ALTRO")).lower()


def _option(value: Any) -> dict[str, str]:
    raw = _enum_value(value)
    return {"value": raw, "label": raw.replace("_", " ").title()}


def _options() -> dict[str, list[dict[str, str]]]:
    return {
        "states": [_option(item) for item in StatoFascicolo],
        "documentTypes": [_option(item) for item in TipoDocumento],
        "activityTypes": [_option(item) for item in TipoAttivita],
        "activityResults": [_option(item) for item in EsitoAttivita],
    }


def _select_options(values: Iterable[Any]) -> list[dict[str, str]]:
    return [_option(value) for value in values]


def _rg(fascicolo: Any) -> str:
    return _text(getattr(fascicolo, "rg_completo", "")) or _text(getattr(fascicolo, "numero_rg", "")) or "n.d."


def _rg_missing(fascicolo: Any) -> bool:
    numero = _first_int(getattr(fascicolo, "numero_rg", ""))
    anno = _first_int(getattr(fascicolo, "anno_rg", ""))
    if numero and anno:
        return False
    snapshot = getattr(fascicolo, "source_snapshot", None)
    if isinstance(snapshot, dict) and bool(snapshot.get("rg_missing")):
        return True
    source_external_id = _text(getattr(fascicolo, "source_external_id", ""))
    if source_external_id.startswith("quickorganizer:"):
        return True
    tipo = _type_for_filters(fascicolo)
    return tipo in {"civile", "penale", "amministrativo", "tributario", "lavoro"} and _status_for_filters(fascicolo) != "archiviato"


def _rg_status_label(fascicolo: Any) -> str:
    snapshot = getattr(fascicolo, "source_snapshot", None)
    if isinstance(snapshot, dict):
        action = _text(snapshot.get("rg_action"))
        if action:
            return action
    return "Acquisire il numero di ruolo dal portale o da un provvedimento del fascicolo."


def _rg_source_label(fascicolo: Any) -> str:
    snapshot = getattr(fascicolo, "source_snapshot", None)
    if isinstance(snapshot, dict):
        source = _text(snapshot.get("rg_source"))
        if source.startswith("AGENDA."):
            return "Manca anche nell'agenda importata"
        if source.startswith("PRATICHE."):
            return "Manca nei dati pratica importati"
        if source:
            return "Dato processuale assente"
    return "Dato processuale da completare"


def _rg_meta(fascicolo: Any) -> dict[str, Any]:
    missing = _rg_missing(fascicolo)
    raw = _rg(fascicolo)
    internal = _text(getattr(fascicolo, "numero", ""))
    if missing:
        return {
            "ref": "RG da acquisire",
            "rg": "Da acquisire",
            "rgMissing": True,
            "rgStatusLabel": _rg_status_label(fascicolo),
            "rgSourceLabel": _rg_source_label(fascicolo),
        }
    return {
        "ref": raw if raw != "n.d." else (internal or "n.d."),
        "rg": raw,
        "rgMissing": False,
        "rgStatusLabel": "",
        "rgSourceLabel": "",
    }


def _first_int(value: Any) -> int:
    match = re.search(r"\d+", _text(value))
    return int(match.group(0)) if match else 0


def _rg_order_from_fascicolo(fascicolo: Any) -> dict[str, int]:
    numero = _first_int(getattr(fascicolo, "numero_rg", ""))
    anno = _first_int(getattr(fascicolo, "anno_rg", ""))
    if numero and anno:
        return {"rgNumber": numero, "rgYear": anno}
    rg = _rg(fascicolo)
    if not anno:
        year_match = re.search(r"(?:19|20)\d{2}", rg)
        anno = int(year_match.group(0)) if year_match else 0
    if not numero:
        parts = rg.rsplit("/", 1)
        numero = _first_int(parts[0] if parts else rg)
    return {"rgNumber": numero, "rgYear": anno}


def _rg_order_from_item(item: dict[str, Any]) -> tuple[int, int, int, str, str]:
    anno = _first_int(item.get("rgYear") or item.get("annoRg") or item.get("anno_rg"))
    numero = _first_int(item.get("rgNumber") or item.get("numeroRg") or item.get("numero_rg"))
    if not anno or not numero:
        rg = _text(item.get("rg"))
        if not anno:
            year_match = re.search(r"(?:19|20)\d{2}", rg)
            anno = int(year_match.group(0)) if year_match else 0
        if not numero:
            parts = rg.rsplit("/", 1)
            numero = _first_int(parts[0] if parts else rg)
    missing = 0 if anno or numero else 1
    return (missing, -anno, -numero, _text(item.get("rg")).casefold(), _text(item.get("id")))


def _automatic_next_deadline_from_documents(fascicolo: Any) -> Any | None:
    deadline_documents = _document_candidates_for_hints(
        fascicolo,
        _document_may_contain_procedural_deadline,
        metadata_matcher=_document_metadata_may_contain_procedural_deadline,
    )
    texts = _document_ai_texts_for_fascicolo(fascicolo, documents=deadline_documents)
    if not texts:
        return None
    metadata_by_document = {document_id: _document_metadata_for_id(fascicolo, document_id) for document_id in texts}
    document_presidio = analyze_fascicolo_document_texts(fascicolo, texts, metadata_by_document)
    try:
        from pct.pec_pipeline import _procedural_date_kind, extract_procedural_dates
    except Exception:
        _procedural_date_kind = None
        extract_procedural_dates = None
    today = date.today()
    candidates: list[dict[str, Any]] = []
    principal_types = {"note_127_ter", "udienza_127_bis", "udienza_documento", "termine_documento"}
    for action in document_presidio.get("actions") or []:
        if _text(action.get("type")) not in principal_types:
            continue
        parsed = _parse_date(action.get("dateIso"))
        if not parsed or parsed < today:
            continue
        candidates.append(
            {
                "date": parsed,
                "kind": "udienza" if "udienza" in _text(action.get("type")) else "termine",
                "document_id": _text(action.get("documentId")),
                "source": _text(action.get("source"), "Documento fascicolo"),
                "label": _text(action.get("title"), "Data processuale"),
                "context": _short(action.get("description"), 220),
                "confidence": 0.99 if _text(action.get("type")) in {"note_127_ter", "udienza_127_bis"} else 0.82,
                "specific_title": _text(action.get("title")),
                "priority": "ALTA" if _text(action.get("priority")) in {"urgent", "important"} else "MEDIA",
            }
        )
    if extract_procedural_dates is None or _procedural_date_kind is None:
        if not candidates:
            return None
    else:
        for document_id, text in texts.items():
            metadata = metadata_by_document.get(document_id) or {}
            if not _document_may_contain_procedural_deadline(text, metadata):
                continue
            if not _document_text_matches_fascicolo(fascicolo, text):
                continue
            source_name = _text(metadata.get("filename") or metadata.get("safe_filename") or document_id, "Documento fascicolo")
            for candidate in extract_procedural_dates({source_name: text}, plain_text=""):
                kind = _procedural_date_kind(candidate)
                if kind not in {"udienza", "termine"}:
                    continue
                parsed = _parse_date(candidate.get("date"))
                if not parsed or parsed < today:
                    continue
                candidates.append(
                    {
                        "date": parsed,
                        "kind": kind,
                        "document_id": document_id,
                        "source": source_name,
                        "label": _text(candidate.get("label"), "Data processuale"),
                        "context": _short(candidate.get("context"), 220),
                        "confidence": float(candidate.get("confidence") or 0.0),
                        "specific_title": "",
                        "priority": "ALTA" if kind == "udienza" else "MEDIA",
                    }
                )
    if not candidates:
        return None
    best = sorted(candidates, key=lambda item: (item["date"], 0 if item["kind"] == "termine" else 1, -item["confidence"]))[0]
    title_prefix = "Udienza" if best["kind"] == "udienza" else "Termine"
    source = _text(best.get("source"), "documento fascicolo")
    return SimpleNamespace(
        id=f"document-ai-{_text(getattr(fascicolo, 'id', ''))}-{best['date'].isoformat()}",
        data_scadenza=best["date"].isoformat(),
        data=best["date"].isoformat(),
        tipo="UDIENZA" if best["kind"] == "udienza" else "ALTRO",
        priorita=_text(best.get("priority"), "ALTA" if best["kind"] == "udienza" else "MEDIA"),
        stato="APERTO",
        titolo=_short(_text(best.get("specific_title")) or f"{title_prefix} letta da {source}", 120),
        descrizione=_text(best.get("context")),
        note="Prossima scadenza letta automaticamente dai documenti indicizzati del fascicolo.",
        id_fascicolo=_text(getattr(fascicolo, "id", "")),
    )


def _document_presidio_for_fascicolo(fascicolo: Any, *, ensure_missing: bool = False) -> dict[str, Any]:
    deadline_documents = _document_candidates_for_hints(
        fascicolo,
        _document_may_contain_procedural_deadline,
        metadata_matcher=_document_metadata_may_contain_procedural_deadline,
    )
    texts = (
        _ensure_deadline_document_ai_texts_for_fascicolo(fascicolo, deadline_documents)
        if ensure_missing
        else _document_ai_texts_for_fascicolo(fascicolo, documents=deadline_documents)
    )
    if not texts:
        return {
            "status": "aggiornato",
            "tone": "success",
            "summary": "Documenti controllati: non risultano ulteriori decreti, udienze o termini processuali da presidiare.",
            "nextAction": None,
            "actions": [],
            "warnings": [],
            "sources": [],
        }
    metadata_by_document = {document_id: _document_metadata_for_id(fascicolo, document_id) for document_id in texts}
    return analyze_fascicolo_document_texts(fascicolo, texts, metadata_by_document)


def _next_deadline(
    fascicolo: Any,
    scadenze_by_fasc: dict[str, list[Any]] | None = None,
    *,
    automatic_from_documents: bool = False,
) -> Any | None:
    prop = getattr(fascicolo, "prossima_scadenza", None)
    if prop:
        return prop
    if scadenze_by_fasc is not None:
        deadlines = scadenze_by_fasc.get(_text(getattr(fascicolo, "id", "")), [])
        dated = [item for item in deadlines if _parse_date(getattr(item, "data_scadenza", "") or getattr(item, "data", ""))]
        dated.sort(key=lambda item: _parse_date(getattr(item, "data_scadenza", "") or getattr(item, "data", "")) or date.max)
        if dated:
            return dated[0]
    if automatic_from_documents:
        return _automatic_next_deadline_from_documents(fascicolo)
    return None


def _next_deadline_date_value(fascicolo: Any, next_deadline: Any | None) -> str:
    if next_deadline:
        return _text(getattr(next_deadline, "data_scadenza", "") or getattr(next_deadline, "data", ""))
    return _text(_next_hearing_value(fascicolo))


def _workspace_counts(fascicolo: Any) -> dict[str, int]:
    data = _safe("workspace_counts", lambda: build_fascicolo_workspace(fascicolo).get("counts", {}), {})
    return data if isinstance(data, dict) else {}


def _fast_documents_count(fascicolo: Any) -> int:
    source_snapshot = getattr(fascicolo, "source_snapshot", {}) or {}
    counts = source_snapshot.get("counts") if isinstance(source_snapshot, dict) else {}
    if isinstance(counts, dict):
        for key in ("documenti_governati", "documenti", "documents", "documenti_portale"):
            try:
                value = int(counts.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value:
                return value
    try:
        return len(getattr(fascicolo, "documenti", []) or [])
    except TypeError:
        return 0


def _governed_documents_count(fascicolo: Any) -> int:
    counts = _workspace_counts(fascicolo)
    value = counts.get("documenti_governati")
    if value is None:
        value = counts.get("documenti")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return len(getattr(fascicolo, "documenti", []) or [])


def _item(
    fascicolo: Any,
    *,
    scadenze_by_fasc: dict[str, list[Any]] | None = None,
    archived: bool | None = None,
    automatic_evidence: bool = False,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    stato = _enum_value(getattr(fascicolo, "stato", StatoFascicolo.APERTO.value))
    rg_order = _rg_order_from_fascicolo(fascicolo)
    n_scadenza = _next_deadline(fascicolo, scadenze_by_fasc, automatic_from_documents=automatic_evidence)
    n_date = _next_deadline_date_value(fascicolo, n_scadenza)
    docs = _governed_documents_count(fascicolo)
    deposits = getattr(fascicolo, "depositi_pct", []) or []
    unread = sum(1 for dep in deposits if _enum_value(getattr(dep, "stato", "")).upper() in {"WARN_CONTROLLI", "ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA", "ERRORE"})
    alerts = unread
    if getattr(fascicolo, "has_conflicts", False):
        alerts += 1
    if n_scadenza and _deadline_tone(n_scadenza) in {"danger", "warning"}:
        alerts += 1
    rg_meta = _rg_meta(fascicolo)
    if rg_meta["rgMissing"]:
        alerts += 1
    archive = getattr(fascicolo, "archivio", None)
    return {
        "id": fid,
        "ref": rg_meta["ref"],
        "internalRef": _text(getattr(fascicolo, "numero", "")),
        "title": _short(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo", 120),
        "subtitle": _short(getattr(fascicolo, "oggetto", ""), 160),
        "type": _type_for_filters(fascicolo),
        "client": _fascicolo_client_label(fascicolo),
        "court": _text(getattr(fascicolo, "tribunale", ""), "Ufficio non impostato"),
        "rg": rg_meta["rg"],
        "rgMissing": rg_meta["rgMissing"],
        "rgStatusLabel": rg_meta["rgStatusLabel"],
        "rgSourceLabel": rg_meta["rgSourceLabel"],
        **rg_order,
        "nextDeadline": _date_label(n_date) if n_date else "n.d.",
        "nextDeadlineIso": n_date,
        "status": "archiviato" if archived is True else _status_for_filters(fascicolo),
        "documents": docs,
        "fascicoloVeloce": bool(getattr(fascicolo, "fascicolo_veloce", False)),
        "documentiInizialiCount": int(getattr(fascicolo, "documenti_iniziali_count", 0) or 0),
        "emailInizialiCount": int(getattr(fascicolo, "email_iniziali_count", 0) or 0),
        "unreadCommunications": unread,
        "alerts": alerts,
        "openedAt": _text(getattr(fascicolo, "data_apertura", "")),
        "closedAt": _text(getattr(fascicolo, "data_chiusura", "")),
        "updatedAt": _text(getattr(fascicolo, "modificato_il", "")),
        "href": f"/fascicoli/{fid}",
        "operationalHref": f"/fascicoli/{fid}",
        "editHref": f"/fascicoli/{fid}/modifica",
        "operationalEditHref": f"/fascicoli/{fid}/modifica",
        "exportPdfHref": f"/fascicoli/{fid}/pdf",
        "deleteHref": f"/fascicoli/{fid}/elimina",
        "archiveZipHref": f"/fascicoli/{fid}/archivio/scarica",
        "restoreAction": f"/fascicoli/{fid}/ripristina",
        "tone": _status_tone(stato),
        "archive": {
            "outcome": _text(getattr(archive, "esito_finale", "")),
            "archivedAt": _text(getattr(archive, "data_archiviazione", "")),
            "reason": _text(getattr(archive, "motivo", "")),
            "notes": _italian_dates_in_text(getattr(archive, "note_archivio", "")),
            "zipAvailable": bool(_text(getattr(archive, "percorso_zip", ""))),
            "zipSize": _bytes_label(getattr(archive, "dimensione_zip", 0)),
            "hash": _text(getattr(archive, "hash_zip", "")),
        } if archive else None,
    }


def _item_light(
    fascicolo: Any,
    *,
    scadenze_by_fasc: dict[str, list[Any]] | None = None,
    archived: bool | None = None,
    office_pec_messages: list[Any] | None = None,
    automatic_evidence: bool = False,
    full_payment_summary: bool = True,
    related_fascicoli: Iterable[Any] | None = None,
    parcelle: Iterable[Any] | None = None,
    duplicate_group: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    stato = _enum_value(getattr(fascicolo, "stato", StatoFascicolo.APERTO.value))
    rg_order = _rg_order_from_fascicolo(fascicolo)
    n_scadenza = _next_deadline(fascicolo, scadenze_by_fasc, automatic_from_documents=automatic_evidence)
    n_date = _next_deadline_date_value(fascicolo, n_scadenza)
    deposits = getattr(fascicolo, "depositi_pct", []) or []
    unread = sum(1 for dep in deposits if _enum_value(getattr(dep, "stato", "")).upper() in {"WARN_CONTROLLI", "ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA", "ERRORE"})
    alerts = unread
    if getattr(fascicolo, "has_conflicts", False):
        alerts += 1
    if n_scadenza and _deadline_tone(n_scadenza) in {"danger", "warning"}:
        alerts += 1
    rg_meta = _rg_meta(fascicolo)
    if rg_meta["rgMissing"]:
        alerts += 1
    if full_payment_summary:
        payment_summary = payment_summary_for_fascicolo(
            fascicolo,
            automatic=automatic_evidence,
            related_fascicoli=related_fascicoli,
            parcelle=parcelle,
            duplicate_group=duplicate_group,
        )
    else:
        payment_summary = payment_summary_for_fascicolo_fast(
            fascicolo,
            related_fascicoli=related_fascicoli,
            parcelle=parcelle,
            duplicate_group=duplicate_group,
        )
    relata_summary: dict[str, Any] = {}
    if office_pec_messages is not None:
        fid_for_relata = quote(fid)
        pec_evidence = office_notification_evidence_from_pec(fascicolo, office_pec_messages)
        pending_releases = [item for item in pec_evidence if not item.get("acquisito")]
        acquired_releases = [item for item in pec_evidence if item.get("acquisito")]
        if pending_releases:
            first_release = pending_releases[0]
            relata_summary = {
                "relataStatus": "da_acquisire",
                "relataStatusLabel": "Provvedimento da scaricare dal portale",
                "relataTone": "warning",
                "relataHref": f"/fascicoli/{fid_for_relata}#relata-notifica",
                "relataPrimaryHref": _text(first_release.get("acquisitionHref")) or f"/fascicoli/{fid_for_relata}#relata-notifica",
                "relataPrimaryLabel": "Scarica dal portale",
                "relataReleaseDetected": True,
                "relataCount": len(pending_releases),
            }
        elif acquired_releases:
            relata_summary = {
                "relataStatus": "da_preparare",
                "relataStatusLabel": "Relata da preparare",
                "relataTone": "warning",
                "relataHref": f"/fascicoli/{fid_for_relata}#relata-notifica",
                "relataPrimaryHref": f"/notifiche-legali?id_fascicolo={fid_for_relata}&fase=notifica#notifica",
                "relataPrimaryLabel": "Prepara relata",
                "relataReleaseDetected": False,
                "relataCount": len(acquired_releases),
            }
    return {
        "id": fid,
        "ref": rg_meta["ref"],
        "internalRef": _text(getattr(fascicolo, "numero", "")),
        "title": _short(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo", 120),
        "subtitle": _short(getattr(fascicolo, "oggetto", ""), 160),
        "type": _type_for_filters(fascicolo),
        "client": _fascicolo_client_label(fascicolo),
        "court": _text(getattr(fascicolo, "tribunale", ""), "Ufficio non impostato"),
        "rg": rg_meta["rg"],
        "rgMissing": rg_meta["rgMissing"],
        "rgStatusLabel": rg_meta["rgStatusLabel"],
        "rgSourceLabel": rg_meta["rgSourceLabel"],
        **rg_order,
        "nextDeadline": _date_label(n_date) if n_date else "n.d.",
        "nextDeadlineIso": n_date,
        "status": "archiviato" if archived is True else _status_for_filters(fascicolo),
        "documents": _fast_documents_count(fascicolo),
        "unreadCommunications": unread,
        "alerts": alerts,
        "paymentSummary": payment_summary,
        "openedAt": _text(getattr(fascicolo, "data_apertura", "")),
        "closedAt": _text(getattr(fascicolo, "data_chiusura", "")),
        "updatedAt": _text(getattr(fascicolo, "modificato_il", "")),
        "href": f"/fascicoli/{fid}",
        "operationalHref": f"/fascicoli/{fid}",
        "editHref": f"/fascicoli/{fid}/modifica",
        "operationalEditHref": f"/fascicoli/{fid}/modifica",
        "exportPdfHref": f"/fascicoli/{fid}/pdf",
        "deleteHref": f"/fascicoli/{fid}/elimina",
        "archiveZipHref": f"/fascicoli/{fid}/archivio/scarica",
        "restoreAction": f"/fascicoli/{fid}/ripristina",
        "tone": _status_tone(stato),
        **relata_summary,
    }


def _annotate_duplicate_items(items: list[dict[str, Any]], groups_by_key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        key = normalise_practice_duplicate_key(item)
        group = groups_by_key.get(key) if key else None
        if not group:
            out.append(
                {
                    **item,
                    "duplicateCount": 0,
                    "duplicateIds": [],
                    "duplicateKey": "",
                    "duplicateLabel": "",
                    "duplicateHref": "",
                }
            )
            continue
        ids = [_text(value) for value in group.get("ids") or [] if _text(value)]
        out.append(
            {
                **item,
                "duplicateCount": int(group.get("count") or len(ids) or 0),
                "duplicateIds": ids,
                "duplicateKey": _text(group.get("key")),
                "duplicateLabel": _text(group.get("label")),
                "duplicateHref": f"/fascicoli?rg={quote(_text(item.get('rg')), safe='')}",
            }
        )
    return out


def _duplicate_group_for_fascicolo(fascicoli: Iterable[Any], fascicolo: Any) -> dict[str, Any] | None:
    key = normalise_practice_duplicate_key(fascicolo)
    if not key:
        return None
    groups = {str(item.get("key") or ""): item for item in duplicate_practice_groups(fascicoli)}
    group = groups.get(key)
    if not group:
        return None
    rg = _text(normalise_practice_duplicate_key(fascicolo))
    href_ref = _rg(fascicolo)
    return {
        **group,
        "href": f"/fascicoli?rg={quote(href_ref, safe='')}" if href_ref and href_ref != "n.d." else "/fascicoli",
        "identity": rg,
    }


def _group_scadenze_by_fasc(rows: Iterable[Any], fascicoli: Iterable[Any] | None = None) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    fascicoli_list = list(fascicoli or [])
    alias_index, by_rg, known_ids = _fascicolo_alias_index(fascicoli_list) if fascicoli_list else ({}, {}, set())
    for item in rows:
        fid = _text(getattr(item, "id_fascicolo", ""))
        if not fascicoli_list:
            if fid:
                grouped.setdefault(fid, []).append(item)
            continue
        target_ids = _resolve_scadenza_fascicolo_ids(
            item,
            alias_index=alias_index,
            by_rg=by_rg,
            known_ids=known_ids,
        )
        if not target_ids and fid:
            target_ids = {fid}
        for target_id in sorted(target_ids):
            if target_id:
                grouped.setdefault(target_id, []).append(item)
    return grouped


def _resolved_scadenze_fascicolo_ids(grouped: dict[str, list[Any]]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for fid, rows in grouped.items():
        for item in rows:
            sid = _text(getattr(item, "id", ""))
            if sid and fid:
                resolved.setdefault(sid, fid)
    return resolved


def _resolved_scadenza_fascicolo_id(scadenza: Any, resolved_ids: dict[str, str] | None = None) -> str:
    sid = _text(getattr(scadenza, "id", ""))
    if resolved_ids and sid:
        resolved = _text(resolved_ids.get(sid, ""))
        if resolved:
            return resolved
    return _text(getattr(scadenza, "id_fascicolo", ""))


def _open_scadenze(get_scadenziario: Callable[[], Any]) -> list[Any]:
    return list(_safe("scadenziario", lambda: get_scadenziario().tutte(solo_aperte=True), []))


def _all_scadenze_by_fasc(get_scadenziario: Callable[[], Any], fascicoli: Iterable[Any] | None = None) -> dict[str, list[Any]]:
    return _group_scadenze_by_fasc(_open_scadenze(get_scadenziario), fascicoli)


def _summary(items: list[dict[str, Any]], archived_count: int = 0, deadlines30: int = 0) -> dict[str, Any]:
    economic_to_review = sum(1 for item in items if (item.get("paymentSummary") or {}).get("stato") in {"da_presidiare", "parziale"})
    economic_analysis_due = sum(
        1
        for item in items
        if ((item.get("paymentSummary") or {}).get("analysis") or {}).get("status") in {"da_analizzare", "da_rianalizzare"}
    )
    invoices_to_issue = sum(int((item.get("paymentSummary") or {}).get("parcelleDaEmettere") or 0) for item in items)
    invoice_drafts_to_review = sum(
        int(((item.get("paymentSummary") or {}).get("proformaPresidio") or {}).get("existingDraftCount") or 0)
        for item in items
    )
    invoices_present = sum(
        int(((item.get("paymentSummary") or {}).get("proformaPresidio") or {}).get("existingCount") or 0)
        for item in items
    )
    registered_amount = round(sum(float((item.get("paymentSummary") or {}).get("totaleRegistrato") or 0.0) for item in items), 2)
    advances_to_recover = round(sum(float((item.get("paymentSummary") or {}).get("anticipazioniDaRecuperare") or 0.0) for item in items), 2)
    duplicate_keys = {_text(item.get("duplicateKey")) for item in items if int(item.get("duplicateCount") or 0) > 1 and _text(item.get("duplicateKey"))}
    today = date.today()
    soon_limit = today + timedelta(days=7)
    return {
        "total": len(items) + archived_count,
        "active": sum(1 for item in items if item["status"] != "archiviato"),
        "inProgress": sum(1 for item in items if item["status"] == "in_corso"),
        "toArchive": sum(1 for item in items if item["status"] in {"definito", "da_archiviare"}),
        "archived": archived_count + sum(1 for item in items if item["status"] == "archiviato"),
        "suspended": sum(1 for item in items if item["status"] == "sospeso"),
        "deadlines7": sum(
            1
            for item in items
            if (parsed := _parse_date(item.get("nextDeadlineIso", ""))) and today <= parsed <= soon_limit
        ),
        "deadlines30": deadlines30,
        "documents": sum(int(item.get("documents") or 0) for item in items),
        "documentsToClassify": sum(int(item.get("alerts") or 0) for item in items),
        "unreadCommunications": sum(int(item.get("unreadCommunications") or 0) for item in items),
        "missingRg": sum(1 for item in items if item.get("rgMissing")),
        "economicToReview": economic_to_review,
        "economicAnalysisDue": economic_analysis_due,
        "invoicesToIssue": invoices_to_issue,
        "invoiceDraftsToReview": invoice_drafts_to_review,
        "invoicesPresent": invoices_present,
        "invoiceWorkTotal": invoices_to_issue + invoice_drafts_to_review,
        "registeredAmount": registered_amount,
        "advancesToRecover": advances_to_recover,
        "duplicatePractices": len(duplicate_keys),
        "duplicatePracticeRows": sum(1 for item in items if int(item.get("duplicateCount") or 0) > 1),
    }


def _facets(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    types = Counter(item["type"] for item in items)
    statuses = Counter(item["status"] for item in items)
    type_labels = {
        "civile": "Civile",
        "penale": "Penale",
        "amministrativo": "Amministrativo",
        "tributario": "Tributario",
        "stragiudiziale": "Stragiudiziale",
        "consulenza": "Consulenza",
        "lavoro": "Lavoro",
        "famiglia": "Famiglia",
        "successioni": "Successioni",
        "altro": "Altro",
    }
    status_labels = {
        "aperto": "Aperto",
        "in_corso": "In corso",
        "definito": "Definito",
        "da_archiviare": "Da archiviare",
        "archiviato": "Archiviato",
        "sospeso": "Sospeso",
    }
    return {
        "types": [{"value": "tutti", "label": "Tutti i tipi", "count": len(items)}]
        + [{"value": value, "label": label, "count": types.get(value, 0)} for value, label in type_labels.items()],
        "statuses": [{"value": "tutti", "label": "Tutti gli stati", "count": len(items)}]
        + [{"value": value, "label": label, "count": statuses.get(value, 0)} for value, label in status_labels.items()],
    }


def _deadline_rows_from_scadenze(
    scadenze: Iterable[Any],
    items_by_id: dict[str, dict[str, Any]],
    days: int = 7,
    *,
    resolved_matter_ids: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    horizon = date.today() + timedelta(days=days)
    out: list[dict[str, Any]] = []
    for scadenza in scadenze:
        due = _parse_date(getattr(scadenza, "data_scadenza", "") or getattr(scadenza, "data", ""))
        if not due or due > horizon:
            continue
        fid = _resolved_scadenza_fascicolo_id(scadenza, resolved_matter_ids)
        matter = items_by_id.get(fid, {})
        out.append(
            {
                "id": _text(getattr(scadenza, "id", ""), f"deadline-{len(out)}"),
                "matterId": fid,
                "matterRef": matter.get("ref") or fid,
                "title": _short(getattr(scadenza, "titolo", "") or "Scadenza", 100),
                "date": _date_label(due),
                "dateIso": due.isoformat(),
                "href": f"/scadenziario?id_fascicolo={fid}" if fid else "/scadenziario",
                "tone": _deadline_tone(scadenza),
            }
        )
    return sorted(out, key=lambda item: item["dateIso"])


def _deadline_rows(get_scadenziario: Callable[[], Any], items_by_id: dict[str, dict[str, Any]], days: int = 7) -> list[dict[str, Any]]:
    return _deadline_rows_from_scadenze(_open_scadenze(get_scadenziario), items_by_id, days=days)


def _contracts() -> dict[str, Any]:
    return {"mock_fallback": False, "read_only": True, "writes": "operational_routes"}


def _list_actions() -> dict[str, str]:
    return {
        "list": "/fascicoli",
        "new": "/fascicoli/nuovo",
        "archive": "/fascicoli/archivio",
        "exportCsv": "/fascicoli/export.csv",
    }


def _positive_int(value: Any, default: int, *, minimum: int = 1, maximum: int = 200) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _matches_list_filters(
    item: dict[str, Any],
    *,
    query: str = "",
    client_filter: str = "",
    rg_filter: str = "",
    type_filter: str = "",
    status_filter: str = "",
    court: str = "",
    alerts_only: bool = False,
    payments_only: bool = False,
    missing_rg_only: bool = False,
    duplicates_only: bool = False,
    payment_filters: dict[str, str] | None = None,
) -> bool:
    needle = _text(query).lower()
    if needle:
        haystack = " ".join(
            _text(item.get(key)).lower()
            for key in ("ref", "internalRef", "title", "subtitle", "client", "court", "rg", "rgStatusLabel", "rgSourceLabel")
        )
        if needle not in haystack:
            return False
    client_needle = _text(client_filter).lower()
    if client_needle and client_needle not in _text(item.get("client")).lower():
        return False
    rg_needle = _text(rg_filter).lower()
    if rg_needle:
        rg_haystack = " ".join(
            _text(value).lower()
            for value in (item.get("rg"), item.get("ref"), item.get("rgNumber"), item.get("rgYear"), item.get("rgStatusLabel"))
        )
        if rg_needle not in rg_haystack:
            return False
    type_key = _text(type_filter).lower()
    if type_key and type_key != "tutti" and _text(item.get("type")).lower() != type_key:
        return False
    status_key = _text(status_filter).lower()
    if status_key and status_key != "tutti" and _text(item.get("status")).lower() != status_key:
        return False
    court_needle = _text(court).lower()
    if court_needle and court_needle not in _text(item.get("court")).lower():
        return False
    if alerts_only and not (int(item.get("alerts") or 0) or int(item.get("unreadCommunications") or 0)):
        return False
    if payments_only and (item.get("paymentSummary") or {}).get("stato") not in {"da_presidiare", "parziale"}:
        return False
    if missing_rg_only and not bool(item.get("rgMissing")):
        return False
    if duplicates_only and int(item.get("duplicateCount") or 0) <= 1:
        return False
    if payment_filters:
        payment_summary = item.get("paymentSummary") or {}
        summary_items = payment_summary.get("items") or {}
        for kind, wanted in payment_filters.items():
            wanted_key = _text(wanted).strip().lower()
            if not wanted_key or wanted_key == "tutti":
                continue
            normalized_kind = _normalise_payment_kind(kind) or kind
            if normalized_kind == "parcella" and wanted_key == "da_emettere":
                proforma = payment_summary.get("proformaPresidio") or {}
                if (
                    int(payment_summary.get("parcelleDaEmettere") or 0) <= 0
                    and int(proforma.get("existingDraftCount") or 0) <= 0
                ):
                    return False
                continue
            actual = _text((summary_items.get(normalized_kind) or {}).get("status")).strip().lower()
            if actual != wanted_key:
                return False
    return True


def _sort_list_items(items: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    key = _text(sort, "rg")
    if key == "rg":
        return sorted(items, key=_rg_order_from_item)
    if key == "cliente":
        return sorted(items, key=lambda item: (_text(item.get("client")).lower(), _text(item.get("title")).lower(), _text(item.get("id"))))
    if key == "scadenza":
        return sorted(items, key=lambda item: (_text(item.get("nextDeadlineIso")) or "9999-12-31", _text(item.get("id"))))
    if key == "documenti":
        return sorted(items, key=lambda item: (-int(item.get("documents") or 0), _text(item.get("title")).lower(), _text(item.get("id"))))
    return sorted(items, key=lambda item: (_text(item.get("updatedAt")) or _text(item.get("openedAt")) or "", _text(item.get("id"))), reverse=True)


def _pagination(page: int, page_size: int, total: int) -> dict[str, int]:
    pages = (total + page_size - 1) // page_size if total else 0
    current = min(max(1, page), max(1, pages))
    return {"page": current, "pageSize": page_size, "total": total, "pages": pages}


def build_react_fascicoli_payload(
    *,
    get_fascicoli: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_fatturazione: Callable[[], Any] | None = None,
    page: int = 1,
    page_size: int = 5,
    query: str = "",
    client_filter: str = "",
    rg_filter: str = "",
    type_filter: str = "",
    status_filter: str = "",
    court: str = "",
    sort: str = "rg",
    view: str = "",
    alerts_only: bool = False,
    payments_only: bool = False,
    missing_rg_only: bool = False,
    duplicates_only: bool = False,
    payment_filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    payment_filters_active = bool(
        payment_filters
        and any(_text(value).strip().lower() not in {"", "tutti"} for value in payment_filters.values())
    )
    sort_key = _text(sort, "rg")
    automatic_for_all = bool(
        payments_only
        or payment_filters_active
        or sort_key == "scadenza"
    )
    base_cache_key = _fascicoli_base_cache_key(
        query=query,
        client_filter=client_filter,
        rg_filter=rg_filter,
        type_filter=type_filter,
        status_filter=status_filter,
        court=court,
        sort=sort,
        view=view,
        alerts_only=alerts_only,
        payments_only=payments_only,
        missing_rg_only=missing_rg_only,
        duplicates_only=duplicates_only,
        payment_filters=payment_filters,
    )
    base = _fascicoli_base_cache_get(base_cache_key)
    if base is None:
        gf = get_fascicoli()
        scadenze_rows = _open_scadenze(get_scadenziario)
        fascicoli = _safe("fascicoli", lambda: gf.tutti(archiviati=False), [])
        scadenze_by_fasc = _group_scadenze_by_fasc(scadenze_rows, fascicoli)
        resolved_scadenze = _resolved_scadenze_fascicolo_ids(scadenze_by_fasc)
        archived = _safe("fascicoli_archivio", lambda: gf.tutti(stato=StatoFascicolo.ARCHIVIATO, archiviati=True), [])
        duplicate_groups = duplicate_practice_groups(fascicoli)
        duplicate_groups_by_key = {_text(group.get("key")): group for group in duplicate_groups if _text(group.get("key"))}
        parcelle_by_fasc = _parcelle_by_fascicolo(get_fatturazione)

        def _related_for_list_row(fascicolo: Any) -> list[Any]:
            return _related_duplicate_fascicoli(fascicoli, fascicolo)

        light_items = _annotate_duplicate_items(
            [
                _item_light(
                    fascicolo,
                    scadenze_by_fasc=scadenze_by_fasc,
                    automatic_evidence=automatic_for_all,
                    full_payment_summary=False,
                    related_fascicoli=_related_for_list_row(fascicolo) if automatic_for_all else None,
                    parcelle=parcelle_by_fasc.get(_text(getattr(fascicolo, "id", "")), []),
                    duplicate_group=duplicate_groups_by_key.get(normalise_practice_duplicate_key(fascicolo)),
                )
                for fascicolo in fascicoli
            ],
            duplicate_groups_by_key,
        )
        filtered = [
            item for item in light_items
            if _matches_list_filters(
                item,
                query=query,
                client_filter=client_filter,
                rg_filter=rg_filter,
                type_filter=type_filter,
                status_filter=status_filter,
                court=court,
                alerts_only=alerts_only,
                payments_only=payments_only,
                missing_rg_only=missing_rg_only,
                duplicates_only=duplicates_only,
                payment_filters=payment_filters,
            )
        ]
        sorted_items = _sort_list_items(filtered, sort)
        items_by_id = {item["id"]: item for item in light_items}
        base = {
            "items": sorted_items,
            "lightItems": light_items,
            "archivedCount": len(archived),
            "deadlines30": len(
                _deadline_rows_from_scadenze(
                    scadenze_rows,
                    items_by_id,
                    days=30,
                    resolved_matter_ids=resolved_scadenze,
                )
            ),
            "deadlines7": _deadline_rows_from_scadenze(
                scadenze_rows,
                items_by_id,
                days=7,
                resolved_matter_ids=resolved_scadenze,
            ),
        }
        _fascicoli_base_cache_set(base_cache_key, base)
    sorted_items = list(base.get("items") or [])
    light_items = list(base.get("lightItems") or [])
    page_size = _positive_int(page_size, 5, maximum=100)
    page = _positive_int(page, 1, maximum=100000)
    pagination = _pagination(page, page_size, len(sorted_items))
    start = (pagination["page"] - 1) * page_size
    items = sorted_items[start:start + page_size]
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "summary": _summary(sorted_items, archived_count=int(base.get("archivedCount") or 0), deadlines30=int(base.get("deadlines30") or 0)),
        "items": items,
        "pagination": pagination,
        "facets": _facets(light_items),
        "deadlines": list(base.get("deadlines7") or []),
        "actions": _list_actions(),
    }


def build_react_archivio_payload(*, get_fascicoli: Callable[[], Any], get_scadenziario: Callable[[], Any], query: str = "") -> dict[str, Any]:
    gf = get_fascicoli()
    if query:
        fascicoli = _safe("archivio", lambda: gf.cerca(testo=query, stato=StatoFascicolo.ARCHIVIATO, archiviati=True), [])
    else:
        fascicoli = _safe("archivio", lambda: gf.tutti(stato=StatoFascicolo.ARCHIVIATO, archiviati=True), [])
    scadenze_by_fasc = _all_scadenze_by_fasc(get_scadenziario, fascicoli)
    items = _sort_list_items([_item(fascicolo, scadenze_by_fasc=scadenze_by_fasc, archived=True) for fascicolo in fascicoli], "rg")
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "summary": _summary(items, archived_count=0, deadlines30=0),
        "items": items,
        "facets": _facets(items),
        "deadlines": [],
        "actions": _list_actions(),
    }


def _client_label(cliente: Any) -> str:
    return _text(getattr(cliente, "nome_completo", "")) or _text(getattr(cliente, "ragione_sociale", "")) or _text(getattr(cliente, "cognome", "")) or "Cliente"


def _client_options(get_clienti: Callable[[], Any]) -> list[dict[str, str]]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(stato=None), [])
    out = []
    for cliente in clienti:
        recapiti = getattr(cliente, "recapiti", None)
        out.append(
            {
                "id": _text(getattr(cliente, "id", "")),
                "label": _client_label(cliente),
                "taxCode": _text(getattr(cliente, "codice_fiscale", "")),
                "vat": _text(getattr(cliente, "partita_iva", "")),
                "email": _text(getattr(recapiti, "email", "") or getattr(cliente, "email", "")),
                "pec": _text(getattr(recapiti, "pec", "") or getattr(cliente, "pec", "")),
                "phone": _text(getattr(recapiti, "telefono", "") or getattr(recapiti, "cellulare", "") or getattr(cliente, "telefono", "")),
                "type": _enum_value(getattr(cliente, "tipo", "")),
                "href": f"/clienti/{_text(getattr(cliente, 'id', ''))}",
            }
        )
    return out


def _soggetto_label(soggetto: Any) -> str:
    return _text(getattr(soggetto, "nome_completo", "")) or "Soggetto"


def _subject_options(get_soggetti: Callable[[], Any] | None) -> list[dict[str, str]]:
    if not callable(get_soggetti):
        return []
    soggetti = _safe("soggetti", lambda: get_soggetti().tutti(), [])
    out: list[dict[str, str]] = []
    for soggetto in soggetti:
        recapiti = getattr(soggetto, "recapiti", None)
        identificativo = _text(getattr(soggetto, "identificativo", ""))
        out.append(
            {
                "id": _text(getattr(soggetto, "id", "")),
                "label": _soggetto_label(soggetto),
                "taxCode": _text(getattr(soggetto, "codice_fiscale", "")) or identificativo,
                "vat": _text(getattr(soggetto, "partita_iva", "")),
                "email": _text(getattr(recapiti, "email", "")),
                "pec": _text(getattr(recapiti, "pec", "")),
                "phone": _text(getattr(recapiti, "telefono", "") or getattr(recapiti, "cellulare", "")),
                "type": _enum_value(getattr(soggetto, "tipo", "")),
                "qualification": _text(getattr(soggetto, "qualifica", "")),
                "href": f"/soggetti/{_text(getattr(soggetto, 'id', ''))}",
            }
        )
    return sorted((row for row in out if row["id"]), key=lambda row: row["label"].casefold())


def _uffici_cache_path() -> str:
    configured = _text(os.getenv("PCT_UFFICI_DB", ""))
    if configured:
        return configured
    repo_data = Path(__file__).resolve().parents[2] / "data" / "uffici" / "uffici_giudiziari.json"
    if repo_data.exists():
        return str(repo_data)
    return "/data/uffici/uffici_giudiziari.json"


def _judicial_office_options() -> list[dict[str, Any]]:
    try:
        from pct.uffici_giudiziari import TIPI_UFFICIO, get_gestore

        uffici = get_gestore(_uffici_cache_path()).carica()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for ufficio in uffici:
        nome = _text(ufficio.get("nome"))
        if not nome:
            continue
        tipo = _text(ufficio.get("tipo"))
        tipo_label = _text((TIPI_UFFICIO.get(tipo) or ("", tipo))[1], tipo)
        distretto = _text(ufficio.get("distretto"))
        label_parts = [nome]
        if tipo_label and tipo_label.casefold() not in nome.casefold():
            label_parts.append(tipo_label)
        if distretto and distretto.casefold() not in nome.casefold():
            label_parts.append(distretto)
        out.append(
            {
                "value": nome,
                "label": " - ".join(label_parts),
                "code": _text(ufficio.get("codice")),
                "ministerialCode": _text(ufficio.get("codice_ministero")),
                "district": distretto,
                "pec": _text(ufficio.get("pec") or ufficio.get("pec_ministero")),
                "kind": tipo_label,
                "services": [
                    _text(servizio)
                    for servizio in (ufficio.get("servizi_ministero") or [])
                    if _text(servizio)
                ],
            }
        )
    return sorted(out, key=lambda row: (str(row.get("kind", "")).casefold(), str(row.get("label", "")).casefold()))


def _deposit_office_payload(fascicolo: Any) -> dict[str, Any]:
    office_name = _text(getattr(fascicolo, "tribunale", ""))
    base = {
        "name": office_name,
        "code": "",
        "ministerialCode": "",
        "district": "",
        "pec": "",
        "kind": "",
        "verified": False,
        "message": "IUSENTRA deve risolvere automaticamente PEC e codice ufficio prima del deposito.",
    }
    if not office_name:
        return {
            **base,
            "message": "Ufficio giudiziario non impostato nella pratica: IUSENTRA non può risolvere automaticamente PEC e codice ufficio.",
        }

    profile = getattr(fascicolo, "profilo_deposito", None)
    if not isinstance(profile, dict):
        raw_profile = _text(getattr(fascicolo, "profilo_deposito_json", ""))
        if raw_profile:
            try:
                parsed_profile = json.loads(raw_profile)
                profile = parsed_profile if isinstance(parsed_profile, dict) else {}
            except Exception:
                profile = {}
        else:
            profile = {}

    profile_office = profile.get("ufficio") if isinstance(profile, dict) else {}
    profile_name = office_name
    profile_pec = ""
    profile_code = ""
    profile_ministerial_code = ""
    profile_district = ""
    profile_kind = ""
    profile_verified = False
    if isinstance(profile_office, dict):
        profile_name = _text(profile_office.get("nome"), office_name)
        profile_pec = _text(profile_office.get("pec") or profile.get("pec"))
        profile_code = _text(
            profile_office.get("codice_iusentra")
            or profile_office.get("codice")
            or profile_office.get("codice_ufficio")
        )
        profile_ministerial_code = _text(
            profile_office.get("codice_ministero")
            or profile_office.get("codice_pst")
            or profile_office.get("codice_ministeriale")
        )
        profile_district = _text(profile_office.get("distretto"))
        profile_kind = _text(profile_office.get("tipo"))
        profile_verified = bool(
            profile_pec
            and (profile_code or profile_ministerial_code)
            and (profile_office.get("pec_verificata") is True or profile.get("pec_verificata") is True)
        )
    profile_complete = bool(profile_pec and (profile_code or profile_ministerial_code))

    try:
        from pct.uffici_giudiziari import TIPI_UFFICIO, get_gestore, risolvi_ufficio

        offices = get_gestore(_uffici_cache_path()).carica()
    except Exception:
        if profile_complete:
            return {
                "name": profile_name,
                "code": profile_code,
                "ministerialCode": profile_ministerial_code,
                "district": profile_district,
                "pec": profile_pec,
                "kind": profile_kind,
                "verified": profile_verified,
                "message": (
                    f"PEC e codice ufficio presenti nel profilo deposito per {profile_name}."
                    if profile_verified
                    else f"PEC e codice ufficio presenti nel profilo deposito per {profile_name}: la prova controlla il certificato dell'ufficio."
                ),
            }
        return {
            **base,
            "message": "Catalogo uffici non disponibile: IUSENTRA non ha potuto risolvere automaticamente PEC e codice ufficio.",
        }

    wanted_terms = [
        profile_name,
        office_name,
        profile_code,
        profile_ministerial_code,
        profile_pec,
    ]
    wanted_terms = [_text(term).casefold() for term in wanted_terms if _text(term)]

    def _office_field_values(row: dict[str, Any]) -> tuple[str, ...]:
        return (
            _text(row.get("nome")).casefold(),
            _text(row.get("codice")).casefold(),
            _text(row.get("codice_ministero")).casefold(),
            _text(row.get("pec")).casefold(),
            _text(row.get("pec_ministero")).casefold(),
        )

    office = None
    for term in wanted_terms:
        try:
            office = risolvi_ufficio(term, cache_path=_uffici_cache_path())
        except Exception:
            office = None
        if office is not None:
            break

    if office is None:
        office = next(
        (row for row in offices if any(term in _office_field_values(row) for term in wanted_terms)),
        None,
        )
    if office is None:
        name_terms = [term for term in wanted_terms[:2] if term]
        office = next(
            (
                row
                for row in offices
                if any(term in _text(row.get("nome")).casefold() for term in name_terms)
            ),
            None,
        )
    if office is None and not profile_complete:
        return {
            **base,
            "message": f"IUSENTRA non ha trovato '{office_name}' nel catalogo uffici: aggiorna il catalogo o correggi l'ufficio della pratica.",
        }
    if office is None and profile_complete:
        return {
            "name": profile_name,
            "code": profile_code,
            "ministerialCode": profile_ministerial_code,
            "district": profile_district,
            "pec": profile_pec,
            "kind": profile_kind,
            "verified": profile_verified,
            "message": (
                f"PEC e codice ufficio presenti nel profilo deposito per {profile_name}."
                if profile_verified
                else f"PEC e codice ufficio presenti nel profilo deposito per {profile_name}: la prova controlla il certificato dell'ufficio."
            ),
        }

    office_type = _text(office.get("tipo"))
    kind = _text((TIPI_UFFICIO.get(office_type) or ("", office_type))[1], office_type)
    pec = _text(profile_pec or office.get("pec") or office.get("pec_ministero"))
    catalog_name = _text(office.get("nome"), office_name)
    name = profile_name if profile_name and profile_name.casefold() != office_name.casefold() else catalog_name
    code = _text(profile_code or office.get("codice"))
    ministerial_code = _text(profile_ministerial_code or office.get("codice_ministero"))
    resolved = bool(pec and (code or ministerial_code))
    completed_from_catalog = bool(
        office
        and (
            (not profile_pec and pec)
            or (not profile_code and code)
            or (not profile_ministerial_code and ministerial_code)
        )
    )
    return {
        "name": name,
        "code": code,
        "ministerialCode": ministerial_code,
        "district": profile_district or _text(office.get("distretto")),
        "pec": pec,
        "kind": profile_kind or kind,
        "verified": resolved,
        "message": (
            f"PEC e codice ufficio risolti automaticamente dal catalogo uffici per {name}."
            if completed_from_catalog or resolved
            else f"IUSENTRA non ha risolto automaticamente PEC e codice ufficio per {name}: aggiorna il catalogo uffici o correggi l'ufficio della pratica."
        ),
    }


def _codice_oggetto_from_source(source: Any) -> dict[str, str]:
    codice = _text(getattr(source, "codice_oggetto_pst", ""))
    if not codice or not codice_oggetto_pst_entry(codice):
        return {
            "codiceOggettoPst": "",
            "fonteCodiceOggetto": "",
            "fileFonteCodiceOggetto": "",
        }
    resolved = codice_oggetto_pst_payload(codice)
    return {
        "codiceOggettoPst": resolved["codice_oggetto_pst"],
        "fonteCodiceOggetto": _text(getattr(source, "fonte_codice_oggetto", "")) or resolved["fonte_codice_oggetto"],
        "fileFonteCodiceOggetto": _text(getattr(source, "file_fonte_codice_oggetto", "")) or resolved["file_fonte_codice_oggetto"],
    }


def _source_practice_prefill(query: dict[str, str], get_preventivi: Callable[[], Any] | None) -> dict[str, Any]:
    if not callable(get_preventivi):
        return {}
    manager = _safe("preventivi_prefill", get_preventivi, None)
    if manager is None:
        return {}
    source: Any | None = None
    preventivo: Any | None = None
    source_kind = ""
    source_preventivo = _text(query.get("source_preventivo"))
    source_conferimento = _text(query.get("source_conferimento"))
    if source_conferimento:
        source = _safe("conferimento_prefill", lambda: manager.get_conferimento(source_conferimento), None)
        source_kind = "conferimento"
        pid = _text(getattr(source, "id_preventivo", "")) if source else ""
        preventivo = _safe("preventivo_conferimento_prefill", lambda: manager.get_preventivo(pid), None) if pid else None
    elif source_preventivo:
        preventivo = _safe("preventivo_prefill", lambda: manager.get_preventivo(source_preventivo), None)
        source = preventivo
        source_kind = "preventivo"
    if source is None:
        return {}
    reference = source
    codice_source = reference if _text(getattr(reference, "codice_oggetto_pst", "")) else preventivo
    codice_payload = _codice_oggetto_from_source(codice_source) if codice_source else _codice_oggetto_from_source(reference)
    amount = getattr(reference, "compenso_pattuito", None)
    if amount in (None, "") and preventivo is not None:
        amount = getattr(preventivo, "totale", "")
    title = _text(getattr(reference, "oggetto", "")) or _text(getattr(preventivo, "oggetto", ""))
    return {
        "title": title,
        "object": title,
        "clientId": _text(getattr(reference, "id_cliente", "")) or _text(getattr(preventivo, "id_cliente", "")),
        "id_cliente": _text(getattr(reference, "id_cliente", "")) or _text(getattr(preventivo, "id_cliente", "")),
        "leadLawyer": _text(getattr(reference, "avvocato_referente", "")),
        "procedureType": _text(getattr(reference, "tipo_procedimento", "")) or _text(getattr(preventivo, "tipo_procedimento", "")),
        "practiceId": _text(getattr(reference, "id_pratica", "")) or _text(getattr(preventivo, "id_pratica", "")),
        "practiceArea": _text(getattr(reference, "area_pratica", "")) or _text(getattr(preventivo, "area_pratica", "")),
        "proceduraOperativaCodice": _text(getattr(reference, "procedura_operativa_codice", "")) or _text(getattr(preventivo, "procedura_operativa_codice", "")),
        "quotedValue": str(getattr(preventivo, "totale", "") or ""),
        "quotedValueRaw": str(getattr(preventivo, "totale", "") or ""),
        "agreedFee": str(amount or ""),
        "agreedFeeRaw": str(amount or ""),
        "sourceKind": source_kind,
        **codice_payload,
    }


def _form_fascicolo_payload(
    fascicolo: Any | None,
    *,
    studio_avvocato_titolare: str = "",
) -> dict[str, Any] | None:
    if not fascicolo:
        return None
    lead_lawyer = _lead_lawyer_label(getattr(fascicolo, "avvocato_referente", ""), studio_avvocato_titolare)
    base = _item(fascicolo)
    base.update(
        {
            "object": _text(getattr(fascicolo, "oggetto", "")),
            "counterparty": _text(getattr(fascicolo, "controparte", "")),
            "counterpartyTaxCode": _text(getattr(fascicolo, "cf_controparte", "")),
            "judge": _text(getattr(fascicolo, "giudice", "")),
            "section": _text(getattr(fascicolo, "sezione", "")),
            "leadLawyer": lead_lawyer,
            "studioLeadLawyer": _text(studio_avvocato_titolare),
            "dominus": _text(getattr(fascicolo, "avvocato_dominus", "")),
            "value": str(getattr(fascicolo, "valore_causa", "") or ""),
            "quotedValue": str(getattr(fascicolo, "valore_preventivato", "") or ""),
            "agreedFee": str(getattr(fascicolo, "compenso_pattuito", "") or ""),
            "procedureType": _text(getattr(fascicolo, "tipo_procedimento", "")),
            "practiceId": _text(getattr(fascicolo, "id_pratica", "")),
            "practiceArea": _text(getattr(fascicolo, "area_pratica", "")),
            "proceduraOperativaCodice": _text(getattr(fascicolo, "procedura_operativa_codice", "")),
            "codiceOggettoPst": _codice_oggetto_label(fascicolo),
            "codiceGuidaPratica": _text(getattr(fascicolo, "codice_guida_pratica", "")),
            "fonteCodiceOggetto": _text(getattr(fascicolo, "fonte_codice_oggetto", "")),
            "fileFonteCodiceOggetto": _text(getattr(fascicolo, "file_fonte_codice_oggetto", "")),
            "riferimentoCartaceo": _text(getattr(fascicolo, "riferimento_cartaceo", "")),
            "attorePrincipale": _text(getattr(fascicolo, "attore_principale", "")),
            "istruttorePmGip": _text(getattr(fascicolo, "istruttore_pm_gip", "")),
            "cancelliere": _text(getattr(fascicolo, "cancelliere", "")),
            "ctu": _text(getattr(fascicolo, "ctu", "")),
            "ctp": _text(getattr(fascicolo, "ctp", "")),
            "statoPraticaOperativa": _text(getattr(fascicolo, "stato_pratica_operativa", "")),
            "personalizzabile": bool(getattr(fascicolo, "personalizzabile", False)),
            "fascicoloVeloce": bool(getattr(fascicolo, "fascicolo_veloce", False)),
            "documentiInizialiCount": int(getattr(fascicolo, "documenti_iniziali_count", 0) or 0),
            "emailInizialiCount": int(getattr(fascicolo, "email_iniziali_count", 0) or 0),
            "dataAperturaIso": _text(getattr(fascicolo, "data_apertura", "")),
            "dataChiusuraIso": _text(getattr(fascicolo, "data_chiusura", "")),
            "firstHearing": _date_label(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotification": _date_label(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearing": _date_label(getattr(fascicolo, "data_prossima_udienza", "")),
            "notes": _italian_dates_in_text(getattr(fascicolo, "note", "")),
            "reservedNotes": _italian_dates_in_text(getattr(fascicolo, "note_riservate", "")),
            "source": _text(getattr(fascicolo, "source", "")),
            "sourceExternalId": _text(getattr(fascicolo, "source_external_id", "")),
            "lastSyncAt": _date_label(getattr(fascicolo, "last_sync_at", "")),
            "syncStatus": _text(getattr(fascicolo, "sync_status", "")),
            "importLogId": _text(getattr(fascicolo, "import_log_id", "")),
            "hasConflicts": bool(getattr(fascicolo, "has_conflicts", False)),
            "documentSyncEnabled": bool(getattr(fascicolo, "document_sync_enabled", False)),
            "eventsSyncEnabled": bool(getattr(fascicolo, "events_sync_enabled", False)),
            "complianceControlsEnabled": bool(getattr(fascicolo, "compliance_controls_enabled", True)),
            "archiveReady": bool(getattr(fascicolo, "archivio_pronto", False)),
            "typeRaw": _enum_value(getattr(fascicolo, "tipo", "")),
            "statusRaw": _enum_value(getattr(fascicolo, "stato", "")),
            "clientId": _text(getattr(fascicolo, "id_cliente", "")),
            "id_cliente": _text(getattr(fascicolo, "id_cliente", "")),
            "tribunale": _text(getattr(fascicolo, "tribunale", "")),
            "numeroRg": _text(getattr(fascicolo, "numero_rg", "")),
            "numero_rg": _text(getattr(fascicolo, "numero_rg", "")),
            "annoRg": str(getattr(fascicolo, "anno_rg", "") or ""),
            "anno_rg": str(getattr(fascicolo, "anno_rg", "") or ""),
            "valueRaw": str(getattr(fascicolo, "valore_causa", "") or ""),
            "quotedValueRaw": str(getattr(fascicolo, "valore_preventivato", "") or ""),
            "agreedFeeRaw": str(getattr(fascicolo, "compenso_pattuito", "") or ""),
            "firstHearingIso": _text(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotificationIso": _text(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearingIso": _text(getattr(fascicolo, "data_prossima_udienza", "")),
        }
    )
    return base


def _deposit_channel_for_type(tipo: str) -> dict[str, str]:
    raw = str(tipo or "").strip().upper()
    if raw == "PENALE":
        return {"channel": "PDP_PENALE", "portal": "PDP", "label": "PDP Penale"}
    if raw == "AMMINISTRATIVO":
        return {"channel": "PAT_AMMINISTRATIVO", "portal": "PAT", "label": "PAT Amministrativo"}
    if raw == "TRIBUTARIO":
        return {"channel": "PTT_TRIBUTARIO", "portal": "PTT", "label": "PTT / SIGIT Tributario"}
    return {"channel": "PCT_TELEMATICO", "portal": "PCT", "label": "PCT / PST Civile"}


def _new_fascicolo_guardrails(query: dict[str, str], fascicolo: Any | None = None) -> dict[str, Any]:
    tipo = query.get("tipo") or _enum_value(getattr(fascicolo, "tipo", "")) or "CIVILE"
    channel = _deposit_channel_for_type(tipo)
    return {
        "available": True,
        "title": "Presidio apertura fascicolo",
        "portal": channel["portal"],
        "channel": channel["channel"],
        "channelLabel": channel["label"],
        "mode": "opening",
        "blocking": [],
        "warnings": [
            {
                "code": "DOCUMENTI_PREDEPOSITO_DOPO_CREAZIONE",
                "message": (
                    "La Guida Pratica resta facoltativa. I dati salvati qui alimentano fascicolo, Lex, documenti "
                    "e controlli quando decidi di usarli."
                ),
                "field": "documenti",
            }
        ],
        "requiredOpeningFields": ["titolo", "tipo", "oggetto", "autorità giudiziaria", "controparte"],
        "nextStep": {
            "label": "Dopo la creazione resta nel fascicolo",
            "href": "",
        },
    }


def build_react_fascicolo_form_payload(
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any] | None = None,
    get_preventivi: Callable[[], Any] | None = None,
    id_fasc: str | None = None,
    query: dict[str, Any] | None = None,
    correction_context: dict[str, Any] | None = None,
    studio_avvocato_titolare: str = "",
) -> dict[str, Any]:
    query = {str(k): _text(v) for k, v in (query or {}).items()}
    fascicolo = _safe("fascicolo", lambda: get_fascicoli().get(id_fasc), None) if id_fasc else None
    source_prefill = {} if fascicolo else _source_practice_prefill(query, get_preventivi)
    if source_prefill.get("clientId") and not query.get("id_cliente"):
        query["id_cliente"] = _text(source_prefill.get("clientId"))
    mode = "edit" if id_fasc else "new"
    action = f"/fascicoli/{id_fasc}/modifica" if id_fasc else "/fascicoli/nuovo"
    detail = f"/fascicoli/{id_fasc}" if id_fasc else "/fascicoli"
    guardrails = _new_fascicolo_guardrails(query, fascicolo)
    workflow = None
    if query.get("source_preventivo") or query.get("source_conferimento"):
        workflow = {
            "title": "Apertura pratica guidata",
            "badges": [value for value in [query.get("source_preventivo"), query.get("source_conferimento"), query.get("from_page")] if value],
            "summary": "Il fascicolo conservera' il collegamento con preventivo e conferimento tramite i campi nascosti storici.",
            "checklist": [
                "Verifica dati cliente, controparte e ufficio giudiziario.",
                "Controlla valore causa, compenso pattuito e tipo procedimento.",
                "Dopo la creazione carica documenti, scadenze e attività iniziali.",
            ],
            "values": [
                {"label": "Preventivo origine", "value": query.get("source_preventivo", "n.d."), "mono": True},
                {"label": "Conferimento origine", "value": query.get("source_conferimento", "n.d."), "mono": True},
            ],
        }
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "mode": mode,
        "action": action,
        "backHref": f"/fascicoli/{id_fasc}" if id_fasc else "/fascicoli",
        "detailHref": detail,
        "query": query,
        "clients": _client_options(get_clienti),
        "subjects": _subject_options(get_soggetti),
        "judicialOffices": _judicial_office_options(),
        "types": _select_options(TipoFascicolo),
        "states": _select_options(StatoFascicolo),
        "studio": {
            "leadLawyer": _text(studio_avvocato_titolare),
        },
        "fascicolo": _form_fascicolo_payload(
            fascicolo,
            studio_avvocato_titolare=studio_avvocato_titolare,
        ) or {
            "leadLawyer": _text(studio_avvocato_titolare),
            "studioLeadLawyer": _text(studio_avvocato_titolare),
            **source_prefill,
        },
        "workflow": workflow,
        "correction": correction_context or {"active": False, "title": "", "help": "", "highlight": ""},
        "guardrails": guardrails,
    }


def _client_payload(cliente: Any) -> dict[str, Any] | None:
    if not cliente:
        return None
    recapiti = getattr(cliente, "recapiti", None)
    indirizzo = getattr(cliente, "indirizzo", None)
    address = " ".join(
        part
        for part in [
            _text(getattr(indirizzo, "via", "")),
            _text(getattr(indirizzo, "cap", "")),
            _text(getattr(indirizzo, "comune", "")),
            _text(getattr(indirizzo, "provincia", "")),
        ]
        if part
    )
    return {
        "id": _text(getattr(cliente, "id", "")),
        "name": _client_label(cliente),
        "taxCode": _text(getattr(cliente, "codice_fiscale", "")),
        "vat": _text(getattr(cliente, "partita_iva", "")),
        "email": _text(getattr(recapiti, "email", "") or getattr(cliente, "email", "")),
        "pec": _text(getattr(recapiti, "pec", "") or getattr(cliente, "pec", "")),
        "phone": _text(getattr(recapiti, "telefono", "") or getattr(recapiti, "cellulare", "") or getattr(cliente, "telefono", "")),
        "address": address,
        "href": f"/clienti/{_text(getattr(cliente, 'id', ''))}",
    }


def _profile(fascicolo: Any, *, apps: Iterable[Any] | None = None, studio_avvocato_titolare: str = "") -> list[dict[str, Any]]:
    source_snapshot = getattr(fascicolo, "source_snapshot", None)
    source_counts = dict(source_snapshot.get("counts") or {}) if isinstance(source_snapshot, dict) else {}
    source_summary = ""
    if source_counts:
        source_summary = ", ".join(
            f"{label} {int(source_counts.get(key) or 0)}"
            for key, label in (
                ("parti", "parti"),
                ("documenti", "documenti"),
                ("depositi", "depositi"),
                ("eventi", "eventi"),
            )
            if int(source_counts.get(key) or 0)
        )
    rows = [
        ("Cliente", _fascicolo_client_label(fascicolo), False, f"/clienti/{_text(getattr(fascicolo, 'id_cliente', ''))}" if _text(getattr(fascicolo, "id_cliente", "")) else ""),
        ("Controparte", getattr(fascicolo, "controparte", ""), False, ""),
        ("Tribunale", getattr(fascicolo, "tribunale", ""), False, ""),
        ("N. registro", _rg(fascicolo), True, ""),
        ("Rif. interno", getattr(fascicolo, "numero", ""), True, ""),
        ("Sezione", getattr(fascicolo, "sezione", ""), False, ""),
        ("Giudice", getattr(fascicolo, "giudice", ""), False, ""),
        ("Oggetto pratica", getattr(fascicolo, "tipo_procedimento", ""), False, ""),
        ("Codice oggetto", _codice_oggetto_label(fascicolo), True, ""),
        ("Attore principale", getattr(fascicolo, "attore_principale", ""), False, ""),
        ("C.T.U.", getattr(fascicolo, "ctu", ""), False, ""),
        ("C.T.P.", getattr(fascicolo, "ctp", ""), False, ""),
        ("Avv. referente", _lead_lawyer_label(getattr(fascicolo, "avvocato_referente", ""), studio_avvocato_titolare), False, ""),
        ("Avv. dominus", getattr(fascicolo, "avvocato_dominus", ""), False, ""),
        ("Valore causa", _euro(getattr(fascicolo, "valore_causa", 0)), False, ""),
        ("Compenso pattuito", _euro(getattr(fascicolo, "compenso_pattuito", 0)), False, ""),
        ("Apertura", _date_label(getattr(fascicolo, "data_apertura", "")), False, ""),
        ("Prima udienza", _date_label(getattr(fascicolo, "data_prima_udienza", "")), False, ""),
        ("Prossima udienza", _date_label(_next_hearing_value(fascicolo, apps)), False, ""),
        ("Chiusura", _date_label(_closure_date_value(fascicolo)), False, ""),
        ("Fonte portale", getattr(fascicolo, "source", ""), False, ""),
        ("Dati letti dal portale", source_summary, False, ""),
        ("Ultimo sync", _date_label(getattr(fascicolo, "last_sync_at", "")), False, ""),
    ]
    return [
        {"label": label, "value": _text(value, "n.d."), "mono": mono, "href": href}
        for label, value, mono, href in rows
        if _text(value) and _text(value) not in {"EUR 0,00", "€ 0,00"}
    ]


def _notifica_portal_acquisition_href(fascicolo: Any, release: dict[str, Any] | None = None) -> str:
    release = release or {}
    source_text = _text(release.get("fontePortale") or release.get("servizioPortale")).upper()
    if "PDP" in source_text:
        base = "/portali/pdp/acquisizione"
    elif "PAT" in source_text or "SIGA" in source_text:
        base = "/portali/pat/acquisizione"
    elif "PTT" in source_text or "SIGIT" in source_text:
        base = "/portali/ptt/acquisizione"
    else:
        base = "/portali/pst/acquisizione"
    params = [
        ("id_fasc", _text(getattr(fascicolo, "id", ""))),
        ("fascicolo_id", _text(getattr(fascicolo, "id", ""))),
        ("mode", "update_existing"),
        ("focus", "documenti"),
        ("numero", _text(getattr(fascicolo, "numero_rg", ""))),
        ("anno", _text(getattr(fascicolo, "anno_rg", ""))),
        ("ufficio", _text(getattr(fascicolo, "tribunale", ""))),
        ("id_deposito_pct", _text(release.get("depositoId"))),
        ("id_deposito", _text(release.get("idDepositoEsterno"))),
        ("id_documento", _text(release.get("documentoId") or release.get("riferimentoPortale"))),
        ("documento_portale", _text(release.get("nome"))),
        ("single_document", "1"),
        ("pec_id", _text(release.get("pecId"))),
        ("hash", _text(release.get("hashSha256"))),
        ("non_duplicare_documenti", "1"),
        ("fase_successiva", "relata_notifica"),
    ]
    query = "&".join(f"{quote(key)}={quote(value)}" for key, value in params if value)
    return f"{base}?{query}#acquisizione-portale" if query else f"{base}#acquisizione-portale"


def _normalise_office_document_name(value: Any) -> str:
    raw = _text(value).lower()
    if raw.endswith(".pdf.p7m"):
        raw = raw[:-4]
    elif raw.endswith(".p7m") and ".pdf" not in raw:
        raw = raw[:-4]
    return re.sub(r"[^a-z0-9]+", "", raw)


def _office_pec_messages() -> list[Any]:
    try:
        from web.helpers import get_email_pec

        return list(get_email_pec().tutte())[:500]
    except Exception:
        return []


def _notification_relata(fascicolo: Any, office_pec_messages: list[Any] | None = None) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    pec_evidence = office_notification_evidence_from_pec(
        fascicolo,
        _office_pec_messages() if office_pec_messages is None else office_pec_messages,
    )
    pending_releases = [item for item in pec_evidence if not item.get("acquisito")]
    local_documents = list(getattr(fascicolo, "documenti", []) or [])

    def _doc_haystack(doc: Any) -> str:
        return " ".join(
            _text(value).lower()
            for value in (
                getattr(doc, "nome", ""),
                getattr(doc, "nome_originale", ""),
                getattr(doc, "nome_portale", ""),
                getattr(doc, "tipo_atto_portale", ""),
                getattr(doc, "classificazione_portale", ""),
                getattr(doc, "note", ""),
                " ".join(str(item) for item in (getattr(doc, "tags", []) or [])),
            )
        )

    office_names = {
        _normalise_office_document_name(item.get("nome"))
        for item in pec_evidence
        if item.get("acquisito")
    }
    office_hashes = {
        _text(item.get("hashSha256")).lower()
        for item in pec_evidence
        if item.get("acquisito") and _text(item.get("hashSha256"))
    }
    office_documents = [
        doc
        for doc in local_documents
        if _normalise_office_document_name(getattr(doc, "nome", "") or getattr(doc, "nome_originale", "") or getattr(doc, "nome_portale", "")) in office_names
        or (_text(getattr(doc, "hash_sha256", "")).lower() in office_hashes if _text(getattr(doc, "hash_sha256", "")) else False)
        or "comunicazione_cancelleria" in _doc_haystack(doc)
        or ("notifica" in _doc_haystack(doc) and any(token in _doc_haystack(doc) for token in ("sentenza", "ordinanza", "decreto", "provvedimento")))
    ]
    notification_kinds = {id(doc): _notification_proof_kind_for_document(doc) for doc in local_documents}
    relata_documents = [doc for doc in local_documents if notification_kinds.get(id(doc)) == "relata"]
    notified_act_documents = [doc for doc in local_documents if notification_kinds.get(id(doc)) == "atto_notificato"]
    signed_relata = [
        doc
        for doc in relata_documents
        if document_has_real_digital_signature(doc)
    ]
    proof_documents = [
        doc
        for doc in local_documents
        if notification_kinds.get(id(doc)) in {"atto_notificato", "pec", "rac", "rdac", "attestazione"}
    ]
    has_rac = any(notification_kinds.get(id(doc)) == "rac" for doc in local_documents)
    has_rdac = any(notification_kinds.get(id(doc)) == "rdac" for doc in local_documents)
    notification_already_sent = any(
        notification_kinds.get(id(doc)) in {"pec", "rac", "rdac", "atto_notificato"}
        for doc in local_documents
    )
    proof_complete = bool(has_rac and has_rdac)
    first_release = pending_releases[0] if pending_releases else {}
    acquisition_href = _notifica_portal_acquisition_href(fascicolo, first_release)
    prepare_href = f"/notifiche-legali?id_fascicolo={quote(fid)}&fase=notifica#notifica" if fid else "/notifiche-legali#notifica"
    deposit_href = f"/notifiche-legali?id_fascicolo={quote(fid)}&fase=deposito#deposito" if fid else "/notifiche-legali#deposito"
    if pending_releases:
        status = "da_acquisire"
        status_label = "Provvedimento da scaricare dal portale"
        tone = "warning"
        primary_href = _text(first_release.get("acquisitionHref")) or acquisition_href
        primary_label = "Scarica dal portale"
    elif office_documents and not relata_documents:
        status = "da_preparare"
        status_label = "Relata da preparare"
        tone = "warning"
        primary_href = prepare_href
        primary_label = "Prepara relata"
    elif relata_documents and not signed_relata:
        status = "da_firmare"
        status_label = "Relata da firmare"
        tone = "warning"
        primary_href = relata_documents[0].id and f"/fascicoli/{quote(fid)}/documenti/{quote(_text(relata_documents[0].id))}/firma"
        primary_label = "Firma relata"
    elif notification_already_sent and not proof_complete:
        status = "ricevute_da_completare"
        status_label = "Ricevute notifica da completare"
        tone = "warning"
        primary_href = deposit_href
        primary_label = "Controlla prova"
    elif signed_relata and not proof_documents:
        status = "pronta_invio"
        status_label = "Relata pronta per revisione e invio"
        tone = "success"
        primary_href = prepare_href
        primary_label = "Apri notifica"
    elif proof_complete:
        status = "prova_raccolta"
        status_label = "Prova notifica pronta per deposito"
        tone = "success"
        primary_href = deposit_href
        primary_label = "Controlla prova"
    else:
        status = "monitoraggio"
        status_label = "Monitoraggio attivo"
        tone = "neutral"
        primary_href = prepare_href
        primary_label = "Apri notifica"
    primary_href = primary_href or prepare_href
    steps = [
        {
            "id": "rilascio_portale",
            "label": "PEC ufficio",
            "status": "da_acquisire" if pending_releases else "superato" if office_documents else "monitorato",
            "detail": f"{len(pending_releases)} documento/i comunicati via PEC da scaricare dal portale" if pending_releases else "Nessuna PEC d'ufficio pendente.",
        },
        {
            "id": "acquisizione",
            "label": "Documento in atti",
            "status": "superato" if office_documents else "da_completare",
            "detail": f"{len(office_documents)} documento/i già nei Documenti e atti." if office_documents else "Integra solo il provvedimento indicato dalla PEC senza duplicare gli atti già presenti.",
        },
        {
            "id": "relata",
            "label": "Relata notifica",
            "status": "superato" if relata_documents else "da_preparare" if office_documents else "in_attesa",
            "detail": f"{len(relata_documents)} relata/e nel fascicolo." if relata_documents else "La relata sarà generata dai dati della pratica e dai documenti collegati.",
        },
        {
            "id": "firma",
            "label": "Firma e revisione avvocato",
            "status": "superato" if signed_relata else "da_firmare" if relata_documents else "in_attesa",
            "detail": "Nessun invio automatico senza revisione finale.",
        },
        {
            "id": "prova",
            "label": "RAC, RdAC e deposito prova",
            "status": "superato" if proof_complete else "da_completare" if signed_relata or notification_already_sent else "in_attesa",
            "detail": (
                f"{len(proof_documents)} documento/i prova collegati."
                if proof_documents
                else "Dopo l'invio PEC collega RAC e RdAC originali, senza creare una nuova notifica."
            ),
        },
    ]
    monitored_documents = []
    seen_monitored_documents: set[str] = set()
    for doc in (office_documents + notified_act_documents + relata_documents + proof_documents):
        kind = notification_kinds.get(id(doc)) or ("documento_ufficio" if doc in office_documents else "prova")
        key = _notification_proof_key(doc, kind)
        if key in seen_monitored_documents:
            continue
        seen_monitored_documents.add(key)
        if doc in signed_relata:
            doc_status = "firmato"
        elif kind == "atto_notificato":
            doc_status = "documento_notificato"
        elif kind in {"rac", "rdac"}:
            doc_status = "ricevuta_presente"
        elif kind == "pec":
            doc_status = "inviato"
        else:
            doc_status = "acquisito"
        doc_id = _text(getattr(doc, "id", ""))
        monitored_name = _document_name_with_signature_suffix(
            doc,
            _professional_document_name(doc, Counter()),
            getattr(doc, "nome", ""),
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome_portale", ""),
            getattr(doc, "percorso", ""),
        )
        monitored_documents.append(
            {
                "id": doc_id,
                "name": monitored_name,
                "kind": kind,
                "kindLabel": _notification_kind_label(kind),
                "status": doc_status,
                "statusLabel": _notification_status_label(doc_status),
                "href": f"/fascicoli/{quote(fid)}/documenti/{quote(doc_id)}/visualizza" if fid and doc_id else "",
            }
        )
        if len(monitored_documents) >= 20:
            break
    system_notification = status_label
    if pending_releases:
        system_notification = "PEC dell'ufficio ricevuta: scarica dal portale solo il provvedimento indicato e collegalo ai Documenti e atti prima della relata."
    elif notification_already_sent and not proof_complete:
        system_notification = "Notifica già inviata: completa RAC e RdAC originali per depositare la prova, senza preparare un nuovo invio."
    elif proof_complete:
        system_notification = "Notifica già inviata e prova raccolta: controlla i file e deposita la prova quando previsto."
    return {
        "status": status,
        "statusLabel": status_label,
        "tone": tone,
        "releaseDetected": bool(pending_releases),
        "notificationAlreadySent": notification_already_sent,
        "proofComplete": proof_complete,
        "pendingPortalDocuments": len(pending_releases),
        "portalDocuments": len(office_documents),
        "officeDocuments": len(office_documents),
        "relataDocuments": len(relata_documents),
        "signedRelataDocuments": len(signed_relata),
        "proofDocuments": len(proof_documents),
        "acquisitionHref": acquisition_href,
        "prepareHref": prepare_href,
        "depositHref": deposit_href,
        "primaryHref": primary_href,
        "primaryLabel": primary_label,
        "systemNotification": system_notification,
        "releasedDocuments": pending_releases[:20],
        "documents": monitored_documents,
        "steps": steps,
    }


def _saved_document_catalog_by_id(fascicolo: Any) -> dict[str, DocumentCatalogClassification]:
    payments = getattr(fascicolo, "pagamenti", {}) or {}
    marker = _presidio_documentale_marker(payments)
    classifications = marker.get("classifications") if isinstance(marker, dict) else []
    if not isinstance(classifications, list):
        return {}
    by_id: dict[str, DocumentCatalogClassification] = {}
    fallback_by_name: dict[str, DocumentCatalogClassification] = {}

    def _make_catalog(row: dict[str, Any]) -> DocumentCatalogClassification | None:
        code = _text(row.get("code") or row.get("classification")).lower()
        label = _text(row.get("label"))
        evidence = _text(row.get("source"), "Presidio documentale salvato")
        if code in {"contributo_unificato_pagamento", "contributo_unificato"}:
            return DocumentCatalogClassification(
                role="contributo_unificato",
                label=label or "Contributo unificato / pagamento",
                section="pagamenti",
                confidence=96,
                evidence=evidence,
                tipo_documento=TipoDocumento.ALLEGATO,
                deposit_role="contributo_unificato",
                deposit_candidate=True,
            )
        if code in {"sentenza_strutturale", "sentenza"}:
            return DocumentCatalogClassification(
                role="provvedimento",
                label=label or "Sentenza",
                section="provvedimenti",
                confidence=94,
                evidence=evidence,
                tipo_documento=TipoDocumento.SENTENZA,
                deposit_role="allegato",
                deposit_candidate=True,
            )
        if code in {"deposito_pct", "deposito_telematico"}:
            return DocumentCatalogClassification(
                role="comunicazione",
                label=label or "Deposito telematico PCT",
                section="comunicazioni",
                confidence=90,
                evidence=evidence,
                tipo_documento=TipoDocumento.DEPOSITO_PCT,
                deposit_role="allegato",
                deposit_candidate=False,
            )
        return None

    for row in classifications:
        if not isinstance(row, dict):
            continue
        catalog = _make_catalog(row)
        if catalog is None:
            continue
        document_id = _text(row.get("documentId") or row.get("document_id") or row.get("id"))
        if document_id:
            by_id[document_id] = catalog
        source_name = _clean_document_filename(row.get("documentoFonte") or row.get("filename") or row.get("name"))
        if source_name:
            fallback_by_name[source_name.casefold()] = catalog
    if fallback_by_name:
        for doc in getattr(fascicolo, "documenti", []) or []:
            did = _text(getattr(doc, "id", ""))
            if not did or did in by_id:
                continue
            names = {
                _clean_document_filename(getattr(doc, "nome", "")),
                _clean_document_filename(getattr(doc, "nome_originale", "")),
                _clean_document_filename(getattr(doc, "nome_portale", "")),
            }
            for name in names:
                catalog = fallback_by_name.get(name.casefold()) if name else None
                if catalog:
                    by_id[did] = catalog
                    break
    return by_id


def _document_catalog_from_saved_type(doc: Any) -> DocumentCatalogClassification:
    try:
        current_type = getattr(doc, "tipo", TipoDocumento.ALTRO)
        tipo = current_type if isinstance(current_type, TipoDocumento) else TipoDocumento(_enum_value(current_type))
    except ValueError:
        tipo = TipoDocumento.ALTRO
    mapping: dict[TipoDocumento, tuple[str, str, str, int, str, bool]] = {
        TipoDocumento.RICORSO: ("atto_principale", "Ricorso - atto principale", "atti", 95, "atto_principale", True),
        TipoDocumento.CITAZIONE: ("atto_principale", "Citazione - atto principale", "atti", 92, "atto_principale", True),
        TipoDocumento.COMPARSA: ("atto_processuale", "Comparsa / memoria difensiva", "atti", 88, "allegato", True),
        TipoDocumento.MEMORIA: ("atto_processuale", "Memoria", "atti", 88, "allegato", True),
        TipoDocumento.SENTENZA: ("provvedimento", "Sentenza", "provvedimenti", 92, "allegato", True),
        TipoDocumento.ORDINANZA: ("provvedimento", "Ordinanza", "provvedimenti", 90, "allegato", True),
        TipoDocumento.DECRETO: ("provvedimento", "Decreto", "provvedimenti", 90, "allegato", True),
        TipoDocumento.VERBALE: ("provvedimento", "Verbale", "provvedimenti", 86, "allegato", True),
        TipoDocumento.PROCURA: ("procura", "Procura alle liti", "procure", 90, "procura", True),
        TipoDocumento.NOTIFICA: ("notifica", "Notifica / prova notifica", "notifiche", 90, "allegato", True),
        TipoDocumento.DEPOSITO_PCT: ("comunicazione", "Deposito telematico PCT", "comunicazioni", 88, "allegato", False),
        TipoDocumento.COMUNICAZIONE: ("comunicazione", "Comunicazione", "comunicazioni", 82, "allegato", False),
        TipoDocumento.CONTRATTO: ("contratto", "Contratto / incarico", "contratti", 84, "allegato", True),
        TipoDocumento.PARCELLA: ("economico", "Parcella / documento economico", "pagamenti", 88, "allegato", False),
        TipoDocumento.ALLEGATO: ("allegato", "Allegato", "allegati", 72, "allegato", True),
    }
    role, label, section, confidence, deposit_role, deposit_candidate = mapping.get(
        tipo,
        ("da_verificare", "Da verificare", "da-verificare", 35, "allegato", False),
    )
    document_tags = {_text(tag).casefold() for tag in (getattr(doc, "tags", []) or [])}
    if tipo == TipoDocumento.COMUNICAZIONE and "email-iniziali" in document_tags:
        label = "Comunicazione / ricevuta"
    return DocumentCatalogClassification(
        role=role,
        label=label,
        section=section,
        confidence=confidence,
        evidence="Tipo documento salvato nel fascicolo",
        tipo_documento=tipo,
        deposit_role=deposit_role,
        deposit_candidate=deposit_candidate,
    )


def _documents(fascicolo: Any, *, gestore_fascicoli: Any | None = None) -> list[dict[str, Any]]:
    fid = _text(getattr(fascicolo, "id", ""))
    out = []
    local_doc_ids = set()
    local_portal_refs: set[tuple[str, str]] = set()

    def _empty_actions() -> dict[str, str]:
        return {
            "preview": "",
            "download": "",
            "acquire": "",
            "edit": "",
            "sign": "",
            "pdfa": "",
            "attest": "",
            "metadata": "",
            "delete": "",
        }

    def _portal_acquisition_href(row: dict[str, Any], dep: Any, source: str) -> str:
        source_text = _text(source).upper()
        if "PDP" in source_text:
            base = "/portali/pdp/acquisizione"
        elif "PAT" in source_text or "SIGA" in source_text:
            base = "/portali/pat/acquisizione"
        elif "PTT" in source_text or "SIGIT" in source_text:
            base = "/portali/ptt/acquisizione"
        else:
            base = "/portali/pst/acquisizione"
        params = [
            ("id_fasc", fid),
            ("fascicolo_id", fid),
            ("mode", "update_existing"),
            ("id_deposito_pct", _text(getattr(dep, "id", ""))),
            ("id_deposito", _text(row.get("id_deposito") or getattr(dep, "id_deposito_esterno", ""))),
            ("id_documento", _text(row.get("id_documento") or row.get("id_cat") or row.get("id_repeatto") or row.get("msg_id"))),
            ("documento_portale", _text(row.get("nome"))),
        ]
        query = "&".join(f"{quote(key)}={quote(value)}" for key, value in params if value)
        return f"{base}?{query}#acquisizione-portale" if query else f"{base}#acquisizione-portale"

    def _portal_ref(field: str, value: Any) -> tuple[str, str] | None:
        text = _text(value)
        return (field, text) if text else None

    def _real_signature(doc: Any, *display_names: Any) -> bool:
        if gestore_fascicoli is None or not fid or not _text(getattr(doc, "id", "")):
            return document_has_real_digital_signature(doc) and not document_has_signed_container(doc, *display_names)
        try:
            if hasattr(gestore_fascicoli, "percorso_documento_lettura"):
                path = gestore_fascicoli.percorso_documento_lettura(fid, _text(getattr(doc, "id", "")))
            else:
                path = gestore_fascicoli.percorso_documento(fid, _text(getattr(doc, "id", "")))
            raw_data = Path(path).read_bytes()
            from web.services.document_crypto import decrypt_doc

            data = decrypt_doc(raw_data)
        except OSError:
            return document_has_real_digital_signature(doc) and not document_has_signed_container(doc, *display_names)
        except Exception:
            return False
        if document_bytes_have_real_digital_signature(
            data,
            *display_names,
            getattr(doc, "nome", ""),
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome_portale", ""),
            str(path),
        ):
            return True
        return document_has_real_digital_signature(doc) and not document_has_signed_container(
            doc,
            *display_names,
            getattr(doc, "nome", ""),
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome_portale", ""),
            str(path),
        )

    local_documents = list(getattr(fascicolo, "documenti", []) or [])
    saved_catalog = _saved_document_catalog_by_id(fascicolo)

    display_name_counters: Counter[str] = Counter()
    for doc in local_documents:
        did = _text(getattr(doc, "id", ""))
        technical_name = _clean_document_filename(getattr(doc, "nome", ""))
        original_name = (
            _clean_document_filename(getattr(doc, "nome_portale", ""))
            or _clean_document_filename(getattr(doc, "nome_originale", ""))
        )
        base_name = _professional_document_name(doc, display_name_counters)
        name = _document_name_with_signature_suffix(
            doc,
            base_name,
            technical_name,
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome_portale", ""),
            getattr(doc, "percorso", ""),
        )
        signed = _real_signature(doc, name, technical_name)
        raw_type = _enum_value(getattr(doc, "tipo", "ALTRO")).replace("_", " ")
        catalog = saved_catalog.get(did) or _document_catalog_from_saved_type(doc)
        display_type = catalog.label if catalog.confidence >= 70 else raw_type
        if did:
            local_doc_ids.add(did)
        for ref in (
            _portal_ref("id_documento", getattr(doc, "id_documento_portale", "")),
            _portal_ref("id_cat", getattr(doc, "id_cat_portale", "")),
            _portal_ref("id_repeatto", getattr(doc, "id_repeatto_portale", "")),
            _portal_ref("msg_id", getattr(doc, "msg_id_portale", "")),
            _portal_ref("nome", getattr(doc, "nome_portale", "") or getattr(doc, "nome_originale", "")),
        ):
            if ref:
                local_portal_refs.add(ref)
        out.append(
            {
                "_sortAt": _parse_datetime(
                    getattr(doc, "data_caricamento", "")
                    or getattr(doc, "data_deposito_portale", "")
                    or getattr(doc, "data_documento", "")
                ),
                "id": did,
                "name": name,
                "type": display_type,
                "rawType": raw_type,
                "size": _bytes_label(getattr(doc, "dimensione_bytes", 0)),
                "uploadedAt": _date_label_optional(getattr(doc, "data_caricamento", "")),
                "documentDate": _date_label_optional(getattr(doc, "data_documento", "")),
                "notes": _short(_italian_dates_in_text(getattr(doc, "note", "")), 180),
                "tags": _visible_document_tags(doc, display_name=name, technical_name=original_name),
                "signed": signed,
                "statusLabel": "Firmato" if signed else "Da firmare",
                "statusTone": "success" if signed else "warning",
                "source": _source_label_for_document(doc),
                "portalName": _clean_document_filename(getattr(doc, "nome_portale", "")) or (_clean_document_filename(getattr(doc, "nome_originale", "")) if not _technical_filename(getattr(doc, "nome_originale", "")) else ""),
                "portalClass": _portal_class_for_document(doc),
                "portalSender": _text(getattr(doc, "mittente_portale", "")),
                "portalDate": _date_label_optional(getattr(doc, "data_deposito_portale", "")),
                "hash": _text(getattr(doc, "hash_sha256", "")),
                "portalDocumentId": _text(getattr(doc, "id_documento_portale", "")),
                "portalIdCat": _text(getattr(doc, "id_cat_portale", "")),
                "portalIdRepeatto": _text(getattr(doc, "id_repeatto_portale", "")),
                "portalMessageId": _text(getattr(doc, "msg_id_portale", "")),
                "portalDepositId": _text(getattr(doc, "id_deposito_esterno", "")),
                "portalParentId": _text(getattr(doc, "id_documento_padre_portale", "")),
                "catalogRole": catalog.role,
                "catalogLabel": catalog.label,
                "catalogSection": catalog.section,
                "catalogConfidence": catalog.confidence,
                "catalogEvidence": catalog.evidence,
                "depositRole": catalog.deposit_role,
                "depositCandidate": catalog.deposit_candidate,
                "actions": {
                    "preview": f"/fascicoli/{fid}/documenti/{did}/visualizza",
                    "download": f"/fascicoli/{fid}/documenti/{did}/scarica",
                    "edit": f"/fascicoli/{fid}/documenti/{did}/editor",
                    "sign": f"/fascicoli/{fid}/documenti/{did}/firma",
                    "pdfa": f"/fascicoli/{fid}/documenti/{did}/converti-pdfa",
                    "attest": f"/fascicoli/{fid}/documenti/{did}/attestazione",
                    "metadata": f"/fascicoli/{fid}/documenti/{did}/metadati",
                    "rename": f"/fascicoli/{fid}/documenti/{did}/rinomina",
                    "delete": f"/fascicoli/{fid}/documenti/{did}/elimina",
                    "acquire": "",
                },
            }
        )

    seen_portal_docs: set[tuple[str, str, str]] = set()
    for dep in getattr(fascicolo, "depositi_pct", []) or []:
        dep_id = _text(getattr(dep, "id", ""))
        imported_doc_ids = {_text(value) for value in (getattr(dep, "documenti_ids", []) or []) if _text(value)}
        for index, row in enumerate(getattr(dep, "documenti_portale", []) or []):
            if not isinstance(row, dict):
                continue
            ref_candidates = [
                _portal_ref("id_documento", row.get("id_documento")),
                _portal_ref("id_cat", row.get("id_cat")),
                _portal_ref("id_repeatto", row.get("id_repeatto")),
                _portal_ref("msg_id", row.get("msg_id")),
                _portal_ref("nome", row.get("nome")),
            ]
            refs = {ref for ref in ref_candidates if ref}
            if refs & local_portal_refs:
                continue
            if imported_doc_ids and imported_doc_ids.issubset(local_doc_ids) and len(imported_doc_ids) >= 1:
                continue
            name = _text(row.get("nome"), "Documento ufficiale")
            portal_identifier = _text(row.get("id_documento") or row.get("id_cat") or row.get("id_repeatto") or row.get("msg_id"))
            key = (
                portal_identifier,
                "" if portal_identifier else _text(row.get("id_deposito") or getattr(dep, "id_deposito_esterno", "") or dep_id),
                name.casefold(),
            )
            if key in seen_portal_docs:
                continue
            seen_portal_docs.add(key)
            source = _text(getattr(dep, "fonte_portale", "")) or _text(getattr(dep, "servizio_portale", ""), "Portale")
            actions = _empty_actions()
            actions["acquire"] = _portal_acquisition_href(row, dep, source)
            portal_catalog = classify_fascicolo_document(
                filename=name,
                tipo=_text(row.get("tipo") or row.get("tipo_atto"), ""),
            )
            out.append(
                {
                    "_sortAt": _parse_datetime(row.get("data_deposito") or row.get("data_documento")),
                    "id": f"portale-{dep_id or 'deposito'}-{index}",
                    "name": name,
                    "type": portal_catalog.label if portal_catalog.confidence >= 70 else _text(row.get("tipo") or row.get("tipo_atto"), "Documento ufficiale"),
                    "rawType": _text(row.get("tipo") or row.get("tipo_atto"), "Documento ufficiale"),
                    "size": _bytes_label(row.get("dimensione_bytes", 0)),
                    "uploadedAt": "",
                    "documentDate": _date_label_optional(row.get("data_deposito") or row.get("data_documento")),
                    "notes": "Documento censito dal portale ufficiale. Per visualizzarlo va acquisito dal PST con sessione autenticata o Local Signer del PC.",
                    "tags": ["Catalogo portale", source],
                    "signed": False,
                    "statusLabel": "Da acquisire",
                    "statusTone": "info",
                    "source": source,
                    "portalName": name,
                    "portalClass": _text(row.get("tipo_atto") or row.get("tipo")),
                    "portalSender": _text(row.get("mittente")),
                    "portalDate": _date_label_optional(row.get("data_deposito") or row.get("data_documento")),
                    "hash": "",
                    "portalDocumentId": _text(row.get("id_documento") or row.get("id_documento_portale")),
                    "portalIdCat": _text(row.get("id_cat")),
                    "portalIdRepeatto": _text(row.get("id_repeatto")),
                    "portalMessageId": _text(row.get("msg_id")),
                    "portalDepositId": _text(row.get("id_deposito") or getattr(dep, "id_deposito_esterno", "")),
                    "portalParentId": _text(row.get("id_documento_padre") or row.get("parent_id_documento")),
                    "catalogRole": portal_catalog.role,
                    "catalogLabel": portal_catalog.label,
                    "catalogSection": portal_catalog.section,
                    "catalogConfidence": portal_catalog.confidence,
                    "catalogEvidence": portal_catalog.evidence,
                    "depositRole": portal_catalog.deposit_role,
                    "depositCandidate": portal_catalog.deposit_candidate,
                    "actions": actions,
                }
            )
    out.sort(key=lambda item: item.get("_sortAt") or datetime.min, reverse=True)
    for item in out:
        item.pop("_sortAt", None)
    return out


_PORTAL_ACTIVITY_TYPES_HIDDEN_FROM_TIMELINE = {
    "DEPOSITO_ATTI",
    "COMUNICAZIONE_CANCELLERIA",
}

_ACTIVITY_TYPES_WITH_DEDICATED_SECTIONS = {
    "COMUNICAZIONE_CANCELLERIA",
}


def _clean_key(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value).casefold()).strip()


def _activity_is_portal_noise(att: Any) -> bool:
    if not _text(getattr(att, "id_deposito_pct", "")):
        return False
    tipo = _enum_value(getattr(att, "tipo", "")).upper()
    title = _text(getattr(att, "titolo", "")).casefold()
    description = _text(getattr(att, "descrizione", "")).casefold()
    return (
        tipo in _PORTAL_ACTIVITY_TYPES_HIDDEN_FROM_TIMELINE
        or "deposito da portale" in title
        or "documenti censiti da" in description
    )


def _activity_group_key(att: Any) -> tuple[str, str, str]:
    tipo = _enum_value(getattr(att, "tipo", "")).upper()
    raw_date = _text(getattr(att, "data", ""))
    title = _clean_key(getattr(att, "titolo", ""))
    if tipo == "UDIENZA":
        activity_id = _text(getattr(att, "id", ""))
        if activity_id:
            return (tipo, raw_date, f"activity:{activity_id}")
        hearing_identity = "|".join(
            part
            for part in (
                _text(getattr(att, "id_appuntamento", "")),
                _text(getattr(att, "id_documento", "")),
                title,
                _text(getattr(att, "hearing_time", "")),
                _text(getattr(att, "remote_hearing_url", "")),
                _text(getattr(att, "remote_hearing_meeting_id", "")),
                _clean_key(getattr(att, "luogo", "")),
            )
            if part
        )
        return (tipo, raw_date, hearing_identity or title)
    if tipo == "ISCRIZIONE_A_RUOLO":
        title = tipo
    deposit_id = _text(getattr(att, "id_deposito_pct", ""))
    event_id = (
        deposit_id
        or _text(getattr(att, "id_appuntamento", ""))
        or _text(getattr(att, "id_documento", ""))
        or title
    )
    return (tipo, raw_date, event_id)


def _activity_quality_score(att: Any) -> int:
    title = _text(getattr(att, "titolo", "")).casefold()
    description = _text(getattr(att, "descrizione", "")).casefold()
    source_bonus = 80 if any(token in f"{title} {description}" for token in ("polisweb", "pst", "portale")) else 0
    specificity_bonus = 40 if any(token in f"{title} {description}" for token in ("rg ", "ruolo", "udienza importata")) else 0
    return (
        len(_text(getattr(att, "descrizione", ""))) * 2
        + len(_text(getattr(att, "note", "")))
        + len(_text(getattr(att, "titolo", "")))
        + source_bonus
        + specificity_bonus
    )


def _visible_activity_records(fascicolo: Any) -> list[Any]:
    selected: dict[tuple[str, str, str], Any] = {}
    for att in getattr(fascicolo, "attivita", []) or []:
        tipo = _enum_value(getattr(att, "tipo", "")).upper()
        if tipo in _ACTIVITY_TYPES_WITH_DEDICATED_SECTIONS:
            continue
        if _activity_is_portal_noise(att):
            continue
        key = _activity_group_key(att)
        previous = selected.get(key)
        if previous is None or _activity_quality_score(att) > _activity_quality_score(previous):
            selected[key] = att
    return sorted(
        selected.values(),
        key=lambda att: (_text(getattr(att, "data", "")), _text(getattr(att, "creato_il", ""))),
        reverse=True,
    )


_PORTAL_ACT_LABELS = {
    "ATTONONCODIFICATO": "Documento non classificato",
    "DEPOSITONONCODIFICATO": "Deposito non classificato",
    "DEPOSITONOTESCRITTESOSTUDIE": "Deposito note scritte sostitutive udienza",
    "DEPOSITONOTECONCLUSIONALI": "Deposito note conclusionali",
    "PRODUZIONEDOCUMENTIRICHIESTI": "Produzione documenti richiesti",
    "DEPOSITODELLEMEMORIE": "Deposito memorie",
    "DEPOSITODIMEMORIE": "Deposito memorie",
    "DEPOSITODICONTRODEDUZIONI": "Deposito controdeduzioni",
    "DEPOSITODISENTENZA": "Deposito sentenza",
    "DEPOSITOSEMPLICE": "Deposito semplice",
    "ISTANZAGENERICA": "Istanza generica",
    "DOCUMENTO": "Documento",
    "DECRETO": "Decreto",
    "ORDINANZA": "Ordinanza",
    "SENTENZA": "Sentenza",
    "VERBALE": "Verbale",
    "CITAZIONE": "Atto di citazione",
}


def _portal_act_label(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "Evento portale"
    key = re.sub(r"[^A-Za-z0-9]+", "", raw).upper()
    if key in _PORTAL_ACT_LABELS:
        return _PORTAL_ACT_LABELS[key]
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", raw)
    spaced = re.sub(r"[_\-]+", " ", spaced)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    return spaced[:1].upper() + spaced[1:] if spaced else "Evento portale"


def _deposit_display_message(dep: Any, portal_docs: list[dict[str, Any]]) -> str:
    act = _portal_act_label(getattr(dep, "tipo_atto", ""))
    service = _text(getattr(dep, "servizio_portale", "")).casefold()
    text = " ".join(
        [
            service,
            _text(getattr(dep, "tipo_atto", "")).casefold(),
            _text(getattr(dep, "messaggio", "")).casefold(),
            _text(getattr(dep, "note", "")).casefold(),
        ]
    )
    raw_act = _text(getattr(dep, "tipo_atto", "")).casefold()
    if raw_act.startswith("istan") or re.search(r"\bistanza\b", raw_act):
        prefix = "Istanza"
    elif any(token in text for token in ("sentenza", "ordinanza", "decreto", "provved")):
        prefix = "Provvedimento"
    elif any(token in text for token in ("accettaz", "consegna", "rdac", "rac", "esito", "busta")):
        prefix = "Esito deposito"
    elif "deposit" in text:
        prefix = "Deposito"
    elif "istan" in text:
        prefix = "Istanza"
    elif "comunic" in text or "canceller" in text or "notific" in text:
        prefix = "Comunicazione"
    else:
        prefix = "Atto dal portale"
    docs = len(portal_docs)
    suffix = f" - {docs} documento" if docs == 1 else f" - {docs} documenti" if docs else ""
    return f"{prefix}: {act}{suffix}"


def _deposit_dedupe_key(dep: Any, portal_docs: list[dict[str, Any]]) -> tuple[str, ...]:
    doc_names = tuple(sorted(_clean_key(doc.get("name")) for doc in portal_docs if doc.get("name")))
    return (
        _date_label(getattr(dep, "timestamp", "")),
        _clean_key(getattr(dep, "servizio_portale", "")),
        _clean_key(getattr(dep, "tipo_atto", "")),
        _clean_key(getattr(dep, "pec_destinatario", "")),
        _clean_key(getattr(dep, "nome_atto_principale", "")),
        "|".join(doc_names),
    )


def _deposit_receipt_texts(dep: Any) -> list[str]:
    texts: list[str] = []
    for attr in (
        "ricevuta_cancelleria",
        "ricevuta_controlli_automatici",
        "ricevuta_consegna",
        "ricevuta_accettazione",
    ):
        value = _text(getattr(dep, attr, ""))
        if value:
            texts.append(value)
    return texts


def _deposit_receipt_field(dep: Any, label: str) -> str:
    pattern = re.compile(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$")
    for text in _deposit_receipt_texts(dep):
        match = pattern.search(text)
        if match:
            return _text(match.group(1))
    return ""


def _fascicolo_role_number(fascicolo: Any) -> str:
    numero = _text(getattr(fascicolo, "numero_rg", ""))
    anno = _text(getattr(fascicolo, "anno_rg", ""))
    if numero and anno and "/" not in numero:
        return f"{numero}/{anno}"
    return numero


def _activities(fascicolo: Any) -> list[dict[str, Any]]:
    fid = _text(getattr(fascicolo, "id", ""))
    out = []
    for att in _visible_activity_records(fascicolo):
        aid = _text(getattr(att, "id", ""))
        result = _enum_value(getattr(att, "esito", "IN_ATTESA"))
        remote_url = _text(getattr(att, "remote_hearing_url", ""))
        remote_verified = bool(getattr(att, "remote_hearing_verified", False))
        if remote_url:
            try:
                from pct.pec_pipeline import _is_remote_hearing_url

                remote_verified = remote_verified and _is_remote_hearing_url(
                    remote_url,
                    context=_text(getattr(att, "remote_hearing_source", ""))
                    or _text(getattr(att, "descrizione", ""))
                    or _text(getattr(att, "note", "")),
                )[0]
            except (ImportError, TypeError, ValueError):
                remote_verified = False
        if not remote_verified:
            remote_url = ""
        out.append(
            {
                "id": aid,
                "type": _enum_value(getattr(att, "tipo", "ALTRO")).replace("_", " "),
                "title": _short(getattr(att, "titolo", ""), 120) or "Attivita",
                "date": _date_label(getattr(att, "data", "")),
                "description": _short(_italian_dates_in_text(getattr(att, "descrizione", "")), 1200),
                "result": result.replace("_", " "),
                "place": _text(getattr(att, "luogo", "")),
                "notes": _short(_italian_dates_in_text(getattr(att, "note", "")), 900),
                "lawyer": _text(getattr(att, "avvocato", "")),
                "documentId": _text(getattr(att, "id_documento", "")),
                "depositId": _text(getattr(att, "id_deposito_pct", "")),
                "hearingTime": _text(getattr(att, "hearing_time", "")),
                "remoteHearingDetected": bool(
                    getattr(att, "remote_hearing_detected", False)
                    or getattr(att, "remote_hearing_mode", "")
                    or remote_url
                ),
                "remoteHearingMode": _text(getattr(att, "remote_hearing_mode", "")),
                "remoteHearingUrl": remote_url,
                "remoteHearingVerified": bool(remote_url and remote_verified),
                "remoteHearingPlatform": _text(getattr(att, "remote_hearing_platform", "")),
                "remoteHearingMeetingId": _text(getattr(att, "remote_hearing_meeting_id", "")),
                "remoteHearingPasscode": _text(getattr(att, "remote_hearing_passcode", "")),
                "remoteHearingAccessInfo": _short(
                    _italian_dates_in_text(getattr(att, "remote_hearing_access_info", "")),
                    900,
                ),
                "remoteHearingSource": _text(getattr(att, "remote_hearing_source", "")),
                "updateAction": f"/fascicoli/{fid}/attivita/{aid}/esito",
                "deleteAction": f"/fascicoli/{fid}/attivita/{aid}/elimina",
                "tone": _activity_tone(result),
            }
        )
    return out


def _deadlines(scadenze: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for item in scadenze:
        sid = _text(getattr(item, "id", ""), f"deadline-{len(out)}")
        raw_date = _text(getattr(item, "data_scadenza", "") or getattr(item, "data", ""))
        out.append(
            {
                "id": sid,
                "title": _short(getattr(item, "titolo", ""), 120) or "Scadenza",
                "date": _date_label(raw_date),
                "dateIso": raw_date,
                "type": _enum_value(getattr(item, "tipo", "")).replace("_", " "),
                "priority": _enum_value(getattr(item, "priorita", "")).replace("_", " "),
                "status": _enum_value(getattr(item, "stato", "")).replace("_", " "),
                "peremptory": bool(getattr(item, "perentorio", False)),
                "notes": _short(_italian_dates_in_text(getattr(item, "note", "")), 160),
                "href": f"/scadenziario?focus={sid}",
                "tone": _deadline_tone(item),
            }
        )
    return sorted(out, key=lambda item: item["dateIso"] or "9999")


def _appointments(apps: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for app in apps:
        aid = _text(getattr(app, "id", ""), f"app-{len(out)}")
        raw = getattr(app, "data_ora", "") or getattr(app, "data_ora_dt", "")
        out.append(
            {
                "id": aid,
                "title": _short(getattr(app, "titolo", ""), 120) or "Appuntamento",
                "date": _date_label(raw),
                "time": _time_label(raw),
                "place": _text(getattr(app, "luogo", "")),
                "court": _text(getattr(app, "tribunale", "")),
                "type": _enum_value(getattr(app, "tipo", "")),
                "href": f"/agenda?id={aid}",
                "tone": "warning" if _parse_date(raw) and (_parse_date(raw) or date.max) <= date.today() + timedelta(days=1) else "primary",
            }
        )
    return out


def _deposits(fascicolo: Any) -> list[dict[str, Any]]:
    out = []
    seen: set[tuple[str, ...]] = set()
    fid = quote(_text(getattr(fascicolo, "id", "")), safe="")
    for dep in getattr(fascicolo, "depositi_pct", []) or []:
        did = _text(getattr(dep, "id", ""), f"deposito-{len(out)}")
        encoded_did = quote(did, safe="")
        status = _enum_value(getattr(dep, "stato", ""))
        portal_docs = []
        for doc in getattr(dep, "documenti_portale", []) or []:
            if not isinstance(doc, dict):
                continue
            portal_docs.append(
                {
                    "_sortAt": _parse_datetime(doc.get("data_deposito") or doc.get("data_documento")),
                    "name": _text(doc.get("nome"), "Documento ufficiale"),
                    "type": _text(doc.get("tipo"), "Documento"),
                    "date": _date_label(doc.get("data_deposito") or doc.get("data_documento")),
                    "sender": _text(doc.get("mittente")),
                    "imported": bool(doc.get("gia_importato") or doc.get("local_doc_id")),
                    "available": bool(doc.get("disponibile", True)),
                }
            )
        portal_docs.sort(key=lambda item: item.get("_sortAt") or datetime.min, reverse=True)
        portal_dates = [item.get("_sortAt") for item in portal_docs if item.get("_sortAt")]
        for item in portal_docs:
            item.pop("_sortAt", None)
        dedupe_key = _deposit_dedupe_key(dep, portal_docs)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        tone = "success" if status in {"ACCETTATO_CANCELLERIA", "CONSEGNATO", "ACCETTATO_PEC"} else "danger" if "ERRORE" in status or "RIFIUTATO" in status else "warning" if "WARN" in status else "primary"
        message = _deposit_display_message(dep, portal_docs)
        simulated = is_simulated_deposit(dep)
        next_phase = next_receipt_phase(dep)
        accepted_at = _datetime_label(_deposit_receipt_field(dep, "Data esito"))
        role_number = _deposit_receipt_field(dep, "Numero ruolo") or _fascicolo_role_number(fascicolo)
        out.append(
            {
                "_sortAt": _parse_datetime(getattr(dep, "timestamp", ""))
                or _parse_datetime(getattr(dep, "registrato_il", ""))
                or _parse_datetime(_deposit_receipt_field(dep, "Data esito"))
                or (max(portal_dates) if portal_dates else None),
                "id": did,
                "timestamp": _date_label(getattr(dep, "timestamp", "")),
                "sentAt": _datetime_label(getattr(dep, "timestamp", "")),
                "acceptedAt": accepted_at,
                "acceptedBy": _deposit_receipt_field(dep, "Mittente PEC"),
                "registeredBy": _text(getattr(dep, "registrato_da", "")),
                "registeredAt": _datetime_label(getattr(dep, "registrato_il", "")),
                "roleNumber": role_number,
                "receiptMessageId": _deposit_receipt_field(dep, "Message-ID"),
                "sourceMessageId": _deposit_receipt_field(dep, "Message-ID deposito"),
                "status": status.replace("_", " "),
                "actType": _portal_act_label(getattr(dep, "tipo_atto", "")),
                "pec": _text(getattr(dep, "pec_destinatario", "")),
                "message": _short(_italian_dates_in_text(message), 200),
                "checks": _enum_value(getattr(dep, "esito_controlli", "")),
                "source": _text(getattr(dep, "fonte_portale", "")) or _text(getattr(dep, "servizio_portale", "")),
                "externalId": _text(getattr(dep, "id_deposito_esterno", "")),
                "mainFile": _text(getattr(dep, "nome_atto_principale", "")),
                "documentsCount": len(getattr(dep, "documenti_ids", []) or []) + len(portal_docs),
                "portalDocuments": portal_docs,
                "simulated": simulated,
                "receiptSteps": receipt_steps(dep),
                "checkReceiptsAction": f"/api/fascicoli/{fid}/depositi/{encoded_did}/controlla" if fid and encoded_did else "",
                "nextSimulationAction": f"/api/fascicoli/{fid}/depositi/{encoded_did}/simula-ricevuta" if simulated and next_phase != "completo" and fid and encoded_did else "",
                "tone": tone,
            }
        )
    out.sort(key=lambda item: item.get("_sortAt") or datetime.min, reverse=True)
    for item in out:
        item.pop("_sortAt", None)
    return out


def _party_role_label(value: Any) -> str:
    label = _text(getattr(value, "label", ""))
    if label:
        return label
    raw = _enum_value(value)
    return raw.replace("_", " ").title() if raw else ""


def _parties(parti: Iterable[Any], *, fascicolo: Any | None = None, cliente: Any | None = None) -> list[dict[str, str]]:
    out = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    def add_party(*, sid: str, name: str, role: str, tax_code: str = "", email: str = "", pec: str = "", phone: str = "", href: str = "") -> None:
        clean_name = _text(name)
        if not clean_name or clean_name in {"-", "—"}:
            return
        clean_sid = _text(sid, f"soggetto-{len(out)}")
        name_key = clean_name.casefold()
        if clean_sid in seen_ids or name_key in seen_names:
            return
        seen_ids.add(clean_sid)
        seen_names.add(name_key)
        out.append(
            {
                "id": clean_sid,
                "name": clean_name,
                "role": _text(role, "Soggetto"),
                "taxCode": _text(tax_code),
                "email": _text(email),
                "pec": _text(pec),
                "phone": _text(phone),
                "href": _text(href, "/soggetti"),
            }
        )

    for item in parti:
        parte = None
        soggetto = item
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            parte, soggetto = item[0], item[1]
        sid = _text(getattr(soggetto, "id", ""), getattr(parte, "id_soggetto", "") if parte else f"soggetto-{len(out)}")
        recapiti = getattr(soggetto, "recapiti", None)
        add_party(
            sid=sid,
            name=_text(getattr(soggetto, "nome_completo", "")),
            role=_party_role_label(getattr(parte, "ruolo", "")) if parte else _party_role_label(getattr(soggetto, "ruolo", "")),
            tax_code=_text(getattr(soggetto, "codice_fiscale", "") or getattr(soggetto, "identificativo", "") or getattr(soggetto, "partita_iva", "")),
            email=_text(getattr(recapiti, "email", "") or getattr(soggetto, "email", "")),
            pec=_text(getattr(recapiti, "pec", "") or getattr(soggetto, "pec", "")),
            phone=_text(getattr(recapiti, "telefono", "") or getattr(soggetto, "telefono", "")),
            href=f"/soggetti/{sid}",
        )

    if cliente is not None:
        client_id = _text(getattr(cliente, "id", ""))
        recapiti = getattr(cliente, "recapiti", None)
        add_party(
            sid=f"cliente-{client_id}" if client_id else "cliente-fascicolo",
            name=_text(getattr(cliente, "nome_completo", "") or getattr(fascicolo, "nome_cliente", "")),
            role="Cliente / assistito",
            tax_code=_text(getattr(cliente, "codice_fiscale", "") or getattr(cliente, "partita_iva", "")),
            email=_text(getattr(recapiti, "email", "") or getattr(cliente, "email", "")),
            pec=_text(getattr(recapiti, "pec", "") or getattr(cliente, "pec", "")),
            phone=_text(getattr(recapiti, "telefono", "") or getattr(cliente, "telefono", "")),
            href=f"/clienti/{client_id}/cartella" if client_id else "/clienti",
        )

    counterparty = _text(getattr(fascicolo, "controparte", "") if fascicolo is not None else "")
    if counterparty:
        fid = _text(getattr(fascicolo, "id", "") if fascicolo is not None else "")
        add_party(
            sid=f"controparte-{fid}" if fid else "controparte-fascicolo",
            name=counterparty,
            role="Controparte",
            tax_code=_text(getattr(fascicolo, "cf_controparte", "") if fascicolo is not None else ""),
            href=f"/soggetti/nuovo?id_fascicolo={fid}&ruolo=CONTROPARTE" if fid else "/soggetti/nuovo",
        )
    return out


def _history(fascicolo: Any) -> list[dict[str, str]]:
    out = []
    for item in getattr(fascicolo, "avanzamento", []) or []:
        out.append(
            {
                "date": _date_label(getattr(item, "data", "")),
                "description": _short(_italian_dates_in_text(getattr(item, "descrizione", "")), 160),
                "from": _text(getattr(item, "stato_precedente", "")),
                "to": _text(getattr(item, "stato_nuovo", "")),
                "notes": _short(_italian_dates_in_text(getattr(item, "note", "")), 180),
                "lawyer": _text(getattr(item, "avvocato", "")),
            }
        )
    return out


def _fatturapa_item(parcelle: list[Any], fascicolo: Any) -> dict[str, Any]:
    fid = quote(_text(getattr(fascicolo, "id", "")), safe="")
    ultima = parcelle[0] if parcelle else None
    if ultima:
        parcella_id = quote(_text(getattr(ultima, "id", "")), safe="")
        numero = _text(getattr(ultima, "numero", ""), "XML")
        return {
            "id": "fatturapa",
            "label": "FatturaPA / SDI",
            "value": numero,
            "note": "XML per invio a SdI / Agenzia Entrate",
            "href": f"/fatturazione/{parcella_id}/xml",
            "tone": "primary",
        }
    return {
        "id": "fatturapa",
        "label": "FatturaPA / SDI",
        "value": "Da creare",
        "note": "genera parcella e XML per Agenzia Entrate",
        "href": f"/fatturazione/nuova?id_fascicolo={fid}",
        "tone": "warning",
    }


def _economics(
    preventivi: list[Any],
    conferimenti: list[Any],
    parcelle: list[Any],
    timesheet_entries: list[Any],
    fascicolo: Any,
    *,
    duplicate_group: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    minutes = sum(int(getattr(item, "minuti", 0) or 0) for item in timesheet_entries)
    parcelle_total = sum(float(getattr(item, "totale", 0.0) or getattr(item, "netto_a_pagare", 0.0) or 0.0) for item in parcelle)
    fid = quote(_text(getattr(fascicolo, "id", "")), safe="")
    preventivo = preventivi[0] if preventivi else None
    conferimento = conferimenti[0] if conferimenti else None
    parcella = parcelle[0] if parcelle else None
    preventivo_id = quote(_text(getattr(preventivo, "id", "")), safe="") if preventivo else ""
    conferimento_id = quote(_text(getattr(conferimento, "id", "")), safe="") if conferimento else ""
    parcella_id = quote(_text(getattr(parcella, "id", "")), safe="") if parcella else ""
    preventivo_href = f"/preventivi/p/{preventivo_id}" if preventivo_id else f"/preventivi/nuovo?id_fascicolo={fid}"
    conferimento_href = f"/preventivi/conferimento/{conferimento_id}" if conferimento_id else f"/preventivi/conferimento/nuovo?id_fascicolo={fid}"
    parcelle_href = f"/fatturazione?id_documento={parcella_id}" if parcella_id else f"/fatturazione/nuova?id_fascicolo={fid}"
    payment_summary = payment_summary_for_fascicolo_fast(
        fascicolo,
        parcelle=parcelle,
        duplicate_group=duplicate_group,
    )
    return [
        {"id": "valore", "label": "Valore causa", "value": _euro(getattr(fascicolo, "valore_causa", 0)), "note": "dato fascicolo", "href": "#profilo", "tone": "primary"},
        {"id": "compenso", "label": "Compenso pattuito", "value": _euro(getattr(fascicolo, "compenso_pattuito", 0)), "note": f"{len(conferimenti)} conferimenti", "href": conferimento_href, "tone": "purple"},
        {"id": "controllo_pagamenti", "label": "Controllo economico", "value": payment_summary["totaleRegistratoLabel"], "note": payment_summary["statoLabel"], "href": "#economia", "tone": payment_summary["tone"]},
        {"id": "parcelle", "label": "Parcelle", "value": _euro(parcelle_total), "note": f"{len(parcelle)} documenti economici", "href": parcelle_href, "tone": "success"},
        _fatturapa_item(parcelle, fascicolo),
        {"id": "tempo", "label": "Tempo", "value": f"{round(minutes/60, 1)} h".replace(".", ","), "note": f"{len(timesheet_entries)} voci timesheet", "href": f"/timesheet?id_fascicolo={fid}", "tone": "info"},
        {"id": "preventivi", "label": "Preventivi", "value": str(len(preventivi)), "note": "collegati al fascicolo", "href": preventivo_href, "tone": "orange"},
    ]


def _workflow(preventivi: list[Any], conferimenti: list[Any], parcelle: list[Any], timesheet_entries: list[Any], cliente: Any) -> list[dict[str, Any]]:
    return [
        {"label": "Cliente", "value": "OK" if cliente else "Da collegare", "note": "anagrafica fascicolo", "tone": "success" if cliente else "warning", "href": "/clienti"},
        {"label": "Preventivo", "value": str(len(preventivi)), "note": "offerte collegate", "tone": "success" if preventivi else "neutral", "href": "/preventivi/"},
        {"label": "Conferimento", "value": str(len(conferimenti)), "note": "incarichi collegati", "tone": "success" if conferimenti else "warning", "href": "/preventivi/"},
        {"label": "Attività", "value": str(len(timesheet_entries)), "note": "voci valorizzabili", "tone": "primary" if timesheet_entries else "neutral", "href": "/timesheet"},
        {"label": "Parcelle", "value": str(len(parcelle)), "note": "fino all'incasso", "tone": "success" if parcelle else "neutral", "href": "/fatturazione/"},
    ]


def _telematic(fascicolo: Any) -> list[dict[str, Any]]:
    fid = _text(getattr(fascicolo, "id", ""))
    encoded_fid = quote(fid, safe="")
    tipo = _enum_value(getattr(fascicolo, "tipo", ""))
    return [
        {"label": "Deposito telematico", "value": "Prepara", "note": "busta, firma, PEC e ricevute", "href": f"/fascicoli/{encoded_fid}/deposito/prepara", "tone": "success"},
        {"label": "PolisWeb / PST", "value": "Apri", "note": "consultazione e acquisizione guidata", "href": f"/polisWeb?id_fasc={fid}", "tone": "primary"},
        {"label": "PDP Penale", "value": "Attivo" if tipo == "PENALE" else "Disponibile", "note": "percorso penale se applicabile", "href": f"/pdp/fascicoli/{fid}", "tone": "danger" if tipo == "PENALE" else "neutral"},
        {"label": "PAT", "value": "Collega", "note": "amministrativo", "href": "/pat", "tone": "info"},
        {"label": "PTT / SIGIT", "value": "Collega", "note": "tributario", "href": "/sigit", "tone": "warning"},
        {"label": "Checklist deposito", "value": "Verifica", "note": "busta, firme, PDF/A", "href": "/deposito/checklist", "tone": "success"},
    ]


def _quality(fascicolo: Any, cliente: Any, scadenze: list[Any], parti: list[Any]) -> list[dict[str, Any]]:
    governed_documents = _fast_documents_count(fascicolo)
    physical_documents = len(getattr(fascicolo, "documenti", []) or [])
    documents_label = f"{governed_documents} elementi"
    if governed_documents != physical_documents:
        documents_label = f"{governed_documents} elementi, {physical_documents} file acquisiti"
    return [
        {"label": "Dati principali", "value": "titolo, tipo, ufficio", "ok": bool(getattr(fascicolo, "titolo", "") and getattr(fascicolo, "tipo", "")), "tone": "success"},
        {"label": "Cliente", "value": _fascicolo_client_label(fascicolo), "ok": bool(cliente), "tone": "success" if cliente else "warning"},
        {"label": "Parti", "value": f"{len(parti)} soggetti", "ok": bool(parti or getattr(fascicolo, "controparte", "")), "tone": "success" if parti else "warning"},
        {"label": "Documenti", "value": documents_label, "ok": bool(governed_documents), "tone": "primary"},
        {"label": "Scadenze", "value": f"{len(scadenze)} termini", "ok": bool(scadenze), "tone": "warning" if scadenze else "neutral"},
        {"label": "Controlli conformita", "value": "attivi" if getattr(fascicolo, "compliance_controls_enabled", True) else "disattivati", "ok": bool(getattr(fascicolo, "compliance_controls_enabled", True)), "tone": "success" if getattr(fascicolo, "compliance_controls_enabled", True) else "orange"},
        {"label": "Sync portale", "value": _text(getattr(fascicolo, "sync_status", ""), "locale"), "ok": not bool(getattr(fascicolo, "has_conflicts", False)), "tone": "danger" if getattr(fascicolo, "has_conflicts", False) else "success"},
    ]


def _full_fascicolo(
    fascicolo: Any,
    *,
    apps: Iterable[Any] | None = None,
    studio_avvocato_titolare: str = "",
    parcelle: Iterable[Any] | None = None,
    duplicate_group: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _item_light(
        fascicolo,
        automatic_evidence=False,
        full_payment_summary=False,
        parcelle=parcelle,
        duplicate_group=duplicate_group,
    )
    next_hearing = _next_hearing_value(fascicolo, apps)
    closure_date = _closure_date_value(fascicolo)
    base.update(
        {
            "object": _text(getattr(fascicolo, "oggetto", "")),
            "counterparty": _text(getattr(fascicolo, "controparte", "")),
            "counterpartyTaxCode": _text(getattr(fascicolo, "cf_controparte", "")),
            "judge": _text(getattr(fascicolo, "giudice", "")),
            "section": _text(getattr(fascicolo, "sezione", "")),
            "leadLawyer": _lead_lawyer_label(getattr(fascicolo, "avvocato_referente", ""), studio_avvocato_titolare),
            "studioLeadLawyer": _text(studio_avvocato_titolare),
            "dominus": _text(getattr(fascicolo, "avvocato_dominus", "")),
            "value": _euro(getattr(fascicolo, "valore_causa", 0)),
            "quotedValue": _euro(getattr(fascicolo, "valore_preventivato", 0)),
            "agreedFee": _euro(getattr(fascicolo, "compenso_pattuito", 0)),
            "procedureType": _text(getattr(fascicolo, "tipo_procedimento", "")),
            "practiceId": _text(getattr(fascicolo, "id_pratica", "")),
            "practiceArea": _text(getattr(fascicolo, "area_pratica", "")),
            "proceduraOperativaCodice": _text(getattr(fascicolo, "procedura_operativa_codice", "")),
            "codiceOggettoPst": _codice_oggetto_label(fascicolo),
            "codiceGuidaPratica": _text(getattr(fascicolo, "codice_guida_pratica", "")),
            "fonteCodiceOggetto": _text(getattr(fascicolo, "fonte_codice_oggetto", "")),
            "fileFonteCodiceOggetto": _text(getattr(fascicolo, "file_fonte_codice_oggetto", "")),
            "firstHearing": _date_label(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotification": _date_label(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearing": _date_label(next_hearing),
            "closedAt": _date_label(closure_date),
            "notes": _italian_dates_in_text(getattr(fascicolo, "note", "")),
            "reservedNotes": _italian_dates_in_text(getattr(fascicolo, "note_riservate", "")),
            "source": _text(getattr(fascicolo, "source", "")),
            "sourceExternalId": _text(getattr(fascicolo, "source_external_id", "")),
            "lastSyncAt": _date_label(getattr(fascicolo, "last_sync_at", "")),
            "syncStatus": _text(getattr(fascicolo, "sync_status", "")),
            "importLogId": _text(getattr(fascicolo, "import_log_id", "")),
            "sourceSnapshot": dict(getattr(fascicolo, "source_snapshot", {}) or {}),
            "hasConflicts": bool(getattr(fascicolo, "has_conflicts", False)),
            "documentSyncEnabled": bool(getattr(fascicolo, "document_sync_enabled", False)),
            "eventsSyncEnabled": bool(getattr(fascicolo, "events_sync_enabled", False)),
            "complianceControlsEnabled": bool(getattr(fascicolo, "compliance_controls_enabled", True)),
            "archiveReady": bool(getattr(fascicolo, "archivio_pronto", False)),
            "fascicoloVeloce": bool(getattr(fascicolo, "fascicolo_veloce", False)),
            "documentiInizialiCount": int(getattr(fascicolo, "documenti_iniziali_count", 0) or 0),
            "emailInizialiCount": int(getattr(fascicolo, "email_iniziali_count", 0) or 0),
            "typeRaw": _enum_value(getattr(fascicolo, "tipo", "")),
            "statusRaw": _enum_value(getattr(fascicolo, "stato", "")),
            "clientId": _text(getattr(fascicolo, "id_cliente", "")),
            "numeroRg": _text(getattr(fascicolo, "numero_rg", "")),
            "annoRg": str(getattr(fascicolo, "anno_rg", "") or ""),
            "valueRaw": str(getattr(fascicolo, "valore_causa", "") or ""),
            "quotedValueRaw": str(getattr(fascicolo, "valore_preventivato", "") or ""),
            "agreedFeeRaw": str(getattr(fascicolo, "compenso_pattuito", "") or ""),
            "firstHearingIso": _text(getattr(fascicolo, "data_prima_udienza", "")),
            "citationNotificationIso": _text(getattr(fascicolo, "data_notifica_citazione", "")),
            "nextHearingIso": _text(next_hearing),
            "closedAtIso": _text(closure_date),
        }
    )
    return base


def _sentenze_economiche_from_payment_summary(payment_summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payment_summary, dict):
        return None
    items = payment_summary.get("items") or {}
    if not isinstance(items, dict):
        return None
    worklist: list[dict[str, Any]] = []
    sentence_signal = False
    pending = 0
    liquidazione_totale = 0.0
    for kind in ("liquidazione_giudice", "parcella", "contributo_unificato", "spese_esborsi"):
        item = items.get(kind) or {}
        if not isinstance(item, dict):
            continue
        status = _text(item.get("status"))
        amount = item.get("importo")
        source = _text(item.get("documentoFonte") or item.get("documento_fonte") or item.get("origine"))
        note = _text(item.get("note"))
        source_haystack = " ".join([source, _text(item.get("origine")), _text(item.get("natura")), note]).casefold()
        if "sentenza" in source_haystack or kind in {"liquidazione_giudice", "parcella"} and (amount is not None or source):
            sentence_signal = True
        if amount is None and status in {"", "da_registrare", "da_emettere"} and not source:
            continue
        amount_number: float | None = None
        if amount is not None:
            try:
                amount_number = float(amount or 0.0)
            except (TypeError, ValueError):
                amount_number = None
        if kind == "liquidazione_giudice" and amount_number is not None:
            liquidazione_totale += amount_number
        if status in {"da_registrare", "da_emettere", "parziale"}:
            pending += 1
        readable_source = _readable_document_source(source, default="Documento economico del fascicolo") if source else ""
        hint_parts = [
            _text(item.get("statusLabel") or PAYMENT_STATUS_LABELS.get(status)),
            f"Fonte: {readable_source}" if readable_source else "",
        ]
        if not readable_source and note:
            hint_parts.append(_short(note, 130))
        label = {
            "liquidazione_giudice": "Liquidazione letta",
            "parcella": "Proforma/parcella",
            "contributo_unificato": "Contributo unificato",
            "spese_esborsi": "Spese/esborsi",
        }.get(kind, PAYMENT_KIND_LABELS.get(kind, "Controllo economico"))
        value = _amount_label(amount_number) if amount_number is not None else _text(item.get("importoLabel") or item.get("statusLabel"), "Da verificare")
        worklist.append(
            {
                "label": label,
                "value": value,
                "hint": " - ".join(part for part in hint_parts if part),
                "tone": _text(item.get("tone"), "warning" if status in {"da_registrare", "da_emettere", "parziale"} else "success"),
            }
        )
    if not sentence_signal or not worklist:
        return None
    main_value = _euro(liquidazione_totale) if liquidazione_totale else f"{len(worklist)} evidenze"
    return {
        "totals": {
            "sentenze_lette": 1,
            "sentenze_verificate": 0,
            "da_verificare": pending,
            "crediti_cliente": 0.0,
            "crediti_avvocato_antistatario": 0.0,
            "spese_liquidate_totale": round(liquidazione_totale, 2),
            "contributo_unificato_alert": 1 if (items.get("contributo_unificato") or {}).get("status") in {"da_registrare", "parziale"} else 0,
        },
        "worklist": worklist,
        "kpi": {
            "label": "Evidenze economiche lette",
            "value": main_value,
            "tone": "warning" if pending else "success",
        },
    }


_SENTENZA_SOURCE_KEY_RE = re.compile(r"sentenza_key:[^\s;,)]*")


def _sentenze_worklist_visible(worklist: Any) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for raw in worklist or []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        hint = _text(item.get("hint"))
        if hint:
            item["hint"] = _SENTENZA_SOURCE_KEY_RE.sub(
                lambda match: _readable_document_source(match.group(0), default="Sentenza indicizzata nel fascicolo"),
                hint,
            )
        visible.append(item)
    return visible


def _sentenze_economiche(fid: str, payment_summary: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Contesto economico da sentenza per il fascicolo (credito cliente art. 91,
    credito avvocato antistatario art. 93, alert contributo unificato).

    Riusa il runtime che gestisce già flag + tenant (slug) + repository + riepilogo:
    non aprire il repo con `_current_tenant_id()` (usa g.tenant.id, mentre gli audit
    sono scritti per slug -> liste vuote). Ritorna None se il flag è spento, se manca
    il contesto studio o se non ci sono sentenze analizzate: la sezione UI resta vuota.
    """

    try:
        from web.services.sentenza_economic_runtime import build_sentenza_economic_payload

        payload = build_sentenza_economic_payload(str(fid or ""))
    except Exception:
        payload = {}
    if payload.get("ok"):
        summary = payload.get("summary") or {}
        totals = summary.get("totals") or {}
        if int(totals.get("sentenze_lette") or 0):
            return {
                "totals": totals,
                "worklist": _sentenze_worklist_visible(summary.get("worklist") or []),
                "kpi": summary.get("kpi") or {},
            }
    return _sentenze_economiche_from_payment_summary(payment_summary)


def build_react_fascicolo_detail_payload(
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_timesheet: Callable[[], Any],
    get_practice_engine: Callable[[], Any] | None = None,
    get_config_studio: Callable[[], Any] | None = None,
    id_fasc: str,
    studio_avvocato_titolare: str = "",
    include_sections: Iterable[str] | None = None,
) -> dict[str, Any]:
    fascicoli_repo = get_fascicoli()
    fascicolo = _safe("fascicolo", lambda: _resolve_fascicolo(fascicoli_repo, id_fasc), None)
    if not fascicolo:
        return {"source": "repository_reali", "generatedAt": _now(), "contracts": _contracts(), "notFound": True, "fascicolo": {"id": id_fasc}}
    fid = _text(getattr(fascicolo, "id", id_fasc))
    include = {str(section).strip().lower() for section in (include_sections or []) if str(section).strip()}
    include_all = "all" in include or "*" in include
    load_documents = include_all or "documenti" in include or "documents" in include
    load_activities = include_all or "attivita" in include or "activities" in include
    load_deadlines = include_all or "scadenze" in include or "deadlines" in include
    load_deposits = include_all or "depositi" in include or "deposits" in include
    load_regia = include_all or "regia" in include or "practice_engine" in include
    load_relata = include_all or "relata" in include or "relata_notifica" in include
    load_audit = include_all or "audit" in include
    load_lex = include_all or load_documents or "lex" in include or "lex_indexing" in include
    cliente = _safe("cliente", lambda: get_clienti().get(getattr(fascicolo, "id_cliente", "")), None) if getattr(fascicolo, "id_cliente", "") else None
    apps = _safe("agenda", lambda: _agenda_for_fascicolo(get_agenda, fascicolo), [])
    scadenze = _safe("scadenziario", lambda: get_scadenziario().tutte(id_fascicolo=fid, solo_aperte=False), [])
    parti = _safe("soggetti", lambda: get_soggetti().parti_fascicolo(fid), [])
    parties = _parties(parti, fascicolo=fascicolo, cliente=cliente)
    preventivi_repo = _safe("preventivi_repo", lambda: get_preventivi(), None)
    preventivi = _safe("preventivi", lambda: preventivi_repo.preventivi_per_fascicolo(fid), []) if preventivi_repo else []
    conferimenti = _safe("conferimenti", lambda: preventivi_repo.conferimenti_per_fascicolo(fid), []) if preventivi_repo else []
    parcelle = _safe("parcelle", lambda: get_fatturazione().per_fascicolo(fid), [])
    timesheet_entries = _safe("timesheet", lambda: get_timesheet().per_fascicolo(fid), [])
    visible_activity_records = _visible_activity_records(fascicolo)
    visible_activities = _activities(fascicolo) if load_activities else []
    activities = visible_activities if load_activities else []
    visible_requests = [item for item in visible_activities if "ISTAN" in item["type"].upper() or "ISTAN" in item["title"].upper()]
    requests = visible_requests if load_activities else []
    visible_deposits = _deposits(fascicolo)
    notification_communication_count = len(_notification_communication_documents(fascicolo))
    notification_relata = _notification_relata(fascicolo) if load_relata else _notification_relata(fascicolo, [])
    relata_count = max(
        int(notification_relata.get("pendingPortalDocuments") or 0),
        int(notification_relata.get("relataDocuments") or 0),
        int(notification_relata.get("signedRelataDocuments") or 0),
        int(notification_relata.get("proofDocuments") or 0),
        1 if _text(notification_relata.get("status")) != "monitoraggio" else 0,
    )
    quick_counts = {
        "profilo": len(_profile(fascicolo, apps=apps, studio_avvocato_titolare=studio_avvocato_titolare)),
        "documenti": len(getattr(fascicolo, "documenti", []) or []),
        "attivita": len(visible_activity_records),
        "udienze_scadenze": len(scadenze) + len(apps),
        "comunicazioni": len(visible_deposits) + notification_communication_count,
        "istanze": len(visible_requests),
        "relata_notifica": relata_count,
    }
    audit_trail = _audit_trail(fid) if load_audit else _audit_trail_placeholder()
    audit_bundle_action = _text((audit_trail.get("actions") or {}).get("bundle"))
    quick_counts["audit"] = int((audit_trail.get("summary") or {}).get("total") or 0)
    lex_indexing = _safe(
        "lex_indexing",
        lambda: _lex_indexing_summary(fid),
        {
            "total_documents": 0,
            "ready": 0,
            "queued": 0,
            "indexing": 0,
            "errors": 0,
            "stale": 0,
            "last_indexed_at": None,
            "status": "ready",
        },
    ) if load_lex else {
        "total_documents": _fast_documents_count(fascicolo),
        "ready": 0,
        "queued": 0,
        "indexing": 0,
        "errors": 0,
        "stale": 0,
        "not_indexed": 0,
        "archived": 0,
        "last_indexed_at": None,
        "status": "ready",
        "warnings": [],
    }
    known_document_count = _fast_documents_count(fascicolo)
    if known_document_count and int(lex_indexing.get("total_documents") or 0) == 0:
        lex_indexing = {**lex_indexing, "total_documents": known_document_count}
    load_document_presidio = include_all or load_deadlines or load_documents or not include
    document_presidio = (
        _document_presidio_for_fascicolo(
            fascicolo,
            ensure_missing=bool(include_all or load_documents or load_deadlines),
        )
        if load_document_presidio
        else {
            "status": "lazy_non_caricato",
            "tone": "neutral",
            "summary": "Apri udienze, scadenze o documenti per leggere decreti e termini dal fascicolo.",
            "nextAction": None,
            "actions": [],
            "warnings": [],
            "sources": [],
        }
    )
    quick_counts["presidio_documenti"] = len(document_presidio.get("actions") or [])
    duplicate_group = _safe(
        "duplicate_group",
        lambda: _duplicate_group_for_fascicolo(fascicoli_repo.tutti(), fascicolo),
        None,
    )
    related_duplicate_rows = _safe(
        "related_duplicate_rows",
        lambda: _related_duplicate_fascicoli(fascicoli_repo.tutti(), fascicolo),
        [],
    )
    payment_summary_detail = payment_summary_for_fascicolo_fast(
        fascicolo,
        related_fascicoli=related_duplicate_rows,
        parcelle=parcelle,
        duplicate_group=duplicate_group,
    )
    deposit_readiness = _safe(
        "deposit_readiness",
        lambda: deposito_ministerial_readiness(
            fascicolo=fascicolo,
            get_clienti=get_clienti,
            get_config_studio=get_config_studio if callable(get_config_studio) else (lambda: None),
            operatore=studio_avvocato_titolare,
        ),
        {
            "contributoUnificato": {"ready": False, "mode": "da_definire", "label": "Da definire", "amount": None, "amountLabel": "", "source": "", "message": "Definisci il contributo unificato."},
            "anagraficaProcedimento": {"ready": False, "label": "Da completare", "missing": [], "message": "Controlla i dati del procedimento."},
            "valoreCausa": {"ready": False, "value": None, "valueLabel": "", "derivedFromExemption": False, "message": "Inserisci il valore della causa."},
        },
    )
    profile_payload = getattr(fascicolo, "profilo_deposito", {}) or {}
    preparation_raw = profile_payload.get("preparazione_busta") if isinstance(profile_payload, dict) else {}
    preparation_raw = preparation_raw if isinstance(preparation_raw, dict) else {}
    preparation_documents = preparation_raw.get("documents") if isinstance(preparation_raw.get("documents"), list) else []
    preparation_datiatto_extra = preparation_raw.get("datiatto_extra")
    preparation_datiatto_extra = preparation_datiatto_extra if isinstance(preparation_datiatto_extra, dict) else {}
    if not isinstance(preparation_datiatto_extra.get("terzi"), list) and isinstance(preparation_datiatto_extra.get("terzo"), dict):
        preparation_datiatto_extra = {**preparation_datiatto_extra, "terzi": [preparation_datiatto_extra["terzo"]]}
    deposit_preparation = {
        "saved": bool(preparation_documents or preparation_datiatto_extra or preparation_raw.get("updated_at")),
        "typeKey": _text(preparation_raw.get("tipo_deposito_telematico_key")),
        "typeLabel": _text(preparation_raw.get("tipo_deposito_telematico_label")),
        "policy": _text(preparation_raw.get("tipo_deposito_telematico_policy")),
        "updatedAt": _text(preparation_raw.get("updated_at")),
        "updatedBy": _text(preparation_raw.get("updated_by")),
        "datiattoExtra": preparation_datiatto_extra,
        "documents": [
            {
                "documentId": _text(row.get("documentId") or row.get("document_id")),
                "selected": bool(row.get("selected")),
                "role": _text(row.get("role")),
                "alreadySigned": bool(row.get("alreadySigned") or row.get("already_signed")),
                "requiresSignature": bool(row.get("requiresSignature") or row.get("requires_signature")),
            }
            for row in preparation_documents
            if isinstance(row, dict) and _text(row.get("documentId") or row.get("document_id"))
        ],
    }
    sentenze_economiche = _sentenze_economiche(fid, payment_summary=payment_summary_detail)
    operational_presidio = build_fascicolo_operational_presidio(
        fascicolo=fascicolo,
        document_presidio=document_presidio,
        notification_relata=notification_relata,
        payment_summary=payment_summary_detail,
        deposits=visible_deposits if load_deposits or include_all or not include else [],
        duplicate_group=duplicate_group,
        sentenze_economiche=sentenze_economiche,
    )
    quick_counts["presidio_operativo"] = len(operational_presidio.get("actions") or [])
    regia_payload = (
        build_react_practice_engine_payload(
            fascicolo_id=fid,
            get_fascicoli=get_fascicoli,
            get_clienti=get_clienti,
            get_preventivi=get_preventivi,
            get_fatturazione=get_fatturazione,
            get_practice_engine=get_practice_engine,
        )
        if callable(get_practice_engine) and load_regia
        else {
            "source": "repository reale",
            "mock_fallback": False,
            "page_state": "lazy_non_caricata" if callable(get_practice_engine) else "runtime_non_configurato",
            "header": {
                "title": _text(getattr(fascicolo, "titolo", "")),
                "practiceType": _enum_value(getattr(fascicolo, "tipo", "")),
                "area": _text(getattr(fascicolo, "area_pratica", "")),
                "channel": "",
                "registry": "",
                "workflow": "",
                "operationalState": "Da caricare",
                "completion": 0,
                "nextAction": "Apri la sezione Regia Operativa per caricare i controlli.",
            },
            "profile": {},
            "economics": {},
            "checklist": [],
            "documentSlots": [],
            "validation": {"status": "lazy_non_caricata", "ready": False, "lastCheck": "", "blockers": [], "warnings": [], "results": []},
            "deposit": {},
            "timeline": [],
            "evidencePack": {},
            "actions": {},
        }
    )
    deposit_catalog = (
        _safe("deposit_catalog", lambda: build_deposit_catalog_payload(include_entries=True), {})
        if load_deposits or load_regia
        else {}
    )
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "fascicolo": _full_fascicolo(
            fascicolo,
            apps=apps,
            studio_avvocato_titolare=studio_avvocato_titolare,
            parcelle=parcelle,
            duplicate_group=duplicate_group,
        ),
        "quickCounts": quick_counts,
        "lex_indexing": lex_indexing,
        "profile": _profile(fascicolo, apps=apps, studio_avvocato_titolare=studio_avvocato_titolare),
        "documents": _documents(fascicolo, gestore_fascicoli=fascicoli_repo) if load_documents else [],
        "activities": activities,
        "deadlines": _deadlines(scadenze) if load_deadlines else [],
        "appointments": _appointments(apps) if load_deadlines else [],
        "documentPresidio": document_presidio,
        "operationalPresidio": operational_presidio,
        "deposits": visible_deposits if load_deposits else [],
        "requests": requests,
        "parties": parties,
        "history": _history(fascicolo),
        "client": _client_payload(cliente),
        "economics": _economics(preventivi, conferimenti, parcelle, timesheet_entries, fascicolo, duplicate_group=duplicate_group),
        "sentenzeEconomiche": sentenze_economiche,
        "workflow": _workflow(preventivi, conferimenti, parcelle, timesheet_entries, cliente),
        "regia": regia_payload,
        "telematic": _telematic(fascicolo),
        "notificationRelata": notification_relata,
        "quality": _quality(fascicolo, cliente, scadenze, parties),
        "depositOffice": _deposit_office_payload(fascicolo),
        "depositCatalog": deposit_catalog,
        "depositReadiness": deposit_readiness,
        "depositPreparation": deposit_preparation,
        "signature": _signature_settings(get_config_studio),
        "auditTrail": audit_trail,
        "actions": {
            "changeState": f"/fascicoli/{fid}/stato",
            "define": f"/fascicoli/{fid}/definisci",
            "archive": f"/fascicoli/{fid}/archivia",
            "restore": f"/fascicoli/{fid}/ripristina",
            "delete": f"/fascicoli/{fid}/elimina",
            "uploadDocument": f"/fascicoli/{fid}/documenti/carica",
            "importPortal": f"/fascicoli/{fid}/documenti/importa-portale",
            "addActivity": f"/fascicoli/{fid}/attivita/aggiungi",
            "complianceOn": f"/fascicoli/{fid}/conformita/controlli?enabled=1",
            "complianceOff": f"/fascicoli/{fid}/conformita/controlli?enabled=0",
            "exportPdf": f"/fascicoli/{fid}/pdf",
            "archiveZip": f"/fascicoli/{fid}/archivio/scarica",
            "auditBundle": audit_bundle_action,
            "refreshLexIndex": f"/api/v1/ui/fascicoli/{fid}/lex-indexing/aggiorna",
            "retryLexIndexErrors": f"/api/v1/ui/fascicoli/{fid}/lex-indexing/riprova-errori",
        },
        "options": _options(),
    }


def _lex_indexing_summary(fid: str) -> dict[str, Any]:
    from web.services.document_intelligence_runtime import (
        build_document_ai_service,
        collect_document_ai_sources_for_fascicolo,
        document_ai_tenant_id,
    )

    tenant_id = document_ai_tenant_id()
    sources = collect_document_ai_sources_for_fascicolo(fid, tenant_id=tenant_id)
    service = build_document_ai_service()
    records = service.repository.list_documents(tenant_id, fid)

    def _preferred_lex_record(current: Any | None, candidate: Any) -> Any:
        if current is None:
            return candidate
        current_ready = str(getattr(current, "status", "") or "").casefold() == "ready"
        candidate_ready = str(getattr(candidate, "status", "") or "").casefold() == "ready"
        if candidate_ready and not current_ready:
            return candidate
        if current_ready and not candidate_ready:
            return current
        return candidate if str(getattr(candidate, "updated_at", "") or "") > str(getattr(current, "updated_at", "") or "") else current

    records_by_sha: dict[str, Any] = {}
    records_by_source_id: dict[str, Any] = {}
    for record in records:
        sha = str(getattr(record, "sha256", "") or "")
        if sha:
            records_by_sha[sha] = _preferred_lex_record(records_by_sha.get(sha), record)
        source_id = str(getattr(record, "id", "") or "")
        if source_id:
            records_by_source_id[source_id] = _preferred_lex_record(records_by_source_id.get(source_id), record)
    ready = queued = indexing = errors = stale = archived = not_indexed = 0
    last_indexed_at = ""
    for source in sources:
        if not source.supported:
            archived += 1
            continue
        record = records_by_sha.get(str(source.sha256 or "")) or records_by_source_id.get(str(source.source_id or ""))
        if record is None:
            not_indexed += 1
            continue
        status = str(getattr(record, "status", "") or "").casefold()
        updated_at = str(getattr(record, "updated_at", "") or "")
        if updated_at > last_indexed_at:
            last_indexed_at = updated_at
        if status == "ready":
            ready += 1
        elif status == "processing":
            indexing += 1
        elif status == "uploaded":
            queued += 1
        elif status == "archived":
            archived += 1
        elif status == "error":
            errors += 1
        else:
            stale += 1
    if indexing:
        status = "indexing"
    elif errors or stale or not_indexed:
        status = "stale" if stale else "error" if errors else "not_indexed"
    else:
        status = "ready"
    payload = {
        "total_documents": len(sources),
        "ready": ready,
        "queued": queued,
        "indexing": indexing,
        "errors": errors,
        "stale": stale,
        "not_indexed": not_indexed,
        "archived": archived,
        "last_indexed_at": last_indexed_at or None,
        "status": status,
        "warnings": [],
    }
    return {
        "total_documents": int(payload.get("total_documents") or 0),
        "ready": int(payload.get("ready") or 0),
        "queued": int(payload.get("queued") or 0),
        "indexing": int(payload.get("indexing") or 0),
        "errors": int(payload.get("errors") or 0),
        "stale": int(payload.get("stale") or 0),
        "not_indexed": int(payload.get("not_indexed") or 0),
        "archived": int(payload.get("archived") or 0),
        "last_indexed_at": payload.get("last_indexed_at") or None,
        "status": str(payload.get("status") or "ready"),
        "warnings": [str(item) for item in list(payload.get("warnings") or [])[:12]],
    }


def build_react_fascicoli_export_payload(*, get_fascicoli: Callable[[], Any], get_scadenziario: Callable[[], Any]) -> dict[str, Any]:
    page = build_react_fascicoli_payload(get_fascicoli=get_fascicoli, get_scadenziario=get_scadenziario)
    recent = page["items"][:12]
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "summary": page["summary"],
        "formats": [
            {"id": "pdf", "label": "PDF lista", "description": "Elenco fascicoli filtrato", "href": "/fascicoli/export.pdf", "tone": "danger"},
            {"id": "csv", "label": "CSV", "description": "Dati strutturati per analisi", "href": "/fascicoli/export.csv", "tone": "success"},
            {"id": "single_pdf", "label": "PDF singolo", "description": "Scheda completa del fascicolo", "href": "/fascicoli/<id>/pdf", "tone": "primary"},
            {"id": "zip", "label": "ZIP archivio", "description": "Archivio documentale dei fascicoli chiusi", "href": "/fascicoli/<id>/archivio/scarica", "tone": "neutral"},
        ],
        "fields": [
            {"key": "numero", "label": "Numero interno", "checked": True},
            {"key": "rg", "label": "N. causa / RG", "checked": True},
            {"key": "titolo", "label": "Titolo e oggetto", "checked": True},
            {"key": "tipo", "label": "Tipo fascicolo", "checked": True},
            {"key": "stato", "label": "Stato", "checked": True},
            {"key": "cliente", "label": "Cliente", "checked": True},
            {"key": "controparte", "label": "Controparte", "checked": True},
            {"key": "tribunale", "label": "Ufficio giudiziario", "checked": True},
            {"key": "date", "label": "Date apertura/chiusura", "checked": True},
            {"key": "avvocato", "label": "Avvocato referente", "checked": True},
            {"key": "economico", "label": "Valori economici", "checked": False},
            {"key": "contributo_unificato_stato", "label": "Contributo unificato - stato", "checked": True},
            {"key": "contributo_unificato_importo", "label": "Contributo unificato - importo", "checked": True},
            {"key": "fondo_spese_stato", "label": "Spese/esborsi - stato", "checked": True},
            {"key": "fondo_spese_importo", "label": "Spese/esborsi - importo", "checked": True},
            {"key": "liquidazione_giudice_stato", "label": "Liquidazione giudice - stato", "checked": True},
            {"key": "liquidazione_giudice_importo", "label": "Liquidazione giudice - importo", "checked": True},
            {"key": "parcella_stato", "label": "Parcella - stato", "checked": True},
            {"key": "parcella_importo", "label": "Parcella - importo", "checked": True},
            {"key": "totale_registrato", "label": "Totale registrato", "checked": True},
            {"key": "sync", "label": "Sync e fonte portale", "checked": False},
        ],
        "presets": [
            {"label": "Attivi", "description": "Tutti i fascicoli non archiviati", "href": "/fascicoli/export.pdf", "tone": "primary"},
            {"label": "Da archiviare", "description": "Fascicoli definiti pronti per conservazione", "href": "/fascicoli/export.pdf?stato=DEFINITO", "tone": "warning"},
            {"label": "CSV completo", "description": "Base dati per controllo di studio", "href": "/fascicoli/export.csv", "tone": "success"},
            {"label": "Archivio", "description": "Controllo fascicoli chiusi", "href": "/fascicoli/archivio", "tone": "neutral"},
        ],
        "recent": recent,
        "facets": page["facets"],
    }
