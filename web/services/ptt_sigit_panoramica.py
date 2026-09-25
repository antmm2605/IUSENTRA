"""La pagina /sigit: i fascicoli tributari con lo stato del deposito PTT e i termini in corso.

Legge solo i dati salvati (fascicoli, archivio PTT): nessun documento viene
aperto. I termini sono quelli dell'art. 22 e 23 D.Lgs. 546/1992 calcolati
dalle date indicate nel procedimento.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from pct.fascicoli import TipoFascicolo
from pct.ptt_sigit import catalogo, termini
from web.services import ptt_sigit_contesto as contesto


def _riga(fascicolo: Any, salvato: dict[str, Any]) -> dict[str, Any]:
    proc = {"rg": contesto.rg(fascicolo), "atti": [], **{k: v for k, v in salvato["procedimento"].items() if v not in (None, "")}}
    corte = catalogo.sede(proc.get("corte") or catalogo.sede_da_testo(fascicolo.tribunale or ""))
    mancanti = [voce for voce, valore in (("Corte", corte), ("atto impugnato", proc.get("atti") or proc.get("rg"))) if not valore]
    scadenze = sorted(termini.termini(proc), key=lambda t: t["scadenza"])
    ultimo = (salvato.get("depositi") or [None])[0]
    return {"id": fascicolo.id, "titolo": fascicolo.titolo, "numero": fascicolo.numero, "cliente": fascicolo.nome_cliente,
            "corte": corte["nome"] if corte else (fascicolo.tribunale or ""), "rg": proc.get("rg") or "", "mancanti": mancanti,
            "termine": scadenze[0] if scadenze else None,
            "ultimoDeposito": {"tipo": ultimo.get("tipo", ""), "stato": ultimo.get("stato", ""), "quando": ultimo.get("aggiornatoIl", "")} if ultimo else None,
            "link": f"/fascicoli/{fascicolo.id}#ptt-sigit"}


def panoramica() -> dict[str, Any]:
    try:
        fascicoli = current_app.extensions["core_runtime"]["get_fascicoli"]().tutti(tipo=TipoFascicolo.TRIBUTARIO)
    except Exception:
        current_app.logger.warning("Fascicoli tributari non leggibili per la pagina PTT", exc_info=True)
        fascicoli = []
    archivio = contesto.archivio()
    righe = [_riga(f, archivio.fascicolo(f.id)) for f in fascicoli]
    righe.sort(key=lambda r: (r["termine"] is None, (r["termine"] or {}).get("scadenza", ""), r["titolo"]))
    stati = [r["ultimoDeposito"]["stato"] for r in righe if r["ultimoDeposito"]]
    return {
        "ok": True, "fascicoli": righe,
        "totali": {"fascicoli": len(righe), "daCompletare": sum(1 for r in righe if r["mancanti"]),
                   "termini": sum(1 for r in righe if r["termine"] and 0 <= r["termine"]["giorni"] <= 30),
                   "depositati": sum(1 for s in stati if s in {"depositata", "acquisita"}),
                   "anomalie": sum(1 for s in stati if "anomalia" in s or s == "rigettata")},
        "portale": catalogo.PORTALE, "telecontenzioso": catalogo.TELECONTENZIOSO, "registrazione": catalogo.REGISTRAZIONE,
        "consultazione": catalogo.CONSULTAZIONE_PUBBLICA, "assistenza": catalogo.ASSISTENZA, "numeroVerde": catalogo.NUMERO_VERDE,
        "fonte": catalogo.FONTE,
    }


__all__ = ["panoramica"]
