"""Riconoscimento della citazione di un articolo nel testo di una pronuncia («art. 414 c.p.c.», «articolo 63 del d.lgs.
n. 165 del 2001»). Usato per leggere i passaggi (scripts/conoscenza_passaggi_pronunce.py) e per la pertinenza delle
questioni interpretative (lex/conoscenza/trasversali.py)."""
from __future__ import annotations

import re

_CODICI = {
    "c.c.": r"(?:c\.\s?c\.|cod\.\s?civ\.?|codice civile)",
    "c.p.c.": r"(?:c\.\s?p\.\s?c\.|cod\.\s?proc\.\s?civ\.?|codice di procedura civile)",
    "c.p.p.": r"(?:c\.\s?p\.\s?p\.|cod\.\s?proc\.\s?pen\.?|codice di procedura penale)",
    "c.p.": r"(?:c\.\s?p\.(?!\s?[acp]\.)|cod\.\s?pen\.?|codice penale)",
    "c.p.a.": r"(?:c\.\s?p\.\s?a\.|cod\.\s?proc\.\s?amm\.?|codice del processo amministrativo|d\.\s?lgs\.?\s*(?:n\.\s*)?104(?:/|\s+del\s+)2010)",
}


def modello_citazione(citazione: str) -> str | None:
    """Espressione che riconosce la citazione dell'articolo nel testo di una pronuncia («art. 414 c.p.c.»,
    «articolo 63 del d.lgs. n. 165 del 2001»)."""
    m = re.match(r"art\.\s*([\d]+)(?:-?\s?(bis|ter|quater|quinquies|sexies|septies|octies))?\s+(.+)$", citazione.strip(), re.I)
    if not m:
        return None
    numero, suffisso, atto = m.group(1), m.group(2), m.group(3).strip().lower()
    art = rf"\bart(?:icol[oi]|t?\.)\s*{numero}" + (rf"\s?-?\s?{suffisso}\b" if suffisso else r"(?![\d]|\s?-?\s?(?:bis|ter|quater)\b)")
    if atto in _CODICI:
        atto_rx = _CODICI[atto]
    else:
        n = re.search(r"(\d+)/(\d{4})", atto)
        if not n:
            return None
        atto_rx = rf"(?:n\.\s*)?{n.group(1)}(?:/|\s+del\s+(?:\d{{1,2}}\s+\w+\s+)?){n.group(2)}"
    return art + (r"[^.;]{0,90}?" if atto in _CODICI else r"[^;]{0,60}?") + atto_rx
