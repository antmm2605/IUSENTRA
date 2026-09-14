"""Numeri romani: «Sez. Vl» e' la Sezione VI, «comma lll» e' il comma III.

Il motore legge la I maiuscola come l minuscola, 1 o barra verticale. Un
numero romano si riconosce da dove sta (dopo «Sez.», «Capo», «Titolo»,
«Libro»; non dopo «comma», che negli atti porta un numero) o dalla sua forma (solo lettere romane, con almeno una I confusa), e
la correzione vale solo se il risultato e' un numero romano ben formato.
"""

from __future__ import annotations

import re

from .regola import Regola, regola_regex

_ROMANO = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_CONFUSE = {"l": "I", "1": "I", "|": "I", "!": "I", "Ì": "I", "í": "I", "ì": "I"}
_CONTESTI = (
    "Sez|Sezione|Sezioni|Capo|Capi|Titolo|Titoli|Libro|Libri|Parte|Parti|Tomo|Volume|Vol|Cap|"
    "Allegato|All|Tabella|Tab|Fase|Grado|Classe|Punto|Paragrafo|Par|§|Modulo|Mod|"
    "Lotto|Blocco|Categoria|Cat|Fascia|Scaglione|Livello|Quadro|Sottosezione"
)
_DOPO_CONTESTO = re.compile(rf"\b({_CONTESTI})(\.?\s+)([IVXLCDMivxlcdm|l1!Ììí]{{1,8}})(?=\b|[).,;:])", re.IGNORECASE)
_TOKEN = re.compile(r"(?<![\w])(?=[IVXLCDMl1|]*[IVXLCDM])(?=[IVXLCDMl1|]*[l1|])([IVXLCDMl1|]{3,8})(?![\w])(?!\.(?:m[oaie]|ss)\b)")
# Parole italiane fatte solo di lettere romane e l: non sono numeri.
_PAROLE_NON_ROMANE = frozenset({"Ill", "ill", "ILL", "Lll", "lll"})
_TUTTE_L = re.compile(r"(?<![\w'])(l{3,4})(?![\w])")


def romano_valido(valore: str) -> bool:
    return bool(valore) and bool(_ROMANO.match(valore))


def valore_romano(valore: str) -> int:
    """Valore intero di un numero romano ben formato (0 se non lo e')."""
    if not romano_valido(valore):
        return 0
    pesi = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    totale = 0
    precedente = 0
    for carattere in reversed(valore):
        peso = pesi[carattere]
        totale += -peso if peso < precedente else peso
        precedente = max(precedente, peso)
    return totale


def normalizza_romano(grezzo: str) -> str:
    """Il numero romano ben formato letto dal motore, o la stringa vuota."""
    candidato = "".join(_CONFUSE.get(carattere, carattere) for carattere in grezzo).upper()
    return candidato if romano_valido(candidato) else ""


def _dopo_contesto(match: re.Match[str]) -> str:
    contesto, spazio, grezzo = match.group(1), match.group(2), match.group(3)
    # «co. 1-bis», «Sez. 4»: un numero e' un numero, anche dopo un contesto romano.
    if re.fullmatch(r"[\d|!]+", grezzo):
        return match.group(0)
    candidato = normalizza_romano(grezzo)
    if not candidato or candidato == grezzo:
        return match.group(0)
    return f"{contesto}{spazio}{candidato}"


def _token(match: re.Match[str]) -> str:
    grezzo = match.group(1)
    if grezzo in _PAROLE_NON_ROMANE:
        return grezzo
    candidato = normalizza_romano(grezzo)
    return candidato if candidato and candidato != grezzo else grezzo


def _tutte_l(match: re.Match[str]) -> str:
    candidato = normalizza_romano(match.group(1))
    return candidato or match.group(1)


REGOLE: tuple[Regola, ...] = (
    regola_regex("rom.contesto.v1", "numero romano dopo Sez., Capo, Titolo, comma", "Lettere confuse riportate al numero romano che il contesto richiede.", _DOPO_CONTESTO, _dopo_contesto),
    regola_regex("rom.token.v1", "numero romano con I letta come l", "Numero romano ricomposto da lettere confuse («Vl» → «VI»).", _TOKEN, _token),
    regola_regex("rom.solo_l.v1", "numero romano di sole I", "«lll» riportato a «III».", _TUTTE_L, _tutte_l),
)

__all__ = ["REGOLE", "normalizza_romano", "romano_valido", "valore_romano"]
