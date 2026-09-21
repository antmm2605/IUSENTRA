"""Riconcilia proposte storiche automatiche con prove correnti dell'archivio.

Conserva righe e fonti. Non interviene su attività confermate, modificate o prive
 di una provenienza riconoscibile, e non legge documenti fisici.
"""
from __future__ import annotations
import uuid
import json
import re
from typing import Any
from pct.formatting import format_date_it
from pct.document_intelligence.models import utc_now

VERSIONE = "2026.09.21.rettifiche-storiche.v1"
NOTA_TERMINE_STORICO = "Creata dalla lettura automatica dei documenti: da confermare."


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def pianifica_rettifiche(fascicolo: Any, *, fatti: list[Any], oggetti: list[Any], scadenze: list[Any], testi: dict[str, str]) -> list[dict[str, Any]]:
    identita = {(o.tipo, o.oggetto_id): o.impronta for o in oggetti}
    correnti = [f for f in fatti if f.sha256 and identita.get((f.tipo, f.oggetto_id)) == f.sha256]
    piano = []
    for att in list(getattr(fascicolo, "attivita", []) or []):
        note = str(getattr(att, "note", "") or "")
        if _enum(getattr(att, "tipo", "")) != "UDIENZA" or _enum(getattr(att, "esito", "")) != "IN_ATTESA" or getattr(att, "avvocato", ""):
            continue
        if not str(getattr(att, "descrizione", "")).startswith("Attività per l'avvocato: Udienza."):
            continue
        if not note.startswith("PEC_DOCUMENT_PRESIDIO:docpresidio:") or any(not (line.startswith("PEC_DOCUMENT_PRESIDIO:docpresidio:") or line == "Fonte: documento fascicolo indicizzato da Lex AI.") for line in note.splitlines()):
            continue
        giorno = str(getattr(att, "data", ""))[:10]
        doc_id = str(getattr(att, "id_documento", ""))
        fonte = [f for f in correnti if f.tipo == "documento" and f.oggetto_id == doc_id and f.categoria == "data" and str(f.valore)[:10] == giorno]
        udienze = [f for f in fonte if f.campo == "udienza"]
        if any(f.verifica in {"verificata", "corretta", "plausibile"} for f in udienze):
            continue
        if udienze and all(f.verifica in {"respinta", "ignorata"} for f in udienze):
            prove = udienze
            motivo = "La lettura corrente esclude questa data come udienza del fascicolo."
        else:
            prove = [f for f in fonte if f.campo == "provvedimento" and f.verifica in {"verificata", "corretta"}]
            if not prove:
                continue
            motivo = "La data è riferita all’emissione del provvedimento, non a un’udienza."
        piano.append({"tipo": "attivita", "id": att.id, "motivo": motivo, "prove": [{"fatto_id": f.id, "documento_id": f.oggetto_id, "sha256": f.sha256, "campo": f.campo, "verifica": f.verifica, "estratto": f.contesto} for f in prove]})
    contratti = {f.oggetto_id: f for f in correnti if f.tipo == "documento" and f.campo == "natura_documentale" and f.valore == "contratto_lavoro" and f.verifica in {"verificata", "corretta"}}
    for scadenza in scadenze:
        giorno = str(scadenza.data_scadenza)[:10]
        if _enum(scadenza.stato) != "APERTO" or scadenza.note != NOTA_TERMINE_STORICO or scadenza.titolo != "Termine del " + format_date_it(giorno):
            continue
        if getattr(scadenza, "id_appuntamento", "") or getattr(scadenza, "avvisi_inviati", []) or getattr(scadenza, "id_utente_responsabile", "") or str(getattr(scadenza, "trace_json", "") or "").strip() not in {"", "[]"}:
            continue
        descrizione = _text(getattr(scadenza, "descrizione", ""))
        decorrenze = re.findall(r"decorrenza dal (\d{2}/\d{2}/\d{4})", descrizione, re.I)
        if not decorrenze or any(data != format_date_it(giorno) for data in decorrenze):
            continue
        if not re.search(r"(?:cessazione|al \d{2}/\d{2}/\d{4})", descrizione, re.I):
            continue
        frammenti = [part.strip() for part in descrizione.split(" | ") if len(part.strip()) >= 80]
        # Ogni frammento deve esistere nel testo corrente; almeno uno nel contratto.
        testi_correnti = {o.oggetto_id: _text(testi.get(o.oggetto_id, "")) for o in oggetti if o.tipo == "documento"}
        if not frammenti or not all(any(part in text for text in testi_correnti.values()) for part in frammenti):
            continue
        prove = [f for doc_id, f in contratti.items() if any(part in testi_correnti.get(doc_id, "") for part in frammenti)]
        if not prove:
            continue
        if any(f.categoria == "data" and f.campo in {"termine", "costituzione"} and str(f.valore)[:10] == giorno and f.verifica in {"verificata", "corretta", "plausibile"} for f in correnti):
            continue
        piano.append({"tipo": "scadenza", "id": scadenza.id, "motivo": "La data è la decorrenza del contratto di lavoro, non un termine processuale.", "prove": [{"fatto_id": f.id, "documento_id": f.oggetto_id, "sha256": f.sha256, "campo": f.campo, "verifica": f.verifica, "estratto": descrizione} for f in prove]})
    return piano


def riconcilia_storico(fascicolo: Any, registro: Any, tenant: str, *, applica: bool = False) -> dict[str, Any]:
    from web.helpers import get_fascicoli, get_scadenziario
    from web.services.archivio_letture_runtime import testi_indice_archivio
    from web.services.document_intelligence_runtime import build_document_ai_service
    scadenziario = get_scadenziario()
    scadenze = list(scadenziario.tutte(id_fascicolo=fascicolo.id, solo_aperte=False))
    piano = pianifica_rettifiche(fascicolo, fatti=registro.fatti(tenant, fascicolo.id, verifiche=None), oggetti=registro.oggetti(tenant, fascicolo.id), scadenze=scadenze, testi=testi_indice_archivio(fascicolo))
    if applica and piano:
        from pct.fascicoli import EsitoAttivita
        repository = build_document_ai_service().repository
        manager = get_fascicoli()
        for item in piano:
            timestamp = utc_now()
            audit_id = "rettifica-" + uuid.uuid4().hex
            repository.append_audit_event({"id": audit_id, "tenant_id": tenant, "fascicolo_id": fascicolo.id, "document_id": item["prove"][0]["documento_id"], "user_id": "archivio_letture", "event_type": "archive.legacy_reconciliation", "timestamp": timestamp, "status": "planned", "payload": {**item, "versione": VERSIONE}})
            nota = "Rettifica dall’archivio delle letture: " + item["motivo"] + " Prove: " + ", ".join(p["fatto_id"] for p in item["prove"])
            if item["tipo"] == "attivita":
                att = next(a for a in fascicolo.attivita if a.id == item["id"])
                manager.aggiorna_attivita(fascicolo.id, att.id, esito=EsitoAttivita.ANNULLATO, note=att.note + "\n" + nota)
            else:
                scadenza = next(s for s in scadenze if s.id == item["id"])
                scadenziario.aggiorna(scadenza.id, stato="ANNULLATO", note=scadenza.note + "\n" + nota, trace_json=json.dumps([{ "operazione": VERSIONE, "audit_id": audit_id, **item}], ensure_ascii=False))
            repository.append_audit_event({"id": audit_id + "-esito", "tenant_id": tenant, "fascicolo_id": fascicolo.id, "document_id": item["prove"][0]["documento_id"], "user_id": "archivio_letture", "event_type": "archive.legacy_reconciliation", "timestamp": utc_now(), "status": "applied", "payload": {"audit_id": audit_id, "tipo": item["tipo"], "id": item["id"], "versione": VERSIONE}})
        from web.services.lettura_cache import invalida_lettura
        invalida_lettura(fascicolo.id)
    return {"dry_run": not applica, "rettifiche": piano, "rettificate": len(piano) if applica else 0}
