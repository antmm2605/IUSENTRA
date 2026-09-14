"""Locazioni, condominio e immobili."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "contratto_locazione",
        r"contratto\s+di\s+locazione(?:\s+.*)?|contratto\s+di\s+affitto(?:\s+.*)?|contratto\s+di\s+comodato(?:\s+.*)?",
        r"\blocator\w+\b|\bconduttor\w+\b|\bcanone\b|\bcomodant\w+\b|\bcomodatari\w+\b|\bimmobil\w+\b",
        "Contratto di locazione",
        role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
        fonte="normattiva_cc_locazione",
        evidence="titolo del contratto e parti della locazione (art. 1571 c.c.; L. 431/1998)",
    ),
    regola(
        "intimazione_sfratto",
        r"(?:atto\s+di\s+)?intimazione\s+di\s+(?:sfratto|licenza)(?:\s+.*)?|sfratto\s+per\s+(?:morosit[aà]|finita\s+locazione)(?:\s+.*)?",
        r"\bsfratt\w+\b|\bmorosit\w+\b|\bcanon\w+\b|\blicenza\b|\brilascio\b|\bconvalida\b",
        "Intimazione di sfratto",
        role="atto_principale", section="atti", tipo=TipoDocumento.CITAZIONE,
        fonte="normattiva_cpc_sfratto", deposit_role="atto_principale",
        evidence="titolo dell'intimazione e citazione per la convalida (artt. 657 e 658 c.p.c.)",
    ),
    regola(
        "disdetta_locazione",
        r"disdetta(?:\s+.*)?|comunicazione\s+di\s+recesso(?:\s+.*)?|recesso\s+dal\s+contratto(?:\s+.*)?",
        r"\blocazion\w+\b|\bcontratto\b|\bpreavviso\b|\bimmobil\w+\b|\bcanone\b",
        "Disdetta o recesso dal contratto di locazione",
        role="corrispondenza", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_cc_locazione", deposit_role="allegato",
        evidence="titolo della comunicazione e cessazione della locazione (art. 1596 c.c.; art. 3 L. 431/1998)",
    ),
    regola(
        "verbale_assemblea_condominio",
        r"verbale\s+(?:dell.?\s*|di\s+)?assemblea(?:\s+(?:condominiale|di\s+condominio|ordinaria|straordinaria))?(?:\s+.*)?",
        r"\bcondomin\w+\b|\bordine\s+del\s+giorno\b|\bdelibera\w*\b|\bmillesim\w+\b|\bamministratore\b",
        "Verbale di assemblea condominiale",
        role="verbale_condominio", section="allegati", tipo=TipoDocumento.VERBALE,
        fonte="normattiva_cc_condominio",
        evidence="titolo del verbale e deliberazioni dell'assemblea (art. 1136 c.c.)",
    ),
    regola(
        "regolamento_condominio",
        r"regolamento\s+(?:di\s+)?condomini(?:o|ale)(?:\s+.*)?",
        r"\bcondomin\w+\b|\bparti\s+comuni\b|\bmillesim\w+\b",
        "Regolamento di condominio",
        role="regolamento", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_cc_condominio",
        evidence="titolo del regolamento e disciplina delle parti comuni (art. 1138 c.c.)",
    ),
    regola(
        "impugnazione_delibera",
        r"(?:atto\s+di\s+citazione\s+per\s+(?:l.?\s*)?)?impugnazione\s+(?:di|della)\s+delibera(?:zione)?(?:\s+.*)?",
        r"\bassemblea\b|\bcondomin\w+\b|\b1137\b|\bannull\w+\b",
        "Impugnazione di delibera assembleare",
        role="atto_principale", section="atti", tipo=TipoDocumento.CITAZIONE,
        fonte="normattiva_cc_condominio", deposit_role="atto_principale",
        evidence="titolo dell'atto e impugnazione della deliberazione (art. 1137 c.c.)",
    ),
    regola(
        "riparto_spese_condominio",
        r"(?:riparto|ripartizione)\s+(?:delle\s+)?spese(?:\s+.*)?|rendiconto\s+condominiale(?:\s+.*)?|bilancio\s+(?:consuntivo|preventivo)(?:\s+.*)?",
        r"\bcondomin\w+\b|\bmillesim\w+\b|\bquot\w+\b|\bspese\b",
        "Riparto delle spese condominiali",
        role="documento_economico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_cc_condominio",
        evidence="titolo del riparto e quote millesimali",
    ),
    regola(
        "verbale_consegna_immobile",
        r"verbale\s+di\s+(?:consegna|riconsegna|rilascio)(?:\s+.*)?",
        r"\bimmobil\w+\b|\bchiavi\b|\blocal\w+\b|\bstato\s+dei\s+luoghi\b|\bunit[aà]\b",
        "Verbale di consegna dell'immobile",
        role="verbale", section="allegati", tipo=TipoDocumento.VERBALE,
        fonte="normattiva_cc_locazione",
        evidence="titolo del verbale e consegna dell'immobile",
    ),
    regola(
        "attestato_prestazione_energetica",
        r"attestato\s+di\s+prestazione\s+energetica(?:\s+.*)?|ape(?:\s+.*)?",
        r"\bclasse\s+energetica\b|\bkwh\b|\bprestazione\s+energetica\b",
        "Attestato di prestazione energetica",
        role="certificato", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_legge_431_1998_locazioni_abitative",
        evidence="titolo dell'attestato e classe energetica dell'immobile",
    ),
)

__all__ = ["REGOLE"]
