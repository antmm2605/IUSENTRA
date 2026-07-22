"""PEC Control Tower: eventi giuridici, scadenze e prove interrogabili da Lex.

Il modulo lavora solo su MIME PEC gia' disponibili nel runtime tenant-aware.
Non invia PEC, non conferma termini legali e non sostituisce la revisione
dell'avvocato: prepara evidenze operative tracciate e verificabili.
"""

from __future__ import annotations

import hashlib
import hmac
from email import message_from_bytes
from email.message import EmailMessage, Message
from email.policy import default as email_policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import re
import sqlite3
from time import monotonic
import uuid
import zipfile
from typing import Any
from xml.etree import ElementTree

try:  # pragma: no cover - zoneinfo è sempre disponibile sulle versioni supportate
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]


ROME_TZ = ZoneInfo("Europe/Rome") if ZoneInfo is not None else timezone(timedelta(hours=1))
SCHEMA_VERSION = "2026-06-06.1"


SQLITE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS legal_communications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    account_email TEXT NOT NULL DEFAULT '',
    folder TEXT NOT NULL DEFAULT '',
    message_id_header TEXT NOT NULL DEFAULT '',
    original_message_id TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    sender TEXT NOT NULL DEFAULT '',
    recipients_json TEXT NOT NULL DEFAULT '[]',
    received_at TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT '',
    mime_sha256 TEXT NOT NULL,
    technical_type TEXT NOT NULL,
    legal_category TEXT NOT NULL,
    legal_event_type TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    confidence_label TEXT NOT NULL DEFAULT '',
    requires_human_confirmation INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'open',
    fascicolo_id TEXT NOT NULL DEFAULT '',
    fascicolo_score REAL NOT NULL DEFAULT 0,
    risk_level TEXT NOT NULL DEFAULT 'media',
    summary TEXT NOT NULL DEFAULT '',
    extracted_json TEXT NOT NULL DEFAULT '{}',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    source_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, mime_sha256)
);

CREATE TABLE IF NOT EXISTS legal_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    risk_level TEXT NOT NULL DEFAULT 'media',
    event_at TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    extracted_json TEXT NOT NULL DEFAULT '{}',
    expected_documents_json TEXT NOT NULL DEFAULT '[]',
    produced_documents_json TEXT NOT NULL DEFAULT '[]',
    missing_documents_json TEXT NOT NULL DEFAULT '[]',
    legal_articles_json TEXT NOT NULL DEFAULT '[]',
    suggested_actions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pec_receipt_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL,
    role TEXT NOT NULL,
    referred_message_id TEXT NOT NULL DEFAULT '',
    receipt_type TEXT NOT NULL DEFAULT '',
    recipient TEXT NOT NULL DEFAULT '',
    receipt_at TEXT NOT NULL DEFAULT '',
    daticert_sha256 TEXT NOT NULL DEFAULT '',
    daticert_json TEXT NOT NULL DEFAULT '{}',
    proof_status TEXT NOT NULL DEFAULT 'partial',
    created_at TEXT NOT NULL,
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_deadlines (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    rule_code TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    title TEXT NOT NULL,
    due_at TEXT NOT NULL,
    source_event_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft_pending_confirmation',
    risk_level TEXT NOT NULL DEFAULT 'media',
    confidence REAL NOT NULL DEFAULT 0,
    requires_human_confirmation INTEGER NOT NULL DEFAULT 1,
    confirmed_at TEXT NOT NULL DEFAULT '',
    confirmed_by TEXT NOT NULL DEFAULT '',
    confirmation_rule TEXT NOT NULL DEFAULT '',
    calculation_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES legal_events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agenda_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    source TEXT NOT NULL DEFAULT 'pec_control_tower',
    created_at TEXT NOT NULL,
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES legal_events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_event_tasks (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'media',
    due_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES legal_events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notification_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    communication_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL DEFAULT 'outbound',
    recipient TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT 'PEC',
    title TEXT NOT NULL,
    draft_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft_pending_confirmation',
    risk_level TEXT NOT NULL DEFAULT 'media',
    requires_human_confirmation INTEGER NOT NULL DEFAULT 1,
    approved_at TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    sent_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES legal_events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notification_recipients (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    notification_id TEXT NOT NULL,
    communication_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    registry_source TEXT NOT NULL DEFAULT '',
    registry_status TEXT NOT NULL DEFAULT 'not_checked',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    FOREIGN KEY (notification_id) REFERENCES notification_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS registry_lookups (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL DEFAULT '',
    recipient_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    registry TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'not_checked',
    confidence REAL NOT NULL DEFAULT 0,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_proofs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    notification_id TEXT NOT NULL DEFAULT '',
    communication_id TEXT NOT NULL,
    proof_type TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'partial',
    created_at TEXT NOT NULL,
    FOREIGN KEY (communication_id) REFERENCES legal_communications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_rule_versions (
    code TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    legal_basis_json TEXT NOT NULL DEFAULT '[]',
    deadline_days INTEGER NOT NULL DEFAULT 0,
    calendar_mode TEXT NOT NULL DEFAULT 'calendar',
    requires_confirmation INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY (code, version)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    previous_hash TEXT NOT NULL DEFAULT '',
    event_hash TEXT NOT NULL,
    key_hint TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_legal_communications_tenant_received
    ON legal_communications (tenant_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_legal_communications_event_received
    ON legal_communications (tenant_id, legal_event_type, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_legal_communications_event_received_prefix
    ON legal_communications (tenant_id, legal_event_type, substr(received_at, 1, 19));
CREATE INDEX IF NOT EXISTS idx_legal_communications_category
    ON legal_communications (tenant_id, legal_category, status);
CREATE INDEX IF NOT EXISTS idx_legal_deadlines_status
    ON legal_deadlines (tenant_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_notification_jobs_status
    ON notification_jobs (tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_referred
    ON pec_receipt_events (tenant_id, referred_message_id, role);
"""


RULE_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "code": "PEC_CANCELLERIA_REVIEW_1D",
        "version": "2026-06-06",
        "description": "Presidio operativo entro un giorno per comunicazioni da cancelleria o provvedimenti.",
        "legal_basis": ["D.L. 179/2012 e regole tecniche PCT da verificare sul caso concreto"],
        "deadline_days": 1,
    },
    {
        "code": "PEC_PA_RISCONTRO_TERMINE_ESPRESSO",
        "version": "2026-06-06",
        "description": "Riscontro a comunicazione PA solo se dal testo emerge un termine espresso.",
        "legal_basis": ["Termine espresso nella comunicazione; disciplina specifica da confermare"],
        "deadline_days": 0,
    },
    {
        "code": "PEC_DIFFIDA_TERMINE_ESPRESSO",
        "version": "2026-06-06",
        "description": "Presidio su diffida o messa in mora con termine espresso o revisione rapida.",
        "legal_basis": ["Contenuto della diffida; norme sostanziali da confermare"],
        "deadline_days": 1,
    },
    {
        "code": "PEC_OUTBOUND_RECEIPT_MONITOR",
        "version": "2026-06-06",
        "description": "Controllo ricevuta di consegna dopo ricevuta di accettazione PEC.",
        "legal_basis": ["DPR 68/2005", "CAD art. 48", "DM PEC 2 novembre 2005"],
        "deadline_days": 1,
    },
    {
        "code": "PEC_FAILED_DELIVERY_REMEDIATION",
        "version": "2026-06-06",
        "description": "Rimessione immediata in revisione di mancata consegna o notifica fallita.",
        "legal_basis": ["DPR 68/2005", "Legge 53/1994 se notifica in proprio"],
        "deadline_days": 0,
    },
    {
        "code": "PEC_UNKNOWN_REVIEW_1D",
        "version": "2026-06-06",
        "description": "Revisione professionale rapida per PEC giuridicamente non classificate con certezza.",
        "legal_basis": ["Regola interna prudenziale IUSENTRA"],
        "deadline_days": 1,
    },
)


EXPECTED_DOCUMENTS: dict[str, list[str]] = {
    "CANCELLERIA_PCT": ["comunicazione di cancelleria", "provvedimento allegato", "busta o ricevuta PEC"],
    "PROVVEDIMENTO_GIUDIZIARIO": ["provvedimento", "relazione di cancelleria o comunicazione", "allegati ufficiali"],
    "NOTIFICA_CONTROPARTE": ["atto da notificare", "relata", "procura se necessaria", "ricevuta di accettazione", "ricevuta di consegna"],
    "ATTO_AMMINISTRATIVO_PA": ["provvedimento o richiesta PA", "protocollo", "allegati richiamati", "bozza di riscontro"],
    "ENTE_RICHIESTA_RISCONTRO": ["richiesta ente", "documenti richiesti", "bozza risposta"],
    "ATTO_TRIBUTARIO_RISCOSSIONE": ["atto ricevuto", "notifica", "estratto ruolo o allegati", "prova data ricezione"],
    "DIFFIDA_MESSA_IN_MORA": ["diffida", "documenti richiamati", "bozza risposta", "prova ricezione"],
    "CONTRATTO_DISDETTA_RECESSO": ["contratto", "disdetta o recesso", "prova ricezione", "bozza risposta"],
    "CLIENTE_DOCUMENTI": ["documenti ricevuti", "richiesta cliente", "istruzioni operative"],
    "PEC_OUTBOUND_PROOF": ["MIME inviato", "ricevuta di accettazione", "ricevuta di consegna", "daticert.xml"],
    "UNKNOWN_LEGAL_RISK": ["MIME originale", "allegati", "classificazione avvocato"],
}


LEGAL_ARTICLES: dict[str, list[str]] = {
    "CANCELLERIA_PCT": ["D.L. 179/2012", "regole tecniche PCT applicabili al registro da verificare"],
    "PROVVEDIMENTO_GIUDIZIARIO": ["codice di rito applicabile al provvedimento", "termini di impugnazione da confermare"],
    "NOTIFICA_CONTROPARTE": ["Legge 53/1994", "DPR 68/2005", "CAD art. 48"],
    "ATTO_AMMINISTRATIVO_PA": ["norma del procedimento indicata nell'atto", "termine espresso da verificare"],
    "ENTE_RICHIESTA_RISCONTRO": ["norma del procedimento indicata nella richiesta"],
    "ATTO_TRIBUTARIO_RISCOSSIONE": ["disciplina tributaria dell'atto ricevuto da verificare"],
    "DIFFIDA_MESSA_IN_MORA": ["artt. 1219 e 1454 c.c. se pertinenti al caso"],
    "CONTRATTO_DISDETTA_RECESSO": ["contratto e disciplina speciale di settore da verificare"],
    "CLIENTE_DOCUMENTI": ["incarico professionale e istruzioni del cliente"],
    "PEC_OUTBOUND_PROOF": ["DPR 68/2005", "CAD art. 48", "DM PEC 2 novembre 2005"],
    "UNKNOWN_LEGAL_RISK": ["normativa da individuare dopo classificazione professionale"],
}


QUESTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deadlines_today", ("pec", "ricevute", "oggi", "scaden")),
    ("notifications_to_do", ("notific", "enti", "contropart")),
    ("outbound_without_delivery", ("pec", "inviate", "consegna")),
    ("unconfirmed_terms", ("termin", "calcolat", "confermat")),
    ("court_registry_acts", ("atti", "cancelleria")),
    ("pa_reply_required", ("comunicazioni", "pa", "risposta")),
    ("failed_notifications", ("notific", "fallit")),
    ("complete_proof", ("prova", "completa")),
    ("confirmed_deadlines", ("chi", "confermato", "regola")),
    ("forfeiture_risk", ("fascicolo", "rischia", "decaden")),
    ("case_workplan", ("cosa", "manca")),
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def now_rome_date() -> date:
    return datetime.now(ROME_TZ).date()


def build_synthetic_pec_eml(
    *,
    subject: str,
    body: str,
    sender: str = "cancelleria@giustiziacert.it",
    to: str = "studio@example.pec.it",
    message_id: str = "",
    dt: datetime | None = None,
    headers: dict[str, str] | None = None,
    attachments: dict[str, bytes | str] | None = None,
) -> bytes:
    """Genera un MIME PEC sintetico per test locali e script di audit."""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = (dt or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    msg["Message-ID"] = message_id or f"<{uuid.uuid4().hex}@iusentra.test>"
    for key, value in (headers or {}).items():
        msg[key] = value
    msg.set_content(body, subtype="plain", charset="utf-8")
    for filename, content in (attachments or {}).items():
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        maintype, subtype = ("application", "octet-stream")
        if filename.lower().endswith(".xml"):
            maintype, subtype = ("application", "xml")
        if filename.lower().endswith(".txt"):
            maintype, subtype = ("text", "plain")
        msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=filename)
    return msg.as_bytes(policy=email_policy)


class PecControlTowerRepository:
    """Repository tenant-aware per trasformare PEC in eventi giuridici tracciati."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        tenant_id: str = "default",
        fascicoli_db_path: str | Path = "",
        fascicoli_docs_path: str | Path = "",
        scadenziario_db_path: str | Path = "",
        agenda_db_path: str | Path = "",
        audit_secret: str | bytes | None = None,
        fascicoli_rows: list[Any] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tenant_id = _clean(tenant_id) or "default"
        self.fascicoli_db_path = Path(fascicoli_db_path) if str(fascicoli_db_path or "").strip() else None
        self.fascicoli_docs_path = Path(fascicoli_docs_path) if str(fascicoli_docs_path or "").strip() else None
        self.scadenziario_db_path = Path(scadenziario_db_path) if str(scadenziario_db_path or "").strip() else None
        self.agenda_db_path = Path(agenda_db_path) if str(agenda_db_path or "").strip() else None
        self.audit_secret = audit_secret
        self._fascicoli_rows = list(fascicoli_rows or [])
        self._ensure_schema()

    def ingest_eml(
        self,
        raw_mime: bytes,
        *,
        account_email: str = "",
        folder: str = "INBOX",
        actor: str = "pec-control-tower",
    ) -> dict[str, Any]:
        if not raw_mime:
            raise ValueError("MIME PEC mancante.")
        parsed = parse_pec_mime(raw_mime)
        mime_sha256 = _sha256(raw_mime)
        existing = self.find_by_mime_sha256(mime_sha256)
        if existing:
            return {"ok": True, "duplicate": True, "data": existing}
        communication_id = _new_id("lcom")
        event_id = _new_id("levt")
        created_at = now_utc_iso()
        technical = classify_technical(parsed)
        legal = classify_legal(parsed, technical)
        matter = self.match_fascicolo(parsed, legal)
        event_at = parsed.get("received_at") or created_at
        received_at = event_at
        expected_docs = EXPECTED_DOCUMENTS.get(legal["legal_category"], EXPECTED_DOCUMENTS["UNKNOWN_LEGAL_RISK"])
        produced_docs = _produced_documents(parsed)
        missing_docs = _missing_documents(expected_docs, produced_docs)
        legal_articles = LEGAL_ARTICLES.get(legal["legal_category"], LEGAL_ARTICLES["UNKNOWN_LEGAL_RISK"])
        suggested_actions = _suggested_actions(legal, missing_docs, matter)
        extracted = {
            **dict(parsed.get("extracted") or {}),
            "registri": _extract_rg_refs(parsed.get("search_text") or ""),
            "termine_espresso": _extract_explicit_deadline(parsed.get("search_text") or "", event_at),
            "fascicolo_match": matter,
        }
        evidence = {
            "mime_sha256": mime_sha256,
            "attachments": parsed.get("attachments") or [],
            "daticert": parsed.get("daticert") or {},
            "headers": parsed.get("headers") or {},
        }
        source = {
            "parser": "pct.pec_control_tower",
            "schema_version": SCHEMA_VERSION,
            "account_email": account_email,
            "folder": folder,
        }
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO legal_communications
                (id, tenant_id, direction, account_email, folder, message_id_header, original_message_id,
                 subject, sender, recipients_json, received_at, sent_at, mime_sha256, technical_type,
                 legal_category, legal_event_type, confidence, confidence_label, requires_human_confirmation,
                 status, fascicolo_id, fascicolo_score, risk_level, summary, extracted_json, evidence_json,
                 source_json, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    communication_id,
                    self.tenant_id,
                    technical["direction"],
                    _clean(account_email),
                    _clean(folder),
                    parsed.get("message_id") or "",
                    technical.get("referred_message_id") or "",
                    parsed.get("subject") or "",
                    parsed.get("sender") or "",
                    _json(parsed.get("recipients") or []),
                    received_at,
                    parsed.get("sent_at") or "",
                    mime_sha256,
                    technical["technical_type"],
                    legal["legal_category"],
                    legal["legal_event_type"],
                    float(legal["confidence"]),
                    legal["confidence_label"],
                    1 if legal["requires_human_confirmation"] else 0,
                    "open",
                    matter.get("fascicolo_id") or "",
                    float(matter.get("score") or 0),
                    legal["risk_level"],
                    legal["summary"],
                    _json(extracted),
                    _json(evidence),
                    _json(source),
                    created_at,
                    created_at,
                ),
            )
            con.execute(
                """
                INSERT INTO legal_events
                (id, tenant_id, communication_id, event_type, label, status, risk_level, event_at,
                 fascicolo_id, extracted_json, expected_documents_json, produced_documents_json,
                 missing_documents_json, legal_articles_json, suggested_actions_json, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event_id,
                    self.tenant_id,
                    communication_id,
                    legal["legal_event_type"],
                    legal["label"],
                    "open",
                    legal["risk_level"],
                    event_at,
                    matter.get("fascicolo_id") or "",
                    _json(extracted),
                    _json(expected_docs),
                    _json(produced_docs),
                    _json(missing_docs),
                    _json(legal_articles),
                    _json(suggested_actions),
                    created_at,
                ),
            )
            self._insert_receipts(con, communication_id, technical, parsed, created_at)
            deadline = self._insert_deadline_if_needed(con, communication_id, event_id, legal, extracted, event_at, matter, created_at)
            if deadline:
                self._insert_agenda(con, communication_id, event_id, deadline, matter, created_at)
            self._insert_tasks(con, communication_id, event_id, legal, missing_docs, matter, deadline, created_at)
            self._insert_notification_if_needed(con, communication_id, event_id, legal, technical, parsed, matter, created_at)
            self._append_audit(
                con,
                entity_type="legal_communication",
                entity_id=communication_id,
                action="ingest_pec_event",
                actor=actor,
                payload={"technical_type": technical["technical_type"], "legal_category": legal["legal_category"]},
            )
        self._sync_json_managers(communication_id, actor=actor)
        return {"ok": True, "duplicate": False, "data": self.get_communication(communication_id)}

    def backfill_from_email_archive(
        self,
        email_manager: Any,
        *,
        limit: int = 1500,
        actor: str = "pec-control-tower-backfill",
        max_seconds: float = 0.0,
    ) -> dict[str, Any]:
        """Alimenta la Control Tower dai MIME PEC gia' salvati nella casella locale."""

        max_items = max(1, int(limit or 1500))
        started_at = monotonic()
        report: dict[str, Any] = {
            "ok": True,
            "scanned": 0,
            "relevant": 0,
            "processed": 0,
            "ingested": 0,
            "duplicates": 0,
            "skipped_not_pec": 0,
            "skipped_missing_mime": 0,
            "limit_reached": False,
            "time_budget_reached": False,
            "categories": {},
            "sample_ids": [],
            "errors": [],
        }
        try:
            rows = sorted(_email_archive_rows(email_manager), key=_email_archive_sort_key, reverse=True)
        except Exception as exc:
            report["ok"] = False
            report["errors"].append({"email_id": "archive", "errore": f"Archivio PEC non leggibile: {exc}"[:180]})
            return report

        for email_obj in rows:
            if max_seconds and monotonic() - started_at >= float(max_seconds):
                report["time_budget_reached"] = True
                break
            report["scanned"] += 1
            email_id = _email_archive_id(email_obj)
            if not email_relevant_for_pec_control(email_obj):
                report["skipped_not_pec"] += 1
                continue
            report["relevant"] += 1
            if report["processed"] >= max_items:
                report["limit_reached"] = True
                break
            raw_mime = _read_email_archive_mime(email_manager, email_obj)
            if not raw_mime:
                raw_mime = _reconstruct_email_archive_mime(email_manager, email_obj)
            if not raw_mime:
                report["skipped_missing_mime"] += 1
                continue
            report["processed"] += 1
            try:
                result = self.ingest_eml(
                    raw_mime,
                    account_email=_email_archive_account(email_obj),
                    folder=_clean(getattr(email_obj, "cartella", "") or "INBOX"),
                    actor=actor,
                )
            except Exception as exc:
                report["errors"].append({"email_id": email_id, "errore": str(exc)[:180]})
                continue
            communication = result.get("data") if isinstance(result.get("data"), dict) else {}
            category = _clean(communication.get("legal_category"))
            if category:
                categories = report["categories"]
                categories[category] = int(categories.get(category) or 0) + 1
            if result.get("duplicate"):
                report["duplicates"] += 1
            else:
                report["ingested"] += 1
            if len(report["sample_ids"]) < 20 and communication.get("id"):
                report["sample_ids"].append(
                    {
                        "email_id": email_id,
                        "communication_id": communication["id"],
                        "category": category,
                        "subject": _clean(communication.get("subject"))[:160],
                    }
                )
        return report

    def find_by_mime_sha256(self, mime_sha256: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT id FROM legal_communications WHERE tenant_id=? AND mime_sha256=?",
                (self.tenant_id, mime_sha256),
            ).fetchone()
        return self.get_communication(str(row["id"])) if row else None

    def list_communications(self, *, limit: int = 100, query: str = "", legal_category: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM legal_communications WHERE tenant_id=?"
        args: list[Any] = [self.tenant_id]
        if legal_category:
            sql += " AND legal_category=?"
            args.append(legal_category)
        if _clean(query):
            sql += " AND (subject LIKE ? OR sender LIKE ? OR summary LIKE ? OR fascicolo_id LIKE ?)"
            needle = f"%{_clean(query)}%"
            args.extend([needle, needle, needle, needle])
        sql += " ORDER BY received_at DESC LIMIT ?"
        args.append(max(1, int(limit or 100)))
        with self._connect() as con:
            rows = [self._communication_from_row(con, row) for row in con.execute(sql, args).fetchall()]
        return rows

    def get_communication(self, communication_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM legal_communications WHERE tenant_id=? AND id=?",
                (self.tenant_id, communication_id),
            ).fetchone()
            if row is None:
                raise KeyError(communication_id)
            return self._communication_from_row(con, row)

    def confirm_communication(self, communication_id: str, *, actor: str, status: str = "confirmed") -> dict[str, Any]:
        updated_at = now_utc_iso()
        with self._connect() as con:
            con.execute(
                """
                UPDATE legal_communications
                SET status=?, requires_human_confirmation=0, updated_at=?
                WHERE tenant_id=? AND id=?
                """,
                (status, updated_at, self.tenant_id, communication_id),
            )
            self._append_audit(
                con,
                entity_type="legal_communication",
                entity_id=communication_id,
                action="confirm_classification",
                actor=actor,
                payload={"status": status},
            )
        return self.get_communication(communication_id)

    def list_deadlines(self, *, status: str = "", limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM legal_deadlines WHERE tenant_id=?"
        args: list[Any] = [self.tenant_id]
        if status:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY due_at ASC LIMIT ?"
        args.append(max(1, int(limit or 100)))
        with self._connect() as con:
            return [_deadline_from_row(row) for row in con.execute(sql, args).fetchall()]

    def confirm_deadline(
        self,
        deadline_id: str,
        *,
        actor: str,
        confirmation_rule: str,
        due_at: str | None = None,
    ) -> dict[str, Any]:
        confirmed_at = now_utc_iso()
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM legal_deadlines WHERE tenant_id=? AND id=?",
                (self.tenant_id, deadline_id),
            ).fetchone()
            if row is None:
                raise KeyError(deadline_id)
            final_due = _clean(due_at) or row["due_at"]
            con.execute(
                """
                UPDATE legal_deadlines
                SET due_at=?, status='confirmed', requires_human_confirmation=0,
                    confirmed_at=?, confirmed_by=?, confirmation_rule=?
                WHERE tenant_id=? AND id=?
                """,
                (final_due, confirmed_at, actor, confirmation_rule, self.tenant_id, deadline_id),
            )
            self._append_audit(
                con,
                entity_type="legal_deadline",
                entity_id=deadline_id,
                action="confirm_deadline",
                actor=actor,
                payload={"due_at": final_due, "confirmation_rule": confirmation_rule},
            )
        return next(row for row in self.list_deadlines(limit=500) if row["id"] == deadline_id)

    def list_agenda(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM agenda_events WHERE tenant_id=? ORDER BY start_at ASC LIMIT ?",
                (self.tenant_id, max(1, int(limit or 100))),
            ).fetchall()
        return [_agenda_from_row(row) for row in rows]

    def draft_notification(
        self,
        communication_id: str,
        *,
        recipient: str,
        title: str = "",
        draft_text: str = "",
        actor: str = "pec-control-tower",
    ) -> dict[str, Any]:
        communication = self.get_communication(communication_id)
        event_id = str((communication.get("events") or [{}])[0].get("id") or "")
        now = now_utc_iso()
        notification_id = _new_id("njob")
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO notification_jobs
                (id, tenant_id, communication_id, event_id, matter_id, recipient, title, draft_text,
                 status, risk_level, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    notification_id,
                    self.tenant_id,
                    communication_id,
                    event_id,
                    communication.get("fascicolo_id") or "",
                    recipient,
                    title or f"Bozza riscontro PEC: {communication.get('subject') or 'comunicazione'}",
                    draft_text,
                    "draft_pending_confirmation",
                    communication.get("risk_level") or "media",
                    now,
                    now,
                ),
            )
            self._append_audit(
                con,
                entity_type="notification_job",
                entity_id=notification_id,
                action="draft_notification",
                actor=actor,
                payload={"communication_id": communication_id, "recipient": recipient},
            )
        return self.get_notification(notification_id)

    def approve_notification(self, notification_id: str, *, actor: str) -> dict[str, Any]:
        now = now_utc_iso()
        with self._connect() as con:
            con.execute(
                """
                UPDATE notification_jobs
                SET status='approved_manual_send_required', approved_at=?, approved_by=?, updated_at=?
                WHERE tenant_id=? AND id=?
                """,
                (now, actor, now, self.tenant_id, notification_id),
            )
            self._append_audit(
                con,
                entity_type="notification_job",
                entity_id=notification_id,
                action="approve_notification_draft",
                actor=actor,
                payload={"send_policy": "manual_or_dedicated_mailbox_only"},
            )
        return self.get_notification(notification_id)

    def record_manual_send(
        self,
        notification_id: str,
        *,
        actor: str,
        sent_at: str = "",
        proof_sha256: str = "",
        proof_filename: str = "",
    ) -> dict[str, Any]:
        now = now_utc_iso()
        final_sent_at = _clean(sent_at) or now
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM notification_jobs WHERE tenant_id=? AND id=?",
                (self.tenant_id, notification_id),
            ).fetchone()
            if row is None:
                raise KeyError(notification_id)
            con.execute(
                """
                UPDATE notification_jobs
                SET status='sent_manually_waiting_receipts', sent_at=?, updated_at=?
                WHERE tenant_id=? AND id=?
                """,
                (final_sent_at, now, self.tenant_id, notification_id),
            )
            if proof_sha256 or proof_filename:
                con.execute(
                    """
                    INSERT INTO notification_proofs
                    (id, tenant_id, notification_id, communication_id, proof_type, role, sha256,
                     filename, evidence_json, status, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        _new_id("nprf"),
                        self.tenant_id,
                        notification_id,
                        row["communication_id"],
                        "manual_send",
                        "send_evidence",
                        proof_sha256,
                        proof_filename,
                        _json({"registered_by": actor, "registered_at": now}),
                        "partial",
                        now,
                    ),
                )
            self._append_audit(
                con,
                entity_type="notification_job",
                entity_id=notification_id,
                action="record_manual_send",
                actor=actor,
                payload={"sent_at": final_sent_at, "proof_filename": proof_filename},
            )
        return self.get_notification(notification_id)

    def get_notification(self, notification_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM notification_jobs WHERE tenant_id=? AND id=?",
                (self.tenant_id, notification_id),
            ).fetchone()
            if row is None:
                raise KeyError(notification_id)
            return self._notification_from_row(con, row)

    def list_notifications(self, *, status: str = "", limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM notification_jobs WHERE tenant_id=?"
        args: list[Any] = [self.tenant_id]
        if status:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY rowid DESC LIMIT ?"
        args.append(max(1, int(limit or 100)))
        with self._connect() as con:
            return [self._notification_from_row(con, row) for row in con.execute(sql, args).fetchall()]

    def get_notification_proofs(self, notification_id: str) -> dict[str, Any]:
        notification = self.get_notification(notification_id)
        proofs = notification.get("proofs") or []
        roles = {str(row.get("role") or "") for row in proofs}
        complete = {"acceptance", "delivery"}.issubset(roles)
        return {
            "notification": notification,
            "proofs": proofs,
            "proof_complete": complete,
            "missing_roles": sorted({"acceptance", "delivery"} - roles),
        }

    def list_audit(self, *, matter_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM audit_events WHERE tenant_id=?"
        args: list[Any] = [self.tenant_id]
        if matter_id:
            ids = [
                row["id"]
                for row in self._connect().execute(
                    "SELECT id FROM legal_communications WHERE tenant_id=? AND fascicolo_id=?",
                    (self.tenant_id, matter_id),
                ).fetchall()
            ]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                sql += f" AND entity_id IN ({placeholders})"
                args.extend(ids)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, int(limit or 100)))
        with self._connect() as con:
            return [_audit_from_row(row) for row in con.execute(sql, args).fetchall()]

    def export_ics(self) -> str:
        rows = self.list_agenda(limit=1000)
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//IUSENTRA//PEC Control Tower//IT"]
        for row in rows:
            start = _parse_dt(row.get("start_at")) or datetime.now(timezone.utc)
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{row.get('id')}@iusentra",
                    f"DTSTAMP:{_ics_dt(datetime.now(timezone.utc))}",
                    f"DTSTART:{_ics_dt(start)}",
                    f"SUMMARY:{_ics_escape(row.get('title'))}",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    def answer_question(self, question: str, *, limit: int = 20) -> dict[str, Any]:
        kind = _question_kind(question)
        with self._connect() as con:
            if kind == "deadlines_today":
                today_rome = now_rome_date()
                candidates = [
                    self._communication_from_row(con, row)
                    for row in con.execute(
                        """
                        SELECT DISTINCT c.* FROM legal_communications c
                        JOIN legal_deadlines d ON d.communication_id=c.id
                        WHERE c.tenant_id=?
                        ORDER BY c.received_at DESC LIMIT ?
                        """,
                        (self.tenant_id, max(50, int(limit or 20) * 8)),
                    ).fetchall()
                ]
                items = [
                    row
                    for row in candidates
                    if (_parse_dt(row.get("received_at")) or datetime.now(timezone.utc)).astimezone(ROME_TZ).date() == today_rome
                ][:limit]
                summary = f"PEC ricevute oggi con scadenze generate: {len(items)}."
            elif kind == "notifications_to_do":
                items = [
                    self._notification_from_row(con, row)
                    for row in con.execute(
                        """
                        SELECT * FROM notification_jobs
                        WHERE tenant_id=? AND status IN (
                            'draft_pending_confirmation',
                            'approved_manual_send_required',
                            'waiting_delivery',
                            'failed_review_required'
                        )
                        ORDER BY risk_level DESC, created_at DESC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                summary = f"Notifiche o riscontri da preparare o presidiare: {len(items)}."
            elif kind == "outbound_without_delivery":
                items = self._outbound_without_delivery(con, limit=limit)
                summary = f"PEC inviate con accettazione ma senza consegna collegata: {len(items)}."
            elif kind == "unconfirmed_terms":
                items = [
                    _deadline_from_row(row)
                    for row in con.execute(
                        """
                        SELECT * FROM legal_deadlines
                        WHERE tenant_id=? AND requires_human_confirmation=1
                        ORDER BY due_at ASC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                summary = f"Termini calcolati ma non confermati: {len(items)}."
            elif kind == "court_registry_acts":
                items = [
                    self._communication_from_row(con, row)
                    for row in con.execute(
                        """
                        SELECT * FROM legal_communications
                        WHERE tenant_id=? AND legal_category IN ('CANCELLERIA_PCT','PROVVEDIMENTO_GIUDIZIARIO')
                        ORDER BY received_at DESC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                summary = f"Atti o comunicazioni da cancelleria individuati: {len(items)}."
            elif kind == "pa_reply_required":
                items = [
                    self._communication_from_row(con, row)
                    for row in con.execute(
                        """
                        SELECT * FROM legal_communications
                        WHERE tenant_id=? AND legal_category IN ('ATTO_AMMINISTRATIVO_PA','ENTE_RICHIESTA_RISCONTRO')
                        ORDER BY received_at DESC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                summary = f"Comunicazioni PA o enti con possibile risposta: {len(items)}."
            elif kind == "failed_notifications":
                receipts = [
                    _receipt_from_row(row)
                    for row in con.execute(
                        """
                        SELECT * FROM pec_receipt_events
                        WHERE tenant_id=? AND role='failed_delivery'
                        ORDER BY created_at DESC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                jobs = [
                    self._notification_from_row(con, row)
                    for row in con.execute(
                        """
                        SELECT * FROM notification_jobs
                        WHERE tenant_id=? AND status='failed_review_required'
                        ORDER BY created_at DESC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                items = jobs + receipts
                summary = f"Notifiche fallite o da rimediare: {len(items)}."
            elif kind == "complete_proof":
                items = self._receipt_proof_bundles(con, limit=limit)
                complete_count = sum(1 for item in items if item.get("proof_complete"))
                summary = f"Fascicoli prova notifica ricostruiti: {len(items)} ({complete_count} completi)."
            elif kind == "confirmed_deadlines":
                items = [
                    _deadline_from_row(row)
                    for row in con.execute(
                        """
                        SELECT * FROM legal_deadlines
                        WHERE tenant_id=? AND confirmed_at<>''
                        ORDER BY confirmed_at DESC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                summary = f"Scadenze confermate con autore e regola: {len(items)}."
            elif kind == "forfeiture_risk":
                items = [
                    _deadline_from_row(row)
                    for row in con.execute(
                        """
                        SELECT * FROM legal_deadlines
                        WHERE tenant_id=? AND status<>'confirmed' AND risk_level IN ('alta','critica')
                        ORDER BY due_at ASC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                summary = f"Fascicoli con rischio operativo di decadenza da verificare: {len(items)}."
            elif kind == "case_workplan":
                items = [
                    self._communication_from_row(con, row)
                    for row in con.execute(
                        """
                        SELECT * FROM legal_communications
                        WHERE tenant_id=? AND fascicolo_id<>''
                        ORDER BY received_at DESC LIMIT ?
                        """,
                        (self.tenant_id, limit),
                    ).fetchall()
                ]
                summary = f"Quadro operativo fascicoli alimentato da PEC: {len(items)}."
            else:
                items = self.list_communications(limit=limit)
                summary = f"Eventi giuridici PEC tracciati: {len(items)}."
        return {
            "id": f"pec-control-{kind}",
            "question": question,
            "answer_kind": kind,
            "summary": summary,
            "items": items,
            "coverage_gaps": _coverage_gaps_for(kind, items),
            "source": "pec_control_tower",
            "tenant_id": self.tenant_id,
            "generated_at": now_utc_iso(),
        }

    def verify_audit_chain(self) -> dict[str, Any]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM audit_events WHERE tenant_id=? ORDER BY rowid ASC",
                (self.tenant_id,),
            ).fetchall()
        previous = ""
        for row in rows:
            payload = {
                "tenant_id": row["tenant_id"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "action": row["action"],
                "actor": row["actor"],
                "payload_json": row["payload_json"],
                "created_at": row["created_at"],
                "previous_hash": previous,
            }
            expected = self._audit_hash(payload)
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                return {"ok": False, "count": len(rows), "broken_event_id": row["id"]}
            previous = row["event_hash"]
        return {"ok": True, "count": len(rows), "last_hash": previous}

    def _ensure_schema(self) -> None:
        with self._connect() as con:
            con.executescript(SQLITE_SCHEMA)
            for seed in RULE_SEEDS:
                con.execute(
                    """
                    INSERT OR IGNORE INTO legal_rule_versions
                    (code, version, description, legal_basis_json, deadline_days, calendar_mode,
                     requires_confirmation, active, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        seed["code"],
                        seed["version"],
                        seed["description"],
                        _json(seed["legal_basis"]),
                        int(seed["deadline_days"]),
                        "calendar",
                        1,
                        1,
                        now_utc_iso(),
                    ),
                )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def _communication_from_row(self, con: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_dict(row)
        for key in ("recipients_json", "extracted_json", "evidence_json", "source_json"):
            target = key.removesuffix("_json")
            payload[target] = _loads(payload.pop(key, "{}"))
        payload["requires_human_confirmation"] = bool(payload.get("requires_human_confirmation"))
        payload["events"] = [
            _event_from_row(event)
            for event in con.execute(
                "SELECT * FROM legal_events WHERE tenant_id=? AND communication_id=? ORDER BY created_at ASC",
                (self.tenant_id, payload["id"]),
            ).fetchall()
        ]
        payload["deadlines"] = [
            _deadline_from_row(deadline)
            for deadline in con.execute(
                "SELECT * FROM legal_deadlines WHERE tenant_id=? AND communication_id=? ORDER BY due_at ASC",
                (self.tenant_id, payload["id"]),
            ).fetchall()
        ]
        payload["tasks"] = [
            _task_from_row(task)
            for task in con.execute(
                "SELECT * FROM legal_event_tasks WHERE tenant_id=? AND communication_id=? ORDER BY created_at ASC",
                (self.tenant_id, payload["id"]),
            ).fetchall()
        ]
        payload["receipts"] = [
            _receipt_from_row(receipt)
            for receipt in con.execute(
                "SELECT * FROM pec_receipt_events WHERE tenant_id=? AND communication_id=? ORDER BY created_at ASC",
                (self.tenant_id, payload["id"]),
            ).fetchall()
        ]
        payload["notifications"] = [
            self._notification_from_row(con, notification)
            for notification in con.execute(
                "SELECT * FROM notification_jobs WHERE tenant_id=? AND communication_id=? ORDER BY created_at ASC",
                (self.tenant_id, payload["id"]),
            ).fetchall()
        ]
        payload["action_url"] = f"/email/?pec_control_tower={payload['id']}"
        return payload

    def _notification_from_row(self, con: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        payload = _row_dict(row)
        payload["requires_human_confirmation"] = bool(payload.get("requires_human_confirmation"))
        payload["recipients"] = [
            _row_dict(recipient)
            for recipient in con.execute(
                "SELECT * FROM notification_recipients WHERE tenant_id=? AND notification_id=?",
                (self.tenant_id, payload["id"]),
            ).fetchall()
        ]
        payload["proofs"] = [
            _proof_from_row(proof)
            for proof in con.execute(
                "SELECT * FROM notification_proofs WHERE tenant_id=? AND notification_id=?",
                (self.tenant_id, payload["id"]),
            ).fetchall()
        ]
        payload["action_url"] = f"/notifiche-legali?notification={payload['id']}"
        return payload

    def _insert_receipts(
        self,
        con: sqlite3.Connection,
        communication_id: str,
        technical: dict[str, Any],
        parsed: dict[str, Any],
        created_at: str,
    ) -> None:
        if not technical.get("receipt_role"):
            return
        daticert = dict(parsed.get("daticert") or {})
        receipt_id = _new_id("prec")
        con.execute(
            """
            INSERT INTO pec_receipt_events
            (id, tenant_id, communication_id, role, referred_message_id, receipt_type, recipient,
             receipt_at, daticert_sha256, daticert_json, proof_status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                receipt_id,
                self.tenant_id,
                communication_id,
                technical["receipt_role"],
                technical.get("referred_message_id") or daticert.get("msgid") or "",
                technical.get("receipt_type") or daticert.get("tipo") or "",
                daticert.get("destinatario") or _first_recipient(parsed),
                daticert.get("receipt_at") or parsed.get("received_at") or created_at,
                daticert.get("sha256") or "",
                _json(daticert),
                "complete" if technical["receipt_role"] == "delivery" else "failed" if technical["receipt_role"] == "failed_delivery" else "partial",
                created_at,
            ),
        )
        con.execute(
            """
            INSERT INTO notification_proofs
            (id, tenant_id, notification_id, communication_id, proof_type, role, sha256, filename,
             evidence_json, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                _new_id("nprf"),
                self.tenant_id,
                "",
                communication_id,
                "pec_receipt",
                technical["receipt_role"],
                daticert.get("sha256") or parsed.get("mime_sha256") or "",
                "daticert.xml" if daticert else "messaggio.eml",
                _json({"technical_type": technical["technical_type"], "referred_message_id": technical.get("referred_message_id") or ""}),
                "complete" if technical["receipt_role"] == "delivery" else "failed" if technical["receipt_role"] == "failed_delivery" else "partial",
                created_at,
            ),
        )

    def _insert_deadline_if_needed(
        self,
        con: sqlite3.Connection,
        communication_id: str,
        event_id: str,
        legal: dict[str, Any],
        extracted: dict[str, Any],
        event_at: str,
        matter: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any] | None:
        rule = _deadline_rule(legal, extracted)
        if not rule:
            return None
        source_dt = _parse_dt(event_at) or datetime.now(timezone.utc)
        explicit = extracted.get("termine_espresso") if isinstance(extracted.get("termine_espresso"), dict) else {}
        if explicit.get("due_at"):
            due_at = explicit["due_at"]
        else:
            due_at = _add_days(source_dt, int(rule.get("deadline_days") or 0)).isoformat()
        deadline_id = _new_id("ldln")
        calculation = {
            "engine": "pec_control_tower",
            "rule_code": rule["code"],
            "rule_version": rule["version"],
            "legal_due_confirmed": False,
            "explicit_term": explicit,
            "source_event_at": event_at,
            "note": "Bozza operativa: conferma obbligatoria dell'avvocato prima di trattarla come termine legale.",
        }
        con.execute(
            """
            INSERT INTO legal_deadlines
            (id, tenant_id, communication_id, event_id, matter_id, rule_code, rule_version, title,
             due_at, source_event_at, status, risk_level, confidence, requires_human_confirmation,
             calculation_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                deadline_id,
                self.tenant_id,
                communication_id,
                event_id,
                matter.get("fascicolo_id") or "",
                rule["code"],
                rule["version"],
                _deadline_title(legal),
                due_at,
                event_at,
                "draft_pending_confirmation",
                legal.get("risk_level") or "media",
                float(legal.get("confidence") or 0),
                1,
                _json(calculation),
                created_at,
            ),
        )
        return {
            "id": deadline_id,
            "due_at": due_at,
            "title": _deadline_title(legal),
            "matter_id": matter.get("fascicolo_id") or "",
        }

    def _insert_agenda(
        self,
        con: sqlite3.Connection,
        communication_id: str,
        event_id: str,
        deadline: dict[str, Any],
        matter: dict[str, Any],
        created_at: str,
    ) -> None:
        con.execute(
            """
            INSERT INTO agenda_events
            (id, tenant_id, communication_id, event_id, matter_id, title, start_at, status, source, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                _new_id("aevt"),
                self.tenant_id,
                communication_id,
                event_id,
                matter.get("fascicolo_id") or "",
                deadline.get("title") or "Presidio PEC",
                deadline.get("due_at") or created_at,
                "draft",
                "pec_control_tower",
                created_at,
            ),
        )

    def _insert_tasks(
        self,
        con: sqlite3.Connection,
        communication_id: str,
        event_id: str,
        legal: dict[str, Any],
        missing_docs: list[str],
        matter: dict[str, Any],
        deadline: dict[str, Any] | None,
        created_at: str,
    ) -> None:
        task_rows = [
            {
                "title": legal["primary_task"],
                "task_type": "legal_review",
                "priority": legal["risk_level"],
                "due_at": (deadline or {}).get("due_at") or created_at,
            }
        ]
        if not matter.get("fascicolo_id"):
            task_rows.append(
                {
                    "title": "Associa la PEC al fascicolo corretto prima di chiudere il presidio.",
                    "task_type": "matter_match",
                    "priority": "alta",
                    "due_at": created_at,
                }
            )
        for missing in missing_docs[:5]:
            task_rows.append(
                {
                    "title": f"Verifica documento mancante: {missing}.",
                    "task_type": "missing_document",
                    "priority": "media",
                    "due_at": (deadline or {}).get("due_at") or "",
                }
            )
        for row in task_rows:
            con.execute(
                """
                INSERT INTO legal_event_tasks
                (id, tenant_id, communication_id, event_id, matter_id, title, task_type, status,
                 priority, due_at, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    _new_id("ltask"),
                    self.tenant_id,
                    communication_id,
                    event_id,
                    matter.get("fascicolo_id") or "",
                    row["title"],
                    row["task_type"],
                    "open",
                    row["priority"],
                    row["due_at"],
                    created_at,
                ),
            )

    def _insert_notification_if_needed(
        self,
        con: sqlite3.Connection,
        communication_id: str,
        event_id: str,
        legal: dict[str, Any],
        technical: dict[str, Any],
        parsed: dict[str, Any],
        matter: dict[str, Any],
        created_at: str,
    ) -> None:
        draft = _notification_draft(legal, technical, parsed)
        if not draft:
            return
        notification_id = _new_id("njob")
        status = "failed_review_required" if technical.get("receipt_role") == "failed_delivery" else "waiting_delivery" if technical.get("receipt_role") == "acceptance" else "draft_pending_confirmation"
        con.execute(
            """
            INSERT INTO notification_jobs
            (id, tenant_id, communication_id, event_id, matter_id, direction, recipient, channel,
             title, draft_text, status, risk_level, requires_human_confirmation, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                notification_id,
                self.tenant_id,
                communication_id,
                event_id,
                matter.get("fascicolo_id") or "",
                draft["direction"],
                draft["recipient"],
                "PEC",
                draft["title"],
                draft["draft_text"],
                status,
                legal.get("risk_level") or "media",
                1,
                created_at,
                created_at,
            ),
        )
        con.execute(
            """
            INSERT INTO notification_recipients
            (id, tenant_id, notification_id, communication_id, name, email, registry_source,
             registry_status, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                _new_id("nrcp"),
                self.tenant_id,
                notification_id,
                communication_id,
                draft.get("recipient_name") or "",
                draft["recipient"],
                draft.get("registry_source") or "",
                "not_checked",
                "pending",
                created_at,
            ),
        )
        con.execute(
            """
            UPDATE notification_proofs
            SET notification_id=?
            WHERE tenant_id=? AND communication_id=? AND notification_id=''
            """,
            (notification_id, self.tenant_id, communication_id),
        )

    def _sync_json_managers(self, communication_id: str, *, actor: str) -> None:
        communication = self.get_communication(communication_id)
        deadline = (communication.get("deadlines") or [None])[0]
        if deadline and self.scadenziario_db_path:
            try:
                from pct.scadenziario import GestioneScadenziario, TipoTermine

                manager = GestioneScadenziario(db_path=str(self.scadenziario_db_path))
                due_date = str(deadline["due_at"])[:10]
                matter_id = deadline.get("matter_id") or communication.get("fascicolo_id") or ""
                already_synced = False
                for row in manager.tutte(solo_aperte=False):
                    if getattr(row, "external_uid", "") == deadline["id"]:
                        already_synced = True
                        break
                    same_day = str(getattr(row, "data_scadenza", "") or "")[:10] == due_date
                    same_matter = not matter_id or not str(getattr(row, "id_fascicolo", "") or "") or str(getattr(row, "id_fascicolo", "") or "") == matter_id
                    pec_audit_marker = "PEC_AUDIT:" in str(getattr(row, "note", "") or "") or str(getattr(row, "deadline_profile_code", "") or "") == "PEC_AUTO_PRESIDIO"
                    if same_day and (same_matter or pec_audit_marker) and pec_audit_marker:
                        already_synced = True
                        break
                if not already_synced:
                    legal_event_type = communication.get("legal_event_type") or "pec"
                    summary = _clean(communication.get("summary") or "", 700)
                    task = _clean(deadline.get("title") or communication.get("summary") or "", 700)
                    description = summary or "Presidio PEC generato dalla classificazione legale."
                    note_lines = [
                        f"PEC_CONTROL_TOWER:{communication_id}",
                        f"Tipo evento: {legal_event_type}",
                        f"Fonte: PEC ricevuta il {communication.get('received_at') or due_date}",
                        f"Attività per l'avvocato: {task}" if task else "",
                        "La comunicazione di cancelleria non prova da sola la notifica dell'avvocato." if legal_event_type == "sentenza_da_valutare_per_notifica" else "",
                        "Termine operativo non definitivo: conferma professionale obbligatoria.",
                    ]
                    manager.nuova(
                        titolo=deadline["title"],
                        tipo=TipoTermine.ADEMPIMENTO,
                        data_scadenza=due_date,
                        id_fascicolo=matter_id,
                        descrizione=description,
                        note="\n".join(line for line in note_lines if line),
                        perentorio=False,
                        source_event_type=legal_event_type,
                        source_event_at=communication.get("received_at") or "",
                        external_uid=deadline["id"],
                        external_provider="pec_control_tower",
                        created_by=actor,
                    )
            except Exception:
                pass
        if deadline and self.agenda_db_path:
            try:
                from pct.agenda import Agenda, TipoAppuntamento

                agenda = Agenda(db_path=str(self.agenda_db_path))
                due_date = str(deadline["due_at"])[:10]
                matter_id = deadline.get("matter_id") or communication.get("fascicolo_id") or ""
                already_synced = False
                for row in agenda.tutti():
                    if getattr(row, "external_uid", "") == deadline["id"]:
                        already_synced = True
                        break
                    same_day = str(getattr(row, "data_ora", "") or "")[:10] == due_date
                    same_matter = not matter_id or not str(getattr(row, "procedimento", "") or "") or str(getattr(row, "procedimento", "") or "") == matter_id
                    pec_audit_marker = str(getattr(row, "external_uid", "") or "").startswith("PEC_AUDIT:")
                    if same_day and (same_matter or pec_audit_marker) and pec_audit_marker:
                        already_synced = True
                        break
                if not already_synced:
                    legal_event_type = communication.get("legal_event_type") or "pec"
                    agenda_note_lines = [
                        f"PEC_CONTROL_TOWER:{communication_id}",
                        f"Tipo evento: {legal_event_type}",
                        _clean(communication.get("summary") or "", 700),
                        "Presidio PEC da confermare.",
                    ]
                    agenda.aggiungi(
                        titolo=deadline["title"],
                        tipo=TipoAppuntamento.SCADENZA,
                        data_ora=str(deadline["due_at"]),
                        durata_minuti=30,
                        luogo="Studio",
                        allow_overlap=True,
                        procedimento=communication.get("fascicolo_id") or "",
                        note="\n".join(line for line in agenda_note_lines if line),
                        external_uid=deadline["id"],
                        external_provider="pec_control_tower",
                    )
            except Exception:
                pass

    def match_fascicolo(self, parsed: dict[str, Any], legal: dict[str, Any]) -> dict[str, Any]:
        text = _normalize_match_text(" ".join([parsed.get("subject") or "", parsed.get("search_text") or ""]))
        rows = self._load_fascicoli_rows()
        best: dict[str, Any] = {"fascicolo_id": "", "score": 0.0, "reason": "Nessun fascicolo compatibile trovato."}
        rg_refs = _extract_rg_refs(text)
        for row in rows:
            payload = _object_dict(row)
            fascicolo_id = _clean(payload.get("id") or payload.get("numero") or payload.get("codice"))
            if not fascicolo_id:
                continue
            score = 0.0
            reasons: list[str] = []
            for key in ("numero", "titolo", "oggetto", "procedimento", "tribunale", "nome_cliente", "cliente", "controparte"):
                value = _normalize_match_text(payload.get(key))
                if value and len(value) > 3 and value in text:
                    score += 1.5
                    reasons.append(key)
            rg_text = _normalize_match_text(" ".join(str(payload.get(key) or "") for key in ("rg", "numero_rg", "procedimento", "numero")))
            for ref in rg_refs:
                ref_text = _normalize_match_text(f"{ref.get('numero')}/{ref.get('anno')}")
                if ref_text and ref_text in rg_text:
                    score += 4
                    reasons.append("numero RG")
            if score > float(best.get("score") or 0):
                best = {
                    "fascicolo_id": fascicolo_id,
                    "score": round(score, 2),
                    "reason": ", ".join(dict.fromkeys(reasons)) or "Corrispondenza testuale",
                    "label": _clean(payload.get("titolo") or payload.get("oggetto") or payload.get("numero") or fascicolo_id),
                }
        if float(best.get("score") or 0) < 2:
            best["fascicolo_id"] = ""
            best["requires_human_match"] = True
        else:
            best["requires_human_match"] = False
        return best

    def _load_fascicoli_rows(self) -> list[Any]:
        if self._fascicoli_rows:
            return list(self._fascicoli_rows)
        if not self.fascicoli_db_path or not self.fascicoli_db_path.exists():
            return []
        try:
            from pct.fascicoli import GestioneFascicoli

            manager = GestioneFascicoli(
                db_path=str(self.fascicoli_db_path),
                documents_dir=str(self.fascicoli_docs_path or ""),
            )
            try:
                return list(manager.tutti(archiviati=True))
            except TypeError:
                return list(manager.tutti())
        except Exception:
            return _load_json_rows(self.fascicoli_db_path)

    def _append_audit(
        self,
        con: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        created_at = now_utc_iso()
        previous = con.execute(
            "SELECT event_hash FROM audit_events WHERE tenant_id=? ORDER BY rowid DESC LIMIT 1",
            (self.tenant_id,),
        ).fetchone()
        previous_hash = str(previous["event_hash"]) if previous else ""
        canonical = {
            "tenant_id": self.tenant_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": _clean(actor) or "system",
            "payload_json": _json(payload),
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        event_hash = self._audit_hash(canonical)
        con.execute(
            """
            INSERT INTO audit_events
            (id, tenant_id, entity_type, entity_id, action, actor, payload_json,
             created_at, previous_hash, event_hash, key_hint)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                _new_id("aud"),
                self.tenant_id,
                entity_type,
                entity_id,
                action,
                _clean(actor) or "system",
                canonical["payload_json"],
                created_at,
                previous_hash,
                event_hash,
                "runtime-configured" if self.audit_secret else "tenant-local",
            ),
        )

    def _audit_hash(self, payload: dict[str, Any]) -> str:
        raw_key = self.audit_secret
        if isinstance(raw_key, str):
            key = raw_key.encode("utf-8")
        elif isinstance(raw_key, bytes):
            key = raw_key
        else:
            key = f"{self.tenant_id}:pec-control-tower".encode("utf-8")
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(key, body, hashlib.sha256).hexdigest()

    def _outbound_without_delivery(self, con: sqlite3.Connection, *, limit: int) -> list[dict[str, Any]]:
        rows = con.execute(
            """
            SELECT r.*, c.subject, c.sender, c.received_at, c.fascicolo_id
            FROM pec_receipt_events r
            JOIN legal_communications c ON c.id=r.communication_id
            WHERE r.tenant_id=? AND r.role='acceptance'
            ORDER BY r.created_at DESC LIMIT ?
            """,
            (self.tenant_id, limit * 2),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            referred = str(row["referred_message_id"] or "")
            delivery = con.execute(
                """
                SELECT 1 FROM pec_receipt_events
                WHERE tenant_id=? AND referred_message_id=? AND role='delivery'
                LIMIT 1
                """,
                (self.tenant_id, referred),
            ).fetchone()
            if delivery:
                continue
            payload = _receipt_from_row(row)
            payload.update(
                {
                    "subject": row["subject"],
                    "sender": row["sender"],
                    "received_at": row["received_at"],
                    "fascicolo_id": row["fascicolo_id"],
                    "status": "waiting_delivery",
                }
            )
            items.append(payload)
            if len(items) >= limit:
                break
        return items

    def _proof_bundle_from_row(self, con: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        notification = self._notification_from_row(con, row)
        roles = {str(item.get("role") or "") for item in notification.get("proofs") or []}
        return {
            "id": notification["id"],
            "title": notification.get("title") or "",
            "recipient": notification.get("recipient") or "",
            "status": notification.get("status") or "",
            "proofs": notification.get("proofs") or [],
            "proof_complete": {"acceptance", "delivery"}.issubset(roles),
            "missing_roles": sorted({"acceptance", "delivery"} - roles),
            "matter_id": notification.get("matter_id") or "",
        }

    def _receipt_proof_bundles(self, con: sqlite3.Connection, *, limit: int) -> list[dict[str, Any]]:
        rows = con.execute(
            """
            SELECT r.*, c.subject, c.fascicolo_id, c.received_at
            FROM pec_receipt_events r
            JOIN legal_communications c ON c.id=r.communication_id
            WHERE r.tenant_id=? AND r.referred_message_id<>''
            ORDER BY r.created_at DESC
            """,
            (self.tenant_id,),
        ).fetchall()
        bundles: dict[str, dict[str, Any]] = {}
        for row in rows:
            referred = str(row["referred_message_id"] or "")
            bundle = bundles.setdefault(
                referred,
                {
                    "id": f"proof_{hashlib.sha256(referred.encode('utf-8')).hexdigest()[:16]}",
                    "title": f"Prova notifica PEC {referred}",
                    "referred_message_id": referred,
                    "matter_id": row["fascicolo_id"] or "",
                    "status": "partial",
                    "proofs": [],
                    "received_at": row["received_at"],
                },
            )
            receipt = _receipt_from_row(row)
            bundle["proofs"].append(receipt)
            if not bundle.get("matter_id") and row["fascicolo_id"]:
                bundle["matter_id"] = row["fascicolo_id"]
        result: list[dict[str, Any]] = []
        for bundle in bundles.values():
            roles = {str(item.get("role") or "") for item in bundle.get("proofs") or []}
            bundle["proof_complete"] = {"acceptance", "delivery"}.issubset(roles)
            bundle["missing_roles"] = sorted({"acceptance", "delivery"} - roles)
            bundle["status"] = "complete" if bundle["proof_complete"] else "partial"
            result.append(bundle)
        result.sort(
            key=lambda item: (
                0 if item.get("proof_complete") else 1,
                str(item.get("received_at") or ""),
            ),
            reverse=False,
        )
        complete = [item for item in result if item.get("proof_complete")]
        partial = [item for item in result if not item.get("proof_complete")]
        complete.sort(key=lambda item: str(item.get("received_at") or ""), reverse=True)
        partial.sort(key=lambda item: str(item.get("received_at") or ""), reverse=True)
        return [*complete, *partial][:limit]


def parse_pec_mime(raw_mime: bytes) -> dict[str, Any]:
    msg = message_from_bytes(raw_mime, policy=email_policy)
    headers = {str(key).lower(): _clean(value) for key, value in msg.items()}
    subject = _clean(msg.get("Subject"))
    sender = _clean(parseaddr(str(msg.get("From") or ""))[1] or msg.get("From"))
    recipients = [
        {"name": _clean(name), "email": _clean(email)}
        for name, email in getaddresses([str(msg.get("To") or ""), str(msg.get("Cc") or "")])
        if _clean(email)
    ]
    message_dt = _message_date(msg)
    body_parts: list[str] = []
    attachments: list[dict[str, Any]] = []
    daticert_payload: dict[str, Any] = {}
    nested_text: list[str] = []
    for part in _iter_leaf_parts(msg):
        disposition = str(part.get_content_disposition() or "")
        content_type = str(part.get_content_type() or "")
        filename = _clean(part.get_filename())
        raw = _part_bytes(part)
        if content_type.startswith("text/") and disposition != "attachment" and not filename:
            body_parts.append(_part_text(part, raw))
            continue
        if filename or disposition == "attachment":
            attachment = {
                "filename": filename or "allegato",
                "content_type": content_type,
                "size": len(raw),
                "sha256": _sha256(raw),
            }
            attachments.append(attachment)
            lower_name = (filename or "").lower()
            if lower_name.endswith(".xml") and "daticert" in lower_name:
                daticert_payload = _parse_daticert(raw)
                daticert_payload["sha256"] = attachment["sha256"]
            elif lower_name.endswith(".eml") or content_type == "message/rfc822":
                try:
                    nested = parse_pec_mime(raw)
                    nested_text.append(nested.get("search_text") or "")
                    attachment["nested_message_id"] = nested.get("message_id") or ""
                except Exception:
                    pass
            elif lower_name.endswith(".zip"):
                zip_payload = _inspect_zip(raw)
                if zip_payload.get("daticert") and not daticert_payload:
                    daticert_payload = dict(zip_payload["daticert"])
                nested_text.extend(zip_payload.get("texts") or [])
                attachment["zip_entries"] = zip_payload.get("entries") or []
    body = _clean(" ".join(body_parts))
    search_text = _clean(" ".join([subject, sender, body, " ".join(item["filename"] for item in attachments), " ".join(nested_text)]))
    return {
        "message_id": _strip_message_id(msg.get("Message-ID")),
        "subject": subject,
        "sender": sender,
        "recipients": recipients,
        "received_at": message_dt.isoformat(),
        "sent_at": message_dt.isoformat(),
        "headers": headers,
        "body": body,
        "attachments": attachments,
        "daticert": daticert_payload,
        "search_text": search_text,
        "extracted": {"sender": sender, "subject": subject},
        "mime_sha256": _sha256(raw_mime),
    }


def classify_technical(parsed: dict[str, Any]) -> dict[str, Any]:
    headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    daticert = parsed.get("daticert") if isinstance(parsed.get("daticert"), dict) else {}
    text = _lower(" ".join([parsed.get("subject") or "", parsed.get("search_text") or "", daticert.get("tipo") or ""]))
    x_ricevuta = _lower(headers.get("x-ricevuta"))
    x_trasporto = _lower(headers.get("x-trasporto"))
    receipt_type = _clean(daticert.get("tipo") or headers.get("x-tiporicevuta") or x_ricevuta)
    referred = _strip_message_id(headers.get("x-riferimento-message-id") or daticert.get("msgid") or "")
    if "non-accettazione" in text or "non accettazione" in text:
        return _technical("PEC_RECEIPT_NON_ACCEPTANCE", "OUTBOUND_PROOF", "failed_delivery", receipt_type, referred)
    if "mancata consegna" in text or "avviso di mancata consegna" in text:
        return _technical("PEC_RECEIPT_FAILED_DELIVERY", "OUTBOUND_PROOF", "failed_delivery", receipt_type, referred)
    if "accettazione" in text or "ricevuta di accettazione" in text:
        return _technical("PEC_RECEIPT_ACCEPTANCE", "OUTBOUND_PROOF", "acceptance", receipt_type, referred)
    if "avvenuta consegna" in text or "ricevuta di consegna" in text or x_ricevuta:
        if "sintetica" in text or "sintetica" in receipt_type.lower():
            typ = "PEC_RECEIPT_DELIVERY_SYNTHETIC"
        elif "breve" in text or "breve" in receipt_type.lower():
            typ = "PEC_RECEIPT_DELIVERY_SHORT"
        elif "completa" in text or "completa" in receipt_type.lower():
            typ = "PEC_RECEIPT_DELIVERY_COMPLETE"
        else:
            typ = "PEC_RECEIPT_DELIVERY"
        return _technical(typ, "OUTBOUND_PROOF", "delivery", receipt_type, referred)
    if "anomalia" in text or "errore" in x_trasporto:
        return _technical("PEC_ANOMALY", "INBOUND", "", receipt_type, referred)
    if "virus" in text:
        return _technical("PEC_VIRUS_WARNING", "INBOUND", "", receipt_type, referred)
    return _technical("PEC_INBOUND_CERTIFIED", "INBOUND", "", receipt_type, referred)


def classify_legal(parsed: dict[str, Any], technical: dict[str, Any]) -> dict[str, Any]:
    text = _lower(" ".join([parsed.get("sender") or "", parsed.get("subject") or "", parsed.get("search_text") or ""]))
    if technical.get("receipt_role"):
        if technical["receipt_role"] == "failed_delivery":
            return _legal(
                "PEC_OUTBOUND_PROOF",
                "notifica_fallita_o_da_rimediare",
                "Notifica fallita o consegna non riuscita",
                "critica",
                0.96,
                "Gestisci subito la mancata consegna e verifica destinatario/canale alternativo.",
                "Ricevuta PEC negativa o mancata consegna.",
            )
        if technical["receipt_role"] == "acceptance":
            return _legal(
                "PEC_OUTBOUND_PROOF",
                "ricevuta_accettazione_da_presidiare",
                "Ricevuta di accettazione PEC",
                "alta",
                0.95,
                "Attendi o collega la ricevuta di consegna; la prova è ancora parziale.",
                "Ricevuta di accettazione senza chiusura automatica della notifica.",
            )
        return _legal(
            "PEC_OUTBOUND_PROOF",
            "ricevuta_consegna_da_conservare",
            "Ricevuta di consegna PEC",
            "alta",
            0.95,
            "Conserva la ricevuta e collega la prova completa alla notifica.",
            "Ricevuta di avvenuta consegna.",
        )
    if any(token in text for token in ("giustiziacert", "cancelleria", "tribunale", "corte d", "ufficio giudiziario", "pst")):
        if "sentenza" in text or "definitivamente decidendo" in text or "resa ex art. 429" in text:
            return _legal(
                "PROVVEDIMENTO_GIUDIZIARIO",
                "sentenza_da_valutare_per_notifica",
                "Sentenza da valutare per la notifica",
                "alta",
                0.92,
                "Esamina la sentenza e valuta/prepara la notifica: la comunicazione di cancelleria non prova la notifica dell'avvocato.",
                "Sentenza o provvedimento decisorio ricevuto dalla cancelleria; serve presidio post-sentenza e valutazione della notifica.",
            )
        if any(token in text for token in ("decreto", "ordinanza", "provvedimento")):
            return _legal(
                "PROVVEDIMENTO_GIUDIZIARIO",
                "provvedimento_da_esaminare",
                "Provvedimento giudiziario ricevuto",
                "alta",
                0.9,
                "Esamina il provvedimento e conferma eventuali termini.",
                "PEC da circuito giustizia con provvedimento o atto allegato.",
            )
        return _legal(
            "CANCELLERIA_PCT",
            "comunicazione_cancelleria",
            "Comunicazione di cancelleria",
            "alta",
            0.88,
            "Collega al fascicolo e verifica se genera termini o adempimenti.",
            "Mittente o contenuto riconducibile a cancelleria/PCT.",
        )
    if any(token in text for token in ("notifica", "relata", "legge 53", "l. 53", "controparte", "da notificare")):
        return _legal(
            "NOTIFICA_CONTROPARTE",
            "notifica_da_preparare_o_presidiare",
            "Notifica verso controparte",
            "alta",
            0.86,
            "Prepara o verifica relata, destinatari e prova completa prima di chiudere.",
            "Contenuto riconducibile a notifica o relata.",
        )
    if any(token in text for token in ("comune", "agenzia delle entrate", "inps", "inail", "ministero", "regione", "protocollo", "pubblica amministrazione")):
        return _legal(
            "ATTO_AMMINISTRATIVO_PA",
            "comunicazione_pa_con_riscontro",
            "Comunicazione PA o ente",
            "alta" if _extract_explicit_deadline(parsed.get("search_text") or "", parsed.get("received_at") or "").get("due_at") else "media",
            0.84,
            "Verifica il termine indicato e prepara eventuale riscontro.",
            "Mittente o contenuto riconducibile a pubblica amministrazione o ente.",
        )
    if any(token in text for token in ("diffida", "messa in mora", "intimazione")):
        return _legal(
            "DIFFIDA_MESSA_IN_MORA",
            "diffida_da_valutare",
            "Diffida o messa in mora",
            "alta",
            0.84,
            "Valuta la risposta e conserva la prova di ricezione.",
            "Parole chiave di diffida o costituzione in mora.",
        )
    if any(token in text for token in ("disdetta", "recesso", "contratto", "risoluzione")):
        return _legal(
            "CONTRATTO_DISDETTA_RECESSO",
            "contratto_disdetta_recesso",
            "Contratto, disdetta o recesso",
            "media",
            0.8,
            "Verifica contratto, termine e documenti richiamati.",
            "Comunicazione contrattuale.",
        )
    if any(token in text for token in ("documenti", "allego", "cliente", "mandato")):
        return _legal(
            "CLIENTE_DOCUMENTI",
            "documenti_cliente",
            "Documenti o istruzioni cliente",
            "media",
            0.76,
            "Archivia nel fascicolo e verifica se mancano atti o allegati.",
            "PEC con documenti o istruzioni operative.",
        )
    return _legal(
        "UNKNOWN_LEGAL_RISK",
        "pec_da_classificare",
        "PEC da classificare",
        "media",
        0.55,
        "Leggi la PEC e classificala prima di creare automatismi.",
        "Classificazione non sufficientemente certa.",
    )


def _technical(technical_type: str, direction: str, role: str, receipt_type: str, referred: str) -> dict[str, Any]:
    return {
        "technical_type": technical_type,
        "direction": direction,
        "receipt_role": role,
        "receipt_type": receipt_type,
        "referred_message_id": referred,
    }


def _legal(
    legal_category: str,
    legal_event_type: str,
    label: str,
    risk_level: str,
    confidence: float,
    primary_task: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "legal_category": legal_category,
        "legal_event_type": legal_event_type,
        "label": label,
        "risk_level": risk_level,
        "confidence": confidence,
        "confidence_label": "alta" if confidence >= 0.85 else "media" if confidence >= 0.7 else "bassa",
        "requires_human_confirmation": confidence < 0.98,
        "primary_task": primary_task,
        "summary": summary,
    }


def _deadline_rule(legal: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any] | None:
    category = legal.get("legal_category")
    event_type = legal.get("legal_event_type")
    code = ""
    if category in {"CANCELLERIA_PCT", "PROVVEDIMENTO_GIUDIZIARIO"}:
        code = "PEC_CANCELLERIA_REVIEW_1D"
    elif category in {"ATTO_AMMINISTRATIVO_PA", "ENTE_RICHIESTA_RISCONTRO"} and extracted.get("termine_espresso"):
        code = "PEC_PA_RISCONTRO_TERMINE_ESPRESSO"
    elif category == "DIFFIDA_MESSA_IN_MORA":
        code = "PEC_DIFFIDA_TERMINE_ESPRESSO"
    elif category == "NOTIFICA_CONTROPARTE":
        code = "PEC_OUTBOUND_RECEIPT_MONITOR"
    elif event_type in {"ricevuta_accettazione_da_presidiare", "notifica_fallita_o_da_rimediare"}:
        code = "PEC_FAILED_DELIVERY_REMEDIATION" if event_type == "notifica_fallita_o_da_rimediare" else "PEC_OUTBOUND_RECEIPT_MONITOR"
    elif category == "UNKNOWN_LEGAL_RISK":
        code = "PEC_UNKNOWN_REVIEW_1D"
    if not code:
        return None
    for seed in RULE_SEEDS:
        if seed["code"] == code:
            return seed
    return None


def _deadline_title(legal: dict[str, Any]) -> str:
    category = legal.get("legal_category")
    event_type = legal.get("legal_event_type")
    if category == "PEC_OUTBOUND_PROOF":
        return "Presidio ricevute PEC da completare"
    if event_type == "sentenza_da_valutare_per_notifica":
        return "Sentenza da valutare per la notifica"
    if category in {"CANCELLERIA_PCT", "PROVVEDIMENTO_GIUDIZIARIO"}:
        return "Verifica comunicazione di cancelleria e termini"
    if category in {"ATTO_AMMINISTRATIVO_PA", "ENTE_RICHIESTA_RISCONTRO"}:
        return "Verifica riscontro a comunicazione PA"
    if category == "DIFFIDA_MESSA_IN_MORA":
        return "Valuta risposta a diffida"
    if category == "NOTIFICA_CONTROPARTE":
        return "Prepara o completa notifica"
    return "Classifica PEC e conferma adempimenti"


def _notification_draft(legal: dict[str, Any], technical: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any] | None:
    category = legal.get("legal_category")
    recipient = _first_recipient(parsed) or parsed.get("sender") or ""
    if category in {"ATTO_AMMINISTRATIVO_PA", "ENTE_RICHIESTA_RISCONTRO"}:
        return {
            "direction": "outbound",
            "recipient": parsed.get("sender") or recipient,
            "title": "Bozza riscontro a comunicazione PA",
            "draft_text": "Predisporre bozza di riscontro dopo verifica del termine espresso e degli allegati.",
            "registry_source": "registro ente da verificare",
        }
    if category == "NOTIFICA_CONTROPARTE":
        return {
            "direction": "outbound",
            "recipient": recipient,
            "title": "Bozza notifica verso controparte",
            "draft_text": "Preparare atto, relata e destinatari. Nessun invio automatico.",
            "registry_source": "INI-PEC/ReGIndE/INAD da verificare",
        }
    if technical.get("receipt_role") == "acceptance":
        return {
            "direction": "outbound",
            "recipient": recipient,
            "title": "Presidio consegna PEC dopo accettazione",
            "draft_text": "La ricevuta di accettazione è presente; manca la consegna collegata.",
            "registry_source": "daticert.xml",
        }
    if technical.get("receipt_role") == "failed_delivery":
        return {
            "direction": "outbound",
            "recipient": recipient,
            "title": "Rimedio a mancata consegna PEC",
            "draft_text": "Verificare indirizzo, registro pubblico e canale alternativo prima di nuovo invio.",
            "registry_source": "daticert.xml",
        }
    return None


def _suggested_actions(legal: dict[str, Any], missing_docs: list[str], matter: dict[str, Any]) -> list[str]:
    actions = [legal["primary_task"]]
    if not matter.get("fascicolo_id"):
        actions.append("Associa l'evento al fascicolo corretto.")
    if missing_docs:
        actions.append("Controlla i documenti mancanti prima della conferma.")
    actions.append("Conferma classificazione e termini solo dopo revisione professionale.")
    return list(dict.fromkeys(actions))


def _coverage_gaps_for(kind: str, items: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    if not items:
        gaps.append("Nessuna evidenza reale trovata nella PEC Control Tower per questa domanda.")
    if kind in {"unconfirmed_terms", "forfeiture_risk"}:
        gaps.append("I termini mostrati sono bozze operative finché non risultano confermati dall'avvocato.")
    if kind == "complete_proof":
        gaps.append("La prova è completa solo quando risultano almeno accettazione e consegna collegate alla stessa notifica.")
    return gaps


def _question_kind(question: str) -> str:
    text = _lower(question)
    for kind, tokens in QUESTION_PATTERNS:
        if all(token in text for token in tokens):
            return kind
    if "scaden" in text and "pec" in text:
        return "deadlines_today"
    if "notific" in text and ("fare" in text or "devo" in text):
        return "notifications_to_do"
    if "decaden" in text:
        return "forfeiture_risk"
    if "cancelleria" in text:
        return "court_registry_acts"
    return "overview"


def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = _row_dict(row)
    for key in ("extracted_json", "expected_documents_json", "produced_documents_json", "missing_documents_json", "legal_articles_json", "suggested_actions_json"):
        target = key.removesuffix("_json")
        payload[target] = _loads(payload.pop(key, "[]" if key.endswith("documents_json") or key == "legal_articles_json" or key == "suggested_actions_json" else "{}"))
    return payload


def _deadline_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = _row_dict(row)
    payload["requires_human_confirmation"] = bool(payload.get("requires_human_confirmation"))
    payload["calculation"] = _loads(payload.pop("calculation_json", "{}"))
    return payload


def _agenda_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return _row_dict(row)


def _task_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return _row_dict(row)


def _receipt_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = _row_dict(row)
    payload["daticert"] = _loads(payload.pop("daticert_json", "{}"))
    return payload


def _proof_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = _row_dict(row)
    payload["evidence"] = _loads(payload.pop("evidence_json", "{}"))
    return payload


def _audit_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = _row_dict(row)
    payload["payload"] = _loads(payload.pop("payload_json", "{}"))
    return payload


def _iter_leaf_parts(msg: Message):
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            yield part
    else:
        yield msg


def _part_bytes(part: Message) -> bytes:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        if isinstance(raw, str):
            return raw.encode(part.get_content_charset() or "utf-8", errors="replace")
        if isinstance(raw, bytes):
            return raw
        return b""
    return bytes(payload)


def _part_text(part: Message, raw: bytes) -> str:
    charset = part.get_content_charset() or "utf-8"
    try:
        text = raw.decode(charset, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    if str(part.get_content_type()).lower() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    return _clean(text)


def _inspect_zip(raw: bytes) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    texts: list[str] = []
    daticert: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist()[:50]:
                if info.is_dir() or info.file_size > 8 * 1024 * 1024:
                    continue
                data = zf.read(info)
                entries.append({"filename": info.filename, "size": len(data), "sha256": _sha256(data)})
                lower = info.filename.lower()
                if lower.endswith("daticert.xml") and not daticert:
                    daticert = _parse_daticert(data)
                    daticert["sha256"] = _sha256(data)
                elif lower.endswith(".eml"):
                    try:
                        nested = parse_pec_mime(data)
                        texts.append(nested.get("search_text") or "")
                    except Exception:
                        pass
                elif lower.endswith((".txt", ".xml")):
                    texts.append(data.decode("utf-8", errors="replace")[:4000])
    except zipfile.BadZipFile:
        pass
    return {"entries": entries, "texts": texts, "daticert": daticert}


def _parse_daticert(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    payload: dict[str, Any] = {"raw_excerpt": _clean(text)[:1200]}
    try:
        root = ElementTree.fromstring(raw)
        flat: dict[str, str] = {}
        for node in root.iter():
            tag = str(node.tag).split("}", 1)[-1].lower()
            value = _clean(node.text)
            if value and tag not in flat:
                flat[tag] = value
            for key, value in node.attrib.items():
                attr = str(key).split("}", 1)[-1].lower()
                if value and attr not in flat:
                    flat[attr] = _clean(value)
        payload.update(flat)
    except ElementTree.ParseError:
        pass
    payload.setdefault("tipo", _regex_value(r"<tipo[^>]*>(.*?)</tipo>", text))
    payload.setdefault("mittente", _regex_value(r"<mittente[^>]*>(.*?)</mittente>", text))
    payload.setdefault("destinatario", _regex_value(r"<destinatari?[^>]*>(.*?)</destinatari?>", text))
    payload.setdefault("oggetto", _regex_value(r"<oggetto[^>]*>(.*?)</oggetto>", text))
    payload.setdefault("msgid", _strip_message_id(_regex_value(r"<msgid[^>]*>(.*?)</msgid>", text) or _regex_value(r"<identificativo[^>]*>(.*?)</identificativo>", text)))
    day = payload.get("giorno") or payload.get("data") or ""
    hour = payload.get("ora") or ""
    payload["receipt_at"] = _combine_daticert_datetime(day, hour)
    return {key: value for key, value in payload.items() if value not in ("", None, [], {})}


def _combine_daticert_datetime(day: str, hour: str) -> str:
    raw = _clean(f"{day} {hour}")
    if not raw:
        return ""
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=ROME_TZ).astimezone(timezone.utc).replace(microsecond=0).isoformat()
        except ValueError:
            continue
    return raw


def _message_date(msg: Message) -> datetime:
    raw = msg.get("Date")
    if raw:
        try:
            parsed = parsedate_to_datetime(str(raw))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).replace(microsecond=0)
        except Exception:
            pass
    return datetime.now(timezone.utc).replace(microsecond=0)


def _extract_explicit_deadline(text: str, event_at: str) -> dict[str, Any]:
    lower = _lower(text)
    match = re.search(r"\bentro\s+(?P<days>\d{1,3})\s+giorn", lower)
    source_dt = _parse_dt(event_at) or datetime.now(timezone.utc)
    if match:
        days = int(match.group("days"))
        return {
            "type": "giorni_espresso",
            "days": days,
            "due_at": _add_days(source_dt, days).isoformat(),
            "source_text": match.group(0),
        }
    date_match = re.search(r"\b(?:entro|scadenza|termine)\s+il\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})", lower)
    if date_match:
        try:
            due = datetime.strptime(date_match.group("date"), "%d/%m/%Y").replace(tzinfo=ROME_TZ, hour=9)
            return {"type": "data_espressa", "due_at": due.astimezone(timezone.utc).isoformat(), "source_text": date_match.group(0)}
        except ValueError:
            pass
    return {}


def _extract_rg_refs(text: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for match in re.finditer(r"\b(?:r\.?\s*g\.?|rg|n\.?)\s*(?P<num>\d{1,7})\s*/\s*(?P<year>20\d{2}|19\d{2})\b", text, re.I):
        refs.append({"numero": match.group("num"), "anno": match.group("year")})
    return refs


def _produced_documents(parsed: dict[str, Any]) -> list[str]:
    docs = [str(item.get("filename") or "") for item in parsed.get("attachments") or [] if item.get("filename")]
    if parsed.get("body"):
        docs.append("corpo PEC")
    return list(dict.fromkeys(docs))


def _missing_documents(expected: list[str], produced: list[str]) -> list[str]:
    produced_text = _lower(" ".join(produced))
    missing = []
    for item in expected:
        words = [word for word in re.split(r"\W+", _lower(item)) if len(word) > 4]
        if words and any(word in produced_text for word in words):
            continue
        missing.append(item)
    return missing


def _first_recipient(parsed: dict[str, Any]) -> str:
    recipients = parsed.get("recipients") or []
    if recipients and isinstance(recipients[0], dict):
        return _clean(recipients[0].get("email"))
    return ""


def _add_days(source_dt: datetime, days: int) -> datetime:
    due = source_dt.astimezone(ROME_TZ) + timedelta(days=max(0, days))
    return due.replace(hour=9, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _ics_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ics_escape(value: Any) -> str:
    return _clean(value).replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def email_relevant_for_pec_control(email_obj: Any) -> bool:
    """Riconosce le righe della casella locale che possono generare eventi PEC giuridici."""

    attachments = " ".join(
        str((item or {}).get("nome") or (item or {}).get("nome_file") or (item or {}).get("filename") or "")
        for item in list(getattr(email_obj, "allegati", []) or [])
        if isinstance(item, dict)
    ).lower()
    text = " ".join(
        str(value or "")
        for value in (
            getattr(email_obj, "oggetto", ""),
            getattr(email_obj, "mittente", ""),
            getattr(email_obj, "mittente_nome", ""),
            getattr(email_obj, "destinatari", ""),
            getattr(email_obj, "corpo_testo", ""),
            getattr(email_obj, "corpo_html", ""),
            getattr(email_obj, "stato_pct", ""),
            getattr(email_obj, "eml_file", ""),
            attachments,
        )
    ).lower()
    return bool(
        getattr(email_obj, "e_pst", False)
        or "posta certificata" in text
        or "giustiziacert" in text
        or "ptel.giustizia" in text
        or "deposito telematico" in text
        or "daticert" in text
        or "postacert" in text
        or "ricevuta di accettazione" in text
        or "avvenuta consegna" in text
        or "mancata consegna" in text
        or "pec" in text
    )


def _email_archive_rows(email_manager: Any) -> list[Any]:
    if hasattr(email_manager, "_carica"):
        data = email_manager._carica()  # noqa: SLF001 - import tenant-aware della casella locale esistente
        if isinstance(data, dict):
            return list(data.values())
        return list(data or [])
    if hasattr(email_manager, "tutte"):
        try:
            return list(email_manager.tutte(con_allegati=True))
        except TypeError:
            return list(email_manager.tutte())
    rows = getattr(email_manager, "rows", None)
    if rows is not None:
        return list(rows.values()) if isinstance(rows, dict) else list(rows)
    return []


def _email_archive_sort_key(email_obj: Any) -> datetime:
    parsed = _parse_dt(getattr(email_obj, "data", "") or getattr(email_obj, "ricevuta_il", ""))
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


def _email_archive_id(email_obj: Any) -> str:
    return _clean(getattr(email_obj, "id", "") or getattr(email_obj, "message_id", "") or "email")


def _email_archive_account(email_obj: Any) -> str:
    return _clean(getattr(email_obj, "destinatari", "") or getattr(email_obj, "mittente", "") or "casella PEC locale")[:240]


def _read_email_archive_mime(email_manager: Any, email_obj: Any) -> bytes:
    reader = getattr(email_manager, "leggi_eml_originale", None)
    if not callable(reader):
        return b""
    try:
        raw = reader(email_obj)
    except Exception:
        return b""
    return bytes(raw or b"")


def _reconstruct_email_archive_mime(email_manager: Any, email_obj: Any) -> bytes:
    """Ricostruisce un MIME minimo solo quando l'originale manca ma gli allegati sono salvati."""

    attachments: list[tuple[str, str, bytes]] = []
    for index, info in enumerate(list(getattr(email_obj, "allegati", []) or [])):
        if not isinstance(info, dict):
            continue
        reader = getattr(email_manager, "leggi_allegato", None)
        if not callable(reader):
            continue
        try:
            raw = reader(email_obj, index)
        except Exception:
            raw = None
        if not raw:
            continue
        filename = _clean(info.get("nome") or info.get("nome_file") or info.get("filename") or f"allegato-{index + 1}.bin")
        content_type = _clean(info.get("mime") or info.get("content_type") or "")
        attachments.append((filename, content_type, bytes(raw)))

    body = _clean(getattr(email_obj, "corpo_testo", "") or re.sub(r"<[^>]+>", " ", str(getattr(email_obj, "corpo_html", "") or "")))
    if not body and not attachments:
        return b""
    msg = EmailMessage()
    msg["Subject"] = _clean(getattr(email_obj, "oggetto", "") or "PEC archiviata")
    msg["From"] = _clean(getattr(email_obj, "mittente", "") or "casella-pec-locale@iusentra.local")
    msg["To"] = _clean(getattr(email_obj, "destinatari", "") or "studio@iusentra.local")
    message_id = _clean(getattr(email_obj, "message_id", ""))
    if message_id:
        msg["Message-ID"] = message_id if message_id.startswith("<") else f"<{message_id}>"
    msg["Date"] = _email_archive_rfc822_date(getattr(email_obj, "data", "") or getattr(email_obj, "ricevuta_il", ""))
    msg["X-IUSENTRA-Source"] = "casella-pec-locale-ricostruita"
    msg.set_content(body or "PEC archiviata localmente con allegati disponibili.", subtype="plain", charset="utf-8")
    for filename, content_type, raw in attachments:
        maintype, subtype = _attachment_mime_parts(filename, content_type)
        msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=filename)
    return msg.as_bytes(policy=email_policy)


def _email_archive_rfc822_date(value: Any) -> str:
    parsed = _parse_dt(value)
    if parsed is None:
        parsed = datetime.now(timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")


def _attachment_mime_parts(filename: str, content_type: str) -> tuple[str, str]:
    lower_type = _lower(content_type)
    if "/" in lower_type:
        maintype, subtype = lower_type.split("/", 1)
        if maintype == "message":
            return "application", "octet-stream"
        return maintype or "application", subtype or "octet-stream"
    lower_name = _lower(filename)
    if lower_name.endswith(".xml"):
        return "application", "xml"
    if lower_name.endswith(".txt"):
        return "text", "plain"
    if lower_name.endswith(".eml"):
        return "application", "octet-stream"
    if lower_name.endswith(".pdf"):
        return "application", "pdf"
    if lower_name.endswith(".zip"):
        return "application", "zip"
    return "application", "octet-stream"


def _load_json_rows(path: Path) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("fascicoli", "items", "data"):
            if isinstance(data.get(key), list):
                return list(data[key])
        return list(data.values())
    return []


def _object_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "to_dict"):
        try:
            return dict(row.to_dict())
        except Exception:
            pass
    return {key: getattr(row, key) for key in dir(row) if not key.startswith("_") and not callable(getattr(row, key))}


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()


def _lower(value: Any) -> str:
    return _clean(value).lower()


def _normalize_match_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9/]+", " ", _lower(value)).strip()


def _strip_message_id(value: Any) -> str:
    text = _clean(value)
    if text.startswith("<") and text.endswith(">"):
        return text[1:-1]
    return text


def _regex_value(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.I | re.S)
    return _clean(match.group(1)) if match else ""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"
