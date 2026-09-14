"""Cifre lette come lettere: «2O24» e' 2024, «art. l» e' art. 1.

Il motore confonde lo zero con la O e l'uno con la l minuscola, la I maiuscola
o la barra verticale. Si corregge solo dentro sequenze che sono numeri per
forma (date, importi, numeri di ruolo, anni) o subito dopo «art.», «n.»,
«co.», «lett.»: mai dentro una parola.
"""

from __future__ import annotations

import re

from .regola import Regola, regola_regex

_CONFUSE = {"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "Ì": "1"}
# Una sequenza numerica per forma: almeno una cifra, almeno una lettera confusa,
# nient'altro che cifre, lettere confuse e separatori di numeri.
_SEQUENZA = re.compile(r"(?<![\w€])(?=[\dOoIl|.,/\-]*\d)(?=[\dOoIl|.,/\-]*[OoIl|])([\dOoIl|]+(?:[.,/\-][\dOoIl|]+)*)(?![\w])")
_DOPO_RIFERIMENTO = re.compile(r"\b((?:[aA]rtt?|[nN]|[cC]o|[cC]omma|[lL]ett|[nN]n|[pP]ag|[pP]agg)\.?\s+)([lIO|][\dOIl|]*|[\dOIl|]*[lIO|][\dOIl|]*)(?=\b|-)")
_ANNO = re.compile(r"\b(1[89]|2[O0])([\dOoIl|]{2})\b")


def _cifre(valore: str) -> str:
    return "".join(_CONFUSE.get(carattere, carattere) for carattere in valore)


def _sequenza(match: re.Match[str]) -> str:
    grezzo = match.group(1)
    # «l/2024» e' plausibile, «ll» da solo no: servono almeno tre segni o un
    # separatore, altrimenti si sta guardando un pezzo di parola.
    if len(grezzo) < 3 and not any(separatore in grezzo for separatore in ".,/-"):
        return grezzo
    return _cifre(grezzo)


def _dopo_riferimento(match: re.Match[str]) -> str:
    return f"{match.group(1)}{_cifre(match.group(2))}"


def _anno(match: re.Match[str]) -> str:
    return f"{_cifre(match.group(1))}{_cifre(match.group(2))}"


REGOLE: tuple[Regola, ...] = (
    regola_regex("num.riferimento.v1", "numero dopo «art.», «n.», «co.»", "Lettere lette al posto delle cifre subito dopo il riferimento.", _DOPO_RIFERIMENTO, _dopo_riferimento),
    regola_regex("num.sequenza.v1", "cifre lette come lettere", "O e l al posto di 0 e 1 dentro date, importi e numeri.", _SEQUENZA, _sequenza),
    regola_regex("num.anno.v1", "anno", "Anno con lettere al posto delle cifre.", _ANNO, _anno),
)

__all__ = ["REGOLE"]
