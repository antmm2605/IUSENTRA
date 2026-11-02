"""La materia del provvedimento, cioè quale rito ne governa i termini.

Le materie sono quelle dei riti, non quelle sostanziali: impresa e crisi, consumatori,
banca, condominio, esecuzioni seguono il codice di procedura civile («civile»); il
lavoro e la previdenza hanno il rito degli artt. 409 ss. c.p.c. («lavoro», senza
sospensione feriale: art. 3 L. 742/1969); la famiglia il rito degli artt. 473-bis ss.;
penale, amministrativo (c.p.a.) e tributario (D.Lgs. 175/2024) hanno regole proprie e
gli artt. 127-bis e 127-ter c.p.c. non vi si applicano.

La materia dichiarata dal fascicolo prevale; altrimenti si legge dall'ufficio e dal
testo. Se il testo non dà indizi si resta al rito civile, che è quello di default dei
provvedimenti del giudice ordinario.
"""

from __future__ import annotations

import re
from typing import Any

from pct.pec_provvedimento_terms import is_labour_matter

from .testo import normalizza

MATERIE_RITO = ("civile", "lavoro", "famiglia", "penale", "amministrativo", "tributario")
#: riti in cui valgono le norme del c.p.c. sulle udienze (127-bis, 127-ter)
RITI_CPC = frozenset({"civile", "lavoro", "famiglia"})

_SEGNALI = (
    ("tributario", r"\bcorte\s+di\s+giustizia\s+tributaria\b|\bcommissione\s+tributaria\b|\bD\.?\s?Lgs\.?\s*(?:n\.\s*)?(?:546/1992|175/2024)\b"),
    ("amministrativo", r"\btribunale\s+amministrativo\s+regionale\b|\bconsiglio\s+di\s+stato\b|\bc\.?\s?p\.?\s?a\.?\b|\bT\.?\s?A\.?\s?R\.?\s"),
    ("penale", r"\bc\.?\s?p\.?\s?p\.?\b|\bimputat[oaie]\b|\bprocura\s+della\s+repubblica\b|\bdibattimento\b|\bg\.?\s?i\.?\s?p\.?\b|\bg\.?\s?u\.?\s?p\.?\b"),
    ("famiglia", r"\b473\s*[-\s]?\s*bis\b|\bseparazione\s+(?:personale|giudiziale|consensuale)\b|\bdivorzio\b|\bscioglimento\s+del\s+matrimonio\b|\bresponsabilit[aà]\s+genitoriale\b"),
)
#: valori di ``Fascicolo.tipo`` e delle materie dichiarate, ricondotti al rito
_ALIAS = {
    "lavoro": "lavoro", "previdenza": "lavoro", "labor": "lavoro", "labour": "lavoro",
    "famiglia": "famiglia", "persone e famiglia": "famiglia",
    "penale": "penale", "diritto e procedura penale": "penale",
    "amministrativo": "amministrativo", "diritto amministrativo e appalti": "amministrativo",
    "tributario": "tributario", "diritto tributario": "tributario",
}
#: «CIVILE» è il tipo predefinito dei fascicoli: non basta a escludere un decreto della sezione lavoro o famiglia,
#: quindi per il rito civile decide il testo.


def da_dichiarata(valore: Any) -> str:
    """La materia dichiarata (dal fascicolo o dal catalogo) ricondotta al rito, o vuoto."""
    chiave = " ".join(str(getattr(valore, "value", valore) or "").lower().replace("_", " ").split())
    if chiave in _ALIAS:
        return _ALIAS[chiave]
    for nome, rito in _ALIAS.items():
        if nome in chiave:
            return rito
    return ""


def materia_del_provvedimento(testo: str, *, dichiarata: Any = "", ufficio: str = "", rg: str = "") -> str:
    """Il rito del provvedimento: dichiarato dal fascicolo, altrimenti letto da ufficio e testo."""
    rito = da_dichiarata(dichiarata)
    if rito:
        return rito
    pulito = normalizza(f"{ufficio}\n{testo}")
    for nome, espressione in _SEGNALI:
        if re.search(espressione, pulito, re.I):
            return nome
    if is_labour_matter(ufficio, rg) or re.search(r"\bgiudice\s+del\s+lavoro\b|\bsezione\s+lavoro\b|\brito\s+del\s+lavoro\b", pulito, re.I):
        return "lavoro"
    return "civile"


__all__ = ["MATERIE_RITO", "RITI_CPC", "da_dichiarata", "materia_del_provvedimento"]
