"""Un solo registro delle norme: il catalogo dell'harness (testo vigente letto da Normattiva) e il registro della
conoscenza procedurale (``pct/procedura_fasi/fonti.FONTI``) devono indicare lo stesso atto e lo stesso articolo, e gli
estratti del registro procedurale devono stare nel testo vigente. Il testo di riferimento è uno solo: l'istantanea
dell'harness (``lex/harness/dati/norme_vigenti.json``), rigenerata da ``scripts/lex_harness_norme.py``."""
from __future__ import annotations

import re
from typing import Any

from .norme import NORME, normalizza, testo_norma

_URN = re.compile(r"N2Ls\?(urn:[^~]+)~art(\w+)")


def _chiave_url(url: str) -> tuple[str, str] | None:
    m = _URN.search(url or "")
    return (m.group(1).lower(), m.group(2).lower()) if m else None


def corrispondenze() -> dict[str, str]:
    """Identificativo del registro procedurale → chiave dell'harness, per gli articoli in comune."""
    from pct.procedura_fasi.fonti import FONTI

    harness = {}
    for chiave in NORME:
        t = testo_norma(chiave)
        if t and _chiave_url(t.url):
            harness[_chiave_url(t.url)] = chiave
    return {i: harness[k] for i, v in FONTI.items() if (k := _chiave_url(v.get("url", ""))) in harness}


def estratti_non_letterali() -> list[dict[str, Any]]:
    """Voci del registro procedurale il cui estratto (spezzato su «…» e «;») non si ritrova nel testo vigente."""
    from pct.procedura_fasi.fonti import FONTI

    uscita = []
    for ident, chiave in corrispondenze().items():
        testo = normalizza(testo_norma(chiave).testo)
        pezzi = [p.strip(" «»\".") for p in re.split(r"\s*(?:\.\.\.|…|;)\s*", FONTI[ident].get("estratto") or "") if len(p) > 25]
        assenti = [p for p in pezzi if normalizza(p) not in testo]
        if assenti:
            uscita.append({"id": ident, "norma": chiave, "assenti": assenti})
    return uscita
