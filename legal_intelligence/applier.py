"""Applicazione controllata degli aggiornamenti rilevati."""

from __future__ import annotations

from datetime import datetime


def can_auto_apply(update: dict) -> bool:
    return update.get("apply_mode") == "auto" and update.get("status") in {"detected", "pending_review"}


def apply_update_record(update: dict) -> dict:
    payload = dict(update)
    if can_auto_apply(payload):
        payload["status"] = "applied"
        payload["applied_at"] = datetime.now().replace(microsecond=0).isoformat()
        payload["application_note"] = "Aggiornamento tecnico sicuro applicato in automatico."
    else:
        payload["status"] = "pending_review"
        payload["application_note"] = "Aggiornamento normativo o interpretativo in attesa di revisione."
    return payload
