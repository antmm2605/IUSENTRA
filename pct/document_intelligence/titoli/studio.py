"""Atti dello studio: incarico, compensi, obblighi antiriciclaggio e privacy."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "preventivo_professionale",
        r"preventivo(?:\s+(?:di\s+massima|di\s+spesa\s+professionale|del\s+compenso|n\.?\s*\d+))?(?:\s+.*)?",
        r"\bcompens\w+\b|\bonorar\w+\b|\bparametr\w+\b|\bd\.?\s*m\.?\s*55\b|\bspese\s+generali\b|\bstudio\s+legale\b|\bcassa\s+(?:forense|avvocati)\b",
        "Preventivo del compenso professionale",
        role="documento_economico", section="pagamenti", tipo=TipoDocumento.PARCELLA,
        fonte="normattiva_l_247_2012_ordinamento_forense", deposit_candidate=False,
        evidence="titolo del preventivo e compenso professionale (art. 13 L. 247/2012)",
    ),
    regola(
        "conferimento_incarico",
        r"(?:conferimento|lettera)\s+(?:di\s+|dell.?\s*)?incarico(?:\s+.*)?|mandato\s+professionale(?:\s+.*)?|contratto\s+d.?\s*opera\s+professionale(?:\s+.*)?|accordo\s+sul\s+compenso(?:\s+.*)?",
        r"\bincaric\w+\b|\bcompens\w+\b|\bavvocat\w+\b|\bcliente\b|\bmandat\w+\b",
        "Conferimento di incarico professionale",
        role="incarico", section="procure", tipo=TipoDocumento.CONTRATTO,
        fonte="normattiva_l_247_2012_ordinamento_forense", deposit_candidate=False,
        evidence="titolo dell'atto e accordo sul compenso (art. 13 L. 247/2012)",
    ),
    regola(
        "adeguata_verifica",
        r"(?:scheda|modulo|questionario)\s+(?:di\s+)?adeguata\s+verifica(?:\s+.*)?|adeguata\s+verifica(?:\s+della\s+clientela)?(?:\s+.*)?|(?:scheda|questionario)\s+antiriciclaggio(?:\s+.*)?",
        r"\bantiriciclag\w+\b|\b231\b|\btitolare\s+effettivo\b|\bcliente\b|\bpersona\s+politicamente\s+esposta\b",
        "Adeguata verifica antiriciclaggio",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_d_lgs_231_2007_adeguata_verifica", deposit_candidate=False,
        evidence="titolo della scheda e obblighi di adeguata verifica (art. 18 D.Lgs. 231/2007)",
    ),
    regola(
        "informativa_privacy",
        r"informativa\s+(?:sul\s+trattamento\s+dei\s+dati(?:\s+personali)?|privacy|ai\s+sensi\s+dell.?\s*art\.?\s*13|ex\s+art\.?\s*13)(?:\s+.*)?",
        r"\btrattamento\b|\bdati\s+personali\b|\btitolare\s+del\s+trattamento\b|\bgdpr\b|\b679\b",
        "Informativa sul trattamento dei dati",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="eurlex_gdpr", deposit_candidate=False,
        evidence="titolo dell'informativa e contenuti obbligatori (art. 13 Reg. UE 2016/679)",
    ),
    regola(
        "consenso_privacy",
        r"consenso\s+(?:al\s+trattamento(?:\s+dei\s+dati)?|privacy|informato)(?:\s+.*)?",
        r"\bacconsent\w+\b|\bdati\b|\btrattamento\b|\bprivacy\b",
        "Consenso al trattamento dei dati",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="eurlex_gdpr", deposit_candidate=False,
        evidence="titolo del modulo e consenso dell'interessato (art. 7 Reg. UE 2016/679)",
    ),
    regola(
        "reclamo_garante",
        r"reclamo\s+(?:al\s+garante|ex\s+art\.?\s*77)(?:\s+.*)?",
        r"\bgarante\b|\bdati\s+personali\b|\btrattamento\b",
        "Reclamo al Garante per la protezione dei dati",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="garante_gdpr", deposit_role="atto_principale",
        evidence="titolo del reclamo e autorità adita (art. 77 Reg. UE 2016/679)",
    ),
    regola(
        "nota_spese",
        r"nota\s+(?:di\s+)?spese(?:\s+e\s+competenze)?(?:\s+.*)?|nota\s+(?:di\s+)?spese\s+e\s+onorari(?:\s+.*)?",
        r"\bspese\b|\bcompet\w+\b|\bonorar\w+\b|\btotale\b|\bfase\b",
        "Nota spese e competenze",
        role="documento_economico", section="pagamenti", tipo=TipoDocumento.PARCELLA,
        fonte="normattiva_dm_55_2014_parametri_forensi", deposit_role="allegato",
        evidence="titolo della nota e voci di compenso (D.M. 55/2014)",
    ),
)

__all__ = ["REGOLE"]
