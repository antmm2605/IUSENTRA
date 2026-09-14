"""Atti tributari e della riscossione."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_TRIBUTARIO = r"\bcorte\s+di\s+giustizia\s+tributaria\b|\bcommissione\s+tributaria\b|\bagenzia\s+delle\s+entrate\b|\bagenzia\s+delle\s+entrate[\s-]*riscossione\b|\btribut\w*\b|\bimposta\b"

REGOLE = (
    regola(
        "ricorso_tributario",
        r"ricorso(?:\s+.*)?",
        r"\bcorte\s+di\s+giustizia\s+tributaria\b|\bcommissione\s+tributaria\b",
        "Ricorso tributario",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_d_lgs_546_1992_controdeduzioni", deposit_role="atto_principale",
        evidence="titolo del ricorso e giudice tributario adito (art. 18 D.Lgs. 546/1992)",
    ),
    regola(
        "controdeduzioni_tributarie",
        r"(?:atto\s+di\s+)?controdeduzioni(?:\s+.*)?",
        _TRIBUTARIO,
        "Controdeduzioni",
        role="atto_difensivo", section="atti", tipo=TipoDocumento.MEMORIA,
        fonte="normattiva_d_lgs_546_1992_controdeduzioni", deposit_role="atto_principale",
        evidence="titolo dell'atto e costituzione della parte resistente (art. 23 D.Lgs. 546/1992)",
    ),
    regola(
        "avviso_accertamento",
        r"avviso\s+di\s+accertamento(?:\s+.*)?",
        r"\bimposta\b|\bimponibile\b|\baccert\w+\b|\bagenzia\s+delle\s+entrate\b|\bsanzion\w*\b",
        "Avviso di accertamento",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_600_1973_accertamento", deposit_role="allegato",
        evidence="titolo dell'avviso e rettifica dell'imponibile (art. 42 D.P.R. 600/1973)",
    ),
    regola(
        "avviso_liquidazione",
        r"avviso\s+di\s+liquidazione(?:\s+.*)?",
        r"\bimposta\b|\bliquida\w+\b|\bagenzia\s+delle\s+entrate\b|\bregistro\b|\bsuccession\w*\b",
        "Avviso di liquidazione",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_600_1973_accertamento", deposit_role="allegato",
        evidence="titolo dell'avviso e liquidazione dell'imposta",
    ),
    regola(
        "cartella_pagamento",
        r"cartella\s+(?:di\s+)?pagamento(?:\s+.*)?|cartella\s+esattoriale(?:\s+.*)?",
        r"\briscossione\b|\bruolo\b|\bagente\s+della\s+riscossione\b|\bimporto\b|\bente\s+creditore\b",
        "Cartella di pagamento",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_602_1973_riscossione", deposit_role="allegato",
        evidence="titolo della cartella e agente della riscossione (art. 25 D.P.R. 602/1973)",
    ),
    regola(
        "intimazione_pagamento_riscossione",
        r"intimazione\s+di\s+pagamento(?:\s+.*)?|avviso\s+di\s+intimazione(?:\s+.*)?",
        r"\briscossione\b|\bcartell\w+\b|\b50\b|\besecuzione\s+forzata\b",
        "Intimazione di pagamento",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_602_1973_riscossione", deposit_role="allegato",
        evidence="titolo dell'intimazione e avviso di esecuzione (art. 50 D.P.R. 602/1973)",
    ),
    regola(
        "preavviso_fermo",
        r"(?:preavviso|comunicazione\s+preventiva)\s+di\s+(?:fermo|iscrizione\s+di\s+fermo)(?:\s+amministrativo)?(?:\s+.*)?|preavviso\s+di\s+ipoteca(?:\s+.*)?",
        r"\bfermo\b|\bipoteca\b|\briscossione\b|\bveicol\w*\b|\b86\b",
        "Preavviso di fermo amministrativo",
        role="atto_amministrativo", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_dpr_602_1973_riscossione", deposit_role="allegato",
        evidence="titolo del preavviso e misura cautelare della riscossione (art. 86 D.P.R. 602/1973)",
    ),
    regola(
        "accertamento_adesione",
        r"istanza\s+di\s+accertamento\s+con\s+adesione(?:\s+.*)?|(?:atto|verbale)\s+di\s+(?:accertamento\s+con\s+)?adesione(?:\s+.*)?",
        r"\badesione\b|\bcontraddittorio\b|\bagenzia\s+delle\s+entrate\b|\bimposta\b",
        "Accertamento con adesione",
        role="atto_principale", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_d_lgs_218_1997_adesione", deposit_role="allegato",
        evidence="titolo dell'istanza e procedimento di adesione (art. 6 D.Lgs. 218/1997)",
    ),
)

__all__ = ["REGOLE"]
