"""Recupero crediti in serie: importazione, fascicoli, atti in blocco e avanzamento con le scadenze.

Orchestrazione applicativa sopra ``pct.recupero_crediti``: ogni posizione diventa un fascicolo del
creditore; gli atti (diffida, ricorso per decreto ingiuntivo, precetto) si compilano in blocco con i
modelli versionati del compilatore e finiscono come bozze nell'editor del fascicolo; ogni evento
registrato crea le scadenze di legge nello scadenziario del fascicolo (artt. 641, 644, 480, 481, 543
c.p.c.). Nulla viene depositato o notificato automaticamente.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from pct.recupero_crediti.modello import STATI, Evento, Posizione
from pct.recupero_crediti.stati import PASSAGGI, ammesso, termini_da_evento

MODELLI_ATTO = {
    "diffida": ("STR_MM_001", "Messa in mora e diffida ad adempiere (art. 1219 c.c.)"),
    "ricorso": ("CIV_RDI_001", "Ricorso per decreto ingiuntivo (art. 633 c.p.c.)"),
    "precetto": ("CIV_PREC_001", "Atto di precetto (art. 480 c.p.c.)"),
}
STATI_PER_ATTO = {"diffida": {"da_diffidare", "diffidato"}, "ricorso": {"da_diffidare", "diffidato", "ricorso_da_depositare"},
                  "precetto": {"esecutivo", "precetto_notificato", "pignoramento"}}


def _euro(valore: float) -> str:
    intero, decimali = f"{float(valore):,.2f}".split(".")
    return f"€ {intero.replace(',', '.')},{decimali}"


def payload_atto(tipo: str, posizione: Posizione, conteggio: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """Campi del modello compilati dai dati della posizione (il resto resta dal prefill del fascicolo)."""
    elenco = "; ".join(f"n. {d.numero or 's.n.'} del {d.data[8:10]}/{d.data[5:7]}/{d.data[:4]} per {_euro(d.importo)}"
                       for d in posizione.documenti)
    interessi = f"interessi {conteggio['tipo_interessi']} dalle singole scadenze al saldo"
    payload = dict(base)
    payload.update({"creditor": posizione.creditore, "debtor": posizione.debitore, "claimant": posizione.creditore,
                    "sender": posizione.creditore, "recipient": posizione.debitore,
                    "counterparty_or_recipient": posizione.debitore, "client_or_sender": posizione.creditore})
    if tipo == "diffida":
        payload.update({"legal_relationship_title": f"forniture e prestazioni documentate dalle fatture {elenco}",
                        "breach_description": f"mancato pagamento delle fatture scadute, per complessivi {_euro(posizione.capitale)}",
                        "requested_amount_or_performance": f"{_euro(conteggio['totale'])} (capitale {_euro(conteggio['capitale'])}, "
                        f"interessi {_euro(conteggio['interessi'])}" + (f", indennizzo forfettario {_euro(conteggio['indennizzo_forfettario'])} "
                                                                         "ex art. 6 D.Lgs. 231/2002" if conteggio["indennizzo_forfettario"] else "") + ")",
                        "deadline_assigned": "15 giorni dal ricevimento"})
    elif tipo == "ricorso":
        payload.update({"credit_source": f"fatture {elenco}", "requested_amount": _euro(posizione.capitale),
                        "written_evidence": "fatture ed estratto autentico delle scritture contabili (art. 634 c.p.c.)",
                        "interest_requested": interessi,
                        "credit_due_date": min((d.scadenza or d.data) for d in posizione.documenti)})
    else:
        payload.update({"principal_amount": _euro(conteggio["capitale"]), "interest_amount": _euro(conteggio["interessi"]),
                        "payment_deadline": "10 giorni dalla notifica (art. 480 c.p.c.)"})
    return payload


def importa(archivio: Any, posizioni: list[Posizione]) -> dict[str, Any]:
    esistenti = {(p.creditore_id, (p.debitore_codice or p.debitore.casefold())) for p in archivio.tutte() if not p.chiusa}
    nuove = [p for p in posizioni if (p.creditore_id, (p.debitore_codice or p.debitore.casefold())) not in esistenti]
    archivio.salva(nuove)
    return {"importate": len(nuove), "gia_presenti": len(posizioni) - len(nuove), "ids": [p.id for p in nuove]}


def apri_fascicoli(archivio: Any, ids: list[str], *, nuovo_fascicolo: Callable[[Posizione], Any]) -> int:
    aperte = []
    for pid in ids:
        posizione = archivio.get(pid)
        if posizione is None or posizione.fascicolo_id:
            continue
        posizione.fascicolo_id = str(getattr(nuovo_fascicolo(posizione), "id", "") or "")
        aperte.append(posizione)
    archivio.salva(aperte)
    return len(aperte)


def genera_atti(archivio: Any, ids: list[str], tipo: str, *, oggi: date, conta: Callable[[Posizione], dict],
                crea_bozza: Callable[[str, dict, Posizione], str], base_payload: Callable[[Posizione], dict]) -> dict[str, Any]:
    if tipo not in MODELLI_ATTO:
        raise ValueError("Atto non riconosciuto.")
    codice, _ = MODELLI_ATTO[tipo]
    create, saltate = [], []
    for pid in ids:
        posizione = archivio.get(pid)
        if posizione is None:
            continue
        if not posizione.fascicolo_id:
            saltate.append(f"{posizione.debitore}: apri prima il fascicolo")
            continue
        if posizione.stato not in STATI_PER_ATTO[tipo]:
            saltate.append(f"{posizione.debitore}: stato «{STATI.get(posizione.stato)}» non adatto")
            continue
        documento = crea_bozza(codice, payload_atto(tipo, posizione, conta(posizione), base_payload(posizione)), posizione)
        posizione.eventi.append(Evento(stato=posizione.stato, data=oggi.isoformat(), nota=f"Bozza {tipo} creata ({documento})"))
        create.append(posizione)
    archivio.salva(create)
    return {"create": len(create), "saltate": saltate}


def avanza(archivio: Any, ids: list[str], nuovo_stato: str, data_evento: date, *, nota: str, utente: str,
           crea_scadenza: Callable[[Posizione, dict], None]) -> dict[str, Any]:
    if nuovo_stato not in STATI:
        raise ValueError("Stato non riconosciuto.")
    aggiornate, rifiutate, scadenze = [], [], 0
    for pid in ids:
        posizione = archivio.get(pid)
        if posizione is None:
            continue
        if not ammesso(posizione.stato, nuovo_stato):
            rifiutate.append(f"{posizione.debitore}: da «{STATI[posizione.stato]}» non si passa a «{STATI[nuovo_stato]}»")
            continue
        posizione.stato = nuovo_stato
        posizione.eventi.append(Evento(stato=nuovo_stato, data=data_evento.isoformat(), nota=nota, utente=utente))
        if posizione.fascicolo_id:
            for termine in termini_da_evento(nuovo_stato, data_evento):
                crea_scadenza(posizione, termine)
                scadenze += 1
        aggiornate.append(posizione)
    archivio.salva(aggiornate)
    return {"aggiornate": len(aggiornate), "rifiutate": rifiutate, "scadenze": scadenze}


def riepilogo(posizioni: list[Posizione]) -> dict[str, Any]:
    per_stato: dict[str, dict[str, Any]] = {}
    for p in posizioni:
        voce = per_stato.setdefault(p.stato, {"stato": p.stato, "etichetta": STATI.get(p.stato, p.stato), "posizioni": 0, "capitale": 0.0})
        voce["posizioni"] += 1
        voce["capitale"] = round(voce["capitale"] + p.capitale, 2)
    return {"posizioni": len(posizioni), "capitale": round(sum(p.capitale for p in posizioni if not p.chiusa), 2),
            "per_stato": [per_stato[s] for s in STATI if s in per_stato]}


__all__ = ["MODELLI_ATTO", "PASSAGGI", "apri_fascicoli", "avanza", "genera_atti", "importa", "payload_atto", "riepilogo"]
