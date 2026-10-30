"""Regole d'identità dal titolo, per area del diritto.

L'ordine è quello di applicazione: prima le aree con titoli specifici, poi i
documenti comuni, infine le regole generiche che raccolgono quello che nessuna
area ha riconosciuto. Una regola specifica non deve mai stare dopo una
generica che la assorbirebbe (il ricorso per decreto ingiuntivo prima del
ricorso; la relazione CTU prima della perizia di parte).
"""

from __future__ import annotations

from . import (
    adr,
    amministrativo,
    civile,
    comuni,
    consumo,
    crisi,
    crisi_procedure,
    deposito,
    esecuzioni,
    esecuzioni_atti,
    famiglia,
    generiche,
    immigrazione,
    istanze_civili,
    lavoro,
    locazioni,
    penale,
    penale_difesa,
    processo_civile,
    procure,
    pubblico,
    sinistri,
    societario,
    stragiudiziale,
    studio,
    tributario,
    tutela,
)
from ._modello import CONFIDENZA_TITOLO, RegolaTitolo, regola
from .fonti import FONTI_TITOLI

AREE: tuple[tuple[str, tuple[RegolaTitolo, ...]], ...] = (
    ("esecuzioni", esecuzioni.REGOLE),
    ("esecuzioni_atti", esecuzioni_atti.REGOLE),
    ("penale", penale.REGOLE),
    ("penale_difesa", penale_difesa.REGOLE),
    ("pubblico", pubblico.REGOLE),
    ("tributario", tributario.REGOLE),
    ("amministrativo", amministrativo.REGOLE),
    ("lavoro", lavoro.REGOLE),
    ("societario", societario.REGOLE),
    ("famiglia", famiglia.REGOLE),
    ("tutela", tutela.REGOLE),
    ("locazioni", locazioni.REGOLE),
    ("crisi", crisi.REGOLE),
    ("crisi_procedure", crisi_procedure.REGOLE),
    ("immigrazione", immigrazione.REGOLE),
    ("adr", adr.REGOLE),
    ("consumo", consumo.REGOLE),
    ("procure", procure.REGOLE),
    ("istanze_civili", istanze_civili.REGOLE),
    ("processo_civile", processo_civile.REGOLE),
    ("civile", civile.REGOLE),
    ("sinistri", sinistri.REGOLE),
    ("studio", studio.REGOLE),
    ("stragiudiziale", stragiudiziale.REGOLE),
    ("deposito", deposito.REGOLE),
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
