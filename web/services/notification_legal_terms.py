"""Termini di legge già calcolati per il fascicolo, mostrati accanto al presidio delle notifiche.

Rito del lavoro: quando il decreto ordina di notificare ricorso e decreto «nei termini di legge», la pipeline PEC
propone in scadenziario i termini dell'art. 415, commi 4 e 5, c.p.c. (`pct.notifica_ricorso_lavoro`): il presidio
li mostra accanto all'ordine di notificazione.

Il presidio non inventa termini: per una sentenza ricevuta il termine certo è quello lungo per
l'impugnazione (art. 327 c.p.c., sei mesi dal deposito, con la sospensione feriale fuori dalle controversie di
lavoro: art. 1 e art. 3 L. 742/1969), già proposto nello scadenziario dalla comunicazione di deposito
(`pct.termine_lungo_sentenza`). Qui lo si legge soltanto: notificando la sentenza decorre per la controparte il
termine breve dell'art. 325 c.p.c., quindi la notifica è utile prima della scadenza del termine lungo.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

MARCATORE = "SENTENZA_327:"


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def termine_lungo_del_fascicolo(fascicolo_id: str, scadenziario: Any) -> dict[str, str] | None:
    """La scadenza del termine lungo più vicina ancora aperta, o None se lo scadenziario non la contiene."""
    if not fascicolo_id or scadenziario is None:
        return None
    try:
        scadenze = scadenziario.tutte(solo_aperte=False, id_fascicolo=fascicolo_id)
    except Exception:
        return None
    candidati = [s for s in scadenze if MARCATORE in _valore(s, "note") and _valore(s, "stato").upper() not in {"COMPLETATO", "ANNULLATO"}]
    if not candidati:
        return None
    scelta = min(candidati, key=lambda s: _valore(s, "data_scadenza"))
    return {
        "date": _valore(scelta, "data_scadenza")[:10],
        # Il titolo della scadenza porta già impugnazione e norma della giurisdizione (c.p.c., c.p.a., D.Lgs. 546/1992).
        "label": _valore(scelta, "titolo") or "Termine lungo per impugnare",
        "state": "bozza da confermare" if _valore(scelta, "stato").upper() == "BOZZA" else "in scadenziario",
        "note": "Notificando la sentenza decorre per la controparte il termine breve dalla notifica.",
        "href": f"/scadenziario/{quote(_valore(scelta, 'id'), safe='')}",
    }


def termine_di_notifica_lavoro(fascicolo_id: str, scadenziario: Any) -> dict[str, str] | None:
    """Il primo termine aperto dell'art. 415 c.p.c. proposto dalla PEC del decreto, o None."""
    if not fascicolo_id or scadenziario is None:
        return None
    try:
        scadenze = scadenziario.tutte(solo_aperte=False, id_fascicolo=fascicolo_id)
    except Exception:
        return None
    candidati = [s for s in scadenze if "LAV_415_NOTIFICA" in _valore(s, "note")
                 and _valore(s, "stato").upper() not in {"COMPLETATO", "ANNULLATO"}]
    if not candidati:
        return None
    scelta = min(candidati, key=lambda s: _valore(s, "data_scadenza"))
    return {
        "date": _valore(scelta, "data_scadenza")[:10],
        "label": "Termine per notificare ricorso e decreto (art. 415 c.p.c.)",
        "state": "bozza da confermare" if _valore(scelta, "stato").upper() == "BOZZA" else "in scadenziario",
        "note": "Dieci giorni dalla pronuncia del decreto (termine ordinatorio) e almeno trenta giorni prima dell'udienza.",
        "href": f"/scadenziario/{quote(_valore(scelta, 'id'), safe='')}",
    }


def termine_per_presidio(notification_case: str, fascicolo_id: str, cache: dict[str, Any]) -> dict[str, str] | None:
    """Sentenze: termine lungo; ordini di notificazione: termini dell'art. 415. Una lettura per fascicolo e caso."""
    caso = str(notification_case or "")
    lettore = termine_lungo_del_fascicolo if "judgment" in caso else termine_di_notifica_lavoro if "order" in caso else None
    if lettore is None:
        return None
    chiave = f"{lettore.__name__}:{fascicolo_id}"
    if chiave not in cache:
        try:
            from web.helpers import get_scadenziario

            cache[chiave] = lettore(fascicolo_id, get_scadenziario())
        except Exception:
            cache[chiave] = None
    return cache[chiave]


__all__ = ["termine_di_notifica_lavoro", "termine_lungo_del_fascicolo", "termine_per_presidio"]
