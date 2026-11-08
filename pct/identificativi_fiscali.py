"""Controllo formale di codice fiscale e partita IVA italiani.

Basi:
- D.P.R. 605/1973, art. 2 e D.M. 23/12/1976 (Sistemi di codificazione dei soggetti
  da iscrivere all'anagrafe tributaria): codice fiscale alfanumerico di 16 caratteri
  per le persone fisiche, con carattere di controllo calcolato sui primi 15 secondo
  le tabelle dei caratteri in posizione pari e dispari (omocodia compresa); codice
  numerico di 11 cifre per i soggetti diversi dalle persone fisiche (enti,
  società, associazioni), con cifra di controllo sulle prime 10.
- D.P.R. 633/1972, art. 35: la partita IVA è di 11 cifre (matricola, codice
  ufficio, cifra di controllo), con lo stesso algoritmo del codice numerico.
"""

from __future__ import annotations

import re

from pct.codice_fiscale import _checksum

_CF_PERSONA = re.compile(r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$")
_NUMERICO = re.compile(r"^\d{11}$")


def normalizza(valore: str) -> str:
    return re.sub(r"\s+", "", str(valore or "")).upper()


def cifra_controllo_numerico(prime_10: str) -> int:
    """Cifra di controllo di partita IVA e codice fiscale numerico (D.M. 23/12/1976)."""
    somma = 0
    for indice, carattere in enumerate(prime_10):
        cifra = int(carattere)
        if indice % 2 == 1:  # posizioni pari (2a, 4a, ...) contate da 1
            cifra *= 2
            if cifra > 9:
                cifra -= 9
        somma += cifra
    return (10 - somma % 10) % 10


def formato_codice_fiscale(valore: str) -> bool:
    """Forma ammessa: 16 caratteri della persona fisica oppure 11 cifre dei soggetti non persone fisiche."""
    cf = normalizza(valore)
    return bool(_CF_PERSONA.match(cf) or _NUMERICO.match(cf))


def controllo_codice_fiscale(valore: str) -> bool:
    """True se forma e carattere di controllo sono corretti."""
    cf = normalizza(valore)
    if _CF_PERSONA.match(cf):
        return _checksum(cf[:15]) == cf[15]
    if _NUMERICO.match(cf):
        return cifra_controllo_numerico(cf[:10]) == int(cf[10])
    return False


def formato_partita_iva(valore: str) -> bool:
    return bool(_NUMERICO.match(normalizza(valore)))


def controllo_partita_iva(valore: str) -> bool:
    piva = normalizza(valore)
    return bool(_NUMERICO.match(piva)) and cifra_controllo_numerico(piva[:10]) == int(piva[10])
