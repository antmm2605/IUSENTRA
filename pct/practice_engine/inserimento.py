"""Inserimento delle righe del presidio procedurale nelle tabelle SQL (usato da ``repository.py``)."""

from __future__ import annotations

import json
from typing import Any

from .models import SlotStatus, new_id, utc_now


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


def inserisci_righe(conn: Any, data: dict[str, Any]) -> None:
    """Inserisce ogni riga delle raccolte in memoria nella sua tabella (le tabelle vanno svuotate prima)."""
    for row in data["practice_profiles"]:
        profile_id = str(row.get("id") or new_id("profile"))
        conn.execute("INSERT INTO practice_profiles (id,fascicolo_id,code,name,area,channel,registry,workflow_code,practice_id,procedure_code,version,source,payload_json,applied_at,applied_by,manual_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (profile_id, row.get("fascicolo_id", ""), row.get("code", ""), row.get("name", ""), row.get("area", ""), row.get("channel", ""), row.get("registry", ""), row.get("workflow_code", ""), row.get("practice_id", ""), row.get("procedure_code", ""), row.get("version", "1.0"), row.get("source", "legal_platform_catalog"), _json_dump(row), row.get("applied_at", utc_now()), row.get("applied_by", ""), row.get("manual_reason", "")))
    for row in data["practice_requirements"]:
        conn.execute("INSERT INTO practice_requirements (id,fascicolo_id,profile_id,requirement_key,label,required,blocking,source,message,suggested_action,sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("req"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("key", ""), row.get("label", ""), bool(row.get("required", True)), bool(row.get("blocking", True)), row.get("source", ""), row.get("message", ""), row.get("suggested_action", ""), int(row.get("sort_order", 0) or 0)))
    for row in data["practice_document_slots"]:
        conn.execute("INSERT INTO practice_document_slots (id,fascicolo_id,profile_id,slot_key,label,type,required,blocking,document_id,status,validators_json,last_validation_at,message,suggested_action,sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("slot"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("slot_key", ""), row.get("label", ""), row.get("type", "ALTRO"), bool(row.get("required", True)), bool(row.get("blocking", True)), row.get("document_id", ""), row.get("status", SlotStatus.MANCANTE.value), _json_dump(row.get("validators", [])), row.get("last_validation_at", ""), row.get("message", ""), row.get("suggested_action", ""), int(row.get("sort_order", 0) or 0)))
    for row in data["practice_checklist_items"]:
        conn.execute("INSERT INTO practice_checklist_items (id,fascicolo_id,profile_id,item_key,label,required,blocking,status,message,suggested_action,sort_order,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("chk"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("key", ""), row.get("label", ""), bool(row.get("required", True)), bool(row.get("blocking", True)), row.get("status", "DA_COMPLETARE"), row.get("message", ""), row.get("suggested_action", ""), int(row.get("sort_order", 0) or 0), row.get("source", "")))
    for row in data["practice_validation_results"]:
        conn.execute("INSERT INTO practice_validation_results (fascicolo_id,scope,slot_key,validator_key,status,severity,message,technical_detail,suggested_action,source,evidence_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("fascicolo_id", ""), row.get("scope", "fascicolo"), row.get("slot_key", ""), row.get("key", ""), row.get("status", "PENDING"), row.get("severity", "INFO"), row.get("message", ""), row.get("technical_detail", ""), row.get("suggested_action", ""), row.get("source", "practice_engine"), _json_dump(row.get("evidence", {})), row.get("created_at", utc_now())))
    for row in data["practice_state_history"]:
        conn.execute("INSERT INTO practice_state_history (id,fascicolo_id,state,actor,reason,payload_json,created_at) VALUES (?,?,?,?,?,?,?)", (row.get("id") or new_id("state"), row.get("fascicolo_id", ""), row.get("state", ""), row.get("actor", ""), row.get("reason", ""), _json_dump(row.get("payload", {})), row.get("created_at", utc_now())))
    for row in data["deposit_sessions"]:
        conn.execute("INSERT INTO deposit_sessions (id,fascicolo_id,profile_id,channel,status,transport_mode,simulated,real_transport,predeposit_status,messages_json,created_at,updated_at,sent_at,acquired_at,final_receipt_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("dep"), row.get("fascicolo_id", ""), row.get("profile_id", ""), row.get("channel", ""), row.get("status", "NON_INVIATO"), row.get("transport_mode", "non_configurato"), bool(row.get("simulated", False)), bool(row.get("real_transport", False)), row.get("predeposit_status", "NON_ESEGUITO"), _json_dump(row.get("messages", [])), row.get("created_at", utc_now()), row.get("updated_at", utc_now()), row.get("sent_at", ""), row.get("acquired_at", ""), row.get("final_receipt_id", "")))
    for row in data["deposit_receipts"]:
        conn.execute("INSERT INTO deposit_receipts (id,deposit_session_id,fascicolo_id,receipt_type,status,positive,source,original_name,original_hash_sha256,original_path,payload_json,imported_at,message) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (row.get("id") or new_id("receipt"), row.get("deposit_session_id", ""), row.get("fascicolo_id", ""), row.get("receipt_type", "ALTRO"), row.get("status", ""), bool(row.get("positive", False)), row.get("source", "import_guidato"), row.get("original_name", ""), row.get("original_hash_sha256", ""), row.get("original_path", ""), _json_dump(row.get("payload", {})), row.get("imported_at", utc_now()), row.get("message", "")))
    for row in data["deposit_timeline_events"]:
        conn.execute("INSERT INTO deposit_timeline_events (id,deposit_session_id,fascicolo_id,event_type,status,message,created_at,evidence_ref) VALUES (?,?,?,?,?,?,?,?)", (row.get("id") or new_id("evt"), row.get("deposit_session_id", ""), row.get("fascicolo_id", ""), row.get("event_type", ""), row.get("status", ""), row.get("message", ""), row.get("created_at", utc_now()), row.get("evidence_ref", "")))
    for row in data["evidence_packs"]:
        conn.execute("INSERT INTO evidence_packs (id,fascicolo_id,deposit_session_id,path,hash_sha256,created_at,available) VALUES (?,?,?,?,?,?,?)", (row.get("id") or new_id("evidence"), row.get("fascicolo_id", ""), row.get("deposit_session_id", ""), row.get("path", ""), row.get("hash_sha256", ""), row.get("created_at", utc_now()), bool(row.get("available", True))))
    for row in data["audit_events"]:
        conn.execute("INSERT INTO practice_audit_events (id,fascicolo_id,event_type,actor,message,reason,payload_json,created_at) VALUES (?,?,?,?,?,?,?,?)", (row.get("id") or new_id("audit"), row.get("fascicolo_id", ""), row.get("event_type", ""), row.get("actor", ""), row.get("message", ""), row.get("reason", ""), _json_dump(row.get("payload", {})), row.get("created_at", utc_now())))
