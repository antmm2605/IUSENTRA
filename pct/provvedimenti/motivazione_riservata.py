"""Sentenza con la motivazione riservata: «Fissa per il deposito della motivazione il termine di giorni 60».

Nel rito del lavoro il giudice legge il dispositivo e può fissare un termine non superiore a sessanta giorni per
il deposito della sentenza (art. 429, comma 1, c.p.c.); la sentenza è pubblicata con il deposito (art. 133 c.p.c.)
e da lì decorre il termine lungo per impugnare (art. 327 c.p.c.). Il termine lungo contato dal dispositivo resta
proposto perché è anticipato, quindi prudente, ma si dichiara provvisorio; la motivazione diventa un'attesa.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from .calcolo import calcola
from .modello import Voce
from .testo import NUMERO, numero

_RE_RISERVA = re.compile(
    rf"\bdeposito\s+della\s+(?:motivazione|sentenza)\s+(?:il\s+)?termine\s+di\s+(?:giorni\s+{NUMERO}|{NUMERO}\s+giorni)", re.I)
_NOTA = ("La motivazione è riservata (art. 429, comma 1, c.p.c.): il termine lungo decorre dal deposito della sentenza "
         "completa (artt. 133 e 327 c.p.c.). La data è contata dal dispositivo, quindi anticipata: aggiornarla al deposito.")


def voci_motivazione_riservata(pulito: str, voci: list[Voce], *, dispositivo_il: date | None, materia: str) -> list[Voce]:
    """Le voci della sentenza con l'attesa della motivazione e il termine lungo dichiarato provvisorio."""
    trovato = _RE_RISERVA.search(pulito)
    if trovato is None or dispositivo_il is None:
        return voci
    giorni = numero(trovato.group(1) or trovato.group(2)) or 0
    calcolo = calcola({"giorni": giorni, "direzione": "forward"}, dispositivo_il, materia=materia) if giorni else None
    aggiornate = [replace(voce, nota=" ".join(p for p in (voce.nota, _NOTA) if p), confidenza=min(voce.confidenza or 0.6, 0.6))
                  if voce.regola_id.endswith("327.impugnazione_lunga") else voce for voce in voci]
    if calcolo is not None:
        aggiornate.append(Voce(
            "giudice.motivazione_riservata", "attesa",
            f"Motivazione della sentenza attesa entro il {calcolo.giorno:%d/%m/%Y}: dal deposito decorrono i termini di impugnazione",
            norme=("cpc_429", "cpc_327"), prova=pulito[trovato.start():trovato.end() + 40][:300], chi="giudice",
            giorno=calcolo.giorno, calcolo=calcolo.spiegazione, dies_a_quo=dispositivo_il, confidenza=0.85,
            dati=(("Lettura del dispositivo", f"{dispositivo_il:%d/%m/%Y}", "data della sentenza"),),
        ))
    return aggiornate


__all__ = ["voci_motivazione_riservata"]
