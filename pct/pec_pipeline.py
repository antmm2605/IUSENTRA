"""Pipeline audit-grade per ingestione e controllo automatico PEC.

Il modulo affianca il client email storico senza sostituirlo: conserva il MIME
originale, versiona il JSON estratto, calcola hash per ogni passaggio e usa una
coda persistente per parser, allegati, OCR, firme, validazione e fascicolo.
"""

from __future__ import annotations

import email
import hashlib
import io
import imaplib
import json
import mimetypes
import re
import sqlite3
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pct.email_client import cartelle_imap_standard
from pct.pec_legal_workflow import classifica_pec_legale

SCHEMA_VERSION = "2026-06-06.pec-audit-pipeline.v3"
DEADLINE_POLICY_VERSION = "2026-06-03.procedural-dates-v1"
DEFAULT_TENANT_ID = "default"
ROME_TZ = ZoneInfo("Europe/Rome")
ATTACHMENT_CLASSES = {
    "atto",
    "procura",
    "ricevute",
    "tecnico",
    "istruttorio",
    "daticert",
    "eml",
    "altro",
    "da confermare",
}
JOB_SEQUENCE = ("parse", "classify", "ocr", "signcheck", "validate", "link")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS pec_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL,
    sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_retention_policies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    original_mime_days INTEGER NOT NULL,
    parsed_json_days INTEGER NOT NULL,
    legal_hold INTEGER NOT NULL DEFAULT 1,
    action TEXT NOT NULL DEFAULT 'review',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pec_messages (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    account_email TEXT NOT NULL,
    folder TEXT NOT NULL,
    imap_uid TEXT NOT NULL DEFAULT '',
    message_id_header TEXT NOT NULL DEFAULT '',
    mime_sha256 TEXT NOT NULL,
    mime_size INTEGER NOT NULL,
    original_mime BLOB NOT NULL,
    received_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ingested',
    quality_status TEXT NOT NULL DEFAULT 'da_controllare',
    signature_status TEXT NOT NULL DEFAULT 'non_verificata',
    linked_fascicolo_id TEXT NOT NULL DEFAULT '',
    linked_fascicolo_score REAL NOT NULL DEFAULT 0,
    retention_policy_id TEXT NOT NULL DEFAULT 'pec_audit_default',
    retention_until TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (tenant_id, account_email, message_id_header, mime_sha256),
    UNIQUE (tenant_id, mime_sha256)
);

CREATE TABLE IF NOT EXISTS pec_parsed_versions (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    parser_version TEXT NOT NULL,
    parsed_json TEXT NOT NULL,
    parsed_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'pec-pipeline',
    FOREIGN KEY(message_id) REFERENCES pec_messages(id),
    UNIQUE (message_id, version)
);

CREATE TABLE IF NOT EXISTS pec_attachments (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    parsed_version_id TEXT NOT NULL,
    attachment_index INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    classification TEXT NOT NULL,
    classification_score REAL NOT NULL,
    classification_reason TEXT NOT NULL,
    ocr_text TEXT NOT NULL DEFAULT '',
    ocr_coverage REAL NOT NULL DEFAULT 0,
    signature_status TEXT NOT NULL DEFAULT 'non_verificata',
    signature_details_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(message_id) REFERENCES pec_messages(id),
    FOREIGN KEY(parsed_version_id) REFERENCES pec_parsed_versions(id),
    UNIQUE (message_id, parsed_version_id, attachment_index)
);

CREATE TABLE IF NOT EXISTS pec_validation_reports (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    parsed_version_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    report_json TEXT NOT NULL,
    report_sha256 TEXT NOT NULL,
    severity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(message_id) REFERENCES pec_messages(id),
    FOREIGN KEY(parsed_version_id) REFERENCES pec_parsed_versions(id)
);

CREATE TABLE IF NOT EXISTS pec_fascicolo_links (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    parsed_version_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL,
    status TEXT NOT NULL,
    seeds_json TEXT NOT NULL,
    candidates_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(message_id) REFERENCES pec_messages(id),
    FOREIGN KEY(parsed_version_id) REFERENCES pec_parsed_versions(id)
);

CREATE TABLE IF NOT EXISTS pec_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '',
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 50,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    available_at TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, message_id, job_type, status)
);

CREATE TABLE IF NOT EXISTS pec_digest_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    digest_date TEXT NOT NULL,
    run_at TEXT NOT NULL,
    digest_json TEXT NOT NULL,
    digest_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    UNIQUE (tenant_id, digest_date)
);

CREATE TABLE IF NOT EXISTS pec_local_acquire_runs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT NOT NULL DEFAULT '',
    cursor_index INTEGER NOT NULL DEFAULT 0,
    total_emails INTEGER NOT NULL DEFAULT 0,
    batch_size INTEGER NOT NULL DEFAULT 50,
    acquired INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    skipped_missing_mime INTEGER NOT NULL DEFAULT 0,
    skipped_not_pec INTEGER NOT NULL DEFAULT 0,
    queued_repairs INTEGER NOT NULL DEFAULT 0,
    deadline_created INTEGER NOT NULL DEFAULT 0,
    deadline_already_exists INTEGER NOT NULL DEFAULT 0,
    deadline_expired INTEGER NOT NULL DEFAULT 0,
    deadline_not_ready INTEGER NOT NULL DEFAULT 0,
    deadline_errors INTEGER NOT NULL DEFAULT 0,
    agenda_linked INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS pec_local_acquire_items (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    email_id TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    deadline_status TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    deadline_id TEXT NOT NULL DEFAULT '',
    agenda_id TEXT NOT NULL DEFAULT '',
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES pec_local_acquire_runs(id),
    UNIQUE (tenant_id, run_id, email_id)
);

CREATE TABLE IF NOT EXISTS pec_audit_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS pec_audit_log_no_update
BEFORE UPDATE ON pec_audit_log
BEGIN
    SELECT RAISE(ABORT, 'pec_audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS pec_audit_log_no_delete
BEFORE DELETE ON pec_audit_log
BEGIN
    SELECT RAISE(ABORT, 'pec_audit_log is append-only');
END;

CREATE INDEX IF NOT EXISTS idx_pec_messages_received ON pec_messages(tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_pec_messages_header ON pec_messages(tenant_id, message_id_header);
CREATE INDEX IF NOT EXISTS idx_pec_messages_quality ON pec_messages(tenant_id, quality_status);
CREATE INDEX IF NOT EXISTS idx_pec_jobs_due ON pec_jobs(status, available_at, priority);
CREATE INDEX IF NOT EXISTS idx_pec_local_runs_status ON pec_local_acquire_runs(tenant_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_run ON pec_local_acquire_items(tenant_id, run_id, status);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_email ON pec_local_acquire_items(tenant_id, email_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_message ON pec_local_acquire_items(tenant_id, message_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_pec_local_items_deadline ON pec_local_acquire_items(tenant_id, deadline_status, due_date);
CREATE INDEX IF NOT EXISTS idx_pec_audit_resource ON pec_audit_log(resource_type, resource_id);
"""


class ManagedConnection(sqlite3.Connection):
    """Connessione SQLite che chiude il file al termine del context manager."""

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        try:
            result = super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()
        return bool(result)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def decode_header_value(value: Any) -> str:
    if not value:
        return ""
    decoded: list[str] = []
    for chunk, charset in decode_header(str(value)):
        if isinstance(chunk, bytes):
            for candidate in (charset, "utf-8", "windows-1252", "iso-8859-1"):
                if not candidate:
                    continue
                try:
                    decoded.append(chunk.decode(candidate, errors="replace"))
                    break
                except LookupError:
                    continue
        else:
            decoded.append(str(chunk))
    return " ".join(part.strip() for part in decoded if part).strip()


def clean_text(value: Any, limit: int = 0) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def parsedate_iso(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        pass
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return ""


def parse_italian_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("\\", "/").replace("-", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def field_result(value: Any, confidence: float, motivation: str, features: Iterable[str]) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 3),
        "motivation": motivation,
        "features": [str(item) for item in features if str(item or "").strip()],
    }


def message_from_bytes(raw_mime: bytes) -> Message:
    return email.message_from_bytes(raw_mime, policy=policy.default)


def extract_addresses(value: Any) -> list[dict[str, str]]:
    decoded = decode_header_value(value)
    return [
        {"name": clean_text(name), "email": clean_text(addr).lower()}
        for name, addr in getaddresses([decoded])
        if clean_text(name) or clean_text(addr)
    ]


def part_payload(part: Message) -> bytes:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    if part.get_content_type() == "message/rfc822":
        nested = part.get_payload()
        if isinstance(nested, list):
            chunks = []
            for item in nested:
                if hasattr(item, "as_bytes"):
                    chunks.append(item.as_bytes(policy=policy.default))
                elif item is not None:
                    chunks.append(str(item).encode("utf-8", errors="replace"))
            return b"\r\n".join(chunks)
        if isinstance(nested, str):
            return nested.encode("utf-8", errors="replace")
    if isinstance(payload, str):
        return payload.encode("utf-8", errors="replace")
    return b""


def decode_part_text(part: Message) -> str:
    payload = part_payload(part)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    for candidate in (charset, "utf-8", "windows-1252", "iso-8859-1"):
        try:
            return payload.decode(candidate, errors="replace")
        except LookupError:
            continue
    return payload.decode("utf-8", errors="replace")


@dataclass
class AttachmentPayload:
    index: int
    filename: str
    content_type: str
    data: bytes
    nested_message_id: str = ""


def extract_message_parts(msg: Message) -> tuple[str, str, list[AttachmentPayload]]:
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[AttachmentPayload] = []
    index = 0
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.is_multipart():
            continue
        content_type = str(part.get_content_type() or "application/octet-stream")
        filename = decode_header_value(part.get_filename() or "")
        disposition = str(part.get("Content-Disposition", "") or "").lower()
        is_attachment = "attachment" in disposition or bool(filename and content_type not in {"text/plain", "text/html"})
        if content_type == "message/rfc822":
            is_attachment = True
        if is_attachment:
            data = part_payload(part)
            nested_id = ""
            if content_type == "message/rfc822" and data:
                try:
                    nested_id = str(message_from_bytes(data).get("Message-ID", "") or "").strip()
                except Exception:
                    nested_id = ""
            attachments.append(
                AttachmentPayload(
                    index=index,
                    filename=filename or f"allegato-{index + 1}{mimetypes.guess_extension(content_type) or '.bin'}",
                    content_type=content_type,
                    data=data,
                    nested_message_id=nested_id,
                )
            )
            index += 1
            continue
        if content_type == "text/plain":
            text_parts.append(decode_part_text(part))
        elif content_type == "text/html":
            html_parts.append(decode_part_text(part))
    return "\n".join(part.strip() for part in text_parts if part.strip()), "\n".join(part.strip() for part in html_parts if part.strip()), attachments


def extract_xml_texts(attachments: list[AttachmentPayload]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for item in attachments:
        name = item.filename.lower()
        if item.content_type in {"application/xml", "text/xml"} or name.endswith(".xml"):
            try:
                texts[item.filename] = item.data.decode("utf-8", errors="replace")
            except Exception:
                texts[item.filename] = ""
            continue
        if name.endswith(".zip") or item.content_type in {"application/zip", "application/x-zip-compressed"}:
            try:
                with zipfile.ZipFile(io.BytesIO(item.data)) as archive:
                    for member in archive.namelist()[:50]:
                        member_lower = member.lower()
                        if not member_lower.endswith(".xml"):
                            continue
                        info = archive.getinfo(member)
                        if info.file_size > 2 * 1024 * 1024:
                            continue
                        with archive.open(member) as handle:
                            texts[f"{item.filename}:{member}"] = handle.read().decode("utf-8", errors="replace")
            except Exception:
                continue
    return texts


def xml_tag_value(xml_text: str, names: Iterable[str]) -> str:
    for name in names:
        pattern = re.compile(rf"<(?:\w+:)?{re.escape(name)}[^>]*>(.*?)</(?:\w+:)?{re.escape(name)}>", re.I | re.S)
        match = pattern.search(xml_text or "")
        if match:
            return clean_text(re.sub(r"<[^>]+>", " ", match.group(1)))
    return ""


def extract_procedural_dates(sources: dict[str, str], plain_text: str = "") -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_candidate(*, source: str, label: str, raw_date: str, context: str, confidence: float) -> None:
        iso_date = parse_italian_date(raw_date)
        if not iso_date:
            return
        clean_label = clean_text(label or "Data processuale", 80)
        clean_context = clean_text(context, 260)
        key = (iso_date, clean_label.lower(), clean_text(source, 120))
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            {
                "date": iso_date,
                "raw_date": raw_date,
                "label": clean_label,
                "source": clean_text(source, 180),
                "context": clean_context,
                "confidence": round(max(0.0, min(1.0, confidence)), 3),
            }
        )

    tag_labels = {
        "DataUdienza": "Udienza",
        "DataScadenza": "Scadenza",
        "DataTermine": "Termine",
        "DataComparizione": "Comparizione",
        "DataCameraConsiglio": "Camera di consiglio",
    }
    for source, text in sources.items():
        for tag, label in tag_labels.items():
            value = xml_tag_value(text, (tag,))
            if value:
                add_candidate(source=source, label=label, raw_date=value, context=f"{tag}: {value}", confidence=0.94)
        searchable = clean_text(re.sub(r"<[^>]+>", " ", text), 20000)
        for pattern in (
            r"\b(?P<label>udienza|pubblica udienza|camera di consiglio|comparizione|rinvio|discussione)\b.{0,80}?\b(?:del|per il|per|al|il)\s+(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"\b(?P<label>termine|scadenza|deposito|costituzione)\b.{0,80}?\b(?:del|entro il|entro|al|il)\s+(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ):
            for match in re.finditer(pattern, searchable, flags=re.I):
                start = max(0, match.start() - 90)
                end = min(len(searchable), match.end() + 120)
                add_candidate(
                    source=source,
                    label=match.group("label"),
                    raw_date=match.group("date"),
                    context=searchable[start:end],
                    confidence=0.88,
                )
    if plain_text:
        searchable = clean_text(plain_text, 20000)
        for match in re.finditer(
            r"\b(?P<label>udienza|pubblica udienza|camera di consiglio|termine|scadenza)\b.{0,80}?\b(?:del|per il|per|al|il|entro il|entro)\s+(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            searchable,
            flags=re.I,
        ):
            start = max(0, match.start() - 90)
            end = min(len(searchable), match.end() + 120)
            add_candidate(
                source="corpo PEC",
                label=match.group("label"),
                raw_date=match.group("date"),
                context=searchable[start:end],
                confidence=0.74,
            )
    return sorted(candidates, key=lambda item: str(item.get("date") or ""))


def receipt_type_from_text(text: str) -> tuple[str, list[str]]:
    lower = text.lower()
    mapping = [
        ("accettazione", ("accettazione", "ricevuta di accettazione")),
        ("avvenuta_consegna", ("avvenuta consegna", "consegna")),
        ("mancata_consegna", ("mancata consegna", "non accettazione", "errore consegna")),
        ("presa_in_carico", ("presa in carico",)),
        ("anomalia", ("anomalia", "rilevazione virus")),
    ]
    for label, needles in mapping:
        found = [needle for needle in needles if needle in lower]
        if found:
            return label, found
    return "", []


def extract_rg_candidates(text: str) -> list[str]:
    patterns = [
        re.compile(r"\bR\.?\s*G\.?\s*(?:n\.?|numero)?\s*[:\-]?\s*(\d{1,7})\s*/\s*(\d{4})\b", re.I),
        re.compile(r"\bRegistro\s+Generale\s*(?:n\.?|numero)?\s*[:\-]?\s*(\d{1,7})\s*/\s*(\d{4})\b", re.I),
        re.compile(r"\bRG\s*(\d{1,7})-(\d{4})\b", re.I),
    ]
    values: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(text or ""):
            value = f"{match.group(1)}/{match.group(2)}"
            if value not in seen:
                seen.add(value)
                values.append(value)
    return values


def _first_profile_value(text: str, patterns: Iterable[str], *, limit: int = 180) -> str:
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.I | re.M)
        if match:
            value = match.group(1) if match.groups() else match.group(0)
            return clean_text(value, limit).strip(" .;:-")
    return ""


def _profile_lines_value(text: str, label: str, *, limit: int = 180) -> str:
    return _first_profile_value(text, (rf"^\s*{re.escape(label)}\s*:\s*(.+?)\s*$",), limit=limit)


PROFILE_INLINE_LABELS = (
    "Sez/Coll.",
    "Tipo procedimento",
    "Numero di Ruolo generale",
    "Numero Ruolo",
    "Giudice",
    "Attore Principale",
    "Convenuto Principale",
    "Ricorr. principale",
    "Resist. principale",
    "Oggetto",
    "Descrizione",
    "Note",
    "Registrato da",
    "CodiceUG",
    "CodiceFiscaleDestinatario",
)


def _profile_value(text: str, labels: str | Iterable[str], *, limit: int = 180) -> str:
    label_values = (labels,) if isinstance(labels, str) else tuple(labels)
    for label in label_values:
        lookahead = "|".join(re.escape(item) for item in PROFILE_INLINE_LABELS if item != label)
        match = re.search(
            rf"\b{re.escape(label)}\s*:\s*(.+?)(?=\s+(?:{lookahead})\s*:|\s+Notificato\s+alla\s+PEC|\s+--|$)",
            text or "",
            flags=re.I | re.S,
        )
        if match:
            return clean_text(match.group(1), limit).strip(" .;:-")
        line_value = _profile_lines_value(text, label, limit=limit)
        if line_value:
            return line_value
    return ""


def _hearing_datetime_from_text(text: str) -> str:
    patterns = (
        r"\bFISSAT[AO]?\s+UDIENZA[^\n]{0,160}?\bIL\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}[:.]\d{2})",
        r"\bUDIENZA[^\n]{0,160}?\bIL\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}[:.]\d{2})",
        r"\bUDIENZA[^\n]{0,160}?\b(\d{1,2}/\d{1,2}/\d{4})\s+(?:ore\s+)?(\d{1,2}[:.]\d{2})",
    )
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.I)
        if match:
            if len(match.groups()) == 2:
                return clean_text(f"{match.group(1)} {match.group(2).replace('.', ':')}", 80)
            return clean_text(match.group(1).replace(".", ":"), 80)
    return ""


def build_pec_procedural_profile(
    *,
    subject: str = "",
    body_text: str = "",
    xml_texts: dict[str, str] | None = None,
    rg_candidates: list[str] | None = None,
    sent_date: str = "",
    delivery_date: str = "",
    event_type: str = "",
    semantic_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estrae una scheda operativa da EML/XML per ragionamento da studio legale."""

    sources = xml_texts or {}
    xml_joined = "\n".join(str(value or "") for value in sources.values())
    haystack = "\n".join([subject or "", body_text or "", xml_joined])
    haystack = haystack.replace("<![CDATA[", " ").replace("]]>", " ")
    readable = re.sub(r"<[^>]+>", " ", haystack)
    rg_values = list(rg_candidates or extract_rg_candidates(readable))
    office = _first_profile_value(
        readable,
        (
            r"^\s*((?:GIUDICE DI PACE|TRIBUNALE|CORTE D['’]APPELLO|CORTE DI CASSAZIONE|PROCURA|TAR|CONSIGLIO DI STATO)\s+(?:di|DI)\s+[^\n.]+)\.?\s*$",
            r"\bUfficio(?:\s+giudiziario)?\s*[:\-]\s*([^\n]+)",
            r"\bCancelleria\s+(?:del|della|di)\s+([^\n]+)",
        ),
    )
    if not office:
        context = semantic_context or {}
        office = clean_text(context.get("office_hint") or "", 160)

    profile = {
        "ufficio": office,
        "cancelleria": _first_profile_value(
            readable,
            (
                r"\bcancelliere\s+([A-ZÀ-Ü][A-ZÀ-Ü'’.\s-]{2,})\s+ha\s+provveduto",
                r"\bRegistrato\s+da\s+([A-ZÀ-Ü][A-ZÀ-Ü'’.\s-]{2,})",
            ),
        ),
        "registrato_da": _profile_value(readable, "Registrato da"),
        "sezione": _profile_value(readable, ("Sezione", "Sez/Coll.")),
        "tipo_procedimento": _profile_value(readable, "Tipo procedimento", limit=240),
        "numero_rg": _profile_value(readable, ("Numero di Ruolo generale", "Numero Ruolo")) or (rg_values[0] if rg_values else ""),
        "giudice": _profile_value(readable, "Giudice"),
        "attore_principale": _profile_value(readable, ("Attore Principale", "Ricorr. principale"), limit=240),
        "convenuto_principale": _profile_value(readable, ("Convenuto Principale", "Resist. principale"), limit=240),
        "data_evento": _profile_value(readable, "Data Evento"),
        "tipo_evento": _profile_value(readable, "Tipo Evento", limit=240),
        "oggetto_evento": _profile_value(readable, "Oggetto", limit=280) or subject,
        "descrizione_evento": _profile_value(readable, "Descrizione", limit=320),
        "notificato_il": _first_profile_value(
            readable,
            (
                r"Notificato\s+alla\s+PEC\s*/\s*in\s+cancelleria\s+il\s+(.+?)(?:\s+Registrato\s+da|\s+--|\n|$)",
                r"\bin\s+data\s+(\d{1,2}/\d{1,2}/\d{4}\s+alle\s+ore\s+\d{1,2}:\d{2})",
            ),
            limit=120,
        ),
        "codice_ufficio": xml_tag_value(xml_joined, ("CodiceUG", "codiceUG", "Ufficio")),
        "codice_fiscale_destinatario": xml_tag_value(xml_joined, ("CodiceFiscaleDestinatario", "codiceFiscaleDestinatario")),
        "data_invio": sent_date,
        "data_consegna": delivery_date,
        "evento_pec": event_type,
        "documenti_letti": sorted(str(name) for name in sources.keys() if str(name or "").strip()),
    }
    lower = readable.lower()
    hearing_datetime = _hearing_datetime_from_text(readable)
    if hearing_datetime:
        profile["udienza_data_ora"] = hearing_datetime
    if "audiovisiv" in lower or "strumenti audiovisivi" in lower:
        profile["modalita_udienza"] = "strumenti audiovisivi"
    elif any(needle in lower for needle in ("udienza da remoto", "videoconferenza", "aula virtuale", "stanza virtuale")):
        profile["modalita_udienza"] = "da remoto"
    practice_phase = ""
    if "sentenza" in lower:
        practice_phase = "provvedimento/sentenza da leggere e notificare o presidiare"
    elif "deposito" in lower:
        practice_phase = "deposito telematico da completare o monitorare"
    elif "notificazione" in lower or "notifica" in lower:
        practice_phase = "notifica/comunicazione che può generare termini"
    elif "udienza" in lower:
        practice_phase = "udienza o rinvio da calendarizzare"
    profile["fase_pratica"] = practice_phase

    essentials = []
    if profile["ufficio"]:
        essentials.append(f"Ufficio: {profile['ufficio']}")
    if profile["giudice"]:
        essentials.append(f"Giudice: {profile['giudice']}")
    if profile["numero_rg"]:
        essentials.append(f"RG: {profile['numero_rg']}")
    if profile["tipo_evento"] or profile["oggetto_evento"]:
        essentials.append(f"Evento: {profile['tipo_evento'] or profile['oggetto_evento']}")
    if profile.get("udienza_data_ora"):
        essentials.append(f"Udienza: {profile['udienza_data_ora']}")
    if profile.get("modalita_udienza"):
        essentials.append(f"Modalità udienza: {profile['modalita_udienza']}")
    if profile["notificato_il"] or delivery_date or sent_date:
        essentials.append(f"Ora da presidiare: {profile['notificato_il'] or delivery_date or sent_date}")
    profile["sintesi_operativa"] = essentials

    checklist = [
        "Collegare la PEC al fascicolo corretto usando RG, ufficio, parti e oggetto.",
        "Leggere gli allegati indicati nel messaggio originale prima di calcolare termini o inviare comunicazioni.",
        "Verificare se l'evento fa decorrere un termine processuale e registrarlo come bozza da confermare.",
        "Controllare se serve produrre un atto, una notifica, un deposito o una comunicazione al cliente.",
        "Conservare MIME, daticert/postacert, allegati e hash come prova della comunicazione.",
    ]
    if "sentenza" in lower:
        checklist.extend(
            [
                "Leggere la sentenza o il provvedimento allegato e annotare esito, motivazione decisiva e termini successivi.",
                "Verificare attestazione di conformità, notifica della sentenza e prova completa se lo studio decide di notificare.",
            ]
        )
    if "procura" in lower:
        checklist.append("Verificare procura alle liti e coerenza con l'atto depositato o notificato.")
    if profile.get("udienza_data_ora") or profile.get("modalita_udienza"):
        checklist.extend(
            [
                "Registrare l'udienza in agenda con data, ora, giudice, fascicolo, parti e modalità di partecipazione.",
                "Se l'udienza è con strumenti audiovisivi, leggere l'allegato PDF per recuperare link, ID riunione e istruzioni di accesso.",
            ]
        )
    profile["checklist_avvocato"] = list(dict.fromkeys(checklist))

    questions = [
        "Quale atto o provvedimento è arrivato e quale allegato devo leggere per primo?",
        "Questa PEC apre un termine processuale, un adempimento di cancelleria o solo un presidio informativo?",
        "A quale fascicolo va collegata la comunicazione e con quale confidenza?",
        "Quali documenti mancano per chiudere prova, deposito o notifica?",
        "Quale azione devo fare adesso: agenda, scadenza, task, notifica, deposito, comunicazione cliente o nulla?",
    ]
    if profile["giudice"]:
        questions.append("Il giudice indicato incide su udienza, fase decisoria o strategia del fascicolo?")
    if "sentenza" in lower:
        questions.append("Quali termini decorrono dalla sentenza e cosa devo preparare per eventuale notifica o impugnazione?")
    if profile.get("udienza_data_ora") or profile.get("modalita_udienza"):
        questions.append("L'udienza va svolta in presenza o con strumenti audiovisivi, e dove si trova il link di collegamento?")
    profile["domande_lex"] = list(dict.fromkeys(questions))

    return {key: value for key, value in profile.items() if value not in ("", [], {})}


REMOTE_HEARING_KEYWORDS = (
    "audiovisiv",
    "strumenti audiovisivi",
    "udienza da remoto",
    "udienza audiovisiva",
    "udienza telematica",
    "trattazione da remoto",
    "videoconferenza",
    "aula virtuale",
    "stanza virtuale",
    "collegamento audiovisivo",
    "collegamento da remoto",
    "collegarsi",
    "link per la connessione",
    "link di collegamento",
    "microsoft teams",
    "teams.microsoft",
    "zoom.us",
    "webex",
    "meet.google",
    "meeting id",
    "id riunione",
    "codice accesso",
)

REMOTE_HEARING_BLOCKED_DOMAINS = (
    "pst.giustizia.it",
    "servizipst.giustizia.it",
    "schemi.processotelematico.giustizia.it",
    "processotelematico.giustizia.it",
    "ca1.agid.gov.it",
    "agid.gov.it",
    "actalis.it",
    "cacert.actalis.it",
    "ocsp07.actalis.it",
    "w3.org",
    "uri.etsi.org",
    "fatturapa.gov.it",
    "agenziaentrate.gov.it",
    "ivaservizi.agenziaentrate.gov.it",
    "normattiva.it",
    "gazzettaufficiale.it",
)

REMOTE_HEARING_BLOCKED_PATH_PARTS = (
    "/ocsp",
    "ocsp",
    "/crl",
    ".crl",
    ".dtd",
    ".xsd",
    ".xml",
    ".p7s",
    ".cer",
    ".crt",
    "schema",
    "schemi",
    "download",
    "xmldsig",
    "signedproperties",
    "xmlenc",
    "certificat",
    "fattura",
    "messaggi/v",
)

REMOTE_HEARING_ALLOWED_DOMAINS = (
    "teams.microsoft.com",
    "zoom.us",
    "webex.com",
    "meet.google.com",
    "meet.jit.si",
    "gotomeeting.com",
    "global.gotomeeting.com",
    "bluejeans.com",
    "whereby.com",
    "lifesizecloud.com",
)

REMOTE_HEARING_ALLOWED_HOST_KEYWORDS = (
    "teams",
    "zoom",
    "webex",
    "gotomeeting",
    "bluejeans",
    "whereby",
    "lifesize",
    "videoconf",
    "videoconferenza",
    "conference",
)

REMOTE_HEARING_ALLOWED_PATH_PARTS = (
    "meetup-join",
    "/j/",
    "/wc/",
    "/meet/",
    "join",
    "meeting",
    "riunione",
    "stanza",
    "aula",
    "videoconf",
    "conference",
)

REMOTE_HEARING_LINK_CONTEXT_KEYWORDS = (
    "udienza",
    "audiovisiv",
    "collegamento",
    "connessione",
    "riunione",
    "meeting",
    "stanza virtuale",
    "aula virtuale",
    "videoconferenza",
    "partecipare",
    "collegarsi",
    "teams",
    "zoom",
    "webex",
)

REMOTE_HEARING_NEGATIVE_CONTEXT_KEYWORDS = (
    "sentenza a verbale",
    "art. 127 ter",
    "art. 127-ter",
    "127 ter cpc",
    "127-ter cpc",
    "note scritte",
    "trattazione scritta",
    "sostituzione dell'udienza",
    "sostituzione udienza",
    "depositate in sostituzione",
    "fattura elettronica",
    "fatturapa",
    "xml signature",
    "xmldsig",
    "signedproperties",
    "ocsp",
    "crl",
)


def _attachment_name(item: dict[str, Any]) -> str:
    return clean_text(item.get("filename") or item.get("name") or "", 240)


def _attachment_content_type(item: dict[str, Any]) -> str:
    return clean_text(item.get("content_type") or item.get("mime") or "", 160).lower()


def _is_pdf_attachment(item: dict[str, Any]) -> bool:
    name = _attachment_name(item).lower()
    content_type = _attachment_content_type(item)
    return (
        content_type.startswith("application/pdf")
        or name.endswith((".pdf", ".pdf.p7m", ".pdf.zip"))
    )


def _attachment_ocr_text(item: dict[str, Any]) -> str:
    return clean_text(item.get("ocr_text") or item.get("text") or "", 20000)


def _is_remote_hearing_technical_attachment(item: dict[str, Any]) -> bool:
    name = _attachment_name(item).lower()
    content_type = _attachment_content_type(item)
    classification = clean_text(item.get("classification") or "", 80).lower()
    if classification in {"firma", "daticert", "postacert", "ricevute"}:
        return True
    if name.endswith((".p7s", ".cer", ".crt", ".crl")):
        return True
    if content_type in {
        "application/pkcs7-signature",
        "application/pkcs7-mime",
        "application/x-pkcs7-signature",
    } and not name.endswith((".pdf.p7m", ".pdf")):
        return True
    return False


def _remote_hearing_negative_context(text: str) -> bool:
    lower = clean_text(text, 12000).lower()
    if not lower:
        return False
    return any(keyword in lower for keyword in REMOTE_HEARING_NEGATIVE_CONTEXT_KEYWORDS)


def _remote_hearing_positive_context(text: str) -> bool:
    lower = clean_text(text, 12000).lower()
    if not lower:
        return False
    if _remote_hearing_negative_context(lower) and not any(
        keyword in lower
        for keyword in (
            "strumenti audiovisivi",
            "udienza da remoto",
            "udienza audiovisiva",
            "videoconferenza",
            "stanza virtuale",
            "aula virtuale",
            "teams.microsoft",
            "zoom.us",
            "webex",
        )
    ):
        return False
    return any(keyword in lower for keyword in REMOTE_HEARING_KEYWORDS)


def _preserved_url_value(value: Any) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return re.sub(r"[\r\n\t ]+", "", text)


def _normalise_extracted_url(raw_url: str) -> tuple[str, bool, str]:
    url = _preserved_url_value(raw_url)
    exact = url == raw_url.strip()
    note = ""
    if url.startswith("www."):
        url = f"https://{url}"
        exact = False
        note = "aggiunto schema https a URL iniziato con www"
    for trailing in (".", ",", ";"):
        if url.endswith(trailing):
            url = url[:-1]
            exact = False
            note = "rimossa punteggiatura finale non parte del link"
    pairs = (("(", ")"), ("[", "]"), ("{", "}"))
    changed = True
    while changed and url:
        changed = False
        for opening, closing in pairs:
            if url.endswith(closing) and url.count(closing) > url.count(opening):
                url = url[:-1]
                exact = False
                note = "rimossa parentesi finale esterna al link"
                changed = True
    return url, exact, note


def _url_host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _remote_hearing_url_context(text: str, start: int, end: int, radius: int = 180) -> str:
    source = str(text or "")
    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", end)
    if line_end < 0:
        line_end = len(source)
    left = max(0, min(line_start, start - radius))
    right = min(len(source), max(line_end, end + radius))
    return clean_text(source[left:right], 600)


def _is_remote_hearing_url(url: str, *, context: str = "") -> tuple[bool, str]:
    value = _preserved_url_value(url)
    if not value:
        return False, "url_vuoto"
    candidate = value if re.match(r"^[a-z][a-z0-9+.-]*://", value, flags=re.I) else f"https://{value}"
    try:
        parsed = urlsplit(candidate)
    except Exception:
        return False, "url_non_valido"
    host = (parsed.hostname or "").lower().lstrip(".")
    path = f"{parsed.path or ''}?{parsed.query or ''}".lower()
    if not host:
        return False, "host_assente"
    if host.startswith(("ocsp", "crl")) or ".ocsp" in host or ".crl" in host:
        return False, "servizio_certificati_non_link_udienza"
    if any(_url_host_matches(host, domain) for domain in REMOTE_HEARING_BLOCKED_DOMAINS):
        return False, "fonte_tecnica_o_istituzionale_non_link_udienza"
    if any(part in host or part in path for part in REMOTE_HEARING_BLOCKED_PATH_PARTS):
        return False, "risorsa_tecnica_non_link_udienza"
    if any(_url_host_matches(host, domain) for domain in REMOTE_HEARING_ALLOWED_DOMAINS):
        return True, "piattaforma_udienza_riconosciuta"
    if any(keyword in host for keyword in REMOTE_HEARING_ALLOWED_HOST_KEYWORDS):
        return True, "host_compatibile_con_udienza_remota"
    context_lower = clean_text(context, 600).lower()
    has_remote_context = any(keyword in context_lower for keyword in REMOTE_HEARING_LINK_CONTEXT_KEYWORDS)
    if has_remote_context and any(part in path for part in REMOTE_HEARING_ALLOWED_PATH_PARTS):
        return True, "contesto_e_percorso_indicano_collegamento_udienza"
    if has_remote_context and re.search(r"\blink\b.{0,80}\b(udienza|collegamento|connessione|riunione|meeting)\b", context_lower):
        return True, "contesto_testuale_indica_link_udienza"
    return False, "url_non_specifico_per_udienza_remota"


def _extract_remote_hearing_links(text: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r"\b(?:https?://|www\.)[^\s<>'\"]+", text or "", flags=re.I):
        raw_url = match.group(0)
        value, exact, note = _normalise_extracted_url(raw_url)
        context = _remote_hearing_url_context(str(text or ""), match.start(), match.end())
        accepted, classification_reason = _is_remote_hearing_url(value, context=context)
        if not accepted:
            continue
        normalised = value.lower()
        if value and normalised not in seen:
            seen.add(normalised)
            values.append(
                {
                    "url": value,
                    "raw_url": raw_url,
                    "exact": exact,
                    "integrity": "exact" if exact else "normalizzato_da_verificare",
                    "normalization_note": note,
                    "classification_reason": classification_reason,
                }
            )
    return values[:8]


def _extract_remote_hearing_times(text: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    patterns = (
        r"\b(?:udienza|discussione|collegamento|connessione|videoconferenza|audiovisiv)[^\n]{0,180}?\b(?:il\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s+(\d{1,2}[:.]\d{2})",
        r"\b(?:udienza|collegamento|connessione|videoconferenza)[^\n]{0,140}?\b(?:il\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{4})[^\n]{0,100}?\b(?:ore|h\.?)\s*(\d{1,2}[:.]\d{2})",
        r"\b(?:udienza|collegamento|connessione|videoconferenza)[^\n]{0,140}?\b(?:ore|h\.?)\s*(\d{1,2}[:.]\d{2})",
        r"\b(?:ore|h\.?)\s*(\d{1,2}[:.]\d{2})[^\n]{0,100}?\b(?:udienza|collegamento|connessione|videoconferenza)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.I):
            groups = [part.replace(".", ":") for part in match.groups() if part]
            value = " ore ".join(groups) if len(groups) == 2 else groups[0] if groups else ""
            value = clean_text(value, 80)
            normalised = value.lower()
            if value and normalised not in seen:
                seen.add(normalised)
                values.append(value)
    return values[:5]


def _extract_remote_hearing_access_lines(text: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for raw_line in re.split(r"[\r\n]+", text or ""):
        line = clean_text(raw_line, 240)
        if not line:
            continue
        lower = line.lower()
        if any(
            needle in lower
            for needle in (
                "id riunione",
                "meeting id",
                "id meeting",
                "codice accesso",
                "passcode",
                "password",
                "stanza virtuale",
                "aula virtuale",
                "link",
                "teams",
                "zoom",
                "webex",
            )
        ):
            urls = [match.group(0) for match in re.finditer(r"\b(?:https?://|www\.)[^\s<>'\"]+", line, flags=re.I)]
            if urls and not any(_is_remote_hearing_url(url, context=line)[0] for url in urls):
                continue
            normalised = lower
            if normalised not in seen:
                seen.add(normalised)
                values.append(line)
    return values[:8]


def build_remote_hearing_profile(parsed: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
    """Individua udienze remote/audiovisive e link contenuti anche nei PDF letti via OCR."""

    headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    body = parsed.get("body") if isinstance(parsed.get("body"), dict) else {}
    parsed_profile = parsed.get("procedural_profile") if isinstance(parsed.get("procedural_profile"), dict) else {}
    sources: list[dict[str, Any]] = [
        {"name": "Oggetto PEC", "type": "oggetto", "text": clean_text(headers.get("subject") or "", 2000)},
        {"name": "Corpo PEC", "type": "corpo", "text": clean_text(body.get("text") or body.get("html") or "", 20000)},
        {
            "name": "Profilo Comunicazione.xml",
            "type": "profilo",
            "text": clean_text(
                " ".join(
                    str(parsed_profile.get(key) or "")
                    for key in (
                        "oggetto_evento",
                        "descrizione_evento",
                        "udienza_data_ora",
                        "modalita_udienza",
                        "notificato_il",
                    )
                ),
                4000,
            ),
        },
    ]
    for item in attachments:
        if _is_remote_hearing_technical_attachment(item):
            continue
        name = _attachment_name(item) or "Allegato"
        text = _attachment_ocr_text(item)
        if text:
            sources.append({"name": name, "type": "pdf" if _is_pdf_attachment(item) else "allegato", "text": text})

    all_text = "\n".join(str(source.get("text") or "") for source in sources)
    lower_all = all_text.lower()
    remote_detected = _remote_hearing_positive_context(all_text)
    link_sources: list[dict[str, str]] = []
    seen_links: set[str] = set()
    times: list[str] = []
    access_lines: list[str] = []
    source_names: list[str] = []
    for source in sources:
        source_text = str(source.get("text") or "")
        if _remote_hearing_positive_context(source_text):
            source_name = str(source.get("name") or "")
            if source_name and source_name not in source_names:
                source_names.append(source_name)
        for link in _extract_remote_hearing_links(source_text):
            link_record = dict(link)
            url = str(link_record.get("url") or "")
            key = url.lower()
            if key not in seen_links:
                seen_links.add(key)
                link_record["source"] = str(source.get("name") or "testo PEC")
                link_record["exact_match"] = bool(link_record.get("exact"))
                link_sources.append(link_record)
        for value in _extract_remote_hearing_times(source_text):
            if value not in times:
                times.append(value)
        for line in _extract_remote_hearing_access_lines(source_text):
            if line not in access_lines:
                access_lines.append(line)

    pdf_attachments = [item for item in attachments if _is_pdf_attachment(item)]
    pdf_without_text = [
        _attachment_name(item) or "PDF allegato"
        for item in pdf_attachments
        if not _attachment_ocr_text(item)
    ]
    pdf_with_text = [
        _attachment_name(item) or "PDF allegato"
        for item in pdf_attachments
        if _attachment_ocr_text(item)
    ]
    body_says_link_in_attachment = bool(
        re.search(
            r"\b(?:link|collegamento|connessione|stanza|aula|riunione)\b[^\n]{0,140}\b(?:allegat[oaie]|pdf|documento)",
            all_text,
            flags=re.I,
        )
    )
    pdf_required = bool((remote_detected or (body_says_link_in_attachment and "udienza" in lower_all)) and pdf_attachments and not link_sources)
    mode = ""
    if "audiovisiv" in lower_all:
        mode = "audiovisiva"
    elif "videoconferenza" in lower_all or "teams" in lower_all or "zoom" in lower_all or "webex" in lower_all:
        mode = "videoconferenza"
    elif remote_detected:
        mode = "da remoto"
    checklist: list[str] = []
    questions: list[str] = []
    warnings: list[str] = []
    if remote_detected or pdf_required or link_sources:
        checklist.extend(
            [
                "Leggere il PDF dell'udienza e verificare link, ora, stanza virtuale, ID riunione e codice di accesso.",
                "Inserire in agenda l'udienza con link di collegamento, orario in ora italiana e promemoria operativo.",
                "Avvisare avvocato e cliente sulle modalità di collegamento e conservare il PDF come prova organizzativa.",
            ]
        )
        questions.extend(
            [
                "Il link dell'udienza audiovisiva è nel corpo PEC o in un PDF allegato?",
                "Qual è l'orario esatto dell'udienza in ora italiana e quale piattaforma va usata?",
                "Chi deve partecipare e quali documenti o istruzioni vanno preparati prima del collegamento?",
            ]
        )
    if pdf_required:
        warnings.append("Il messaggio richiama un'udienza remota o un collegamento, ma il link non è ancora stato estratto: leggere/OCR il PDF allegato.")
        checklist.insert(0, "Aprire o acquisire con OCR il PDF allegato perché può contenere il link di collegamento all'udienza.")
    if link_sources:
        checklist.append("Verificare il link estratto prima di comunicarlo o usarlo per l'accesso all'udienza.")
    if not (remote_detected or pdf_required or link_sources):
        return {}
    profile = {
        "detected": bool(remote_detected or link_sources),
        "mode": mode,
        "links": link_sources,
        "times": times,
        "access_info": access_lines,
        "sources": source_names,
        "pdf_sources": pdf_with_text,
        "pdf_pending": pdf_without_text,
        "pdf_required": pdf_required,
        "warnings": warnings,
        "checklist": list(dict.fromkeys(checklist)),
        "questions": list(dict.fromkeys(questions)),
        "numero_rg": parsed_profile.get("numero_rg") or "",
        "giudice": parsed_profile.get("giudice") or "",
        "ufficio": parsed_profile.get("ufficio") or "",
    }
    return {key: value for key, value in profile.items() if value not in ("", [], {})}


def _remote_hearing_from_report(report: dict[str, Any], proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    proposal = proposal if isinstance(proposal, dict) else {}
    for candidate in (
        proposal.get("remote_hearing"),
        report.get("remote_hearing"),
        (report.get("procedural_profile") or {}).get("remote_hearing") if isinstance(report.get("procedural_profile"), dict) else {},
    ):
        if isinstance(candidate, dict):
            return candidate
    return {}


def _remote_hearing_link_records(remote_hearing: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in list(remote_hearing.get("links") or []):
        if not isinstance(item, dict):
            continue
        url = clean_text(item.get("url") or "")
        source = clean_text(item.get("source") or "fonte PEC/allegato", 160)
        accepted, reason = _is_remote_hearing_url(url, context=source)
        if not accepted:
            continue
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        row = dict(item)
        row["url"] = url
        row["source"] = source
        row["classification_reason"] = clean_text(row.get("classification_reason") or reason, 120)
        records.append(row)
    return records


def _remote_hearing_deadline_extra(report: dict[str, Any], proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    remote = _remote_hearing_from_report(report, proposal)
    links = _remote_hearing_link_records(remote)
    first = links[0] if links else {}
    times = [clean_text(item, 80) for item in list(remote.get("times") or []) if clean_text(item, 80)]
    access_info = [
        clean_text(item, 220)
        for item in list(remote.get("access_info") or [])
        if clean_text(item, 220)
    ]
    mode = clean_text(remote.get("mode") or ("da remoto" if remote.get("detected") else ""), 80)
    return {
        "remote_hearing_detected": bool(remote.get("detected") or links or remote.get("pdf_required")),
        "remote_hearing_mode": mode,
        "remote_hearing_url": clean_text(first.get("url") or "", 1000),
        "remote_hearing_source": clean_text(first.get("source") or "", 240),
        "remote_hearing_verified": bool(first.get("exact_match") or first.get("exact")),
        "remote_hearing_integrity": clean_text(first.get("integrity") or "", 80),
        "remote_hearing_time": times[0] if times else "",
        "remote_hearing_access_info": "\n".join(access_info[:5]),
        "remote_hearing_pdf_required": bool(remote.get("pdf_required") and not links),
    }


def _remote_hearing_note_lines(report: dict[str, Any], proposal: dict[str, Any] | None = None) -> list[str]:
    extra = _remote_hearing_deadline_extra(report, proposal)
    if not extra.get("remote_hearing_detected"):
        return []
    lines = [f"Udienza da remoto: {extra.get('remote_hearing_mode') or 'da remoto'}"]
    if extra.get("remote_hearing_time"):
        lines.append(f"Orario collegamento: {extra['remote_hearing_time']}")
    if extra.get("remote_hearing_url"):
        lines.append(f"Link udienza audiovisiva: {extra['remote_hearing_url']}")
        if extra.get("remote_hearing_source"):
            lines.append(f"Fonte link udienza: {extra['remote_hearing_source']}")
        lines.append(
            "Verifica link udienza: identico alla fonte letta."
            if extra.get("remote_hearing_verified")
            else "Verifica link udienza: link normalizzato, controllo visivo richiesto."
        )
    elif extra.get("remote_hearing_pdf_required"):
        lines.append("Link udienza audiovisiva: da acquisire dal PDF allegato.")
    if extra.get("remote_hearing_access_info"):
        lines.append(f"Istruzioni accesso udienza: {clean_text(extra['remote_hearing_access_info'], 400)}")
    return lines


def _remote_hearing_updates_for_existing(existing: Any, extra: dict[str, Any], note_lines: list[str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    current_url = str(getattr(existing, "remote_hearing_url", "") or "").strip()
    current_source = str(getattr(existing, "remote_hearing_source", "") or "").strip()
    current_note = str(getattr(existing, "note", "") or "")

    def _strip_remote_note_lines(note: str) -> str:
        cleaned: list[str] = []
        for line in str(note or "").splitlines():
            marker = line.strip()
            if marker.startswith(
                (
                    "Udienza da remoto:",
                    "Orario collegamento:",
                    "Link udienza audiovisiva:",
                    "Fonte link udienza:",
                    "Verifica link udienza:",
                    "Istruzioni accesso udienza:",
                )
            ):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    if not extra.get("remote_hearing_detected"):
        stale_keys = {
            "remote_hearing_detected": False,
            "remote_hearing_mode": "",
            "remote_hearing_url": "",
            "remote_hearing_source": "",
            "remote_hearing_verified": False,
            "remote_hearing_integrity": "",
            "remote_hearing_time": "",
            "remote_hearing_access_info": "",
            "remote_hearing_pdf_required": False,
        }
        for key, value in stale_keys.items():
            current_value = getattr(existing, key, False if isinstance(value, bool) else "")
            if current_value != value and str(current_value or "").strip():
                updates[key] = value
        cleaned_note = _strip_remote_note_lines(current_note)
        if cleaned_note != current_note.strip():
            updates["note"] = cleaned_note
        return updates

    if current_url and not _is_remote_hearing_url(current_url, context=current_source)[0]:
        updates.update(
            {
                "remote_hearing_url": "",
                "remote_hearing_source": "",
                "remote_hearing_verified": False,
                "remote_hearing_integrity": "",
            }
        )
    for key, value in extra.items():
        if value in ("", [], {}, None):
            continue
        if isinstance(value, bool):
            if value and not bool(getattr(existing, key, False)):
                updates[key] = value
            continue
        if not str(getattr(existing, key, "") or "").strip():
            updates[key] = value
    if current_url and "Link udienza audiovisiva:" in current_note and not _is_remote_hearing_url(current_url, context=current_source)[0]:
        cleaned_lines: list[str] = []
        skip_link_meta = False
        for line in current_note.splitlines():
            if "Link udienza audiovisiva:" in line and current_url in line:
                skip_link_meta = True
                continue
            if skip_link_meta and (
                line.startswith("Fonte link udienza:")
                or line.startswith("Verifica link udienza:")
            ):
                continue
            skip_link_meta = False
            cleaned_lines.append(line)
        current_note = "\n".join(cleaned_lines).strip()
        updates["note"] = current_note
    missing_lines = [line for line in note_lines if line and line not in current_note]
    if missing_lines:
        updates["note"] = "\n".join(part for part in (current_note.strip(), *missing_lines) if part)
    if extra.get("remote_hearing_detected") and _enum_text(getattr(existing, "tipo", "")) != "UDIENZA":
        updates["tipo"] = "UDIENZA"
    return updates


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


LEGAL_CONTEXT_RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "pct_comunicazione_cancelleria",
        "event_hint": "comunicazione_cancelleria",
        "label": "Comunicazione o notificazione di cancelleria PCT",
        "office_hint": "Ufficio giudiziario civile",
        "keywords": ("comunicazione di cancelleria", "biglietto di cancelleria", "notificazione di cancelleria", "cancelleria", "pst", "processo civile telematico"),
        "regex": (r"\bd\.?\s*l\.?\s*179\s*/\s*2012\b", r"\bart\.?\s*16\b.*\b179\s*/\s*2012\b"),
        "min_features": 2,
        "base_confidence": 0.72,
        "norms": (
            ("D.L. 179/2012, art. 16", "Comunicazioni e notificazioni telematiche degli uffici giudiziari"),
            ("D.M. Giustizia 44/2011", "Regole tecniche del processo telematico civile e penale"),
            ("Provvedimento DGSIA 16 aprile 2014", "Specifiche tecniche PCT/PPT ex art. 34 D.M. 44/2011"),
        ),
        "questions": (
            "Quale provvedimento o atto di cancelleria e' comunicato?",
            "La comunicazione fa decorrere termini processuali o solo conoscenza dell'atto?",
            "Data e ora di consegna PEC sono certe e leggibili nei dati di certificazione?",
        ),
    },
    {
        "id": "pct_deposito_telematico",
        "event_hint": "pct_deposito",
        "label": "Deposito telematico civile",
        "office_hint": "Ufficio giudiziario civile",
        "keywords": ("deposito telematico", "busta telematica", "atto.enc", "datiatto.xml", "indicebusta", "esito controlli automatici", "esito intervento cancelleria", "accettazione deposito", "rifiuto deposito"),
        "regex": (r"\br\.?\s*g\.?\s*(?:n\.?)?\s*\d{1,7}\s*/\s*\d{4}\b", r"\bd\.?\s*l\.?\s*179\s*/\s*2012\b"),
        "min_features": 1,
        "base_confidence": 0.78,
        "norms": (
            ("D.L. 179/2012, art. 16-bis", "Deposito telematico degli atti processuali"),
            ("D.M. Giustizia 44/2011", "Regole tecniche del processo telematico"),
            ("Provvedimento DGSIA 16 aprile 2014", "Specifiche tecniche busta telematica e controlli"),
        ),
        "questions": (
            "Sono presenti atto principale, procura se necessaria, ricevute e eventuali esiti successivi?",
            "L'esito e' accettazione, controlli automatici, intervento cancelleria o rifiuto?",
            "Il deposito e' collegato al fascicolo corretto tramite RG, ufficio e parti?",
        ),
    },
    {
        "id": "notifica_avvocato_l53",
        "event_hint": "notifica_l53",
        "label": "Notifica in proprio dell'avvocato via PEC",
        "office_hint": "",
        "keywords": ("notificazione ai sensi della legge n. 53 del 1994", "legge 53/1994", "l. 53/1994", "art. 3-bis", "relata di notifica", "notifica in proprio", "attestazione di conformita"),
        "regex": (r"\blegge\s+n\.?\s*53\s+del\s+1994\b", r"\bl\.?\s*53\s*/\s*1994\b", r"\bart\.?\s*3[- ]?bis\b"),
        "min_features": 1,
        "base_confidence": 0.86,
        "norms": (
            ("L. 53/1994, art. 3-bis", "Notificazioni telematiche eseguite dagli avvocati"),
            ("D.L. 179/2012, artt. 16-ter e 16-undecies", "Pubblici elenchi e attestazioni di conformita"),
            ("D.P.R. 68/2005", "Prova di invio e consegna PEC"),
        ),
        "questions": (
            "L'oggetto riporta la formula di legge della notifica in proprio?",
            "Sono presenti atto notificato, relata, procura o attestazione di conformita se necessarie?",
            "Il destinatario risulta tratto da pubblico elenco valido?",
        ),
    },
    {
        "id": "notifica_giudice_pace",
        "event_hint": "notifica_giudice_pace",
        "label": "Notifica o comunicazione Giudice di Pace",
        "office_hint": "Giudice di Pace",
        "keywords": ("giudice di pace", "g.d.p.", "gdp", "notificazione", "convocazione", "decreto ingiuntivo", "opposizione a sanzione"),
        "regex": (r"\bd\.?\s*l\.?\s*179\s*/\s*2012\b", r"\bart\.?\s*16\b.*\b179\s*/\s*2012\b"),
        "min_features": 2,
        "base_confidence": 0.82,
        "norms": (
            ("D.L. 179/2012, art. 16", "Comunicazioni e notificazioni telematiche"),
            ("D.M. Giustizia 44/2011", "Regole tecniche del processo telematico"),
            ("D.P.R. 68/2005", "Ricevute PEC e dati di certificazione"),
        ),
        "questions": (
            "L'atto notificato proviene dal Giudice di Pace o da controparte?",
            "L'atto apre termine per opposizione, comparizione o pagamento?",
            "RG, ufficio e parti permettono il collegamento automatico a un fascicolo?",
        ),
    },
    {
        "id": "unep_notifica",
        "event_hint": "notifica_unep",
        "label": "Notifica UNEP o richiesta di notificazione",
        "office_hint": "UNEP",
        "keywords": ("unep", "ufficio notificazioni", "ufficiale giudiziario", "richiesta di notifica", "notifica a mezzo pec", "art. 149-bis"),
        "regex": (r"\bart\.?\s*149[- ]?bis\b",),
        "min_features": 1,
        "base_confidence": 0.78,
        "norms": (
            ("c.p.c., art. 149-bis", "Notificazione a mezzo posta elettronica"),
            ("Provvedimento DGSIA 16 aprile 2014", "Flussi telematici verso UNEP anche via PEC"),
            ("D.P.R. 68/2005", "Ricevute PEC"),
        ),
        "questions": (
            "Si tratta di richiesta all'UNEP o di notifica ricevuta dall'UNEP?",
            "Sono disponibili relazione, atto notificato e ricevute PEC?",
            "Il destinatario e l'indirizzo PEC risultano verificabili?",
        ),
    },
    {
        "id": "pat_amministrativo",
        "event_hint": "pat_notifica_o_deposito",
        "label": "Processo amministrativo telematico",
        "office_hint": "TAR o Consiglio di Stato",
        "keywords": ("processo amministrativo telematico", "pat", "siga", "tar", "consiglio di stato", "segreteria tar", "notifica del ricorso", "d.p.c.m. 40/2016", "dpcm 40/2016"),
        "regex": (r"\bd\.?\s*p\.?\s*c\.?\s*m\.?\s*40\s*/\s*2016\b", r"\bart\.?\s*14\b.*\bd\.?\s*p\.?\s*c\.?\s*m\.?\s*40\b"),
        "min_features": 1,
        "base_confidence": 0.78,
        "norms": (
            ("D.P.C.M. 40/2016", "Regole tecnico-operative del processo amministrativo telematico"),
            ("c.p.a., art. 136 e allegato 2", "Comunicazioni e depositi telematici nel processo amministrativo"),
            ("Reg. UE 910/2014 eIDAS", "Firme elettroniche e servizi fiduciari"),
        ),
        "questions": (
            "La PEC documenta notifica del ricorso, deposito PAT o comunicazione di segreteria?",
            "La prova della notifica contiene messaggio completo, atto e ricevuta di avvenuta consegna?",
            "Formato firma e file allegati sono coerenti con PAT e specifiche applicabili?",
        ),
    },
    {
        "id": "ptt_tributario",
        "event_hint": "ptt_notifica_o_deposito",
        "label": "Processo tributario telematico",
        "office_hint": "Corte di giustizia tributaria",
        "keywords": ("processo tributario telematico", "ptt", "sigit", "s.i.gi.t", "corte di giustizia tributaria", "commissione tributaria", "ricorso tributario", "controdeduzioni telematiche", "decreto 163/2013"),
        "regex": (r"\bd\.?\s*m\.?\s*163\s*/\s*2013\b", r"\bart\.?\s*16[- ]?bis\b.*\bd\.?\s*lgs\.?\s*546\s*/\s*1992\b"),
        "min_features": 1,
        "base_confidence": 0.78,
        "norms": (
            ("D.M. MEF 163/2013", "Regole del processo tributario telematico"),
            ("D.Lgs. 546/1992, art. 16-bis", "Comunicazioni, notificazioni e depositi telematici tributari"),
            ("D.P.R. 68/2005", "PEC e ricevute"),
        ),
        "questions": (
            "La PEC riguarda notifica del ricorso, deposito PTT o comunicazione della Corte tributaria?",
            "Sono presenti ricevute PEC, atto e allegati fiscali richiamati?",
            "Il termine fiscale/processuale va calcolato da consegna PEC, deposito o provvedimento?",
        ),
    },
    {
        "id": "penale_snt",
        "event_hint": "penale_snt",
        "label": "Notificazione o comunicazione penale SNT",
        "office_hint": "Ufficio penale",
        "keywords": ("sistema notificazioni telematiche", "snt", "notificazioni telematiche penali", "procura della repubblica", "tribunale penale", "atti del pubblico ministero", "art. 151 c.p.p", "art. 148 c.p.p"),
        "regex": (r"\bart\.?\s*151\b.*\bc\.?\s*p\.?\s*p\.?\b", r"\bart\.?\s*148\b.*\bc\.?\s*p\.?\s*p\.?\b"),
        "min_features": 1,
        "base_confidence": 0.78,
        "norms": (
            ("D.L. 179/2012, art. 16", "Notificazioni e comunicazioni telematiche in ambito giustizia"),
            ("Circolare Ministero Giustizia 11 dicembre 2014", "Avvio SNT penale"),
            ("c.p.p., artt. 148 e 151", "Notificazioni e atti del pubblico ministero"),
        ),
        "questions": (
            "La PEC e' diretta al difensore, alla parte o ad altro soggetto abilitato?",
            "L'atto penale notificato contiene termine di impugnazione, deposito o comparizione?",
            "Il canale SNT e le ricevute sono completi e riferibili all'atto allegato?",
        ),
    },
    {
        "id": "penale_pdp",
        "event_hint": "penale_deposito_portale",
        "label": "Deposito atti penali o portale penale",
        "office_hint": "Portale processo penale telematico",
        "keywords": ("portale deposito atti penali", "pdp", "deposito atti penali", "portale processo penale telematico", "nomina difensore", "deposito querela", "atti penali telematici"),
        "regex": (r"\bp\.?\s*d\.?\s*p\.?\b",),
        "min_features": 1,
        "base_confidence": 0.7,
        "norms": (
            ("D.M. Giustizia 44/2011", "Regole tecniche anche per tecnologie nel processo penale"),
            ("Provvedimento DGSIA 16 aprile 2014", "Specifiche tecniche processo civile e penale"),
            ("Normativa PPT vigente", "Depositi e portale penale da verificare sul tipo atto"),
        ),
        "questions": (
            "La PEC conferma deposito o contiene richiesta/errore del portale penale?",
            "Tipo di atto, registro e ufficio sono riconoscibili?",
            "Esistono esiti successivi o ricevute da attendere?",
        ),
    },
    {
        "id": "pec_ricevuta_certificata",
        "event_hint": "ricevuta_pec",
        "label": "Ricevuta PEC certificata",
        "office_hint": "",
        "keywords": ("ricevuta di accettazione", "ricevuta di avvenuta consegna", "avvenuta consegna", "mancata consegna", "anomalia messaggio", "daticert.xml", "postacert.eml"),
        "regex": (r"\brd?ac\b", r"\brac\b", r"\bpostacert\b"),
        "min_features": 1,
        "base_confidence": 0.74,
        "norms": (
            ("D.P.R. 68/2005, art. 6", "Ricevuta di accettazione e avvenuta consegna"),
            ("CAD, art. 48", "Trasmissione telematica con ricevute opponibili se conforme"),
            ("Reg. UE 910/2014 eIDAS", "Servizi elettronici di recapito certificato"),
        ),
        "questions": (
            "La ricevuta e' accettazione, consegna, mancata consegna o anomalia?",
            "La ricevuta contiene dati di certificazione e riferimento al messaggio originario?",
            "Per una notifica, la ricevuta contiene messaggio completo e allegati?",
        ),
    },
    {
        "id": "domicilio_digitale_pubblici_elenchi",
        "event_hint": "domicilio_digitale",
        "label": "Domicilio digitale e pubblici elenchi",
        "office_hint": "",
        "keywords": ("reginde", "ini-pec", "inipec", "inad", "registro ppaa", "pubblici elenchi", "domicilio digitale", "art. 16-ter", "art. 16-sexies"),
        "regex": (r"\bart\.?\s*16[- ]?ter\b", r"\bart\.?\s*16[- ]?sexies\b"),
        "min_features": 1,
        "base_confidence": 0.68,
        "norms": (
            ("D.L. 179/2012, artt. 16-ter e 16-sexies", "Pubblici elenchi e domicilio digitale"),
            ("CAD, artt. 6-bis, 6-quater e 62", "Indici e domicili digitali"),
            ("RegistroPPAA PST", "Pubblico elenco per notificazioni e comunicazioni"),
        ),
        "questions": (
            "Da quale pubblico elenco e' tratto l'indirizzo PEC?",
            "Il destinatario corrisponde al soggetto processuale o amministrativo?",
            "Serve attestare la provenienza dell'indirizzo per la prova della notifica?",
        ),
    },
)


def _rule_matches(rule: dict[str, Any], lower_text: str) -> list[str]:
    features: list[str] = []
    for keyword in rule.get("keywords") or ():
        needle = str(keyword).lower()
        if not needle:
            continue
        if len(needle) <= 5 and re.fullmatch(r"[a-z0-9]+", needle):
            if re.search(rf"\b{re.escape(needle)}\b", lower_text, re.I):
                features.append(f"keyword:{keyword}")
            continue
        if needle in lower_text:
            features.append(f"keyword:{keyword}")
    for pattern in rule.get("regex") or ():
        if re.search(str(pattern), lower_text, re.I | re.S):
            features.append(f"pattern:{pattern}")
    return features


def _dedupe_dicts(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        label = clean_text(item.get("label"))
        reason = clean_text(item.get("reason"))
        key = (label.lower(), reason.lower())
        if not label or key in seen:
            continue
        seen.add(key)
        result.append({"label": label, "reason": reason})
    return result


def _dedupe_texts(items: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = clean_text(item)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def detect_pec_legal_context(text: str) -> dict[str, Any]:
    """Riconosce contesti processuali che richiedono presidio dell'avvocato."""

    raw = clean_text(text)
    lower = raw.lower()
    matches: list[dict[str, Any]] = []
    for rule in LEGAL_CONTEXT_RULES:
        features = _rule_matches(rule, lower)
        if len(features) < int(rule.get("min_features") or 1):
            continue
        confidence = float(rule.get("base_confidence") or 0.55) + min(0.18, len(set(features)) * 0.035)
        matches.append(
            {
                "id": rule["id"],
                "label": rule["label"],
                "event_hint": rule["event_hint"],
                "office_hint": rule.get("office_hint") or "",
                "confidence": round(min(confidence, 0.98), 3),
                "features": features,
                "normative_references": [
                    {"label": label, "reason": reason}
                    for label, reason in list(rule.get("norms") or ())
                ],
                "agent_questions": list(rule.get("questions") or ()),
            }
        )
    if not matches:
        return {}
    matches.sort(key=lambda item: float(item.get("confidence") or 0.0), reverse=True)
    primary = matches[0]
    normative_refs = _dedupe_dicts(ref for match in matches for ref in list(match.get("normative_references") or []))
    questions = _dedupe_texts(
        [
            "Quale atto risulta notificato, depositato o comunicato negli allegati?",
            "Quale ufficio, numero RG/protocollo, parti e destinatari emergono da testo e allegati?",
            "Quale data di consegna/perfezionamento risulta dai dati di certificazione PEC?",
            "La comunicazione apre termini per opposizione, comparizione, impugnazione o adempimenti?",
            "Esiste un fascicolo gia' aperto o va proposto un nuovo collegamento?",
            *(question for match in matches for question in list(match.get("agent_questions") or [])),
        ]
    )
    recommended_actions = [
        "Segnalare subito il contesto telematico/processuale riconosciuto.",
        "Aprire atto e ricevute prima di assumere una scadenza.",
        "Verificare provenienza, pubblico elenco o ufficio mittente quando rilevante.",
        "Proporre collegamento al fascicolo tramite RG, parti, ufficio e parole chiave.",
        "Registrare automaticamente il presidio operativo e preparare eventuale richiesta di integrazione da validare prima dell'invio.",
    ]
    all_features = _dedupe_texts(feature for match in matches for feature in list(match.get("features") or []))
    return {
        "event_hint": primary["event_hint"],
        "office_hint": primary.get("office_hint") or "",
        "label": primary.get("label") or "",
        "confidence": primary["confidence"],
        "features": all_features,
        "matched_contexts": matches[:6],
        "normative_references": normative_refs,
        "agent_questions": questions,
        "recommended_actions": recommended_actions,
        "agent_policy": {
            "stance": "presidio_non_bloccante",
            "must_do": [
                "distinguere dato certo da MIME/ricevute, dato estratto con confidence e inferenza normativa",
                "segnalare il possibile termine senza calcolarlo come definitivo se mancano atto, data o base giuridica certa",
                "registrare automaticamente presidi e scadenze operative; non inviare, depositare o assumere termini legali conclusivi senza validazione dell'avvocato",
                "citare il contesto normativo come riferimento operativo, non come parere conclusivo",
            ],
        },
    }


def classify_attachment(item: AttachmentPayload, message_context: str = "") -> tuple[str, float, str]:
    name = item.filename.lower()
    mime = item.content_type.lower()
    name_context = f"{name} {mime}"
    context = f"{name} {mime} {message_context[:3000].lower()}"
    if any(needle in name_context for needle in ("daticert.xml", "postacert.eml", "postacert.xml")):
        return "daticert", 0.96, "nome tecnico PEC riconosciuto"
    if ".eml" in name_context or "message/rfc822" in name_context:
        return "eml", 0.95, "messaggio EML allegato o annidato"
    if any(needle in name_context for needle in ("procura", "mandato")):
        return "procura", 0.91, "nome riconducibile a procura"
    if any(needle in name_context for needle in ("atto", "ricorso", "citazione", "memoria", "comparsa", "istanza", "decreto")):
        return "atto", 0.86, "nome riconducibile ad atto processuale"
    if any(needle in name_context for needle in ("ricevuta", "accettazione", "consegna", "esito", "rdac", "rac")):
        return "ricevute", 0.88, "nome riconducibile a ricevuta PEC/PCT"
    rules: list[tuple[str, float, tuple[str, ...], str]] = [
        ("daticert", 0.96, ("daticert.xml", "postacert.eml", "postacert.xml"), "nome tecnico PEC riconosciuto"),
        ("eml", 0.95, (".eml", "message/rfc822"), "messaggio EML allegato o annidato"),
        ("procura", 0.91, ("procura", "mandato alle liti"), "nome o testo riconducibile a procura"),
        ("ricevute", 0.88, ("ricevuta", "accettazione", "consegna", "esito", "rdac", "rac"), "ricevuta PEC/PCT riconosciuta"),
        ("atto", 0.84, ("atto", "ricorso", "citazione", "memoria", "comparsa", "istanza", "decreto"), "atto processuale riconosciuto"),
        ("istruttorio", 0.78, ("documento", "doc.", "allegato", "prova", "verbale", "relazione", "ctu"), "allegato istruttorio probabile"),
        ("tecnico", 0.76, (".xml", ".xsd", "segnatura", "busta", "indicebusta"), "file tecnico del deposito"),
    ]
    for label, score, needles, reason in rules:
        if any(needle in context for needle in needles):
            return label, score, reason
    if (mime.startswith("application/pdf") or name.endswith((".pdf", ".pdf.p7m"))) and any(
        needle in context for needle in ("giudice di pace", "notificazione", "d.l. 179/2012")
    ):
        return "atto", 0.72, "PDF probabile di notifica giudiziaria"
    if item.data and len(item.data) < 512:
        return "da confermare", 0.46, "file troppo piccolo per classificazione affidabile"
    if mime.startswith("application/pdf") or name.endswith(".pdf"):
        return "da confermare", 0.52, "PDF senza segnali sufficienti"
    return "altro", 0.62, "classificazione residuale per formato non specifico"


_ZIP_ATTACHMENT_TYPES = {"application/zip", "application/x-zip-compressed"}


def _is_zip_attachment(filename: str, content_type: str = "") -> bool:
    return str(filename or "").lower().endswith(".zip") or str(content_type or "").lower() in _ZIP_ATTACHMENT_TYPES


def _looks_like_raw_zip_text(text: str) -> bool:
    sample = str(text or "").lstrip("\ufeff \t\r\n")
    if not sample.startswith("PK"):
        return False
    head = sample[:1200]
    return len(sample) > 200 or any(marker in head for marker in ("\x00", "\x03", "\x04", "\x14", ".pdf", "[Content_Types]"))


def _is_stale_zip_ocr_text(filename: str, content_type: str, ocr_text: str) -> bool:
    return _is_zip_attachment(filename, content_type) and _looks_like_raw_zip_text(ocr_text)


def extract_text_with_coverage(item: AttachmentPayload) -> tuple[str, float]:
    name = item.filename
    lower = name.lower()
    text = ""
    allow_binary_fallback = True
    is_zip = _is_zip_attachment(name, item.content_type)
    if item.content_type.startswith("text/") or lower.endswith((".txt", ".xml", ".csv")):
        text = item.data.decode("utf-8", errors="replace")
    elif lower.endswith(".eml") or item.content_type == "message/rfc822":
        try:
            nested = message_from_bytes(item.data)
            plain, html, _attachments = extract_message_parts(nested)
            text = plain or clean_text(re.sub(r"<[^>]+>", " ", html))
        except Exception:
            text = item.data.decode("utf-8", errors="replace")
    elif lower.endswith((".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
        try:
            from pct.ocr import estrai_testo

            text = estrai_testo(item.data, name)
        except Exception:
            text = ""
    elif is_zip:
        allow_binary_fallback = False
        parts: list[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(item.data)) as archive:
                for entry in archive.infolist()[:30]:
                    entry_name = entry.filename
                    entry_lower = entry_name.lower()
                    if entry.is_dir() or entry.file_size > 12_000_000:
                        continue
                    if not entry_lower.endswith((".pdf", ".txt", ".xml", ".csv", ".eml")):
                        continue
                    payload = archive.read(entry)
                    entry_text = ""
                    if entry_lower.endswith((".txt", ".xml", ".csv")):
                        entry_text = payload.decode("utf-8", errors="replace")
                    elif entry_lower.endswith(".eml"):
                        try:
                            nested = message_from_bytes(payload)
                            plain, html, _attachments = extract_message_parts(nested)
                            entry_text = plain or clean_text(re.sub(r"<[^>]+>", " ", html))
                        except Exception:
                            entry_text = payload.decode("utf-8", errors="replace")
                    elif entry_lower.endswith(".pdf"):
                        try:
                            from pct.ocr import estrai_testo

                            entry_text = estrai_testo(payload, entry_name)
                        except Exception:
                            entry_text = ""
                    if entry_text:
                        parts.append(f"[{entry_name}]\n{entry_text}")
        except Exception:
            parts = []
        text = "\n\n".join(parts)
    if not text and allow_binary_fallback:
        decoded = item.data.decode("utf-8", errors="ignore")
        printable = sum(1 for char in decoded if char.isprintable() or char.isspace())
        if decoded and printable / max(len(decoded), 1) > 0.65:
            text = decoded
    cleaned = clean_text(text, 20000)
    if not item.data:
        return cleaned, 0.0
    if not cleaned:
        return "", 0.0
    ratio = min(1.0, len(cleaned.encode("utf-8", errors="ignore")) / max(len(item.data), 1))
    if item.content_type.startswith("text/") or lower.endswith((".txt", ".xml", ".eml")):
        ratio = max(ratio, 0.9)
    return cleaned, round(ratio, 3)


def verify_signature(item: AttachmentPayload) -> tuple[str, dict[str, Any]]:
    name = item.filename.lower()
    details: dict[str, Any] = {"filename": item.filename, "content_type": item.content_type, "checks": []}
    if b"IUSENTRA_INVALID_SIGNATURE" in item.data or "firma_invalida" in name or "invalid" in name:
        details["checks"].append({"name": "contenuto", "status": "invalid", "detail": "marcatore di firma non valida nel dataset di controllo"})
        return "non_valida", details
    if not (name.endswith((".p7m", ".pdf")) or item.data.startswith(b"%PDF")):
        return "non_applicabile", details
    try:
        from pct.firma import analizza_firma_documento, busta_cades_valida

        signatures = analizza_firma_documento(item.data, item.filename)
        details["signatures"] = signatures
        if name.endswith(".p7m"):
            valid_cades = busta_cades_valida(item.data)
            details["checks"].append({"name": "CAdES", "status": "valid" if valid_cades else "invalid"})
            return ("valida" if valid_cades else "non_valida"), details
        if signatures:
            expired = any(bool(sig.get("scaduto")) for sig in signatures if isinstance(sig, dict))
            return ("scaduta" if expired else "valida"), details
        details["checks"].append({"name": "PAdES", "status": "missing", "detail": "nessuna firma PDF rilevata"})
        return "assente", details
    except Exception as exc:
        details["checks"].append({"name": "verifica", "status": "error", "detail": str(exc)})
        return "errore", details


def parse_pec_message(raw_mime: bytes) -> dict[str, Any]:
    msg = message_from_bytes(raw_mime)
    text_body, html_body, attachments = extract_message_parts(msg)
    xml_texts = extract_xml_texts(attachments)
    xml_joined = "\n".join(xml_texts.values())
    subject = decode_header_value(msg.get("Subject", ""))
    message_id = str(msg.get("Message-ID", "") or "").strip()
    from_addresses = extract_addresses(msg.get("From", ""))
    to_addresses = extract_addresses(msg.get("To", ""))
    cc_addresses = extract_addresses(msg.get("Cc", ""))
    sender = from_addresses[0]["email"] if from_addresses else ""
    sender_name = from_addresses[0]["name"] if from_addresses else ""
    body_all = "\n".join([subject, text_body, clean_text(re.sub(r"<[^>]+>", " ", html_body)), xml_joined])
    procedural_dates = extract_procedural_dates(xml_texts, plain_text=body_all)
    receipt_xml_type = xml_tag_value(xml_joined, ("tipo", "tipoRicevuta", "ricevuta"))
    receipt_text_type, receipt_features = receipt_type_from_text(body_all)
    receipt_type = clean_text(receipt_xml_type).lower().replace(" ", "_") or receipt_text_type
    rg_values = extract_rg_candidates(body_all)
    delivery_date = (
        parsedate_iso(xml_tag_value(xml_joined, ("data", "dataOraConsegna", "dataConsegna")))
        or parsedate_iso(xml_tag_value(xml_joined, ("giorno",)))
    )
    sent_date = parsedate_iso(msg.get("Date", ""))
    certified_features = []
    lower_all = body_all.lower()
    if "postacert" in lower_all or any("daticert" in name.lower() for name in xml_texts):
        certified_features.append("metadati postacert/daticert")
    if receipt_type:
        certified_features.append("tipo ricevuta PEC rilevato")
    if "pec" in sender or "postacert" in sender:
        certified_features.append("mittente PEC o postacert")
    protocol_features = []
    if rg_values:
        protocol_features.append("riferimento RG nel testo o nell'oggetto")
    if re.search(r"\bprot(?:ocollo)?\.?\s*[:\-]?\s*[\w./-]+", body_all, re.I):
        protocol_features.append("riferimento protocollo testuale")
    protocol = rg_values[0] if rg_values else ""
    if not protocol:
        match = re.search(r"\bprot(?:ocollo)?\.?\s*[:\-]?\s*([\w./-]+)", body_all, re.I)
        if match:
            protocol = match.group(1)
    legal_context = detect_pec_legal_context(body_all)
    legal_workflow = classifica_pec_legale(
        subject=subject,
        body=body_all,
        sender=sender,
        recipients=[item.get("email", "") for item in [*to_addresses, *cc_addresses] if isinstance(item, dict)],
        attachments=[
            {
                "filename": item.filename,
                "content_type": item.content_type,
                "size_bytes": len(item.data),
                "sha256": sha256_bytes(item.data),
            }
            for item in attachments
        ],
        message_id=message_id,
    )
    procedural_profile = build_pec_procedural_profile(
        subject=subject,
        body_text=body_all,
        xml_texts=xml_texts,
        rg_candidates=rg_values,
        sent_date=sent_date,
        delivery_date=delivery_date,
        event_type=str(legal_context.get("event_hint") or legal_workflow.get("event_type") or ""),
        semantic_context=legal_context,
    )
    office_value = procedural_profile.get("ufficio") or ""
    judge_value = procedural_profile.get("giudice") or ""
    event_value = procedural_profile.get("tipo_evento") or procedural_profile.get("oggetto_evento") or ""
    notice_time_value = procedural_profile.get("notificato_il") or delivery_date or sent_date
    hearing_time_value = procedural_profile.get("udienza_data_ora") or ""
    hearing_mode_value = procedural_profile.get("modalita_udienza") or ""
    fields = {
        "mittente": field_result(
            {"name": sender_name, "email": sender},
            0.94 if sender else 0.22,
            "Header From decodificato" if sender else "Mittente non presente negli header",
            ["header:From"] if sender else [],
        ),
        "data_invio": field_result(
            sent_date,
            0.9 if sent_date else 0.18,
            "Header Date normalizzato" if sent_date else "Data invio non leggibile",
            ["header:Date"] if sent_date else [],
        ),
        "data_consegna": field_result(
            delivery_date,
            0.92 if delivery_date and xml_joined else 0.58 if delivery_date else 0.2,
            "Data da metadati PEC" if delivery_date and xml_joined else "Data consegna non presente nei metadati",
            ["daticert.xml"] if delivery_date and xml_joined else [],
        ),
        "tipo_ricevuta": field_result(
            receipt_type,
            0.93 if receipt_xml_type else 0.78 if receipt_type else 0.24,
            "Tipo ricevuta da XML PEC" if receipt_xml_type else "Tipo ricevuta da oggetto/testo" if receipt_type else "Tipo ricevuta non riconosciuto",
            ["xml:tipo"] if receipt_xml_type else receipt_features,
        ),
        "protocollo": field_result(
            protocol,
            0.86 if rg_values else 0.64 if protocol else 0.2,
            "Riferimento RG riconosciuto" if rg_values else "Protocollo testuale riconosciuto" if protocol else "Nessun riferimento processuale forte",
            protocol_features,
        ),
        "pec_certificata": field_result(
            bool(certified_features),
            0.95 if len(certified_features) >= 2 else 0.7 if certified_features else 0.25,
            "Indicatori PEC certificata presenti" if certified_features else "Indicatori PEC certificata non sufficienti",
            certified_features,
        ),
        "contesto_legale": field_result(
            legal_context,
            float(legal_context.get("confidence") or 0.0) if legal_context else 0.18,
            "Contesto processuale rilevato nel testo PEC" if legal_context else "Nessun contesto processuale forte rilevato",
            legal_context.get("features") or [] if legal_context else [],
        ),
        "ufficio_giudiziario": field_result(
            office_value,
            0.86 if office_value else 0.2,
            "Ufficio/cancelleria estratto da testo o XML della comunicazione" if office_value else "Ufficio non riconosciuto nei dati disponibili",
            ["profilo_processuale", "eml/xml"] if office_value else [],
        ),
        "giudice": field_result(
            judge_value,
            0.86 if judge_value else 0.2,
            "Giudice estratto dalla comunicazione di cancelleria" if judge_value else "Giudice non indicato o non riconosciuto",
            ["profilo_processuale", "comunicazione.xml"] if judge_value else [],
        ),
        "evento_processuale": field_result(
            event_value,
            0.84 if event_value else 0.2,
            "Evento processuale estratto dal messaggio o dalla Comunicazione.xml" if event_value else "Evento processuale non riconosciuto",
            ["profilo_processuale", "xml:Oggetto/Tipo Evento"] if event_value else [],
        ),
        "orario_notifica": field_result(
            notice_time_value,
            0.86 if notice_time_value else 0.2,
            "Orario da presidiare letto da notifica/certificazione PEC" if notice_time_value else "Orario non riconosciuto",
            ["profilo_processuale", "daticert/header"] if notice_time_value else [],
        ),
        "orario_udienza": field_result(
            hearing_time_value,
            0.9 if hearing_time_value else 0.2,
            "Data e ora udienza estratte dalla comunicazione di cancelleria" if hearing_time_value else "Data e ora udienza non riconosciute",
            ["profilo_processuale", "comunicazione.xml"] if hearing_time_value else [],
        ),
        "modalita_udienza": field_result(
            hearing_mode_value,
            0.9 if hearing_mode_value else 0.2,
            "Modalità dell'udienza riconosciuta dalla comunicazione" if hearing_mode_value else "Modalità udienza non riconosciuta",
            ["profilo_processuale", "comunicazione.xml"] if hearing_mode_value else [],
        ),
    }
    return {
        "schema": "iusentra.pec.parsed.v2",
        "parser_version": SCHEMA_VERSION,
        "headers": {
            "message_id": message_id,
            "subject": subject,
            "from": from_addresses,
            "to": to_addresses,
            "cc": cc_addresses,
            "date": sent_date,
        },
        "fields": fields,
        "semantic_context": legal_context,
        "legal_workflow": legal_workflow,
        "procedural_profile": procedural_profile,
        "rg_candidates": rg_values,
        "body": {
            "text": clean_text(text_body, 20000),
            "html_text": clean_text(re.sub(r"<[^>]+>", " ", html_body), 20000),
        },
        "xml_documents": [{"filename": name, "sha256": sha256_bytes(text.encode("utf-8", errors="replace"))} for name, text in xml_texts.items()],
        "procedural_dates": procedural_dates,
        "attachments": [
            {
                "index": item.index,
                "filename": item.filename,
                "content_type": item.content_type,
                "size_bytes": len(item.data),
                "sha256": sha256_bytes(item.data),
                "nested_message_id": item.nested_message_id,
            }
            for item in attachments
        ],
        "extracted_at": iso_now(),
    }


def event_type_from_parsed(parsed: dict[str, Any], classes: Iterable[str]) -> str:
    subject = str((parsed.get("headers") or {}).get("subject") or "")
    body = str(((parsed.get("body") or {}).get("text") or ""))
    receipt = str((((parsed.get("fields") or {}).get("tipo_ricevuta") or {}).get("value") or ""))
    text = f"{subject} {body} {receipt}".lower()
    class_set = set(classes)
    semantic_context = parsed.get("semantic_context") if isinstance(parsed.get("semantic_context"), dict) else {}
    event_hint = str(semantic_context.get("event_hint") or "")
    if event_hint in {
        "pct_deposito",
        "comunicazione_cancelleria",
        "notifica_l53",
        "notifica_giudice_pace",
        "notifica_telematica",
        "notifica_unep",
        "pat_notifica_o_deposito",
        "ptt_notifica_o_deposito",
        "penale_snt",
        "penale_deposito_portale",
        "ricevuta_pec",
        "domicilio_digitale",
    }:
        return event_hint
    legal_workflow = parsed.get("legal_workflow") if isinstance(parsed.get("legal_workflow"), dict) else {}
    legal_event = str(legal_workflow.get("event_type") or "")
    if legal_event and legal_event != "pec_non_riconosciuta":
        return legal_event
    if "deposito" in text or {"atto", "procura"} & class_set:
        return "deposito"
    if "notifica" in text:
        return "notifica"
    if "cancelleria" in text or "comunicazione" in text:
        return "comunicazione"
    if receipt:
        return "ricevuta"
    return "messaggio"


PCT_DEPOSIT_EXPECTED_SEQUENCE: tuple[dict[str, Any], ...] = (
    {
        "id": "accettazione_pec",
        "order": 1,
        "label": "Accettazione PEC",
        "expected": "Ricevuta di accettazione del messaggio inviato dal professionista.",
        "checks": (
            "Message-ID e hash MIME presenti",
            "data e ora di accettazione leggibili",
            "nessuna anomalia di invio o indirizzo destinatario",
        ),
    },
    {
        "id": "consegna_pec",
        "order": 2,
        "label": "Consegna PEC",
        "expected": "Ricevuta di avvenuta consegna al dominio giustizia; la data/ora va presidiata per i termini.",
        "checks": (
            "daticert.xml o ricevuta completa presenti",
            "destinatario ufficio coerente",
            "RG/ufficio/parti ricavabili o da collegare al fascicolo",
        ),
    },
    {
        "id": "esito_controlli_deposito",
        "order": 3,
        "label": "Esito controlli deposito",
        "expected": "PEC con esito dei controlli automatici formali su messaggio e busta telematica.",
        "checks": (
            "assenza di errore fatale o rifiuto tecnico",
            "eventuali warning da leggere e comunicare",
            "atto, DatiAtto.xml, firma e allegati coerenti",
        ),
    },
    {
        "id": "accettazione_o_rifiuto_deposito",
        "order": 4,
        "label": "Accettazione o rifiuto deposito",
        "expected": "PEC finale di accettazione deposito, automatica/manuale, oppure rifiuto/intervento cancelleria.",
        "checks": (
            "accettazione deposito confermata o rifiuto esplicito",
            "data di accettazione e fascicolo corretti",
            "in caso di rifiuto preparare comunicazione e nuova attività",
        ),
    },
)


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


def detect_pct_deposit_stage(parsed: dict[str, Any]) -> dict[str, Any]:
    subject = str((parsed.get("headers") or {}).get("subject") or "")
    body = str(((parsed.get("body") or {}).get("text") or ""))
    receipt = str((((parsed.get("fields") or {}).get("tipo_ricevuta") or {}).get("value") or ""))
    text = f"{subject} {body} {receipt}".lower()
    if _contains_any(text, ("rifiuto deposito", "deposito rifiutato", "rifiutato dalla cancelleria", "rifiuto dell'atto")):
        return {
            "id": "rifiuto_deposito",
            "order": 4,
            "label": "Rifiuto deposito",
            "status": "danger",
            "confidence": 0.9,
            "reason": "il testo richiama rifiuto del deposito o rifiuto della cancelleria",
        }
    if _contains_any(text, ("accettazione deposito", "deposito accettato", "accettato dalla cancelleria")):
        return {
            "id": "accettazione_deposito",
            "order": 4,
            "label": "Accettazione deposito",
            "status": "ok",
            "confidence": 0.9,
            "reason": "il testo richiama accettazione del deposito",
        }
    if _contains_any(text, ("esito intervento cancelleria", "intervento cancelleria", "intervento manuale")):
        return {
            "id": "intervento_cancelleria",
            "order": 4,
            "label": "Esito intervento cancelleria",
            "status": "warning",
            "confidence": 0.82,
            "reason": "il testo richiama intervento della cancelleria",
        }
    if _contains_any(text, ("esito controlli automatici", "esito controlli deposito", "controlli automatici")):
        status = "warning" if _contains_any(text, ("warning", "anomalia", "errore")) else "ok"
        if _contains_any(text, ("errore fatale", "fatal", "atto non conforme", "rifiuto tecnico")):
            status = "danger"
        return {
            "id": "esito_controlli_deposito",
            "order": 3,
            "label": "Esito controlli deposito",
            "status": status,
            "confidence": 0.88,
            "reason": "il testo richiama l'esito dei controlli automatici del deposito",
        }
    if _contains_any(text, ("avvenuta consegna", "ricevuta di consegna", "consegna pec", "rdac")):
        return {
            "id": "consegna_pec",
            "order": 2,
            "label": "Consegna PEC",
            "status": "ok",
            "confidence": 0.86,
            "reason": "il testo richiama avvenuta consegna PEC",
        }
    if _contains_any(text, ("ricevuta di accettazione", "accettazione pec", "accettazione del messaggio")):
        return {
            "id": "accettazione_pec",
            "order": 1,
            "label": "Accettazione PEC",
            "status": "ok",
            "confidence": 0.84,
            "reason": "il testo richiama accettazione PEC",
        }
    return {
        "id": "deposito_da_ricondurre",
        "order": 0,
        "label": "Deposito da ricondurre",
        "status": "warning",
        "confidence": 0.45,
        "reason": "il testo indica un deposito, ma la fase della sequenza non è certa",
    }


def build_pct_deposit_lifecycle(parsed: dict[str, Any], attachments: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    subject = str((parsed.get("headers") or {}).get("subject") or "")
    body = str(((parsed.get("body") or {}).get("text") or ""))
    text = f"{subject} {body}".lower()
    if event_type not in {"deposito", "pct_deposito"} and "deposito" not in text:
        return {}
    stage = detect_pct_deposit_stage(parsed)
    attachment_classes = {str(item.get("classification") or "") for item in attachments}
    stage_status = str(stage.get("status") or "warning")
    expected_next = [
        item
        for item in PCT_DEPOSIT_EXPECTED_SEQUENCE
        if int(item["order"]) > int(stage.get("order") or 0)
    ][:2]
    checks = [
        "Verificare che siano arrivate almeno accettazione PEC, consegna PEC, esito controlli deposito e accettazione/rifiuto deposito.",
        "Non comunicare il deposito come definitivamente accettato finché manca la PEC finale di accettazione deposito o esito cancelleria.",
        "Se l'esito controlli contiene errore fatale, rifiuto o atto non conforme, aprire subito anomalia e preparare comunicazione all'avvocato.",
        "Se manca la consegna PEC, presidiare termini e prova di deposito prima di assumere la data come certa.",
    ]
    if "daticert" not in attachment_classes and "ricevute" not in attachment_classes:
        checks.append("Recuperare o verificare i dati di certificazione PEC collegati al deposito.")
    if "procura" not in attachment_classes:
        checks.append("Verificare se la procura era dovuta per questo deposito e se risulta nella busta o nel fascicolo.")
    if stage_status == "ok" and stage.get("id") == "accettazione_deposito":
        communication = "Deposito verosimilmente accettato: comunicare l'esito solo dopo controllo di fascicolo, RG, atto e allegati."
    elif stage_status == "danger":
        communication = "Deposito con rifiuto o errore critico: segnalare subito e preparare attività correttiva."
    else:
        communication = "Deposito da presidiare: comunicare lo stato intermedio e indicare quali PEC/esiti mancano ancora."
    return {
        "kind": "pct_deposit_lifecycle",
        "current_stage": stage,
        "expected_sequence": [dict(item) for item in PCT_DEPOSIT_EXPECTED_SEQUENCE],
        "expected_next": [dict(item) for item in expected_next],
        "checks": checks,
        "communication": communication,
        "official_reference": {
            "label": "PST Giustizia - deposito telematico di un atto",
            "url": "https://servizipst.giustizia.it/PST/it/pst_1_0.wp?contentId=SPR376&previousPage=pst_1_2",
        },
    }


def _field_date_value(parsed: dict[str, Any], *keys: str) -> str:
    fields = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else {}
    for key in keys:
        payload = fields.get(key) if isinstance(fields.get(key), dict) else {}
        value = parsedate_iso(payload.get("value"))
        if value:
            return value
    headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    return parsedate_iso(headers.get("date"))


def _date_only(value: str) -> date | None:
    parsed = parsedate_iso(value)
    if not parsed:
        return None
    try:
        return datetime.fromisoformat(parsed.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _operational_due_date(source_date: date | None, *, lead_days: int) -> str:
    base = source_date or datetime.now(ROME_TZ).date()
    candidate = base + timedelta(days=max(0, lead_days))
    return candidate.isoformat()


def _procedural_date_kind(candidate: dict[str, Any]) -> str:
    label = clean_text(candidate.get("label"), 120).lower()
    context = clean_text(candidate.get("context"), 420).lower()
    haystack = f"{label} {context}"
    if any(
        needle in haystack
        for needle in (
            "udienza",
            "fissazione udienza",
            "fissata udienza",
            "udienza fissata",
            "differimento udienza",
            "rinvio udienza",
            "udienza rinviata",
            "pubblica udienza",
            "camera di consiglio",
            "discussione",
            "comparizione",
            "strumenti audiovisivi",
            "videoconferenza",
            "aula virtuale",
        )
    ):
        return "udienza"
    if any(needle in label for needle in ("termine", "scadenza", "costituzione", "deposito")) and any(
        needle in context for needle in ("entro", "termine", "scadenza", "depositare", "costituir")
    ):
        return "termine"
    return ""


def _date_label_it(value: str) -> str:
    try:
        parsed = date.fromisoformat(str(value or ""))
    except ValueError:
        return clean_text(value, 20)
    return parsed.strftime("%d/%m/%Y")


def _extract_inline_field(text: str, label: str, *, limit: int = 160) -> str:
    match = re.search(
        rf"\b{re.escape(label)}\s*:\s*(.+?)(?=\s+(?:Data\s+Evento|Tipo\s+Evento|Oggetto|Descrizione|Note|Registrato\s+da|Notificato\s+alla\s+PEC)\s*:|\s+--|$)",
        text or "",
        flags=re.I | re.S,
    )
    return clean_text(match.group(1), limit).strip(" .;:-") if match else ""


def _normalise_event_phrase(value: str) -> str:
    text = clean_text(value, 120).strip(" .;:-")
    text = re.sub(r"\bCPC\b", "c.p.c.", text, flags=re.I)
    text = re.sub(r"\bART\.?\s*", "art. ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    return text[:1].upper() + text[1:].lower()


def _hearing_event_summary(parsed: dict[str, Any], candidate: dict[str, Any]) -> str:
    profile = parsed.get("procedural_profile") if isinstance(parsed.get("procedural_profile"), dict) else {}
    context = clean_text(candidate.get("context") or "", 520)
    object_value = (
        _extract_inline_field(context, "Oggetto", limit=180)
        or clean_text(profile.get("oggetto_evento") or "", 180)
        or clean_text(candidate.get("label") or "", 80)
    )
    description_value = _extract_inline_field(context, "Descrizione", limit=220) or clean_text(profile.get("descrizione_evento") or "", 220)
    event_type = _extract_inline_field(context, "Tipo Evento", limit=120) or clean_text(profile.get("tipo_evento") or "", 120)
    haystack = f"{event_type} {object_value} {description_value} {context}".lower()
    object_norm = _normalise_event_phrase(object_value)
    description_norm = _normalise_event_phrase(description_value)
    if "mancata comparizione" in haystack and "309" in haystack:
        return "Rinvio udienza - mancata comparizione parti ex art. 309 c.p.c."
    if "differimento udienza" in haystack:
        return "Differimento udienza"
    if "rinvio" in haystack or "rinviata" in haystack or "rinviato" in haystack:
        if object_norm and "rinvio" in object_norm.lower():
            return f"Rinvio udienza - {object_norm}"
        return "Rinvio udienza"
    if "fissazione udienza" in haystack or "fissata udienza" in haystack:
        if "discussione" in haystack:
            return "Fissazione udienza di discussione"
        return "Fissazione udienza"
    if "discussione" in haystack:
        return "Udienza di discussione"
    if object_norm and object_norm.lower() not in {"udienza", "data processuale"}:
        return object_norm
    if description_norm:
        return description_norm
    return "Udienza"


def _deadline_title_for_procedural_date(parsed: dict[str, Any], candidate: dict[str, Any], *, kind: str, subject: str) -> str:
    profile = parsed.get("procedural_profile") if isinstance(parsed.get("procedural_profile"), dict) else {}
    rg = clean_text(profile.get("numero_rg") or "", 40)
    office = clean_text(profile.get("ufficio") or "", 70)
    date_label = _date_label_it(str(candidate.get("date") or ""))
    if kind == "udienza":
        event = _hearing_event_summary(parsed, candidate)
        details = [event, date_label]
        if rg:
            details.append(f"RG {rg}")
        elif office:
            details.append(office)
        return clean_text(" - ".join(part for part in details if part), 150)
    event = clean_text(profile.get("oggetto_evento") or candidate.get("label") or "", 80)
    prefix = "Termine da PEC"
    details = []
    if rg:
        details.append(f"RG {rg}")
    if event and event.lower() not in subject.lower():
        details.append(event)
    if office and not rg:
        details.append(office)
    middle = f" - {' - '.join(details)}" if details else ""
    return clean_text(f"{prefix}{middle}: {subject}", 150)


def _deadline_description_for_procedural_date(candidate: dict[str, Any], *, kind: str, source: str) -> str:
    context = clean_text(candidate.get("context") or "", 420)
    if kind == "udienza":
        object_value = _extract_inline_field(context, "Oggetto", limit=180)
        description_value = _extract_inline_field(context, "Descrizione", limit=220)
        event_date = _extract_inline_field(context, "Data Evento", limit=80)
        parts = []
        if object_value:
            parts.append(f"Evento: {_normalise_event_phrase(object_value)}")
        if description_value:
            parts.append(f"Dettaglio: {_normalise_event_phrase(description_value)}")
        if event_date:
            parts.append(f"Data evento cancelleria: {event_date}")
        parts.append(f"Fonte: {source}")
        return clean_text(". ".join(parts), 280)
    return clean_text(f"Data processuale futura letta da {source}: {context}", 280)


def _deadline_responsible_actor(actor: str) -> str:
    value = clean_text(actor, 80)
    technical = value.lower()
    if not value or technical in {
        "pec-api",
        "pec-worker",
        "pec-linker",
        "pec-demo",
        "pec-maintenance",
        "pytest",
        "codex-test",
    }:
        return ""
    if technical.startswith(("codex", "pec-")):
        return ""
    return value


def _deadline_updates_for_existing(existing: Any, proposal: dict[str, Any], *, title: str, actor: str = "") -> dict[str, Any]:
    updates: dict[str, Any] = {}
    current_title = clean_text(getattr(existing, "titolo", "") or "", 160)
    if title and current_title != title and current_title.startswith(("Udienza da PEC", "Termine da PEC", "Valuta termini da notifica PEC", "Data processuale")):
        updates["titolo"] = title
    if clean_text(proposal.get("reason")):
        current_desc = clean_text(getattr(existing, "descrizione", "") or "", 260)
        desired_desc = clean_text(proposal.get("reason"), 260)
        if current_desc != desired_desc:
            updates["descrizione"] = desired_desc
    if str(proposal.get("deadline_kind") or "") == "udienza":
        tipo_value = getattr(getattr(existing, "tipo", ""), "value", getattr(existing, "tipo", ""))
        if str(tipo_value).upper() != "UDIENZA":
            updates["tipo"] = "UDIENZA"
    desired_actor = _deadline_responsible_actor(actor)
    current_actor = clean_text(getattr(existing, "id_utente_responsabile", "") or "", 80)
    if current_actor and not _deadline_responsible_actor(current_actor):
        updates["id_utente_responsabile"] = desired_actor
    if desired_actor and current_actor != desired_actor:
        updates["id_utente_responsabile"] = desired_actor
    if clean_text(proposal.get("source_event_type")) and clean_text(getattr(existing, "source_event_type", "") or "") != clean_text(proposal.get("source_event_type")):
        updates["source_event_type"] = clean_text(proposal.get("source_event_type"))
    if clean_text(proposal.get("source_event_at")) and clean_text(getattr(existing, "source_event_at", "") or "") != clean_text(proposal.get("source_event_at")):
        updates["source_event_at"] = clean_text(proposal.get("source_event_at"))
    return updates


def build_deadline_proposal(
    parsed: dict[str, Any],
    *,
    event_type: str,
    issues: list[dict[str, Any]],
    deposit_lifecycle: dict[str, Any],
) -> dict[str, Any]:
    """Produce una scadenza operativa automatica, distinta dal calcolo legale conclusivo."""

    issue_codes = {str(item.get("code") or "") for item in issues}
    source_date_iso = _field_date_value(parsed, "data_consegna", "data_invio")
    source_date = _date_only(source_date_iso)
    subject = clean_text(((parsed.get("headers") or {}).get("subject") or "PEC"), 90)
    procedural_dates = [item for item in list(parsed.get("procedural_dates") or []) if isinstance(item, dict)]
    today = datetime.now(ROME_TZ).date()
    future_dates: list[dict[str, Any]] = []
    for item in procedural_dates:
        try:
            item_day = date.fromisoformat(str(item.get("date") or ""))
        except ValueError:
            continue
        kind = _procedural_date_kind(item)
        if item_day >= today and kind:
            enriched = dict(item)
            enriched["deadline_kind"] = kind
            future_dates.append(enriched)
    if future_dates:
        candidate = sorted(
            future_dates,
            key=lambda item: (
                0 if str(item.get("deadline_kind") or "") == "udienza" else 1,
                str(item.get("date") or ""),
                -float(item.get("confidence") or 0.0),
            ),
        )[0]
        label = clean_text(candidate.get("label") or "Data processuale", 80)
        source = clean_text(candidate.get("source") or "allegato PEC", 160)
        deadline_kind = str(candidate.get("deadline_kind") or "")
        title = _deadline_title_for_procedural_date(parsed, candidate, kind=deadline_kind, subject=subject)
        description = _deadline_description_for_procedural_date(candidate, kind=deadline_kind, source=source)
        return {
            "status": "ready",
            "auto_create": True,
            "title": title,
            "due_date": str(candidate.get("date") or ""),
            "source_event_at": str(candidate.get("date") or source_date_iso),
            "source_event_type": event_type,
            "priority": "alta" if deadline_kind == "udienza" or "udienza" in label.lower() else "media",
            "legal_deadline": False,
            "deadline_kind": deadline_kind,
            "reason": description,
            "detected_procedural_date": candidate,
        }
    notice_events = {
        "notifica_giudice_pace",
        "notifica_telematica",
        "notifica_l53",
        "notifica_unep",
        "pat_notifica_o_deposito",
        "ptt_notifica_o_deposito",
        "penale_snt",
        "penale_deposito_portale",
    }
    critical = any(str(item.get("severity") or "") == "danger" for item in issues)
    if critical:
        return {
            "status": "ready",
            "auto_create": True,
            "title": f"Presidio urgente PEC: {subject}",
            "due_date": _operational_due_date(source_date, lead_days=0),
            "source_event_at": source_date_iso,
            "source_event_type": event_type,
            "priority": "alta",
            "legal_deadline": False,
            "reason": "Esito PEC critico: il software registra un presidio operativo immediato e segnala verifica dell'avvocato.",
        }
    if event_type == "pct_deposito" and "pct_deposit_followup_expected" in issue_codes:
        return {
            "status": "ready",
            "auto_create": True,
            "title": f"Verifica sequenza deposito PEC: {subject}",
            "due_date": _operational_due_date(source_date, lead_days=1),
            "source_event_at": source_date_iso,
            "source_event_type": event_type,
            "priority": "media",
            "legal_deadline": False,
            "reason": "Deposito telematico in fase intermedia: il software registra un presidio per attendere o cercare la PEC finale di accettazione/rifiuto.",
        }
    if event_type in {"comunicazione", "comunicazione_cancelleria"}:
        return {
            "status": "ready",
            "auto_create": True,
            "title": f"Verifica comunicazione di cancelleria PEC: {subject}",
            "due_date": _operational_due_date(source_date, lead_days=2),
            "source_event_at": source_date_iso,
            "source_event_type": event_type,
            "priority": "media",
            "legal_deadline": False,
            "reason": "Comunicazione di cancelleria rilevata: il software registra un presidio operativo non bloccante per leggere allegati, termini e prossima azione.",
        }
    if event_type in notice_events:
        return {
            "status": "review_required",
            "auto_create": False,
            "title": f"Valuta termini da notifica PEC: {subject}",
            "due_date": "",
            "source_event_at": source_date_iso,
            "source_event_type": event_type,
            "priority": "alta",
            "legal_deadline": False,
            "reason": "Notifica giudiziaria rilevata senza termine certo: il software registra l'evento PEC, ma non crea una scadenza finché non viene letto un termine o un'udienza concreta.",
        }
    if issues:
        return {
            "status": "ready",
            "auto_create": True,
            "title": f"Presidio anomalie PEC: {subject}",
            "due_date": _operational_due_date(source_date, lead_days=2),
            "source_event_at": source_date_iso,
            "source_event_type": event_type,
            "priority": "media",
            "legal_deadline": False,
            "reason": "Sono presenti anomalie non bloccanti: il software registra un promemoria operativo per chiuderle.",
        }
    return {
        "status": "not_needed",
        "auto_create": False,
        "title": "",
        "due_date": "",
        "source_event_at": source_date_iso,
        "source_event_type": event_type,
        "priority": "normale",
        "legal_deadline": False,
        "reason": "Nessuna scadenza operativa automatica richiesta dalla matrice PEC.",
    }


def build_validation_report(parsed: dict[str, Any], attachments: list[dict[str, Any]]) -> dict[str, Any]:
    classes = [str(item.get("classification") or "") for item in attachments]
    event_type = event_type_from_parsed(parsed, classes)
    present = {item for item in classes if item}
    required_by_event = {
        "deposito": ["atto", "procura", "ricevute"],
        "pct_deposito": ["atto", "procura", "ricevute"],
        "notifica": ["atto", "ricevute"],
        "notifica_telematica": ["atto", "ricevute"],
        "notifica_giudice_pace": ["atto", "ricevute"],
        "notifica_l53": ["atto", "ricevute"],
        "notifica_unep": ["atto", "ricevute"],
        "pat_notifica_o_deposito": ["atto", "ricevute"],
        "ptt_notifica_o_deposito": ["atto", "ricevute"],
        "penale_snt": ["atto", "ricevute"],
        "penale_deposito_portale": ["atto"],
        "domicilio_digitale": [],
        "ricevuta_pec": ["ricevute"],
        "ricevuta": ["ricevute"],
        "comunicazione": [],
        "comunicazione_cancelleria": [],
        "messaggio": [],
    }
    required = required_by_event.get(event_type, [])
    issues: list[dict[str, Any]] = []
    deposit_lifecycle = build_pct_deposit_lifecycle(parsed, attachments, event_type)
    for class_name in required:
        if class_name not in present and not (class_name == "ricevute" and "daticert" in present):
            issues.append(
                {
                    "code": f"missing_{class_name}",
                    "severity": "warning",
                    "blocking": False,
                    "title": f"Allegato {class_name} non confermato",
                    "detail": "Il controllo automatico segnala l'assenza o la bassa confidenza della classe richiesta.",
                }
            )
    if deposit_lifecycle:
        stage = deposit_lifecycle.get("current_stage") if isinstance(deposit_lifecycle.get("current_stage"), dict) else {}
        stage_status = str(stage.get("status") or "")
        if stage_status == "danger":
            issues.append(
                {
                    "code": "pct_deposit_critical_outcome",
                    "severity": "danger",
                    "blocking": False,
                    "title": "Deposito con esito critico",
                    "detail": deposit_lifecycle.get("communication") or "Rifiuto o errore critico da comunicare subito.",
                }
            )
        elif str(stage.get("id") or "") != "accettazione_deposito":
            next_labels = ", ".join(str(item.get("label") or "") for item in list(deposit_lifecycle.get("expected_next") or []))
            issues.append(
                {
                    "code": "pct_deposit_followup_expected",
                    "severity": "warning",
                    "blocking": False,
                    "title": "Deposito da presidiare",
                    "detail": f"Fase riconosciuta: {stage.get('label') or 'non certa'}. Attendere o cercare: {next_labels or 'PEC finale di accettazione/rifiuto deposito'}.",
                }
            )
    semantic_context = parsed.get("semantic_context") if isinstance(parsed.get("semantic_context"), dict) else {}
    legal_workflow = parsed.get("legal_workflow") if isinstance(parsed.get("legal_workflow"), dict) else {}
    if legal_workflow:
        action = str(legal_workflow.get("azione_proposta") or "")
        priority = str(legal_workflow.get("priority") or "media")
        if action:
            issues.append(
                {
                    "code": f"legal_workflow_{legal_workflow.get('event_type') or 'evento'}",
                    "severity": "danger" if priority == "rossa" else "warning" if priority == "alta" else "info",
                    "blocking": False,
                    "title": str(legal_workflow.get("event_label") or "Evento PEC"),
                    "detail": action,
                }
            )
        if legal_workflow.get("event_type") == "ricevuta_accettazione_pec":
            issues.append(
                {
                    "code": "pec_acceptance_does_not_close_deposit",
                    "severity": "warning",
                    "blocking": False,
                    "title": "Ricevuta PEC non conclusiva",
                    "detail": "La sola accettazione PEC non chiude il deposito se mancano consegna ed esito cancelleria.",
                }
            )
    notice_events = {
        "notifica_giudice_pace",
        "notifica_telematica",
        "notifica_l53",
        "notifica_unep",
        "pat_notifica_o_deposito",
        "ptt_notifica_o_deposito",
        "penale_snt",
        "penale_deposito_portale",
    }
    if event_type in notice_events:
        office = str(semantic_context.get("office_hint") or "ufficio giudiziario")
        issues.append(
            {
                "code": "legal_notice_review_required",
                "severity": "warning",
                "blocking": False,
                "title": "Possibile notifica giudiziaria",
                "detail": f"Il testo richiama {office} e richiede presidio su atto, ricevute, termini e fascicolo.",
            }
        )
        protocol_value = str((((parsed.get("fields") or {}).get("protocollo") or {}).get("value") or ""))
        if not protocol_value:
            issues.append(
                {
                    "code": "legal_notice_rg_missing",
                    "severity": "info",
                    "blocking": False,
                    "title": "RG o protocollo non riconosciuto",
                    "detail": "L'agente deve proporre candidati fascicolo ma lasciare il collegamento da confermare.",
                }
            )
    if event_type == "notifica_l53" and "ricevute" not in present and "daticert" not in present:
        issues.append(
            {
                "code": "l53_receipt_proof_missing",
                "severity": "warning",
                "blocking": False,
                "title": "Prova PEC della notifica da completare",
                "detail": "Per una notifica in proprio vanno verificate ricevute e allegati effettivamente notificati.",
            }
        )
    if event_type == "penale_snt":
        issues.append(
            {
                "code": "penal_recipient_scope_review",
                "severity": "info",
                "blocking": False,
                "title": "Destinatario penale da controllare",
                "detail": "Nel penale l'agente deve verificare ruolo del destinatario e atto notificato prima di proporre termini.",
            }
        )
        delivery_date = str((((parsed.get("fields") or {}).get("data_consegna") or {}).get("value") or ""))
        if not delivery_date:
            issues.append(
                {
                    "code": "legal_notice_delivery_date_missing",
                    "severity": "warning",
                    "blocking": False,
                    "title": "Data di consegna da verificare",
                    "detail": "Per eventuali termini serve controllare ricevuta e metadati PEC; il software registra solo un presidio operativo automatico.",
                }
            )
    for item in attachments:
        if item.get("classification") == "da confermare":
            issues.append(
                {
                    "code": "attachment_to_confirm",
                    "severity": "info",
                    "blocking": False,
                    "title": "Allegato da confermare",
                    "detail": f"{item.get('filename')}: classificazione sotto soglia.",
                }
            )
        if item.get("signature_status") in {"non_valida", "errore", "scaduta"}:
            issues.append(
                {
                    "code": "signature_attention",
                    "severity": "warning",
                    "blocking": False,
                    "title": "Firma da verificare",
                    "detail": f"{item.get('filename')}: esito {item.get('signature_status')}.",
                }
            )
    procedural_profile = parsed.get("procedural_profile") if isinstance(parsed.get("procedural_profile"), dict) else {}
    remote_hearing = build_remote_hearing_profile(parsed, attachments)
    if remote_hearing:
        procedural_profile = dict(procedural_profile)
        procedural_profile["remote_hearing"] = remote_hearing
        checklist = [str(item) for item in list(procedural_profile.get("checklist_avvocato") or []) if str(item or "").strip()]
        questions = [str(item) for item in list(procedural_profile.get("domande_lex") or []) if str(item or "").strip()]
        remote_checklist = [str(item) for item in list(remote_hearing.get("checklist") or []) if str(item or "").strip()]
        remote_questions = [str(item) for item in list(remote_hearing.get("questions") or []) if str(item or "").strip()]
        procedural_profile["checklist_avvocato"] = list(dict.fromkeys([*remote_checklist, *checklist]))
        procedural_profile["domande_lex"] = list(dict.fromkeys([*remote_questions, *questions]))
        if remote_hearing.get("detected") or remote_hearing.get("pdf_required"):
            sintesi = [str(item) for item in list(procedural_profile.get("sintesi_operativa") or []) if str(item or "").strip()]
            mode = str(remote_hearing.get("mode") or "da remoto")
            links = remote_hearing.get("links") if isinstance(remote_hearing.get("links"), list) else []
            times = remote_hearing.get("times") if isinstance(remote_hearing.get("times"), list) else []
            if links:
                first_link = links[0] if isinstance(links[0], dict) else {}
                sintesi.append(f"Udienza {mode}: link rilevato in {first_link.get('source') or 'allegato/testo PEC'}.")
            elif remote_hearing.get("pdf_required"):
                pending = ", ".join(str(item) for item in list(remote_hearing.get("pdf_pending") or remote_hearing.get("pdf_sources") or [])[:3])
                sintesi.append(f"Udienza {mode}: leggere il PDF per recuperare il link di collegamento{f' ({pending})' if pending else ''}.")
            if times:
                sintesi.append(f"Orario udienza/collegamento: {times[0]}.")
            procedural_profile["sintesi_operativa"] = list(dict.fromkeys(sintesi))
        if remote_hearing.get("pdf_required"):
            issues.append(
                {
                    "code": "remote_hearing_pdf_link_required",
                    "severity": "warning",
                    "blocking": False,
                    "title": "Link udienza da leggere nel PDF",
                    "detail": "La PEC richiama un'udienza da remoto/audiovisiva, ma il link non è ancora stato estratto: acquisire o leggere il PDF allegato prima di chiudere il presidio.",
                }
            )
        elif remote_hearing.get("links"):
            first = remote_hearing["links"][0] if isinstance(remote_hearing["links"][0], dict) else {}
            issues.append(
                {
                    "code": "remote_hearing_link_detected",
                    "severity": "info",
                    "blocking": False,
                    "title": "Udienza da remoto riconosciuta",
                    "detail": f"Link o istruzioni di collegamento rilevati in {first.get('source') or 'testo PEC/allegato'}: verificare e riportare in agenda.",
                }
            )
    severity = "ok"
    if any(item["severity"] == "warning" for item in issues):
        severity = "warning"
    if any(item["severity"] == "danger" for item in issues):
        severity = "danger"
    deadline_proposal = build_deadline_proposal(
        parsed,
        event_type=event_type,
        issues=issues,
        deposit_lifecycle=deposit_lifecycle,
    )
    if remote_hearing:
        deadline_proposal = dict(deadline_proposal)
        deadline_proposal["remote_hearing"] = remote_hearing
    lawyer_checklist = [str(item) for item in list(procedural_profile.get("checklist_avvocato") or []) if str(item or "").strip()]
    procedural_questions = [str(item) for item in list(procedural_profile.get("domande_lex") or []) if str(item or "").strip()]
    return {
        "event_type": event_type,
        "required": required,
        "present": sorted(present),
        "issues": issues,
        "deposit_lifecycle": deposit_lifecycle,
        "semantic_context": semantic_context,
        "legal_workflow": legal_workflow,
        "procedural_profile": procedural_profile,
        "remote_hearing": remote_hearing,
        "lawyer_checklist": lawyer_checklist,
        "normative_references": semantic_context.get("normative_references") or [],
        "agent_questions": [
            *procedural_questions,
            *(semantic_context.get("agent_questions") or []),
            *(
                [
                    "Sono arrivate tutte le quattro PEC/esiti del deposito o manca ancora accettazione/rifiuto finale?",
                    "L'esito controlli automatici contiene warning, errore fatale o atto non conforme?",
                    "Posso comunicare deposito accettato oppure devo comunicare solo uno stato intermedio?",
                ]
                if deposit_lifecycle
                else []
            ),
        ],
        "recommended_actions": [
            *lawyer_checklist[:5],
            *(semantic_context.get("recommended_actions") or []),
            *([legal_workflow.get("azione_proposta")] if legal_workflow.get("azione_proposta") else []),
            *(
                [deadline_proposal.get("reason")]
                if deadline_proposal.get("auto_create") and deadline_proposal.get("reason")
                else []
            ),
            *(
                [
                    "Mostrare la fase attuale del deposito e le PEC ancora attese.",
                    "Preparare comunicazione all'avvocato con esito, anomalie e prossimi controlli.",
                    "Registrare automaticamente il follow-up se manca l'esito finale di accettazione o rifiuto deposito.",
                ]
                if deposit_lifecycle
                else []
            ),
        ],
        "deadline_proposal": deadline_proposal,
        "blocking": False,
        "severity": severity,
        "generated_at": iso_now(),
    }


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _json_loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or "{}"))
    except Exception:
        return {}


def _local_acquire_item_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["detail"] = _json_loads(payload.pop("detail_json", "{}"))
    return payload


def _lookup_text(obj: Any, *names: str) -> str:
    for name in names:
        value = obj.get(name, "") if isinstance(obj, dict) else getattr(obj, name, "")
        if value is None:
            continue
        if hasattr(value, "value"):
            value = value.value
        text = clean_text(value)
        if text:
            return text
    return ""


def _normalise_lookup(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _lookup_tokens(value: Any) -> tuple[str, ...]:
    normalised = _normalise_lookup(value)
    return tuple(part for part in normalised.split() if part)


def _lookup_name_score(query: Any, candidate: Any) -> float:
    """Confronta nomi cliente in modo indipendente dall'ordine dei token."""

    query_tokens = set(_lookup_tokens(query))
    candidate_tokens = set(_lookup_tokens(candidate))
    if not query_tokens or not candidate_tokens:
        return 0.0
    if query_tokens == candidate_tokens:
        return 1.0
    overlap = len(query_tokens & candidate_tokens)
    if not overlap:
        return 0.0
    score = overlap / max(len(query_tokens), len(candidate_tokens))
    if min(len(query_tokens), len(candidate_tokens)) >= 2 and (
        query_tokens.issubset(candidate_tokens) or candidate_tokens.issubset(query_tokens)
    ):
        score = max(score, 0.86)
    return score


def _client_lookup_variants(cliente: Any) -> list[str]:
    nome = _lookup_text(cliente, "nome")
    cognome = _lookup_text(cliente, "cognome")
    variants = [
        _lookup_text(cliente, "id"),
        _lookup_text(cliente, "nome_completo", "ragione_sociale", "denominazione"),
        " ".join(part for part in (nome, cognome) if part),
        " ".join(part for part in (cognome, nome) if part),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for value in variants:
        cleaned = clean_text(value)
        key = _normalise_lookup(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


class PecAuditRepository:
    """Repository SQLite per PEC audit-grade e coda worker automatizzata."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        tenant_id: str = DEFAULT_TENANT_ID,
        clienti_db_path: str | Path | None = None,
        fascicoli_db_path: str | Path | None = None,
        fascicoli_docs_path: str | Path | None = None,
        scadenziario_db_path: str | Path | None = None,
        agenda_db_path: str | Path | None = None,
    ):
        self.db_path = Path(db_path)
        self.tenant_id = str(tenant_id or DEFAULT_TENANT_ID)
        self.clienti_db_path = Path(clienti_db_path) if clienti_db_path else None
        self.fascicoli_db_path = Path(fascicoli_db_path) if fascicoli_db_path else None
        self.fascicoli_docs_path = Path(fascicoli_docs_path) if fascicoli_docs_path else None
        self.scadenziario_db_path = Path(scadenziario_db_path) if scadenziario_db_path else None
        self.agenda_db_path = Path(agenda_db_path) if agenda_db_path else None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._quarantine_stale_journal()
        self.ensure_schema()

    def _quarantine_stale_journal(self) -> None:
        journal = self.db_path.with_name(f"{self.db_path.name}-journal")
        if not self.db_path.exists() or not journal.exists():
            return
        try:
            db_stat = self.db_path.stat()
            journal_stat = journal.stat()
        except OSError:
            return
        newest_mtime = max(db_stat.st_mtime, journal_stat.st_mtime)
        age_seconds = datetime.now().timestamp() - newest_mtime
        if journal_stat.st_size < 1024 * 1024 or age_seconds < 120:
            return
        stamp = datetime.now(ROME_TZ).strftime("%Y%m%d-%H%M%S")
        for path in (self.db_path, journal):
            if not path.exists():
                continue
            target = path.with_name(f"{path.name}.interrotto-{stamp}")
            counter = 1
            while target.exists():
                target = path.with_name(f"{path.name}.interrotto-{stamp}-{counter}")
                counter += 1
            try:
                path.replace(target)
            except OSError:
                return

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0, factory=ManagedConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SQLITE_SCHEMA)
            migration_sha = sha256_bytes(SQLITE_SCHEMA.encode("utf-8"))
            conn.execute(
                """
                INSERT OR IGNORE INTO pec_schema_migrations(version, applied_at, sha256)
                VALUES (?, ?, ?)
                """,
                (SCHEMA_VERSION, iso_now(), migration_sha),
            )
            now = iso_now()
            conn.execute(
                """
                INSERT OR IGNORE INTO pec_retention_policies
                (id, name, original_mime_days, parsed_json_days, legal_hold, action, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("pec_audit_default", "Conservazione PEC audit-grade", 3650, 3650, 1, "review", now, now),
            )

    def append_audit(
        self,
        conn: sqlite3.Connection,
        *,
        action: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any] | None = None,
        actor: str = "pec-pipeline",
    ) -> str:
        prev_row = conn.execute(
            "SELECT entry_hash FROM pec_audit_log WHERE tenant_id=? ORDER BY occurred_at DESC, rowid DESC LIMIT 1",
            (self.tenant_id,),
        ).fetchone()
        prev_hash = str(prev_row["entry_hash"] if prev_row else "")
        entry_id = uuid.uuid4().hex
        occurred_at = iso_now()
        payload_json = canonical_json(payload or {})
        entry_hash = sha256_json(
            {
                "id": entry_id,
                "tenant_id": self.tenant_id,
                "occurred_at": occurred_at,
                "actor": actor,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "payload_json": payload_json,
                "prev_hash": prev_hash,
            }
        )
        conn.execute(
            """
            INSERT INTO pec_audit_log
            (id, tenant_id, occurred_at, actor, action, resource_type, resource_id, payload_json, prev_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, self.tenant_id, occurred_at, actor, action, resource_type, resource_id, payload_json, prev_hash, entry_hash),
        )
        return entry_hash

    def enqueue_job(
        self,
        conn: sqlite3.Connection,
        job_type: str,
        *,
        message_id: str = "",
        payload: dict[str, Any] | None = None,
        priority: int = 50,
        actor: str = "pec-pipeline",
    ) -> str:
        now = iso_now()
        job_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT OR IGNORE INTO pec_jobs
            (id, tenant_id, message_id, job_type, status, priority, attempts, max_attempts, available_at,
             payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'queued', ?, 0, 3, ?, ?, ?, ?)
            """,
            (
                job_id,
                self.tenant_id,
                message_id,
                job_type,
                int(priority),
                now,
                canonical_json(payload or {}),
                now,
                now,
            ),
        )
        self.append_audit(
            conn,
            action=f"pec.job.{job_type}.queued",
            resource_type="pec_job",
            resource_id=message_id or job_id,
            payload={"job_type": job_type, "message_id": message_id},
            actor=actor,
        )
        return job_id

    def ingest_mime(
        self,
        raw_mime: bytes,
        *,
        account_email: str = "",
        folder: str = "INBOX",
        imap_uid: str = "",
        actor: str = "pec-ingest",
        enqueue: bool = True,
    ) -> dict[str, Any]:
        if not raw_mime:
            raise ValueError("MIME PEC vuoto.")
        mime_hash = sha256_bytes(raw_mime)
        msg = message_from_bytes(raw_mime)
        message_id_header = str(msg.get("Message-ID", "") or "").strip()
        received_at = parsedate_iso(msg.get("Date", "")) or iso_now()
        message_pk = f"pec_{mime_hash[:24]}"
        retention_until = (date.today() + timedelta(days=3650)).isoformat()
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM pec_messages
                WHERE tenant_id=? AND (mime_sha256=? OR (message_id_header<>'' AND message_id_header=? AND account_email=?))
                LIMIT 1
                """,
                (self.tenant_id, mime_hash, message_id_header, account_email),
            ).fetchone()
            if existing:
                existing_id = str(existing["id"])
                self.append_audit(
                    conn,
                    action="pec.mime.duplicate",
                    resource_type="pec_message",
                    resource_id=existing_id,
                    payload={"mime_sha256": mime_hash, "message_id_header": message_id_header, "folder": folder},
                    actor=actor,
                )
                return {"id": existing_id, "duplicate": True, "mime_sha256": mime_hash}
            stale_existing = conn.execute(
                """
                SELECT id, tenant_id FROM pec_messages
                WHERE id=? OR mime_sha256=?
                   OR (message_id_header<>'' AND message_id_header=? AND account_email=?)
                ORDER BY CASE WHEN tenant_id=? THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (message_pk, mime_hash, message_id_header, account_email, self.tenant_id),
            ).fetchone()
            if stale_existing:
                existing_id = str(stale_existing["id"] or "")
                previous_tenant = str(stale_existing["tenant_id"] or "")
                if existing_id and previous_tenant and previous_tenant != self.tenant_id:
                    conn.execute(
                        "UPDATE pec_messages SET tenant_id=? WHERE id=? AND tenant_id=?",
                        (self.tenant_id, existing_id, previous_tenant),
                    )
                self.append_audit(
                    conn,
                    action="pec.mime.duplicate",
                    resource_type="pec_message",
                    resource_id=existing_id,
                    payload={
                        "mime_sha256": mime_hash,
                        "message_id_header": message_id_header,
                        "folder": folder,
                        "tenant_normalized_from": previous_tenant if previous_tenant != self.tenant_id else "",
                    },
                    actor=actor,
                )
                return {"id": existing_id, "duplicate": True, "mime_sha256": mime_hash}
            metadata = {
                "headers": {
                    "subject": decode_header_value(msg.get("Subject", "")),
                    "from": decode_header_value(msg.get("From", "")),
                    "to": decode_header_value(msg.get("To", "")),
                }
            }
            conn.execute(
                """
                INSERT INTO pec_messages
                (id, tenant_id, account_email, folder, imap_uid, message_id_header, mime_sha256, mime_size,
                 original_mime, received_at, ingested_at, retention_until, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_pk,
                    self.tenant_id,
                    clean_text(account_email).lower(),
                    clean_text(folder) or "INBOX",
                    clean_text(imap_uid),
                    message_id_header,
                    mime_hash,
                    len(raw_mime),
                    sqlite3.Binary(raw_mime),
                    received_at,
                    iso_now(),
                    retention_until,
                    canonical_json(metadata),
                ),
            )
            self.append_audit(
                conn,
                action="pec.mime.ingested",
                resource_type="pec_message",
                resource_id=message_pk,
                payload={"mime_sha256": mime_hash, "message_id_header": message_id_header, "mime_size": len(raw_mime)},
                actor=actor,
            )
            if enqueue:
                self.enqueue_job(conn, "parse", message_id=message_pk, priority=20, actor=actor)
        return {"id": message_pk, "duplicate": False, "mime_sha256": mime_hash}

    def fetch_imap(
        self,
        *,
        imap_host: str,
        imap_port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        folders: list[str] | None = None,
        limit: int = 50,
        actor: str = "pec-imap",
    ) -> dict[str, Any]:
        folders = folders or cartelle_imap_standard()
        report = {"fetched": 0, "ingested": 0, "duplicates": 0, "errors": 0, "folders": []}
        client: imaplib.IMAP4
        client = imaplib.IMAP4_SSL(imap_host, imap_port) if use_ssl else imaplib.IMAP4(imap_host, imap_port)
        try:
            if not use_ssl:
                client.starttls()
            client.login(username, password)
            for folder in folders:
                try:
                    status, _data = client.select(folder, readonly=True)
                    if status != "OK":
                        continue
                    status, data = client.search(None, "ALL")
                    if status != "OK" or not data or not data[0]:
                        continue
                    uids = data[0].split()
                    selected = uids[-max(1, int(limit or 50)) :]
                    folder_report = {"folder": folder, "seen": len(selected), "ingested": 0, "duplicates": 0}
                    for uid in reversed(selected):
                        try:
                            status, msg_data = client.fetch(uid, "(RFC822)")
                            if status != "OK" or not msg_data or not msg_data[0]:
                                continue
                            raw = msg_data[0][1]
                            if not isinstance(raw, bytes):
                                continue
                            result = self.ingest_mime(
                                raw,
                                account_email=username,
                                folder=str(folder),
                                imap_uid=uid.decode("ascii", errors="ignore"),
                                actor=actor,
                            )
                            report["fetched"] += 1
                            if result.get("duplicate"):
                                report["duplicates"] += 1
                                folder_report["duplicates"] += 1
                            else:
                                report["ingested"] += 1
                                folder_report["ingested"] += 1
                        except Exception:
                            report["errors"] += 1
                    report["folders"].append(folder_report)
                except Exception:
                    report["errors"] += 1
        finally:
            try:
                client.logout()
            except Exception:
                pass
        with self.connect() as conn:
            self.append_audit(conn, action="pec.imap.fetch", resource_type="pec_mailbox", resource_id=username, payload=report, actor=actor)
        return report

    def get_message_row(self, conn: sqlite3.Connection, message_id: str) -> sqlite3.Row:
        clean_id = clean_text(message_id)
        row = conn.execute(
            "SELECT * FROM pec_messages WHERE tenant_id=? AND id=?",
            (self.tenant_id, clean_id),
        ).fetchone()
        if row is None:
            stale = conn.execute("SELECT * FROM pec_messages WHERE id=? LIMIT 1", (clean_id,)).fetchone()
            if stale is not None:
                previous_tenant = str(stale["tenant_id"] or "")
                if previous_tenant and previous_tenant != self.tenant_id:
                    conn.execute(
                        "UPDATE pec_messages SET tenant_id=? WHERE id=? AND tenant_id=?",
                        (self.tenant_id, clean_id, previous_tenant),
                    )
                    self.append_audit(
                        conn,
                        action="pec.message.tenant_normalized",
                        resource_type="pec_message",
                        resource_id=clean_id,
                        payload={"tenant_normalized_from": previous_tenant},
                        actor="pec-repository",
                    )
                row = conn.execute(
                    "SELECT * FROM pec_messages WHERE tenant_id=? AND id=?",
                    (self.tenant_id, clean_id),
                ).fetchone()
        if row is None:
            raise KeyError(f"PEC non trovata: {clean_id}")
        return row

    def latest_parsed_row(self, conn: sqlite3.Connection, message_id: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT * FROM pec_parsed_versions
            WHERE message_id=?
            ORDER BY version DESC
            LIMIT 1
            """,
            (message_id,),
        ).fetchone()

    def _insert_validation_report(
        self,
        conn: sqlite3.Connection,
        *,
        message_id: str,
        parsed_version_id: str,
        report: dict[str, Any],
        actor: str,
        action: str = "pec.validation.reported",
    ) -> dict[str, Any]:
        report_id = uuid.uuid4().hex
        report_hash = sha256_json(report)
        conn.execute(
            """
            INSERT INTO pec_validation_reports
            (id, message_id, parsed_version_id, event_type, report_json, report_sha256, severity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                message_id,
                parsed_version_id,
                report["event_type"],
                canonical_json(report),
                report_hash,
                report["severity"],
                iso_now(),
            ),
        )
        quality = "verde" if report["severity"] == "ok" else "giallo" if report["severity"] == "warning" else "rosso"
        conn.execute("UPDATE pec_messages SET quality_status=?, status=? WHERE id=?", (quality, "validated", message_id))
        self.append_audit(
            conn,
            action=action,
            resource_type="pec_validation_report",
            resource_id=report_id,
            payload={"message_id": message_id, "report_sha256": report_hash, "severity": report["severity"]},
            actor=actor,
        )
        return {"message_id": message_id, "report_id": report_id, "severity": report["severity"], "report_sha256": report_hash}

    def parse_and_store(self, message_id: str, *, actor: str = "pec-parser") -> dict[str, Any]:
        with self.connect() as conn:
            row = self.get_message_row(conn, message_id)
            raw_mime = bytes(row["original_mime"])
            parsed = parse_pec_message(raw_mime)
            previous = self.latest_parsed_row(conn, message_id)
            version = int(previous["version"] if previous else 0) + 1
            parsed_hash = sha256_json(parsed)
            parsed_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO pec_parsed_versions
                (id, message_id, version, parser_version, parsed_json, parsed_sha256, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (parsed_id, message_id, version, SCHEMA_VERSION, canonical_json(parsed), parsed_hash, iso_now(), actor),
            )
            conn.execute(
                "UPDATE pec_messages SET status=?, quality_status=? WHERE id=?",
                ("parsed", "da_controllare", message_id),
            )
            self.append_audit(
                conn,
                action="pec.parsed.version_created",
                resource_type="pec_parsed_version",
                resource_id=parsed_id,
                payload={"message_id": message_id, "version": version, "parsed_sha256": parsed_hash},
                actor=actor,
            )
            self.enqueue_job(conn, "classify", message_id=message_id, priority=25, actor=actor)
        return {"message_id": message_id, "parsed_version_id": parsed_id, "version": version, "parsed_sha256": parsed_hash}

    def _attachment_payloads_for_message(self, conn: sqlite3.Connection, message_id: str) -> tuple[dict[str, Any], list[AttachmentPayload]]:
        row = self.get_message_row(conn, message_id)
        parsed_row = self.latest_parsed_row(conn, message_id)
        if parsed_row is None:
            raise KeyError("JSON PEC non ancora disponibile.")
        parsed = json.loads(parsed_row["parsed_json"])
        _text, _html, attachments = extract_message_parts(message_from_bytes(bytes(row["original_mime"])))
        return {"row": row, "parsed_row": parsed_row, "parsed": parsed}, attachments

    def classify_attachments(self, message_id: str, *, actor: str = "pec-classifier") -> dict[str, Any]:
        with self.connect() as conn:
            ctx, payloads = self._attachment_payloads_for_message(conn, message_id)
            parsed_row = ctx["parsed_row"]
            parsed = ctx["parsed"]
            message_context = " ".join(
                [
                    str((parsed.get("headers") or {}).get("subject") or ""),
                    str(((parsed.get("body") or {}).get("text") or "")),
                    str(((parsed.get("body") or {}).get("html_text") or "")),
                ]
            )
            created: list[dict[str, Any]] = []
            for item in payloads:
                classification, score, reason = classify_attachment(item, message_context)
                if score < 0.65 and classification != "da confermare":
                    classification = "da confermare"
                    reason = "confidenza sotto soglia"
                attachment_id = uuid.uuid4().hex
                metadata = {"nested_message_id": item.nested_message_id}
                conn.execute(
                    """
                    INSERT OR REPLACE INTO pec_attachments
                    (id, message_id, parsed_version_id, attachment_index, filename, content_type, size_bytes,
                     sha256, classification, classification_score, classification_reason, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attachment_id,
                        message_id,
                        parsed_row["id"],
                        item.index,
                        item.filename,
                        item.content_type,
                        len(item.data),
                        sha256_bytes(item.data),
                        classification,
                        score,
                        reason,
                        canonical_json(metadata),
                        iso_now(),
                    ),
                )
                created.append({"filename": item.filename, "classification": classification, "score": score})
            self.append_audit(
                conn,
                action="pec.attachments.classified",
                resource_type="pec_message",
                resource_id=message_id,
                payload={"attachments": created},
                actor=actor,
            )
            self.enqueue_job(conn, "ocr", message_id=message_id, priority=30, actor=actor)
        return {"message_id": message_id, "attachments": created}

    def _stale_zip_ocr_rows(self, conn: sqlite3.Connection, message_id: str, parsed_version_id: str) -> list[sqlite3.Row]:
        rows = conn.execute(
            """
            SELECT attachment_index, filename, content_type, ocr_text
            FROM pec_attachments
            WHERE message_id=? AND parsed_version_id=?
              AND COALESCE(ocr_text, '')<>''
            """,
            (message_id, parsed_version_id),
        ).fetchall()
        return [
            row
            for row in rows
            if _is_stale_zip_ocr_text(str(row["filename"] or ""), str(row["content_type"] or ""), str(row["ocr_text"] or ""))
        ]

    def _refresh_ocr_for_message_on_connection(
        self,
        conn: sqlite3.Connection,
        message_id: str,
        *,
        actor: str,
        action: str = "pec.attachments.ocr",
    ) -> list[dict[str, Any]]:
        _ctx, payloads = self._attachment_payloads_for_message(conn, message_id)
        processed: list[dict[str, Any]] = []
        for item in payloads:
            text, coverage = extract_text_with_coverage(item)
            conn.execute(
                """
                UPDATE pec_attachments
                SET ocr_text=?, ocr_coverage=?
                WHERE message_id=? AND attachment_index=?
                """,
                (text, coverage, message_id, item.index),
            )
            processed.append({"filename": item.filename, "coverage": coverage, "chars": len(text)})
        self.append_audit(
            conn,
            action=action,
            resource_type="pec_message",
            resource_id=message_id,
            payload={"attachments": processed},
            actor=actor,
        )
        return processed

    def ocr_attachments(self, message_id: str, *, actor: str = "pec-ocr") -> dict[str, Any]:
        with self.connect() as conn:
            processed = self._refresh_ocr_for_message_on_connection(conn, message_id, actor=actor)
            self.enqueue_job(conn, "signcheck", message_id=message_id, priority=35, actor=actor)
        return {"message_id": message_id, "attachments": processed}

    def verify_signatures(self, message_id: str, *, actor: str = "pec-signcheck") -> dict[str, Any]:
        with self.connect() as conn:
            _ctx, payloads = self._attachment_payloads_for_message(conn, message_id)
            statuses: list[dict[str, Any]] = []
            aggregate = "non_applicabile"
            priority = {"non_valida": 5, "errore": 4, "scaduta": 3, "valida": 2, "assente": 1, "non_applicabile": 0}
            for item in payloads:
                status, details = verify_signature(item)
                conn.execute(
                    """
                    UPDATE pec_attachments
                    SET signature_status=?, signature_details_json=?
                    WHERE message_id=? AND attachment_index=?
                    """,
                    (status, canonical_json(details), message_id, item.index),
                )
                statuses.append({"filename": item.filename, "status": status})
                if priority.get(status, 0) > priority.get(aggregate, 0):
                    aggregate = status
            conn.execute("UPDATE pec_messages SET signature_status=? WHERE id=?", (aggregate, message_id))
            self.append_audit(conn, action="pec.signatures.checked", resource_type="pec_message", resource_id=message_id, payload={"status": aggregate, "attachments": statuses}, actor=actor)
            self.enqueue_job(conn, "validate", message_id=message_id, priority=40, actor=actor)
        return {"message_id": message_id, "signature_status": aggregate, "attachments": statuses}

    def attachment_rows(self, conn: sqlite3.Connection, message_id: str, parsed_version_id: str = "") -> list[dict[str, Any]]:
        params: tuple[Any, ...]
        if parsed_version_id:
            query = "SELECT * FROM pec_attachments WHERE message_id=? AND parsed_version_id=? ORDER BY attachment_index"
            params = (message_id, parsed_version_id)
        else:
            query = "SELECT * FROM pec_attachments WHERE message_id=? ORDER BY attachment_index"
            params = (message_id,)
        rows = []
        for row in conn.execute(query, params).fetchall():
            item = _row_to_dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            item["signature_details"] = json.loads(item.pop("signature_details_json") or "{}")
            rows.append(item)
        return rows

    def validate_message(self, message_id: str, *, actor: str = "pec-validator") -> dict[str, Any]:
        with self.connect() as conn:
            parsed_row = self.latest_parsed_row(conn, message_id)
            if parsed_row is None:
                raise KeyError("JSON PEC non ancora disponibile.")
            parsed = json.loads(parsed_row["parsed_json"])
            attachments = self.attachment_rows(conn, message_id, parsed_row["id"])
            report = build_validation_report(parsed, attachments)
            result = self._insert_validation_report(
                conn,
                message_id=message_id,
                parsed_version_id=str(parsed_row["id"]),
                report=report,
                actor=actor,
            )
            self.enqueue_job(conn, "link", message_id=message_id, priority=45, actor=actor)
        return result

    def refresh_validation_reports(self, *, actor: str = "pec-maintenance", limit: int = 0) -> dict[str, Any]:
        """Rigenera i report PEC già acquisiti con le regole correnti.

        Serve quando cambiano classificazione giuridica, estrazione OCR o filtri
        dei link: la UI e Lex devono leggere l'ultimo report corretto, non un
        JSON storico ormai superato.
        """

        checked = 0
        updated = 0
        errors: list[str] = []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM pec_messages
                WHERE tenant_id=?
                ORDER BY received_at DESC, ingested_at DESC
                """,
                (self.tenant_id,),
            ).fetchall()
            for row in rows:
                if limit and checked >= int(limit):
                    break
                message_id = str(row["id"] or "")
                checked += 1
                try:
                    parsed_row = self.latest_parsed_row(conn, message_id)
                    if parsed_row is None:
                        errors.append(f"{message_id}: JSON PEC non ancora disponibile.")
                        continue
                    parsed = json.loads(parsed_row["parsed_json"])
                    parsed_id = str(parsed_row["id"])
                    if self._stale_zip_ocr_rows(conn, message_id, parsed_id):
                        self._refresh_ocr_for_message_on_connection(
                            conn,
                            message_id,
                            actor=actor,
                            action="pec.attachments.ocr_repaired",
                        )
                    attachments = self.attachment_rows(conn, message_id, parsed_id)
                    report = build_validation_report(parsed, attachments)
                    self._insert_validation_report(
                        conn,
                        message_id=message_id,
                        parsed_version_id=parsed_id,
                        report=report,
                        actor=actor,
                        action="pec.validation.refreshed",
                    )
                    updated += 1
                except Exception as exc:
                    errors.append(f"{message_id}: {exc}")
        return {"ok": not errors, "checked": checked, "updated": updated, "errors": errors[:20]}

    def _fascicoli_candidates(self, parsed: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if not self.fascicoli_db_path:
            return {"rg": [], "parties": [], "office": "", "keywords": []}, []
        try:
            from pct.fascicoli import GestioneFascicoli

            manager = GestioneFascicoli(db_path=str(self.fascicoli_db_path), documents_dir=str(self.fascicoli_docs_path or self.fascicoli_db_path.parent / "documenti"))
            fascicoli = manager.tutti(archiviati=True)
        except Exception:
            return {"rg": [], "parties": [], "office": "", "keywords": []}, []
        headers = parsed.get("headers") or {}
        fields = parsed.get("fields") or {}
        body = parsed.get("body") or {}
        rg = list(parsed.get("rg_candidates") or [])
        sender_field = (fields.get("mittente") or {}).get("value") or {}
        parties = [
            clean_text(sender_field.get("name") if isinstance(sender_field, dict) else ""),
            clean_text(sender_field.get("email") if isinstance(sender_field, dict) else ""),
        ]
        text = " ".join([str(headers.get("subject") or ""), str(body.get("text") or ""), str(body.get("html_text") or "")])
        office_match = re.search(r"\b(?:tribunale|corte|giudice di pace)\s+di\s+([A-Za-zÀ-ÿ' ]{3,40})", text, re.I)
        office = clean_text(office_match.group(0) if office_match else "")
        keywords = [item.lower() for item in re.findall(r"\b[A-Za-zÀ-ÿ]{5,}\b", text)[:40]]
        seeds = {"rg": rg, "parties": [item for item in parties if item], "office": office, "keywords": keywords[:12]}
        candidates: list[dict[str, Any]] = []
        for fascicolo in fascicoli:
            score = 0.0
            reasons: list[str] = []
            fasc_rg = ""
            numero_rg = clean_text(getattr(fascicolo, "numero_rg", ""))
            anno_rg = clean_text(getattr(fascicolo, "anno_rg", ""))
            if numero_rg and anno_rg:
                fasc_rg = f"{numero_rg}/{anno_rg}"
            elif numero_rg:
                fasc_rg = numero_rg
            if fasc_rg and any(candidate == fasc_rg or candidate in fasc_rg or fasc_rg in candidate for candidate in rg):
                score += 0.58
                reasons.append("RG coincidente")
            party_text = " ".join(
                clean_text(getattr(fascicolo, attr, ""))
                for attr in ("nome_cliente", "controparte", "attore_principale", "oggetto", "titolo")
            ).lower()
            party_hits = [party for party in parties if party and party.lower() in party_text]
            if party_hits:
                score += min(0.24, 0.12 * len(party_hits))
                reasons.append("parte o mittente compatibile")
            office_text = clean_text(getattr(fascicolo, "tribunale", "")).lower()
            if office and office_text and (office.lower() in office_text or office_text in office.lower()):
                score += 0.1
                reasons.append("ufficio compatibile")
            keyword_hits = sorted({kw for kw in keywords if len(kw) >= 6 and kw in party_text})
            if keyword_hits:
                score += min(0.12, 0.03 * len(keyword_hits))
                reasons.append("parole chiave comuni")
            if score:
                candidates.append(
                    {
                        "id": str(getattr(fascicolo, "id", "")),
                        "title": clean_text(getattr(fascicolo, "titolo", ""), 120),
                        "number": clean_text(getattr(fascicolo, "numero", "")),
                        "rg": fasc_rg,
                        "score": round(min(score, 1.0), 3),
                        "reasons": reasons,
                    }
                )
        candidates.sort(key=lambda item: float(item["score"]), reverse=True)
        return seeds, candidates[:5]

    def link_fascicolo(self, message_id: str, *, threshold: float = 0.78, actor: str = "pec-linker") -> dict[str, Any]:
        with self.connect() as conn:
            parsed_row = self.latest_parsed_row(conn, message_id)
            if parsed_row is None:
                raise KeyError("JSON PEC non ancora disponibile.")
            parsed = json.loads(parsed_row["parsed_json"])
            seeds, candidates = self._fascicoli_candidates(parsed)
            best = candidates[0] if candidates else {}
            score = float(best.get("score") or 0.0)
            fascicolo_id = str(best.get("id") or "") if score >= threshold else ""
            status = "automatico" if fascicolo_id else "proposte" if candidates else "nessun_candidato"
            link_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO pec_fascicolo_links
                (id, message_id, parsed_version_id, fascicolo_id, score, status, seeds_json, candidates_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (link_id, message_id, parsed_row["id"], fascicolo_id, score, status, canonical_json(seeds), canonical_json(candidates), iso_now()),
            )
            conn.execute(
                "UPDATE pec_messages SET linked_fascicolo_id=?, linked_fascicolo_score=?, status=? WHERE id=?",
                (fascicolo_id, score, "linked" if fascicolo_id else "link_candidates", message_id),
            )
            self.append_audit(conn, action="pec.fascicolo.reconciled", resource_type="pec_message", resource_id=message_id, payload={"status": status, "score": score, "candidates": candidates}, actor=actor)
        auto_deadline: dict[str, Any] = {}
        try:
            report = self.get_message_detail(message_id).get("validation_report") or {}
            proposal = report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {}
            if proposal.get("auto_create"):
                auto_deadline = self.schedule_deadline(message_id, actor=actor)
        except Exception as exc:
            auto_deadline = {"ok": False, "message": f"Scadenza automatica non registrata: {exc}"}
        return {
            "message_id": message_id,
            "status": status,
            "fascicolo_id": fascicolo_id,
            "score": score,
            "candidates": candidates,
            "seeds": seeds,
            "auto_deadline": auto_deadline,
        }

    def run_pending_jobs(self, *, limit: int = 100, actor: str = "pec-worker") -> dict[str, Any]:
        processed = 0
        failed = 0
        done: list[dict[str, Any]] = []
        for _ in range(max(1, int(limit or 100))):
            with self.connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM pec_jobs
                    WHERE tenant_id=? AND status='queued' AND available_at<=?
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    """,
                    (self.tenant_id, iso_now()),
                ).fetchone()
                if row is None:
                    break
                conn.execute(
                    "UPDATE pec_jobs SET status='running', attempts=attempts+1, started_at=?, updated_at=? WHERE id=?",
                    (iso_now(), iso_now(), row["id"]),
                )
            try:
                job_type = str(row["job_type"])
                message_id = str(row["message_id"] or "")
                if job_type == "parse":
                    result = self.parse_and_store(message_id, actor=actor)
                elif job_type == "classify":
                    result = self.classify_attachments(message_id, actor=actor)
                elif job_type == "ocr":
                    result = self.ocr_attachments(message_id, actor=actor)
                elif job_type == "signcheck":
                    result = self.verify_signatures(message_id, actor=actor)
                elif job_type == "validate":
                    result = self.validate_message(message_id, actor=actor)
                elif job_type == "link":
                    result = self.link_fascicolo(message_id, actor=actor)
                elif job_type == "digest":
                    payload = json.loads(row["payload_json"] or "{}")
                    result = self.build_daily_digest(digest_date=str(payload.get("digest_date") or date.today().isoformat()), actor=actor)
                else:
                    raise ValueError(f"Job PEC non riconosciuto: {job_type}")
                with self.connect() as conn:
                    conn.execute(
                        "UPDATE pec_jobs SET status='done', finished_at=?, error='', updated_at=? WHERE id=?",
                        (iso_now(), iso_now(), row["id"]),
                    )
                    self.append_audit(conn, action=f"pec.job.{job_type}.done", resource_type="pec_job", resource_id=str(row["id"]), payload={"result": result}, actor=actor)
                processed += 1
                done.append({"job_type": job_type, "message_id": message_id, "result": result})
            except Exception as exc:
                with self.connect() as conn:
                    status = "failed"
                    available_at = (utc_now() + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
                    attempts = int(row["attempts"] or 0) + 1
                    if attempts < int(row["max_attempts"] or 3):
                        status = "queued"
                    conn.execute(
                        "UPDATE pec_jobs SET status=?, error=?, available_at=?, updated_at=? WHERE id=?",
                        (status, str(exc), available_at, iso_now(), row["id"]),
                    )
                    self.append_audit(conn, action=f"pec.job.{row['job_type']}.failed", resource_type="pec_job", resource_id=str(row["id"]), payload={"error": str(exc)}, actor=actor)
                failed += 1
        return {"processed": processed, "failed": failed, "jobs": done}

    def enqueue_missing_operational_jobs(self, message_id: str, *, actor: str = "pec-presidio") -> dict[str, Any]:
        """Rimette in coda solo il prossimo passaggio mancante per una PEC già acquisita.

        Il presidio massivo lavora spesso su MIME già presenti: senza questa
        riparazione un messaggio duplicato può restare fermo a uno stato
        intermedio e non arrivare mai a scadenziario/agenda.
        """

        with self.connect() as conn:
            self.get_message_row(conn, message_id)
            parsed_row = self.latest_parsed_row(conn, message_id)
            if parsed_row is None:
                job_id = self.enqueue_job(conn, "parse", message_id=message_id, priority=20, actor=actor)
                return {"message_id": message_id, "queued": ["parse"], "job_id": job_id, "stage": "parse_missing"}

            parsed_id = str(parsed_row["id"])
            attachment_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM pec_attachments WHERE message_id=? AND parsed_version_id=?",
                    (message_id, parsed_id),
                ).fetchone()[0]
                or 0
            )
            if attachment_count == 0:
                job_id = self.enqueue_job(conn, "classify", message_id=message_id, priority=25, actor=actor)
                return {"message_id": message_id, "queued": ["classify"], "job_id": job_id, "stage": "attachments_missing"}

            ocr_missing = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM pec_attachments
                    WHERE message_id=? AND parsed_version_id=?
                      AND classification NOT IN ('daticert', 'eml')
                      AND COALESCE(ocr_text, '')=''
                    """,
                    (message_id, parsed_id),
                ).fetchone()[0]
                or 0
            )
            stale_zip_ocr = len(self._stale_zip_ocr_rows(conn, message_id, parsed_id))
            if ocr_missing or stale_zip_ocr:
                job_id = self.enqueue_job(conn, "ocr", message_id=message_id, priority=30, actor=actor)
                return {
                    "message_id": message_id,
                    "queued": ["ocr"],
                    "job_id": job_id,
                    "stage": "ocr_stale_zip" if stale_zip_ocr else "ocr_missing",
                    "ocr_missing": ocr_missing,
                    "stale_zip_ocr": stale_zip_ocr,
                }

            signatures_missing = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM pec_attachments
                    WHERE message_id=? AND parsed_version_id=?
                      AND COALESCE(signature_status, '') IN ('', 'non_verificata')
                    """,
                    (message_id, parsed_id),
                ).fetchone()[0]
                or 0
            )
            if signatures_missing:
                job_id = self.enqueue_job(conn, "signcheck", message_id=message_id, priority=35, actor=actor)
                return {"message_id": message_id, "queued": ["signcheck"], "job_id": job_id, "stage": "signature_missing"}

            if not self.latest_report(conn, message_id):
                job_id = self.enqueue_job(conn, "validate", message_id=message_id, priority=40, actor=actor)
                return {"message_id": message_id, "queued": ["validate"], "job_id": job_id, "stage": "validation_missing"}

            if not self.latest_link(conn, message_id):
                job_id = self.enqueue_job(conn, "link", message_id=message_id, priority=45, actor=actor)
                return {"message_id": message_id, "queued": ["link"], "job_id": job_id, "stage": "link_missing"}

        return {"message_id": message_id, "queued": [], "stage": "complete"}

    def latest_report(self, conn: sqlite3.Connection, message_id: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT * FROM pec_validation_reports
            WHERE message_id=?
            ORDER BY created_at DESC, rowid DESC
            LIMIT 1
            """,
            (message_id,),
        ).fetchone()
        return json.loads(row["report_json"]) if row else {}

    def latest_link(self, conn: sqlite3.Connection, message_id: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT * FROM pec_fascicolo_links
            WHERE message_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (message_id,),
        ).fetchone()
        if not row:
            return {}
        payload = _row_to_dict(row)
        payload["seeds"] = json.loads(payload.pop("seeds_json") or "{}")
        payload["candidates"] = json.loads(payload.pop("candidates_json") or "[]")
        return payload

    def list_messages(
        self,
        *,
        limit: int = 100,
        folder: str = "",
        q: str = "",
        include_details: bool = True,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM pec_messages WHERE tenant_id=?"
        params: list[Any] = [self.tenant_id]
        if folder:
            query += " AND folder=?"
            params.append(folder)
        if q:
            query += " AND metadata_json LIKE ?"
            params.append(f"%{q}%")
        query += " ORDER BY received_at DESC LIMIT ?"
        params.append(int(limit or 100))
        rows: list[dict[str, Any]] = []
        with self.connect() as conn:
            for row in conn.execute(query, tuple(params)).fetchall():
                item = _row_to_dict(row)
                item.pop("original_mime", None)
                item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
                if include_details:
                    item["validation_report"] = self.latest_report(conn, item["id"])
                    item["fascicolo_link"] = self.latest_link(conn, item["id"])
                else:
                    item["validation_report"] = {}
                    item["fascicolo_link"] = {}
                rows.append(item)
        return rows

    def get_message_detail(self, message_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = self.get_message_row(conn, message_id)
            item = _row_to_dict(row)
            item["original_mime"] = None
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            parsed_row = self.latest_parsed_row(conn, message_id)
            parsed = json.loads(parsed_row["parsed_json"]) if parsed_row else {}
            parsed_meta = _row_to_dict(parsed_row) if parsed_row else {}
            if parsed_meta:
                parsed_meta.pop("parsed_json", None)
            return {
                "message": item,
                "parsed": parsed,
                "parsed_version": parsed_meta,
                "attachments": self.attachment_rows(conn, message_id, str(parsed_meta.get("id") or "")),
                "validation_report": self.latest_report(conn, message_id),
                "fascicolo_link": self.latest_link(conn, message_id),
            }

    def find_by_header_message_id(self, message_id_header: str) -> dict[str, Any] | None:
        if not message_id_header:
            return None
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM pec_messages
                WHERE tenant_id=? AND message_id_header=?
                ORDER BY ingested_at DESC
                LIMIT 1
                """,
                (self.tenant_id, message_id_header),
            ).fetchone()
            if not row:
                return None
        return self.get_message_detail(str(row["id"]))

    def summaries_by_header_message_ids(
        self,
        headers: Iterable[str],
        *,
        include_details: bool = True,
    ) -> dict[str, dict[str, Any]]:
        seen_values: set[str] = set()
        values: list[str] = []
        for item in headers:
            value = str(item or "").strip()
            if value and value not in seen_values:
                seen_values.add(value)
                values.append(value)
        if not values:
            return {}
        result: dict[str, dict[str, Any]] = {}
        with self.connect() as conn:
            for offset in range(0, len(values), 900):
                chunk = values[offset : offset + 900]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT id, message_id_header, quality_status, signature_status, linked_fascicolo_id,
                           linked_fascicolo_score, received_at
                    FROM pec_messages
                    WHERE tenant_id=? AND message_id_header IN ({placeholders})
                    ORDER BY received_at DESC
                    """,
                    (self.tenant_id, *chunk),
                ).fetchall()
                for row in rows:
                    header = str(row["message_id_header"] or "")
                    if header in result:
                        continue
                    summary = {
                        "id": row["id"],
                        "message_id_header": header,
                        "quality_status": row["quality_status"],
                        "signature_status": row["signature_status"],
                        "linked_fascicolo_id": row["linked_fascicolo_id"],
                        "linked_fascicolo_score": row["linked_fascicolo_score"],
                        "received_at": row["received_at"],
                        "fields": {},
                        "validation_report": {},
                        "fascicolo_link": {},
                        "attachments": [],
                    }
                    if include_details:
                        parsed_row = self.latest_parsed_row(conn, str(row["id"]))
                        parsed = json.loads(parsed_row["parsed_json"]) if parsed_row else {}
                        summary["fields"] = parsed.get("fields") or {}
                        summary["validation_report"] = self.latest_report(conn, str(row["id"]))
                        summary["fascicolo_link"] = self.latest_link(conn, str(row["id"]))
                        summary["attachments"] = self.attachment_rows(
                            conn,
                            str(row["id"]),
                            str(parsed_row["id"] if parsed_row else ""),
                        )
                    result[header] = summary
        return result

    def ids_by_header_message_ids(self, headers: Iterable[str]) -> dict[str, str]:
        seen_values: set[str] = set()
        values: list[str] = []
        for item in headers:
            value = str(item or "").strip()
            if value and value not in seen_values:
                seen_values.add(value)
                values.append(value)
        if not values:
            return {}
        result: dict[str, str] = {}
        with self.connect() as conn:
            for offset in range(0, len(values), 900):
                chunk = values[offset : offset + 900]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT id, message_id_header
                    FROM pec_messages
                    WHERE message_id_header IN ({placeholders})
                    ORDER BY CASE WHEN tenant_id=? THEN 0 ELSE 1 END
                    """,
                    (*chunk, self.tenant_id),
                ).fetchall()
                for row in rows:
                    header = str(row["message_id_header"] or "")
                    if header and header not in result:
                        result[header] = str(row["id"] or "")
        return result

    def original_mime(self, message_id: str) -> tuple[bytes, dict[str, Any]]:
        with self.connect() as conn:
            row = self.get_message_row(conn, message_id)
            self.append_audit(conn, action="pec.mime.opened", resource_type="pec_message", resource_id=message_id, payload={"mime_sha256": row["mime_sha256"]}, actor="pec-api")
            return bytes(row["original_mime"]), _row_to_dict(row)

    def build_daily_digest(self, *, digest_date: str | None = None, actor: str = "pec-digest") -> dict[str, Any]:
        digest_day = digest_date or date.today().isoformat()
        start = f"{digest_day}T00:00:00Z"
        end = f"{digest_day}T23:59:59Z"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, received_at, quality_status, signature_status, linked_fascicolo_id, metadata_json
                FROM pec_messages
                WHERE tenant_id=? AND received_at BETWEEN ? AND ?
                ORDER BY received_at DESC
                """,
                (self.tenant_id, start, end),
            ).fetchall()
            items = []
            anomalies = []
            fascicoli = set()
            for row in rows:
                metadata = json.loads(row["metadata_json"] or "{}")
                subject = clean_text(((metadata.get("headers") or {}).get("subject") or ""), 140)
                item = {
                    "id": row["id"],
                    "subject": subject,
                    "received_at": row["received_at"],
                    "quality_status": row["quality_status"],
                    "signature_status": row["signature_status"],
                    "href": f"/email/?pec_audit={row['id']}",
                }
                items.append(item)
                if row["linked_fascicolo_id"]:
                    fascicoli.add(row["linked_fascicolo_id"])
                if row["quality_status"] != "verde" or row["signature_status"] in {"non_valida", "errore", "scaduta"}:
                    anomalies.append(item)
            digest = {
                "date": digest_day,
                "generated_at": iso_now(),
                "new_messages": len(items),
                "touched_fascicoli": sorted(fascicoli),
                "anomalies": anomalies,
                "items": items,
                "direct_links": {
                    "pec": "/email/",
                    "digest": "/api/pec/digest",
                },
            }
            digest_hash = sha256_json(digest)
            digest_id = f"{self.tenant_id}:{digest_day}"
            conn.execute(
                """
                INSERT INTO pec_digest_runs
                (id, tenant_id, digest_date, run_at, digest_json, digest_sha256, status)
                VALUES (?, ?, ?, ?, ?, ?, 'done')
                ON CONFLICT(tenant_id, digest_date) DO UPDATE SET
                    run_at=excluded.run_at,
                    digest_json=excluded.digest_json,
                    digest_sha256=excluded.digest_sha256,
                    status=excluded.status
                """,
                (digest_id, self.tenant_id, digest_day, iso_now(), canonical_json(digest), digest_hash),
            )
            self.append_audit(conn, action="pec.digest.created", resource_type="pec_digest", resource_id=digest_id, payload={"digest_sha256": digest_hash, "new_messages": len(items)}, actor=actor)
        return digest

    def latest_digest(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT digest_json FROM pec_digest_runs
                WHERE tenant_id=?
                ORDER BY digest_date DESC, run_at DESC
                LIMIT 1
                """,
                (self.tenant_id,),
            ).fetchone()
            if not row:
                return self.build_daily_digest()
            return json.loads(row["digest_json"])

    def apply_retention_policy(self, *, dry_run: bool = True, actor: str = "pec-retention") -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, retention_until, retention_policy_id
                FROM pec_messages
                WHERE tenant_id=? AND retention_until<>'' AND retention_until<?
                ORDER BY retention_until ASC
                """,
                (self.tenant_id, date.today().isoformat()),
            ).fetchall()
            report = {
                "dry_run": dry_run,
                "expired": [{"id": row["id"], "retention_until": row["retention_until"], "policy": row["retention_policy_id"]} for row in rows],
                "action": "review",
            }
            self.append_audit(conn, action="pec.retention.reviewed", resource_type="pec_retention", resource_id=self.tenant_id, payload=report, actor=actor)
        return report

    def _fascicolo_card(self, fascicolo: Any, *, confidence: float, reason: str) -> dict[str, Any]:
        fascicolo_id = _lookup_text(fascicolo, "id")
        numero = _lookup_text(fascicolo, "numero")
        titolo = _lookup_text(fascicolo, "titolo")
        cliente = _lookup_text(fascicolo, "nome_cliente")
        stato = _lookup_text(fascicolo, "stato")
        return {
            "id": fascicolo_id,
            "numero": numero,
            "titolo": titolo,
            "nome_cliente": cliente,
            "stato": stato,
            "label": " - ".join(part for part in (numero, titolo) if part) or fascicolo_id,
            "confidence": round(max(0.0, min(1.0, confidence)), 2),
            "reason": reason,
            "href": f"/fascicoli/{fascicolo_id}" if fascicolo_id else "/fascicoli",
        }

    def prepare_save_to_fascicolo(
        self,
        message_id: str,
        *,
        nome: str = "",
        cognome: str = "",
        cliente_id: str = "",
        actor: str = "pec-api",
    ) -> dict[str, Any]:
        self.get_message_detail(message_id)
        if not self.clienti_db_path:
            return {"ok": False, "message": "Archivio clienti non configurato per questa azione.", "requires_confirmation": False, "candidates": []}
        if not self.fascicoli_db_path:
            return {"ok": False, "message": "Archivio fascicoli non configurato per questa azione.", "requires_confirmation": False, "candidates": []}

        nome = clean_text(nome, 80)
        cognome = clean_text(cognome, 80)
        cliente_id = clean_text(cliente_id, 80)
        query = " ".join(part for part in (nome, cognome) if part).strip()
        if not cliente_id and not query:
            return {"ok": False, "message": "Indica nome e cognome del cliente prima di cercare il fascicolo aperto.", "requires_confirmation": False, "candidates": []}

        try:
            from pct.clienti import GestioneClienti, StatoCliente
            from pct.fascicoli import GestioneFascicoli, StatoFascicolo

            clienti = GestioneClienti(db_path=str(self.clienti_db_path))
            fascicoli = GestioneFascicoli(
                db_path=str(self.fascicoli_db_path),
                documents_dir=str(self.fascicoli_docs_path or self.fascicoli_db_path.parent / "documenti"),
            )
        except Exception:
            return {"ok": False, "message": "Ricerca fascicolo non disponibile in questo momento.", "requires_confirmation": False, "candidates": []}

        matched_clienti: list[Any] = []
        if cliente_id:
            cliente = clienti.get(cliente_id)
            if cliente:
                matched_clienti.append(cliente)
        if query:
            haystack_terms = {part for part in (_normalise_lookup(nome), _normalise_lookup(cognome), _normalise_lookup(query)) if part}
            for cliente in clienti.tutti():
                if getattr(cliente, "stato", None) == StatoCliente.ARCHIVIATO:
                    continue
                variants = _client_lookup_variants(cliente)
                normalised_variants = [_normalise_lookup(value) for value in variants]
                score = max((_lookup_name_score(query, value) for value in variants), default=0.0)
                if score >= 0.72 or any(
                    term
                    and any(term in variant or variant in term for variant in normalised_variants if variant)
                    for term in haystack_terms
                ):
                    if all(getattr(existing, "id", "") != getattr(cliente, "id", "") for existing in matched_clienti):
                        matched_clienti.append(cliente)

        matched_ids = {clean_text(getattr(cliente, "id", "")) for cliente in matched_clienti if clean_text(getattr(cliente, "id", ""))}
        query_norm = _normalise_lookup(query)
        matched_names = [
            value
            for cliente in matched_clienti
            for value in _client_lookup_variants(cliente)
            if _lookup_tokens(value)
        ]
        candidates_by_id: dict[str, dict[str, Any]] = {}
        for fascicolo in fascicoli.tutti(archiviati=False):
            if getattr(fascicolo, "stato", None) in {StatoFascicolo.DEFINITO, StatoFascicolo.ARCHIVIATO}:
                continue
            fascicolo_id = _lookup_text(fascicolo, "id")
            fascicolo_cliente_id = _lookup_text(fascicolo, "id_cliente", "cliente_id", "idCliente")
            fascicolo_cliente_raw = _lookup_text(fascicolo, "nome_cliente", "cliente", "assistito", "intestatario")
            fascicolo_cliente = _normalise_lookup(fascicolo_cliente_raw)
            if matched_ids and fascicolo_cliente_id in matched_ids:
                candidates_by_id[fascicolo_id] = self._fascicolo_card(fascicolo, confidence=1.0, reason="Cliente collegato all'anagrafica del fascicolo.")
                continue
            score = _lookup_name_score(query, fascicolo_cliente_raw)
            if matched_names:
                score = max(score, *(_lookup_name_score(name, fascicolo_cliente_raw) for name in matched_names))
            if score >= 0.72 or (query_norm and fascicolo_cliente and (query_norm in fascicolo_cliente or fascicolo_cliente in query_norm)):
                candidates_by_id[fascicolo_id] = self._fascicolo_card(
                    fascicolo,
                    confidence=max(0.82, min(0.96, score or 0.82)),
                    reason="Nome cliente coerente con il fascicolo aperto.",
                )

        candidates = sorted(candidates_by_id.values(), key=lambda item: (-float(item.get("confidence") or 0), str(item.get("label") or "")))
        cliente_card = {}
        if matched_clienti:
            cliente = matched_clienti[0]
            cliente_card = {
                "id": _lookup_text(cliente, "id"),
                "nome": _lookup_text(cliente, "nome"),
                "cognome": _lookup_text(cliente, "cognome"),
                "nome_completo": _lookup_text(cliente, "nome_completo", "ragione_sociale"),
            }
        with self.connect() as conn:
            self.append_audit(
                conn,
                action="pec.fascicolo.prepare_save",
                resource_type="pec_message",
                resource_id=message_id,
                payload={"query": query, "cliente_id": cliente_id, "candidates": [item.get("id") for item in candidates[:10]]},
                actor=actor,
            )
        if not candidates:
            return {
                "ok": False,
                "message": "Nessun fascicolo aperto trovato per il cliente indicato.",
                "requires_confirmation": False,
                "cliente": cliente_card,
                "candidates": [],
            }
        return {
            "ok": True,
            "message": "Conferma il fascicolo aperto in cui salvare il MIME della PEC.",
            "requires_confirmation": True,
            "cliente": cliente_card,
            "candidates": candidates,
        }

    def save_to_fascicolo(self, message_id: str, *, fascicolo_id: str = "", actor: str = "pec-api") -> dict[str, Any]:
        detail = self.get_message_detail(message_id)
        target_id = fascicolo_id or str((detail.get("message") or {}).get("linked_fascicolo_id") or "")
        if not target_id:
            return {"ok": False, "message": "Nessun fascicolo collegato automaticamente.", "candidates": (detail.get("fascicolo_link") or {}).get("candidates") or []}
        if not self.fascicoli_db_path:
            return {"ok": False, "message": "Archivio fascicoli non configurato per questa azione."}
        raw, row = self.original_mime(message_id)
        try:
            from pct.fascicoli import GestioneFascicoli, TipoDocumento

            manager = GestioneFascicoli(
                db_path=str(self.fascicoli_db_path),
                documents_dir=str(self.fascicoli_docs_path or self.fascicoli_db_path.parent / "documenti"),
            )
            subject = clean_text(((json.loads(row["metadata_json"] or "{}").get("headers") or {}).get("subject") or "PEC"), 80)
            doc = manager.aggiungi_documento(
                target_id,
                f"PEC - {subject}.eml",
                TipoDocumento.COMUNICAZIONE,
                raw,
                note="MIME originale PEC conservato dalla pipeline audit-grade.",
                tags=["PEC", "audit"],
                caricato_da=actor,
                fonte_documento="PEC_AUDIT_PIPELINE",
                msg_id_portale=message_id,
            )
        except Exception as exc:
            return {"ok": False, "message": f"Salvataggio nel fascicolo non completato: {exc}"}
        with self.connect() as conn:
            self.append_audit(conn, action="pec.fascicolo.saved", resource_type="pec_message", resource_id=message_id, payload={"fascicolo_id": target_id, "document_id": getattr(doc, "id", "")}, actor=actor)
        document_id = getattr(doc, "id", "")
        return {
            "ok": True,
            "message": "MIME PEC salvato nel fascicolo.",
            "fascicolo_id": target_id,
            "document_id": document_id,
            "fascicolo_href": f"/fascicoli/{target_id}",
            "document_href": f"/fascicoli/{target_id}#documento-{document_id}" if document_id else f"/fascicoli/{target_id}",
        }

    def request_missing_attachment(self, message_id: str, *, actor: str = "pec-api") -> dict[str, Any]:
        detail = self.get_message_detail(message_id)
        issues = (detail.get("validation_report") or {}).get("issues") or []
        missing = [item for item in issues if str(item.get("code") or "").startswith("missing_")]
        with self.connect() as conn:
            self.append_audit(conn, action="pec.missing_attachment.requested", resource_type="pec_message", resource_id=message_id, payload={"missing": missing}, actor=actor)
        if missing:
            labels = ", ".join(str(item.get("title") or "allegato") for item in missing)
            return {"ok": True, "message": f"Richiesta preparata per: {labels}.", "missing": missing}
        return {"ok": True, "message": "Non risultano allegati obbligatori mancanti dal controllo automatico.", "missing": []}

    def _agenda_datetime_candidates(self, target_date: str) -> list[str]:
        text = clean_text(target_date)
        if not text:
            return []
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            parsed = datetime.combine(date.fromisoformat(text[:10]), datetime.min.time())
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(ROME_TZ).replace(tzinfo=None)
        base_day = parsed.date()
        candidates: list[datetime] = []
        if parsed.hour or parsed.minute or parsed.second:
            candidates.append(parsed.replace(second=0, microsecond=0))
        for hour, minute in ((9, 0), (8, 30), (10, 0), (11, 30), (15, 0), (16, 30), (18, 0)):
            candidate = datetime.combine(base_day, datetime.min.time()).replace(hour=hour, minute=minute)
            if candidate not in candidates:
                candidates.append(candidate)
        return [candidate.isoformat(timespec="seconds") for candidate in candidates]

    def _deadline_date_in_rome(self, target_date: str) -> date | None:
        text = clean_text(target_date)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            try:
                return date.fromisoformat(text[:10])
            except Exception:
                return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(ROME_TZ)
        return parsed.date()

    def _is_expired_deadline_date(self, target_date: str) -> bool:
        deadline_day = self._deadline_date_in_rome(target_date)
        if deadline_day is None:
            return False
        return deadline_day < datetime.now(ROME_TZ).date()

    def _studio_db_for_data_path(self, path: Path | str):
        try:
            from pct.storage import StudioDB

            p = Path(path)
            tenant_child_dirs = {
                "agenda",
                "auth",
                "backup",
                "clienti",
                "comunicazioni",
                "config",
                "email",
                "fascicoli",
                "fatturazione",
                "intelligence",
                "notifiche",
                "privacy",
                "scadenziario",
                "soggetti",
                "studio",
                "template_atti",
                "telematico",
                "timesheet",
            }
            if p.suffix:
                root = p.parent.parent if p.parent.name.lower() in tenant_child_dirs else p.parent
            else:
                root = p.parent if p.name.lower() in tenant_child_dirs else p
            return StudioDB.get(str(root / "studio.db"))
        except Exception:
            return None

    def _scadenziario_manager(self):
        from pct.scadenziario import GestioneScadenziario

        return GestioneScadenziario(
            db_path=str(self.scadenziario_db_path),
            studio_db=self._studio_db_for_data_path(self.scadenziario_db_path),
        )

    def _agenda_manager(self):
        from pct.agenda import Agenda

        return Agenda(
            db_path=str(self.agenda_db_path),
            studio_db=self._studio_db_for_data_path(self.agenda_db_path),
        )

    def _sync_pec_deadline_to_agenda(
        self,
        *,
        message_id: str,
        title: str,
        target_date: str,
        proposal: dict[str, Any],
        report: dict[str, Any],
        linked_fascicolo_id: str = "",
        deadline_id: str = "",
        actor: str = "pec-api",
    ) -> dict[str, Any]:
        if not self.agenda_db_path:
            return {"ok": False, "message": "Agenda non configurata per questa azione."}
        try:
            from pct.agenda import TipoAppuntamento
            from pct.ical_import import EventoImportato

            agenda = self._agenda_manager()
            event_uid = f"PEC_AUDIT:{message_id}:deadline"
            remote_lines = _remote_hearing_note_lines(report, proposal)
            remote_extra = _remote_hearing_deadline_extra(report, proposal)
            description = "\n".join(
                part
                for part in (
                    clean_text(proposal.get("reason")) or "Presidio operativo generato dalla PEC.",
                    *remote_lines,
                    f"Fascicolo: {linked_fascicolo_id}" if linked_fascicolo_id else "",
                    f"Scadenza: {deadline_id}" if deadline_id else "",
                    f"Tipo evento: {proposal.get('source_event_type') or report.get('event_type') or '-'}",
                    f"Decorrenza letta: {proposal.get('source_event_at') or '-'}",
                    "Fonte: pipeline PEC audit-grade.",
                )
                if part
            )
            last_report: dict[str, Any] = {}
            for data_ora in self._agenda_datetime_candidates(target_date):
                event = EventoImportato(
                    uid=event_uid,
                    titolo=f"Presidio PEC - {title}"[:120],
                    data_ora=data_ora,
                    durata_minuti=30,
                    tutto_giorno=False,
                    luogo="Udienza da remoto" if remote_extra.get("remote_hearing_url") else "Agenda studio",
                    descrizione=description,
                    stato_ical="CONFIRMED",
                    organizzatore=_deadline_responsible_actor(actor),
                )
                last_report = agenda.upsert_da_evento_importato(
                    event,
                    provider="pec_audit",
                    source_url=f"/api/pec/messages/{message_id}",
                    profile_id="pec_scadenziario",
                    default_tipo=TipoAppuntamento.SCADENZA,
                    reminder_minuti=1440,
                    allow_overlap=True,
                )
                if last_report.get("outcome") != "conflict":
                    appuntamento = last_report.get("appuntamento")
                    agenda_id = str(getattr(appuntamento, "id", "") or "")
                    if agenda_id and linked_fascicolo_id:
                        try:
                            appuntamento = agenda.modifica(agenda_id, procedimento=linked_fascicolo_id)
                        except Exception:
                            pass
                    return {
                        "ok": True,
                        "message": "Scadenza PEC collegata anche all'agenda.",
                        "agenda_id": agenda_id,
                        "agenda_outcome": str(last_report.get("outcome") or ""),
                        "agenda_href": f"/agenda/{agenda_id}" if agenda_id else "/agenda",
                    }
            return {
                "ok": False,
                "message": "Scadenza creata, ma l'agenda aveva già impegni sovrapposti negli orari di presidio.",
                "agenda_outcome": str(last_report.get("outcome") or "conflict"),
            }
        except Exception as exc:
            return {"ok": False, "message": f"Agenda non aggiornata: {exc}"}

    def _validation_report_from_parsed(self, parsed: dict[str, Any]) -> dict[str, Any]:
        attachments: list[dict[str, Any]] = []
        for item in list(parsed.get("attachments") or []):
            if not isinstance(item, dict):
                continue
            filename = clean_text(item.get("filename"), 240)
            content_type = clean_text(item.get("content_type"), 120)
            probe = AttachmentPayload(
                index=int(item.get("index") or len(attachments)),
                filename=filename or f"allegato-{len(attachments) + 1}.bin",
                content_type=content_type or "application/octet-stream",
                data=b"",
            )
            classification, score, reason = classify_attachment(probe, json.dumps(parsed, ensure_ascii=False)[:3000])
            attachments.append(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "classification": classification,
                    "classification_score": score,
                    "classification_reason": reason,
                    "signature_status": "non_verificata",
                }
            )
        return build_validation_report(parsed, attachments)

    def existing_deadlines_by_message_id(self, message_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        wanted = {clean_text(item) for item in message_ids if clean_text(item)}
        if not wanted or not self.scadenziario_db_path:
            return {}
        try:
            manager = self._scadenziario_manager()
            result: dict[str, dict[str, Any]] = {}
            pattern = re.compile(r"\bPEC_AUDIT:([A-Za-z0-9_.:-]+)")
            for existing in manager.tutte(solo_aperte=False):
                notes = str(getattr(existing, "note", "") or "")
                for match in pattern.finditer(notes):
                    message_id = clean_text(match.group(1))
                    if message_id in wanted and message_id not in result:
                        result[message_id] = {
                            "deadline_id": str(getattr(existing, "id", "") or ""),
                            "due_date": str(getattr(existing, "data_scadenza", "") or ""),
                            "agenda_id": str(getattr(existing, "id_appuntamento", "") or ""),
                            "title": str(getattr(existing, "titolo", "") or ""),
                        }
                        break
            return result
        except Exception:
            return {}

    def skipped_deadlines_by_message_id(self, message_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        values: list[str] = []
        seen: set[str] = set()
        for item in message_ids:
            value = clean_text(item)
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        if not values:
            return {}
        result: dict[str, dict[str, Any]] = {}
        try:
            with self.connect() as conn:
                for offset in range(0, len(values), 900):
                    chunk = values[offset : offset + 900]
                    placeholders = ",".join("?" for _ in chunk)
                    rows = conn.execute(
                        f"""
                        SELECT resource_id, payload_json, occurred_at
                        FROM pec_audit_log
                        WHERE tenant_id=?
                          AND action='pec.deadline.skipped_expired'
                          AND resource_type='pec_message'
                          AND resource_id IN ({placeholders})
                        ORDER BY occurred_at DESC
                        """,
                        (self.tenant_id, *chunk),
                    ).fetchall()
                    for row in rows:
                        message_id = clean_text(row["resource_id"])
                        if not message_id or message_id in result:
                            continue
                        try:
                            payload = json.loads(row["payload_json"] or "{}")
                        except Exception:
                            payload = {}
                        if str(payload.get("deadline_policy_version") or "") != DEADLINE_POLICY_VERSION:
                            continue
                        result[message_id] = {
                            "message_id": message_id,
                            "due_date": clean_text(payload.get("due_date")),
                            "expired": True,
                            "message": "Termine già superato: già verificato con la politica scadenze PEC corrente.",
                            "occurred_at": clean_text(row["occurred_at"]),
                        }
        except Exception:
            return {}
        return result

    @staticmethod
    def _message_id_from_deadline_note(note: str) -> str:
        values = PecAuditRepository._message_ids_from_deadline_note(note)
        return values[0] if values else ""

    @staticmethod
    def _message_ids_from_deadline_note(note: str) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"\bPEC_AUDIT:([^\s\r\n]+)", str(note or "")):
            value = match.group(1).strip().strip(".,;")
            if not value.startswith("pec_"):
                continue
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return values

    def _detail_for_deadline_note(self, note: str) -> tuple[str, dict[str, Any]]:
        missing: list[str] = []
        for message_id in self._message_ids_from_deadline_note(note):
            try:
                return message_id, self.get_message_detail(message_id)
            except KeyError:
                missing.append(message_id)
        if missing:
            raise KeyError(f"PEC non trovate: {', '.join(missing[:5])}")
        raise KeyError("Nessun riferimento PEC nella scadenza.")

    def enrich_deadlines_with_remote_hearing_links(self, *, actor: str = "pec-maintenance", limit: int = 0) -> dict[str, Any]:
        if not self.scadenziario_db_path:
            return {"ok": False, "message": "Scadenziario non configurato.", "updated": 0, "checked": 0}
        manager = self._scadenziario_manager()
        checked = 0
        updated = 0
        skipped = 0
        errors: list[str] = []
        for scadenza in manager.tutte(solo_aperte=False):
            if limit and checked >= int(limit):
                break
            message_id = ""
            note = str(getattr(scadenza, "note", "") or "")
            if "PEC_AUDIT:" not in note:
                continue
            message_id = self._message_id_from_deadline_note(note)
            checked += 1
            if not message_id:
                skipped += 1
                continue
            try:
                message_id, detail = self._detail_for_deadline_note(note)
                report = detail.get("validation_report") if isinstance(detail.get("validation_report"), dict) else {}
                proposal = report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {}
                remote_extra = _remote_hearing_deadline_extra(report, proposal)
                remote_note_lines = _remote_hearing_note_lines(report, proposal)
                updates = _remote_hearing_updates_for_existing(scadenza, remote_extra, remote_note_lines)
                if not updates:
                    skipped += 1
                    continue
                scadenza = manager.aggiorna(str(getattr(scadenza, "id", "")), **updates)
                updated += 1
                self._sync_pec_deadline_to_agenda(
                    message_id=message_id,
                    title=str(getattr(scadenza, "titolo", "") or "PEC"),
                    target_date=str(getattr(scadenza, "operational_due_at", "") or getattr(scadenza, "data_scadenza", "") or ""),
                    proposal=proposal,
                    report=report,
                    linked_fascicolo_id=str(getattr(scadenza, "id_fascicolo", "") or ""),
                    deadline_id=str(getattr(scadenza, "id", "") or ""),
                    actor=actor,
                )
            except Exception as exc:
                errors.append(f"{message_id or getattr(scadenza, 'id', '') or 'scadenza'}: {exc}")
        return {
            "ok": not errors,
            "checked": checked,
            "updated": updated,
            "skipped": skipped,
            "errors": errors[:20],
        }

    def repair_pec_deadlines(self, *, actor: str = "pec-maintenance", limit: int = 0) -> dict[str, Any]:
        if not self.scadenziario_db_path:
            return {"ok": False, "message": "Scadenziario non configurato.", "checked": 0, "updated": 0, "deleted": 0}
        manager = self._scadenziario_manager()
        agenda = self._agenda_manager() if self.agenda_db_path else None
        checked = 0
        updated = 0
        deleted = 0
        skipped = 0
        errors: list[str] = []
        for scadenza in list(manager.tutte(solo_aperte=False)):
            if limit and checked >= int(limit):
                break
            message_id = ""
            note = str(getattr(scadenza, "note", "") or "")
            if "PEC_AUDIT:" not in note:
                continue
            message_id = self._message_id_from_deadline_note(note)
            checked += 1
            if not message_id:
                skipped += 1
                continue
            try:
                message_id, detail = self._detail_for_deadline_note(note)
                parsed = detail.get("parsed") if isinstance(detail.get("parsed"), dict) else {}
                attachments = detail.get("attachments") if isinstance(detail.get("attachments"), list) else []
                report = build_validation_report(parsed, attachments)
                proposal = report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {}
                current_title = clean_text(getattr(scadenza, "titolo", "") or "", 180)
                is_generic_notice = current_title.startswith("Valuta termini da notifica PEC")
                if is_generic_notice and not proposal.get("auto_create"):
                    scadenza_id = str(getattr(scadenza, "id", "") or "")
                    agenda_id = str(getattr(scadenza, "id_appuntamento", "") or "")
                    if agenda is not None:
                        if not agenda_id:
                            app = agenda.trova_per_uid_esterno(
                                f"PEC_AUDIT:{message_id}:deadline",
                                provider="pec_audit",
                                profile_id="pec_scadenziario",
                            )
                            agenda_id = str(getattr(app, "id", "") or "") if app else ""
                        if agenda_id:
                            try:
                                agenda.elimina(agenda_id)
                            except Exception:
                                pass
                    manager.elimina(scadenza_id)
                    deleted += 1
                    with self.connect() as conn:
                        self.append_audit(
                            conn,
                            action="pec.deadline.cleanup_deleted",
                            resource_type="pec_message",
                            resource_id=message_id,
                            payload={
                                "deadline_id": scadenza_id,
                                "agenda_id": agenda_id,
                                "reason": "Rimossa scadenza generica da notifica PEC senza termine o udienza concreta.",
                                "deadline_policy_version": DEADLINE_POLICY_VERSION,
                            },
                            actor=actor,
                        )
                    continue
                proposal_title = clean_text(proposal.get("title") or current_title, 120)
                remote_extra = _remote_hearing_deadline_extra(report, proposal)
                remote_note_lines = _remote_hearing_note_lines(report, proposal)
                updates = {
                    **_deadline_updates_for_existing(scadenza, proposal, title=proposal_title, actor=actor),
                    **_remote_hearing_updates_for_existing(scadenza, remote_extra, remote_note_lines),
                }
                if not updates:
                    skipped += 1
                    continue
                scadenza = manager.aggiorna(str(getattr(scadenza, "id", "")), **updates)
                updated += 1
                if proposal.get("auto_create"):
                    self._sync_pec_deadline_to_agenda(
                        message_id=message_id,
                        title=str(getattr(scadenza, "titolo", "") or proposal_title or "PEC"),
                        target_date=str(getattr(scadenza, "operational_due_at", "") or getattr(scadenza, "data_scadenza", "") or ""),
                        proposal=proposal,
                        report=report,
                        linked_fascicolo_id=str(getattr(scadenza, "id_fascicolo", "") or ""),
                        deadline_id=str(getattr(scadenza, "id", "") or ""),
                        actor=actor,
                    )
            except Exception as exc:
                errors.append(f"{message_id or getattr(scadenza, 'id', '') or 'scadenza'}: {exc}")
        return {
            "ok": not errors,
            "checked": checked,
            "updated": updated,
            "deleted": deleted,
            "skipped": skipped,
            "errors": errors[:20],
        }

    def get_local_acquire_run(self, run_id: str) -> dict[str, Any]:
        clean_id = clean_text(run_id)
        if not clean_id:
            return {}
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM pec_local_acquire_runs WHERE tenant_id=? AND id=?",
                (self.tenant_id, clean_id),
            ).fetchone()
        return _row_to_dict(row)

    def start_local_acquire_run(self, *, total_emails: int, batch_size: int, actor: str = "pec-api") -> dict[str, Any]:
        run_id = f"plar_{uuid.uuid4().hex[:24]}"
        now = iso_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pec_local_acquire_runs
                (id, tenant_id, status, started_at, updated_at, cursor_index, total_emails, batch_size)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (run_id, self.tenant_id, "running", now, now, 0, int(total_emails or 0), int(batch_size or 50)),
            )
            self.append_audit(
                conn,
                action="pec.local_acquire.started",
                resource_type="pec_local_acquire_run",
                resource_id=run_id,
                payload={"total_emails": int(total_emails or 0), "batch_size": int(batch_size or 50)},
                actor=actor,
            )
        return self.get_local_acquire_run(run_id)

    def update_local_acquire_run(
        self,
        run_id: str,
        *,
        cursor_index: int,
        total_emails: int,
        batch_size: int,
        deltas: dict[str, int] | None = None,
        status: str = "running",
        payload: dict[str, Any] | None = None,
        actor: str = "pec-api",
    ) -> dict[str, Any]:
        allowed = {
            "acquired",
            "duplicates",
            "skipped_missing_mime",
            "skipped_not_pec",
            "queued_repairs",
            "deadline_created",
            "deadline_already_exists",
            "deadline_expired",
            "deadline_not_ready",
            "deadline_errors",
            "agenda_linked",
            "errors",
        }
        clean_id = clean_text(run_id)
        now = iso_now()
        status = clean_text(status) or "running"
        finished_at = now if status in {"completed", "failed", "cancelled"} else ""
        payload_json = canonical_json(payload or {})
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM pec_local_acquire_runs WHERE tenant_id=? AND id=?",
                (self.tenant_id, clean_id),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO pec_local_acquire_runs
                    (id, tenant_id, status, started_at, updated_at, cursor_index, total_emails, batch_size, payload_json)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (clean_id, self.tenant_id, "running", now, now, 0, int(total_emails or 0), int(batch_size or 50), "{}"),
                )
            assignments = [
                "status=?",
                "updated_at=?",
                "finished_at=CASE WHEN ?<>'' THEN ? ELSE finished_at END",
                "cursor_index=?",
                "total_emails=?",
                "batch_size=?",
                "payload_json=?",
            ]
            args: list[Any] = [status, now, finished_at, finished_at, int(cursor_index or 0), int(total_emails or 0), int(batch_size or 50), payload_json]
            for key, value in (deltas or {}).items():
                if key not in allowed:
                    continue
                assignments.append(f"{key}={key}+?")
                args.append(int(value or 0))
            args.extend([self.tenant_id, clean_id])
            conn.execute(
                f"UPDATE pec_local_acquire_runs SET {', '.join(assignments)} WHERE tenant_id=? AND id=?",
                args,
            )
            self.append_audit(
                conn,
                action="pec.local_acquire.updated" if status == "running" else f"pec.local_acquire.{status}",
                resource_type="pec_local_acquire_run",
                resource_id=clean_id,
                payload={"cursor_index": cursor_index, "total_emails": total_emails, "deltas": deltas or {}, "status": status},
                actor=actor,
            )
        return self.get_local_acquire_run(clean_id)

    def record_local_acquire_item(
        self,
        run_id: str,
        *,
        email_id: str,
        message_id: str = "",
        subject: str = "",
        status: str,
        deadline_status: str = "",
        due_date: str = "",
        deadline_id: str = "",
        agenda_id: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        now = iso_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pec_local_acquire_items
                (id, tenant_id, run_id, email_id, message_id, subject, status, deadline_status,
                 due_date, deadline_id, agenda_id, detail_json, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id, run_id, email_id) DO UPDATE SET
                    message_id=excluded.message_id,
                    subject=excluded.subject,
                    status=excluded.status,
                    deadline_status=excluded.deadline_status,
                    due_date=excluded.due_date,
                    deadline_id=excluded.deadline_id,
                    agenda_id=excluded.agenda_id,
                    detail_json=excluded.detail_json,
                    updated_at=excluded.updated_at
                """,
                (
                    f"plai_{uuid.uuid4().hex[:24]}",
                    self.tenant_id,
                    clean_text(run_id),
                    clean_text(email_id),
                    clean_text(message_id),
                    clean_text(subject, 240),
                    clean_text(status) or "processed",
                    clean_text(deadline_status),
                    clean_text(due_date),
                    clean_text(deadline_id),
                    clean_text(agenda_id),
                    canonical_json(detail or {}),
                    now,
                    now,
                ),
            )

    def local_acquire_presidio_index(self, *, limit: int = 10000) -> dict[str, dict[str, dict[str, Any]]]:
        terminal_statuses = {
            "processed",
            "ingested",
            "duplicate",
            "missing_mime",
            "deadline_created",
            "deadline_already_exists",
            "deadline_expired",
            "deadline_not_ready",
            "already_presided",
        }
        by_email_id: dict[str, dict[str, Any]] = {}
        by_message_id: dict[str, dict[str, Any]] = {}
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pec_local_acquire_items
                WHERE tenant_id=?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (self.tenant_id, max(1, int(limit or 10000))),
            ).fetchall()
        for row in rows:
            item = _local_acquire_item_from_row(row)
            status = clean_text(item.get("status"))
            deadline_status = clean_text(item.get("deadline_status"))
            if status not in terminal_statuses and not deadline_status:
                continue
            email_id = clean_text(item.get("email_id"))
            message_id = clean_text(item.get("message_id"))
            if email_id and email_id not in by_email_id:
                by_email_id[email_id] = item
            if message_id and message_id not in by_message_id:
                by_message_id[message_id] = item
        return {"by_email_id": by_email_id, "by_message_id": by_message_id}

    def local_acquire_run_report(self, run_id: str, *, limit: int = 100) -> dict[str, Any]:
        run = self.get_local_acquire_run(run_id)
        if not run:
            return {}
        with self.connect() as conn:
            items = [
                _local_acquire_item_from_row(row)
                for row in conn.execute(
                    """
                    SELECT * FROM pec_local_acquire_items
                    WHERE tenant_id=? AND run_id=?
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (self.tenant_id, clean_text(run_id), max(1, int(limit or 100))),
                ).fetchall()
            ]
        payload = dict(run)
        payload["payload"] = _json_loads(payload.pop("payload_json", "{}"))
        payload["items"] = items
        return payload

    def schedule_deadline_from_payload(
        self,
        message_id: str,
        *,
        parsed: dict[str, Any],
        report: dict[str, Any] | None = None,
        message: dict[str, Any] | None = None,
        actor: str = "pec-api",
        due_date: str = "",
    ) -> dict[str, Any]:
        if not self.scadenziario_db_path:
            return {"ok": False, "message": "Scadenziario non configurato per questa azione."}
        report = dict(report or {})
        message = dict(message or {})
        if not report or not isinstance(report.get("deadline_proposal"), dict):
            report = self._validation_report_from_parsed(parsed)
        proposal = report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {}
        target_date = due_date or clean_text(proposal.get("due_date"))
        if not target_date:
            return {"ok": False, "message": "Nessuna scadenza automatica calcolabile per questa PEC.", "proposal": proposal}
        if self._is_expired_deadline_date(target_date):
            try:
                with self.connect() as conn:
                    self.append_audit(
                        conn,
                        action="pec.deadline.skipped_expired",
                        resource_type="pec_message",
                        resource_id=message_id,
                        payload={"due_date": target_date, "proposal": proposal, "deadline_policy_version": DEADLINE_POLICY_VERSION},
                        actor=actor,
                    )
            except Exception:
                pass
            return {
                "ok": False,
                "message": "Termine già superato: non riportato in scadenziario o agenda.",
                "due_date": target_date,
                "expired": True,
                "proposal": proposal,
            }
        title = clean_text(proposal.get("title") or (parsed.get("headers") or {}).get("subject") or "Verifica PEC", 120)
        marker = f"PEC_AUDIT:{message_id}"
        remote_extra = _remote_hearing_deadline_extra(report, proposal)
        remote_note_lines = _remote_hearing_note_lines(report, proposal)
        try:
            from pct.scadenziario import TipoTermine

            manager = self._scadenziario_manager()
            for existing in manager.tutte(solo_aperte=False):
                if marker in str(getattr(existing, "note", "") or ""):
                    updates = {
                        **_deadline_updates_for_existing(existing, proposal, title=title, actor=actor),
                        **_remote_hearing_updates_for_existing(existing, remote_extra, remote_note_lines),
                    }
                    if updates:
                        try:
                            existing = manager.aggiorna(str(getattr(existing, "id", "")), **updates)
                        except Exception:
                            pass
                    agenda = self._sync_pec_deadline_to_agenda(
                        message_id=message_id,
                        title=str(getattr(existing, "titolo", "") or title),
                        target_date=str(getattr(existing, "operational_due_at", "") or getattr(existing, "data_scadenza", "") or target_date),
                        proposal=proposal,
                        report=report,
                        linked_fascicolo_id=str(message.get("linked_fascicolo_id") or getattr(existing, "id_fascicolo", "") or ""),
                        deadline_id=str(getattr(existing, "id", "") or ""),
                        actor=actor,
                    )
                    agenda_id = str(agenda.get("agenda_id") or "")
                    if agenda_id and not str(getattr(existing, "id_appuntamento", "") or ""):
                        try:
                            manager.aggiorna(str(getattr(existing, "id", "")), id_appuntamento=agenda_id)
                        except Exception:
                            pass
                    return {
                        "ok": True,
                        "message": "Scadenza automatica già presente nello scadenziario.",
                        "deadline_id": getattr(existing, "id", ""),
                        "due_date": getattr(existing, "data_scadenza", target_date),
                        "agenda": agenda,
                        "already_exists": True,
                        "proposal": proposal,
                    }
            scadenza = manager.nuova(
                titolo=title,
                tipo=TipoTermine.UDIENZA
                if remote_extra.get("remote_hearing_detected")
                or str(proposal.get("deadline_kind") or "") == "udienza"
                or "udienza" in title.lower()
                else TipoTermine.ADEMPIMENTO,
                data_scadenza=target_date,
                id_fascicolo=str(message.get("linked_fascicolo_id") or ""),
                descrizione=clean_text(proposal.get("reason")) or "Scadenza generata automaticamente dalla pipeline PEC audit-grade.",
                note="\n".join(
                    part
                    for part in (
                        marker,
                        f"Tipo evento: {proposal.get('source_event_type') or report.get('event_type') or '-'}",
                        f"Decorrenza letta: {proposal.get('source_event_at') or '-'}",
                        *remote_note_lines,
                        "Termine legale conclusivo: no, presidio operativo automatico da verificare professionalmente.",
                    )
                    if part
                ),
                id_utente_responsabile=_deadline_responsible_actor(actor),
                source_event_type=str(proposal.get("source_event_type") or report.get("event_type") or ""),
                source_event_at=str(proposal.get("source_event_at") or ""),
                operational_due_at=target_date,
                deadline_profile_code="PEC_AUTO_PRESIDIO",
                **remote_extra,
            )
        except Exception as exc:
            return {"ok": False, "message": f"Scadenza non creata: {exc}"}
        agenda = self._sync_pec_deadline_to_agenda(
            message_id=message_id,
            title=title,
            target_date=target_date,
            proposal=proposal,
            report=report,
            linked_fascicolo_id=str(message.get("linked_fascicolo_id") or ""),
            deadline_id=str(getattr(scadenza, "id", "") or ""),
            actor=actor,
        )
        agenda_id = str(agenda.get("agenda_id") or "")
        if agenda_id:
            try:
                manager.aggiorna(str(getattr(scadenza, "id", "")), id_appuntamento=agenda_id)
                scadenza.id_appuntamento = agenda_id
            except Exception:
                pass
        try:
            with self.connect() as conn:
                self.append_audit(
                    conn,
                    action="pec.deadline.scheduled",
                    resource_type="pec_message",
                    resource_id=message_id,
                    payload={
                        "deadline_id": getattr(scadenza, "id", ""),
                        "due_date": target_date,
                        "proposal": proposal,
                        "agenda": agenda,
                        "deadline_policy_version": DEADLINE_POLICY_VERSION,
                    },
                    actor=actor,
                )
        except Exception:
            pass
        return {
            "ok": True,
            "message": "Scadenza automatica creata nello scadenziario.",
            "deadline_id": getattr(scadenza, "id", ""),
            "due_date": target_date,
            "agenda": agenda,
            "proposal": proposal,
        }

    def schedule_deadline(self, message_id: str, *, actor: str = "pec-api", due_date: str = "") -> dict[str, Any]:
        if not self.scadenziario_db_path:
            return {"ok": False, "message": "Scadenziario non configurato per questa azione."}
        detail = self.get_message_detail(message_id)
        message = detail.get("message") or {}
        parsed = detail.get("parsed") or {}
        report = detail.get("validation_report") if isinstance(detail.get("validation_report"), dict) else {}
        proposal = report.get("deadline_proposal") if isinstance(report.get("deadline_proposal"), dict) else {}
        target_date = due_date or clean_text(proposal.get("due_date"))
        if not target_date:
            return {"ok": False, "message": "Nessuna scadenza automatica calcolabile per questa PEC.", "proposal": proposal}
        if self._is_expired_deadline_date(target_date):
            with self.connect() as conn:
                self.append_audit(
                    conn,
                    action="pec.deadline.skipped_expired",
                    resource_type="pec_message",
                    resource_id=message_id,
                    payload={"due_date": target_date, "proposal": proposal, "deadline_policy_version": DEADLINE_POLICY_VERSION},
                    actor=actor,
                )
            return {
                "ok": False,
                "message": "Termine già superato: non riportato in scadenziario o agenda.",
                "due_date": target_date,
                "expired": True,
                "proposal": proposal,
            }
        title = clean_text(proposal.get("title") or (parsed.get("headers") or {}).get("subject") or "Verifica PEC", 120)
        marker = f"PEC_AUDIT:{message_id}"
        remote_extra = _remote_hearing_deadline_extra(report, proposal)
        remote_note_lines = _remote_hearing_note_lines(report, proposal)
        try:
            from pct.scadenziario import TipoTermine

            manager = self._scadenziario_manager()
            for existing in manager.tutte(solo_aperte=False):
                if marker in str(getattr(existing, "note", "") or ""):
                    updates = {
                        **_deadline_updates_for_existing(existing, proposal, title=title, actor=actor),
                        **_remote_hearing_updates_for_existing(existing, remote_extra, remote_note_lines),
                    }
                    if updates:
                        try:
                            existing = manager.aggiorna(str(getattr(existing, "id", "")), **updates)
                        except Exception:
                            pass
                    agenda = self._sync_pec_deadline_to_agenda(
                        message_id=message_id,
                        title=str(getattr(existing, "titolo", "") or title),
                        target_date=str(getattr(existing, "operational_due_at", "") or getattr(existing, "data_scadenza", "") or target_date),
                        proposal=proposal,
                        report=report,
                        linked_fascicolo_id=str(message.get("linked_fascicolo_id") or getattr(existing, "id_fascicolo", "") or ""),
                        deadline_id=str(getattr(existing, "id", "") or ""),
                        actor=actor,
                    )
                    agenda_id = str(agenda.get("agenda_id") or "")
                    if agenda_id and not str(getattr(existing, "id_appuntamento", "") or ""):
                        try:
                            manager.aggiorna(str(getattr(existing, "id", "")), id_appuntamento=agenda_id)
                        except Exception:
                            pass
                    return {
                        "ok": True,
                        "message": "Scadenza automatica già presente nello scadenziario.",
                        "deadline_id": getattr(existing, "id", ""),
                        "due_date": getattr(existing, "data_scadenza", target_date),
                        "agenda": agenda,
                        "already_exists": True,
                        "proposal": proposal,
                    }
            scadenza = manager.nuova(
                titolo=title,
                tipo=TipoTermine.UDIENZA
                if remote_extra.get("remote_hearing_detected")
                or str(proposal.get("deadline_kind") or "") == "udienza"
                or "udienza" in title.lower()
                else TipoTermine.ADEMPIMENTO,
                data_scadenza=target_date,
                id_fascicolo=str(message.get("linked_fascicolo_id") or ""),
                descrizione=clean_text(proposal.get("reason")) or "Scadenza generata automaticamente dalla pipeline PEC audit-grade.",
                note="\n".join(
                    part
                    for part in (
                        marker,
                        f"Tipo evento: {proposal.get('source_event_type') or report.get('event_type') or '-'}",
                        f"Decorrenza letta: {proposal.get('source_event_at') or '-'}",
                        *remote_note_lines,
                        "Termine legale conclusivo: no, presidio operativo automatico da verificare professionalmente.",
                    )
                    if part
                ),
                id_utente_responsabile=_deadline_responsible_actor(actor),
                source_event_type=str(proposal.get("source_event_type") or report.get("event_type") or ""),
                source_event_at=str(proposal.get("source_event_at") or ""),
                operational_due_at=target_date,
                deadline_profile_code="PEC_AUTO_PRESIDIO",
                **remote_extra,
            )
        except Exception as exc:
            return {"ok": False, "message": f"Scadenza non creata: {exc}"}
        agenda = self._sync_pec_deadline_to_agenda(
            message_id=message_id,
            title=title,
            target_date=target_date,
            proposal=proposal,
            report=report,
            linked_fascicolo_id=str(message.get("linked_fascicolo_id") or ""),
            deadline_id=str(getattr(scadenza, "id", "") or ""),
            actor=actor,
        )
        agenda_id = str(agenda.get("agenda_id") or "")
        if agenda_id:
            try:
                manager.aggiorna(str(getattr(scadenza, "id", "")), id_appuntamento=agenda_id)
                scadenza.id_appuntamento = agenda_id
            except Exception:
                pass
        with self.connect() as conn:
            self.append_audit(
                conn,
                action="pec.deadline.scheduled",
                resource_type="pec_message",
                resource_id=message_id,
                payload={
                    "deadline_id": getattr(scadenza, "id", ""),
                    "due_date": target_date,
                    "proposal": proposal,
                    "agenda": agenda,
                    "deadline_policy_version": DEADLINE_POLICY_VERSION,
                },
                actor=actor,
            )
        return {"ok": True, "message": "Scadenza automatica creata nello scadenziario.", "deadline_id": getattr(scadenza, "id", ""), "due_date": target_date, "agenda": agenda, "proposal": proposal}


def synthetic_pec_messages() -> list[tuple[str, bytes]]:
    """Dataset sintetico pubblico: nessun dato privato o reale di studio."""

    def build(
        index: int,
        subject: str,
        sender: str,
        body: str,
        attachments: list[tuple[str, str, bytes]],
        *,
        date_header: str = "Wed, 20 May 2026 09:00:00 +0200",
    ) -> bytes:
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = "studio@example.test"
        msg["Subject"] = subject
        msg["Date"] = date_header
        msg["Message-ID"] = f"<synthetic-pec-{index}@iusentra.test>"
        msg.set_content(body)
        for filename, content_type, data in attachments:
            maintype, subtype = content_type.split("/", 1) if "/" in content_type else ("application", "octet-stream")
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        return msg.as_bytes(policy=policy.SMTP)

    daticert = b"""<?xml version="1.0" encoding="UTF-8"?>
<postacert><tipo>avvenuta_consegna</tipo><data>2026-05-20T09:03:00+02:00</data></postacert>"""
    nested = EmailMessage()
    nested["From"] = "cancelleria@example.test"
    nested["To"] = "studio@example.test"
    nested["Subject"] = "Comunicazione annidata RG 882/2026"
    nested["Message-ID"] = "<nested-pec@iusentra.test>"
    nested.set_content("Comunicazione contenuta in EML annidata.")
    return [
        (
            "deposito_completo",
            build(
                1,
                "Deposito telematico RG 1234/2026 - avvenuta consegna",
                "Cancelleria PEC <cancelleria@pec.example.test>",
                "Ricevuta di avvenuta consegna per deposito RG 1234/2026 presso Tribunale di Milano.",
                [
                    ("atto_ricorso.pdf", "application/pdf", b"%PDF-1.4\nAtto ricorso RG 1234/2026\n%%EOF"),
                    ("procura_liti.pdf", "application/pdf", b"%PDF-1.4\nProcura alle liti\n%%EOF"),
                    ("daticert.xml", "application/xml", daticert),
                ],
            ),
        ),
        (
            "firma_invalida",
            build(
                2,
                "Deposito RG 4321/2026 - accettazione con firma da verificare",
                "PST <pst@pec.example.test>",
                "Ricevuta di accettazione deposito RG 4321/2026.",
                [
                    ("atto_memoria.pdf.p7m", "application/pkcs7-mime", b"IUSENTRA_INVALID_SIGNATURE"),
                    ("daticert.xml", "application/xml", daticert.replace(b"avvenuta_consegna", b"accettazione")),
                ],
            ),
        ),
        (
            "allegati_mancanti",
            build(
                3,
                "Deposito telematico RG 765/2026 - ricevuta",
                "Cancelleria <cancelleria@pec.example.test>",
                "Deposito telematico RG 765/2026 senza procura allegata.",
                [("atto_principale.pdf", "application/pdf", b"%PDF-1.4\nAtto principale\n%%EOF")],
            ),
        ),
        (
            "eml_annidata",
            build(
                4,
                "Comunicazione cancelleria RG 882/2026 con messaggio allegato",
                "Cancelleria <cancelleria@pec.example.test>",
                "Comunicazione di cancelleria con EML annidata per RG 882/2026.",
                [("messaggio_originale.eml", "message/rfc822", nested.as_bytes(policy=policy.SMTP))],
            ),
        ),
        (
            "mittente_ambiguo",
            build(
                5,
                "GIUDICE DI PACE - Notificazione ai sensi del D.L. 179/2012",
                "Ufficio notifiche <info@example.test>",
                "Notificazione telematica da presidiare. Il testo richiama il Giudice di Pace e il D.L. 179/2012 ma non espone RG chiaro.",
                [("daticert.xml", "application/xml", daticert)],
            ),
        ),
    ]


def ingest_synthetic_dataset(repository: PecAuditRepository, *, run_workers: bool = True) -> dict[str, Any]:
    results = []
    for label, raw in synthetic_pec_messages():
        result = repository.ingest_mime(raw, account_email="studio@example.test", folder="INBOX", imap_uid=label, actor="pec-demo")
        result["label"] = label
        results.append(result)
    worker_report = repository.run_pending_jobs(limit=200, actor="pec-demo") if run_workers else {"processed": 0, "failed": 0}
    digest = repository.build_daily_digest(digest_date="2026-05-20", actor="pec-demo")
    return {"ingested": results, "workers": worker_report, "digest": digest}
