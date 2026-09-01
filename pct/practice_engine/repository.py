"""Repository SQL tenant-aware per il presidio procedurale del fascicolo.
SQLite o PostgreSQL sono la fonte di verità. Il JSON storico resta soltanto
un mirror rigenerabile e una sorgente d'importazione una tantum: non viene
mai letto per decidere lo stato operativo quando l'archivio SQL è disponibile.
"""

from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any
from .models import (
    AuditEvent, ChecklistItem, DepositReceipt, DepositSession, DocumentSlot, EvidencePack, PracticeProfile,
    PracticeState, SlotStatus, TimelineEvent, ValidationResult, dataclass_from_dict, new_id, utc_now,
)

STORE_KEYS = [
    "practice_profiles", "practice_requirements", "practice_document_slots", "practice_checklist_items",
    "practice_validation_results", "practice_state_history", "deposit_sessions", "deposit_receipts",
    "deposit_timeline_events", "evidence_packs", "audit_events",
]

class PracticeEngineRepository:
    def __init__(self, db_path: str, *, studio_db: Any | None = None):
        self.db_path = Path(db_path)
        self.root_dir = self.db_path.parent
        self.receipts_dir = self.root_dir / "receipts"
        self.evidence_dir = self.root_dir / "evidence_packs"
        for folder in (self.root_dir, self.receipts_dir, self.evidence_dir):
            folder.mkdir(parents=True, exist_ok=True)
        self.studio_db = studio_db or self._default_studio_db()
        self._suspend_persist = False
        self.last_mirror_error = ""
        self._ensure_sql_schema()
        self._bootstrap_sql_from_legacy_mirror()
        self._data = self._load()
    @classmethod
    def from_fascicoli_db(cls, fascicoli_db_path: str, *, studio_db: Any | None = None) -> "PracticeEngineRepository":
        base = Path(fascicoli_db_path).parent
        return cls(str(base / "practice_engine" / "practice_engine.json"), studio_db=studio_db)
    @property
    def source_of_truth(self) -> str:
        return str(getattr(self.studio_db, "backend_kind", "sqlite") or "sqlite")
    def _default_studio_db(self) -> Any:
        """Crea il backend SQL solo per i chiamanti legacy senza injection.
        I runtime Flask passano sempre il backend del tenant. Il percorso di
        compatibilità è riservato a tool e test e conserva la stessa root
        ``studio.db`` del fascicolo, non un database JSON parallelo.
        """
        from pct.storage import StudioDB
        if self.root_dir.name == "practice_engine" and self.root_dir.parent.name == "fascicoli":
            root = self.root_dir.parent.parent
        else:
            root = self.root_dir.parent
        return StudioDB.get(str(root / "studio.db"))
    def _empty(self) -> dict[str, Any]:
        return {key: [] for key in STORE_KEYS}
    def _legacy_data(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return self._empty()
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return self._empty()
        except (OSError, json.JSONDecodeError):
            return self._empty()
        data = self._empty()
        for key in STORE_KEYS:
            rows = raw.get(key, [])
            data[key] = rows if isinstance(rows, list) else []
        return data
    @staticmethod
    def _json_value(raw: Any, default: Any) -> Any:
        if isinstance(raw, (dict, list)):
            return raw
        if raw in (None, ""):
            return default
        try:
            parsed = json.loads(str(raw))
        except (TypeError, ValueError):
            return default
        return parsed if isinstance(parsed, type(default)) else default
    @staticmethod
    def _row_value(row: Any, key: str, default: Any = "") -> Any:
        try:
            value = row[key]
        except (KeyError, IndexError, TypeError):
            return default
        return default if value is None else value
    def _ensure_sql_schema(self) -> None:
        sql_dir = Path(__file__).resolve().parents[1] / "sql"
        is_postgres = self.source_of_truth == "postgresql"
        migration = sql_dir / ("20260504_practice_engine_postgres.sql" if is_postgres else "20260504_practice_engine.sql")
        script = migration.read_text(encoding="utf-8")
        if is_postgres:
            with self.studio_db.raw_conn.cursor() as cursor:
                cursor.execute(script)
            self.studio_db.raw_conn.commit()
            return
        self.studio_db.conn.executescript(script)
        self.studio_db.conn.commit()
    def _sql_has_records(self) -> bool:
        tables = (
            "practice_profiles", "practice_requirements", "practice_document_slots",
            "practice_checklist_items", "practice_validation_results", "practice_state_history",
            "deposit_sessions", "deposit_receipts", "deposit_timeline_events", "evidence_packs",
            "practice_audit_events",
        )
        for table in tables:
            row = self.studio_db.conn.execute(f"SELECT 1 AS present FROM {table} LIMIT 1").fetchone()
            if row:
                return True
        return False
    @staticmethod
    def _legacy_row_identity(collection: str, row: dict[str, Any]) -> tuple[str, ...]:
        """Identità stabile per l'importazione una tantum del mirror storico.
        I record SQL restano prioritari. L'identità per fascicolo evita che un
        vecchio ``id`` condiviso fra mirror diversi possa sovrascrivere un
        presidio già consolidato nello studio.
        """
        fascicolo_id = str(row.get("fascicolo_id") or "")
        if collection == "practice_profiles":
            return (collection, fascicolo_id)
        if collection == "practice_requirements":
            return (collection, fascicolo_id, str(row.get("profile_id") or ""), str(row.get("key") or ""))
        if collection == "practice_document_slots":
            return (collection, fascicolo_id, str(row.get("slot_key") or ""))
        if collection == "practice_checklist_items":
            return (collection, fascicolo_id, str(row.get("key") or ""))
        if collection == "practice_validation_results":
            return (
                collection,
                fascicolo_id,
                str(row.get("scope") or ""),
                str(row.get("slot_key") or ""),
                str(row.get("key") or ""),
                str(row.get("created_at") or ""),
            )
        return (collection, str(row.get("id") or ""))
    def _bootstrap_sql_from_legacy_mirror(self) -> None:
        """Importa dal mirror solo i record ancora assenti dalla fonte SQL.
        Il tenant può avere già altri fascicoli in SQL mentre un vecchio mirror
        contiene il primo presidio di una pratica diversa. Saltare tutto il
        mirror in quel caso perderebbe dati; sostituire SQL con JSON sarebbe
        invece una regressione. Il merge è quindi monotono: SQL vince sempre e
        il JSON serve una sola volta esclusivamente per colmare record assenti.
        """
        legacy = self._legacy_data()
        if not any(legacy.values()):
            return
        current = self._load()
        merged = {key: list(current.get(key, [])) for key in STORE_KEYS}
        changed = False
        for collection in STORE_KEYS:
            known = {
                self._legacy_row_identity(collection, row)
                for row in merged[collection]
                if isinstance(row, dict)
            }
            for raw_row in legacy.get(collection, []):
                if not isinstance(raw_row, dict):
                    continue
                identity = self._legacy_row_identity(collection, raw_row)
                if identity in known:
                    continue
                merged[collection].append(dict(raw_row))
                known.add(identity)
                changed = True
        if changed:
            self._data = self._normalize_legacy_profile_ids(merged)
            self._persist_all()
    @staticmethod
    def _normalize_legacy_profile_ids(data: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        """Rende univoci gli identificativi legacy riusati fra fascicoli.
        I vecchi mirror usavano in alcuni casi il *codice* del profilo anche
        come chiave primaria. Lo stesso codice puo' essere applicato a piu'
        fascicoli e non e' quindi una chiave SQL valida. La normalizzazione
        interviene soltanto sugli id duplicati e riallinea i riferimenti
        ``profile_id`` delle entita' appartenenti allo stesso fascicolo.
        """
        profiles = [row for row in data.get("practice_profiles", []) if isinstance(row, dict)]
        occurrences: dict[str, int] = {}
        for row in profiles:
            profile_id = str(row.get("id") or "").strip()
            if profile_id:
                occurrences[profile_id] = occurrences.get(profile_id, 0) + 1
        replacements: dict[tuple[str, str], str] = {}
        for row in profiles:
            profile_id = str(row.get("id") or "").strip()
            fascicolo_id = str(row.get("fascicolo_id") or "").strip()
            if not profile_id or occurrences.get(profile_id, 0) < 2:
                continue
            canonical_id = f"profile::{fascicolo_id}::{profile_id}"
            row["id"] = canonical_id
            replacements[(fascicolo_id, profile_id)] = canonical_id
        if not replacements:
            return data
        for collection in (
            "practice_requirements",
            "practice_document_slots",
            "practice_checklist_items",
            "deposit_sessions",
        ):
            for row in data.get(collection, []):
                if not isinstance(row, dict):
                    continue
                key = (str(row.get("fascicolo_id") or "").strip(), str(row.get("profile_id") or "").strip())
                replacement = replacements.get(key)
                if replacement:
                    row["profile_id"] = replacement
        return data

    def _load(self) -> dict[str, Any]:
        data = self._empty()
        conn = self.studio_db.conn
        for row in conn.execute("SELECT * FROM practice_profiles ORDER BY applied_at, id").fetchall():
            payload = self._json_value(self._row_value(row, "payload_json", "{}"), {})
            payload.update({
                "id": self._row_value(row, "id", payload.get("id", "")),
                "fascicolo_id": self._row_value(row, "fascicolo_id", payload.get("fascicolo_id", "")),
                "code": self._row_value(row, "code", payload.get("code", "")),
                "applied_at": self._row_value(row, "applied_at", payload.get("applied_at", "")),
                "applied_by": self._row_value(row, "applied_by", payload.get("applied_by", "")),
                "manual_reason": self._row_value(row, "manual_reason", payload.get("manual_reason", "")),
            })
            data["practice_profiles"].append(payload)
        for row in conn.execute("SELECT * FROM practice_requirements ORDER BY sort_order, id").fetchall():
            data["practice_requirements"].append({
                "id": self._row_value(row, "id"), "fascicolo_id": self._row_value(row, "fascicolo_id"),
                "profile_id": self._row_value(row, "profile_id"), "key": self._row_value(row, "requirement_key"),
                "label": self._row_value(row, "label"), "required": bool(self._row_value(row, "required", True)),
                "blocking": bool(self._row_value(row, "blocking", True)), "source": self._row_value(row, "source"),
                "message": self._row_value(row, "message"), "suggested_action": self._row_value(row, "suggested_action"),
                "sort_order": int(self._row_value(row, "sort_order", 0) or 0),
            })
        for row in conn.execute("SELECT * FROM practice_document_slots ORDER BY sort_order, id").fetchall():
            data["practice_document_slots"].append({
                "id": self._row_value(row, "id"), "fascicolo_id": self._row_value(row, "fascicolo_id"),
                "profile_id": self._row_value(row, "profile_id"), "slot_key": self._row_value(row, "slot_key"),
                "label": self._row_value(row, "label"), "type": self._row_value(row, "type"),
                "required": bool(self._row_value(row, "required", True)), "blocking": bool(self._row_value(row, "blocking", True)),
                "document_id": self._row_value(row, "document_id"), "status": self._row_value(row, "status"),
                "validators": self._json_value(self._row_value(row, "validators_json", "[]"), []),
                "last_validation_at": self._row_value(row, "last_validation_at"), "message": self._row_value(row, "message"),
                "suggested_action": self._row_value(row, "suggested_action"), "sort_order": int(self._row_value(row, "sort_order", 0) or 0),
            })
        for row in conn.execute("SELECT * FROM practice_checklist_items ORDER BY sort_order, id").fetchall():
            data["practice_checklist_items"].append({
                "id": self._row_value(row, "id"), "fascicolo_id": self._row_value(row, "fascicolo_id"),
                "profile_id": self._row_value(row, "profile_id"), "key": self._row_value(row, "item_key"),
                "label": self._row_value(row, "label"), "required": bool(self._row_value(row, "required", True)),
                "blocking": bool(self._row_value(row, "blocking", True)), "status": self._row_value(row, "status"),
                "message": self._row_value(row, "message"), "suggested_action": self._row_value(row, "suggested_action"),
                "sort_order": int(self._row_value(row, "sort_order", 0) or 0), "source": self._row_value(row, "source"),
            })
        for row in conn.execute("SELECT * FROM practice_validation_results ORDER BY id").fetchall():
            data["practice_validation_results"].append({
                "key": self._row_value(row, "validator_key"), "status": self._row_value(row, "status"),
                "severity": self._row_value(row, "severity"), "message": self._row_value(row, "message"),
                "technical_detail": self._row_value(row, "technical_detail"), "suggested_action": self._row_value(row, "suggested_action"),
                "source": self._row_value(row, "source"), "evidence": self._json_value(self._row_value(row, "evidence_json", "{}"), {}),
                "created_at": self._row_value(row, "created_at"), "fascicolo_id": self._row_value(row, "fascicolo_id"),
                "scope": self._row_value(row, "scope"), "slot_key": self._row_value(row, "slot_key"),
            })
        for row in conn.execute("SELECT * FROM practice_state_history ORDER BY created_at, id").fetchall():
            data["practice_state_history"].append({
                "id": self._row_value(row, "id"), "fascicolo_id": self._row_value(row, "fascicolo_id"),
                "state": self._row_value(row, "state"), "actor": self._row_value(row, "actor"),
                "reason": self._row_value(row, "reason"), "payload": self._json_value(self._row_value(row, "payload_json", "{}"), {}),
                "created_at": self._row_value(row, "created_at"),
            })
        session_rows = conn.execute("SELECT * FROM deposit_sessions ORDER BY created_at, id").fetchall()
        receipt_rows = conn.execute("SELECT * FROM deposit_receipts ORDER BY imported_at, id").fetchall()
        timeline_rows = conn.execute("SELECT * FROM deposit_timeline_events ORDER BY created_at, id").fetchall()
        evidence_rows = conn.execute("SELECT * FROM evidence_packs ORDER BY created_at, id").fetchall()
        audit_rows = conn.execute("SELECT * FROM practice_audit_events ORDER BY created_at, id").fetchall()
        data["deposit_sessions"] = [self._session_row(row) for row in session_rows]
        data["deposit_receipts"] = [self._receipt_row(row) for row in receipt_rows]
        data["deposit_timeline_events"] = [self._timeline_row(row) for row in timeline_rows]
        data["evidence_packs"] = [self._evidence_row(row) for row in evidence_rows]
        data["audit_events"] = [self._audit_row(row) for row in audit_rows]
        return data
    def _session_row(self, row: Any) -> dict[str, Any]:
        return {"id": self._row_value(row, "id"), "fascicolo_id": self._row_value(row, "fascicolo_id"), "profile_id": self._row_value(row, "profile_id"), "channel": self._row_value(row, "channel"), "status": self._row_value(row, "status"), "transport_mode": self._row_value(row, "transport_mode"), "simulated": bool(self._row_value(row, "simulated", False)), "real_transport": bool(self._row_value(row, "real_transport", False)), "predeposit_status": self._row_value(row, "predeposit_status"), "messages": self._json_value(self._row_value(row, "messages_json", "[]"), []), "created_at": self._row_value(row, "created_at"), "updated_at": self._row_value(row, "updated_at"), "sent_at": self._row_value(row, "sent_at"), "acquired_at": self._row_value(row, "acquired_at"), "final_receipt_id": self._row_value(row, "final_receipt_id")}
    def _receipt_row(self, row: Any) -> dict[str, Any]:
        return {"id": self._row_value(row, "id"), "deposit_session_id": self._row_value(row, "deposit_session_id"), "fascicolo_id": self._row_value(row, "fascicolo_id"), "receipt_type": self._row_value(row, "receipt_type"), "status": self._row_value(row, "status"), "positive": bool(self._row_value(row, "positive", False)), "source": self._row_value(row, "source"), "original_name": self._row_value(row, "original_name"), "original_hash_sha256": self._row_value(row, "original_hash_sha256"), "original_path": self._row_value(row, "original_path"), "payload": self._json_value(self._row_value(row, "payload_json", "{}"), {}), "imported_at": self._row_value(row, "imported_at"), "message": self._row_value(row, "message")}
    def _timeline_row(self, row: Any) -> dict[str, Any]:
        return {"id": self._row_value(row, "id"), "deposit_session_id": self._row_value(row, "deposit_session_id"), "fascicolo_id": self._row_value(row, "fascicolo_id"), "event_type": self._row_value(row, "event_type"), "status": self._row_value(row, "status"), "message": self._row_value(row, "message"), "created_at": self._row_value(row, "created_at"), "evidence_ref": self._row_value(row, "evidence_ref")}
    def _evidence_row(self, row: Any) -> dict[str, Any]:
        return {"id": self._row_value(row, "id"), "fascicolo_id": self._row_value(row, "fascicolo_id"), "deposit_session_id": self._row_value(row, "deposit_session_id"), "path": self._row_value(row, "path"), "hash_sha256": self._row_value(row, "hash_sha256"), "created_at": self._row_value(row, "created_at"), "available": bool(self._row_value(row, "available", True))}
    def _audit_row(self, row: Any) -> dict[str, Any]:
        return {"id": self._row_value(row, "id"), "fascicolo_id": self._row_value(row, "fascicolo_id"), "event_type": self._row_value(row, "event_type"), "actor": self._row_value(row, "actor"), "message": self._row_value(row, "message"), "reason": self._row_value(row, "reason"), "payload": self._json_value(self._row_value(row, "payload_json", "{}"), {}), "created_at": self._row_value(row, "created_at")}
    def _json_dump(self, value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))
    def _commit(self) -> None:
        raw = getattr(self.studio_db, "raw_conn", None)
        (raw or self.studio_db.conn).commit()
    def _rollback(self) -> None:
        raw = getattr(self.studio_db, "raw_conn", None)
        (raw or self.studio_db.conn).rollback()
    def _persist_all(self) -> None:
        conn = self.studio_db.conn
        tables = ("practice_profiles", "practice_requirements", "practice_document_slots", "practice_checklist_items", "practice_validation_results", "practice_state_history", "deposit_sessions", "deposit_receipts", "deposit_timeline_events", "evidence_packs", "practice_audit_events")
        try:
            conn.execute("BEGIN")
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
            self._insert_all(conn)
            self._commit()
        except Exception:
            self._rollback()
            raise
    def _insert_all(self, conn: Any) -> None:
        for row in self._data["practice_profiles"]:
            profile_id = str(row.get("id") or new_id("profile"))
            conn.execute("INSERT INTO practice_profiles (id,fascicolo_id,code,name,area,channel,registry,workflow_code,practice_id,procedure_code,version,source,payload_json,applied_at,applied_by,manual_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (profile_id, row.get("fascicolo_id", ""), row.get("code", ""), row.get("name", ""), row.get("area", ""), row.get("channel", ""), row.get("registry", ""), row.get("workflow_code", ""), row.get("practice_id", ""), row.get("procedure_code", ""), row.get("version", "1.0"), row.get("source", "legal_platform_catalog"), self._json_dump(row), row.get("applied_at", utc_now()), row.get("applied_by", ""), row.get("manual_reason", "")))
        for row in self._data["practice_requirements"]:
            conn.execute("INSERT INTO practice_requirements (id,fascicolo_id,profile_id,requirement_key,label,required,blocking,source,message,suggested_action,sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("req"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("key", ""), row.get("label", ""), bool(row.get("required", True)), bool(row.get("blocking", True)), row.get("source", ""), row.get("message", ""), row.get("suggested_action", ""), int(row.get("sort_order", 0) or 0)))
        for row in self._data["practice_document_slots"]:
            conn.execute("INSERT INTO practice_document_slots (id,fascicolo_id,profile_id,slot_key,label,type,required,blocking,document_id,status,validators_json,last_validation_at,message,suggested_action,sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("slot"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("slot_key", ""), row.get("label", ""), row.get("type", "ALTRO"), bool(row.get("required", True)), bool(row.get("blocking", True)), row.get("document_id", ""), row.get("status", SlotStatus.MANCANTE.value), self._json_dump(row.get("validators", [])), row.get("last_validation_at", ""), row.get("message", ""), row.get("suggested_action", ""), int(row.get("sort_order", 0) or 0)))
        for row in self._data["practice_checklist_items"]:
            conn.execute("INSERT INTO practice_checklist_items (id,fascicolo_id,profile_id,item_key,label,required,blocking,status,message,suggested_action,sort_order,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("chk"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("key", ""), row.get("label", ""), bool(row.get("required", True)), bool(row.get("blocking", True)), row.get("status", "DA_COMPLETARE"), row.get("message", ""), row.get("suggested_action", ""), int(row.get("sort_order", 0) or 0), row.get("source", "")))
        for row in self._data["practice_validation_results"]:
            conn.execute("INSERT INTO practice_validation_results (fascicolo_id,scope,slot_key,validator_key,status,severity,message,technical_detail,suggested_action,source,evidence_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("fascicolo_id", ""), row.get("scope", "fascicolo"), row.get("slot_key", ""), row.get("key", ""), row.get("status", "PENDING"), row.get("severity", "INFO"), row.get("message", ""), row.get("technical_detail", ""), row.get("suggested_action", ""), row.get("source", "practice_engine"), self._json_dump(row.get("evidence", {})), row.get("created_at", utc_now())))
        for row in self._data["practice_state_history"]:
            conn.execute("INSERT INTO practice_state_history (id,fascicolo_id,state,actor,reason,payload_json,created_at) VALUES (?,?,?,?,?,?,?)", (row.get("id") or new_id("state"), row.get("fascicolo_id", ""), row.get("state", ""), row.get("actor", ""), row.get("reason", ""), self._json_dump(row.get("payload", {})), row.get("created_at", utc_now())))
        for row in self._data["deposit_sessions"]:
            conn.execute("INSERT INTO deposit_sessions (id,fascicolo_id,profile_id,channel,status,transport_mode,simulated,real_transport,predeposit_status,messages_json,created_at,updated_at,sent_at,acquired_at,final_receipt_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("dep"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("channel", ""), row.get("status", "NON_INVIATO"), row.get("transport_mode", "non_configurato"), bool(row.get("simulated", False)), bool(row.get("real_transport", False)), row.get("predeposit_status", "NON_ESEGUITO"), self._json_dump(row.get("messages", [])), row.get("created_at", utc_now()), row.get("updated_at", utc_now()), row.get("sent_at", ""), row.get("acquired_at", ""), row.get("final_receipt_id", "")))
        for row in self._data["deposit_receipts"]:
            conn.execute("INSERT INTO deposit_receipts (id,deposit_session_id,fascicolo_id,receipt_type,status,positive,source,original_name,original_hash_sha256,original_path,payload_json,imported_at,message) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("receipt"), row.get("deposit_session_id", ""), row.get("fascicolo_id", ""), row.get("receipt_type", "ALTRO"), row.get("status", ""), bool(row.get("positive", False)), row.get("source", "import_guidato"), row.get("original_name", ""), row.get("original_hash_sha256", ""), row.get("original_path", ""), self._json_dump(row.get("payload", {})), row.get("imported_at", utc_now()), row.get("message", "")))
        for row in self._data["deposit_timeline_events"]:
            conn.execute("INSERT INTO deposit_timeline_events (id,deposit_session_id,fascicolo_id,event_type,status,message,created_at,evidence_ref) VALUES (?,?,?,?,?,?,?,?)", (row.get("id") or new_id("evt"), row.get("deposit_session_id", ""), row.get("fascicolo_id", ""), row.get("event_type", ""), row.get("status", ""), row.get("message", ""), row.get("created_at", utc_now()), row.get("evidence_ref", "")))
        for row in self._data["evidence_packs"]:
            conn.execute("INSERT INTO evidence_packs (id,fascicolo_id,deposit_session_id,path,hash_sha256,created_at,available) VALUES (?,?,?,?,?,?,?)", (row.get("id") or new_id("evidence"), row.get("fascicolo_id", ""), row.get("deposit_session_id", ""), row.get("path", ""), row.get("hash_sha256", ""), row.get("created_at", utc_now()), bool(row.get("available", True))))
        for row in self._data["audit_events"]:
            conn.execute("INSERT INTO practice_audit_events (id,fascicolo_id,event_type,actor,message,reason,payload_json,created_at) VALUES (?,?,?,?,?,?,?,?)", (row.get("id") or new_id("audit"), row.get("fascicolo_id", ""), row.get("event_type", ""), row.get("actor", ""), row.get("message", ""), row.get("reason", ""), self._json_dump(row.get("payload", {})), row.get("created_at", utc_now())))
    def _write_legacy_mirror(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.db_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.db_path)
            self.last_mirror_error = ""
        except OSError as exc:
            self.last_mirror_error = str(exc)
    def _save(self) -> None:
        if self._suspend_persist:
            return
        self._persist_all()
        self._write_legacy_mirror()
    def reload(self) -> None:
        self._data = self._load()

    def apply_profile(
        self,
        fascicolo_id: str,
        profile: PracticeProfile,
        *,
        actor: str = "",
        reason: str = "",
        reset: bool = False,
    ) -> dict[str, Any]:
        fascicolo_id = str(fascicolo_id or "").strip()
        current = self.get_profile_snapshot(fascicolo_id) or {}
        existing = [row for row in self._data["practice_profiles"] if row.get("fascicolo_id") != fascicolo_id]
        snapshot = profile.to_dict()
        snapshot.update({
            "id": str(current.get("id") or new_id("profile")),
            "fascicolo_id": fascicolo_id,
            "applied_at": utc_now(),
            "applied_by": actor,
            "manual_reason": reason,
        })
        existing.append(snapshot)
        self._data["practice_profiles"] = existing
        if reset:
            self._data["practice_document_slots"] = [
                row for row in self._data["practice_document_slots"] if row.get("fascicolo_id") != fascicolo_id
            ]
            self._data["practice_checklist_items"] = [
                row for row in self._data["practice_checklist_items"] if row.get("fascicolo_id") != fascicolo_id
            ]
        self._suspend_persist = True
        try:
            self.ensure_slots(fascicolo_id, profile)
            self.ensure_checklist(fascicolo_id, profile)
            self.record_state(fascicolo_id, PracticeState.FASCICOLO_APERTO.value, actor=actor, reason="Profilo pratica applicato.")
            self.audit(fascicolo_id, "PROFILE_APPLIED", actor=actor, message=f"Profilo {profile.code} applicato.", reason=reason, payload={"profile_code": profile.code})
        finally:
            self._suspend_persist = False
        self._save()
        return snapshot
    def get_profile_snapshot(self, fascicolo_id: str) -> dict[str, Any] | None:
        for row in reversed(self._data["practice_profiles"]):
            if row.get("fascicolo_id") == fascicolo_id:
                return dict(row)
        return None

    def ensure_slots(self, fascicolo_id: str, profile: PracticeProfile) -> list[DocumentSlot]:
        existing = {row.get("slot_key"): row for row in self._data["practice_document_slots"] if row.get("fascicolo_id") == fascicolo_id}
        rows = list(self._data["practice_document_slots"])
        for index, spec in enumerate(profile.required_slots, start=1):
            key = str(spec.get("slot_key") or "").strip().upper()
            if not key:
                continue
            if key in existing:
                row = existing[key]
                changed = False
                updates = {
                    "profile_id": profile.code,
                    "label": str(spec.get("label") or key),
                    "type": str(spec.get("type") or "ALTRO"),
                    "required": bool(spec.get("required", True)),
                    "blocking": bool(spec.get("blocking", True)),
                    "validators": list(spec.get("validators") or []),
                    "message": str(spec.get("message") or ""),
                    "suggested_action": str(spec.get("suggested_action") or ""),
                    "sort_order": int(spec.get("sort_order") or index),
                }
                for field, value in updates.items():
                    if row.get(field) != value:
                        row[field] = value
                        changed = True
                if changed:
                    rows = [
                        row if item.get("fascicolo_id") == fascicolo_id and item.get("slot_key") == key else item
                        for item in rows
                    ]
                continue
            slot = DocumentSlot(
                id=new_id("slot"),
                fascicolo_id=fascicolo_id,
                profile_id=profile.code,
                slot_key=key,
                label=str(spec.get("label") or key),
                type=str(spec.get("type") or "ALTRO"),
                required=bool(spec.get("required", True)),
                blocking=bool(spec.get("blocking", True)),
                validators=list(spec.get("validators") or []),
                message=str(spec.get("message") or ""),
                suggested_action=str(spec.get("suggested_action") or ""),
                sort_order=int(spec.get("sort_order") or index),
            )
            rows.append(asdict(slot))
        self._data["practice_document_slots"] = rows
        self._save()
        return self.list_slots(fascicolo_id)

    def ensure_checklist(self, fascicolo_id: str, profile: PracticeProfile) -> list[ChecklistItem]:
        existing = {row.get("key"): row for row in self._data["practice_checklist_items"] if row.get("fascicolo_id") == fascicolo_id}
        rows = list(self._data["practice_checklist_items"])
        for index, item in enumerate(profile.checklist_items, start=1):
            if item.key in existing:
                continue
            rows.append(
                asdict(
                    ChecklistItem(
                        id=new_id("chk"),
                        fascicolo_id=fascicolo_id,
                        profile_id=profile.code,
                        key=item.key,
                        label=item.label,
                        required=item.required,
                        blocking=item.blocking,
                        message=item.message,
                        suggested_action=item.suggested_action,
                        sort_order=index,
                        source=item.source,
                    )
                )
            )
        self._data["practice_checklist_items"] = rows
        self._save()
        return self.list_checklist(fascicolo_id)
    def list_slots(self, fascicolo_id: str) -> list[DocumentSlot]:
        rows = [
            dataclass_from_dict(DocumentSlot, row)
            for row in self._data["practice_document_slots"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: (item.sort_order, item.label))
    def get_slot(self, fascicolo_id: str, slot_key: str) -> DocumentSlot | None:
        key = str(slot_key or "").strip().upper()
        for slot in self.list_slots(fascicolo_id):
            if slot.slot_key.upper() == key:
                return slot
        return None
    def upsert_slot(self, slot: DocumentSlot) -> DocumentSlot:
        rows = [
            row
            for row in self._data["practice_document_slots"]
            if not (row.get("fascicolo_id") == slot.fascicolo_id and row.get("slot_key") == slot.slot_key)
        ]
        rows.append(asdict(slot))
        self._data["practice_document_slots"] = rows
        self._save()
        return slot
    def link_slot(self, fascicolo_id: str, slot_key: str, document_id: str, *, actor: str = "") -> DocumentSlot:
        slot = self.get_slot(fascicolo_id, slot_key)
        if not slot:
            raise KeyError(f"Slot documentale '{slot_key}' non trovato.")
        slot.document_id = str(document_id or "").strip()
        slot.status = SlotStatus.DA_VALIDARE.value if slot.document_id else SlotStatus.MANCANTE.value
        slot.message = "Documento collegato. Ripeti la verifica dello slot."
        slot.suggested_action = "Esegui la validazione dello slot documentale."
        self.upsert_slot(slot)
        self.audit(fascicolo_id, "DOCUMENT_SLOT_LINKED", actor=actor, message=f"Slot {slot.slot_key} collegato al documento {document_id}.")
        return slot
    def list_checklist(self, fascicolo_id: str) -> list[ChecklistItem]:
        rows = [
            dataclass_from_dict(ChecklistItem, row)
            for row in self._data["practice_checklist_items"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: (item.sort_order, item.label))

    def save_validation_results(
        self,
        fascicolo_id: str,
        results: list[ValidationResult],
        *,
        scope: str = "fascicolo",
        slot_key: str = "",
    ) -> list[ValidationResult]:
        rows = [
            row
            for row in self._data["practice_validation_results"]
            if not (row.get("fascicolo_id") == fascicolo_id and row.get("scope") == scope and row.get("slot_key", "") == slot_key)
        ]
        for result in results:
            row = asdict(result)
            row.update({"fascicolo_id": fascicolo_id, "scope": scope, "slot_key": slot_key})
            rows.append(row)
        self._data["practice_validation_results"] = rows
        self._save()
        return results
    def list_validation_results(self, fascicolo_id: str, *, scope: str = "", slot_key: str = "") -> list[ValidationResult]:
        rows: list[ValidationResult] = []
        for row in self._data["practice_validation_results"]:
            if row.get("fascicolo_id") != fascicolo_id:
                continue
            if scope and row.get("scope") != scope:
                continue
            if slot_key and row.get("slot_key", "") != slot_key:
                continue
            rows.append(dataclass_from_dict(ValidationResult, row))
        return rows
    def record_state(self, fascicolo_id: str, state: str, *, actor: str = "", reason: str = "", payload: dict[str, Any] | None = None) -> None:
        self._data["practice_state_history"].append(
            {
                "id": new_id("state"),
                "fascicolo_id": fascicolo_id,
                "state": state,
                "actor": actor,
                "reason": reason,
                "payload": payload or {},
                "created_at": utc_now(),
            }
        )
        self._save()
    def latest_state(self, fascicolo_id: str) -> str:
        for row in reversed(self._data["practice_state_history"]):
            if row.get("fascicolo_id") == fascicolo_id:
                return str(row.get("state") or "")
        return PracticeState.PRE_FASCICOLO.value
    def create_deposit_session(self, fascicolo_id: str, profile_id: str, channel: str, *, status: str, transport_mode: str = "non_configurato", messages: list[str] | None = None) -> DepositSession:
        session = DepositSession(
            id=new_id("dep"),
            fascicolo_id=fascicolo_id,
            profile_id=profile_id,
            channel=channel,
            status=status,
            transport_mode=transport_mode,
            messages=list(messages or []),
        )
        self._data["deposit_sessions"].append(asdict(session))
        self.add_timeline_event(session.id, fascicolo_id, "DEPOSIT_SESSION_CREATED", status, "Sessione deposito creata.")
        self._save()
        return session
    def get_deposit_session(self, deposito_id: str) -> DepositSession | None:
        for row in self._data["deposit_sessions"]:
            if row.get("id") == deposito_id:
                return dataclass_from_dict(DepositSession, row)
        return None
    def update_deposit_session(self, session: DepositSession) -> DepositSession:
        session.updated_at = utc_now()
        rows = [row for row in self._data["deposit_sessions"] if row.get("id") != session.id]
        rows.append(asdict(session))
        self._data["deposit_sessions"] = rows
        self._save()
        return session
    def list_deposit_sessions(self, fascicolo_id: str) -> list[DepositSession]:
        rows = [
            dataclass_from_dict(DepositSession, row)
            for row in self._data["deposit_sessions"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: item.created_at, reverse=True)
    def add_receipt(self, receipt: DepositReceipt) -> DepositReceipt:
        self._data["deposit_receipts"].append(asdict(receipt))
        self.add_timeline_event(
            receipt.deposit_session_id,
            receipt.fascicolo_id,
            receipt.receipt_type,
            receipt.status,
            receipt.message or "Ricevuta importata e collegata al deposito.",
            evidence_ref=receipt.id,
        )
        self._save()
        return receipt
    def list_receipts(self, deposito_id: str) -> list[DepositReceipt]:
        return [
            dataclass_from_dict(DepositReceipt, row)
            for row in self._data["deposit_receipts"]
            if row.get("deposit_session_id") == deposito_id
        ]
    def add_timeline_event(self, deposito_id: str, fascicolo_id: str, event_type: str, status: str, message: str, *, evidence_ref: str = "") -> TimelineEvent:
        event = TimelineEvent(new_id("evt"), deposito_id, fascicolo_id, event_type, status, message, evidence_ref=evidence_ref)
        self._data["deposit_timeline_events"].append(asdict(event))
        self._save()
        return event
    def list_timeline(self, deposito_id: str) -> list[TimelineEvent]:
        rows = [
            dataclass_from_dict(TimelineEvent, row)
            for row in self._data["deposit_timeline_events"]
            if row.get("deposit_session_id") == deposito_id
        ]
        return sorted(rows, key=lambda item: item.created_at)
    def save_evidence_pack(self, pack: EvidencePack) -> EvidencePack:
        rows = [row for row in self._data["evidence_packs"] if row.get("id") != pack.id]
        rows.append(asdict(pack))
        self._data["evidence_packs"] = rows
        self._save()
        return pack
    def get_evidence_pack(self, deposito_id: str) -> EvidencePack | None:
        for row in reversed(self._data["evidence_packs"]):
            if row.get("deposit_session_id") == deposito_id:
                return dataclass_from_dict(EvidencePack, row)
        return None
    def audit(self, fascicolo_id: str, event_type: str, *, actor: str = "", message: str = "", reason: str = "", payload: dict[str, Any] | None = None) -> AuditEvent:
        event = AuditEvent(new_id("audit"), fascicolo_id, event_type, actor=actor, message=message, reason=reason, payload=payload or {})
        self._data["audit_events"].append(asdict(event))
        self._save()
        return event
    def list_audit(self, fascicolo_id: str) -> list[AuditEvent]:
        return [
            dataclass_from_dict(AuditEvent, row)
            for row in self._data["audit_events"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
