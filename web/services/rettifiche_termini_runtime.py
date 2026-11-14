"""Applica il piano di ``pct/archivio_letture/rettifica_termini`` alle scadenze del fascicolo.

Solo scadenze automatiche intatte dell'archivio delle letture; ogni modifica è registrata nella
traccia della scadenza, nella nota e nel registro delle operazioni (art. 20 CAD: la rettifica si
registra, non si cancella). ``applica=False`` produce lo stesso piano senza scrivere.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from typing import Any

logger = logging.getLogger(__name__)


def _traccia(scadenza: Any, voce: dict[str, Any]) -> str:
    try:
        traccia = json.loads(getattr(scadenza, "trace_json", "") or "[]")
    except (TypeError, ValueError):
        traccia = [{"storico": getattr(scadenza, "trace_json", "")}]
    if not isinstance(traccia, list):
        traccia = [{"storico": traccia}]
    traccia.append(voce)
    return json.dumps(traccia, ensure_ascii=False)


def riconcilia_termini_riletti(fascicolo: Any, registro: Any, tenant: str, *, applica: bool = True) -> dict[str, Any]:
    from pct.archivio_letture.rettifica_termini import VERSIONE, piano_rettifiche
    from pct.ora_italiana import oggi_roma
    from web.helpers import get_scadenziario

    fid = str(getattr(fascicolo, "id", "") or "")
    oggetti = {(o.tipo, o.oggetto_id): o.impronta for o in registro.oggetti(tenant, fid)}
    fatti = [f for f in registro.fatti(tenant, fid, categoria="data", verifiche=None)
             if oggetti.get((f.tipo, f.oggetto_id)) == f.sha256]
    scadenziario = get_scadenziario()
    scadenze = {s.id: s for s in scadenziario.tutte(id_fascicolo=fid, solo_aperte=False)}
    piano = piano_rettifiche(scadenze.values(), fatti, oggi=oggi_roma())
    esito = {"dry_run": not applica, "piano": [asdict(r) for r in piano], "aggiornate": 0, "annullate": 0}
    if not applica:
        esito["agenda_piano"] = [asdict(r) for r in _piano_agenda(fascicolo, fatti)]
        return esito
    from pct.document_intelligence.models import utc_now
    from web.services.document_intelligence_runtime import build_document_ai_service

    repository = build_document_ai_service().repository
    for rettifica in piano:
        scadenza = scadenze[rettifica.scadenza_id]
        audit_id = "rettifica-termine-" + uuid.uuid4().hex
        voce = {"operazione": VERSIONE, "audit_id": audit_id, "azione": rettifica.azione, "motivo": rettifica.motivo,
                "campi": rettifica.campi, "prove": rettifica.prove, "titolo_precedente": scadenza.titolo}
        repository.append_audit_event({"id": audit_id, "tenant_id": tenant, "fascicolo_id": fid, "document_id": None,
                                       "user_id": "archivio_letture", "event_type": "archive.deadline_reread",
                                       "timestamp": utc_now(), "status": "planned", "payload": voce})
        try:
            if rettifica.azione == "annulla":
                scadenziario.aggiorna(scadenza.id, stato="ANNULLATO", trace_json=_traccia(scadenza, voce),
                                      note=scadenza.note + "\nRettifica automatica della lettura: " + rettifica.motivo)
                esito["annullate"] += 1
            else:
                righe = scadenza.note.splitlines()
                # La nota resta nella forma automatica di tre righe: la riga punta al fatto corrente.
                righe[1] = "ARCHIVIO_FATTO:" + rettifica.fatto_id
                scadenziario.aggiorna(scadenza.id, trace_json=_traccia(scadenza, voce), note="\n".join(righe), **rettifica.campi)
                registro.segna_consegna(tenant, fid, rettifica.fatto_id, "scadenziario", stato="consegnato",
                                        riferimento=scadenza.id, motivo="Scadenza riallineata alla lettura corrente.",
                                        versione_presidio=VERSIONE)
                esito["aggiornate"] += 1
        except Exception:
            logger.exception("Rettifica della scadenza %s non riuscita (fascicolo %s)", scadenza.id, fid)
            continue
        repository.append_audit_event({"id": audit_id + "-esito", "tenant_id": tenant, "fascicolo_id": fid, "document_id": None,
                                       "user_id": "archivio_letture", "event_type": "archive.deadline_reread",
                                       "timestamp": utc_now(), "status": "applied", "payload": {"audit_id": audit_id}})
    esito["agenda"] = _riconcilia_agenda(fascicolo, fatti, tenant, repository)
    if esito["aggiornate"] or esito["annullate"] or esito["agenda"]:
        from web.services.lettura_cache import invalida_lettura
        invalida_lettura(fid)
    return esito


def _piano_agenda(fascicolo: Any, fatti: list[Any]) -> list[Any]:
    from pct.archivio_letture.rettifica_termini import piano_agenda
    from web.helpers import get_agenda

    procedimento = f"RG {getattr(fascicolo, 'numero_rg', '')}/{getattr(fascicolo, 'anno_rg', '')}"
    appuntamenti = [a for a in get_agenda().tutti()
                    if str(getattr(a, "id_fascicolo", "") or "") == str(fascicolo.id) or str(getattr(a, "procedimento", "") or "").strip() == procedimento]
    return piano_agenda(appuntamenti, fatti, tribunale=str(getattr(fascicolo, "tribunale", "") or ""))


def _riconcilia_agenda(fascicolo: Any, fatti: list[Any], tenant: str, repository: Any) -> int:
    from pct.archivio_letture.rettifica_termini import VERSIONE
    from pct.document_intelligence.models import utc_now
    from web.helpers import get_agenda

    agenda = get_agenda()
    fatte = 0
    for rettifica in _piano_agenda(fascicolo, fatti):
        appuntamento = agenda.get(rettifica.scadenza_id)
        if appuntamento is None:
            continue
        audit_id = "rettifica-udienza-" + uuid.uuid4().hex
        try:
            agenda.modifica(appuntamento.id, note=(str(appuntamento.note or "") + "\nRettifica automatica della lettura: " + rettifica.motivo).strip(),
                            **rettifica.campi)
        except Exception:
            logger.exception("Rettifica della modalità d'udienza %s non riuscita", appuntamento.id)
            continue
        repository.append_audit_event({"id": audit_id, "tenant_id": tenant, "fascicolo_id": str(fascicolo.id), "document_id": None,
                                       "user_id": "archivio_letture", "event_type": "archive.hearing_mode_reread", "timestamp": utc_now(),
                                       "status": "applied", "payload": {"operazione": VERSIONE, "appuntamento": appuntamento.id,
                                                                        "campi": rettifica.campi, "motivo": rettifica.motivo, "prove": rettifica.prove}})
        fatte += 1
    return fatte


__all__ = ["riconcilia_termini_riletti"]
