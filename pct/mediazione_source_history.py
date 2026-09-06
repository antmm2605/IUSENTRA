"""Versioned public evidence: preserve prior observations on partial/error runs.

A successful acquisition is not a verified filing channel. This module cannot
approve, send, re-send or change any private proceeding.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def material(result):
    """Ignore banners/clock markup; retain contact context and relevant links."""
    return {
        "identity_match": bool(result.get("identity_match")),
        "contacts": sorted({(c["address"], c["source_url"], c["excerpt"], bool(c["pec_explicit"]),
                             bool(c["filing_context"])) for c in result.get("contacts", [])}),
        "resources": sorted({(r["url"], r.get("label", ""), r["kind"]) for r in result.get("resources", [])}),
        "api_documents": sorted({(r["url"], r.get("label", "")) for r in result.get("api_documents", [])}),
    }


def acquisition_outcome(result):
    if not any(p.get("status") == 200 and p.get("parsed") for p in result.get("pages", [])):
        return "non_acquisita"
    if result.get("errors") or result.get("remaining_urls"):
        return "acquisizione_parziale"
    return "acquisita"


def record(conn, number, result):
    """Must run in caller's transaction, including its job-lease ownership check."""
    checked_at = result["checked_at"]
    parsed = datetime.fromisoformat(checked_at)
    if parsed.tzinfo is None:
        raise ValueError("La verifica delle fonti richiede una data con fuso orario.")
    checked_at = parsed.astimezone(timezone.utc).isoformat()
    if parsed > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("La data della verifica delle fonti è nel futuro.")
    result = dict(result, checked_at=checked_at)
    payload = json.dumps(result, ensure_ascii=False)
    identifier, material_hash = uuid4().hex, digest(material(result))
    outcome = acquisition_outcome(result)
    conn.execute("INSERT INTO mediazione_source_state(registration_number) VALUES (?) "
                 "ON CONFLICT(registration_number) DO NOTHING", (number,))
    previous = conn.execute(
        "SELECT s.*, h.material_sha256, a.checked_at AS last_checked_at FROM mediazione_source_state s "
        "LEFT JOIN mediazione_source_history h ON h.id=s.last_success_id "
        "LEFT JOIN mediazione_source_history a ON a.id=s.last_attempt_id WHERE s.registration_number=?", (number,)).fetchone()
    obsolete = bool(previous["last_checked_at"] and parsed <= datetime.fromisoformat(previous["last_checked_at"]))
    if obsolete:
        outcome = "esito_superato"
    changed = bool(previous["last_success_id"] and previous["material_sha256"] != material_hash)
    conn.execute("INSERT INTO mediazione_source_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (identifier, number, checked_at, digest(result), material_hash, outcome, payload))
    conn.execute("INSERT INTO mediazione_directory_audit VALUES (?, ?, ?, ?, ?)",
                 (identifier, checked_at, "channel_research", 1, number))
    if obsolete:
        return outcome
    conn.execute("UPDATE mediazione_source_state SET last_attempt_id=?, last_success_id=?, "
                 "last_change_at=?, revision=? WHERE registration_number=?",
                 (identifier, identifier if outcome == "acquisita" else previous["last_success_id"],
                  checked_at if changed and outcome == "acquisita" else previous["last_change_at"],
                  previous["revision"] + int(outcome == "acquisita" and (changed or not previous["last_success_id"])), number))
    conn.execute("INSERT INTO mediazione_channel_checks VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(registration_number) DO UPDATE SET checked_at=excluded.checked_at, "
                 "status=excluded.status, result_json=excluded.result_json",
                 (number, checked_at, result["status"], payload))
    return outcome


def source_status(repo, number, *, now=None):
    now = now or datetime.now(timezone.utc)
    with repo.connection() as conn:
        row = conn.execute(
            "SELECT s.*, a.checked_at, a.outcome, a.result_json, h.checked_at AS success_at, "
            "h.result_json AS success_json, j.due_at, j.lease_until, j.last_error "
            "FROM mediazione_source_state s LEFT JOIN mediazione_source_history a ON a.id=s.last_attempt_id "
            "LEFT JOIN mediazione_source_history h ON h.id=s.last_success_id "
            "LEFT JOIN mediazione_source_jobs j ON j.registration_number=s.registration_number "
            "WHERE s.registration_number=?", (number,)).fetchone()
    if not row:
        return {"stato": "da_controllare", "invio_autorizzato": False, "revisione": 0}
    latest = json.loads(row["result_json"] or "{}")
    successful = json.loads(row["success_json"] or "{}")
    expired = not row["success_at"] or datetime.fromisoformat(row["success_at"]) < now - timedelta(days=7)
    status = "in_aggiornamento" if row["lease_until"] and row["lease_until"] > now.isoformat() else (
        "acquisizione_parziale" if row["outcome"] == "acquisizione_parziale" else
        "fonte_non_raggiunta" if row["outcome"] == "non_acquisita" else
        "da_aggiornare" if expired else "fonti_acquisite")
    return {"stato": status, "revisione": row["revision"], "ultimo_controllo": row["checked_at"],
            "ultima_acquisizione": row["success_at"] or "", "prossimo_controllo": row["due_at"] or "",
            "ultima_variazione": row["last_change_at"], "invio_autorizzato": False,
            "fonti": latest.get("pages", []), "contatti": latest.get("contacts", []),
            "documentazione_api": latest.get("api_documents", []), "problemi": latest.get("errors", []),
            "risorse_osservate": latest.get("resources", []),
            "risorse_precedenti": successful.get("resources", []),
            "fonti_precedenti": successful.get("pages", []),
            "identita_riscontrata": bool(latest.get("identity_match"))}
