from __future__ import annotations

import base64
import json
from collections import defaultdict
from datetime import datetime, time
from typing import Any, Mapping
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from web.services.notification_presidia_runtime import current_actor_id, presidio_permissions, public_permissions

ROME = ZoneInfo("Europe/Rome")

STATUS_LABELS = {
    "DETECTED": "Rilevato",
    "NEEDS_REVIEW": "Da esaminare",
    "ORIGINAL_TO_ACQUIRE": "Originale da acquisire",
    "ORIGINAL_ACQUIRED": "Originale acquisito",
    "NOTIFICATION_CONFIRMED": "Notifica necessaria confermata",
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
    "office_pec_copy": "PEC di cancelleria · copia informativa",
    "portal_original": "Documento PST acquisito nel fascicolo",
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
    "NOTIFICATION_CONFIRMED": "Verifica destinatari e prepara relata",
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
    "PROOF_DEPOSITED": "Nessuna nuova relata: verifica la prova depositata",
    "CLOSED": "Presidio chiuso",
    "NOT_REQUIRED": "Nessuna notifica da eseguire",
    "CANCELLED": "Presidio annullato",
}
NOTIFICATION_CASE_LABELS = {
    "judgment_to_notify_review": "Sentenza da valutare per la notifica",
    "judgment_short_term_review": "Sentenza da valutare per l'impugnazione",
    "legal_notification_review": "Notifica legale da verificare",
    "strategic_notification_review": "Valutazione della notifica necessaria",
}
LEGAL_SOURCE_LABELS = {
    "src.it.l53_1994.art3bis": "Legge 21 gennaio 1994, n. 53, art. 3-bis",
    "src.it.cpc.arts137_149": "Codice di procedura civile, artt. 137-149",
    "src.it.cpc.art133": "Codice di procedura civile, art. 133",
    "src.it.cpc.art285": "Codice di procedura civile, art. 285",
    "src.it.cpc.art325": "Codice di procedura civile, art. 325",
    "src.it.cpc.art326": "Codice di procedura civile, art. 326",
    "src.it.cpc.art327": "Codice di procedura civile, art. 327",
    "src.it.cpc.art429": "Codice di procedura civile, art. 429",
    "src.it.cpc.art431": "Codice di procedura civile, art. 431",
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


def _cursor_encode(cursor: tuple[str, str] | Mapping[str, Any] | None) -> str | None:
    if not cursor:
        return None
    if isinstance(cursor, Mapping):
        updated_at = str(cursor.get("updatedAt") or cursor.get("updated_at") or "")
        cursor_id = str(cursor.get("id") or "")
        if not updated_at or not cursor_id:
            return None
        cursor = (updated_at, cursor_id)
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
    """Espone la pratica in linguaggio operativo, sempre dal repository del tenant attivo."""

    identifier = str(fascicolo_id or "").strip()
    result = {
        "id": identifier,
        "label": "Pratica da completare",
        "client": "",
        "subject": "",
        "rg": "",
        "office": "",
        "href": f"/fascicoli/{quote(identifier, safe='')}" if identifier else "",
    }
    if not identifier:
        return result
    try:
        from web.helpers import get_fascicoli

        fascicolo = get_fascicoli().get(identifier)
    except Exception:
        fascicolo = None
    if fascicolo is None:
        return result

    client = str(getattr(fascicolo, "nome_cliente", "") or "").strip()
    subject = str(
        getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or ""
    ).strip()
    rg = str(getattr(fascicolo, "rg_completo", "") or "").strip()
    if rg.casefold().startswith("rg "):
        rg = rg[3:].strip()
    if not rg:
        number = str(getattr(fascicolo, "numero_rg", "") or "").strip()
        year = str(getattr(fascicolo, "anno_rg", "") or "").strip()
        rg = f"{number}/{year}" if number and year else number
    office = str(getattr(fascicolo, "tribunale", "") or "").strip()
    result.update(
        {
            "label": client or subject or "Pratica da completare",
            "client": client,
            "subject": subject if subject != client else "",
            "rg": rg,
            "office": office,
        }
    )
    return result


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
            source_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or item.get("title") or "").strip()
            labels.append(label or LEGAL_SOURCE_LABELS.get(source_id, "Fonte normativa verificata"))
        else:
            source_id = str(item or "").strip()
            labels.append(LEGAL_SOURCE_LABELS.get(source_id, "Fonte normativa verificata"))
    return [label for label in labels if label][:6]


def _notification_case_label(value: Any) -> str:
    case = str(value or "").strip()
    return NOTIFICATION_CASE_LABELS.get(case.casefold(), "Notifica legale da verificare")


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
        "notification_case_label": _notification_case_label(
            projection.get("notificationCase") or row.get("notification_case")
        ),
        "channel": channel,
        "channel_label": CHANNEL_LABELS.get(channel, channel.upper()),
        "recipients": [{"id": str(item.get("id") or ""), "name": str(item.get("name") or item.get("pec_address") or "Destinatario"), "role": str(item.get("role") or ""), "status_label": _recipient_status_label(item), "delivery_status": str(item.get("delivery_status") or "")} for item in recipients[:4]],
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "priority": str(projection.get("priority") or row.get("priority") or "P1"),
        "confidence": float(projection.get("confidence") or row.get("confidence") or 0.0),
        "detection_reason": str(row.get("detection_reason") or ""),
        "rule_label": "Valutazione guidata da fonti normative",
        "legal_sources": _legal_sources(row),
        "next_action": NEXT_ACTIONS.get(status, "Consulta il presidio"),
        "human_review_required": bool(projection.get("humanReviewRequired") or row.get("human_review_required")),
        "legacy_assumed_handled": bool(projection.get("legacyAssumedHandled") or row.get("legacy_assumed_handled")),
        "assigned_user": _assignee(str(projection.get("assignedUserId") or row.get("assigned_user_id") or ""), assignees),
        "updated_at": str(projection.get("updatedAt") or row.get("updated_at") or ""),
    }


def _status_facets(repo: Any) -> dict[str, int]:
    _reconcile_open_presidia_with_fascicolo_proof(repo)
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


def _reconcile_open_presidia_with_fascicolo_proof(repo: Any, *, limit: int = 50) -> None:
    permissions = presidio_permissions()
    if not permissions.get("can_write"):
        return
    with repo.connection() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM pec_legal_notification_presidia
            WHERE tenant_id=?
              AND status IN (
                'DETECTED','NEEDS_REVIEW','ORIGINAL_TO_ACQUIRE','ORIGINAL_ACQUIRED',
                'NOTIFICATION_CONFIRMED','RECIPIENTS_TO_VERIFY','READY_FOR_RELATA',
                'RELATA_DRAFTED','RELATA_SIGNED','READY_TO_SEND','SENT_WAITING_RAC',
                'RAC_RECEIVED','PARTIAL_DELIVERY','DELIVERY_COMPLETE','PROOF_TO_DEPOSIT',
                'LEGACY_REVIEW_REQUIRED'
              )
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (repo.tenant_id, int(limit)),
        ).fetchall()
    if not rows:
        return
    try:
        from web.services.notification_presidia_fascicolo_reconciliation import (
            reconcile_presidio_with_fascicolo_notification_proof,
        )

        actor = current_actor_id()
        for row in rows:
            reconcile_presidio_with_fascicolo_notification_proof(repo, str(row["id"]), actor=actor)
    except Exception:
        return


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


def _has_linked_portal_document(docs: list[Mapping[str, Any]]) -> bool:
    return any(
        str(item.get("document_role") or "") == "portal_original"
        and bool(str(item.get("fascicolo_document_id") or "").strip())
        and bool(item.get("authoritative"))
        for item in docs
    )


def _try_link_existing_pst_document(
    repo: Any,
    row: Mapping[str, Any],
    docs: list[Mapping[str, Any]],
    portal_context: Mapping[str, Any],
) -> bool:
    if _has_linked_portal_document(docs):
        return False
    if not str(row.get("fascicolo_id") or "").strip():
        return False
    permissions = presidio_permissions()
    if not permissions.get("can_write"):
        return False
    try:
        from web.services.pst_original_presidio_runtime import (
            link_existing_pst_originals_for_current_tenant,
        )

        report = link_existing_pst_originals_for_current_tenant(
            repo,
            presidio=row,
            actor=current_actor_id(),
            portal_context=portal_context,
        )
    except Exception:
        return False
    return bool(report.get("collegati"))


def _summary_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "fascicoloId": row.get("fascicolo_id"),
        "status": row.get("status"),
        "priority": row.get("priority"),
        "confidence": row.get("confidence"),
        "humanReviewRequired": row.get("human_review_required"),
        "notificationCase": row.get("notification_case"),
        "channel": row.get("channel"),
        "assignedUserId": row.get("assigned_user_id"),
        "legacyAssumedHandled": row.get("legacy_assumed_handled"),
        "sourceEffectiveAt": row.get("source_effective_at"),
        "explicitDueAt": row.get("explicit_due_at"),
        "updatedAt": row.get("updated_at"),
    }


def build_presidio_detail_payload(repo: Any, presidio_id: str) -> dict[str, Any]:
    permissions = presidio_permissions()
    if not permissions["can_read"]:
        raise PermissionError("Permesso messaggi.leggi richiesto.")
    row, docs, recipients = _detail_rows(repo, presidio_id)
    assignees = _user_options()
    detail = _summary(_summary_projection(row), row, recipients, docs, assignees)
    practice = detail.get("practice") if isinstance(detail.get("practice"), Mapping) else {}
    detail["recipients"] = [_public_recipient(item) for item in recipients]
    fascicolo_id = str(row.get("fascicolo_id") or "")
    source_message_id = str(row.get("source_message_id") or "")
    portal_context = _pec_portal_acquisition_context(
        repo,
        source_message_id,
        expected_rg=str(practice.get("rg") or ""),
    )
    if _try_link_existing_pst_document(repo, row, docs, portal_context):
        row, docs, recipients = _detail_rows(repo, presidio_id)
        detail = _summary(_summary_projection(row), row, recipients, docs, assignees)
        practice = detail.get("practice") if isinstance(detail.get("practice"), Mapping) else {}
        detail["recipients"] = [_public_recipient(item) for item in recipients]
        fascicolo_id = str(row.get("fascicolo_id") or "")
        source_message_id = str(row.get("source_message_id") or "")
    try:
        from web.services.notification_presidia_fascicolo_reconciliation import (
            reconcile_presidio_with_fascicolo_notification_proof,
        )

        report = reconcile_presidio_with_fascicolo_notification_proof(
            repo,
            presidio_id,
            actor=current_actor_id(),
        )
        if report.get("status") != str(row.get("status") or ""):
            row, docs, recipients = _detail_rows(repo, presidio_id)
            detail = _summary(_summary_projection(row), row, recipients, docs, assignees)
            practice = detail.get("practice") if isinstance(detail.get("practice"), Mapping) else {}
            detail["recipients"] = [_public_recipient(item) for item in recipients]
            fascicolo_id = str(row.get("fascicolo_id") or "")
            source_message_id = str(row.get("source_message_id") or "")
    except Exception:
        pass
    has_portal_original = _has_linked_portal_document(docs)
    detail["documents"] = [
        _public_document(
            item,
            fascicolo_id=fascicolo_id,
            source_message_id=source_message_id,
            has_portal_original=has_portal_original,
            practice=practice,
            portal_context=portal_context,
        )
        for item in docs
    ]
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


def _pec_field_value(fields: Mapping[str, Any], key: str) -> str:
    raw = fields.get(key)
    if isinstance(raw, Mapping):
        raw = raw.get("value")
    return str(raw or "").strip()


def _pec_portal_acquisition_context(
    repo: Any,
    source_message_id: str,
    *,
    expected_rg: str = "",
) -> dict[str, str]:
    """Ricava dal record PEC già indicizzato i parametri ministeriali certi."""

    message_id = str(source_message_id or "").strip()
    if not message_id:
        return {}
    try:
        with repo.connection() as conn:
            row = conn.execute(
                """
                SELECT parsed.parsed_json
                FROM pec_parsed_versions AS parsed
                JOIN pec_messages AS message ON message.id=parsed.message_id
                WHERE message.tenant_id=? AND message.id=?
                ORDER BY parsed.version DESC
                LIMIT 1
                """,
                (repo.tenant_id, message_id),
            ).fetchone()
        parsed = json.loads(str(row["parsed_json"] or "{}")) if row else {}
    except Exception:
        return {}
    if not isinstance(parsed, Mapping):
        return {}

    fields = parsed.get("fields") if isinstance(parsed.get("fields"), Mapping) else {}
    workflow = (
        parsed.get("legal_workflow")
        if isinstance(parsed.get("legal_workflow"), Mapping)
        else {}
    )
    registries = workflow.get("registri") if isinstance(workflow.get("registri"), list) else []
    expected_number, separator, expected_year = str(expected_rg or "").partition("/")
    selected_registry: Mapping[str, Any] = {}
    for item in registries:
        if not isinstance(item, Mapping):
            continue
        if separator and (
            str(item.get("numero") or "").lstrip("0") == expected_number.strip().lstrip("0")
            and str(item.get("anno") or "").strip() == expected_year.strip()
        ):
            selected_registry = item
            break
        if not selected_registry:
            selected_registry = item

    registry = str(
        selected_registry.get("registro_normalizzato")
        or selected_registry.get("suffisso")
        or ""
    ).strip()
    table = str(selected_registry.get("tabella_ministeriale") or "").strip()
    raw_matter = str(selected_registry.get("materia") or "").strip()
    schema = raw_matter.casefold()
    matter = raw_matter
    service = ""
    normalized_profile = " ".join((registry, table, raw_matter)).upper()
    if "LAV" in normalized_profile or "LAVORO" in normalized_profile:
        schema = "lavoro"
        matter = "Lavoro e previdenza"
        registry = registry or "LAV"
        table = table or "SICID_LAVORO"
        service = "JPW_SIL_DISTR"
    elif "VOLONT" in normalized_profile or "SIVG" in normalized_profile:
        schema = "volontaria"
        matter = "Volontaria giurisdizione"
        service = "JPW_SIVG"
    elif "GDP" in normalized_profile or "SIGP" in normalized_profile:
        schema = "giudice di pace"
        matter = "Giudice di pace"
        service = "JPW_SIGP"
    elif "CASS" in normalized_profile and "PEN" in normalized_profile:
        schema = "cassazione penale"
        matter = "Cassazione penale"
        service = "JPW_CASSPE"
    elif "CASS" in normalized_profile:
        schema = "cassazione civile"
        matter = "Cassazione civile"
        service = "JPW_CASSCI"
    elif "SIECIC" in normalized_profile or "ESECU" in normalized_profile:
        schema = schema or "esecuzioni"
        matter = matter or "Esecuzioni e concorsuali"
        service = "JPW_SIECIC"
    elif registry or table:
        schema = schema or "civile"
        matter = matter or "Civile contenzioso"
        service = "JPW_SICID"

    context = {
        "ufficio": _pec_field_value(fields, "ufficio_giudiziario"),
        "ufficio_codice": _pec_field_value(fields, "codice_ufficio"),
        "numero": str(selected_registry.get("numero") or "").strip(),
        "anno": str(selected_registry.get("anno") or "").strip(),
        "assistito": _pec_field_value(fields, "cliente")
        or _pec_field_value(fields, "parte_processuale"),
        "schema": schema,
        "materia": matter,
        "registro": registry,
        "tabella_ministeriale": table,
        "servizio_pst_preferito": service,
        "registro_portale": registry,
    }
    event_text = _pec_field_value(fields, "evento_processuale").casefold()
    for document_type in ("sentenza", "ordinanza", "decreto", "verbale", "provvedimento"):
        if document_type in event_text:
            context["tipo_documento"] = document_type
            break
    return {key: value for key, value in context.items() if value}


def _original_acquisition_href(
    fascicolo_id: str,
    source_message_id: str,
    practice: Mapping[str, Any] | None = None,
    portal_context: Mapping[str, Any] | None = None,
) -> str:
    """Riusa il percorso React governato del monitor fascicolo per acquisire l'originale."""

    identifier = str(fascicolo_id or "").strip()
    if not identifier:
        return ""
    params = {
        "id_fasc": identifier,
        "fascicolo_id": identifier,
        "mode": "update_existing",
        "focus": "documenti",
        "single_document": "1",
        "pec_id": str(source_message_id or "").strip(),
        "non_duplicare_documenti": "1",
        "fase_successiva": "relata_notifica",
    }
    practice_data = practice or {}
    portal_data = portal_context or {}
    rg = str(practice_data.get("rg") or "").strip()
    numero, separator, anno = rg.partition("/")
    if separator:
        params["numero"] = numero.strip()
        params["anno"] = anno.strip()
    office = str(practice_data.get("office") or "").strip()
    client = str(practice_data.get("client") or "").strip()
    subject = str(practice_data.get("subject") or "").strip()
    if office:
        params["ufficio"] = office
    if client:
        params["assistito"] = client
    if subject:
        params["oggetto"] = subject
    for key in (
        "ufficio",
        "ufficio_codice",
        "numero",
        "anno",
        "assistito",
        "controparte",
        "cf",
        "schema",
        "materia",
        "registro",
        "tabella_ministeriale",
        "servizio_pst_preferito",
        "registro_portale",
        "tipo_documento",
    ):
        value = str(portal_data.get(key) or "").strip()
        if value:
            params[key] = value
    return f"/portali/pst/acquisizione?{urlencode(params)}#acquisizione-portale"


def _public_document(
    row: Mapping[str, Any],
    *,
    fascicolo_id: str = "",
    source_message_id: str = "",
    has_portal_original: bool = False,
    practice: Mapping[str, Any] | None = None,
    portal_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    role = str(row.get("document_role") or "")
    fascicolo_document_id = str(row.get("fascicolo_document_id") or "").strip()
    public_id = fascicolo_document_id or str(row.get("id") or "").strip()
    name = str(row.get("original_filename") or "Documento collegato").strip()
    viewer_url = ""
    download_url = ""
    if fascicolo_id and fascicolo_document_id:
        base = (
            f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/"
            f"{quote(fascicolo_document_id, safe='')}"
        )
        viewer_url = f"{base}/visualizza"
        download_url = f"{base}/scarica"
    elif role == "office_pec_copy" and source_message_id and name:
        base = f"/api/v1/ui/email/source/{quote(source_message_id, safe='')}"
        viewer_url = f"{base}?{urlencode({'name': name})}"
        download_url = f"{base}?{urlencode({'name': name, 'download': '1'})}"
    authoritative = bool(
        role == "portal_original"
        and fascicolo_document_id
        and row.get("authoritative")
    )
    acquisition_required = role == "office_pec_copy" and not has_portal_original
    return {
        "id": public_id,
        "name": name,
        "role_label": DOCUMENT_ROLE_LABELS.get(role, role or "Documento"),
        "version_label": f"Versione {row.get('document_version') or '1'}",
        "authoritative": authoritative,
        "original_acquisition_required": acquisition_required,
        "original_acquisition_url": (
            _original_acquisition_href(
                fascicolo_id,
                source_message_id,
                practice,
                portal_context,
            )
            if acquisition_required
            else ""
        ),
        "viewer_url": viewer_url,
        "download_url": download_url,
    }


def _available_actions(row: Mapping[str, Any], permissions: Mapping[str, bool], has_linkables: bool) -> list[dict[str, Any]]:
    status = str(row.get("status") or "")
    can_write = bool(permissions.get("can_write"))
    can_link = bool(permissions.get("can_link_document"))
    terminal = status in {"CLOSED", "NOT_REQUIRED", "CANCELLED"}
    actions = [
        {"id": "open-case", "label": "Apri fascicolo", "kind": "link", "href": _practice_payload(str(row.get("fascicolo_id") or ""))["href"], "enabled": bool(row.get("fascicolo_id"))},
        {
            "id": "confirm",
            "label": "Conferma notifica",
            "kind": "mutation",
            "mutation": "confirm",
            "enabled": can_write and status in {"DETECTED", "NEEDS_REVIEW", "ORIGINAL_ACQUIRED"},
            "disabled_reason": (
                "Decisione già registrata. Puoi modificarla qui sotto."
                if status == "NOTIFICATION_CONFIRMED"
                else "Prova notifica già depositata nel fascicolo. Non preparare una nuova relata."
                if status == "PROOF_DEPOSITED"
                else ""
            ),
            "tone": "primary",
        },
        {"id": "not-required", "label": "Segna non necessaria", "kind": "mutation", "mutation": "not-required", "enabled": can_write and not terminal, "tone": "neutral"},
        {"id": "assign", "label": "Assegna", "kind": "mutation", "mutation": "assign", "enabled": can_write, "tone": "neutral"},
        {"id": "link-document", "label": "Collega prova, ricevuta o documento", "kind": "mutation", "mutation": "link-document", "enabled": can_link and has_linkables, "disabled_reason": "" if has_linkables else "Nessuna prova, ricevuta o documento del fascicolo collegabile."},
        {"id": "reconcile", "label": "Riconcilia ricevute", "kind": "mutation", "mutation": "reconcile", "enabled": can_write, "tone": "warning"},
        {"id": "retry", "label": "Riprova job", "kind": "mutation", "mutation": "retry", "enabled": can_write, "tone": "neutral"},
    ]
    if status == "NOTIFICATION_CONFIRMED":
        actions.insert(
            2,
            {
                "id": "revise-decision",
                "label": "Modifica decisione",
                "kind": "mutation",
                "mutation": "revise-decision",
                "enabled": can_write,
                "disabled_reason": "" if can_write else "Permesso di modifica richiesto.",
                "tone": "neutral",
            },
        )
    return actions


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
        name = str(
            getattr(document, "nome", "")
            or getattr(document, "nome_originale", "")
            or ""
        ).strip()
        value = str(getattr(document, "id", "") or name).strip()
        if not value:
            continue
        tipo = getattr(document, "tipo", "")
        tipo_value = str(getattr(tipo, "value", tipo) or "").strip()
        tipo_label = tipo_value.replace("_", " ").capitalize()
        label = name or "Documento senza nome"
        if tipo_label and tipo_label.casefold() not in label.casefold():
            label = f"{label} · {tipo_label}"
        options.append({"value": value, "label": label, "document_name": name or label})
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
