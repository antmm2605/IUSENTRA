"""Dati del portale del cliente con link personale (letture, nessuna scrittura).

Spostati da `web/blueprints/portale.py` perché li usano sia le pagine storiche
sia le API JSON della pagina React: pratiche, appuntamenti, scadenze e area
economica sono sempre filtrati sul cliente del link.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app

from pct.economico_context import riepilogo_contesto_economico
from web.services.portale_cliente_legacy_contesto import ContestoPortale, fascicoli_visibili, permesso

ROME_TZ = ZoneInfo("Europe/Rome")
STATI_ACCETTABILI = {"INVIATO", "APERTO"}


def _valore(stato: Any) -> str:
    return str(getattr(stato, "value", stato) or "")


def _get_preventivi():
    from web.helpers import get_preventivi

    return get_preventivi()


def _get_fatturazione():
    from web.helpers import get_fatturazione

    return get_fatturazione()


def _mappa_fascicoli_cliente(id_cliente: str) -> dict[str, Any]:
    from web.helpers import get_fascicoli

    try:
        return {f.id: f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente}
    except Exception:
        return {}


def documenti_economici_cliente(id_cliente: str) -> dict[str, Any]:
    """Preventivi (non bozze), conferimenti e parcelle del cliente, con la cronologia."""
    fascicoli_map = _mappa_fascicoli_cliente(id_cliente)
    gp_prev = None
    try:
        from pct.preventivi import StatoPreventivo

        gp_prev = _get_preventivi()
        preventivi = [
            p for p in gp_prev.tutti_preventivi()
            if p.id_cliente == id_cliente and p.stato not in {StatoPreventivo.BOZZA, StatoPreventivo.IN_CALCOLO}
        ]
        conferimenti = [c for c in gp_prev.tutti_conferimenti() if c.id_cliente == id_cliente]
    except Exception:
        preventivi, conferimenti = [], []
    try:
        parcelle = [p for p in _get_fatturazione().tutte() if p.id_cliente == id_cliente]
    except Exception:
        parcelle = []

    preventivi = sorted(preventivi, key=lambda p: (p.data_emissione or "", p.creato_il or ""), reverse=True)
    conferimenti = sorted(conferimenti, key=lambda c: (c.data_incarico or "", c.creato_il or ""), reverse=True)
    parcelle = sorted(parcelle, key=lambda p: (p.data_emissione or "", p.creato_il or ""), reverse=True)

    timeline = []
    for p in preventivi:
        fascicolo = fascicoli_map.get(p.id_fascicolo)
        timeline.append({
            "kind": "preventivo", "id": p.id, "numero": p.numero, "data": p.data_emissione, "titolo": p.oggetto,
            "stato": _valore(p.stato), "totale": round(p.totale, 2),
            "fascicolo_label": fascicolo.titolo if fascicolo else "",
            "calc_summary": riepilogo_contesto_economico(getattr(p, "log_calcolo", None)),
        })
    for c in conferimenti:
        fascicolo = fascicoli_map.get(c.id_fascicolo)
        preventivo = gp_prev.get_preventivo(c.id_preventivo) if (gp_prev and c.id_preventivo) else None
        timeline.append({
            "kind": "conferimento", "id": c.id, "numero": c.numero, "data": c.data_incarico, "titolo": c.oggetto,
            "stato": _valore(c.stato), "totale": round(c.compenso_pattuito or 0.0, 2),
            "fascicolo_label": fascicolo.titolo if fascicolo else "",
            "calc_summary": riepilogo_contesto_economico(getattr(preventivo, "log_calcolo", None)) if c.id_preventivo else {},
        })
    for parcella in parcelle:
        fascicolo = fascicoli_map.get(parcella.id_fascicolo)
        timeline.append({
            "kind": "parcella", "id": parcella.id, "numero": parcella.numero, "data": parcella.data_emissione,
            "titolo": parcella.note or "Parcella professionale", "stato": _valore(parcella.stato),
            "totale": round(parcella.totale, 2), "fascicolo_label": fascicolo.titolo if fascicolo else "",
            "calc_summary": riepilogo_contesto_economico(getattr(parcella, "log_calcolo", None)),
        })

    timeline.sort(key=lambda row: (row.get("data") or "", row.get("numero") or ""), reverse=True)
    return {
        "preventivi": preventivi,
        "conferimenti": conferimenti,
        "parcelle": parcelle,
        "timeline": timeline,
        "stats": {
            "preventivi": len(preventivi),
            "conferimenti": len(conferimenti),
            "parcelle": len(parcelle),
            "totale": len(timeline),
        },
    }


def preventivo_del_cliente(id_cliente: str, id_preventivo: str):
    gp_prev = _get_preventivi()
    p = gp_prev.get_preventivo(id_preventivo)
    return (p if p and p.id_cliente == id_cliente else None), gp_prev


def conferimento_del_cliente(id_cliente: str, id_conferimento: str):
    gp_prev = _get_preventivi()
    c = gp_prev.get_conferimento(id_conferimento)
    return (c if c and c.id_cliente == id_cliente else None), gp_prev


def parcella_del_cliente(id_cliente: str, id_parcella: str):
    gf = _get_fatturazione()
    p = gf.get(id_parcella)
    return (p if p and p.id_cliente == id_cliente else None), gf


def workflow_summary(cliente, *, preventivo=None, conferimento=None) -> dict[str, Any]:
    from pct.workflow_commerciale import build_workflow_summary
    from web.helpers import get_fascicoli

    fascicolo = None
    if conferimento and getattr(conferimento, "id_fascicolo", ""):
        fascicolo = get_fascicoli().get(conferimento.id_fascicolo)
    elif preventivo and getattr(preventivo, "id_fascicolo", ""):
        fascicolo = get_fascicoli().get(preventivo.id_fascicolo)
    try:
        return build_workflow_summary(cliente=cliente, preventivo=preventivo, conferimento=conferimento, fascicolo=fascicolo)
    except Exception:
        current_app.logger.exception("Errore riepilogo workflow portale")
        return {}


def arricchisci_economici(portale_obj, cliente, dati: dict[str, Any]) -> list[dict[str, Any]]:
    """Riepiloghi e azioni consentite su preventivi e conferimenti.

    Annota ogni documento con `workflow_summary`, `calc_summary`, `can_accept` o
    `can_sign` e restituisce le azioni richieste al cliente (senza indirizzi:
    li aggiunge chi le mostra, pagina storica o API).
    """
    gp_prev = _get_preventivi()
    permessi = portale_obj.permessi
    economici = bool(getattr(permessi, "vedi_economici", False))
    azioni: list[dict[str, Any]] = []

    for doc in dati["preventivi"]:
        setattr(doc, "workflow_summary", workflow_summary(cliente, preventivo=doc))
        setattr(doc, "calc_summary", riepilogo_contesto_economico(getattr(doc, "log_calcolo", None)))
        can_accept = bool(
            getattr(permessi, "accetta_preventivi", True) and economici
            and _valore(getattr(doc, "stato", "")) in STATI_ACCETTABILI
        )
        setattr(doc, "can_accept", can_accept)
        if can_accept:
            azioni.append({
                "kind": "preventivo", "id": doc.id, "title": f"Accetta il preventivo {doc.numero}",
                "subtitle": getattr(doc, "oggetto", ""), "button_label": "Accetta preventivo",
            })

    for doc in dati["conferimenti"]:
        preventivo = gp_prev.get_preventivo(doc.id_preventivo) if doc.id_preventivo else None
        setattr(doc, "workflow_summary", workflow_summary(cliente, preventivo=preventivo, conferimento=doc))
        setattr(doc, "calc_summary", riepilogo_contesto_economico(getattr(preventivo, "log_calcolo", None)) if preventivo else {})
        can_sign = bool(
            getattr(permessi, "firma_conferimenti", True) and economici
            and not getattr(doc, "firma_cliente_eseguita", False)
            and not getattr(doc, "id_fascicolo", "")
        )
        setattr(doc, "can_sign", can_sign)
        if can_sign:
            azioni.append({
                "kind": "conferimento", "id": doc.id, "title": f"Firma il conferimento {doc.numero}",
                "subtitle": getattr(doc, "oggetto", ""), "button_label": "Firma conferimento",
            })
    return azioni


def oggi_roma():
    return datetime.now(ROME_TZ).date()


def dati_home(contesto: ContestoPortale) -> dict[str, Any]:
    """Tutto ciò che mostra la pagina iniziale del portale, secondo i permessi."""
    from pct.legal_intelligence import costruisci_tracker_fascicoli
    from web.helpers import get_agenda, get_scadenziario

    cliente = contesto.cliente
    oggi = oggi_roma()
    fascicoli = fascicoli_visibili(contesto)
    appuntamenti: list[Any] = []
    scadenze: list[Any] = []
    economici: dict[str, Any] = {"stats": {"preventivi": 0, "conferimenti": 0, "parcelle": 0, "totale": 0}, "timeline": []}
    azioni: list[dict[str, Any]] = []

    if permesso(contesto, "vedi_appuntamenti"):
        appuntamenti = [
            a for a in get_agenda().tutti()
            if a.id_cliente == cliente.id and a.data_ora_dt.date() >= oggi
        ][:5]
    if permesso(contesto, "vedi_scadenze"):
        id_fascicoli = {f.id for f in fascicoli}
        scadenze = [s for s in get_scadenziario().imminenti(entro_giorni=30) if s.id_fascicolo in id_fascicoli]
    if permesso(contesto, "vedi_economici"):
        economici = documenti_economici_cliente(cliente.id)
        azioni = arricchisci_economici(contesto.portale, cliente, economici)

    return {
        "fascicoli": fascicoli,
        "tracker_map": costruisci_tracker_fascicoli(fascicoli),
        "appuntamenti": appuntamenti,
        "scadenze": scadenze,
        "economici": economici,
        "azioni_richieste": azioni,
        "oggi": oggi,
    }


__all__ = [
    "arricchisci_economici",
    "conferimento_del_cliente",
    "dati_home",
    "documenti_economici_cliente",
    "oggi_roma",
    "parcella_del_cliente",
    "preventivo_del_cliente",
    "workflow_summary",
]
