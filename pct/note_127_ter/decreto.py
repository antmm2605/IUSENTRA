"""Riconoscere il decreto di trattazione scritta e ciò che dispone (art. 127-ter c.p.c.).

Art. 127-ter c.p.c. (D.Lgs. 149/2022): il giudice può disporre che l'udienza sia sostituita
dal deposito di note scritte contenenti le sole istanze e conclusioni, assegnando un termine
perentorio; il giorno di scadenza del termine è considerato data di udienza. Le parti possono
opporsi entro cinque giorni dalla comunicazione (comma 2).

Qui si legge solo ciò che il decreto scrive: nessuna data, nessun orario e nessun onere viene
dedotto se il testo non lo dice. Quando il decreto rinvia a «l'udienza già fissata» o alla
«predetta udienza» senza indicarne la data, la data non si inventa: la cerca
``udienza_riferita`` nel fascicolo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_RE_127_TER = re.compile(r"\b127\s*[-\s]?\s*ter\b", re.I)
_RE_NOTE = re.compile(r"\bnote\s+(?:scritte|di\s+trattazione)\b|\btrattazione\s+scritta\b", re.I)
_RE_SOSTITUZIONE = re.compile(r"\bsostitu\w*\s+(?:dell'\s*|l'\s*)?udienza\b|\budienza\b.{0,80}?\bsostituit[ao]\b", re.I)
_RE_SENTENZA = re.compile(r"\bin\s+nome\s+del\s+popolo\s+italiano\b|\bdefinitivamente\s+(?:pronunciando|decidendo)\b", re.I)
#: il decreto non fissa una data propria: rinvia all'udienza già presente nel fascicolo
_RE_UDIENZA_FISSATA = re.compile(
    r"\budienza\s+gi[aà]\s+fissata\b|\b(?:predetta|suddetta|medesima)\s+udienza\b"
    r"|\bdata\s+dell'\s*udienza\s+(?:gi[aà]\s+)?fissata\b",
    re.I,
)
_RE_ORA_LIMITE = re.compile(r"\bentro\s+le\s+ore\s+(\d{1,2})(?:\s*[.:,]\s*(\d{2}))?", re.I)
_RE_SOLO_ISTANZE = re.compile(r"\b(?:sole|solo|esclusivamente(?:\s+le)?)\s+istanze\s+e\s+(?:le\s+)?conclusioni\b", re.I)
_RE_INDICAZIONI = re.compile(r"note\s+per\s+la\s+trattazione\s+scritta", re.I)
_RE_PROVA_NOTIFICA = re.compile(
    r"mancata\s+costituzione\s+(?:di\s+|della\s+)?(?:parte\s+)?resistente.{0,240}?prova\s+dell'\s*avvenuta\s+notific",
    re.I | re.S,
)
_RE_EML = re.compile(r"\.eml\b|avvenuta\s+consegna", re.I)
_RE_CONFORMITA = re.compile(r"attestazione\s+di\s+conformit", re.I)
_RE_DECISIONE = re.compile(r"nel\s+termine\s+di\s+(\d{1,3})\s*(?:gg\.?|giorni)\s+dalla\s+scadenza", re.I)
_DATA = r"(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{4})"
_RE_DATA = re.compile(rf"\b{_DATA}\b")
#: la data in calce («Palmi, 31/10/2026») è la pronuncia, non il termine
_RE_PRONUNCIA = re.compile(rf"\b[A-ZÀ-Ü][a-zà-ù']+(?:\s+[A-ZÀ-Üa-zà-ù']+){{0,2}},\s*(?:l[iì]\s*)?{_DATA}\b")


@dataclass(frozen=True)
class DecretoNoteScritte:
    """Ciò che il decreto dispone, così come lo scrive."""

    rinvia_udienza_fissata: bool
    data_propria: bool
    ora_limite: str
    solo_istanze_conclusioni: bool
    indicazioni_richieste: bool
    invito_prova_notifica: bool
    prova_telematica: bool
    prova_cartacea: bool
    giorni_decisione: int
    data_pronuncia: date | None

    @property
    def senza_data(self) -> bool:
        """Il termine coincide con l'udienza già fissata e il decreto non ne scrive la data."""
        return self.rinvia_udienza_fissata and not self.data_propria


def _normalizza(testo: str) -> str:
    return " ".join(str(testo or "").replace("’", "'").replace("‘", "'").split())


def _data(giorno: str, mese: str, anno: str) -> date | None:
    try:
        return date(int(anno), int(mese), int(giorno))
    except ValueError:
        return None


def _ora(trovata: re.Match[str] | None) -> str:
    if trovata is None:
        return ""
    ore, minuti = int(trovata.group(1)), int(trovata.group(2) or 0)
    return f"{ore:02d}:{minuti:02d}" if ore < 24 and minuti < 60 else ""


def riconosci_decreto(testo: str) -> DecretoNoteScritte | None:
    """Il decreto ex art. 127-ter c.p.c. che sostituisce l'udienza, o None se il testo non lo è.

    Una sentenza che richiama il 127-ter come modalità già svolta non è un decreto di
    trattazione scritta: non apre termini per le note.
    """
    pulito = _normalizza(testo)
    if not (_RE_127_TER.search(pulito) and _RE_NOTE.search(pulito) and _RE_SOSTITUZIONE.search(pulito)):
        return None
    if _RE_SENTENZA.search(pulito):
        return None
    pronunce = {d for t in _RE_PRONUNCIA.finditer(pulito) if (d := _data(t.group(1), t.group(2), t.group(3)))}
    senza_calce = _RE_PRONUNCIA.sub(" ", pulito)
    decisione = _RE_DECISIONE.search(pulito)
    prova = bool(_RE_PROVA_NOTIFICA.search(pulito))
    return DecretoNoteScritte(
        rinvia_udienza_fissata=bool(_RE_UDIENZA_FISSATA.search(pulito)),
        data_propria=any(_data(t.group(1), t.group(2), t.group(3)) for t in _RE_DATA.finditer(senza_calce)),
        ora_limite=_ora(_RE_ORA_LIMITE.search(pulito)),
        solo_istanze_conclusioni=bool(_RE_SOLO_ISTANZE.search(pulito)),
        indicazioni_richieste=bool(_RE_INDICAZIONI.search(pulito)),
        invito_prova_notifica=prova,
        prova_telematica=prova and bool(_RE_EML.search(pulito)),
        prova_cartacea=prova and bool(_RE_CONFORMITA.search(pulito)),
        giorni_decisione=int(decisione.group(1)) if decisione else 0,
        data_pronuncia=next(iter(pronunce)) if len(pronunce) == 1 else None,
    )


__all__ = ["DecretoNoteScritte", "riconosci_decreto"]
