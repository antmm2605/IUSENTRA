"""Procure, domicilio e vicende del mandato difensivo (c.p.c., artt. 83-85; c.p.p., artt. 96-107)."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "procura_alle_liti",
        r"procura\s+(?:generale\s+|speciale\s+)?alle\s+liti(?:\s+.*)?|procura\s+speciale\s+per\s+(?:(?:il\s+)?(?:giudizio\s+di\s+)?appello|(?:il\s+)?ricorso(?!.*mediazione).*|(?:la\s+)?fase\s+.*|il\s+giudizio.*)|"
        r"procura\s+(?:per\s+(?:la\s+)?fase\s+esecutiva|ad\s+litem)(?:\s+.*)?|procura\s*/\s*mandato\s+difensivo(?:\s+.*)?|mandato\s+(?:difensivo|alle\s+liti)(?:\s+.*)?",
        r"\bdifensor\w+\b|\bprocurator\w+\b|\bnomin\w+\b|\bconferisc\w+\b|\bmandat\w+\b|\b83\b",
        "Procura alle liti",
        role="procura", section="procure", tipo=TipoDocumento.PROCURA, deposit_role="procura",
        fonte="normattiva_cpc", evidence="titolo della procura e conferimento del mandato al difensore (art. 83 c.p.c.)",
    ),
    regola(
        "elezione_domicilio",
        r"(?:atto\s+di\s+|dichiarazione\s+di\s+)?elezione\s+di\s+domicilio(?:\s+.*)?|nomina\s+(?:del\s+)?(?:domiciliatario|sostituto\s+processuale|corrispondente)(?:\s+.*)?|delega\s+(?:di\s+)?sostituzione(?:\s+in\s+udienza)?(?:\s+.*)?",
        r"\bdomicili\w+\b|\bsostitu\w+\b|\bdelega\w*\b|\bavvocat\w+\b|\bdifensor\w+\b",
        "Elezione di domicilio o nomina del domiciliatario",
        role="procura", section="procure", tipo=TipoDocumento.PROCURA, deposit_role="allegato",
        fonte="normattiva_cpc", evidence="titolo dell'atto e domicilio o sostituto del difensore (artt. 84 e 170 c.p.c.; art. 9 L. 247/2012)",
    ),
    regola(
        "revoca_rinuncia_mandato",
        r"(?:atto\s+di\s+|lettera\s+di\s+|dichiarazione\s+di\s+)?(?:revoca|rinuncia)\s+(?:del(?:l.?\s*)?\s*|al(?:l.?\s*)?\s*)(?:mandato|incarico|procura)(?:\s+difensivo)?(?:\s+.*)?|revoca\s+o\s+rinuncia\s+al\s+mandato(?:\s+.*)?",
        r"\bmandat\w+\b|\bincaric\w+\b|\bprocur\w+\b|\brevoc\w+\b|\brinunci\w+\b|\b85\b|\b107\b",
        "Revoca o rinuncia al mandato",
        role="procura", section="procure", tipo=TipoDocumento.PROCURA, deposit_role="allegato",
        fonte="normattiva_cpc", evidence="titolo dell'atto e cessazione del mandato difensivo (art. 85 c.p.c.; art. 107 c.p.p.; art. 32 Codice deontologico forense)",
    ),
)

__all__ = ["REGOLE"]
