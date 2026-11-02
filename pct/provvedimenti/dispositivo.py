"""I capi del dispositivo: chi deve fare che cosa, ed entro quando.

Il dispositivo si apre con «P.Q.M.» o con i verbi che il giudice scrive in maiuscolo
(DISPONE, FISSA, ASSEGNA, RINVIA, ORDINA, INVITA, AVVISA, AMMETTE, NOMINA, CONDANNA,
RIGETTA…). Ogni capo va dal suo verbo al verbo successivo; da ciascuno si leggono:

* ``chi``: parti, ricorrente, resistente/convenuto, attore, CTU, cancelleria;
* ``oggetto``: note, memorie, notifica, deposito, pagamento, comparizione…;
* l'``ancora`` della data (``ancore.py``).

Nessun capo è inventato: un capo senza verbo del giudice non esiste, e la motivazione
che precede il «P.Q.M.» non apre termini.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ancore import Ancora, ancora_del_capo
from .testo import normalizza

VERBI = (
    "dispone", "fissa", "assegna", "rinvia", "ordina", "invita", "avvisa", "avverte", "ammette", "nomina",
    "condanna", "rigetta", "respinge", "accoglie", "dichiara", "ingiunge", "autorizza", "concede", "differisce",
    "revoca", "sostituisce", "manda", "onera", "pone", "liquida", "delega", "conferma", "riserva",
)
_RE_VERBO = re.compile(r"(?<![\w'])(?:si\s+)?(" + "|".join(VERBI) + r")(?![\w'])", re.I)
_RE_PQM = re.compile(r"\bP\.?\s?Q\.?\s?M\.?(?=\W)|\bper\s+questi\s+motivi\b", re.I)

_CHI = (
    ("consulente tecnico d'ufficio", r"\bc\.?\s?t\.?\s?u\b|\bconsulente\s+tecnico\s+d'\s*ufficio\b|\bal\s+consulente\b"),
    ("cancelleria", r"\b(?:alla\s+)?cancelleria\b|\bsegreteria\b"),
    ("ricorrente", r"\b(?:parte\s+)?ricorrente\b|\bistante\b"),
    ("resistente", r"\b(?:parte\s+)?resistente\b|\bconvenut[oa]\b|\bintimat[oa]\b"),
    ("attore", r"\b(?:parte\s+)?attric?e\b"),
    ("opponente", r"\bopponente\b"),
    ("parti", r"\b(?:alle\s+)?parti\b|\bdifensori\b"),
)
_OGGETTI = (
    ("note", r"\bnote\b"),
    ("costituzione", r"\bcostitu\w+\b"),
    ("memoria", r"\bmemori[ae]\b|\bcomparse?\b"),
    ("notifica", r"\bnotific\w+\b|\bintimazion\w+\b"),
    ("pagamento", r"\bpaga\w*\b|\bversa\w*\b|\bacconto\b|\bfondo\s+spese\b|\bcontributo\b"),
    ("comparizione", r"\bcompari\w+\b|\bcomparire\b"),
    ("giuramento", r"\bgiurament\w+\b"),
    ("relazione", r"\brelazione\b|\bbozza\b|\bosservazioni\b"),
    ("deposito", r"\bdeposit\w+\b|\bprodu\w+\b"),
)


@dataclass(frozen=True)
class Capo:
    verbo: str
    testo: str
    inizio: int
    chi: str
    oggetto: str
    ancora: Ancora | None
    perentorio: bool | None


def _primo(elenco: tuple[tuple[str, str], ...], testo: str) -> str:
    return next((nome for nome, espressione in elenco if re.search(espressione, testo, re.I)), "")


def chi_e_oggetto(testo: str, posizione: int | None = None) -> tuple[str, str]:
    """Chi e che cosa; con ``posizione``, il soggetto è l'ultimo nominato prima della data."""
    if posizione is None:
        return _primo(_CHI, testo), _primo(_OGGETTI, testo)
    vicino, dove = "", -1
    for nome, espressione in _CHI:
        for trovato in re.finditer(espressione, testo[:posizione], re.I):
            if trovato.start() > dove:
                vicino, dove = nome, trovato.start()
    return vicino, _primo(_OGGETTI, testo)


def _perentorio(testo: str) -> bool | None:
    if re.search(r"\bperentori\w*\b|\ba\s+pena\s+di\s+(?:decadenza|inammissibilit)", testo, re.I):
        return True
    if re.search(r"\bordinatori\w*\b", testo, re.I):
        return False
    return None


def inizio_dispositivo(testo: str) -> int:
    """La posizione del «P.Q.M.» (l'ultimo, se ce n'è più d'uno), altrimenti 0."""
    trovati = list(_RE_PQM.finditer(testo))
    return trovati[-1].end() if trovati else 0


def capi(testo: str) -> list[Capo]:
    """I capi del dispositivo, nell'ordine in cui il giudice li scrive."""
    pulito = normalizza(testo)
    base = inizio_dispositivo(pulito)
    corpo = pulito[base:]
    verbi = [m for m in _RE_VERBO.finditer(corpo) if m.group(1).isupper() or _a_inizio_frase(corpo, m.start())]
    elenco: list[Capo] = []
    for indice, trovato in enumerate(verbi):
        fine = verbi[indice + 1].start() if indice + 1 < len(verbi) else len(corpo)
        frase = corpo[trovato.start():fine].strip(" ;,.•-")[:600]
        elenco.append(Capo(
            verbo=trovato.group(1).lower(), testo=frase, inizio=base + trovato.start(),
            chi=_primo(_CHI, frase), oggetto=_primo(_OGGETTI, frase),
            ancora=ancora_del_capo(frase), perentorio=_perentorio(frase),
        ))
    return elenco


def _a_inizio_frase(testo: str, posizione: int) -> bool:
    """Un verbo minuscolo apre un capo solo a inizio frase o dopo «;», «:», «•», «e»: «di nomina» non è «NOMINA»."""
    prima = testo[max(0, posizione - 6):posizione]
    return posizione == 0 or bool(re.search(r"(?:[.;:•]|\be|\bed|,)\s*$", prima))


__all__ = ["Capo", "VERBI", "capi", "chi_e_oggetto", "inizio_dispositivo"]
