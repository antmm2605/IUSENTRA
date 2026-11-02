"""Quale udienza sostituisce il decreto che rinvia a «l'udienza già fissata» (art. 127-ter c.p.c.).

Il termine per le note scade «sino alla data della predetta udienza»: la data è quella
dell'udienza futura già presente nel fascicolo (agenda, scadenziario, data della prossima
udienza). Si propone solo se la candidata è **una**: senza udienze future, o con più date
diverse, la scelta resta all'avvocato e nessuna data viene indovinata.

Le date dell'agenda possono essere salvate con o senza fuso: ogni confronto avviene in ora
italiana (Europe/Rome), normalizzando entrambi i lati (regola CLAUDE.md sul fuso orario).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")
_LOG = logging.getLogger(__name__)
_STATI_CHIUSI = {"ANNULLATO", "RINVIATO", "COMPLETATO"}
_RE_RG = re.compile(r"\b(\d{1,7})\s*/\s*(\d{4})\b")


@dataclass(frozen=True)
class UdienzaRiferita:
    """L'udienza sostituita, oppure perché non si può indicarla da sola."""

    giorno: date | None
    ora: str = ""
    id_appuntamento: str = ""
    candidate: tuple[date, ...] = ()

    @property
    def esito(self) -> str:
        if self.giorno is not None:
            return "trovata"
        return "ambigua" if len(self.candidate) > 1 else "nessuna"


def _valore(oggetto: Any, nome: str) -> Any:
    valore = oggetto.get(nome) if isinstance(oggetto, dict) else getattr(oggetto, nome, "")
    return getattr(valore, "value", valore)


def _testo(oggetto: Any, nome: str) -> str:
    return str(_valore(oggetto, nome) or "").strip()


def _rome_aware(valore: datetime) -> datetime:
    return valore.replace(tzinfo=ROME_TZ) if valore.tzinfo is None else valore.astimezone(ROME_TZ)


def _quando(grezzo: Any) -> datetime | None:
    """Data e ora in Europe/Rome, accettando ISO con o senza fuso e la sola data."""
    testo = str(grezzo or "").strip()
    if not testo:
        return None
    try:
        return _rome_aware(datetime.fromisoformat(testo.replace("Z", "+00:00")))
    except ValueError:
        pass
    try:
        return _rome_aware(datetime.fromisoformat(testo[:10]))
    except ValueError:
        _LOG.info("Data d'udienza non leggibile, voce saltata: %r", testo[:40])
        return None


def normalizza_rg(valore: Any) -> str:
    trovato = _RE_RG.search(str(valore or ""))
    return f"{int(trovato.group(1))}/{trovato.group(2)}" if trovato else ""


def _del_fascicolo(appuntamento: Any, fascicolo_id: str, rg: str) -> bool:
    if fascicolo_id and _testo(appuntamento, "id_fascicolo") == fascicolo_id:
        return True
    nota = _testo(appuntamento, "note")
    if fascicolo_id and re.search(rf"^\s*Fascicolo\s*:\s*{re.escape(fascicolo_id)}\s*$", nota, flags=re.M | re.I):
        return True
    return bool(rg) and normalizza_rg(_testo(appuntamento, "procedimento")) == rg


def _udienze_in_agenda(appuntamenti: Iterable[Any], fascicolo_id: str, rg: str) -> Iterable[tuple[datetime, str]]:
    for voce in appuntamenti or []:
        if _testo(voce, "tipo").upper() != "UDIENZA" or _testo(voce, "stato").upper() in _STATI_CHIUSI:
            continue
        if _testo(voce, "external_uid").startswith("PEC_RICEZIONE:") or not _del_fascicolo(voce, fascicolo_id, rg):
            continue
        quando = _quando(_valore(voce, "data_ora"))
        if quando is not None:
            yield quando, _testo(voce, "id")


def _udienze_in_scadenziario(scadenze: Iterable[Any], fascicolo_id: str) -> Iterable[tuple[datetime, str]]:
    for voce in scadenze or []:
        if _testo(voce, "tipo").upper() != "UDIENZA" or _testo(voce, "stato").upper() not in {"APERTO", "SCADUTO"}:
            continue
        if not fascicolo_id or _testo(voce, "id_fascicolo") != fascicolo_id:
            continue
        quando = _quando(_valore(voce, "data_scadenza"))
        if quando is not None:
            yield quando, _testo(voce, "id_appuntamento")


def udienza_riferita(
    *,
    appuntamenti: Iterable[Any] = (),
    scadenze: Iterable[Any] = (),
    fascicolo_id: str = "",
    rg: str = "",
    prossima_udienza: Any = "",
    oggi: date,
) -> UdienzaRiferita:
    """La sola udienza futura del fascicolo (oggi compreso), o l'elenco delle candidate."""
    rg = normalizza_rg(rg)
    per_giorno: dict[date, tuple[str, str]] = {}
    fonti: list[tuple[datetime, str]] = [
        *_udienze_in_agenda(appuntamenti, fascicolo_id, rg),
        *_udienze_in_scadenziario(scadenze, fascicolo_id),
    ]
    prossima = _quando(prossima_udienza)
    if prossima is not None:
        fonti.append((prossima, ""))
    for quando, id_appuntamento in fonti:
        giorno = quando.date()
        if giorno < oggi:
            continue
        ora = quando.strftime("%H:%M") if (quando.hour, quando.minute) != (0, 0) else ""
        attuale = per_giorno.get(giorno, ("", ""))
        per_giorno[giorno] = (attuale[0] or ora, attuale[1] or id_appuntamento)
    candidate = tuple(sorted(per_giorno))
    if len(candidate) != 1:
        return UdienzaRiferita(giorno=None, candidate=candidate)
    ora, id_appuntamento = per_giorno[candidate[0]]
    return UdienzaRiferita(giorno=candidate[0], ora=ora, id_appuntamento=id_appuntamento, candidate=candidate)


__all__ = ["ROME_TZ", "UdienzaRiferita", "normalizza_rg", "udienza_riferita"]
