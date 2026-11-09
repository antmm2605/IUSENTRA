"""Regole della materia per collegare la guida pratica ai fascicoli con oggetto breve o assente.

Il suggeritore per parole richiede almeno due parole significative: «retribuzione», «ottemperanza» o «precetto»
da sole non bastano, e nei titoli i nomi delle parti diluiscono il confronto. Queste regole riconoscono le parole
processuali che individuano da sole il rito, con la controparte quando decide la giurisdizione:
- retribuzione nel lavoro: pubblico impiego contrattualizzato se la controparte è una pubblica amministrazione
  (art. 63 D.Lgs. 165/2001), lavoro privato altrimenti;
- ottemperanza: artt. 112-114 c.p.a. (tributaria: art. 70 D.Lgs. 546/1992);
- silenzio sul riconoscimento di un titolo estero: art. 16 D.Lgs. 206/2007 e artt. 31, 117 c.p.a.;
- precetto: artt. 479-481 c.p.c. (non l'opposizione, che ha la sua scheda);
- ricorso contro un decreto ministeriale davanti al TAR: artt. 29 e 41 c.p.a.
Si applicano solo quando il suggeritore ordinario non trova nulla: non cambiano i collegamenti esistenti.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_PA = re.compile(
    r"\b(mim|miur|ministero|ministro|istruzione|ufficio scolastico|usr|avvocatura|inps|inail|comune|regione|provincia|"
    r"azienda sanitaria|asl|asp|agenzia delle entrate|universita|prefettura|questura)\b"
)

# (parole tutte presenti, parole da escludere, tipi di fascicolo ammessi o None, controparte PA: True/False/None, codice)
REGOLE: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...] | None, bool | None, str], ...] = (
    (("ottemperanza",), (), ("TRIBUTARIO",), None, "GUIDA_TRIBUTARIO_OTTEMPERANZA"),
    (("ottemperanza",), (), None, None, "GUIDA_AMMINISTRATIVO_OTTEMPERANZA"),
    (("silenzio", "titolo estero"), (), None, None, "GUIDA_AMMINISTRATIVO_SILENZIO_RICONOSCIMENTO_TITOLO_ESTERO"),
    (("silenzio", "riconoscimento", "titolo"), (), None, None, "GUIDA_AMMINISTRATIVO_SILENZIO_RICONOSCIMENTO_TITOLO_ESTERO"),
    (("silenzio",), (), ("AMMINISTRATIVO",), None, "GUIDA_AMMINISTRATIVO_SILENZIO"),
    (("precetto",), ("opposizione",), None, None, "GUIDA_PRECETTO_ANCHE_CONTRO_PA"),
    (("ricorso avverso decreto",), (), ("AMMINISTRATIVO",), None, "GUIDA_AMMINISTRATIVO_RICORSO_TAR"),
    (("retribuzione",), (), ("LAVORO",), True, "222050"),
    (("retribuzione",), (), ("LAVORO",), False, "220050"),
)


def _piega(valore: Any) -> str:
    testo = unicodedata.normalize("NFKD", str(valore or "")).encode("ascii", "ignore").decode("ascii").lower()
    return " " + re.sub(r"[^a-z0-9]+", " ", testo).strip() + " "


def controparte_pubblica(fascicolo: dict[str, Any]) -> bool:
    testo = _piega(" ".join(str(fascicolo.get(k) or "") for k in ("controparte", "titolo", "title", "oggetto")))
    return bool(_PA.search(testo))


def regola_della_materia(fascicolo: dict[str, Any], codici_disponibili: Any) -> tuple[str, str] | None:
    """(codice, parole riconosciute) della prima regola che si applica e la cui scheda esiste, altrimenti None."""
    testo = _piega(" ".join(str(fascicolo.get(k) or "") for k in ("oggetto", "object", "titolo", "title")))
    tipo = str(fascicolo.get("tipo") or "").upper()
    pubblica = controparte_pubblica(fascicolo)
    for parole, escluse, tipi, pa, codice in REGOLE:
        if not all(f" {p} " in testo for p in parole) or any(f" {e} " in testo for e in escluse):
            continue
        if tipi is not None and tipo not in tipi:
            continue
        if pa is not None and pa != pubblica:
            continue
        if codice in codici_disponibili:
            return codice, " + ".join(parole)
    return None
