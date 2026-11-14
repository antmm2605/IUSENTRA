"""L'atto è dello studio? Lo dice il difensore che l'atto nomina, confrontato con gli avvocati dello studio.

Il difensore è indicato nell'atto di parte (art. 125 c.p.c.: l'atto è sottoscritto dal difensore) e nel provvedimento
che decide sulla domanda di quella parte («letto il ricorso … depositato da ALFA S.R.L. - Avv. MARIO ROSSI»); nella
relata di notifica in proprio l'avvocato notificante si dichiara («Io sottoscritto Avv. …», art. 3-bis L. 53/1994).
Se uno di questi è un avvocato dello studio, l'atto o la domanda sono dello studio; se l'atto nomina come difensore
solo avvocati estranei, non lo sono; se non nomina difensori, dagli atti non risulta.

Collaudo 10/11/2026 (decreto ingiuntivo, Giudice di Pace di Palmi): il presidio diceva «Dagli atti non risulta se
l'atto è dello studio» mentre il decreto nominava l'avvocato dello studio difensore del ricorrente.

Funzione pura: riceve il testo già letto e i nomi degli avvocati dello studio (dati dello studio), non apre file.
"""

from __future__ import annotations

import re
from typing import Iterable

# Le formule con cui l'atto nomina il difensore della parte che agisce o che deposita.
_FORMULE = (
    r"(?:depositat[oa]|propost[oa]|presentat[oa])\s+da\s+[^;\n]{0,160}?[-–,]\s*avv(?:\.|ocato)\s+(?P<n1>[A-ZÀ-Üa-zà-ü' ]{3,60})",
    r"(?:io\s+)?(?:il\s+)?sottoscritt[oa]\s+avv(?:\.|ocato)\s+(?P<n2>[A-ZÀ-Üa-zà-ü' ]{3,60})",
    r"rappresentat[oa]\s+e\s+difes[oa]\s+(?:dall[’']\s*|dal(?:l[ao])?\s+)?avv(?:\.|ocato|ocata)?\s+(?P<n3>[A-ZÀ-Üa-zà-ü' ]{3,60})",
    r"avv(?:\.|ocato)\s+(?P<n4>[A-ZÀ-Üa-zà-ü' ]{3,60}?)\s*,?\s*(?:c\.?\s*f\.?\s*[:.]?\s*[A-Z0-9]{16}\s*,?\s*)?(?:difensore|procuratore)\b",
)
_RE_FORMULE = re.compile("|".join(f"(?:{formula})" for formula in _FORMULE), re.I)
_PAROLE_VUOTE = {"avv", "avvocato", "dott", "prof", "e", "di", "del", "della", "c", "f", "cf"}


def _parole(nome: str) -> frozenset[str]:
    return frozenset(p for p in re.findall(r"[a-zà-ü']{2,}", str(nome or "").casefold()) if p not in _PAROLE_VUOTE)


def difensori_nominati(testo: str) -> list[frozenset[str]]:
    """Le parole del nome di ogni difensore che il testo nomina con una delle formule del difensore della parte."""
    esito = []
    for trovato in _RE_FORMULE.finditer(str(testo or "")):
        nome = next(valore for valore in trovato.groupdict().values() if valore)
        parole = _parole(nome)
        if len(parole) >= 2:
            esito.append(parole)
    return esito


def atto_dello_studio(testo: str, avvocati_studio: Iterable[str]) -> bool | None:
    """True se il difensore nominato è un avvocato dello studio, False se sono nominati solo difensori estranei, None
    se l'atto non nomina difensori o lo studio non ha avvocati registrati."""
    studio = [parole for nome in avvocati_studio or () if len(parole := _parole(nome)) >= 2]
    nominati = difensori_nominati(testo)
    if not studio or not nominati:
        return None
    for nominato in nominati:
        if any(avvocato <= nominato for avvocato in studio):
            return True
    return False


__all__ = ["atto_dello_studio", "difensori_nominati"]
