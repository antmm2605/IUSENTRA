"""Regole d'identità dal titolo, per area del diritto.

L'ordine è quello di applicazione: prima le aree con titoli specifici, poi i
documenti comuni, infine le regole generiche che raccolgono quello che nessuna
area ha riconosciuto. Una regola specifica non deve mai stare dopo una
generica che la assorbirebbe (il ricorso per decreto ingiuntivo prima del
ricorso; la relazione CTU prima della perizia di parte).
"""

from __future__ import annotations

from . import (
    amministrativo,
    civile,
    comuni,
    crisi,
    esecuzioni,
    famiglia,
    generiche,
    immigrazione,
    lavoro,
    locazioni,
    penale,
    sinistri,
    studio,
    tributario,
)
from ._modello import CONFIDENZA_TITOLO, RegolaTitolo, regola
from .fonti import FONTI_TITOLI

AREE: tuple[tuple[str, tuple[RegolaTitolo, ...]], ...] = (
    ("esecuzioni", esecuzioni.REGOLE),
    ("penale", penale.REGOLE),
    ("tributario", tributario.REGOLE),
    ("amministrativo", amministrativo.REGOLE),
    ("lavoro", lavoro.REGOLE),
    ("famiglia", famiglia.REGOLE),
    ("locazioni", locazioni.REGOLE),
    ("crisi", crisi.REGOLE),
    ("immigrazione", immigrazione.REGOLE),
    ("civile", civile.REGOLE),
    ("sinistri", sinistri.REGOLE),
    ("studio", studio.REGOLE),
    ("comuni", comuni.REGOLE),
    ("generiche", generiche.REGOLE),
)

REGOLE_TITOLO: tuple[RegolaTitolo, ...] = tuple(regola_ for _, regole in AREE for regola_ in regole)

_ID_DUPLICATI = [voce for voce in {r.id for r in REGOLE_TITOLO} if sum(1 for r in REGOLE_TITOLO if r.id == voce) > 1]
if _ID_DUPLICATI:  # pragma: no cover - errore di programmazione, non di dati
    raise RuntimeError(f"regole d'identità con lo stesso identificativo: {_ID_DUPLICATI}")


def area_della_regola(rule_id: str) -> str:
    for nome, regole in AREE:
        if any(r.id == rule_id for r in regole):
            return nome
    return ""


__all__ = ["AREE", "CONFIDENZA_TITOLO", "FONTI_TITOLI", "REGOLE_TITOLO", "RegolaTitolo", "area_della_regola", "regola"]
