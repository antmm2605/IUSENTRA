"""Helpers condivisi dalle route del deposito telematico."""

from __future__ import annotations

import os
from typing import Any

from pct.pratiche_collegate_catalog import normalize_codice_oggetto_pst


def _unique_clean_ids(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    return cleaned


def deposito_oggetto(form: Any, fascicolo: Any) -> str:
    raw_codice = str(
        form.get("codice_oggetto_pst", "") or getattr(fascicolo, "codice_oggetto_pst", "") or ""
    ).strip()
    normalized = normalize_codice_oggetto_pst(
        raw_codice
        or form.get("oggetto", "")
        or getattr(fascicolo, "oggetto", "")
    )
    return (
        normalized
        or raw_codice
        or str(form.get("oggetto", "") or "").strip()
        or str(getattr(fascicolo, "titolo", "") or "").strip()
    )


def wants_json_response(headers: Any) -> bool:
    accept = headers.get("Accept", "") if hasattr(headers, "get") else ""
    return (headers.get("X-Requested-With") == "XMLHttpRequest" if hasattr(headers, "get") else False) or "application/json" in accept


def manual_deposito_payload(form: Any, actor: str, *, actor_key: str) -> dict[str, str]:
    return {
        "tipo_atto": form.get("tipo_atto", "ATTO"),
        "pec_destinatario": form.get("pec_destinatario", ""),
        "stato": form.get("stato", "INVIATO"),
        "messaggio": form.get("messaggio", ""),
        "ricevuta_accettazione": form.get("ricevuta_accettazione", ""),
        "ricevuta_consegna": form.get("ricevuta_consegna", ""),
        "ricevuta_controlli_automatici": form.get("ricevuta_controlli_automatici", ""),
        "esito_controlli": form.get("esito_controlli", ""),
        "ricevuta_cancelleria": form.get("ricevuta_cancelleria", ""),
        "note": form.get("note", ""),
        actor_key: actor,
    }


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


def validate_busta_document_selection(
    fascicolo,
    gestore_fascicoli,
    id_fascicolo: str,
    form: Any,
    atto_id: str,
    allegati_ids: list[str],
) -> str:
    """Verifica che la busta rispetti la selezione mostrata all'avvocato."""
    planned_ids = _unique_clean_ids([atto_id, *allegati_ids])
    if hasattr(form, "getlist"):
        selected_ids = _unique_clean_ids(list(form.getlist("documenti_selezionati_ids")))
    else:
        raw_selected = form.get("documenti_selezionati_ids", []) if hasattr(form, "get") else []
        selected_ids = _unique_clean_ids(list(raw_selected or []))

    if selected_ids and set(selected_ids) != set(planned_ids):
        missing_in_package = [doc_id for doc_id in selected_ids if doc_id not in planned_ids]
        extra_in_package = [doc_id for doc_id in planned_ids if doc_id not in selected_ids]
        details = []
        if missing_in_package:
            details.append(f"non inclusi nella busta: {', '.join(missing_in_package)}")
        if extra_in_package:
            details.append(f"in busta ma non selezionati: {', '.join(extra_in_package)}")
        suffix = f" ({'; '.join(details)})" if details else ""
        return (
            "La selezione a video non coincide con i documenti che stanno per entrare nella busta"
            f"{suffix}. Ricarica la proposta e conferma di nuovo i documenti da inviare."
        )

    known_docs = {str(getattr(doc, "id", "") or ""): doc for doc in getattr(fascicolo, "documenti", [])}
    for doc_id in planned_ids:
        documento = known_docs.get(doc_id)
        if not documento:
            return f"Documento selezionato non presente nel fascicolo: {doc_id}. Ricarica la proposta busta."
        try:
            gestore_fascicoli.percorso_documento(id_fascicolo, doc_id)
        except Exception:
            nome = str(getattr(documento, "nome", "") or doc_id)
            return (
                f"Documento selezionato non reperibile su disco: {nome}. "
                "Carica nuovamente il file o correggi la selezione prima di generare la busta."
            )

    return ""


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
