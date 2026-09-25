"""Distretto e circondario da indicare nella maschera «Ufficio Destinazione» del PDP.

Il PDP chiede Tipo Ufficio, Distretto (26 distretti di corte d'appello),
Circondario/Circolo e Sede/Ufficio. Si ricavano dal bundle ufficiale degli
uffici giudiziari (anagrafica del Ministero: comune e distretto di ogni
ufficio), cercando il tribunale del comune nominato nel fascicolo o nel registro.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from . import catalogo


def _chiave(valore: str) -> str:
    base = unicodedata.normalize("NFKD", str(valore or "")).casefold()
    parole = re.findall(r"[a-z]+", "".join(c for c in base if not unicodedata.combining(c)))
    return "".join(p for p in parole if p not in {"di", "d", "del", "della"})


def sede_pdp(nome_ufficio: str, uffici: Iterable[dict[str, Any]]) -> dict[str, str]:
    """{distretto, circondario} per il PDP; vuoti se il comune non si riconosce."""
    nome = _chiave(nome_ufficio)
    if not nome:
        return {"distretto": "", "circondario": ""}
    candidati = []
    for ufficio in uffici:
        if ufficio.get("tipo") != "TRIBUNALE" or not ufficio.get("comune_ministero"):
            continue
        citta = re.sub(r"(?i)^tribunale( ordinario)? di ", "", str(ufficio.get("nome") or ""))
        for variante in {ufficio["comune_ministero"], str(ufficio["comune_ministero"]).split(" - ")[0], citta}:
            chiave = _chiave(variante)
            if chiave and nome.endswith(chiave):
                candidati.append((len(chiave), ufficio))
    if not candidati:
        return {"distretto": "", "circondario": ""}
    tribunale = max(candidati, key=lambda c: c[0])[1]
    distretto_bundle = _chiave(tribunale.get("distretto_ministero") or tribunale.get("distretto") or "")
    distretto = next((d for d in catalogo.distretti() if _chiave(d) == distretto_bundle), "")
    return {"distretto": distretto, "circondario": str(tribunale["comune_ministero"]).split(" - ")[0].upper()}


__all__ = ["sede_pdp"]
