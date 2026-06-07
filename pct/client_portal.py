"""Repository tenant-aware per il Portale Cliente.

Il modulo espone una persistenza piccola e compatibile con SQLite/PostgreSQL.
I token d'invito vengono salvati solo come hash: il token in chiaro vive solo
nel risultato della creazione invito e nella richiesta del cliente.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from pct.postgres_runtime_support import PostgresRepositoryBackend


SCHEMA_CLIENT_PORTAL_SQLITE = Path(__file__).with_name("sql") / "20260607_client_portal.sql"
SCHEMA_CLIENT_PORTAL_POSTGRES = Path(__file__).with_name("sql") / "20260607_client_portal_postgres.sql"

CLIENT_PORTAL_TABLES = (
    "client_portal_profiles",
    "client_portal_matters",
    "client_portal_invites",
    "client_portal_steps",
    "client_portal_document_requests",
    "client_portal_documents",
    "client_portal_signature_requests",
    "client_portal_consents",
    "client_portal_messages",
    "client_portal_appointments",
    "client_portal_notifications",
    "client_portal_questionnaires",
    "client_portal_surveys",
    "client_portal_evidence_packs",
    "client_portal_settings",
    "client_portal_push_subscriptions",
    "client_portal_audit_events",
)

DEFAULT_CLIENT_PORTAL_SETTINGS = {
    "enabled": True,
    "inviteExpiresDays": 14,
    "allowedUploadTypes": [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
    "maxUploadMb": 20,
    "notifications": {
        "inApp": True,
        "email": False,
        "webPush": False,
    },
    "videoCalls": {
        "enabled": False,
        "provider": "",
    },
    "signatures": {
        "simpleEvidence": True,
        "qualifiedProvider": "",
    },
}


class ClientPortalError(ValueError):
    """Errore controllato del Portale Cliente."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def token_hash(token: str) -> str:
    cleaned = str(token or "").strip()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest() if cleaned else ""


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: Any, fallback: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        return fallback


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


class ClientPortalRepository:
    """Repository del Portale Cliente con backend SQLite o PostgreSQL."""

    def __init__(self, db_path: str | Path = "", *, postgres_dsn: str = "") -> None:
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.backend_kind = "postgres" if self.postgres_dsn else "sqlite"
        self.db_path = Path(db_path or "./data/client_portal/client_portal.db")
        self._pg_backend: PostgresRepositoryBackend | None = None
        if self.postgres_dsn:
            self._pg_backend = PostgresRepositoryBackend(self.postgres_dsn, SCHEMA_CLIENT_PORTAL_POSTGRES)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_sqlite_schema()

    def _ensure_sqlite_schema(self) -> None:
        schema = SCHEMA_CLIENT_PORTAL_SQLITE.read_text(encoding="utf-8")
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(schema)

    def connection(self):
        if self._pg_backend is not None:
            return self._pg_backend.connection()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        if self._pg_backend is not None:
            self._pg_backend.close()

    def _fetchone(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return _row_dict(row)

    def _fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_dict(row) for row in rows]

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self.connection() as conn:
            conn.execute(sql, tuple(params))

    def _insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        names = ", ".join(columns)
        sql = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
        self._execute(sql, [values[column] for column in columns])
        return dict(values)

    def _update(self, table: str, values: dict[str, Any], where: str, params: Iterable[Any]) -> None:
        if not values:
            return
        assignments = ", ".join(f"{column} = ?" for column in values)
        self._execute(
            f"UPDATE {table} SET {assignments} WHERE {where}",
            [*values.values(), *tuple(params)],
        )

    def _count(self, table: str, tenant_id: str, extra_where: str = "", params: Iterable[Any] = ()) -> int:
        where = "tenant_id = ?"
        if extra_where:
            where += f" AND {extra_where}"
        row = self._fetchone(f"SELECT COUNT(*) AS total FROM {table} WHERE {where}", (tenant_id, *tuple(params)))
        return int(row.get("total") or 0)

    def schema_table_names(self) -> set[str]:
        if self.backend_kind == "postgres":
            return set(CLIENT_PORTAL_TABLES)
        rows = self._fetchall("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'client_portal_%'")
        return {str(row.get("name") or "") for row in rows}

    def get_settings(self, tenant_id: str) -> dict[str, Any]:
        row = self._fetchone("SELECT settings_json FROM client_portal_settings WHERE tenant_id = ?", (tenant_id,))
        settings = dict(DEFAULT_CLIENT_PORTAL_SETTINGS)
        saved = json_loads(row.get("settings_json"), {})
        if isinstance(saved, dict):
            settings.update(saved)
            for key in ("notifications", "videoCalls", "signatures"):
                nested = dict(DEFAULT_CLIENT_PORTAL_SETTINGS.get(key, {}))
                nested.update(saved.get(key) if isinstance(saved.get(key), dict) else {})
                settings[key] = nested
        return settings

    def update_settings(self, tenant_id: str, settings: dict[str, Any], *, actor_id: str = "") -> dict[str, Any]:
        now = utc_now()
        merged = self.get_settings(tenant_id)
        merged.update(settings)
        for key in ("notifications", "videoCalls", "signatures"):
            if isinstance(settings.get(key), dict):
                nested = dict(self.get_settings(tenant_id).get(key, {}))
                nested.update(settings[key])
                merged[key] = nested
        row = self._fetchone("SELECT tenant_id FROM client_portal_settings WHERE tenant_id = ?", (tenant_id,))
        values = {
            "settings_json": json_dumps(merged),
            "updated_at": now,
            "updated_by": actor_id,
        }
        if row:
            self._update("client_portal_settings", values, "tenant_id = ?", (tenant_id,))
        else:
            self._insert("client_portal_settings", {"tenant_id": tenant_id, **values})
        self.record_audit(tenant_id, "studio", actor_id, "client_portal.settings.update", "settings", tenant_id, merged)
        return merged

    def ensure_profile(self, tenant_id: str, *, client_id: str, display_name: str, email: str = "", phone: str = "", fiscal_code: str = "", identity_expires_at: str = "", preferences: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        row = self._fetchone(
            "SELECT * FROM client_portal_profiles WHERE tenant_id = ? AND client_id = ?",
            (tenant_id, client_id),
        )
        values = {
            "display_name": display_name,
            "email": email,
            "phone": phone,
            "fiscal_code": fiscal_code,
            "identity_expires_at": identity_expires_at,
            "updated_at": now,
        }
        if preferences is not None:
            values["preferences_json"] = json_dumps(preferences)
        if row:
            self._update("client_portal_profiles", values, "id = ?", (row["id"],))
            return self.get_profile(tenant_id, client_id) or {**row, **values}
        record = {
            "id": new_id("cpp"),
            "tenant_id": tenant_id,
            "client_id": client_id,
            **values,
            "preferences_json": json_dumps(preferences or {"email": True, "sms": False, "webPush": False}),
            "created_at": now,
        }
        self._insert("client_portal_profiles", record)
        return record

    def get_profile(self, tenant_id: str, client_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            "SELECT * FROM client_portal_profiles WHERE tenant_id = ? AND client_id = ?",
            (tenant_id, client_id),
        )
        return row or None

    def ensure_matter(self, tenant_id: str, *, client_id: str, fascicolo_id: str, title: str, status: str = "attiva", opened_at: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
        if not fascicolo_id:
            raise ClientPortalError("Fascicolo richiesto per aprire il portale cliente.")
        now = utc_now()
        row = self._fetchone(
            "SELECT * FROM client_portal_matters WHERE tenant_id = ? AND fascicolo_id = ?",
            (tenant_id, fascicolo_id),
        )
        values = {
            "client_id": client_id,
            "title": title,
            "status": status or "attiva",
            "opened_at": opened_at,
            "updated_at": now,
        }
        if data is not None:
            values["data_json"] = json_dumps(data)
        if row:
            self._update("client_portal_matters", values, "id = ?", (row["id"],))
            matter = self.get_matter(tenant_id, row["id"]) or {**row, **values}
        else:
            matter = {
                "id": new_id("cpm"),
                "tenant_id": tenant_id,
                "client_id": client_id,
                "fascicolo_id": fascicolo_id,
                "title": title,
                "status": status or "attiva",
                "progress": 15,
                "next_action": "Completare privacy, anagrafica e documenti richiesti.",
                "opened_at": opened_at,
                "closed_at": "",
                "data_json": json_dumps(data or {}),
                "created_at": now,
                "updated_at": now,
            }
            self._insert("client_portal_matters", matter)
        self.ensure_starter_records(tenant_id, matter["id"], client_id)
        return matter

    def get_matter(self, tenant_id: str, matter_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            "SELECT * FROM client_portal_matters WHERE tenant_id = ? AND id = ?",
            (tenant_id, matter_id),
        )
        return row or None

    def ensure_starter_records(self, tenant_id: str, matter_id: str, client_id: str) -> None:
        now = utc_now()
        if self._count("client_portal_steps", tenant_id, "matter_id = ?", (matter_id,)) == 0:
            steps = [
                ("Privacy e consensi", "da_fare"),
                ("Anagrafica cliente", "da_fare"),
                ("Documenti richiesti", "da_fare"),
                ("Documenti da firmare", "in_attesa"),
                ("Appuntamento o videocall", "in_attesa"),
            ]
            for index, (title, status) in enumerate(steps, start=1):
                self._insert(
                    "client_portal_steps",
                    {
                        "id": new_id("cps"),
                        "tenant_id": tenant_id,
                        "matter_id": matter_id,
                        "position": index,
                        "title": title,
                        "status": status,
                        "due_at": "",
                        "visible_to_client": 1,
                        "payload_json": "{}",
                        "created_at": now,
                    },
                )
        if self._count("client_portal_document_requests", tenant_id, "matter_id = ?", (matter_id,)) == 0:
            self.add_document_request(
                tenant_id,
                matter_id=matter_id,
                title="Documento di identità",
                description="Caricare un documento leggibile e in corso di validità.",
                required=True,
                accepted_types=["application/pdf", "image/jpeg", "image/png"],
            )
        if self._count("client_portal_consents", tenant_id, "client_id = ? AND matter_id = ?", (client_id, matter_id)) == 0:
            self.set_consent(
                tenant_id,
                client_id=client_id,
                matter_id=matter_id,
                consent_key="privacy_portale_cliente",
                version="1",
                accepted=False,
                payload={"title": "Informativa privacy Portale Cliente"},
                actor_type="sistema",
            )
        if self._count("client_portal_questionnaires", tenant_id, "matter_id = ?", (matter_id,)) == 0:
            self._insert(
                "client_portal_questionnaires",
                {
                    "id": new_id("cpq"),
                    "tenant_id": tenant_id,
                    "matter_id": matter_id,
                    "title": "Questionario iniziale pratica",
                    "status": "aperto",
                    "questions_json": json_dumps([
                        {"id": "obiettivo", "label": "Qual è l'obiettivo principale della pratica?", "type": "textarea"},
                        {"id": "urgenza", "label": "Ci sono scadenze o urgenze già note?", "type": "textarea"},
                    ]),
                    "responses_json": "{}",
                    "created_at": now,
                    "submitted_at": "",
                },
            )

    def create_invite(self, tenant_id: str, *, client_id: str, matter_id: str, expires_days: int = 14, channel: str = "email", notes: str = "", actor_id: str = "", metadata: dict[str, Any] | None = None, token_value: str = "") -> dict[str, Any]:
        if not client_id or not matter_id:
            raise ClientPortalError("Cliente e fascicolo sono obbligatori.")
        now = utc_now()
        token = str(token_value or "").strip() or secrets.token_urlsafe(32)
        record = {
            "id": new_id("cpi"),
            "tenant_id": tenant_id,
            "client_id": client_id,
            "matter_id": matter_id,
            "token_hash": token_hash(token),
            "status": "attivo",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=max(1, min(int(expires_days or 14), 90)))).replace(microsecond=0).isoformat(),
            "accepted_at": "",
            "revoked_at": "",
            "created_at": now,
            "created_by": actor_id,
            "last_sent_at": now,
            "channel": channel or "email",
            "notes": notes,
            "metadata_json": json_dumps(metadata or {}),
        }
        self._insert("client_portal_invites", record)
        self.record_audit(tenant_id, "studio", actor_id, "client_portal.invite.create", "invite", record["id"], {"clientId": client_id, "matterId": matter_id})
        return {"invite": record, "token": token}

    def find_invite_by_token(self, token: str) -> dict[str, Any] | None:
        digest = token_hash(token)
        if not digest:
            return None
        row = self._fetchone("SELECT * FROM client_portal_invites WHERE token_hash = ?", (digest,))
        return row or None

    def accept_invite(self, invite_id: str, *, actor_ip: str = "") -> dict[str, Any]:
        now = utc_now()
        row = self._fetchone("SELECT * FROM client_portal_invites WHERE id = ?", (invite_id,))
        if not row:
            raise ClientPortalError("Invito non trovato.")
        self._update("client_portal_invites", {"status": "accettato", "accepted_at": now}, "id = ?", (invite_id,))
        self.record_audit(row["tenant_id"], "cliente", row["client_id"], "client_portal.invite.accept", "invite", invite_id, {"ip": actor_ip})
        return self._fetchone("SELECT * FROM client_portal_invites WHERE id = ?", (invite_id,))

    def revoke_invite(self, tenant_id: str, invite_id: str, *, actor_id: str = "") -> dict[str, Any]:
        now = utc_now()
        row = self._fetchone("SELECT * FROM client_portal_invites WHERE tenant_id = ? AND id = ?", (tenant_id, invite_id))
        if not row:
            raise ClientPortalError("Invito non trovato.")
        self._update("client_portal_invites", {"status": "revocato", "revoked_at": now}, "id = ?", (invite_id,))
        self.record_audit(tenant_id, "studio", actor_id, "client_portal.invite.revoke", "invite", invite_id, {})
        return self._fetchone("SELECT * FROM client_portal_invites WHERE id = ?", (invite_id,))

    def add_document_request(self, tenant_id: str, *, matter_id: str, title: str, description: str = "", required: bool = True, due_at: str = "", accepted_types: list[str] | None = None) -> dict[str, Any]:
        record = {
            "id": new_id("cpdr"),
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "title": title,
            "description": description,
            "required": 1 if required else 0,
            "status": "richiesto",
            "due_at": due_at,
            "accepted_types_json": json_dumps(accepted_types or []),
            "created_at": utc_now(),
        }
        return self._insert("client_portal_document_requests", record)

    def add_document(self, tenant_id: str, *, matter_id: str, request_id: str, client_id: str, filename: str, stored_name: str, content_type: str, size_bytes: int, sha256: str) -> dict[str, Any]:
        record = {
            "id": new_id("cpd"),
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "request_id": request_id,
            "client_id": client_id,
            "filename": filename,
            "stored_name": stored_name,
            "content_type": content_type,
            "size_bytes": int(size_bytes or 0),
            "sha256": sha256,
            "status": "caricato",
            "uploaded_at": utc_now(),
            "reviewed_at": "",
            "review_note": "",
        }
        self._insert("client_portal_documents", record)
        if request_id:
            self._update("client_portal_document_requests", {"status": "ricevuto"}, "id = ? AND tenant_id = ?", (request_id, tenant_id))
        self._update_progress_from_activity(tenant_id, matter_id)
        self.record_audit(tenant_id, "cliente", client_id, "client_portal.document.upload", "document", record["id"], {"matterId": matter_id, "sha256": sha256})
        return record

    def add_signature_request(self, tenant_id: str, *, matter_id: str, title: str, description: str = "", document_id: str = "", due_at: str = "") -> dict[str, Any]:
        record = {
            "id": new_id("cpsr"),
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "document_id": document_id,
            "title": title,
            "description": description,
            "status": "da_firmare",
            "due_at": due_at,
            "created_at": utc_now(),
            "completed_at": "",
            "evidence_json": "{}",
        }
        return self._insert("client_portal_signature_requests", record)

    def complete_signature(self, tenant_id: str, signature_id: str, *, client_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
        row = self._fetchone("SELECT * FROM client_portal_signature_requests WHERE tenant_id = ? AND id = ?", (tenant_id, signature_id))
        if not row:
            raise ClientPortalError("Richiesta firma non trovata.")
        evidence_payload = {
            **dict(evidence or {}),
            "clientId": client_id,
            "completedAt": utc_now(),
        }
        self._update(
            "client_portal_signature_requests",
            {"status": "firmato", "completed_at": evidence_payload["completedAt"], "evidence_json": json_dumps(evidence_payload)},
            "id = ?",
            (signature_id,),
        )
        self._update_progress_from_activity(tenant_id, row["matter_id"])
        self.record_audit(tenant_id, "cliente", client_id, "client_portal.signature.complete", "signature", signature_id, {"matterId": row["matter_id"]})
        return self._fetchone("SELECT * FROM client_portal_signature_requests WHERE id = ?", (signature_id,))

    def set_consent(self, tenant_id: str, *, client_id: str, matter_id: str, consent_key: str, version: str = "1", accepted: bool, payload: dict[str, Any] | None = None, actor_type: str = "cliente") -> dict[str, Any]:
        existing = self._fetchone(
            "SELECT * FROM client_portal_consents WHERE tenant_id = ? AND client_id = ? AND matter_id = ? AND consent_key = ? AND version = ?",
            (tenant_id, client_id, matter_id, consent_key, version),
        )
        accepted_at = utc_now() if accepted else ""
        values = {
            "accepted": 1 if accepted else 0,
            "accepted_at": accepted_at,
            "payload_json": json_dumps(payload or {}),
        }
        if existing:
            self._update("client_portal_consents", values, "id = ?", (existing["id"],))
            record = self._fetchone("SELECT * FROM client_portal_consents WHERE id = ?", (existing["id"],))
        else:
            record = {
                "id": new_id("cpc"),
                "tenant_id": tenant_id,
                "client_id": client_id,
                "matter_id": matter_id,
                "consent_key": consent_key,
                "version": version,
                **values,
            }
            self._insert("client_portal_consents", record)
        if accepted:
            self._update_progress_from_activity(tenant_id, matter_id)
        self.record_audit(tenant_id, actor_type, client_id, "client_portal.consent.update", "consent", record["id"], {"accepted": bool(accepted), "key": consent_key})
        return record

    def add_message(self, tenant_id: str, *, matter_id: str, sender_type: str, sender_id: str, body: str, attachment_document_id: str = "") -> dict[str, Any]:
        text = " ".join(str(body or "").split()).strip()
        if not text:
            raise ClientPortalError("Messaggio vuoto.")
        record = {
            "id": new_id("cpmg"),
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "sender_type": sender_type,
            "sender_id": sender_id,
            "body": text[:4000],
            "attachment_document_id": attachment_document_id,
            "created_at": utc_now(),
            "read_at": "",
        }
        self._insert("client_portal_messages", record)
        self.record_audit(tenant_id, sender_type, sender_id, "client_portal.message.create", "message", record["id"], {"matterId": matter_id})
        return record

    def add_appointment(self, tenant_id: str, *, matter_id: str, title: str, starts_at: str, ends_at: str = "", location: str = "", video_url: str = "") -> dict[str, Any]:
        record = {
            "id": new_id("cpa"),
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "title": title,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "status": "proposto",
            "location": location,
            "video_url": video_url,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        return self._insert("client_portal_appointments", record)

    def update_appointment_status(self, tenant_id: str, appointment_id: str, *, status: str, actor_id: str = "", actor_type: str = "studio") -> dict[str, Any]:
        row = self._fetchone("SELECT * FROM client_portal_appointments WHERE tenant_id = ? AND id = ?", (tenant_id, appointment_id))
        if not row:
            raise ClientPortalError("Appuntamento non trovato.")
        self._update("client_portal_appointments", {"status": status, "updated_at": utc_now()}, "tenant_id = ? AND id = ?", (tenant_id, appointment_id))
        self.record_audit(tenant_id, actor_type, actor_id, "client_portal.appointment.update", "appointment", appointment_id, {"status": status})
        return self._fetchone("SELECT * FROM client_portal_appointments WHERE tenant_id = ? AND id = ?", (tenant_id, appointment_id))

    def add_notification(self, tenant_id: str, *, client_id: str, matter_id: str, title: str, body: str = "", kind: str = "info", priority: str = "normale", href: str = "", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        record = {
            "id": new_id("cpn"),
            "tenant_id": tenant_id,
            "client_id": client_id,
            "matter_id": matter_id,
            "title": title,
            "body": body,
            "kind": kind,
            "priority": priority,
            "href": href,
            "read_at": "",
            "created_at": utc_now(),
            "payload_json": json_dumps(payload or {}),
        }
        return self._insert("client_portal_notifications", record)

    def mark_notification_read(self, tenant_id: str, notification_id: str, *, client_id: str) -> dict[str, Any]:
        row = self._fetchone(
            "SELECT * FROM client_portal_notifications WHERE tenant_id = ? AND id = ? AND client_id = ?",
            (tenant_id, notification_id, client_id),
        )
        if not row:
            raise ClientPortalError("Notifica non trovata.")
        self._update("client_portal_notifications", {"read_at": utc_now()}, "id = ?", (notification_id,))
        return self._fetchone("SELECT * FROM client_portal_notifications WHERE id = ?", (notification_id,))

    def update_preferences(self, tenant_id: str, *, client_id: str, preferences: dict[str, Any]) -> dict[str, Any]:
        profile = self.get_profile(tenant_id, client_id)
        if not profile:
            raise ClientPortalError("Profilo cliente non trovato.")
        current = json_loads(profile.get("preferences_json"), {})
        if not isinstance(current, dict):
            current = {}
        current.update({key: bool(value) if isinstance(value, bool) else value for key, value in dict(preferences or {}).items()})
        self._update("client_portal_profiles", {"preferences_json": json_dumps(current), "updated_at": utc_now()}, "id = ?", (profile["id"],))
        return self.get_profile(tenant_id, client_id) or profile

    def update_profile_fields(self, tenant_id: str, *, client_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "display_name": "display_name",
            "email": "email",
            "phone": "phone",
            "fiscal_code": "fiscal_code",
            "identity_expires_at": "identity_expires_at",
        }
        values = {
            db_key: " ".join(str(fields.get(api_key) or "").split()).strip()
            for api_key, db_key in allowed.items()
            if api_key in fields
        }
        if values:
            values["updated_at"] = utc_now()
            self._update("client_portal_profiles", values, "tenant_id = ? AND client_id = ?", (tenant_id, client_id))
        profile = self.get_profile(tenant_id, client_id)
        if not profile:
            raise ClientPortalError("Profilo cliente non trovato.")
        self.record_audit(tenant_id, "cliente", client_id, "client_portal.profile.update", "profile", profile["id"], {"fields": sorted(values)})
        return profile

    def submit_questionnaire(self, tenant_id: str, questionnaire_id: str, *, matter_id: str, responses: dict[str, Any], client_id: str) -> dict[str, Any]:
        row = self._fetchone(
            "SELECT * FROM client_portal_questionnaires WHERE tenant_id = ? AND id = ? AND matter_id = ?",
            (tenant_id, questionnaire_id, matter_id),
        )
        if not row:
            raise ClientPortalError("Questionario non trovato.")
        self._update(
            "client_portal_questionnaires",
            {"status": "inviato", "responses_json": json_dumps(responses or {}), "submitted_at": utc_now()},
            "id = ?",
            (questionnaire_id,),
        )
        self.record_audit(tenant_id, "cliente", client_id, "client_portal.questionnaire.submit", "questionnaire", questionnaire_id, {"matterId": matter_id})
        return self._fetchone("SELECT * FROM client_portal_questionnaires WHERE id = ?", (questionnaire_id,))

    def submit_survey(self, tenant_id: str, *, matter_id: str, rating: int, comment: str, client_id: str) -> dict[str, Any]:
        record = {
            "id": new_id("cpsv"),
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "rating": max(0, min(int(rating or 0), 5)),
            "comment": str(comment or "").strip()[:2000],
            "submitted_at": utc_now(),
            "payload_json": json_dumps({"clientId": client_id}),
        }
        self._insert("client_portal_surveys", record)
        self.record_audit(tenant_id, "cliente", client_id, "client_portal.survey.submit", "survey", record["id"], {"matterId": matter_id})
        return record

    def create_evidence_pack(self, tenant_id: str, *, matter_id: str, actor_id: str = "") -> dict[str, Any]:
        summary = self.matter_snapshot(tenant_id, matter_id)
        minimized = {
            "matter": summary.get("matter"),
            "documents": len(summary.get("documents") or []),
            "signatures": len(summary.get("signatures") or []),
            "messages": len(summary.get("messages") or []),
            "consents": len(summary.get("consents") or []),
            "appointments": len(summary.get("appointments") or []),
            "createdAt": utc_now(),
        }
        record = {
            "id": new_id("cpep"),
            "tenant_id": tenant_id,
            "matter_id": matter_id,
            "status": "preparato",
            "summary_json": json_dumps(minimized),
            "created_at": minimized["createdAt"],
            "created_by": actor_id,
        }
        self._insert("client_portal_evidence_packs", record)
        self.record_audit(tenant_id, "studio", actor_id, "client_portal.evidence_pack.create", "evidence_pack", record["id"], {"matterId": matter_id})
        return record

    def record_audit(self, tenant_id: str, actor_type: str, actor_id: str, action: str, resource_type: str, resource_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        record = {
            "id": new_id("cpae"),
            "tenant_id": tenant_id,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "created_at": utc_now(),
            "details_json": json_dumps(details or {}),
        }
        self._insert("client_portal_audit_events", record)
        return record

    def _list(self, table: str, tenant_id: str, where: str = "", params: Iterable[Any] = (), order: str = "created_at DESC", limit: int = 200) -> list[dict[str, Any]]:
        clause = "tenant_id = ?"
        if where:
            clause += f" AND {where}"
        return self._fetchall(
            f"SELECT * FROM {table} WHERE {clause} ORDER BY {order} LIMIT ?",
            (tenant_id, *tuple(params), int(limit)),
        )

    def _update_progress_from_activity(self, tenant_id: str, matter_id: str) -> None:
        consents_ok = self._count("client_portal_consents", tenant_id, "matter_id = ? AND accepted = 1", (matter_id,)) > 0
        docs_ok = self._count("client_portal_documents", tenant_id, "matter_id = ?", (matter_id,)) > 0
        signatures_pending = self._count("client_portal_signature_requests", tenant_id, "matter_id = ? AND status <> ?", (matter_id, "firmato"))
        messages = self._count("client_portal_messages", tenant_id, "matter_id = ?", (matter_id,))
        progress = 15 + (25 if consents_ok else 0) + (25 if docs_ok else 0) + (20 if signatures_pending == 0 else 0) + (15 if messages else 0)
        progress = max(0, min(progress, 100))
        next_action = "Aprire la chat con il cliente o preparare il pacchetto finale." if progress >= 80 else "Completare le attività richieste dal portale cliente."
        self._update("client_portal_matters", {"progress": progress, "next_action": next_action, "updated_at": utc_now()}, "tenant_id = ? AND id = ?", (tenant_id, matter_id))

    def matter_snapshot(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        matter = self.get_matter(tenant_id, matter_id) or {}
        client_id = str(matter.get("client_id") or "")
        return {
            "matter": matter,
            "profile": self.get_profile(tenant_id, client_id) or {},
            "steps": self._list("client_portal_steps", tenant_id, "matter_id = ?", (matter_id,), order="position ASC", limit=50),
            "documentRequests": self._list("client_portal_document_requests", tenant_id, "matter_id = ?", (matter_id,), order="created_at ASC", limit=80),
            "documents": self._list("client_portal_documents", tenant_id, "matter_id = ?", (matter_id,), order="uploaded_at DESC", limit=100),
            "signatures": self._list("client_portal_signature_requests", tenant_id, "matter_id = ?", (matter_id,), order="created_at DESC", limit=100),
            "consents": self._list("client_portal_consents", tenant_id, "matter_id = ?", (matter_id,), order="consent_key ASC", limit=50),
            "messages": self._list("client_portal_messages", tenant_id, "matter_id = ?", (matter_id,), order="created_at ASC", limit=200),
            "appointments": self._list("client_portal_appointments", tenant_id, "matter_id = ?", (matter_id,), order="starts_at ASC", limit=80),
            "questionnaires": self._list("client_portal_questionnaires", tenant_id, "matter_id = ?", (matter_id,), order="created_at ASC", limit=50),
            "surveys": self._list("client_portal_surveys", tenant_id, "matter_id = ?", (matter_id,), order="submitted_at DESC", limit=50),
            "evidencePacks": self._list("client_portal_evidence_packs", tenant_id, "matter_id = ?", (matter_id,), order="created_at DESC", limit=50),
        }

    def dashboard_snapshot(self, tenant_id: str) -> dict[str, Any]:
        matters = self._list("client_portal_matters", tenant_id, order="updated_at DESC", limit=200)
        profiles = self._list("client_portal_profiles", tenant_id, order="display_name ASC", limit=200)
        invites = self._list("client_portal_invites", tenant_id, order="created_at DESC", limit=200)
        notifications = self._list("client_portal_notifications", tenant_id, order="created_at DESC", limit=100)
        return {
            "profiles": profiles,
            "matters": matters,
            "invites": invites,
            "documentRequests": self._list("client_portal_document_requests", tenant_id, order="created_at DESC", limit=200),
            "documents": self._list("client_portal_documents", tenant_id, order="uploaded_at DESC", limit=200),
            "signatures": self._list("client_portal_signature_requests", tenant_id, order="created_at DESC", limit=200),
            "messages": self._list("client_portal_messages", tenant_id, order="created_at DESC", limit=200),
            "appointments": self._list("client_portal_appointments", tenant_id, order="starts_at ASC", limit=200),
            "notifications": notifications,
            "questionnaires": self._list("client_portal_questionnaires", tenant_id, order="created_at DESC", limit=200),
            "surveys": self._list("client_portal_surveys", tenant_id, order="submitted_at DESC", limit=100),
            "evidencePacks": self._list("client_portal_evidence_packs", tenant_id, order="created_at DESC", limit=100),
            "settings": self.get_settings(tenant_id),
            "summary": {
                "clients": len(profiles),
                "matters": len(matters),
                "activeInvites": sum(1 for row in invites if row.get("status") == "attivo"),
                "pendingDocuments": self._count("client_portal_document_requests", tenant_id, "status = ?", ("richiesto",)),
                "pendingSignatures": self._count("client_portal_signature_requests", tenant_id, "status = ?", ("da_firmare",)),
                "unreadNotifications": sum(1 for row in notifications if not row.get("read_at")),
            },
        }

    def client_snapshot_by_invite(self, invite: dict[str, Any]) -> dict[str, Any]:
        tenant_id = str(invite.get("tenant_id") or "")
        matter_id = str(invite.get("matter_id") or "")
        client_id = str(invite.get("client_id") or "")
        snapshot = self.matter_snapshot(tenant_id, matter_id)
        snapshot["invite"] = invite
        snapshot["notifications"] = self._list("client_portal_notifications", tenant_id, "client_id = ?", (client_id,), order="created_at DESC", limit=100)
        snapshot["settings"] = self.get_settings(tenant_id)
        return snapshot
