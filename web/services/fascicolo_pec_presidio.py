"""Le PEC del presidio che riguardano un fascicolo: collegate, per numero di ruolo o per nome del cliente.

Il linker del presidio (pct/pec_pipeline) collega i messaggi al fascicolo quando
riconosce la pratica; una comunicazione può però citare il numero di ruolo o
il nome dell'assistito senza collegamento, e l'avvocato deve vederla comunque.
Questo servizio interroga il registro SQLite del presidio con le tre chiavi e
dice per ogni messaggio da quale corrispondenza viene, insieme agli eventi, ai
termini e alle udienze che il presidio ne ha estratto. Solo lettura: nessuna
modifica al presidio, nessun contenuto grezzo dei messaggi.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

MASSIMO_MESSAGGI = 0


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def chiavi_ruolo(numero_rg: str, anno_rg: str) -> list[str]:
    """Le forme con cui una comunicazione cita il ruolo: «1234/2026», «1234/26», «R.G. 1234»."""
    numero = re.sub(r"\D", "", _clean(numero_rg))
    anno = re.sub(r"\D", "", _clean(anno_rg))
    if not numero:
        return []
    chiavi = []
    if len(anno) == 4:
        chiavi.extend([f"{numero}/{anno}", f"{numero}/{anno[2:]}", f"{numero}-{anno}"])
    chiavi.extend([f"RG {numero}", f"R.G. {numero}", f"n. {numero}"])
    return chiavi


def chiavi_cliente(nome_cliente: str) -> list[str]:
    """Nome e cognome dell'assistito, nei due ordini; niente sotto le due parole per non pescare omonimi."""
    parole = [parola for parola in re.split(r"\s+", _clean(nome_cliente)) if len(parola) > 1]
    if len(parole) < 2:
        return []
    return [" ".join(parole), " ".join(reversed(parole))]


def _corrispondenza(riga: dict[str, Any], fascicolo_id: str, ruolo: list[str], cliente: list[str]) -> str:
    if _clean(riga.get("linked_fascicolo_id")) == fascicolo_id:
        return "collegamento"
    testo = _clean(riga.get("metadata_json")).lower()
    if any(chiave.lower() in testo for chiave in ruolo):
        return "rg"
    if any(chiave.lower() in testo for chiave in cliente):
        return "cliente"
    return ""


def _messaggi(conn: sqlite3.Connection, tenant_id: str, fascicolo_id: str, ruolo: list[str], cliente: list[str], limit: int) -> list[dict[str, Any]]:
    condizioni = ["linked_fascicolo_id=?"]
    params: list[Any] = [tenant_id, fascicolo_id]
    for chiave in ruolo + cliente:
        condizioni.append("metadata_json LIKE ?")
        params.append(f"%{chiave}%")
    query = (
        "SELECT id, received_at, mime_sha256, status, quality_status, signature_status, linked_fascicolo_id, metadata_json "
        f"FROM pec_messages WHERE tenant_id=? AND ({' OR '.join(condizioni)}) ORDER BY received_at DESC"
    )
    if limit > 0:
        query += " LIMIT ?"
        params.append(int(limit))
    return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]


def _per_messaggio(conn: sqlite3.Connection, tenant_id: str, ids: list[str]) -> tuple[dict[str, list], dict[str, list], dict[str, list]]:
    eventi: dict[str, list] = {}
    termini: dict[str, list] = {}
    udienze: dict[str, list] = {}
    if not ids:
        return eventi, termini, udienze
    segnaposto = ",".join("?" for _ in ids)
    for row in conn.execute(
        f"SELECT id, message_id, primary_event, family, priority, human_review_required FROM pec_legal_events WHERE tenant_id=? AND message_id IN ({segnaposto})",
        (tenant_id, *ids),
    ).fetchall():
        eventi.setdefault(row["message_id"], []).append(dict(row))
    for row in conn.execute(
        "SELECT d.id, d.deadline_type, d.norm_ref, d.dies_a_quo_date, d.peremptory, d.deterministic_status, d.scadenziario_id, "
        "d.human_review_required, d.duration_value, d.duration_unit, d.direction, e.message_id FROM pec_legal_deadlines d JOIN pec_legal_events e ON e.id=d.legal_event_id AND e.tenant_id=d.tenant_id "
        f"WHERE d.tenant_id=? AND e.message_id IN ({segnaposto})",
        (tenant_id, *ids),
    ).fetchall():
        termini.setdefault(row["message_id"], []).append(dict(row))
    for row in conn.execute(
        "SELECT h.id, h.hearing_date, h.hearing_time, h.mode, h.agenda_id, h.human_review_required, e.message_id "
        f"FROM pec_legal_hearings h JOIN pec_legal_events e ON e.id=h.legal_event_id WHERE h.tenant_id=? AND e.message_id IN ({segnaposto})",
        (tenant_id, *ids),
    ).fetchall():
        udienze.setdefault(row["message_id"], []).append(dict(row))
    return eventi, termini, udienze


def messaggi_pec_per_fascicolo(fascicolo: Any, *, repository: Any = None, limit: int = MASSIMO_MESSAGGI) -> list[dict[str, Any]]:
    """I messaggi del presidio che riguardano il fascicolo, già ridotti ai dati che la lettura usa."""
    fascicolo_id = _clean(getattr(fascicolo, "id", ""))
    if not fascicolo_id:
        return []
    ruolo = chiavi_ruolo(getattr(fascicolo, "numero_rg", ""), getattr(fascicolo, "anno_rg", ""))
    cliente = chiavi_cliente(getattr(fascicolo, "nome_cliente", ""))
    try:
        if repository is None:
            from web.services.pec_pipeline_runtime import repository_for_current_request

            repository = repository_for_current_request()
        tenant_id = str(getattr(repository, "tenant_id", "default") or "default")
        with repository.connect() as conn:
            righe = _messaggi(conn, tenant_id, fascicolo_id, ruolo, cliente, limit)
            eventi, termini, udienze = _per_messaggio(conn, tenant_id, [str(riga["id"]) for riga in righe])
            reports = {str(row["id"]): repository.latest_report(conn, str(row["id"])) for row in righe}
            parsed = {}
            for row in righe:
                version = repository.latest_parsed_row(conn, str(row["id"]))
                parsed[str(row["id"])] = json.loads(version["parsed_json"] or "{}") if version else {}

    except Exception:
        # Presidio non ancora inizializzato o registro assente: la lettura non deve fallire.
        return []
    messaggi: list[dict[str, Any]] = []
    for riga in righe:
        try:
            metadata = json.loads(riga.get("metadata_json") or "{}")
        except (TypeError, ValueError):
            metadata = {}
        intestazioni = dict(metadata.get("headers") or {}) if isinstance(metadata, dict) else {}
        corrispondenza = _corrispondenza(riga, fascicolo_id, ruolo, cliente)
        if not corrispondenza:
            continue
        identificativo = str(riga["id"])
        report = reports.get(identificativo, {})
        reading = parsed.get(identificativo, {})
        deposito = report.get("event_type") == "pct_deposito"
        messaggi.append({
            "mime_sha256": _clean(riga.get("mime_sha256")),
            "issues": list(report.get("issues") or []),
            "event_type": report.get("event_type", ""),
            "deposit_lifecycle": dict(report.get("deposit_lifecycle") or {}),
            "pec_receipt": dict(reading.get("pec_receipt") or {}),
            "archive_receipt_reference": dict(metadata.get("archive_receipt_reference") or {}),
            "header_message_id": _clean(((reading.get("legal_workflow") or {}).get("correlation_inputs") or {}).get("message_id")),
            "procedural_profile": dict(reading.get("procedural_profile") or {}),
            "deadline_proposal": dict(report.get("deadline_proposal") or {}),
            "id": identificativo,
            "received_at": _clean(riga.get("received_at")),
            "subject": _clean(intestazioni.get("subject")),
            "from": _clean(intestazioni.get("from")),
            "status": _clean(riga.get("status")),
            "quality_status": _clean(riga.get("quality_status")),
            "signature_status": _clean(riga.get("signature_status")),
            "collegata": _clean(riga.get("linked_fascicolo_id")) == fascicolo_id,
            "corrispondenza": corrispondenza,
            "eventi": eventi.get(identificativo, []),
            "termini": [] if deposito else termini.get(identificativo, []),
            "udienze": [] if deposito else [h for h in udienze.get(identificativo, []) if h.get("hearing_date")],
        })
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from flask import has_app_context
    if has_app_context():
        registro = registro_corrente()
        fatti = registro.fatti(tenant_corrente(), fascicolo_id, verifiche=("verificata", "corretta", "plausibile"))
        for messaggio in messaggi:
            for termine in messaggio["termini"]:
                proposte = [f for f in fatti if f.tipo == "pec" and f.oggetto_id == messaggio["id"]
                            and f.campo == "scadenza_proposta"
                            and any(p.get("termine_id") == termine["id"] for p in f.prove)]
                if proposte:
                    termine["deadline"] = proposte[0].valore
                    termine["fatto_id"] = proposte[0].id
            eventi_correnti = [f for f in fatti if f.tipo == "pec" and f.oggetto_id == messaggio["id"] and f.categoria == "evento" and f.campo in {"fissazione_note", "riassegnazione_note"}]
            if eventi_correnti:
                messaggio["eventi"] = [{"primary_event":f.campo,"family":"comunicazione_lavoro","priority":"P1","human_review_required":False,"fatto_id":f.id} for f in eventi_correnti]
                messaggio["udienze"] = []
    return messaggi


__all__ = ["MASSIMO_MESSAGGI", "chiavi_cliente", "chiavi_ruolo", "messaggi_pec_per_fascicolo"]
