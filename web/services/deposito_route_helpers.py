"""Helpers condivisi dalle route del deposito telematico."""

from __future__ import annotations

import os
from typing import Any


def ufficio_da_nome(nome_ufficio: str) -> dict[str, Any] | None:
    if not nome_ufficio:
        return None
    try:
        from pct.uffici_giudiziari import get_gestore as _get_uff

        cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
        return next(
            (
                row
                for row in _get_uff(cache_path).carica()
                if str(row.get("nome", "")).lower() == nome_ufficio.lower()
            ),
            None,
        )
    except Exception:
        return None


def allegati_busta(fascicolo, gestore_fascicoli, id_fascicolo: str, allegati_ids: list[str], allegato_cls):
    allegati = []
    for allegato_id in allegati_ids:
        if not allegato_id:
            continue
        try:
            documento = next((doc for doc in fascicolo.documenti if doc.id == allegato_id), None)
            percorso = str(gestore_fascicoli.percorso_documento(id_fascicolo, allegato_id))
            allegati.append(
                allegato_cls(
                    percorso=percorso,
                    descrizione=documento.nome if documento else allegato_id,
                )
            )
        except Exception:
            continue
    return allegati


def validation_summary(validation: object) -> dict[str, Any]:
    issues = list(getattr(validation, "issues", []) or [])
    blockers = [issue for issue in issues if isinstance(issue, dict) and issue.get("level") == "BLOCK"]
    warnings = [issue for issue in issues if isinstance(issue, dict) and issue.get("level") == "WARNING"]
    public_issues = [
        {
            "level": str(issue.get("level", "")),
            "code": str(issue.get("code", "")),
            "title": str(issue.get("title", "")),
            "field": str(issue.get("field", "")),
        }
        for issue in issues[:20]
        if isinstance(issue, dict)
    ]
    return {"ok": not blockers, "blockers": len(blockers), "warnings": len(warnings), "issues": public_issues}


def guided_transport_completion_response(
    *,
    busta: object,
    id_deposito: str,
    timestamp: str,
    pec_dest: str,
    tipo_atto: str,
    oggetto_pec: str,
    attachment_path: str,
    validation: object,
) -> dict[str, Any] | None:
    audit_tecnico = {}
    audit_func = getattr(busta, "audit_conformita_pst", None)
    if callable(audit_func):
        audit_tecnico = audit_func()
    if audit_tecnico.get("uses_real_encryption") is True:
        return None
    next_actions = list(audit_tecnico.get("guided_next_actions") or [])
    if not next_actions:
        algoritmo = str(audit_tecnico.get("required_encryption_algorithm") or "AES256")
        next_actions = [
            "Controlla atto principale, allegati, firme e DatiAtto.xml nel pacchetto preparato.",
            f"Genera o collega Atto.enc ministeriale cifrato {algoritmo}.",
            "Riprendi dal fascicolo per presidiare ricevuta di accettazione, RdAC ed esiti.",
        ]
    return {
        "ok": False,
        "requires_guided_completion": True,
        "package_ready": True,
        "id_deposito": id_deposito,
        "timestamp": timestamp,
        "pec_dest": pec_dest,
        "tipo_atto": tipo_atto,
        "oggetto_pec": oggetto_pec,
        "attachment_path": attachment_path,
        "errore": "Invio diretto sospeso: manca la busta ministeriale conforme.",
        "message": (
            "Il software ha preparato il pacchetto di controllo, ma non registra un deposito come valido "
            "finché Atto.msg non viene cifrato in Atto.enc con algoritmo ministeriale vigente. "
            "Completa il passaggio indicato e poi riprendi il presidio ricevute dal fascicolo."
        ),
        "next_actions": next_actions,
        "validation": validation_summary(validation),
        "busta_audit": audit_tecnico,
    }
