"""Lettura dei feed RSS 2.0 e Atom in voci grezze (titolo, collegamento, descrizione, data).

Il parsing usa `defusedxml`, che rifiuta entità esterne e definizioni di entità
(nessun accesso a file o rete durante la lettura). Il testo dell'ente non viene
riscritto: si tolgono solo i tag HTML e gli spazi superflui.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
import html as html_module
import re
from zoneinfo import ZoneInfo

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from pct.notiziario.rete import ErroreFonte

ROME_TZ = ZoneInfo("Europe/Rome")
_TAG = re.compile(r"<[^>]+>")
_DATA_NUMERICA = re.compile(r"\b([0-3]?\d)[/.-]([01]?\d)[/.-](20\d{2})\b")
_DATA_ISO = re.compile(r"\b(20\d{2})-([01]\d)-([0-3]\d)")


@dataclass(frozen=True)
class VoceGrezza:
    titolo: str
    collegamento: str
    descrizione: str
    data: str  # AAAA-MM-GG nel fuso Europe/Rome, "" se il feed non la dichiara
    identificativo: str = ""


def testo_pulito(valore: object) -> str:
    testo = html_module.unescape(_TAG.sub(" ", str(valore or "")))
    return " ".join(testo.replace("�", "").replace("\xa0", " ").split()).strip()


def data_della_voce(valore: object) -> str:
    """Data di pubblicazione dichiarata dal feed, convertita nel giorno di Roma."""
    testo = " ".join(str(valore or "").split())
    if not testo:
        return ""
    try:
        istante = parsedate_to_datetime(testo)
    except (TypeError, ValueError, IndexError, OverflowError):
        istante = None
    if istante is not None:
        if istante.tzinfo is None:
            return istante.date().isoformat()
        return istante.astimezone(ROME_TZ).date().isoformat()
    iso = _DATA_ISO.search(testo)
    if iso:
        try:
            istante = datetime.fromisoformat(testo.replace("Z", "+00:00"))
            if istante.tzinfo is not None:
                return istante.astimezone(ROME_TZ).date().isoformat()
        except ValueError:
            pass
        return _data_valida(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    numerica = _DATA_NUMERICA.search(testo)
    if numerica:
        return _data_valida(int(numerica.group(3)), int(numerica.group(2)), int(numerica.group(1)))
    return ""


def _data_valida(anno: int, mese: int, giorno: int) -> str:
    try:
        return date(anno, mese, giorno).isoformat()
    except ValueError:
        return ""


def _figlio(nodo, *nomi: str) -> str:
    for nome in nomi:
        for figlio in nodo:
            tag = figlio.tag.rsplit("}", 1)[-1] if isinstance(figlio.tag, str) else ""
            if tag.lower() == nome.lower():
                return figlio.text or ""
    return ""


def _collegamento(nodo) -> str:
    for figlio in nodo:
        tag = figlio.tag.rsplit("}", 1)[-1] if isinstance(figlio.tag, str) else ""
        if tag != "link":
            continue
        href = figlio.attrib.get("href")
        if href and figlio.attrib.get("rel", "alternate") == "alternate":
            return href.strip()
        if (figlio.text or "").strip():
            return figlio.text.strip()
    return ""


def leggi_feed(contenuto: bytes) -> list[VoceGrezza]:
    """Voci del feed nell'ordine pubblicato. Solleva `ErroreFonte` se il contenuto non è un feed."""
    try:
        radice = SafeET.fromstring(contenuto)
    except (SafeET.ParseError, DefusedXmlException, ValueError) as exc:
        raise ErroreFonte("La fonte non ha restituito un feed leggibile.") from exc
    nodi = [n for n in radice.iter() if isinstance(n.tag, str) and n.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
    if not nodi and radice.tag.rsplit("}", 1)[-1] not in {"rss", "feed", "RDF"}:
        raise ErroreFonte("La fonte non ha restituito un feed leggibile.")
    voci: list[VoceGrezza] = []
    for nodo in nodi:
        titolo = testo_pulito(_figlio(nodo, "title"))
        collegamento = _collegamento(nodo)
        if not titolo or not collegamento:
            continue
        voci.append(VoceGrezza(
            titolo=titolo,
            collegamento=collegamento,
            descrizione=testo_pulito(_figlio(nodo, "encoded", "description", "summary", "content")),
            data=data_della_voce(_figlio(nodo, "pubDate", "pubdate", "published", "updated", "date")),
            identificativo=testo_pulito(_figlio(nodo, "guid", "id")),
        ))
    return voci


__all__ = ["ROME_TZ", "VoceGrezza", "data_della_voce", "leggi_feed", "testo_pulito"]
