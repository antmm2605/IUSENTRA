"""Come il capo del dispositivo definisce la data: l'«ancora» del termine.

Il giudice scrive la data in uno di questi modi, e solo questi si leggono:

* ``esplicita``: «entro il 15/01/2027», «udienza del 12 gennaio 2027 ore 9.30»;
* ``prima_udienza``: «almeno 10 giorni prima dell'udienza», «sino a 30 giorni liberi prima»;
* ``fino_udienza``: «sino alla data della predetta udienza», «entro la data dell'udienza»;
* ``da_evento``: «entro 20 giorni dalla comunicazione / notificazione / pronuncia /
  deposito / scadenza»;
* ``per_rinvio``: «nei termini di cui all'art. 171-ter», «ai sensi dell'art. 189»: la
  durata è quella di legge (tabella versionata delle regole);
* ``senza_decorrenza``: «nel termine di 30 giorni» senza dire da quando: è ambiguo e
  si chiede all'avvocato, mai si indovina.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .testo import GIORNI, NUMERO, date_vere, numero, ora_dopo

EVENTI = {"comunicazione": "comunicazione", "comunicato": "comunicazione", "notifica": "notificazione",
          "notificazione": "notificazione", "pronuncia": "pronuncia", "deposito": "deposito",
          "pubblicazione": "pubblicazione", "scadenza": "scadenza"}

_RE_PRIMA = re.compile(
    rf"(?:almeno|sino\s+a|fino\s+a|entro|non\s+oltre)\s+(?:il\s+)?(?:termine\s+di\s+)?{NUMERO}\s+{GIORNI}\s+(liberi\s+)?prima\s+"
    r"(?:dell[a']\s*|della\s+data\s+(?:dell[a']\s*)?)?(udienza|data|scadenza|trattazione|camera\s+di\s+consiglio|dibattimento)",
    re.I,
)
_RE_FINO_UDIENZA = re.compile(
    r"(?:sino|fino)\s+(?:al(?:la)?\s+)?(?:data\s+dell[a']\s*|giorno\s+dell[a']\s*)?(?:predetta\s+|suddetta\s+|medesima\s+)?udienza"
    r"|entro\s+(?:la\s+data\s+dell[a']\s*|il\s+giorno\s+dell[a']\s*)(?:predetta\s+)?udienza",
    re.I,
)
_RE_DA_EVENTO = re.compile(
    rf"(?:entro|nel\s+termine\s+(?:perentorio\s+|ordinatorio\s+)?di|termine\s+(?:perentorio\s+)?di)\s+(?:giorni\s+)?{NUMERO}\s*(?:{GIORNI})?\s+"
    r"(?:decorrent\w+\s+)?dal(?:la|l')?\s*(?:data\s+(?:di|della|del)\s+)?"
    r"(comunicazione|comunicato|notifica(?:zione)?|pronuncia|deposito|pubblicazione|scadenza)",
    re.I,
)
_RE_SENZA = re.compile(
    rf"(?:termine\s+(?:perentorio\s+|ordinatorio\s+)?di|entro)\s+(?:(?:giorni|gg\.?)\s+{NUMERO}|{NUMERO}\s*{GIORNI})", re.I,
)
_RE_RINVIO = re.compile(r"\b(?:ai\s+sensi|a\s+norma|di\s+cui)\s+(?:all'\s*|dell'\s*)?art(?:icolo|\.)?\s*(\d{2,4}(?:\s*[-\s]?\s*(?:bis|ter|quater|quinquies|sexies)(?:\.\d+)?)?)(?=.{0,20}?\bc\.?\s?p\.?\s?[cpa]\b)", re.I)
_RE_ENTRO_DATA = re.compile(r"\b(?:entro\s+(?:e\s+non\s+oltre\s+)?(?:il|la\s+data\s+del)|sino\s+al|fino\s+al|termine\s+(?:perentorio\s+)?(?:del|al))\s*$", re.I)
_RE_UDIENZA_PRIMA = re.compile(r"\budienza\b[^.;]{0,60}$|\b(?:al|per\s+il|il\s+giorno)\s*$", re.I)


@dataclass(frozen=True)
class Ancora:
    tipo: str  # esplicita | udienza_esplicita | prima_udienza | fino_udienza | da_evento | per_rinvio | senza_decorrenza
    giorno: date | None = None
    ora: str = ""
    giorni: int = 0
    liberi: bool = False
    evento: str = ""
    norma: str = ""
    letto: str = ""


def _data_nel_capo(capo: str) -> Ancora | None:
    for giorno, inizio, fine, scritto in date_vere(capo):
        prima = capo[max(0, inizio - 60):inizio]
        if _RE_ENTRO_DATA.search(prima):
            return Ancora("esplicita", giorno=giorno, ora=ora_dopo(capo, fine), letto=scritto)
        if _RE_UDIENZA_PRIMA.search(prima):
            return Ancora("udienza_esplicita", giorno=giorno, ora=ora_dopo(capo, fine), letto=scritto)
    return None


def ancore_esplicite(capo: str) -> list[tuple[Ancora, int, int]]:
    """Tutte le date esplicite «entro / sino al …» del capo, con la posizione: un capo può assegnarne più d'una."""
    trovate = []
    for giorno, inizio, fine, scritto in date_vere(capo):
        if _RE_ENTRO_DATA.search(capo[max(0, inizio - 60):inizio]):
            trovate.append((Ancora("esplicita", giorno=giorno, ora=ora_dopo(capo, fine), letto=scritto), inizio, fine))
    return trovate


def ancora_del_capo(capo: str) -> Ancora | None:
    """L'ancora della data scritta nel capo, o None se il capo non parla di date."""
    data = _data_nel_capo(capo)
    if data is not None and data.tipo == "esplicita":
        return data
    prima = _RE_PRIMA.search(capo)
    if prima:
        return Ancora("prima_udienza", giorni=numero(prima.group(1)) or 0, liberi=bool(prima.group(2)), letto=prima.group(0))
    evento = _RE_DA_EVENTO.search(capo)
    if evento:
        return Ancora("da_evento", giorni=numero(evento.group(1)) or 0, evento=EVENTI[evento.group(2).lower()], letto=evento.group(0))
    if _RE_FINO_UDIENZA.search(capo):
        return Ancora("fino_udienza", letto=_RE_FINO_UDIENZA.search(capo).group(0))
    if data is not None:
        return data
    rinvio = _RE_RINVIO.search(capo)
    if rinvio and re.search(r"\btermin\w*\b", capo, re.I):
        return Ancora("per_rinvio", norma=re.sub(r"[\s-]", "", rinvio.group(1).lower()), letto=rinvio.group(0))
    senza = _RE_SENZA.search(capo)
    if senza:
        return Ancora("senza_decorrenza", giorni=numero(senza.group(1) or senza.group(2)) or 0, letto=senza.group(0))
    return None


__all__ = ["Ancora", "EVENTI", "ancora_del_capo", "ancore_esplicite"]
