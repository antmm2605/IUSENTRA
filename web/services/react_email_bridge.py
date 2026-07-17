"""Bridge dati per le pagine React Email PEC ed email ordinaria.

La funzione costruisce payload in sola lettura sopra GestioneEmailRicevute,
riusando le caselle locali e i servizi Flask auditati per le azioni operative.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from email import policy
from pathlib import Path
from typing import Any
import email
import html as html_lib
import re
import unicodedata
from urllib.parse import quote

from pct.email_client import CartellaEmail, GestioneEmailRicevute, StatoEmail
from pct.formatting import DISPLAY_TIMEZONE, parse_datetime_rome
from pct.pec_pipeline import (
    AttachmentPayload,
    build_pec_procedural_profile,
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


def _clean_multiline_text(value: Any, *, limit: int = 200000) -> str:
    text = _repair_text_encoding_artifacts(str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text).strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "\n\n[Testo abbreviato per dimensione: apri il MIME o l'allegato per la copia integrale.]"
    return text


def _dedupe_signature(value: Any) -> str:
    text = html_lib.unescape(_repair_text_encoding_artifacts(str(value or "")))
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w@./:+-]+", " ", text, flags=re.UNICODE)
    return text.strip()


def _looks_like_duplicate_text(value: str, existing: list[str]) -> bool:
    signature = _dedupe_signature(value)
    if not signature:
        return True
    for item in existing:
        other = _dedupe_signature(item)
        if not other:
            continue
        if signature == other:
            return True
        if min(len(signature), len(other)) >= 80 and (signature in other or other in signature):
            return True
        if min(len(signature), len(other)) >= 160:
            left = signature[:4000]
            right = other[:4000]
            if SequenceMatcher(None, left, right).ratio() >= 0.94:
                return True
    return False


def _iter_message_display_parts(message: email.message.Message) -> list[email.message.Message]:
    if not message.is_multipart():
        return [message]
    payload = message.get_payload()
    if not isinstance(payload, list):
        return [message]
    parts: list[email.message.Message] = []
    for part in payload:
        if not hasattr(part, "get_content_type"):
            continue
        if str(part.get_content_type() or "").lower() == "message/rfc822":
            parts.append(part)
            continue
        if part.is_multipart():
            parts.extend(_iter_message_display_parts(part))
            continue
        parts.append(part)
    return parts


def _repair_text_encoding_artifacts(value: str) -> str:
    """Ripara i mojibake piu' comuni nei testi PEC gia' decodificati male."""
    text = value or ""
    markers = ("\u00c3", "\u00c2", "\u00e2\u20ac", "\u00e2\u0080", "\u00ef\u00bf\u00bd", "\ufffd")
    if any(marker in text for marker in markers):
        try:
            candidate = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            candidate = text
        original_markers = sum(text.count(marker) for marker in markers)
        candidate_markers = sum(candidate.count(marker) for marker in markers)
        if candidate_markers <= original_markers:
            text = candidate
    text = re.sub(r"(?<=\w)(?:\u00ef\u00bf\u00bd|\ufffd)(?=\w)", "\u2019", text)
    text = text.replace("\u00c2 ", " ").replace("\u00c2", "")
    return text


def _html_to_readable_text(value: Any) -> str:
    html = str(value or "")
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text.replace("&nbsp;", " "))
    return _clean_multiline_text(text)


def _message_readable_text(message: email.message.Message, *, depth: int = 0) -> str:
    if depth > 4:
        return ""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    nested_parts: list[str] = []
    parts = _iter_message_display_parts(message)
    for part in parts:
        content_type = str(part.get_content_type() or "").lower()
        disposition = str(part.get_content_disposition() or "").lower()
        filename = str(part.get_filename() or "")
        if content_type == "message/rfc822":
            payload = part.get_payload()
            nested_messages = payload if isinstance(payload, list) else []
            for nested in nested_messages:
                if hasattr(nested, "items"):
                    nested_parts.append(_format_nested_message(nested, filename or "messaggio allegato", depth=depth + 1))
            continue
        if disposition == "attachment" and filename:
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True)
            content = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload or "")
        if content_type == "text/plain":
            cleaned = _clean_multiline_text(content)
            if cleaned and not _looks_like_duplicate_text(cleaned, [*plain_parts, *html_parts]):
                plain_parts.append(cleaned)
        elif content_type == "text/html":
            cleaned = _html_to_readable_text(content)
            if cleaned and not _looks_like_duplicate_text(cleaned, [*plain_parts, *html_parts]):
                html_parts.append(cleaned)
    body = "\n\n".join(part for part in [*plain_parts, *html_parts, *nested_parts] if part)
    return _clean_multiline_text(body)


def _format_nested_message(message: email.message.Message, label: str, *, depth: int = 0) -> str:
    heading = "Email ricevuta originale" if label == "email ricevuta originale" else f"Messaggio allegato: {label}"
    header_lines = [heading]
    for title, header in (("Oggetto", "Subject"), ("Da", "From"), ("A", "To"), ("Data", "Date")):
        value = _safe_text(message.get(header, ""))
        if value:
            header_lines.append(f"{title}: {value}")
    body = _message_readable_text(message, depth=depth)
    return _clean_multiline_text("\n".join(header_lines) + ("\n\n" + body if body else ""))


def _nested_eml_sections(email_obj: Any, gestore: GestioneEmailRicevute) -> list[str]:
    sections: list[str] = []
    for index, info in enumerate(list(getattr(email_obj, "allegati", []) or [])):
        if not isinstance(info, dict):
            continue
        name = _safe_text(info.get("nome") or info.get("nome_file") or f"allegato-{index + 1}.eml")
        mime = _safe_text(info.get("mime") or info.get("content_type")).lower()
        if not (name.lower().endswith(".eml") or mime == "message/rfc822"):
            continue
        raw = gestore.leggi_allegato(email_obj, index)
        if not raw:
            continue
        try:
            nested = email.message_from_bytes(raw, policy=policy.default)
        except Exception:
            continue
        section = _format_nested_message(nested, name)
        if section:
            sections.append(section)
    return sections


def _email_complete_body_text(email_obj: Any, gestore: GestioneEmailRicevute) -> str:
    raw_eml = gestore.leggi_eml_originale(email_obj)
    sections: list[str] = []
    if raw_eml:
        try:
            original = email.message_from_bytes(raw_eml, policy=policy.default)
            sections.append(_format_nested_message(original, "email ricevuta originale"))
        except Exception:
            pass
    if not sections:
        base_text = _clean_multiline_text(getattr(email_obj, "corpo_testo", "") or "")
        if not base_text:
            base_text = _html_to_readable_text(getattr(email_obj, "corpo_html", "") or "")
        if base_text:
            sections.append(base_text)
    for section in _nested_eml_sections(email_obj, gestore):
        current_text = "\n\n".join(sections)
        if section and section not in sections and section not in current_text:
            sections.append(section)
    for section in _textual_attachment_sections(email_obj, gestore):
        if section and section not in sections:
            sections.append(section)
    return _clean_multiline_text("\n\n---\n\n".join(sections))


def _email_body_payload(email_obj: Any, gestore: GestioneEmailRicevute) -> dict[str, str]:
    raw_eml = gestore.leggi_eml_originale(email_obj)
    sections: list[str] = []
    has_original = False
    if raw_eml:
        try:
            original = email.message_from_bytes(raw_eml, policy=policy.default)
            formatted = _format_nested_message(original, "email ricevuta originale")
            if formatted:
                sections.append(formatted)
                has_original = True
        except Exception:
            pass
    if not sections:
        base_text = _clean_multiline_text(getattr(email_obj, "corpo_testo", "") or "")
        if not base_text:
            base_text = _html_to_readable_text(getattr(email_obj, "corpo_html", "") or "")
        if base_text:
            sections.append(base_text)
    nested_sections = _nested_eml_sections(email_obj, gestore)
    for section in nested_sections:
        current_text = "\n\n".join(sections)
        if section and section not in sections and section not in current_text:
            sections.append(section)
    textual_sections = _textual_attachment_sections(email_obj, gestore)
    for section in textual_sections:
        if section and section not in sections:
            sections.append(section)

    body_text = _clean_multiline_text("\n\n---\n\n".join(sections))
    if has_original:
        completeness = "originale_acquisito"
        label = "EML originale acquisito: corpo, messaggio allegato e allegati testuali sono ricostruiti nella lettura."
    elif nested_sections or textual_sections:
        completeness = "ricostruito_da_allegati"
        label = "Testo ricostruito da corpo e allegati disponibili; acquisisci il MIME originale per la copia forense integrale."
    else:
        completeness = "testo_disponibile"
        label = "È disponibile solo il testo salvato in casella; acquisisci il MIME originale per vedere la PEC completa."
    return {
        "bodyText": body_text,
        "bodyCompleteness": completeness,
        "bodyCompletenessLabel": label,
    }


def _textual_attachment_sections(email_obj: Any, gestore: GestioneEmailRicevute) -> list[str]:
    sections: list[str] = []
    for index, info in enumerate(list(getattr(email_obj, "allegati", []) or [])):
        if not isinstance(info, dict):
            continue
        name = _safe_text(info.get("nome") or info.get("nome_file") or f"allegato-{index + 1}")
        mime = _safe_text(info.get("mime") or info.get("content_type")).lower()
        lower_name = name.lower()
        if lower_name.endswith(".eml") or mime == "message/rfc822":
            continue
        is_textual = (
            mime.startswith("text/")
            or mime in {"application/xml", "text/xml", "application/json", "application/csv"}
            or lower_name.endswith((".txt", ".xml", ".json", ".csv"))
        )
        if not is_textual:
            continue
        raw = gestore.leggi_allegato(email_obj, index)
        if not raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        cleaned = _clean_multiline_text(text, limit=120000)
        if cleaned:
            sections.append(f"Allegato testuale: {name}\nTipo: {mime or 'file'}\n\n{cleaned}")
    return sections


def _normalise_search(value: Any) -> str:
    text = unicodedata.normalize("NFD", _safe_text(value).lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.split())


def _matches_search(haystack: str, query: str) -> bool:
    haystack_norm = _normalise_search(haystack)
    tokens = [token for token in _normalise_search(query).split() if token]
    if not tokens:
        return True
    for token in tokens:
        if token in haystack_norm:
            continue
        stem = token[:-1] if len(token) > 4 and token[-1] in "aeiou" else token
        if stem and stem != token and stem in haystack_norm:
            continue
        return False
    return True


def _pec_quality_label(value: str) -> tuple[str, str]:
    raw = str(value or "").strip().lower()
    if raw == "verde":
        return "Qualità verde", "success"
    if raw == "giallo":
        return "Qualità da presidiare", "warning"
    if raw == "rosso":
        return "Qualità critica", "danger"
    if raw in {"da_controllare", "provvisorio", "provisional"}:
        return "Presidio richiesto", "warning"
    return "Controllo non disponibile", "neutral"


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


def _pec_audit_summaries(
    db_path: str,
    emails: list[Any],
    *,
    tenant_id: str = "default",
    include_telematic: bool = True,
    include_details: bool = True,
) -> dict[str, dict[str, Any]]:
    if not include_telematic:
        return {}
    audit_db = _pec_audit_db_path(db_path)
    if not audit_db.exists():
        return {}
    headers = [str(getattr(email_obj, "message_id", "") or "").strip() for email_obj in emails]
    try:
        from pct.pec_pipeline import PecAuditRepository

        return PecAuditRepository(audit_db, tenant_id=tenant_id).summaries_by_header_message_ids(
            headers,
            include_details=include_details,
        )
    except Exception:
        return {}


def _pec_audit_all_summaries(
    db_path: str,
    *,
    tenant_id: str = "default",
    include_telematic: bool = True,
    include_details: bool = True,
) -> list[dict[str, Any]]:
    if not include_telematic:
        return []
    audit_db = _pec_audit_db_path(db_path)
    if not audit_db.exists():
        return []
    try:
        from pct.pec_pipeline import PecAuditRepository

        repo = PecAuditRepository(audit_db, tenant_id=tenant_id)
        summaries: list[dict[str, Any]] = []
        for row in repo.list_messages(limit=200, include_details=include_details):
            detail = repo.get_message_detail(str(row.get("id") or "")) if include_details else {}
            message = detail.get("message") if isinstance(detail.get("message"), dict) else row
            parsed = detail.get("parsed") if isinstance(detail.get("parsed"), dict) else {}
            body = parsed.get("body") if isinstance(parsed.get("body"), dict) else {}
            body_text = _safe_text(parsed.get("body_text") or body.get("text") or body.get("html_text"))
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
                    "body_text": body_text,
                    "validation_report": detail.get("validation_report") or row.get("validation_report") or {},
                    "fascicolo_link": detail.get("fascicolo_link") or row.get("fascicolo_link") or {},
                    "attachments": detail.get("attachments") or [],
                }
            )
        return summaries
    except Exception:
        return []


def _pec_presidio_index(db_path: str, *, tenant_id: str = "default", include_telematic: bool = True) -> dict[str, dict[str, dict[str, Any]]]:
    if not include_telematic:
        return {"by_email_id": {}, "by_message_id": {}}
    audit_db = _pec_audit_db_path(db_path)
    if not audit_db.exists():
        return {"by_email_id": {}, "by_message_id": {}}
    try:
        from pct.pec_pipeline import PecAuditRepository

        return PecAuditRepository(audit_db, tenant_id=tenant_id).local_acquire_presidio_index()
    except Exception:
        return {"by_email_id": {}, "by_message_id": {}}


def _pec_audit_payload(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary:
        return None
    quality_label, quality_tone = _pec_quality_label(str(summary.get("quality_status") or ""))
    signature_label, signature_tone = _pec_signature_label(str(summary.get("signature_status") or ""))
    pec_id = str(summary.get("id") or "")
    report = summary.get("validation_report") if isinstance(summary.get("validation_report"), dict) else {}
    deadline_proposal = report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {}
    semantic_context = report.get("semantic_context") if isinstance(report.get("semantic_context"), dict) else {}
    procedural_profile = report.get("procedural_profile") if isinstance(report.get("procedural_profile"), dict) else {}
    event_type = _canonical_pec_event_type(report, procedural_profile)
    link = summary.get("fascicolo_link") if isinstance(summary.get("fascicolo_link"), dict) else {}
    fields = summary.get("fields") if isinstance(summary.get("fields"), dict) else {}
    attachments = summary.get("attachments") if isinstance(summary.get("attachments"), list) else []
    provisional = bool(summary.get("provisional"))
    source_email_id = _safe_text(summary.get("source_email_id"))
    mime_available = bool(summary.get("mime_available"))
    run_audit_href = (
        f"/api/pec/email/{quote(source_email_id, safe='')}/acquisisci"
        if provisional and mime_available and source_email_id
        else "/api/pec/fetch?limit=50"
        if provisional
        else f"/api/pec/messages/{quote(pec_id, safe='')}/riesegui-controllo"
        if pec_id
        else ""
    )
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
        "eventType": event_type,
        "depositLifecycle": report.get("deposit_lifecycle") if isinstance(report.get("deposit_lifecycle"), dict) else {},
        "semanticContext": semantic_context,
        "proceduralProfile": procedural_profile,
        "lawyerChecklist": list(report.get("lawyer_checklist") or procedural_profile.get("checklist_avvocato") or []),
        "normativeReferences": list(report.get("normative_references") or semantic_context.get("normative_references") or []),
        "agentQuestions": list(report.get("agent_questions") or semantic_context.get("agent_questions") or []),
        "recommendedActions": list(report.get("recommended_actions") or semantic_context.get("recommended_actions") or []),
        "deadlineProposal": deadline_proposal,
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
            "scheduleDeadline": "" if provisional or not deadline_proposal.get("auto_create") else f"/api/pec/messages/{quote(pec_id, safe='')}/schedula-scadenza" if pec_id else "",
            "openMime": "" if provisional else f"/api/pec/messages/{quote(pec_id, safe='')}/mime" if pec_id else "",
            "runAudit": run_audit_href,
        },
        "persisted": not provisional,
        "storageLabel": "MIME pronto da acquisire" if provisional and mime_available else "MIME da acquisire automaticamente" if provisional else "MIME originale conservato",
        "storageTone": "warning" if provisional else "success",
        "sourceEmailId": source_email_id,
    }


def _canonical_pec_event_type(report: dict[str, Any], procedural_profile: dict[str, Any]) -> str:
    event_type = _safe_text(report.get("event_type"))
    if event_type != "notifica_giudice_pace":
        return event_type

    office = _safe_text(procedural_profile.get("ufficio")).casefold()
    if not office or "giudice di pace" in office:
        return event_type

    other_court_markers = (
        "tribunale",
        "corte d'appello",
        "corte di cassazione",
        "procura",
        "tribunale amministrativo",
        "consiglio di stato",
    )
    if any(marker in office for marker in other_court_markers):
        return "comunicazione_cancelleria"
    return event_type


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


def _provisional_pec_audit_summary(
    email_obj: Any,
    *,
    include_telematic: bool = True,
    context_override: str = "",
) -> dict[str, Any] | None:
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
            context_override,
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
    procedural_profile = build_pec_procedural_profile(
        subject=subject,
        body_text=context_text,
        xml_texts={},
        rg_candidates=[protocol] if protocol else [],
        sent_date=sent_date,
        delivery_date="",
        event_type=str(semantic_context.get("event_hint") or ""),
        semantic_context=semantic_context,
    )
    office_value = _safe_text(procedural_profile.get("ufficio"))
    judge_value = _safe_text(procedural_profile.get("giudice"))
    event_value = _safe_text(procedural_profile.get("tipo_evento") or procedural_profile.get("oggetto_evento"))
    client_value = _safe_text(procedural_profile.get("cliente"))
    party_value = _safe_text(procedural_profile.get("parte_processuale"))
    parties_value = procedural_profile.get("parti_processuali") if isinstance(procedural_profile.get("parti_processuali"), list) else []
    party_records_value = procedural_profile.get("soggetti_parti") if isinstance(procedural_profile.get("soggetti_parti"), list) else []
    office_code_value = _safe_text(procedural_profile.get("codice_ufficio"))
    notice_time_value = _safe_text(procedural_profile.get("notificato_il") or sent_date)
    hearing_time_value = _safe_text(procedural_profile.get("udienza_data_ora"))
    hearing_mode_value = _safe_text(procedural_profile.get("modalita_udienza"))
    fields = {
        "mittente": field_result(
            _address_value(sender),
            0.72 if sender else 0.18,
            "Letto dallo storico della casella PEC; confermare sul MIME originale quando il controllo completo viene eseguito.",
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
        "ufficio_giudiziario": field_result(
            office_value,
            0.72 if office_value and context_override else 0.62 if office_value else 0.2,
            "Ufficio/cancelleria letto dal testo completo disponibile; confermare con audit MIME." if office_value else "Ufficio non riconosciuto nei dati disponibili.",
            ["profilo_processuale", "email_completa"] if office_value else [],
        ),
        "codice_ufficio": field_result(
            office_code_value,
            0.74 if office_code_value and context_override else 0.6 if office_code_value else 0.2,
            "Codice ufficio letto dal testo/XML disponibile; l'audit MIME lo userà per risolvere l'ufficio reale." if office_code_value else "Codice ufficio non riconosciuto.",
            ["profilo_processuale", "email_completa"] if office_code_value else [],
        ),
        "giudice": field_result(
            judge_value,
            0.72 if judge_value and context_override else 0.62 if judge_value else 0.2,
            "Giudice letto dalla comunicazione; confermare con Comunicazione.xml o allegati." if judge_value else "Giudice non indicato o non riconosciuto.",
            ["profilo_processuale", "email_completa"] if judge_value else [],
        ),
        "cliente": field_result(
            client_value,
            0.72 if client_value and context_override else 0.62 if client_value else 0.2,
            "Cliente o assistito letto dai dati disponibili; confermare con fascicolo e Comunicazione.xml." if client_value else "Cliente non riconosciuto nei dati disponibili.",
            ["profilo_processuale", "email_completa"] if client_value else [],
        ),
        "parte_processuale": field_result(
            party_value,
            0.72 if party_value and context_override else 0.62 if party_value else 0.2,
            "Parte/soggetto processuale letto dai dati disponibili; confermare con Comunicazione.xml." if party_value else "Parte/soggetto processuale non riconosciuto.",
            ["profilo_processuale", "email_completa"] if party_value else [],
        ),
        "parti_processuali": field_result(
            parties_value,
            0.72 if parties_value and context_override else 0.62 if parties_value else 0.2,
            "Elenco parti processuali ricostruito dai dati disponibili." if parties_value else "Elenco parti non riconosciuto.",
            ["profilo_processuale", "email_completa"] if parties_value else [],
        ),
        "soggetti_parti": field_result(
            party_records_value,
            0.72 if party_records_value and context_override else 0.62 if party_records_value else 0.2,
            "Ruoli delle parti ricostruiti dai dati disponibili." if party_records_value else "Ruoli parte non riconosciuti.",
            ["profilo_processuale", "email_completa"] if party_records_value else [],
        ),
        "evento_processuale": field_result(
            event_value,
            0.72 if event_value and context_override else 0.62 if event_value else 0.2,
            "Evento processuale letto dal messaggio completo disponibile." if event_value else "Evento processuale non riconosciuto.",
            ["profilo_processuale", "email_completa"] if event_value else [],
        ),
        "orario_notifica": field_result(
            notice_time_value,
            0.7 if notice_time_value else 0.2,
            "Orario da presidiare letto dalla scheda o dalla comunicazione." if notice_time_value else "Orario non riconosciuto.",
            ["profilo_processuale", "email:data"] if notice_time_value else [],
        ),
        "orario_udienza": field_result(
            hearing_time_value,
            0.72 if hearing_time_value and context_override else 0.62 if hearing_time_value else 0.2,
            "Data e ora udienza lette dal messaggio completo disponibile; da confermare con audit MIME." if hearing_time_value else "Data e ora udienza non riconosciute.",
            ["profilo_processuale", "email_completa"] if hearing_time_value else [],
        ),
        "modalita_udienza": field_result(
            hearing_mode_value,
            0.72 if hearing_mode_value and context_override else 0.62 if hearing_mode_value else 0.2,
            "Modalità udienza letta dal messaggio completo disponibile; da confermare con audit MIME." if hearing_mode_value else "Modalità udienza non riconosciuta.",
            ["profilo_processuale", "email_completa"] if hearing_mode_value else [],
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
        "procedural_profile": procedural_profile,
        "body": {"text": context_text},
    }
    report = build_validation_report(parsed, attachments)
    report.setdefault("issues", [])
    report["issues"] = [
        {
            "code": "audit_storage_pending",
            "severity": "warning",
            "blocking": False,
            "title": "Acquisizione MIME originale richiesta",
            "detail": "Il software ha eseguito il presidio sul testo disponibile; per chiudere l'esito deve acquisire il MIME originale da IMAP, verificare allegati, firme, OCR e hash.",
        },
        *list(report.get("issues") or []),
    ]
    recommended = [
        "Esegui controllo per acquisire il MIME originale e aggiornare esito, firme, OCR e collegamento fascicolo.",
        *list(report.get("recommended_actions") or []),
    ]
    report["recommended_actions"] = list(dict.fromkeys(_safe_text(item) for item in recommended if _safe_text(item)))
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
        "mime_available": bool(str(getattr(email_obj, "eml_file", "") or "").strip()),
    }


def _pec_audit_text(summary: dict[str, Any]) -> str:
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    headers = metadata.get("headers") if isinstance(metadata.get("headers"), dict) else {}
    report = summary.get("validation_report") if isinstance(summary.get("validation_report"), dict) else {}
    parts = [
        headers.get("subject"),
        headers.get("from"),
        headers.get("to"),
        summary.get("body_text"),
        report.get("event_type"),
        " ".join(str(item.get("title") or "") for item in list(report.get("issues") or []) if isinstance(item, dict)),
        " ".join(str(item.get("filename") or item.get("name") or "") for item in list(summary.get("attachments") or []) if isinstance(item, dict)),
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
    if query and not _matches_search(_pec_audit_text(summary), query):
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


def _pec_audit_virtual_row(
    summary: dict[str, Any],
    *,
    base_path: str = "/email",
    pec_presidio: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        or "PEC conservata nel controllo completo.",
        220,
    )
    base = "/" + str(base_path or "/email").strip("/")
    encoded = quote(pec_id, safe="")
    audit_payload = _pec_audit_payload(summary) or {}
    presidio_payload = dict(pec_presidio or {})
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
        "origin": "controllo PEC",
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
        "pecPresidiata": bool(presidio_payload),
        "pecPresidioStatus": _safe_text(presidio_payload.get("status")),
        "pecPresidioDeadlineStatus": _safe_text(presidio_payload.get("deadline_status")),
        "pecPresidioDueDate": _safe_text(presidio_payload.get("due_date")),
        "pecAudit": audit_payload,
    }


def _parse_datetime(value: Any) -> datetime | None:
    parsed = parse_datetime_rome(value)
    if parsed is None:
        return None
    return parsed.astimezone(DISPLAY_TIMEZONE).replace(tzinfo=None)


def _format_time(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    today = datetime.now(DISPLAY_TIMEZONE).date()
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
    pec_presidio: dict[str, Any] | None = None,
    include_provisional_audit: bool = True,
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
    presidio_payload = dict(pec_presidio or {})
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
        "pecPresidiata": bool(presidio_payload),
        "pecPresidioStatus": _safe_text(presidio_payload.get("status")),
        "pecPresidioDeadlineStatus": _safe_text(presidio_payload.get("deadline_status")),
        "pecPresidioDueDate": _safe_text(presidio_payload.get("due_date")),
    }
    audit_payload = _pec_audit_payload(pec_audit)
    if audit_payload is None and include_provisional_audit:
        audit_payload = _pec_audit_payload(
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
    body_payload = _email_body_payload(email_obj, gestore)
    audit_summary = _pec_audit_summaries(db_path, [email_obj], tenant_id=tenant_id, include_telematic=include_telematic).get(
        str(getattr(email_obj, "message_id", "") or "").strip(),
        {},
    )
    effective_audit = audit_summary or _provisional_pec_audit_summary(
        email_obj,
        include_telematic=include_telematic,
        context_override=body_payload.get("bodyText", ""),
    ) or {}
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
        "bodyText": body_payload["bodyText"],
        "bodyCompleteness": body_payload["bodyCompleteness"],
        "bodyCompletenessLabel": body_payload["bodyCompletenessLabel"],
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
    large_mailbox = len(all_emails) > 80
    persisted_audit_summaries = _pec_audit_summaries(
        db_path,
        all_emails,
        tenant_id=tenant_id,
        include_telematic=include_telematic,
        include_details=not large_mailbox,
    )
    if large_mailbox and len(emails) <= 80:
        persisted_audit_summaries.update(
            _pec_audit_summaries(
                db_path,
                emails,
                tenant_id=tenant_id,
                include_telematic=include_telematic,
                include_details=True,
            )
        )
    presidio_index = _pec_presidio_index(db_path, tenant_id=tenant_id, include_telematic=include_telematic)
    presidiati_by_email = presidio_index.get("by_email_id") if isinstance(presidio_index.get("by_email_id"), dict) else {}
    presidiati_by_message = presidio_index.get("by_message_id") if isinstance(presidio_index.get("by_message_id"), dict) else {}

    def _presidio_for_email(email_obj: Any) -> dict[str, Any]:
        email_id = str(getattr(email_obj, "id", "") or "").strip()
        if email_id and email_id in presidiati_by_email:
            return dict(presidiati_by_email[email_id])
        header = str(getattr(email_obj, "message_id", "") or "").strip()
        audit_summary = persisted_audit_summaries.get(header) if header else {}
        audit_message_id = str((audit_summary or {}).get("id") or "").strip()
        if audit_message_id and audit_message_id in presidiati_by_message:
            return dict(presidiati_by_message[audit_message_id])
        return {}

    provisional_audit_enabled = include_telematic and len(emails) <= 80
    audit_summaries = dict(persisted_audit_summaries)
    if provisional_audit_enabled:
        for email_obj in emails:
            header = str(getattr(email_obj, "message_id", "") or "").strip()
            email_id = str(getattr(email_obj, "id", "") or "").strip()
            if (header and header in audit_summaries) or (email_id and email_id in audit_summaries):
                continue
            provisional = _provisional_pec_audit_summary(email_obj, include_telematic=include_telematic)
            if provisional:
                audit_summaries[header or email_id] = provisional
    email_headers = {str(getattr(email_obj, "message_id", "") or "").strip() for email_obj in all_emails if str(getattr(email_obj, "message_id", "") or "").strip()}
    audit_only_summaries = [
        item
        for item in _pec_audit_all_summaries(
            db_path,
            tenant_id=tenant_id,
            include_telematic=include_telematic,
            include_details=not large_mailbox,
        )
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
            pec_presidio=_presidio_for_email(email_obj),
            include_provisional_audit=False,
        )
        for email_obj in emails
    ]
    rows.extend(
        _pec_audit_virtual_row(
            item,
            base_path=base,
            pec_presidio=presidiati_by_message.get(str(item.get("id") or "").strip()) if isinstance(presidiati_by_message, dict) else {},
        )
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
    def _email_requires_presidio(email_obj: Any) -> bool:
        if not include_telematic or _presidio_for_email(email_obj):
            return False
        audit = (
            audit_summaries.get(str(getattr(email_obj, "message_id", "") or "").strip())
            or audit_summaries.get(str(getattr(email_obj, "id", "") or "").strip())
            or {}
        )
        audit_warning = str(audit.get("quality_status") or "") in {"giallo", "rosso", "da_controllare"}
        status = str(getattr(email_obj, "stato_pct", "") or "").upper()
        pct_warning = bool(status and any(marker in status for marker in ("RIFIUT", "ERRORE", "WARN")))
        return audit_warning or pct_warning

    warning_total = sum(1 for email_obj in all_emails if _email_requires_presidio(email_obj)) + sum(
        1
        for item in audit_only_summaries
        if str(item.get("quality_status") or "") in {"giallo", "rosso", "da_controllare"}
        and str(item.get("id") or "").strip() not in presidiati_by_message
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
            "pecLocalAcquire": "/api/pec/email/acquisisci-locali?limit=5000&batch_size=50" if include_telematic else "",
            "operationalInbox": f"{base}/",
            "localPecTest": local_test_path,
            "legalNotice": "/notifiche-legali",
            "lex": "#lex",
        },
    }
