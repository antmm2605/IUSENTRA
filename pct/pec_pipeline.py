"""Pipeline audit-grade per ingestione e controllo automatico PEC.

Il modulo affianca il client email storico senza sostituirlo: conserva il MIME
originale, versiona il JSON estratto, calcola hash per ogni passaggio e usa una
coda persistente per parser, allegati, OCR, firme, validazione e fascicolo.
"""

from __future__ import annotations

import email
import hashlib
import imaplib
import json
import mimetypes
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

from pct.email_client import cartelle_imap_standard

SCHEMA_VERSION = "2026-05-21.pec-audit-pipeline.v2"
DEFAULT_TENANT_ID = "default"
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
CREATE INDEX IF NOT EXISTS idx_pec_messages_quality ON pec_messages(tenant_id, quality_status);
CREATE INDEX IF NOT EXISTS idx_pec_jobs_due ON pec_jobs(status, available_at, priority);
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
    return texts


def xml_tag_value(xml_text: str, names: Iterable[str]) -> str:
    for name in names:
        pattern = re.compile(rf"<(?:\w+:)?{re.escape(name)}[^>]*>(.*?)</(?:\w+:)?{re.escape(name)}>", re.I | re.S)
        match = pattern.search(xml_text or "")
        if match:
            return clean_text(re.sub(r"<[^>]+>", " ", match.group(1)))
    return ""


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


def extract_text_with_coverage(item: AttachmentPayload) -> tuple[str, float]:
    name = item.filename
    lower = name.lower()
    text = ""
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
    if not text:
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
        "rg_candidates": rg_values,
        "body": {
            "text": clean_text(text_body, 20000),
            "html_text": clean_text(re.sub(r"<[^>]+>", " ", html_body), 20000),
        },
        "xml_documents": [{"filename": name, "sha256": sha256_bytes(text.encode("utf-8", errors="replace"))} for name, text in xml_texts.items()],
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
    base = source_date or date.today()
    candidate = base + timedelta(days=max(0, lead_days))
    today = date.today()
    if candidate < today:
        return today.isoformat()
    return candidate.isoformat()


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
    if event_type in notice_events:
        return {
            "status": "ready",
            "auto_create": True,
            "title": f"Valuta termini da notifica PEC: {subject}",
            "due_date": _operational_due_date(source_date, lead_days=1),
            "source_event_at": source_date_iso,
            "source_event_type": event_type,
            "priority": "alta",
            "legal_deadline": False,
            "reason": "Notifica giudiziaria rilevata: il software registra automaticamente il presidio operativo per identificare atto, fascicolo e termini applicabili.",
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
    return {
        "event_type": event_type,
        "required": required,
        "present": sorted(present),
        "issues": issues,
        "deposit_lifecycle": deposit_lifecycle,
        "semantic_context": semantic_context,
        "normative_references": semantic_context.get("normative_references") or [],
        "agent_questions": [
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
            *(semantic_context.get("recommended_actions") or []),
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
    ):
        self.db_path = Path(db_path)
        self.tenant_id = str(tenant_id or DEFAULT_TENANT_ID)
        self.clienti_db_path = Path(clienti_db_path) if clienti_db_path else None
        self.fascicoli_db_path = Path(fascicoli_db_path) if fascicoli_db_path else None
        self.fascicoli_docs_path = Path(fascicoli_docs_path) if fascicoli_docs_path else None
        self.scadenziario_db_path = Path(scadenziario_db_path) if scadenziario_db_path else None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, factory=ManagedConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
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
        row = conn.execute(
            "SELECT * FROM pec_messages WHERE tenant_id=? AND id=?",
            (self.tenant_id, message_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"PEC non trovata: {message_id}")
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

    def ocr_attachments(self, message_id: str, *, actor: str = "pec-ocr") -> dict[str, Any]:
        with self.connect() as conn:
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
            self.append_audit(conn, action="pec.attachments.ocr", resource_type="pec_message", resource_id=message_id, payload={"attachments": processed}, actor=actor)
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
            report_id = uuid.uuid4().hex
            report_hash = sha256_json(report)
            conn.execute(
                """
                INSERT INTO pec_validation_reports
                (id, message_id, parsed_version_id, event_type, report_json, report_sha256, severity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (report_id, message_id, parsed_row["id"], report["event_type"], canonical_json(report), report_hash, report["severity"], iso_now()),
            )
            quality = "verde" if report["severity"] == "ok" else "giallo" if report["severity"] == "warning" else "rosso"
            conn.execute("UPDATE pec_messages SET quality_status=?, status=? WHERE id=?", (quality, "validated", message_id))
            self.append_audit(conn, action="pec.validation.reported", resource_type="pec_validation_report", resource_id=report_id, payload={"message_id": message_id, "report_sha256": report_hash, "severity": report["severity"]}, actor=actor)
            self.enqueue_job(conn, "link", message_id=message_id, priority=45, actor=actor)
        return {"message_id": message_id, "report_id": report_id, "severity": report["severity"], "report_sha256": report_hash}

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

    def latest_report(self, conn: sqlite3.Connection, message_id: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT * FROM pec_validation_reports
            WHERE message_id=?
            ORDER BY created_at DESC
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

    def list_messages(self, *, limit: int = 100, folder: str = "", q: str = "") -> list[dict[str, Any]]:
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
                item["validation_report"] = self.latest_report(conn, item["id"])
                item["fascicolo_link"] = self.latest_link(conn, item["id"])
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

    def summaries_by_header_message_ids(self, headers: Iterable[str]) -> dict[str, dict[str, Any]]:
        values = [str(item or "").strip() for item in headers if str(item or "").strip()]
        if not values:
            return {}
        placeholders = ",".join("?" for _ in values)
        result: dict[str, dict[str, Any]] = {}
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, message_id_header, quality_status, signature_status, linked_fascicolo_id,
                       linked_fascicolo_score, received_at
                FROM pec_messages
                WHERE tenant_id=? AND message_id_header IN ({placeholders})
                ORDER BY received_at DESC
                """,
                (self.tenant_id, *values),
            ).fetchall()
            for row in rows:
                header = str(row["message_id_header"] or "")
                if header in result:
                    continue
                parsed_row = self.latest_parsed_row(conn, str(row["id"]))
                parsed = json.loads(parsed_row["parsed_json"]) if parsed_row else {}
                report = self.latest_report(conn, str(row["id"]))
                link = self.latest_link(conn, str(row["id"]))
                attachments = self.attachment_rows(conn, str(row["id"]), str(parsed_row["id"] if parsed_row else ""))
                result[header] = {
                    "id": row["id"],
                    "quality_status": row["quality_status"],
                    "signature_status": row["signature_status"],
                    "linked_fascicolo_id": row["linked_fascicolo_id"],
                    "linked_fascicolo_score": row["linked_fascicolo_score"],
                    "fields": (parsed.get("fields") or {}),
                    "validation_report": report,
                    "fascicolo_link": link,
                    "attachments": attachments,
                }
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
        title = clean_text(proposal.get("title") or (parsed.get("headers") or {}).get("subject") or "Verifica PEC", 120)
        marker = f"PEC_AUDIT:{message_id}"
        try:
            from pct.scadenziario import GestioneScadenziario, TipoTermine

            manager = GestioneScadenziario(db_path=str(self.scadenziario_db_path))
            for existing in manager.tutte(solo_aperte=False):
                if marker in str(getattr(existing, "note", "") or ""):
                    return {
                        "ok": True,
                        "message": "Scadenza automatica già presente nello scadenziario.",
                        "deadline_id": getattr(existing, "id", ""),
                        "due_date": getattr(existing, "data_scadenza", target_date),
                        "already_exists": True,
                        "proposal": proposal,
                    }
            scadenza = manager.nuova(
                titolo=title,
                tipo=TipoTermine.ADEMPIMENTO,
                data_scadenza=target_date,
                id_fascicolo=str(message.get("linked_fascicolo_id") or ""),
                descrizione=clean_text(proposal.get("reason")) or "Scadenza generata automaticamente dalla pipeline PEC audit-grade.",
                note=(
                    f"{marker}\n"
                    f"Tipo evento: {proposal.get('source_event_type') or report.get('event_type') or '-'}\n"
                    f"Decorrenza letta: {proposal.get('source_event_at') or '-'}\n"
                    "Termine legale conclusivo: no, presidio operativo automatico da verificare professionalmente."
                ),
                id_utente_responsabile=actor,
                source_event_type=str(proposal.get("source_event_type") or report.get("event_type") or ""),
                source_event_at=str(proposal.get("source_event_at") or ""),
                operational_due_at=target_date,
                deadline_profile_code="PEC_AUTO_PRESIDIO",
            )
        except Exception as exc:
            return {"ok": False, "message": f"Scadenza non creata: {exc}"}
        with self.connect() as conn:
            self.append_audit(conn, action="pec.deadline.scheduled", resource_type="pec_message", resource_id=message_id, payload={"deadline_id": getattr(scadenza, "id", ""), "due_date": target_date, "proposal": proposal}, actor=actor)
        return {"ok": True, "message": "Scadenza automatica creata nello scadenziario.", "deadline_id": getattr(scadenza, "id", ""), "due_date": target_date, "proposal": proposal}


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
