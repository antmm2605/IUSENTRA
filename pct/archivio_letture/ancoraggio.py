"""L'ancoraggio: una data è un fatto solo se il testo dice che cosa è.

«All'udienza del 10/03/2026», «entro il 31/12/2025», «notificato il 15/08/2025»,
«ricevuta di avvenuta consegna … 12/03/2026 ore 10:15»: la parola che precede
la data (o la segue da vicino) le dà il campo. Una data senza ancora — un
numero in una tabella, una data qualunque in mezzo al testo — non è un fatto e
non si propone a nessuno. Le date di nascita, dei documenti d'identità, dei
protocolli, delle fatture e delle versioni sono ancore negative: la data resta
dov'è.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FINESTRA_PRIMA = 110
FINESTRA_DOPO = 45
FINESTRA_NEGATIVA = 30

# (campo, espressione sul testo che precede la data). L'ordine conta solo a parità di distanza.
ANCORE: tuple[tuple[str, str], ...] = (
    ("udienza", r"udienz[ae]|comparizion[ei]|camera di consiglio|discussion[ei]|rinvi[ao]t?[ao]?|trattazion[ei]|fissa(?:ta|to|re)?"),
    ("termine", r"termin[ei]|entro (?:il|e non oltre|la data)|non oltre|scad(?:e|enza|ono)|perentori[oa]|decorren[zt][ae]|a decorrere"),
    ("costituzione", r"costituzion[ei]|costituirsi"),
    ("deposito", r"deposit(?:o|ato|ata|ata il|are)|data (?:di )?deposito|depositat[oa]"),
    ("notifica", r"notificat[oa]|notifica(?:zione)?|data (?:di )?notifica|notificare"),
    ("accettazione", r"accettazione|accettat[oa]"),
    ("consegna", r"avvenuta consegna|consegna|consegnat[oa]"),
    ("comunicazione", r"comunicazion[ei]|comunicat[oa]|biglietto di cancelleria"),
    ("provvedimento", r"sentenza|ordinanza|decreto|provvedimento|emess[oa]|pubblicat[oa]|pronunciat[oa]|depositata in cancelleria"),
    ("data_atto", r"(?:l[iì]'?|addì|add[iì]'?)\s*,?\s*$"),
)
_ANCORE_RE = tuple((campo, re.compile(rf"(?:{espressione})", re.IGNORECASE)) for campo, espressione in ANCORE)
_NEGATIVE = re.compile(
    r"nat[oa]\s+(?:a|il|in)|nascita|rilasciat[oa]|scadenz[ae]\s+(?:del documento|carta|passaporto|patente)|valid[oa]\s+fino|"
    r"documento\s+d'identit|carta\s+d'identit|passaporto|patente|codice\s+fiscale|prot(?:\.|ocollo)|fattura\s+n|parcella\s+n|"
    r"vers(?:\.|ione)|iban|c\.?c\.?\s*n|dal\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}\s+al\s*$|"
    # la data di una legge o di un decreto normativo non è una data del fascicolo
    r"(?:legge|l\.|d\.?\s?lgs\.?|d\.?\s?p\.?\s?r\.?|d\.?\s?m\.?|d\.?\s?l\.|d\.?\s?p\.?\s?c\.?\s?m\.?|decreto\s+(?:legislativo|ministeriale|legge))\s*(?:n\.?\s*\d+(?:/\d+)?\s*(?:del)?\s*)?$",
    re.IGNORECASE,
)
_ORA = re.compile(r"(?:ore|alle ore|alle|h\.?)\s*(?P<ora>[01]?\d|2[0-3])\s*[:.,]\s*(?P<minuti>[0-5]\d)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Ancora:
    campo: str
    testo: str
    distanza: int


def _spazi(testo: str) -> str:
    return " ".join(str(testo or "").split())


def ancora_per(testo: str, inizio: int, fine: int, *, limite: int = 0, limite_dopo: int | None = None) -> Ancora | None:
    """L'ancora più vicina alla data che sta in testo[inizio:fine]; None se la data non ha campo.

    `limite` è la fine della data precedente e `limite_dopo` l'inizio della
    successiva: un'ancora vale per la prima data che la segue, non per una
    sfilza di date in tabella; l'ancora che segue la data vale solo sulla
    stessa riga e prima del punto.
    """
    prima = testo[max(0, inizio - FINESTRA_PRIMA, limite):inizio]
    if _NEGATIVE.search(prima[-FINESTRA_NEGATIVA:]):
        return None
    migliore: Ancora | None = None
    for campo, espressione in _ANCORE_RE:
        for match in espressione.finditer(prima):
            distanza = len(prima) - match.end()
            if migliore is None or distanza < migliore.distanza:
                migliore = Ancora(campo=campo, testo=_spazi(match.group(0)), distanza=distanza)
    if migliore is not None:
        return migliore
    dopo = testo[fine:min(fine + FINESTRA_DOPO, limite_dopo if limite_dopo is not None else len(testo))]
    dopo = re.split(r"[\n.;]", dopo, maxsplit=1)[0]
    for campo, espressione in _ANCORE_RE:
        if campo == "data_atto":
            continue
        match = espressione.search(dopo)
        if match and not _NEGATIVE.search(dopo[:match.start()]):
            distanza = match.start()
            if migliore is None or distanza < migliore.distanza:
                migliore = Ancora(campo=campo, testo=_spazi(match.group(0)), distanza=distanza)
    return migliore


def ora_vicina(testo: str, fine: int) -> str:
    """L'orario scritto subito dopo la data («ore 9.30», «alle 10:15»), in forma HH:MM."""
    match = _ORA.search(testo[fine:fine + FINESTRA_DOPO])
    if not match:
        return ""
    return f"{int(match.group('ora')):02d}:{match.group('minuti')}"


def brano(testo: str, inizio: int, fine: int, *, raggio: int = 90) -> str:
    return _spazi(testo[max(0, inizio - raggio):min(len(testo), fine + raggio)])


__all__ = ["ANCORE", "Ancora", "ancora_per", "brano", "ora_vicina"]
