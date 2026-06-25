"""Bridge dati per le superfici React Fascicoli.

Il modulo normalizza repository, azioni e metadati del dominio Fascicoli:
lettura tramite API React, scritture demandate ai servizi Flask già auditati.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from flask import current_app, has_app_context

from pct.fascicoli import EsitoAttivita, StatoFascicolo, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.fascicolo_workspace import build_fascicolo_workspace
from pct.deposito_simulazione import is_simulated_deposit, next_receipt_phase, receipt_steps
from pct.notifiche_legali import office_notification_evidence_from_pec
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry, codice_oggetto_pst_payload
from pct.document_signature_state import (
    document_bytes_have_real_digital_signature,
    document_has_real_digital_signature,
    document_has_signed_container,
)
from web.services.react_practice_engine_bridge import build_react_practice_engine_payload

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


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


def _quickorganizer_name_from_note(note: Any) -> str:
    text = _text(note)
    if not text.lower().startswith("import quickorganizer."):
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
    if source == "IMPORT_ESTERNO" and portal_class.lower() == "quickorganizer":
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
    if portal_class.lower() == "quickorganizer":
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
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
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


def _time_label(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%H:%M")


def _euro(value: Any) -> str:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        number = 0.0
    text = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {text}"


PAYMENT_KINDS = (
    "contributo_unificato",
    "fondo_spese",
    "liquidazione_giudice",
    "parcella",
)

PAYMENT_KIND_LABELS = {
    "contributo_unificato": "Contributo unificato",
    "fondo_spese": "Fondo spese",
    "liquidazione_giudice": "Liquidazione giudice",
    "parcella": "Parcella",
}

PAYMENT_KIND_ALIASES = {
    "cu": "contributo_unificato",
    "contributo": "contributo_unificato",
    "contributo_unificato": "contributo_unificato",
    "contributo unificato": "contributo_unificato",
    "fondo": "fondo_spese",
    "fondo_spese": "fondo_spese",
    "fondo spese": "fondo_spese",
    "anticipazione": "fondo_spese",
    "anticipazioni": "fondo_spese",
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
    "fondo_spese": "da_registrare",
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


def _payment_source_for_kind(payments: Any, kind: str) -> dict[str, Any]:
    if not isinstance(payments, dict):
        return {}
    for key, value in payments.items():
        if _normalise_payment_kind(key) == kind and isinstance(value, dict):
            return dict(value)
    return {}


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
    payment_date = _text(raw.get("data_pagamento") or raw.get("dataPagamento") or raw.get("date"))
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
        "documentoFonte": _text(raw.get("documento_fonte") or raw.get("documentSource")),
        "updatedAt": _text(raw.get("updated_at") or raw.get("updatedAt")),
        "updatedAtLabel": _date_label(raw.get("updated_at") or raw.get("updatedAt")) if _text(raw.get("updated_at") or raw.get("updatedAt")) else "",
        "updatedBy": _text(raw.get("updated_by") or raw.get("updatedBy")),
        "updateAction": f"/api/v1/ui/fascicoli/{quote(fid, safe='')}/pagamenti/{kind}",
        "history": _payment_history(raw),
    }


def payment_summary_for_fascicolo(fascicolo: Any) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    payments = getattr(fascicolo, "pagamenti", {}) or {}
    items = {
        kind: _payment_item(kind, _payment_source_for_kind(payments, kind), fid)
        for kind in PAYMENT_KINDS
    }
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
        if kind in {"contributo_unificato", "fondo_spese"} and item["status"] in {"da_registrare", "parziale"} and item["importo"] is not None
    )
    latest = max((_text(item["updatedAt"]) for item in items.values()), default="")
    updated_by = ""
    if latest:
        updated_by = next((_text(item["updatedBy"]) for item in items.values() if _text(item["updatedAt"]) == latest), "")
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
        "parcelleDaEmettere": 1 if items["parcella"]["status"] == "da_emettere" else 0,
        "mancanti": len(missing),
        "updatedAt": latest,
        "updatedAtLabel": _date_label(latest) if latest else "",
        "updatedBy": updated_by,
        "items": items,
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
    except Exception as exc:
        return {"ok": False, "id": proforma_id, "message": str(exc)}


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


def _next_deadline(fascicolo: Any, scadenze_by_fasc: dict[str, list[Any]] | None = None) -> Any | None:
    prop = getattr(fascicolo, "prossima_scadenza", None)
    if prop:
        return prop
    if scadenze_by_fasc is None:
        return None
    deadlines = scadenze_by_fasc.get(_text(getattr(fascicolo, "id", "")), [])
    dated = [item for item in deadlines if _parse_date(getattr(item, "data_scadenza", "") or getattr(item, "data", ""))]
    dated.sort(key=lambda item: _parse_date(getattr(item, "data_scadenza", "") or getattr(item, "data", "")) or date.max)
    return dated[0] if dated else None


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


def _item(fascicolo: Any, *, scadenze_by_fasc: dict[str, list[Any]] | None = None, archived: bool | None = None) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    stato = _enum_value(getattr(fascicolo, "stato", StatoFascicolo.APERTO.value))
    rg_order = _rg_order_from_fascicolo(fascicolo)
    n_scadenza = _next_deadline(fascicolo, scadenze_by_fasc)
    n_date = _next_deadline_date_value(fascicolo, n_scadenza)
    docs = _governed_documents_count(fascicolo)
    deposits = getattr(fascicolo, "depositi_pct", []) or []
    unread = sum(1 for dep in deposits if _enum_value(getattr(dep, "stato", "")).upper() in {"WARN_CONTROLLI", "ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA", "ERRORE"})
    alerts = unread
    if getattr(fascicolo, "has_conflicts", False):
        alerts += 1
    if n_scadenza and _deadline_tone(n_scadenza) in {"danger", "warning"}:
        alerts += 1
    archive = getattr(fascicolo, "archivio", None)
    return {
        "id": fid,
        "ref": _rg(fascicolo) if _rg(fascicolo) != "n.d." else _text(getattr(fascicolo, "numero", ""), fid),
        "internalRef": _text(getattr(fascicolo, "numero", "")),
        "title": _short(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo", 120),
        "subtitle": _short(getattr(fascicolo, "oggetto", ""), 160),
        "type": _type_for_filters(fascicolo),
        "client": _fascicolo_client_label(fascicolo),
        "court": _text(getattr(fascicolo, "tribunale", ""), "Ufficio non impostato"),
        "rg": _rg(fascicolo),
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
) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    stato = _enum_value(getattr(fascicolo, "stato", StatoFascicolo.APERTO.value))
    rg_order = _rg_order_from_fascicolo(fascicolo)
    n_scadenza = _next_deadline(fascicolo, scadenze_by_fasc)
    n_date = _next_deadline_date_value(fascicolo, n_scadenza)
    deposits = getattr(fascicolo, "depositi_pct", []) or []
    unread = sum(1 for dep in deposits if _enum_value(getattr(dep, "stato", "")).upper() in {"WARN_CONTROLLI", "ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA", "ERRORE"})
    alerts = unread
    if getattr(fascicolo, "has_conflicts", False):
        alerts += 1
    if n_scadenza and _deadline_tone(n_scadenza) in {"danger", "warning"}:
        alerts += 1
    payment_summary = payment_summary_for_fascicolo(fascicolo)
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
        "ref": _rg(fascicolo) if _rg(fascicolo) != "n.d." else _text(getattr(fascicolo, "numero", ""), fid),
        "internalRef": _text(getattr(fascicolo, "numero", "")),
        "title": _short(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo", 120),
        "subtitle": _short(getattr(fascicolo, "oggetto", ""), 160),
        "type": _type_for_filters(fascicolo),
        "client": _fascicolo_client_label(fascicolo),
        "court": _text(getattr(fascicolo, "tribunale", ""), "Ufficio non impostato"),
        "rg": _rg(fascicolo),
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
    invoices_to_issue = sum(int((item.get("paymentSummary") or {}).get("parcelleDaEmettere") or 0) for item in items)
    registered_amount = round(sum(float((item.get("paymentSummary") or {}).get("totaleRegistrato") or 0.0) for item in items), 2)
    advances_to_recover = round(sum(float((item.get("paymentSummary") or {}).get("anticipazioniDaRecuperare") or 0.0) for item in items), 2)
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
        "economicToReview": economic_to_review,
        "invoicesToIssue": invoices_to_issue,
        "registeredAmount": registered_amount,
        "advancesToRecover": advances_to_recover,
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
    payment_filters: dict[str, str] | None = None,
) -> bool:
    needle = _text(query).lower()
    if needle:
        haystack = " ".join(
            _text(item.get(key)).lower()
            for key in ("ref", "internalRef", "title", "subtitle", "client", "court", "rg")
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
            for value in (item.get("rg"), item.get("ref"), item.get("rgNumber"), item.get("rgYear"))
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
    if payment_filters:
        summary_items = (item.get("paymentSummary") or {}).get("items") or {}
        for kind, wanted in payment_filters.items():
            wanted_key = _text(wanted).strip().lower()
            if not wanted_key or wanted_key == "tutti":
                continue
            actual = _text((summary_items.get(kind) or {}).get("status")).strip().lower()
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
    page: int = 1,
    page_size: int = 5,
    query: str = "",
    client_filter: str = "",
    rg_filter: str = "",
    type_filter: str = "",
    status_filter: str = "",
    court: str = "",
    sort: str = "rg",
    alerts_only: bool = False,
    payments_only: bool = False,
    payment_filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    gf = get_fascicoli()
    scadenze_rows = _open_scadenze(get_scadenziario)
    fascicoli = _safe("fascicoli", lambda: gf.tutti(archiviati=False), [])
    scadenze_by_fasc = _group_scadenze_by_fasc(scadenze_rows, fascicoli)
    resolved_scadenze = _resolved_scadenze_fascicolo_ids(scadenze_by_fasc)
    archived = _safe("fascicoli_archivio", lambda: gf.tutti(stato=StatoFascicolo.ARCHIVIATO, archiviati=True), [])
    light_items = [_item_light(fascicolo, scadenze_by_fasc=scadenze_by_fasc) for fascicolo in fascicoli]
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
            payment_filters=payment_filters,
        )
    ]
    sorted_items = _sort_list_items(filtered, sort)
    page_size = _positive_int(page_size, 5, maximum=100)
    page = _positive_int(page, 1, maximum=100000)
    pagination = _pagination(page, page_size, len(sorted_items))
    start = (pagination["page"] - 1) * page_size
    items = sorted_items[start:start + page_size]
    items_by_id = {item["id"]: item for item in light_items}
    deadlines30 = len(_deadline_rows_from_scadenze(scadenze_rows, items_by_id, days=30, resolved_matter_ids=resolved_scadenze))
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "summary": _summary(filtered, archived_count=len(archived), deadlines30=deadlines30),
        "items": items,
        "pagination": pagination,
        "facets": _facets(light_items),
        "deadlines": _deadline_rows_from_scadenze(scadenze_rows, items_by_id, days=7, resolved_matter_ids=resolved_scadenze),
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
        "message": "Ufficio destinatario da verificare prima del deposito.",
    }
    if not office_name:
        return base
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
        profile_verified = bool(profile_pec and (profile_office.get("pec_verificata") is True or profile.get("pec_verificata") is True))
        if profile_pec:
            return {
                "name": profile_name,
                "code": profile_code,
                "ministerialCode": profile_ministerial_code,
                "district": _text(profile_office.get("distretto")),
                "pec": profile_pec,
                "kind": _text(profile_office.get("tipo")),
                "verified": profile_verified,
                "message": (
                    f"PEC verificata dal profilo deposito SQL per {profile_name}."
                    if profile_verified
                    else f"PEC presente nel profilo deposito per {profile_name}: verifica manuale prima dell'invio reale."
                ),
            }
    try:
        from pct.uffici_giudiziari import TIPI_UFFICIO, get_gestore

        offices = get_gestore(_uffici_cache_path()).carica()
    except Exception:
        return {
            **base,
            "message": "Catalogo uffici non disponibile: verifica manuale obbligatoria prima dell'invio reale.",
        }

    wanted = office_name.casefold()
    office = next(
        (
            row
            for row in offices
            if _text(row.get("nome")).casefold() == wanted
            or _text(row.get("codice")).casefold() == wanted
            or _text(row.get("codice_ministero")).casefold() == wanted
        ),
        None,
    )
    if office is None:
        office = next((row for row in offices if wanted and wanted in _text(row.get("nome")).casefold()), None)
    if office is None:
        return {
            **base,
            "message": f"Ufficio '{office_name}' non trovato nel catalogo: verifica PEC destinataria prima dell'invio reale.",
        }
    office_type = _text(office.get("tipo"))
    kind = _text((TIPI_UFFICIO.get(office_type) or ("", office_type))[1], office_type)
    pec = _text(office.get("pec") or office.get("pec_ministero"))
    name = _text(office.get("nome"), office_name)
    code = _text(office.get("codice"))
    ministerial_code = _text(office.get("codice_ministero"))
    return {
        "name": name,
        "code": code,
        "ministerialCode": ministerial_code,
        "district": _text(office.get("distretto")),
        "pec": pec,
        "kind": kind,
        "verified": bool(name and code and pec),
        "message": (
            f"PEC verificata dal catalogo uffici per {name}."
            if pec
            else f"PEC non disponibile nel catalogo per {name}: non procedere all'invio reale senza verifica."
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
        if _text(value) and _text(value) != "EUR 0,00"
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

    display_name_counters: Counter[str] = Counter()
    for doc in getattr(fascicolo, "documenti", []) or []:
        did = _text(getattr(doc, "id", ""))
        technical_name = _clean_document_filename(getattr(doc, "nome", ""))
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
                "id": did,
                "name": name,
                "type": _enum_value(getattr(doc, "tipo", "ALTRO")).replace("_", " "),
                "size": _bytes_label(getattr(doc, "dimensione_bytes", 0)),
                "uploadedAt": _date_label_optional(getattr(doc, "data_caricamento", "")),
                "documentDate": _date_label_optional(getattr(doc, "data_documento", "")),
                "notes": _short(_italian_dates_in_text(getattr(doc, "note", "")), 180),
                "tags": _visible_document_tags(doc, display_name=name, technical_name=technical_name),
                "signed": signed,
                "statusLabel": "Firmato" if signed else "Da firmare",
                "statusTone": "success" if signed else "warning",
                "source": _source_label_for_document(doc),
                "portalName": _clean_document_filename(getattr(doc, "nome_portale", "")) or (_clean_document_filename(getattr(doc, "nome_originale", "")) if not _technical_filename(getattr(doc, "nome_originale", "")) else ""),
                "portalClass": _portal_class_for_document(doc),
                "portalSender": _text(getattr(doc, "mittente_portale", "")),
                "portalDate": _date_label_optional(getattr(doc, "data_deposito_portale", "")),
                "hash": _text(getattr(doc, "hash_sha256", "")),
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
            out.append(
                {
                    "id": f"portale-{dep_id or 'deposito'}-{index}",
                    "name": name,
                    "type": _text(row.get("tipo") or row.get("tipo_atto"), "Documento ufficiale"),
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
                    "actions": actions,
                }
            )
    return out


_PORTAL_ACTIVITY_TYPES_HIDDEN_FROM_TIMELINE = {
    "DEPOSITO_ATTI",
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
    if tipo in {"UDIENZA", "ISCRIZIONE_A_RUOLO"}:
        title = tipo
    deposit_id = _text(getattr(att, "id_deposito_pct", ""))
    return (tipo, raw_date, deposit_id or title)


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


def _activities(fascicolo: Any) -> list[dict[str, Any]]:
    fid = _text(getattr(fascicolo, "id", ""))
    out = []
    for att in _visible_activity_records(fascicolo):
        aid = _text(getattr(att, "id", ""))
        result = _enum_value(getattr(att, "esito", "IN_ATTESA"))
        out.append(
            {
                "id": aid,
                "type": _enum_value(getattr(att, "tipo", "ALTRO")).replace("_", " "),
                "title": _short(getattr(att, "titolo", ""), 120) or "Attivita",
                "date": _date_label(getattr(att, "data", "")),
                "description": _short(_italian_dates_in_text(getattr(att, "descrizione", "")), 220),
                "result": result.replace("_", " "),
                "place": _text(getattr(att, "luogo", "")),
                "notes": _short(_italian_dates_in_text(getattr(att, "note", "")), 180),
                "lawyer": _text(getattr(att, "avvocato", "")),
                "documentId": _text(getattr(att, "id_documento", "")),
                "depositId": _text(getattr(att, "id_deposito_pct", "")),
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
                    "name": _text(doc.get("nome"), "Documento ufficiale"),
                    "type": _text(doc.get("tipo"), "Documento"),
                    "date": _date_label(doc.get("data_deposito") or doc.get("data_documento")),
                    "sender": _text(doc.get("mittente")),
                    "imported": bool(doc.get("gia_importato") or doc.get("local_doc_id")),
                    "available": bool(doc.get("disponibile", True)),
                }
            )
        dedupe_key = _deposit_dedupe_key(dep, portal_docs)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        tone = "success" if status in {"ACCETTATO_CANCELLERIA", "CONSEGNATO", "ACCETTATO_PEC"} else "danger" if "ERRORE" in status or "RIFIUTATO" in status else "warning" if "WARN" in status else "primary"
        message = _deposit_display_message(dep, portal_docs)
        simulated = is_simulated_deposit(dep)
        next_phase = next_receipt_phase(dep)
        out.append(
            {
                "id": did,
                "timestamp": _date_label(getattr(dep, "timestamp", "")),
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


def _economics(preventivi: list[Any], conferimenti: list[Any], parcelle: list[Any], timesheet_entries: list[Any], fascicolo: Any) -> list[dict[str, Any]]:
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
    payment_summary = payment_summary_for_fascicolo(fascicolo)
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


def _full_fascicolo(fascicolo: Any, *, apps: Iterable[Any] | None = None, studio_avvocato_titolare: str = "") -> dict[str, Any]:
    base = _item_light(fascicolo)
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
    load_lex = include_all or "lex" in include or "lex_indexing" in include
    cliente = _safe("cliente", lambda: get_clienti().get(getattr(fascicolo, "id_cliente", "")), None) if getattr(fascicolo, "id_cliente", "") else None
    apps = _safe("agenda", lambda: get_agenda().cerca(testo=getattr(fascicolo, "numero_rg", "")) if getattr(fascicolo, "numero_rg", "") else [], [])
    scadenze = _safe("scadenziario", lambda: get_scadenziario().tutte(id_fascicolo=fid, solo_aperte=False), [])
    parti = _safe("soggetti", lambda: get_soggetti().parti_fascicolo(fid), [])
    parties = _parties(parti, fascicolo=fascicolo, cliente=cliente)
    preventivi_repo = _safe("preventivi_repo", lambda: get_preventivi(), None)
    preventivi = _safe("preventivi", lambda: preventivi_repo.preventivi_per_fascicolo(fid), []) if preventivi_repo else []
    conferimenti = _safe("conferimenti", lambda: preventivi_repo.conferimenti_per_fascicolo(fid), []) if preventivi_repo else []
    parcelle = _safe("parcelle", lambda: get_fatturazione().per_fascicolo(fid), [])
    timesheet_entries = _safe("timesheet", lambda: get_timesheet().per_fascicolo(fid), [])
    visible_activities = _activities(fascicolo) if load_activities else []
    activities = visible_activities if load_activities else []
    visible_requests = [item for item in visible_activities if "ISTAN" in item["type"].upper() or "ISTAN" in item["title"].upper()]
    requests = visible_requests if load_activities else []
    visible_deposits = _deposits(fascicolo) if load_deposits else []
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
        "attivita": len(getattr(fascicolo, "attivita", []) or []),
        "udienze_scadenze": len(scadenze) + len(apps),
        "comunicazioni": len(getattr(fascicolo, "depositi_pct", []) or []) + notification_communication_count,
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
    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "fascicolo": _full_fascicolo(fascicolo, apps=apps, studio_avvocato_titolare=studio_avvocato_titolare),
        "quickCounts": quick_counts,
        "lex_indexing": lex_indexing,
        "profile": _profile(fascicolo, apps=apps, studio_avvocato_titolare=studio_avvocato_titolare),
        "documents": _documents(fascicolo, gestore_fascicoli=fascicoli_repo) if load_documents else [],
        "activities": activities,
        "deadlines": _deadlines(scadenze) if load_deadlines else [],
        "appointments": _appointments(apps) if load_deadlines else [],
        "deposits": visible_deposits if load_deposits else [],
        "requests": requests,
        "parties": parties,
        "history": _history(fascicolo),
        "client": _client_payload(cliente),
        "economics": _economics(preventivi, conferimenti, parcelle, timesheet_entries, fascicolo),
        "workflow": _workflow(preventivi, conferimenti, parcelle, timesheet_entries, cliente),
        "regia": regia_payload,
        "telematic": _telematic(fascicolo),
        "notificationRelata": notification_relata,
        "quality": _quality(fascicolo, cliente, scadenze, parties),
        "depositOffice": _deposit_office_payload(fascicolo),
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
    from web.services.document_intelligence_runtime import build_lex_indexing_summary_payload

    payload = build_lex_indexing_summary_payload(fid, process=False)
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
            {"key": "fondo_spese_stato", "label": "Fondo spese - stato", "checked": True},
            {"key": "fondo_spese_importo", "label": "Fondo spese - importo", "checked": True},
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
