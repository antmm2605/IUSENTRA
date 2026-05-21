"""Bridge dati per le pagine React Email PEC ed email ordinaria.

La funzione costruisce payload in sola lettura sopra GestioneEmailRicevute,
riusando le caselle locali e i servizi Flask auditati per le azioni operative.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pct.email_client import CartellaEmail, GestioneEmailRicevute, StatoEmail
from pct.pec_pipeline import (
    AttachmentPayload,
    build_validation_report,
    classify_attachment,
    detect_pec_legal_context,
    field_result,
)

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _safe_text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split())
    return text or fallback


def _short_text(value: Any, limit: int = 180) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _pec_quality_label(value: str) -> tuple[str, str]:
    raw = str(value or "").strip().lower()
    if raw == "verde":
        return "Qualità verde", "success"
    if raw == "giallo":
        return "Qualità da presidiare", "warning"
    if raw == "rosso":
        return "Qualità critica", "danger"
    if raw in {"da_controllare", "provvisorio", "provisional"}:
        return "Controllo da completare", "warning"
    return "Da controllare", "neutral"


def _pec_signature_label(value: str) -> tuple[str, str]:
    raw = str(value or "").strip().lower()
    if raw == "valida":
        return "Firme valide", "success"
    if raw in {"non_valida", "errore", "scaduta"}:
        return "Firme da verificare", "danger"
    if raw == "assente":
        return "Firma assente", "warning"
    if raw == "non_applicabile":
        return "Firma non richiesta", "neutral"
    return "Firme non verificate", "neutral"


def _pec_audit_db_path(db_path: str) -> Path:
    return Path(db_path).expanduser().resolve().parent / "pec_audit.sqlite"


def _pec_audit_summaries(db_path: str, emails: list[Any], *, tenant_id: str = "default", include_telematic: bool = True) -> dict[str, dict[str, Any]]:
    if not include_telematic:
        return {}
    audit_db = _pec_audit_db_path(db_path)
    if not audit_db.exists():
        return {}
    headers = [str(getattr(email_obj, "message_id", "") or "").strip() for email_obj in emails]
    try:
        from pct.pec_pipeline import PecAuditRepository

        return PecAuditRepository(audit_db, tenant_id=tenant_id).summaries_by_header_message_ids(headers)
    except Exception:
        return {}


def _pec_audit_all_summaries(db_path: str, *, tenant_id: str = "default", include_telematic: bool = True) -> list[dict[str, Any]]:
    if not include_telematic:
        return []
    audit_db = _pec_audit_db_path(db_path)
    if not audit_db.exists():
        return []
    try:
        from pct.pec_pipeline import PecAuditRepository

        repo = PecAuditRepository(audit_db, tenant_id=tenant_id)
        summaries: list[dict[str, Any]] = []
        for row in repo.list_messages(limit=200):
            detail = repo.get_message_detail(str(row.get("id") or ""))
            message = detail.get("message") if isinstance(detail.get("message"), dict) else {}
            parsed = detail.get("parsed") if isinstance(detail.get("parsed"), dict) else {}
            summaries.append(
                {
                    "id": row.get("id") or message.get("id") or "",
                    "message_id_header": message.get("message_id_header") or row.get("message_id_header") or "",
                    "quality_status": message.get("quality_status") or row.get("quality_status") or "",
                    "signature_status": message.get("signature_status") or row.get("signature_status") or "",
                    "linked_fascicolo_id": message.get("linked_fascicolo_id") or row.get("linked_fascicolo_id") or "",
                    "linked_fascicolo_score": message.get("linked_fascicolo_score") or row.get("linked_fascicolo_score") or 0,
                    "received_at": message.get("received_at") or row.get("received_at") or "",
                    "metadata": message.get("metadata") or row.get("metadata") or {},
                    "fields": parsed.get("fields") or {},
                    "body_text": parsed.get("body_text") or "",
                    "validation_report": detail.get("validation_report") or {},
                    "fascicolo_link": detail.get("fascicolo_link") or {},
                    "attachments": detail.get("attachments") or [],
                }
            )
        return summaries
    except Exception:
        return []


def _pec_audit_payload(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary:
        return None
    quality_label, quality_tone = _pec_quality_label(str(summary.get("quality_status") or ""))
    signature_label, signature_tone = _pec_signature_label(str(summary.get("signature_status") or ""))
    pec_id = str(summary.get("id") or "")
    report = summary.get("validation_report") if isinstance(summary.get("validation_report"), dict) else {}
    semantic_context = report.get("semantic_context") if isinstance(report.get("semantic_context"), dict) else {}
    link = summary.get("fascicolo_link") if isinstance(summary.get("fascicolo_link"), dict) else {}
    fields = summary.get("fields") if isinstance(summary.get("fields"), dict) else {}
    attachments = summary.get("attachments") if isinstance(summary.get("attachments"), list) else []
    provisional = bool(summary.get("provisional"))
    source_email_id = _safe_text(summary.get("source_email_id"))
    run_audit_href = "/api/pec/fetch?limit=50" if provisional else ""
    return {
        "id": pec_id,
        "qualityStatus": str(summary.get("quality_status") or ""),
        "qualityLabel": quality_label,
        "qualityTone": quality_tone,
        "signatureStatus": str(summary.get("signature_status") or ""),
        "signatureLabel": signature_label,
        "signatureTone": signature_tone,
        "linkedFascicoloId": str(summary.get("linked_fascicolo_id") or ""),
        "linkedFascicoloScore": float(summary.get("linked_fascicolo_score") or 0),
        "mimeHref": "" if provisional else f"/api/pec/messages/{quote(pec_id, safe='')}/mime" if pec_id else "",
        "validationIssues": list(report.get("issues") or []),
        "validationSeverity": str(report.get("severity") or ""),
        "eventType": str(report.get("event_type") or ""),
        "depositLifecycle": report.get("deposit_lifecycle") if isinstance(report.get("deposit_lifecycle"), dict) else {},
        "semanticContext": semantic_context,
        "normativeReferences": list(report.get("normative_references") or semantic_context.get("normative_references") or []),
        "agentQuestions": list(report.get("agent_questions") or semantic_context.get("agent_questions") or []),
        "recommendedActions": list(report.get("recommended_actions") or semantic_context.get("recommended_actions") or []),
        "confidence": fields,
        "candidates": list(link.get("candidates") or []),
        "attachments": [
            {
                "name": _safe_text(item.get("filename") if isinstance(item, dict) else ""),
                "classification": _safe_text(item.get("classification") if isinstance(item, dict) else ""),
                "classificationScore": float((item or {}).get("classification_score") or 0) if isinstance(item, dict) else 0,
                "ocrCoverage": float((item or {}).get("ocr_coverage") or 0) if isinstance(item, dict) else 0,
                "signatureStatus": _safe_text(item.get("signature_status") if isinstance(item, dict) else ""),
            }
            for item in attachments
            if isinstance(item, dict)
        ],
        "quickActions": {
            "saveMatter": "" if provisional else f"/api/pec/messages/{quote(pec_id, safe='')}/salva-fascicolo" if pec_id else "",
            "requestMissingAttachment": "" if provisional else f"/api/pec/messages/{quote(pec_id, safe='')}/richiedi-allegato-mancante" if pec_id else "",
            "scheduleDeadline": "" if provisional else f"/api/pec/messages/{quote(pec_id, safe='')}/schedula-scadenza" if pec_id else "",
            "openMime": "" if provisional else f"/api/pec/messages/{quote(pec_id, safe='')}/mime" if pec_id else "",
            "runAudit": run_audit_href,
        },
        "persisted": not provisional,
        "storageLabel": "MIME originale da acquisire" if provisional else "MIME originale conservato",
        "storageTone": "warning" if provisional else "success",
        "sourceEmailId": source_email_id,
    }


def _address_value(value: Any) -> dict[str, str]:
    raw = _safe_text(value)
    if "@" in raw and "<" in raw and ">" in raw:
        name = raw.split("<", 1)[0].strip().strip('"')
        email = raw.split("<", 1)[1].split(">", 1)[0].strip().lower()
        return {"name": name, "email": email}
    return {"name": "", "email": raw.lower() if "@" in raw else raw}


def _receipt_type_from_legacy_email(email_obj: Any, context_text: str) -> str:
    haystack = context_text.lower()
    pct = str(getattr(email_obj, "stato_pct", "") or "").upper()
    if "accettazione deposito" in haystack or pct == "ACCETTATO_PEC":
        return "accettazione_deposito"
    if "avvenuta consegna" in haystack or "ricevuta di consegna" in haystack or pct == "CONSEGNATO":
        return "avvenuta_consegna"
    if "esito controlli" in haystack or "controlli automatici" in haystack or "CONTROLLI" in pct:
        return "esito_controlli_deposito"
    if "rifiuto" in haystack or "RIFIUT" in pct:
        return "rifiuto_deposito"
    if "consegna" in haystack:
        return "consegna"
    if "accettazione" in haystack:
        return "accettazione"
    return ""


def _first_protocol_candidate(text: str) -> str:
    import re

    patterns = (
        r"\bR\.?\s*G\.?\s*(?:n\.?\s*)?(\d{1,7}\s*/\s*\d{4})\b",
        r"\bRG\s+(\d{1,7}\s*/\s*\d{4})\b",
        r"\bprotocollo\s+([A-Z0-9./-]{4,})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return _safe_text(match.group(1)).replace(" ", "")
    return ""


def _legacy_attachment_audit_rows(email_obj: Any, context_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, info in enumerate(list(getattr(email_obj, "allegati", []) or [])):
        if not isinstance(info, dict):
            continue
        name = _safe_text(info.get("nome") or info.get("nome_file") or f"allegato-{index + 1}")
        mime = _safe_text(info.get("mime") or info.get("content_type") or "application/octet-stream")
        size = int(info.get("size") or info.get("dimensione") or 0)
        classification, score, reason = classify_attachment(
            AttachmentPayload(index=index, filename=name, content_type=mime, data=b""),
            context_text,
        )
        if score < 0.7 and classification not in {"daticert", "eml"}:
            classification = "da confermare"
        rows.append(
            {
                "index": index,
                "filename": name,
                "classification": classification,
                "classification_score": round(score, 3),
                "classification_reason": reason,
                "ocr_coverage": 0.0,
                "signature_status": "non_verificata",
                "size_bytes": size,
                "content_type": mime,
            }
        )
    return rows


def _provisional_pec_audit_summary(email_obj: Any, *, include_telematic: bool = True) -> dict[str, Any] | None:
    """Costruisce il presidio UI per PEC storiche non ancora migrate in pec_audit.sqlite."""

    if not include_telematic:
        return None
    subject = _safe_text(getattr(email_obj, "oggetto", ""))
    body = _safe_text(getattr(email_obj, "corpo_testo", "") or getattr(email_obj, "corpo_html", ""))
    sender = _safe_text(getattr(email_obj, "mittente", "") or getattr(email_obj, "mittente_nome", ""))
    recipients = _safe_text(getattr(email_obj, "destinatari", ""))
    context_text = " ".join(
        item
        for item in (
            subject,
            body,
            sender,
            recipients,
            _safe_text(getattr(email_obj, "stato_pct", "")),
            " ".join(_safe_text(item.get("nome") or item.get("nome_file")) for item in list(getattr(email_obj, "allegati", []) or []) if isinstance(item, dict)),
        )
        if item
    )
    semantic_context = detect_pec_legal_context(context_text)
    is_certified = bool(
        str(getattr(email_obj, "message_id", "") or "").strip()
        or "postacert" in context_text.lower()
        or "daticert" in context_text.lower()
        or "posta certificata" in subject.lower()
        or bool(getattr(email_obj, "e_pst", False))
    )
    has_telematic_signal = bool(semantic_context or getattr(email_obj, "e_pst", False) or "deposito" in context_text.lower() or "notific" in context_text.lower())
    if not (is_certified or has_telematic_signal):
        return None
    attachments = _legacy_attachment_audit_rows(email_obj, context_text)
    protocol = _first_protocol_candidate(context_text)
    receipt_type = _receipt_type_from_legacy_email(email_obj, context_text)
    sent_date = str(getattr(email_obj, "data", "") or getattr(email_obj, "timestamp", "") or getattr(email_obj, "ricevuta_il", "") or "")
    fields = {
        "mittente": field_result(
            _address_value(sender),
            0.72 if sender else 0.18,
            "Letto dallo storico della casella PEC; confermare sul MIME originale quando il controllo audit-grade viene eseguito.",
            ["email:mittente"] if sender else [],
        ),
        "data_invio": field_result(
            sent_date,
            0.68 if sent_date else 0.18,
            "Data disponibile nella scheda email; da confermare con header e dati di certificazione.",
            ["email:data"] if sent_date else [],
        ),
        "data_consegna": field_result(
            "",
            0.18,
            "Dato non confermato: serve il MIME originale o il daticert.xml.",
            [],
        ),
        "tipo_ricevuta": field_result(
            receipt_type,
            0.62 if receipt_type else 0.2,
            "Tipo ricevuta dedotto da oggetto, corpo o stato PCT storico.",
            ["email:oggetto", "email:stato_pct"] if receipt_type else [],
        ),
        "protocollo": field_result(
            protocol,
            0.7 if protocol else 0.2,
            "Protocollo/RG cercato nel testo visibile della PEC.",
            ["pattern:RG/protocollo"] if protocol else [],
        ),
        "pec_certificata": field_result(
            is_certified,
            0.76 if is_certified else 0.25,
            "Indicatori PEC/PST presenti nella scheda messaggio.",
            ["message-id", "posta-certificata", "pst"] if is_certified else [],
        ),
        "contesto_legale": field_result(
            semantic_context,
            float(semantic_context.get("confidence") or 0.0) if semantic_context else 0.28,
            "Contesto processuale riconosciuto sul testo visibile della PEC." if semantic_context else "Contesto processuale non forte sul testo visibile.",
            semantic_context.get("features") or [] if semantic_context else [],
        ),
    }
    parsed = {
        "headers": {
            "message_id": str(getattr(email_obj, "message_id", "") or ""),
            "subject": subject,
            "from": [_address_value(sender)] if sender else [],
            "to": [_address_value(recipients)] if recipients else [],
            "date": sent_date,
        },
        "fields": fields,
        "semantic_context": semantic_context,
        "body": {"text": body},
    }
    report = build_validation_report(parsed, attachments)
    report.setdefault("issues", [])
    report["issues"] = [
        {
            "code": "audit_storage_pending",
            "severity": "warning",
            "blocking": False,
            "title": "Conservazione audit-grade da eseguire",
            "detail": "La PEC è visibile nello storico email, ma il MIME originale non risulta ancora nella cassaforte PEC audit-grade. Usa il controllo per acquisire il MIME originale da IMAP.",
        },
        *list(report.get("issues") or []),
    ]
    report["severity"] = "warning" if report.get("severity") in {"", "ok"} else report.get("severity")
    quality_status = "giallo" if has_telematic_signal else "da_controllare"
    signature_status = "non_applicabile"
    if any(str(item.get("filename") or "").lower().endswith((".p7m", ".pdf")) for item in attachments):
        signature_status = "non_verificata"
    return {
        "id": f"email:{getattr(email_obj, 'id', '')}",
        "message_id_header": str(getattr(email_obj, "message_id", "") or ""),
        "quality_status": quality_status,
        "signature_status": signature_status,
        "linked_fascicolo_id": "",
        "linked_fascicolo_score": 0,
        "received_at": sent_date,
        "metadata": {"headers": {"subject": subject, "from": sender, "to": recipients}},
        "fields": fields,
        "body_text": body,
        "validation_report": report,
        "fascicolo_link": {},
        "attachments": attachments,
        "provisional": True,
        "source_email_id": str(getattr(email_obj, "id", "") or ""),
    }


def _pec_audit_text(summary: dict[str, Any]) -> str:
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    headers = metadata.get("headers") if isinstance(metadata.get("headers"), dict) else {}
    report = summary.get("validation_report") if isinstance(summary.get("validation_report"), dict) else {}
    parts = [
        headers.get("subject"),
        headers.get("from"),
        summary.get("body_text"),
        report.get("event_type"),
        " ".join(str(item.get("title") or "") for item in list(report.get("issues") or []) if isinstance(item, dict)),
    ]
    return " ".join(_safe_text(item).lower() for item in parts if _safe_text(item))


def _pec_audit_matches_filters(
    summary: dict[str, Any],
    *,
    folder: str,
    query: str,
    stato: str,
    solo_pst: bool,
    con_allegati: bool,
    stato_pct: str,
) -> bool:
    if folder != CartellaEmail.INBOX:
        return False
    if stato == StatoEmail.NON_LETTA:
        return False
    attachments = list(summary.get("attachments") or [])
    if con_allegati and not attachments:
        return False
    if query and query.strip().lower() not in _pec_audit_text(summary):
        return False
    report = summary.get("validation_report") if isinstance(summary.get("validation_report"), dict) else {}
    if stato_pct:
        haystack = " ".join(
            [
                str(report.get("event_type") or ""),
                str(report.get("severity") or ""),
                str(summary.get("quality_status") or ""),
                str(summary.get("signature_status") or ""),
            ]
        ).lower()
        if stato_pct.lower() not in haystack:
            return False
    return True


def _pec_audit_virtual_row(summary: dict[str, Any], *, base_path: str = "/email") -> dict[str, Any]:
    pec_id = str(summary.get("id") or "")
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    headers = metadata.get("headers") if isinstance(metadata.get("headers"), dict) else {}
    report = summary.get("validation_report") if isinstance(summary.get("validation_report"), dict) else {}
    subject = _safe_text(headers.get("subject"), "(nessun oggetto)")
    sender = _safe_text(headers.get("from"))
    issues = [item for item in list(report.get("issues") or []) if isinstance(item, dict)]
    preview = _short_text(
        summary.get("body_text")
        or "; ".join(_safe_text(item.get("title")) for item in issues if _safe_text(item.get("title")))
        or "PEC conservata nella pipeline audit-grade.",
        220,
    )
    base = "/" + str(base_path or "/email").strip("/")
    encoded = quote(pec_id, safe="")
    audit_payload = _pec_audit_payload(summary) or {}
    return {
        "id": f"pec-audit:{pec_id}",
        "folder": CartellaEmail.INBOX,
        "status": StatoEmail.LETTA,
        "sender": sender,
        "senderName": sender,
        "recipients": _safe_text(headers.get("to")),
        "subject": subject,
        "preview": preview,
        "timestamp": str(summary.get("received_at") or ""),
        "timeLabel": _format_time(summary.get("received_at")),
        "unread": False,
        "isPst": True,
        "pctStatus": _safe_text(report.get("event_type")),
        "attachmentCount": len(list(summary.get("attachments") or [])),
        "origin": "controllo PEC audit-grade",
        "detailHref": f"/api/pec/messages/{encoded}/mime",
        "operationalHref": f"{base}/?pec_audit={encoded}",
        "replyHref": "",
        "trashHref": "",
        "restoreHref": "",
        "deleteHref": "",
        "markReadHref": "",
        "markUnreadHref": "",
        "tone": audit_payload.get("qualityTone") or "neutral",
        "auditOnly": True,
        "pecAudit": audit_payload,
    }


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            if parsed.tzinfo:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return None


def _format_time(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    today = date.today()
    if parsed.date() == today:
        return parsed.strftime("%H:%M")
    if parsed.date() == today - timedelta(days=1):
        return "ieri"
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]}"
    return parsed.strftime("%d/%m/%Y")


def _normalise_folder(value: Any) -> str:
    raw = _enum_value(value).upper()
    if raw == CartellaEmail.INVIATI or raw in {"SENT", "SENT ITEMS", "POSTA INVIATA"}:
        return CartellaEmail.INVIATI
    if raw == CartellaEmail.CESTINO or raw in {"TRASH", "DELETED", "DELETED ITEMS", "POSTA ELIMINATA"}:
        return CartellaEmail.CESTINO
    return CartellaEmail.INBOX


def _tone(email_obj: Any, *, include_telematic: bool = True) -> str:
    pct = str(getattr(email_obj, "stato_pct", "") or "").upper()
    if include_telematic and any(marker in pct for marker in ("RIFIUT", "ERRORE")):
        return "danger"
    if include_telematic and any(marker in pct for marker in ("WARN", "ANOMALIA")):
        return "warning"
    if include_telematic and pct:
        return "primary"
    if include_telematic and getattr(email_obj, "e_pst", False):
        return "purple"
    if _normalise_folder(getattr(email_obj, "cartella", "")) == CartellaEmail.INVIATI:
        return "success"
    return "neutral"


def _sync_inviati_da_messaggi(gestore: GestioneEmailRicevute, messaggi_db: str) -> None:
    """Allinea le email inviate da GestioneMessaggi, come fa la vista operativa."""
    if not messaggi_db:
        return
    try:
        from pct.messaggi import CanaleMsggio, GestioneMessaggi

        manager = GestioneMessaggi(config=None, db_path=messaggi_db)
        inviati = []
        for msg in manager.tutti(canale=CanaleMsggio.EMAIL):
            stato = _enum_value(getattr(msg, "stato", ""))
            if stato in {"INVIATO", "CONSEGNATO", "LETTO"}:
                inviati.append(msg)
        if inviati:
            gestore.sincronizza_inviati(inviati)
    except Exception:
        return


def _email_row(
    email_obj: Any,
    *,
    base_path: str = "/email",
    compose_path: str = "/email/scrivi",
    include_telematic: bool = True,
    pec_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    email_id = str(getattr(email_obj, "id", "") or "")
    folder = _normalise_folder(getattr(email_obj, "cartella", ""))
    timestamp = str(getattr(email_obj, "timestamp", "") or getattr(email_obj, "data", "") or getattr(email_obj, "ricevuta_il", "") or "")
    sender_name = _safe_text(getattr(email_obj, "mittente_nome", ""))
    sender = _safe_text(getattr(email_obj, "mittente", ""))
    recipients = _safe_text(getattr(email_obj, "destinatari", ""))
    subject = _safe_text(getattr(email_obj, "oggetto", ""), "(nessun oggetto)")
    status = _enum_value(getattr(email_obj, "stato", ""))
    encoded_id = quote(email_id, safe="")
    base = "/" + str(base_path or "/email").strip("/")
    compose_base = "/" + str(compose_path or "/email/scrivi").strip("/")
    is_pst = bool(getattr(email_obj, "e_pst", False)) if include_telematic else False
    pct_status = _safe_text(getattr(email_obj, "stato_pct", "")) if include_telematic else ""
    row = {
        "id": email_id,
        "folder": folder,
        "status": status,
        "sender": sender,
        "senderName": sender_name,
        "recipients": recipients,
        "subject": subject,
        "preview": _short_text(getattr(email_obj, "anteprima", "") or getattr(email_obj, "corpo_testo", ""), 220),
        "timestamp": timestamp,
        "timeLabel": _format_time(timestamp),
        "unread": status == StatoEmail.NON_LETTA,
        "isPst": is_pst,
        "pctStatus": pct_status,
        "attachmentCount": len(list(getattr(email_obj, "allegati", []) or [])),
        "origin": _safe_text(getattr(email_obj, "origine", "")),
        "detailHref": f"{base}/messaggio/{encoded_id}",
        "operationalHref": f"{base}/?cartella={folder}&id={encoded_id}",
        "replyHref": f"{compose_base}?a={quote(sender, safe='')}&oggetto={quote('Re: ' + subject, safe='')}",
        "trashHref": f"{base}/{encoded_id}/cestino",
        "restoreHref": f"{base}/{encoded_id}/ripristina",
        "deleteHref": f"{base}/{encoded_id}/elimina",
        "markReadHref": f"{base}/{encoded_id}/segna-letta",
        "markUnreadHref": f"{base}/{encoded_id}/segna-non-letta",
        "tone": _tone(email_obj, include_telematic=include_telematic),
    }
    audit_payload = _pec_audit_payload(pec_audit) or _pec_audit_payload(
        _provisional_pec_audit_summary(email_obj, include_telematic=include_telematic)
    )
    if audit_payload:
        row["pecAudit"] = audit_payload
        if audit_payload.get("eventType"):
            row["isPst"] = True
        if audit_payload.get("qualityTone") in {"warning", "danger"}:
            row["tone"] = audit_payload.get("qualityTone")
    return row


def _facet(value: str, label: str, count: int) -> dict[str, Any]:
    return {"value": value, "label": label, "count": int(count or 0)}


def _size_label(value: Any) -> str:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        size = 0
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B" if size else ""


def _attachment_rows(
    email_obj: Any,
    *,
    base_path: str,
    gestore: GestioneEmailRicevute | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    email_id = quote(str(getattr(email_obj, "id", "") or ""), safe="")
    base = "/" + str(base_path or "/email").strip("/")
    for index, info in enumerate(list(getattr(email_obj, "allegati", []) or [])):
        if not isinstance(info, dict):
            info = {}
        name = _safe_text(info.get("nome") or info.get("nome_file") or f"allegato-{index + 1}")
        href = f"{base}/messaggio/{email_id}/allegato/{index}"
        available = True
        if gestore is not None:
            available = gestore.allegato_disponibile(email_obj, index)
        rows.append(
            {
                "index": index,
                "name": name,
                "mime": _safe_text(info.get("mime")),
                "sizeLabel": _size_label(info.get("size") or info.get("dimensione")),
                "viewHref": href if available else "",
                "previewHref": href if available else "",
                "downloadHref": f"{href}?download=1" if available else "",
                "available": available,
                "statusLabel": (
                    ""
                    if available
                    else "Da recuperare con la sincronizzazione; se resta assente, verifica la presenza nella casella."
                ),
            }
        )
    return rows


def build_react_email_detail_payload(
    *,
    db_path: str,
    id_email: str,
    base_path: str = "/email",
    compose_path: str = "/email/scrivi",
    settings_path: str = "/impostazioni?tab=pec",
    include_telematic: bool = True,
    tenant_id: str = "default",
) -> dict[str, Any] | None:
    gestore = GestioneEmailRicevute(db_path=db_path)
    email_obj = gestore.get(id_email)
    if not email_obj:
        return None
    audit_summary = _pec_audit_summaries(db_path, [email_obj], tenant_id=tenant_id, include_telematic=include_telematic).get(
        str(getattr(email_obj, "message_id", "") or "").strip(),
        {},
    )
    effective_audit = audit_summary or _provisional_pec_audit_summary(email_obj, include_telematic=include_telematic) or {}
    sender = _safe_text(getattr(email_obj, "mittente", ""))
    subject = _safe_text(getattr(email_obj, "oggetto", ""))
    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": True},
        "item": _email_row(
            email_obj,
            base_path=base_path,
            compose_path=compose_path,
            include_telematic=include_telematic,
            pec_audit=effective_audit,
        ),
        "bodyText": str(getattr(email_obj, "corpo_testo", "") or ""),
        "bodyHtml": str(getattr(email_obj, "corpo_html", "") or ""),
        "attachments": _attachment_rows(email_obj, base_path=base_path, gestore=gestore),
        "pecAudit": _pec_audit_payload(effective_audit),
        "actions": {
            "inbox": f"{('/' + str(base_path or '/email').strip('/')).rstrip('/')}/",
            "reply": f"{('/' + str(compose_path or '/email/scrivi').strip('/'))}?a={quote(sender, safe='')}&oggetto={quote('Re: ' + subject, safe='')}",
            "settings": settings_path,
        },
    }


def build_react_email_payload(
    *,
    db_path: str,
    messaggi_db: str = "",
    base_path: str = "/email",
    compose_path: str = "/email/scrivi",
    settings_path: str = "/impostazioni?tab=pec",
    sync_path: str | None = None,
    auto_esiti_path: str = "/email/auto-esiti",
    local_test_path: str = "/impostazioni?tab=pec",
    lex_context: str = "email-pec",
    include_telematic: bool = True,
    folder: str = CartellaEmail.INBOX,
    query: str = "",
    stato: str = "",
    solo_pst: bool = False,
    con_allegati: bool = False,
    stato_pct: str = "",
    origine: str = "",
    data_da: str = "",
    data_a: str = "",
    tenant_id: str = "default",
) -> dict[str, Any]:
    gestore = GestioneEmailRicevute(db_path=db_path)
    _sync_inviati_da_messaggi(gestore, messaggi_db)
    base = "/" + str(base_path or "/email").strip("/")
    sync_href = sync_path or f"{base}/sincronizza"

    folder_valida = _normalise_folder(folder)
    emails = gestore.tutte(
        cartella=folder_valida,
        solo_non_lette=stato == StatoEmail.NON_LETTA,
        q=query,
        stato_lettura=stato if stato in {StatoEmail.NON_LETTA, StatoEmail.LETTA} else "",
        solo_pst=solo_pst if include_telematic else False,
        con_allegati=con_allegati,
        stato_pct=stato_pct if include_telematic else "",
        origine=origine,
        data_da=data_da,
        data_a=data_a,
    )
    all_emails = list(gestore._carica().values())  # noqa: SLF001 - bridge read-only su repository operativa
    stats = gestore.statistiche()
    persisted_audit_summaries = _pec_audit_summaries(db_path, all_emails, tenant_id=tenant_id, include_telematic=include_telematic)
    audit_summaries = dict(persisted_audit_summaries)
    for email_obj in all_emails:
        header = str(getattr(email_obj, "message_id", "") or "").strip()
        if header and header in audit_summaries:
            continue
        provisional = _provisional_pec_audit_summary(email_obj, include_telematic=include_telematic)
        if provisional:
            audit_summaries[header or str(getattr(email_obj, "id", "") or "")] = provisional
    email_headers = {str(getattr(email_obj, "message_id", "") or "").strip() for email_obj in all_emails if str(getattr(email_obj, "message_id", "") or "").strip()}
    audit_only_summaries = [
        item
        for item in _pec_audit_all_summaries(db_path, tenant_id=tenant_id, include_telematic=include_telematic)
        if str(item.get("message_id_header") or "").strip() not in email_headers
    ]
    rows = [
        _email_row(
            email_obj,
            base_path=base,
            compose_path=compose_path,
            include_telematic=include_telematic,
            pec_audit=audit_summaries.get(str(getattr(email_obj, "message_id", "") or "").strip())
            or audit_summaries.get(str(getattr(email_obj, "id", "") or "").strip()),
        )
        for email_obj in emails
    ]
    rows.extend(
        _pec_audit_virtual_row(item, base_path=base)
        for item in audit_only_summaries
        if _pec_audit_matches_filters(
            item,
            folder=folder_valida,
            query=query,
            stato=stato,
            solo_pst=solo_pst,
            con_allegati=con_allegati,
            stato_pct=stato_pct,
        )
    )
    pct_counts = Counter(
        str(getattr(email_obj, "stato_pct", "") or "")
        for email_obj in all_emails
        if include_telematic and getattr(email_obj, "stato_pct", "")
    )

    audit_only_attachments = sum(len(list(item.get("attachments") or [])) for item in audit_only_summaries)
    attachments_total = sum(len(list(getattr(email_obj, "allegati", []) or [])) for email_obj in all_emails) + audit_only_attachments
    auto_linked = sum(1 for email_obj in all_emails if include_telematic and bool(getattr(email_obj, "auto_registrata", False)))
    audit_warning_total = sum(1 for item in [*audit_summaries.values(), *audit_only_summaries] if str(item.get("quality_status") or "") in {"giallo", "rosso", "da_controllare"})
    warning_total = audit_warning_total + sum(
        1
        for email_obj in all_emails
        if include_telematic and any(marker in str(getattr(email_obj, "stato_pct", "") or "").upper() for marker in ("RIFIUT", "ERRORE", "WARN"))
    )
    pst_total = 0
    if include_telematic:
        pst_total = len(audit_only_summaries)
        for email_obj in all_emails:
            header = str(getattr(email_obj, "message_id", "") or "").strip()
            email_id = str(getattr(email_obj, "id", "") or "").strip()
            if getattr(email_obj, "e_pst", False) or audit_summaries.get(header) or audit_summaries.get(email_id):
                pst_total += 1

    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "contracts": {"mock_fallback": False, "read_only": True},
        "summary": {
            "total": int(stats.get("totale", len(all_emails)) or 0) + len(audit_only_summaries),
            "filtered": len(rows),
            "inbox": int(stats.get("inbox", 0) or 0) + len(audit_only_summaries),
            "unread": stats.get("non_lette", 0),
            "sent": stats.get("inviati", 0),
            "trash": stats.get("cestino", 0),
            "pst": pst_total,
            "attachments": attachments_total,
            "autoLinked": auto_linked,
            "warnings": warning_total,
        },
        "items": rows,
        "facets": {
            "folders": [
                _facet(CartellaEmail.INBOX, "In arrivo", int(stats.get("inbox", 0)) + len(audit_only_summaries)),
                _facet(CartellaEmail.INVIATI, "Inviati", int(stats.get("inviati", 0))),
                _facet(CartellaEmail.CESTINO, "Cestino", int(stats.get("cestino", 0))),
            ],
            "statuses": [
                _facet("tutti", "Tutte", len(all_emails) + len(audit_only_summaries)),
                _facet(StatoEmail.NON_LETTA, "Non lette", int(stats.get("non_lette", 0))),
                _facet(StatoEmail.LETTA, "Lette", sum(1 for email_obj in all_emails if getattr(email_obj, "stato", "") == StatoEmail.LETTA) + len(audit_only_summaries)),
                _facet(StatoEmail.CESTINO, "Nel cestino", int(stats.get("cestino", 0))),
            ],
            "pctStatuses": [
                _facet("", "Tutti gli esiti", int(stats.get("pst", 0)) if include_telematic else 0),
                *[_facet(value, value, count) for value, count in sorted(pct_counts.items())],
            ],
        },
        "actions": {
            "compose": compose_path,
            "settings": settings_path,
            "sync": sync_href,
            "bulkAction": "/api/v1/ui/email/bulk-action" if include_telematic else "/api/v1/ui/email-ordinaria/bulk-action",
            "autoEsiti": auto_esiti_path if include_telematic else "",
            "operationalInbox": f"{base}/",
            "localPecTest": local_test_path,
            "legalNotice": "/notifiche-legali",
            "lex": "#lex",
        },
    }
