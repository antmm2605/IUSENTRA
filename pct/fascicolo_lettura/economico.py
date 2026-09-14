"""Il presidio economico del fascicolo, con gli importi.

Preventivo e conferimento sono l'incarico (art. 13 L. 247/2012: compenso
pattuito per iscritto e preventivo scritto al cliente); parcelle emesse,
pagate e scadute sono il credito dello studio; il controllo pagamenti del
fascicolo porta la liquidazione disposta dal giudice (letta dalla sentenza
dal presidio economico), le anticipazioni da recuperare e lo stato di ogni
voce; i pagamenti registrati in fatturazione dicono se la somma è arrivata
davvero sul conto dello studio (bonifico) e quando. La lettura riporta tutto
com'è dovuto a chi deve decidere se riscuotere, sollecitare, fatturare o
formalizzare, sulla stessa fonte della pagina Fatturazione.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_da, data_it, euro, pulisci


def _importo(valore: Any) -> float:
    try:
        return round(float(valore or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _parcella(voce: dict[str, Any]) -> dict[str, Any]:
    stato = pulisci(voce.get("stato")).upper()
    scadenza = data_da(voce.get("data_scadenza"))
    metodo = pulisci(voce.get("metodo_pagamento"))
    return {
        "metodo": metodo,
        "bonifico": "bonific" in metodo.lower(),
        "pagata_il": data_it(voce.get("data_pagamento")),
        "id": pulisci(voce.get("id")),
        "numero": pulisci(voce.get("numero")),
        "stato": stato,
        "totale": _importo(voce.get("totale")),
        "totale_it": euro(voce.get("totale")) or "€ 0,00",
        "emessa_il": data_it(voce.get("data_emissione")),
        "scadenza": data_it(voce.get("data_scadenza")),
        "scadenza_iso": scadenza.isoformat() if scadenza else "",
    }


def _voce_presidio(voce: Any) -> dict[str, Any]:
    if not isinstance(voce, dict):
        return {}
    importo = voce.get("importo")
    return {
        "stato": pulisci(voce.get("status")),
        "stato_etichetta": pulisci(voce.get("statusLabel")),
        "importo": _importo(importo) if importo is not None else None,
        "importo_it": euro(importo) if importo is not None else "",
        "data": data_it(voce.get("dataPagamentoIso") or voce.get("dataPagamento") or voce.get("data_pagamento")),
        "metodo": pulisci(voce.get("metodo")),
        "fonte": pulisci(voce.get("documentoFonte") or voce.get("documento_fonte") or voce.get("origine")),
        "pagato": bool(voce.get("pagato")),
        "previsto": bool(voce.get("previsto")),
        "nota": pulisci(voce.get("note"))[:160],
    }


def economico(dati: dict[str, Any], oggi: Any = None) -> dict[str, Any]:
    sintesi = dict((dati or {}).get("summary") or {})
    parcelle = [_parcella(voce) for voce in list((dati or {}).get("parcelle") or [])]
    presidio = dict((dati or {}).get("presidio") or {})
    voci = presidio.get("items") if isinstance(presidio.get("items"), dict) else {}
    liquidazione = _voce_presidio(voci.get("liquidazione_giudice"))
    contributo = _voce_presidio(voci.get("contributo_unificato"))
    spese = _voce_presidio(voci.get("spese_esborsi"))
    sentenze = dict((dati or {}).get("sentenze") or {})
    giorno_oggi = data_da(oggi)
    scadute = [
        voce for voce in parcelle
        if voce["stato"] == "SCADUTA"
        or (voce["stato"] == "EMESSA" and voce["scadenza_iso"] and giorno_oggi and data_da(voce["scadenza_iso"]) < giorno_oggi)
    ]
    aperte = [voce for voce in parcelle if voce["stato"] in {"EMESSA", "SCADUTA"}]
    fatturato = _importo(sintesi.get("totale_fatturato"))
    incassato = _importo(sintesi.get("totale_incassato"))
    saldo = _importo(sintesi.get("saldo_aperto")) or round(max(fatturato - incassato, 0.0), 2)
    preventivato = _importo(sintesi.get("totale_preventivato") or sintesi.get("totale_preventivi"))
    conferito = _importo(sintesi.get("totale_conferito") or sintesi.get("totale_conferimenti"))
    bonifici = [voce for voce in parcelle if voce["stato"] == "PAGATA" and voce["bonifico"]]
    incassato_bonifico = round(sum(voce["totale"] for voce in bonifici), 2)
    liquidato = liquidazione.get("importo") or 0.0
    if not liquidato:
        liquidazione_incasso = ""
    elif liquidazione.get("pagato") or incassato >= liquidato:
        liquidazione_incasso = "incassata"
    elif incassato > 0:
        liquidazione_incasso = "parziale"
    else:
        liquidazione_incasso = "non_incassata"
    anticipazioni = _importo(presidio.get("anticipazioniDaRecuperare"))
    return {
        "presente": bool(sintesi) or bool(parcelle) or bool(voci),
        "preventivi": int(sintesi.get("preventivi_count") or 0),
        "conferimenti": int(sintesi.get("conferimenti_count") or 0),
        "parcelle": len(parcelle),
        "preventivato": preventivato,
        "preventivato_it": euro(preventivato),
        "conferito": conferito,
        "conferito_it": euro(conferito),
        "fatturato": fatturato,
        "fatturato_it": euro(fatturato) or ("€ 0,00" if parcelle else ""),
        "incassato": incassato,
        "incassato_it": euro(incassato) or ("€ 0,00" if fatturato else ""),
        "saldo_aperto": saldo,
        "saldo_aperto_it": euro(saldo) or ("€ 0,00" if fatturato else ""),
        "parcelle_aperte": aperte,
        "parcelle_scadute": scadute,
        "importo_scaduto": round(sum(voce["totale"] for voce in scadute), 2),
        "importo_scaduto_it": euro(sum(voce["totale"] for voce in scadute)),
        "ha_incarico": bool(int(sintesi.get("conferimenti_count") or 0) or int(sintesi.get("preventivi_count") or 0)),
        # Controllo pagamenti del fascicolo (stessa fonte della pagina del fascicolo e di Fatturazione).
        "presidio_stato": pulisci(presidio.get("stato")),
        "presidio_stato_etichetta": pulisci(presidio.get("statoLabel")),
        "liquidazione": liquidazione,
        "liquidato": liquidato,
        "liquidato_it": liquidazione.get("importo_it", ""),
        "liquidazione_incasso": liquidazione_incasso,
        "contributo_unificato": contributo,
        "spese": spese,
        "anticipazioni_da_recuperare": anticipazioni,
        "anticipazioni_da_recuperare_it": euro(anticipazioni),
        "bonifici": bonifici,
        "incassato_bonifico": incassato_bonifico,
        "incassato_bonifico_it": euro(incassato_bonifico) or ("€ 0,00" if incassato else ""),
        "sentenze_lette": int(dict(sentenze.get("totals") or {}).get("sentenze_lette") or 0),
    }


__all__ = ["economico"]
