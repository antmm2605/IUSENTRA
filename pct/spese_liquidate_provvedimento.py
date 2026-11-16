"""Le spese liquidate da un provvedimento diverso dalla sentenza: decreto ingiuntivo, ordinanza, decreto.

Il giudice liquida le spese anche fuori dalla sentenza: nel decreto ingiuntivo «liquida le spese e le
competenze» del procedimento monitorio (art. 641, terzo comma, c.p.c.), nell'ordinanza che definisce il
procedimento semplificato (art. 281-terdecies c.p.c.), nei decreti e nelle ordinanze che chiudono un
procedimento (art. 91 c.p.c., che vale per ogni provvedimento che chiude il processo davanti al giudice).
Le spese si dividono in compensi del difensore (D.M. 55/2014, con il rimborso forfettario del 15%, art. 2,
comma 2) ed esborsi non imponibili (contributo unificato, marca, notifiche: art. 15, primo comma, n. 3,
D.P.R. 633/1972). La distrazione in favore del difensore antistatario segue l'art. 93 c.p.c.

Modulo puro: riusa la lettura del capo spese delle sentenze (``pct.spese_liquidate_lettura``) e aggiunge
gli esborsi; nessun credito senza importo letto (collaudo 10/11/2026, G-14: «€ 76,00 per spese non imponibili
ed € 300,00 per compensi professionali, oltre rimborso spese generali nella misura del 15%, Cpa e Iva»).
"""

from __future__ import annotations

import re
from typing import Any

from pct.spese_liquidate_lettura import MONEY_AMOUNT_PATTERN, compatta_testo, esborsi_inclusi_nel_liquidato, estrai_spese_liquidate, parse_importo

ETICHETTE = {
    "decreto ingiuntivo": ("decreto ingiuntivo", "art. 641, terzo comma, c.p.c."),
    "ordinanza": ("ordinanza", "art. 91 c.p.c."),
    "decreto": ("decreto", "art. 91 c.p.c."),
}
_ESBORSI = re.compile(
    r"(?:€|euro|EUR)\s*(?P<amount>" + MONEY_AMOUNT_PATTERN + r")\s*(?:,\s*)?per\s+(?:spese(?!\s+generali)(?:\s+non\s+imponibili|\s+vive|\s+esenti)?|esborsi)\b",
    re.IGNORECASE,
)
_ACCESSORI = re.compile(r"spese\s+generali|rimborso\s+forfettario|\bc\.?\s*p\.?\s*a\b|\biva\b", re.IGNORECASE)
_DISTRAZIONE = re.compile(r"\bdistra(?:e|endo|tt[aei]|rsi|zione)\b|\bantistatari", re.IGNORECASE)


def natura_provvedimento(etichetta: str) -> tuple[str, str] | None:
    """(natura, norma) per l'etichetta del catalogo, o None se non è un provvedimento che liquida spese fuori sentenza."""
    testo = " ".join(str(etichetta or "").casefold().split())
    if testo.startswith("sentenza") or "ricorso" in testo or "istanza" in testo or "precedente" in testo:
        return None
    for chiave, valore in ETICHETTE.items():
        if testo.startswith(chiave):
            return valore
    return None


def spese_liquidate(testo: str) -> dict[str, Any] | None:
    """Compensi, esborsi, accessori e distrazione liquidati nel provvedimento, con il brano che li prova."""
    compensi, brano = estrai_spese_liquidate(testo)
    if compensi is None:
        return None
    piano = compatta_testo(testo)
    esborsi = None
    for trovato in _ESBORSI.finditer(piano):
        if abs(trovato.start() - piano.find(brano[:40])) < 600 or not brano:
            esborsi = parse_importo(trovato.group("amount"))
            break
    inclusi, _ = esborsi_inclusi_nel_liquidato(brano, compensi)
    if inclusi is not None:
        compensi, esborsi = round(compensi - inclusi, 2), inclusi
    # La distrazione (art. 93 c.p.c.) segue di solito la liquidazione nella stessa frase o subito dopo
    # («… oltre accessori, il tutto da distrarsi a favore dell'avv. …»): si guarda anche il seguito del capo spese.
    posizione = piano.find(brano[:60]) if brano else -1
    seguito = piano[posizione:posizione + len(brano) + 300] if posizione >= 0 else brano
    return {"compensi": compensi, "esborsi": esborsi, "accessori": bool(_ACCESSORI.search(brano)),
            "distrazione": bool(_DISTRAZIONE.search(seguito)), "brano": brano}


__all__ = ["ETICHETTE", "natura_provvedimento", "spese_liquidate"]
