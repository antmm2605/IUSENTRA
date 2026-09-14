"""Marcatori degli elenchi: puntati, numerati, per lettera, romani, decimali.

Un atto scandisce i motivi e le conclusioni con elenchi, e l'elenco va
restituito come tale: il marcatore riconosciuto dice di che tipo e' la voce e
che numero porta, cosi' che il documento finale numeri le voci come l'originale
e non ricominci da uno. Il riconoscimento tiene conto della voce precedente:
«c.» e' un marcatore se viene dopo «b.», altrimenti e' l'abbreviazione di
«comma»; «i)» e' romano se apre la lista, e' la lettera i se segue «h)».
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .numeri_romani import normalizza_romano, valore_romano

PUNTATO = "puntato"
NUMERATO = "numerato"
LETTERA = "lettera"
ROMANO = "romano"
DECIMALE = "decimale"

_PUNTATO = re.compile(r"^([-•·–—*▪■●○◦►➢✓✔❖»])\s+(?=\S)")
_NUMERATO = re.compile(r"^\(?(\d{1,3})(?:[.)]|°|º)\s+(?=\S)")
_DECIMALE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})[.)]?\s+(?=[^\d\s])")
_LETTERA_PARENTESI = re.compile(r"^\(?([a-zA-Z])\)\s+(?=\S)")
_LETTERA_PUNTO = re.compile(r"^([a-zA-Z])\.\s+(?=[^\d\s])")
_ROMANO_PARENTESI = re.compile(r"^\(?([ivxlIVXL|l1]{1,6})\)\s+(?=\S)")
_ROMANO_PUNTO = re.compile(r"^([ivxlIVXL|l1]{1,6})\.\s+(?=[^\d\s])")
# Lettere che da sole sono anche abbreviazioni forensi («c.» comma, «v.» vedi,
# «n.» numero, «p.» pagina, «s.» seguenti, «l.» legge): marcatore solo in
# continuazione di un elenco per lettere.
_LETTERE_AMBIGUE = frozenset("cdlmnpstv")
_ROMANI_AMBIGUI = frozenset({"v", "x", "l", "V", "X", "L"})


@dataclass(frozen=True)
class Marcatore:
    """Il segno che apre una voce di elenco, letto e classificato."""

    tipo: str
    valore: int
    testo: str
    livello: int = 1

    def come_dizionario(self) -> dict[str, object]:
        return {"tipo": self.tipo, "valore": self.valore, "testo": self.testo, "livello": self.livello}


def _lettera_valore(lettera: str) -> int:
    return ord(lettera.lower()) - ord("a") + 1


def continua(precedente: Marcatore | None, nuovo: Marcatore) -> bool:
    """Vero se la voce nuova segue la precedente nello stesso elenco."""
    if precedente is None or precedente.tipo != nuovo.tipo:
        return False
    if nuovo.tipo == PUNTATO:
        return True
    if nuovo.tipo == DECIMALE:
        return nuovo.livello == precedente.livello and nuovo.valore == precedente.valore + 1
    return nuovo.valore == precedente.valore + 1


def _romano(grezzo: str, con_parentesi: bool, precedente: Marcatore | None) -> Marcatore | None:
    candidato = normalizza_romano(grezzo)
    if not candidato:
        return None
    valore = valore_romano(candidato)
    if valore == 0 or valore > 60:
        return None
    marcatore = Marcatore(ROMANO, valore, grezzo + (")" if con_parentesi else "."))
    if con_parentesi or continua(precedente, marcatore):
        return marcatore
    # Un elenco romano puo' aprirsi con «I.»; «V.», «X.» e «L.» da soli sono
    # abbreviazioni («vedi», «legge»), non voci.
    if valore == 1 and grezzo not in _ROMANI_AMBIGUI:
        return marcatore
    return None


def _lettera(lettera: str, con_parentesi: bool, precedente: Marcatore | None) -> Marcatore | None:
    marcatore = Marcatore(LETTERA, _lettera_valore(lettera), lettera + (")" if con_parentesi else "."))
    if continua(precedente, marcatore):
        return marcatore
    if con_parentesi:
        return marcatore
    if lettera.islower() and lettera not in _LETTERE_AMBIGUE:
        return marcatore
    return None


def marcatore_di(testo: str, *, precedente: Marcatore | None = None) -> Marcatore | None:
    """Il marcatore in testa alla riga, se la riga apre una voce di elenco."""
    riga = str(testo or "").lstrip()
    if not riga:
        return None
    if match := _PUNTATO.match(riga):
        return Marcatore(PUNTATO, 0, match.group(1))
    if match := _DECIMALE.match(riga):
        parti = match.group(1).split(".")
        return Marcatore(DECIMALE, int(parti[-1]), match.group(1), livello=len(parti))
    if match := _NUMERATO.match(riga):
        return Marcatore(NUMERATO, int(match.group(1)), match.group(0).strip())
    for espressione, con_parentesi in ((_ROMANO_PARENTESI, True), (_ROMANO_PUNTO, False)):
        if match := espressione.match(riga):
            grezzo = match.group(1)
            # «i)» dopo «h)» e' la lettera i, non il romano I.
            if len(grezzo) == 1 and grezzo.isalpha() and precedente is not None and precedente.tipo == LETTERA:
                lettera = _lettera(grezzo, con_parentesi, precedente)
                if lettera is not None:
                    return lettera
            romano = _romano(grezzo, con_parentesi, precedente)
            if romano is not None:
                return romano
    for espressione, con_parentesi in ((_LETTERA_PARENTESI, True), (_LETTERA_PUNTO, False)):
        if match := espressione.match(riga):
            return _lettera(match.group(1), con_parentesi, precedente)
    return None


def senza_marcatore(testo: str, marcatore: Marcatore | None) -> str:
    """Il testo della voce senza il segno che la apre."""
    riga = str(testo or "").lstrip()
    if marcatore is None:
        return riga
    for espressione in (_PUNTATO, _DECIMALE, _NUMERATO, _ROMANO_PARENTESI, _ROMANO_PUNTO, _LETTERA_PARENTESI, _LETTERA_PUNTO):
        match = espressione.match(riga)
        if match:
            return riga[match.end():].strip()
    return riga


def canonico(marcatore: Marcatore) -> str:
    """Il marcatore come lo scriverebbe un atto ben composto."""
    if marcatore.tipo == PUNTATO:
        return "•"
    if marcatore.tipo == NUMERATO:
        return f"{marcatore.valore}."
    if marcatore.tipo == LETTERA:
        return f"{chr(ord('a') + marcatore.valore - 1)})"
    if marcatore.tipo == ROMANO:
        return f"{_romano_da_intero(marcatore.valore)}."
    return f"{marcatore.testo}"


def _romano_da_intero(valore: int) -> str:
    coppie = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    resto = valore
    risultato = ""
    for peso, lettere in coppie:
        while resto >= peso:
            risultato += lettere
            resto -= peso
    return risultato


__all__ = [
    "DECIMALE",
    "LETTERA",
    "Marcatore",
    "NUMERATO",
    "PUNTATO",
    "ROMANO",
    "canonico",
    "continua",
    "marcatore_di",
    "senza_marcatore",
]
