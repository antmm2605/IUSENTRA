"""Un termine non è mai un'udienza: quali voci di scadenziario e agenda sono udienze vere.

L'udienza è il giorno in cui il giudice tiene (o sostituisce con il deposito di note, art. 127-ter c.p.c.) la
trattazione della causa. I termini che si contano a ritroso dall'udienza — notificare ricorso e decreto almeno trenta
giorni prima (art. 415, comma 5, c.p.c.), costituirsi almeno dieci giorni prima (art. 416, comma 1, c.p.c.), le
memorie integrative (art. 171-ter c.p.c.) — sono adempimenti di parte, non udienze: il loro titolo nomina l'udienza
(«almeno 10 giorni prima dell'udienza») ma la data non lo è. Il termine per le note che sostituiscono l'udienza vale
come data di udienza per effetto dell'art. 127-ter, ultimo comma, c.p.c. quando il termine è registrato con la sua fonte.

Collaudo 10/11/2026: «Preparare l'udienza del 12/11/2026» (era la costituzione del convenuto, l'udienza era il
23/11/2026) e «Preparare l'udienza del 08/01/2027» (era il termine per notificare, l'udienza era il 09/02/2027).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

STATI_CHIUSI = {"ANNULLATO", "ANNULLATA", "CANCELLATO", "RIFIUTATO"}
# Il titolo dichiara un adempimento contato dall'udienza: è un termine.
_TERMINE_RIFERITO = re.compile(
    r"\bprima\s+dell[’']?\s*udienza|\bdopo\s+l[’']?\s*udienza|\bcostituzion|\bnotific|\bmemori|\bdeposito\b|\btermine\b(?!\s+per\s+note\s+in\s+sostituzione)",
    re.I,
)
_UDIENZA_NEL_TITOLO = re.compile(r"^\s*(?:udienza|rinvio\s+(?:dell[’']?\s*)?udienza|fissazione\s+(?:dell[’']?\s*)?udienza|"
                                 r"riassegnazione\s+termine\s+per\s+note\s+in\s+sostituzione\s+udienza|"
                                 r"fissazione\s+termine\s+per\s+note\s+in\s+sostituzione\s+udienza)", re.I)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def _giorno(valore: Any) -> date | None:
    testo = _testo(valore)
    for formato, lunghezza in (("%Y-%m-%d", 10), ("%d/%m/%Y", 10)):
        try:
            return datetime.strptime(testo[:lunghezza], formato).date()
        except ValueError:
            continue
    return None


def e_udienza(voce: dict[str, Any]) -> bool:
    """La voce (scadenza o appuntamento serializzati) è un'udienza vera, non un termine riferito all'udienza.

    Vale il tipo dichiarato dal registro (``UDIENZA``); senza tipo vale il titolo che comincia con «Udienza»,
    «Rinvio udienza», «Fissazione udienza» o con la voce dell'udienza cartolare. Una voce di tipo termine
    (notifica, deposito, costituzione, termine perentorio) non è mai un'udienza, qualunque cosa dica il titolo.
    """
    if _testo(voce.get("stato")).upper() in STATI_CHIUSI:
        return False
    tipo = _testo(voce.get("tipo")).upper().replace(" ", "_")
    titolo = _testo(voce.get("titolo") or voce.get("title"))
    if tipo:
        return tipo == "UDIENZA"
    return bool(_UDIENZA_NEL_TITOLO.search(titolo)) and not _TERMINE_RIFERITO.search(titolo)


def udienze_future(voci: Iterable[dict[str, Any]], oggi: date) -> list[date]:
    """I giorni delle udienze vere da oggi in poi, in ordine."""
    giorni = set()
    from pct.note_127_ter.proposta import TITOLO_NOTE_127_TER

    for voce in voci or ():
        note_in_sostituzione = (
            _testo(voce.get("stato")).upper() == "APERTO"
            and _testo(voce.get("tipo")).upper() == "TERMINE_PERENTORIO"
            and _testo(voce.get("hearing_mode")) == "note_scritte"
            and bool(_testo(voce.get("hearing_mode_source")))
            and _testo(voce.get("titolo")).startswith(TITOLO_NOTE_127_TER)
        )
        if not (e_udienza(voce) or note_in_sostituzione):
            continue
        giorno = _giorno(voce.get("data") or voce.get("data_scadenza") or voce.get("data_ora"))
        if giorno and giorno >= oggi:
            giorni.add(giorno)
    return sorted(giorni)


def prossima_udienza(*, dichiarata: Any = "", scadenze: Iterable[dict[str, Any]] = (), appuntamenti: Iterable[dict[str, Any]] = (),
                     oggi: date) -> date | None:
    """La prossima udienza vera: quella del profilo, dello scadenziario (tipo UDIENZA) o dell'agenda (tipo UDIENZA)."""
    candidati = udienze_future([*scadenze, *appuntamenti], oggi)
    profilo = _giorno(dichiarata)
    if profilo and profilo >= oggi:
        candidati.append(profilo)
    return min(candidati) if candidati else None


def _data_re(giorno: date) -> str:
    return r"0?%d[./-]0?%d[./-]%d(?!\d)" % (giorno.day, giorno.month, giorno.year)


def udienza_nel_brano(contesto: str, giorno: date) -> bool:
    """Il brano dice espressamente che quel giorno è un'udienza («udienza del 16.10.2025», «all'udienza in data …»)."""
    testo = " ".join(str(contesto or "").split())
    return bool(re.search(r"udienza\s+(?:di\s+discussione\s+)?(?:del(?:\s+giorno)?|in\s+data|fissata\s+(?:per\s+)?(?:il|al))\s+"
                          + _data_re(giorno), testo, re.I))


def data_di_emissione(contesto: str, giorno: date) -> bool:
    """La data, nel brano letto, è quella del provvedimento («n. cronol. 1918/2026 del 02/02/2026», «emesso il …»,
    «Decreto fissazione udienza, emesso … in data 18/05/2026»), non un'udienza.

    L'udienza è il giorno fissato dal giudice per la trattazione (artt. 175 e 420 c.p.c.); il numero cronologico e la
    data di emissione identificano il provvedimento che la fissa (art. 135 c.p.c.); la sola data in calce no, perché note
    scritte e verbali portano in calce il giorno dell'udienza. Collaudo 10/11/2026: «Fissazione
    udienza discussione n. cronol. 1918/2026 del 02/02/2026» era diventata l'udienza del 02/02/2026.
    """
    testo = " ".join(str(contesto or "").split())
    data = _data_re(giorno)
    if udienza_nel_brano(testo, giorno):
        return False  # lo stesso brano dice che quel giorno è l'udienza
    return bool(re.search(r"(?:n\.?\s*cronol\.?|n\.?\s*cron\.?|n\.?\s*rep\.?|repert\w*)\s*\d+\s*/\s*\d{4}\s+del\s+" + data, testo, re.I)
                or re.search(r"(?:emess[oa]|pronunciat[oa]|pubblicat[oa])\b[^;\d]{0,80}?\s(?:in\s+data|il)\s+" + data, testo, re.I)
                or re.search(r"(?:emess[oa]|pronunciat[oa]|pubblicat[oa])\s+" + data, testo, re.I))


__all__ = ["data_di_emissione", "e_udienza", "prossima_udienza", "udienza_nel_brano", "udienze_future"]
