"""Immigrazione e protezione internazionale."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "decreto_espulsione",
        r"decreto\s+di\s+espulsione(?:\s+.*)?|provvedimento\s+di\s+espulsione(?:\s+.*)?",
        r"\bespuls\w+\b|\bprefett\w+\b|\bstranier\w+\b|\b286\b|\bquestor\w+\b",
        "Decreto di espulsione",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_tu_immigrazione_286_1998", deposit_role="allegato",
        evidence="titolo del decreto e allontanamento dello straniero (art. 13 D.Lgs. 286/1998)",
    ),
    regola(
        "decisione_commissione_territoriale",
        r"(?:provvedimento|decisione)\s+della\s+commissione\s+territoriale(?:\s+.*)?|commissione\s+territoriale(?:\s+.*)?",
        r"\bprotezione\s+internazionale\b|\brichiedent\w+\b|\basilo\b|\bcommissione\s+territoriale\b|\brifugiat\w+\b",
        "Decisione della Commissione territoriale",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_d_lgs_25_2008_protezione_internazionale", deposit_role="allegato",
        evidence="titolo della decisione e domanda di protezione (art. 32 D.Lgs. 25/2008)",
    ),
    regola(
        "ricorso_protezione_internazionale",
        r"ricorso(?:\s+.*)?",
        r"\bprotezione\s+internazionale\b|\bcommissione\s+territoriale\b|\bprotezione\s+(?:speciale|sussidiaria)\b",
        "Ricorso in materia di protezione internazionale",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_d_lgs_25_2008_protezione_internazionale", deposit_role="atto_principale",
        evidence="titolo del ricorso e domanda di protezione internazionale (art. 35 D.Lgs. 25/2008)",
    ),
)

__all__ = ["REGOLE"]
