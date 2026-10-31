"""Le quote di una ricevuta telematica pagoPA: quanto è contributo unificato e quanto altro.

Una sola RT può pagare insieme il contributo unificato (art. 13 D.P.R. 115/2002) e
l'anticipazione forfettaria dell'art. 30 (27 euro) o altri diritti: ogni voce è un
`datiSingoloPagamento` con il proprio `singoloImportoPagato` e la propria causale
(specifiche PagamentiTelematiciGiustizia). Il contributo pagato è la somma delle sole
quote con causale «contributo unificato», mai il totale della ricevuta.

Regola unica per il caricamento della ricevuta nel fascicolo e per l'archivio delle letture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree

_CAUSALE_CU = re.compile(r"contributo\s+unificato", re.IGNORECASE)
_CAUSALE_ART_30 = re.compile(r"anticipazion\w*\s+forfettari\w*|\bart\.?\s*30\b|diritti\s+forfettari", re.IGNORECASE)


@dataclass(frozen=True)
class QuoteRicevuta:
    contributo: Decimal
    art_30: Decimal
    altre: Decimal
    totale: Decimal
    errore: str = ""


def _contenuto_xml(data: bytes) -> bytes:
    from pct.pagamenti_giustizia import _sblocca_payload

    return _sblocca_payload(data)


def quote_della_ricevuta(data: bytes, totale_dichiarato: float) -> QuoteRicevuta:
    """Quote per causale; `errore` se le quote non tornano col totale o il contributo non è identificato."""
    vuote = QuoteRicevuta(Decimal(0), Decimal(0), Decimal(0), Decimal(0))
    try:
        radice = ElementTree.fromstring(_contenuto_xml(data))
    except Exception:
        return QuoteRicevuta(**{**vuote.__dict__, "errore": "XML non leggibile come ricevuta telematica."})
    contributo, art_30, altre, tutte = Decimal(0), Decimal(0), Decimal(0), []
    for nodo in radice.iter():
        if nodo.tag.split("}")[-1] != "datiSingoloPagamento":
            continue
        campi = {el.tag.split("}")[-1]: str(el.text or "").strip() for el in nodo.iter()}
        try:
            importo = Decimal(campi.get("singoloImportoPagato", ""))
            if not importo.is_finite() or importo < 0:
                raise InvalidOperation
        except InvalidOperation:
            return QuoteRicevuta(**{**vuote.__dict__, "errore": "Una quota della ricevuta non ha un importo valido."})
        tutte.append(importo)
        causale = f"{campi.get('causaleVersamento', '')} {campi.get('datiSpecificiRiscossione', '')}"
        if _CAUSALE_CU.search(causale):
            contributo += importo
        elif _CAUSALE_ART_30.search(causale):
            art_30 += importo
        else:
            altre += importo
    totale = Decimal(str(totale_dichiarato))
    if not totale.is_finite() or totale < 0:
        return QuoteRicevuta(contributo, art_30, altre, Decimal(0), "Il totale della ricevuta non è un importo valido.")
    if not tutte or abs(sum(tutte) - totale) > Decimal("0.01"):
        return QuoteRicevuta(contributo, art_30, altre, totale, "Le quote della ricevuta non coincidono con il totale pagato.")
    if not contributo:
        return QuoteRicevuta(contributo, art_30, altre, totale, "La ricevuta non identifica separatamente il contributo unificato.")
    return QuoteRicevuta(contributo, art_30, altre, totale)


__all__ = ["QuoteRicevuta", "quote_della_ricevuta"]
