"""Quale parte difende lo studio: si propongono solo i termini che spettano al cliente.

Caso reale (Tribunale di Vicenza, sezione lavoro, RG 901/2026): lo studio difende il ricorrente, ma
dal decreto di fissazione dell'udienza (art. 415 c.p.c.) veniva proposta anche la «Costituzione del
convenuto con memoria difensiva» (art. 416 c.p.c.), che è un onere della controparte. Ogni regola della
tabella ``provvedimenti_regole`` dichiara ``chi`` deve agire: le regole di una parte determinata si
propongono solo se il cliente ha quel ruolo; quelle delle «parti», del giudice o della cancelleria
restano sempre. Se il ruolo del cliente non è certo, nessuna regola si scarta (fail-closed: meglio una
bozza in più da scartare che un termine del cliente perduto).

Il ruolo si ricava dalle parti scritte dalla cancelleria nella Comunicazione.xml («Ricorr. principale»,
«Resist. principale», art. 16 D.L. 179/2012; specifiche DGSIA) confrontate col cliente del fascicolo,
come fa la lettura del fascicolo (``pct/fascicolo_lettura/percorso._ruolo_cliente``).
"""

from __future__ import annotations

import re
from typing import Any

ATTIVO = "ricorrente"
PASSIVO = "resistente"

#: chi promuove il giudizio o l'impugnazione
_CHI_ATTIVI = frozenset({"ricorrente", "attore", "appellante", "opponente", "reclamante", "richiedente"})
#: chi lo subisce
_CHI_PASSIVI = frozenset({"convenuto", "resistente", "ingiunto", "appellato", "opposto", "reclamato"})


def _parole(nome: Any) -> set[str]:
    return {p for p in re.split(r"[^\wÀ-ÿ']+", str(nome or "").lower()) if len(p) > 1}


def _stessa_persona(a: Any, b: Any) -> bool:
    pa, pb = _parole(a), _parole(b)
    return bool(pa and pb) and (pa <= pb or pb <= pa)


def ruolo_cliente(cliente: Any, *, attore: Any = "", convenuto: Any = "", controparte: Any = "") -> str:
    """«ricorrente», «resistente» o "" se non si sa con certezza."""
    attivo = _stessa_persona(cliente, attore)
    passivo = _stessa_persona(cliente, convenuto)
    if attivo != passivo:
        return ATTIVO if attivo else PASSIVO
    if not attivo and controparte:
        contro_attivo, contro_passivo = _stessa_persona(controparte, attore), _stessa_persona(controparte, convenuto)
        if contro_attivo != contro_passivo:
            return PASSIVO if contro_attivo else ATTIVO
    return ""


def spetta_al_cliente(chi: Any, ruolo: str) -> bool:
    """La regola di ``chi`` riguarda il cliente con ``ruolo`` (sempre vero se il ruolo non è noto)."""
    soggetto = str(chi or "").strip().lower()
    if ruolo == ATTIVO:
        return soggetto not in _CHI_PASSIVI
    if ruolo == PASSIVO:
        return soggetto not in _CHI_ATTIVI
    return True


__all__ = ["ATTIVO", "PASSIVO", "ruolo_cliente", "spetta_al_cliente"]
