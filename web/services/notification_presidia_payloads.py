from __future__ import annotations

import base64
import json
from collections import defaultdict
from datetime import datetime, time
from typing import Any, Mapping
from urllib.parse import quote
from zoneinfo import ZoneInfo

from web.services.notification_presidia_runtime import current_actor_id, presidio_permissions, public_permissions

ROME = ZoneInfo("Europe/Rome")

STATUS_LABELS = {
    "DETECTED": "Rilevato",
    "NEEDS_REVIEW": "Da esaminare",
    "ORIGINAL_TO_ACQUIRE": "Originale da acquisire",
    "ORIGINAL_ACQUIRED": "Originale acquisito",
    "NOTIFICATION_CONFIRMED": "Notifica confermata",
    "RECIPIENTS_TO_VERIFY": "Destinatari da verificare",
    "READY_FOR_RELATA": "Relata da preparare",
    "RELATA_DRAFTED": "Relata preparata",
    "RELATA_SIGNED": "Relata firmata",
    "READY_TO_SEND": "Pronta per invio locale",
    "SENT_WAITING_RAC": "In attesa RAC",
    "RAC_RECEIVED": "RAC ricevuta",
    "PARTIAL_DELIVERY": "Consegna parziale",
    "DELIVERY_COMPLETE": "Consegna completa",
    "DELIVERY_FAILED": "Mancata consegna",
    "PROOF_TO_DEPOSIT": "Prova da depositare",
    "PROOF_DEPOSITED": "Prova depositata",
    "CLOSED": "Chiusa",
    "NOT_REQUIRED": "Non necessaria",
    "CANCELLED": "Annullata",
    "LEGACY_ASSUMED_HANDLED": "Storico presunto gestito",
    "LEGACY_REVIEW_REQUIRED": "Storico da controllare",
}
CHANNEL_LABELS = {"pec": "PEC", "unep": "UNEP", "non_pec": "Non PEC", "nonpec": "Non PEC", "cliente": "Cliente"}
DOCUMENT_ROLE_LABELS = {
    "office_pec_copy": "Copia da PEC ufficio",
    "portal_original": "Originale PST",
    "notified_act": "Atto notificato",
    "relata": "Relata",
    "attestation": "Attestazione",
    "sent_pec": "PEC inviata",
    "rac": "RAC",
    "rdac": "RdAC",
    "delivery_failure": "Mancata consegna",
    "proof_deposit_receipt": "Deposito prova",
}
EVIDENCE_TYPE_LABELS = {"source_message": "Messaggio PEC sorgente", "document": "Documento collegato", "receipt": "Ricevuta PEC", "human_decision": "Decisione operatore", "pipeline": "Evento pipeline"}
NEXT_ACTIONS = {
    "DETECTED": "Esamina e conferma se la notifica è necessaria",
    "NEEDS_REVIEW": "Esamina e conferma se la notifica è necessaria",
    "ORIGINAL_TO_ACQUIRE": "Acquisisci originale dal fascicolo d’ufficio",
    "RECIPIENTS_TO_VERIFY": "Verifica destinatari e pubblici elenchi",
    "READY_FOR_RELATA": "Prepara la relata",
    "RELATA_DRAFTED": "Controlla e firma la relata",
    "RELATA_SIGNED": "Esegui invio dal PC locale",
    "READY_TO_SEND": "Esegui invio dal PC locale",
    "SENT_WAITING_RAC": "Attendi ricevuta di accettazione",
    "RAC_RECEIVED": "Attendi ricevuta di consegna",
    "PARTIAL_DELIVERY": "Verifica destinatari mancanti",
    "DELIVERY_FAILED": "Gestisci mancata consegna",
    "DELIVERY_COMPLETE": "Deposita la prova di notifica",
    "PROOF_TO_DEPOSIT": "Deposita la prova di notifica",
}


def _json_value(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _cursor_encode(cursor: tuple[str, str] | None) -> str | None:
    if not cursor:
        return None
    raw = json.dumps({"updated_at": cursor[0], "id": cursor[1]}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _cursor_decode(raw: str) -> tuple[str, str] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        padded = text + "=" * (-len(text) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return str(payload["updated_at"]), str(payload["id"])
    except Exception:
        return None


def _html_date_to_iso(value: Any, *, end: bool) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        base = datetime.combine(datetime.fromisoformat(text).date(), time(23, 59, 59) if end else time(0, 0, 0))
        return base.replace(tzinfo=ROME).isoformat()
    return text


def _bool_filter(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "si", "sì"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _practice_payload(fascicolo_id: str) -> dict[str, str]:
    label = f"Fascicolo {fascicolo_id}" if fascicolo_id else "Fascicolo non indicato"
    href = f"/fascicoli/{quote(fascicolo_id, safe='')}" if fascicolo_id else ""
    return {"id": fascicolo_id, "label": label, "href": href}


def _option(value: str, label: str) -> dict[str, str]:
    return {"value": str(value or ""), "label": str(label or value or "")}


def _user_options() -> list[dict[str, str]]:
    try:
        from web.helpers import get_utenti

        users = get_utenti().tutti()
    except Exception:
        users = []
    options: list[dict[str, str]] = []
    seen: set[str] = set()
    for user in users:
        value = str(getattr(user, "username", "") or getattr(user, "id", "") or "").strip()
        if not value or value in seen:
            continue
        label = str(getattr(user, "nome_completo", "") or getattr(user, "username", "") or value).strip()
        options.append(_option(value, label))
        seen.add(value)
    actor = current_actor_id()
    if actor and actor not in seen:
        options.insert(0, _option(actor, actor))
    return options


def _assignee(value: str, options: list[dict[str, str]]) -> dict[str, str] | None:
    if not value:
        return None
    return next((item for item in options if item["value"] == value), _option(value, value))


def _query_many(repo: Any, table: str, ids: list[str], order: str) -> dict[str, list[dict[str, Any]]]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    sql = f"SELECT * FROM {table} WHERE tenant_id=? AND presidio_id IN ({placeholders}) {order}"
    with repo.connection() as conn:
        rows = [repo._row(row) for row in conn.execute(sql, tuple([repo.tenant_id, *ids])).fetchall()]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("presidio_id") or "")].append(row)
    return grouped


def _presidio_rows(repo: Any, ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    sql = f"SELECT * FROM pec_legal_notification_presidia WHERE tenant_id=? AND id IN ({placeholders})"
    with repo.connection() as conn:
        rows = [repo._row(row) for row in conn.execute(sql, tuple([repo.tenant_id, *ids])).fetchall()]
    return {str(row["id"]): row for row in rows}


def _recipient_status_label(row: Mapping[str, Any]) -> str:
    delivery = str(row.get("delivery_status") or "pending")
    if delivery == "delivered":
        return "Consegnata"
    if delivery == "failed":
        return "Mancata consegna"
    if str(row.get("rac_status") or "") == "received":
        return "RAC ricevuta"
    if str(row.get("send_status") or "") == "sent":
        return "Inviata"
    return "Da inviare"


def _document_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    row = next((item for item in rows if item.get("authoritative")), rows[0])
    role = str(row.get("document_role") or "")
    return {"id": str(row.get("fascicolo_document_id") or row.get("id") or ""), "name": str(row.get("original_filename") or "Documento collegato"), "role_label": DOCUMENT_ROLE_LABELS.get(role, role or "Documento")}


def _legal_sources(row: Mapping[str, Any]) -> list[str]:
    values = _json_value(row.get("legal_basis_json"), [])
    labels: list[str] = []
    for item in values if isinstance(values, list) else []:
        if isinstance(item, Mapping):
            labels.append(str(item.get("label") or item.get("title") or item.get("id") or "").strip())
        else:
            labels.append(str(item or "").strip())
    return [label for label in labels if label][:6]


def _summary(projection: Mapping[str, Any], row: Mapping[str, Any], recipients: list[Mapping[str, Any]], documents: list[Mapping[str, Any]], assignees: list[dict[str, str]]) -> dict[str, Any]:
    status = str(projection.get("status") or row.get("status") or "DETECTED")
    channel = str(projection.get("channel") or row.get("channel") or "pec").lower()
    return {
        "id": str(projection.get("id") or row.get("id") or ""),
        "practice": _practice_payload(str(projection.get("fascicoloId") or row.get("fascicolo_id") or "")),
        "document": _document_summary(documents),
        "source_effective_at": str(projection.get("sourceEffectiveAt") or row.get("source_effective_at") or ""),
        "explicit_due_at": projection.get("explicitDueAt") or row.get("explicit_due_at"),
        "notification_case": str(projection.get("notificationCase") or row.get("notification_case") or ""),
        "notification_case_label": str(row.get("notification_case") or projection.get("notificationCase") or "Notifica legale"),
        "channel": channel,
        "channel_label": CHANNEL_LABELS.get(channel, channel.upper()),
        "recipients": [{"id": str(item.get("id") or ""), "name": str(item.get("name") or item.get("pec_address") or "Destinatario"), "role": str(item.get("role") or ""), "status_label": _recipient_status_label(item), "delivery_status": str(item.get("delivery_status") or "")} for item in recipients[:4]],
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "priority": str(projection.get("priority") or row.get("priority") or "P1"),
        "confidence": float(projection.get("confidence") or row.get("confidence") or 0.0),
        "detection_reason": str(row.get("detection_reason") or ""),
        "rule_label": str(row.get("rulepack_version") or "Rulepack notifiche legali"),
        "legal_sources": _legal_sources(row),
        "next_action": NEXT_ACTIONS.get(status, "Consulta il presidio"),
        "human_review_required": bool(projection.get("humanReviewRequired") or row.get("human_review_required")),
        "legacy_assumed_handled": bool(projection.get("legacyAssumedHandled") or row.get("legacy_assumed_handled")),
        "assigned_user": _assignee(str(projection.get("assignedUserId") or row.get("assigned_user_id") or ""), assignees),
        "updated_at": str(projection.get("updatedAt") or row.get("updated_at") or ""),
    }


def _status_facets(repo: Any) -> dict[str, int]:
    with repo.connection() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM pec_legal_notification_presidia
            WHERE tenant_id=?
            GROUP BY status
            """,
            (repo.tenant_id,),
        ).fetchall()
    return {str(row["status"]): int(row["count"] or 0) for row in rows}


def build_presidia_list_payload(repo: Any, filters: Mapping[str, Any]) -> dict[str, Any]:
    permissions = presidio_permissions()
    if not permissions["can_read"]:
        raise PermissionError("Permesso messaggi.leggi richiesto.")
    page = repo.list_presidia(
        status=str(filters.get("status") or ""),
        priority=str(filters.get("priority") or ""),
        fascicolo_id=str(filters.get("fascicolo") or ""),
        assigned_user_id=str(filters.get("assigned_user") or ""),
        channel=str(filters.get("channel") or ""),
        recipient_identity_key=str(filters.get("recipient") or ""),
        legacy_assumed_handled=_bool_filter(filters.get("legacy")),
        needs_review=_bool_filter(filters.get("needs_review")),
        date_from=_html_date_to_iso(filters.get("date_from"), end=False),
        date_to=_html_date_to_iso(filters.get("date_to"), end=True),
        cursor=_cursor_decode(str(filters.get("cursor") or "")),
        limit=int(filters.get("limit") or 50),
    )
    public = page.to_public_dict()
    ids = [str(item["id"]) for item in public["items"]]
    rows = _presidio_rows(repo, ids)
    docs = _query_many(repo, "pec_legal_notification_documents", ids, "ORDER BY authoritative DESC, created_at DESC, id DESC")
    recipients = _query_many(repo, "pec_legal_notification_recipients", ids, "ORDER BY required DESC, updated_at DESC, id DESC")
    assignees = _user_options()
    items = [_summary(item, rows.get(str(item["id"]), {}), recipients.get(str(item["id"]), []), docs.get(str(item["id"]), []), assignees) for item in public["items"]]
    return {
        "ok": True,
        "items": items,
        "pagination": {"cursor": str(filters.get("cursor") or ""), "next_cursor": _cursor_encode(public.get("nextCursor")), "has_more": bool(public.get("nextCursor")), "total": None, "limit": int(filters.get("limit") or 50)},
        "facets": {"status": _status_facets(repo)},
        "filter_options": {"assignees": assignees, "channels": [_option(key, label) for key, label in CHANNEL_LABELS.items()]},
        "permissions": public_permissions(permissions),
        "partial": False,
        "warnings": [],
    }


def _detail_rows(repo: Any, presidio_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    row = repo.get_presidio(presidio_id)
    docs = _query_many(repo, "pec_legal_notification_documents", [presidio_id], "ORDER BY authoritative DESC, created_at DESC, id DESC").get(presidio_id, [])
    recipients = _query_many(repo, "pec_legal_notification_recipients", [presidio_id], "ORDER BY required DESC, updated_at DESC, id DESC").get(presidio_id, [])
    return row, docs, recipients


def build_presidio_detail_payload(repo: Any, presidio_id: str) -> dict[str, Any]:
    permissions = presidio_permissions()
    if not permissions["can_read"]:
        raise PermissionError("Permesso messaggi.leggi richiesto.")
    row, docs, recipients = _detail_rows(repo, presidio_id)
    assignees = _user_options()
    projection = {"id": row["id"], "fascicoloId": row.get("fascicolo_id"), "status": row.get("status"), "priority": row.get("priority"), "confidence": row.get("confidence"), "humanReviewRequired": row.get("human_review_required"), "notificationCase": row.get("notification_case"), "channel": row.get("channel"), "assignedUserId": row.get("assigned_user_id"), "legacyAssumedHandled": row.get("legacy_assumed_handled"), "sourceEffectiveAt": row.get("source_effective_at"), "explicitDueAt": row.get("explicit_due_at"), "updatedAt": row.get("updated_at")}
    detail = _summary(projection, row, recipients, docs, assignees)
    detail["recipients"] = [_public_recipient(item) for item in recipients]
    detail["documents"] = [_public_document(item) for item in docs]
    detail["assignment_options"] = assignees
    detail["linkable_documents"] = _linkable_documents(str(row.get("fascicolo_id") or ""))
    detail["available_actions"] = _available_actions(row, permissions, bool(detail["linkable_documents"]))
    detail["source_pec_href"] = "/email"
    if not permissions["can_write"]:
        detail["read_only_reason"] = "Permesso messaggi.scrivi non disponibile."
    return {"ok": True, "presidio": detail, "permissions": public_permissions(permissions), "warnings": []}


def _public_recipient(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "name": str(item.get("name") or item.get("pec_address") or "Destinatario"),
        "role": str(item.get("role") or ""),
        "status_label": _recipient_status_label(item),
        "delivery_status": str(item.get("delivery_status") or ""),
        "fiscal_id": str(item.get("fiscal_id") or ""),
        "pec_address": str(item.get("pec_address") or ""),
        "public_register": str(item.get("public_register") or ""),
        "public_register_verified_at": item.get("public_register_verified_at"),
        "send_status": str(item.get("send_status") or ""),
        "rac_status": str(item.get("rac_status") or ""),
        "failure_reason": str(item.get("failure_reason") or ""),
        "updated_at": str(item.get("updated_at") or ""),
    }


def _public_document(row: Mapping[str, Any]) -> dict[str, Any]:
    role = str(row.get("document_role") or "")
    doc_id = str(row.get("fascicolo_document_id") or row.get("id") or "")
    return {
        "id": doc_id,
        "name": str(row.get("original_filename") or "Documento collegato"),
        "role_label": DOCUMENT_ROLE_LABELS.get(role, role or "Documento"),
        "version_label": f"Versione {row.get('document_version') or '1'}",
        "authoritative": bool(row.get("authoritative")),
        "viewer_url": f"/fascicoli/documenti/{quote(doc_id, safe='')}" if doc_id else "",
        "download_url": f"/fascicoli/documenti/{quote(doc_id, safe='')}/download" if doc_id else "",
    }


def _available_actions(row: Mapping[str, Any], permissions: Mapping[str, bool], has_linkables: bool) -> list[dict[str, Any]]:
    status = str(row.get("status") or "")
    can_write = bool(permissions.get("can_write"))
    can_link = bool(permissions.get("can_link_document"))
    terminal = status in {"CLOSED", "NOT_REQUIRED", "CANCELLED"}
    return [
        {"id": "open-case", "label": "Apri fascicolo", "kind": "link", "href": _practice_payload(str(row.get("fascicolo_id") or ""))["href"], "enabled": bool(row.get("fascicolo_id"))},
        {"id": "confirm", "label": "Conferma notifica", "kind": "mutation", "mutation": "confirm", "enabled": can_write and status in {"DETECTED", "NEEDS_REVIEW", "ORIGINAL_ACQUIRED"}, "tone": "primary"},
        {"id": "not-required", "label": "Segna non necessaria", "kind": "mutation", "mutation": "not-required", "enabled": can_write and not terminal, "tone": "neutral"},
        {"id": "assign", "label": "Assegna", "kind": "mutation", "mutation": "assign", "enabled": can_write, "tone": "neutral"},
        {"id": "link-document", "label": "Collega documento", "kind": "mutation", "mutation": "link-document", "enabled": can_link and has_linkables, "disabled_reason": "" if has_linkables else "Nessun documento fascicolo collegabile."},
        {"id": "reconcile", "label": "Riconcilia ricevute", "kind": "mutation", "mutation": "reconcile", "enabled": can_write, "tone": "warning"},
        {"id": "retry", "label": "Riprova job", "kind": "mutation", "mutation": "retry", "enabled": can_write, "tone": "neutral"},
    ]


def _linkable_documents(fascicolo_id: str) -> list[dict[str, str]]:
    if not fascicolo_id:
        return []
    try:
        from web.helpers import get_fascicoli

        fascicolo = get_fascicoli().get(fascicolo_id)
        documents = getattr(fascicolo, "documenti", []) or []
    except Exception:
        return []
    options: list[dict[str, str]] = []
    for document in documents[:80]:
        value = str(getattr(document, "id", "") or getattr(document, "nome_file", "") or "").strip()
        if not value:
            continue
        label = str(getattr(document, "titolo", "") or getattr(document, "nome_file", "") or value).strip()
        options.append(_option(value, label))
    return options


def build_evidence_payload(repo: Any, presidio_id: str) -> dict[str, Any]:
    permissions = presidio_permissions()
    if not permissions["can_view_evidence"]:
        raise PermissionError("Permesso fascicoli.leggi richiesto per vedere le evidenze.")
    repo.get_presidio(presidio_id)
    with repo.connection() as conn:
        rows = [repo._row(row) for row in conn.execute(
            """
            SELECT * FROM pec_legal_notification_evidence
            WHERE tenant_id=? AND presidio_id=?
            ORDER BY created_at DESC, id DESC
            """,
            (repo.tenant_id, presidio_id),
        ).fetchall()]
    return {"ok": True, "items": [_public_evidence(presidio_id, item) for item in rows]}


def _public_evidence(presidio_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    evidence_id = str(row.get("id") or "")
    excerpt = str(row.get("text_excerpt") or "")
    base = f"/api/v1/ui/notifiche-legali/presidi/{quote(presidio_id, safe='')}/evidence/{quote(evidence_id, safe='')}/content"
    etype = str(row.get("evidence_type") or "")
    stype = str(row.get("source_type") or "")
    return {"id": evidence_id, "type_label": EVIDENCE_TYPE_LABELS.get(etype, etype or "Evidenza"), "source_label": EVIDENCE_TYPE_LABELS.get(stype, stype or "Fonte"), "locator_label": str(row.get("source_id") or row.get("message_id") or ""), "text_excerpt": excerpt, "confidence": float(row.get("confidence") or 0.0), "created_at": str(row.get("created_at") or ""), "can_view_content": bool(excerpt), "content_url": base if excerpt else "", "download_url": base + "?download=1" if excerpt else ""}


def evidence_text(repo: Any, presidio_id: str, evidence_id: str) -> str:
    if not presidio_permissions()["can_view_evidence"]:
        raise PermissionError("Permesso fascicoli.leggi richiesto per vedere l'evidenza.")
    repo.get_presidio(presidio_id)
    with repo.connection() as conn:
        row = conn.execute(
            """
            SELECT text_excerpt FROM pec_legal_notification_evidence
            WHERE tenant_id=? AND presidio_id=? AND id=?
            """,
            (repo.tenant_id, presidio_id, evidence_id),
        ).fetchone()
    if row is None:
        raise KeyError("Evidenza non trovata.")
    return str(row["text_excerpt"] or "")


def build_transitions_payload(repo: Any, presidio_id: str) -> dict[str, Any]:
    if not presidio_permissions()["can_read"]:
        raise PermissionError("Permesso messaggi.leggi richiesto.")
    repo.get_presidio(presidio_id)
    with repo.connection() as conn:
        rows = [repo._row(row) for row in conn.execute(
            """
            SELECT * FROM pec_legal_notification_transitions
            WHERE tenant_id=? AND presidio_id=?
            ORDER BY chain_index, occurred_at, id
            """,
            (repo.tenant_id, presidio_id),
        ).fetchall()]
    return {"ok": True, "items": [{"id": str(row.get("id") or ""), "previous_status": str(row.get("previous_status") or "") or None, "next_status": str(row.get("next_status") or ""), "actor_label": str(row.get("actor") or "Sistema"), "reason": str(row.get("reason") or ""), "occurred_at": str(row.get("occurred_at") or "")} for row in rows]}
