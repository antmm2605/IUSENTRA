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


_AZIONI_DELLA_PERSONA = ("scadenziario.modifica", "scadenziario.completa", "scadenziario.elimina", "scadenza.completata")


def _scadenze_toccate(scadenze: dict[str, Any]) -> frozenset[str]:
    """Le scadenze su cui una persona è intervenuta, secondo il registro di audit dello studio."""
    try:
        from web.helpers import get_utenti

        eventi = get_utenti().audit_log(azione="scadenz", limit=100000)
    except Exception:  # senza registro non si può escludere l'intervento dell'avvocato: nessuna riga si modifica
        return frozenset(scadenze)
    return frozenset(str(e.risorsa_id) for e in eventi
                     if str(getattr(e, "risorsa_id", "")) in scadenze and str(getattr(e, "azione", "")).startswith(_AZIONI_DELLA_PERSONA))


def riconcilia_termini_riletti(fascicolo: Any, registro: Any, tenant: str, *, applica: bool = True) -> dict[str, Any]:
    from pct.archivio_letture.rettifica_termini import (
        VERSIONE, piano_agenda, piano_agenda_documentale_sostituita, piano_rettifiche,
        piano_udienze_sostituite, sostituzioni_documentate,
    )
    from pct.ora_italiana import oggi_roma
    from web.helpers import get_agenda, get_scadenziario

    fid = str(getattr(fascicolo, "id", "") or "")
    oggetti = {(o.tipo, o.oggetto_id): o.impronta for o in registro.oggetti(tenant, fid)}
    fatti = [f for f in registro.fatti(tenant, fid, categoria="data", verifiche=None)
             if oggetti.get((f.tipo, f.oggetto_id)) == f.sha256]
    scadenziario = get_scadenziario()
    scadenze = {s.id: s for s in scadenziario.tutte(id_fascicolo=fid, solo_aperte=False)}
    agenda = get_agenda()
    procedimento = f"RG {getattr(fascicolo, 'numero_rg', '')}/{getattr(fascicolo, 'anno_rg', '')}"
    appuntamenti = [a for a in agenda.tutti()
                    if str(a.id_fascicolo or "") == fid or (not a.id_fascicolo and a.procedimento.strip() == procedimento)]
    fonti_pec = {}
    for documento in getattr(fascicolo, "documenti", ()) or ():
        intestazione, _, _ = str(getattr(documento, "note", "") or "").partition("\n")
        marker, _, pec_id = intestazione.partition(":")
        if marker == "IUSENTRA_PROVVEDIMENTO_CANCELLERIA" and pec_id.strip():
            fonti_pec[documento.id] = pec_id.strip()
    oggi = oggi_roma()
    piano = piano_rettifiche(scadenze.values(), fatti, oggi=oggi, toccate=_scadenze_toccate(scadenze))
    segnalazioni = [r for r in piano if r.azione == "segnala"]
    piano = [r for r in piano if r.azione != "segnala"]
    piano_appuntamenti = piano_agenda(appuntamenti, fatti, tribunale=str(getattr(fascicolo, "tribunale", "") or ""))
    sostituzioni = sostituzioni_documentate(fatti)
    piano_appuntamenti.extend(piano_agenda_documentale_sostituita(appuntamenti, sostituzioni, oggi=oggi))
    sostituite = piano_udienze_sostituite(scadenze.values(), appuntamenti, sostituzioni, fonti_pec, oggi=oggi)
    piano.extend(scadenza for scadenza, _ in sostituite if scadenze[scadenza.scadenza_id].stato.value != "ANNULLATO")
    esito = {
        "dry_run": not applica, "piano": [asdict(r) for r in piano], "aggiornate": 0, "annullate": 0,
        "segnalazioni": [asdict(r) for r in segnalazioni],
        "fonti_udienze_sostituite": [{"documento": documento, "data": giorno} for documento, giorno in sostituzioni],
    }
    if not applica:
        esito["agenda_piano"] = [asdict(r) for r in piano_appuntamenti + [a for _, a in sostituite]]
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
            elif not rettifica.fatto_id:
                # Riga del presidio PEC (udienza titolata come opposizione ex art. 127-ter): la nota si integra, non si riscrive.
                scadenziario.aggiorna(scadenza.id, trace_json=_traccia(scadenza, voce),
                                      note=scadenza.note + "\nRettifica automatica della lettura: " + rettifica.motivo, **rettifica.campi)
                esito["aggiornate"] += 1
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
    for scadenza, appuntamento in sostituite:
        dopo = scadenziario.get(scadenza.scadenza_id)
        if dopo and dopo.stato.value == "ANNULLATO":
            piano_appuntamenti.append(appuntamento)
    esito["agenda"] = _riconcilia_agenda(fascicolo, agenda, piano_appuntamenti, tenant, repository)
    if esito["aggiornate"] or esito["annullate"] or esito["agenda"]:
        from web.services.lettura_cache import invalida_lettura
        invalida_lettura(fid)
    return esito


def _riconcilia_agenda(fascicolo: Any, agenda: Any, piano: list[Any], tenant: str, repository: Any) -> int:
    from pct.agenda import StatoAppuntamento
    from pct.archivio_letture.rettifica_termini import VERSIONE
    from pct.document_intelligence.models import utc_now

    fatte = 0
    for rettifica in piano:
        appuntamento = agenda.get(rettifica.scadenza_id)
        if appuntamento is None or appuntamento.stato == StatoAppuntamento.ANNULLATO:
            continue
        campi = dict(rettifica.campi)
        if "stato" in campi:
            campi["stato"] = StatoAppuntamento(campi["stato"])
        audit_id = "rettifica-udienza-" + uuid.uuid4().hex
        try:
            revisione = agenda.revision_token(appuntamento.id)
            nota = (str(appuntamento.note or "") + "\nRettifica automatica della lettura: " + rettifica.motivo).strip()
            agenda.modifica(appuntamento.id, expected_version=revisione, note=nota, **campi)
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
