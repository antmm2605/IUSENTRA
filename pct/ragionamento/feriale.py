"""Sospensione feriale dei termini: quando non si applica, per materia (art. 3 L. 742/1969; art. 92 R.D. 12/1941).

Testo vigente letto su Normattiva il 19/11/2026:
- art. 3 L. 7 ottobre 1969, n. 742 (in vigore dal 06/11/1969): «In materia civile, l'articolo 1 non si applica alle
  cause ed ai procedimenti indicati nell'articolo 92 dell'ordinamento giudiziario 30 gennaio 1941, n. 12, nonché alle
  controversie previste dagli articoli 429 e 459 del codice di procedura civile» (oggi lavoro, art. 409, e previdenza
  e assistenza obbligatorie, art. 442 c.p.c.);
- art. 92 R.D. 30 gennaio 1941, n. 12 (in vigore dal 19/03/2004): cause relative ad alimenti, procedimenti cautelari,
  procedimenti per l'amministrazione di sostegno, l'interdizione e l'inabilitazione, ordini di protezione contro gli
  abusi familiari, sfratto, opposizione all'esecuzione, dichiarazione e revoca dei fallimenti e, in genere, le cause
  dichiarate urgenti dal presidente o dal giudice.

La materia si legge dal codice oggetto ministeriale PST (descrizione, voce padre, area) e, se manca, dagli atti
catalogati. L'opposizione agli atti esecutivi (art. 617 c.p.c.) e le azioni del fallimento diverse dalla sua
dichiarazione o revoca non sono escluse. La dichiarazione d'urgenza è un provvedimento del giudice: non si deduce.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .testo import semplice

_L742 = "art. 3 L. 742/1969"
_OG92 = "art. 3 L. 742/1969 e art. 92 R.D. 12/1941"
# (espressione sul testo semplificato di descrizione, voce padre e area, motivo, norma)
_MATERIE: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bopposizione all'?\s*esecuzione\b"), "opposizione all'esecuzione", _OG92),
    (re.compile(r"\bcautelar|\bart\.?\s*700\b|\bsequestro\b|\bistruzione preventiva\b|\bdenuncia di nuova opera\b"),
     "procedimento cautelare", _OG92),
    (re.compile(r"\baliment"), "causa relativa ad alimenti", _OG92),
    (re.compile(r"\bamministrazione di sostegno\b|\binterdizion|\binabilitazion"),
     "amministrazione di sostegno, interdizione o inabilitazione", _OG92),
    (re.compile(r"\babusi familiari\b|\bordini? di protezione\b"), "ordini di protezione contro gli abusi familiari", _OG92),
    (re.compile(r"\bsfratto\b"), "procedimento di sfratto", _OG92),
    (re.compile(r"\b(?:dichiarazione|dichiarativa) di fallimento\b|\brevoca del fallimento\b|"
                r"\bapertura della liquidazione giudiziale\b"), "dichiarazione o revoca del fallimento", _OG92),
)
# Senza codice oggetto decidono solo gli atti che introducono il procedimento escluso: un documento di prova («contratto
# di lavoro», «verbale di sequestro») o un incidente cautelare in corso di causa non cambiano la materia del fascicolo.
_ATTI_INTRODUTTIVI: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bopposizione all'?\s*esecuzione\b|\bart\.?\s*615\b"), "opposizione all'esecuzione"),
    (re.compile(r"\bricorso (?:cautelare|ex art\.?\s*700)\b"), "procedimento cautelare"),
    (re.compile(r"\b(?:intimazione|convalida) di (?:licenza o di )?sfratto\b"), "procedimento di sfratto"),
)


def esclusione_feriale(rito: str, voce: dict[str, Any], etichette_atti: Iterable[str] = ()) -> str:
    """Il motivo per cui la sospensione feriale non si applica, con la norma; stringa vuota se si applica."""
    codice = " | ".join(semplice(voce.get(k)) for k in ("descrizione", "descrizionePadre", "area") if voce.get(k))
    if rito == "lavoro" or semplice(voce.get("area")).startswith("lavoro"):
        return f"controversia di lavoro o di previdenza e assistenza obbligatorie ({_L742})"
    if codice:
        if "opposizione agli atti esecutivi" in codice:
            return ""
        return next((f"{motivo} ({norma})" for espressione, motivo, norma in _MATERIE if espressione.search(codice)), "")
    for etichetta in map(semplice, etichette_atti):
        if "opposizione agli atti esecutivi" in etichetta:
            continue
        for espressione, motivo in _ATTI_INTRODUTTIVI:
            if espressione.search(etichetta):
                return f"{motivo} ({_OG92})"
    return ""


__all__ = ["esclusione_feriale"]
