"""L'udienza a cui il provvedimento si riferisce, e come si tiene.

Prima vale l'udienza che il provvedimento stesso fissa o a cui rinvia (capi FISSA,
RINVIA, DIFFERISCE, o «udienza del …» nell'avviso della segreteria). Se il
provvedimento non scrive una data, si usa l'udienza futura del fascicolo con
``pct.note_127_ter.udienza_riferita`` (una sola candidata, Europe/Rome): con più
candidate o nessuna, la scelta resta all'avvocato.

Modalità (come si tiene l'udienza), lette dal testo:

* ``cartolare``: sostituita da note scritte (art. 127-ter c.p.c.);
* ``da_remoto``: collegamento audiovisivo (art. 127-bis c.p.c.; art. 81 D.Lgs. 175/2024);
* ``camera_di_consiglio`` / ``pubblica_udienza``: processo tributario (art. 81 D.Lgs.
  175/2024) e amministrativo;
* ``in_presenza``: comparizione personale disposta o richiesta.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pct.note_127_ter.udienza_riferita import UdienzaRiferita, udienza_riferita

from .dispositivo import Capo
from .testo import date_vere, estratto, ora_dopo

MODALITA = {
    "cartolare": "udienza cartolare (note scritte, art. 127-ter c.p.c.)",
    "da_remoto": "udienza da remoto (collegamento audiovisivo)",
    "camera_di_consiglio": "camera di consiglio",
    "pubblica_udienza": "pubblica udienza",
    "in_presenza": "udienza in presenza",
}
_SEGNALI_MODALITA = (
    ("cartolare", r"\b127\s*[-\s]?\s*ter\b|\bnote\s+scritte\b.{0,80}\bsostitu|\btrattazione\s+scritta\b"),
    ("da_remoto", r"\b127\s*[-\s]?\s*bis\b|\bcollegament\w+\s+audiovisiv|\bda\s+remoto\b|\bvideoconferenza\b|\bmicrosoft\s+teams\b"),
    ("camera_di_consiglio", r"\bcamera\s+di\s+consiglio\b"),
    ("pubblica_udienza", r"\bpubblica\s+udienza\b|\budienza\s+pubblica\b"),
    ("in_presenza", r"\bin\s+presenza\b|\bcomparizione\s+personale\b|\bcomparire\s+personalmente\b"),
)
_RE_CONTESTO_UDIENZA = re.compile(
    r"\b(?:udienza|trattazione|camera\s+di\s+consiglio|dibattimento|comparizione|discussione)\b[^.;]{0,70}$", re.I,
)
_RE_NON_UDIENZA = re.compile(r"\b(?:entro|sino|fino|termine|scadenza|deposit\w*|pronunciat\w*|emess\w*)\b[^.;]{0,25}$", re.I)
_VERBI_UDIENZA = {"fissa", "rinvia", "differisce", "dispone", "nomina", "ammette"}


@dataclass(frozen=True)
class UdienzaLetta:
    giorno: date
    ora: str
    modalita: str
    prova: str
    da_capo: bool


def modalita(testo: str) -> str:
    for nome, espressione in _SEGNALI_MODALITA:
        if re.search(espressione, testo, re.I):
            return nome
    return ""


def udienze_lette(testo: str, capi_letti: Iterable[Capo], *, oggi: date) -> list[UdienzaLetta]:
    """Le udienze future scritte nel provvedimento: prima quelle dei capi FISSA/RINVIA."""
    dai_capi: dict[date, UdienzaLetta] = {}
    for capo in capi_letti:
        if capo.verbo not in _VERBI_UDIENZA or capo.ancora is None or capo.ancora.tipo != "udienza_esplicita":
            continue
        # Un capo può fissare più udienze («l'udienza del … e l'udienza del …»): si leggono tutte.
        for giorno, inizio, fine, _ in date_vere(capo.testo):
            prima = capo.testo[max(0, inizio - 80):inizio]
            if giorno < oggi or not _RE_CONTESTO_UDIENZA.search(prima) or _RE_NON_UDIENZA.search(prima):
                continue
            dai_capi.setdefault(giorno, UdienzaLetta(giorno, ora_dopo(capo.testo, fine), modalita(capo.testo) or modalita(testo),
                                                     capo.testo[:300], True))
    if dai_capi:
        return sorted(dai_capi.values(), key=lambda u: u.giorno)
    lette: dict[date, UdienzaLetta] = {}
    for giorno, inizio, fine, _ in date_vere(testo):
        prima = testo[max(0, inizio - 80):inizio]
        if giorno < oggi or not _RE_CONTESTO_UDIENZA.search(prima) or _RE_NON_UDIENZA.search(prima):
            continue
        intorno = testo[max(0, inizio - 200):fine + 200]
        lette.setdefault(giorno, UdienzaLetta(giorno, ora_dopo(testo, fine), modalita(intorno) or modalita(testo),
                                              estratto(testo, inizio, fine), False))
    return sorted(lette.values(), key=lambda u: u.giorno)


def udienza_del_fascicolo(
    *, oggi: date, fascicolo_id: str = "", rg: str = "", appuntamenti: Iterable[Any] = (), scadenze: Iterable[Any] = (),
    prossima_udienza: Any = "",
) -> UdienzaRiferita:
    """L'udienza futura del fascicolo, solo se è una; altrimenti le candidate per la domanda."""
    if not fascicolo_id and not rg and not prossima_udienza:
        return UdienzaRiferita(giorno=None)
    return udienza_riferita(appuntamenti=appuntamenti, scadenze=scadenze, fascicolo_id=fascicolo_id, rg=rg,
                            prossima_udienza=prossima_udienza, oggi=oggi)


__all__ = ["MODALITA", "UdienzaLetta", "modalita", "udienza_del_fascicolo", "udienze_lette"]
