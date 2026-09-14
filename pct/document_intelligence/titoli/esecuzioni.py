"""Atti dell'esecuzione forzata (c.p.c., libro III)."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "atto_precetto",
        r"(?:atto\s+di\s+)?precetto(?:\s+.*)?",
        r"\bintim\w+\b.{0,80}\bprecetto\b|\bfa\s+precetto\b|\btitolo\s+esecutivo\b|\bformula\s+esecutiva\b",
        "Atto di precetto",
        role="atto_esecutivo", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_cpc_esecuzione_forzata",
        evidence="titolo dell'atto e intimazione ad adempiere (art. 480 c.p.c.)",
    ),
    regola(
        "atto_pignoramento",
        r"(?:atto\s+di\s+)?pignoramento(?:\s+.*)?",
        r"\bpignora\b|\bterzo\s+pignorat\w*\b|\bsi\s+procede\b.{0,40}\bpignoramento\b|\bprecetto\b",
        "Atto di pignoramento",
        role="atto_esecutivo", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_cpc_esecuzione_forzata", deposit_role="atto_principale",
        evidence="titolo dell'atto e dichiarazione di pignoramento (artt. 492 e 543 c.p.c.)",
    ),
    regola(
        "opposizione_esecuzione",
        r"(?:atto\s+di\s+(?:citazione\s+in\s+)?)?opposizione\s+(?:all.?\s*esecuzione|agli\s+atti\s+esecutivi|ex\s+art\.?\s*61[57])(?:\s+.*)?",
        r"\bopponent\w*\b|\bpignoramento\b|\bprecetto\b|\b61[57]\b",
        "Opposizione esecutiva",
        role="atto_principale", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_cpc_opposizioni_esecutive", deposit_role="atto_principale",
        evidence="titolo dell'opposizione e riferimenti all'esecuzione (artt. 615 e 617 c.p.c.)",
    ),
    regola(
        "istanza_vendita",
        r"istanza\s+di\s+vendita(?:\s+.*)?",
        r"\bpignorat\w*\b|\bvendita\b|\bimmobil\w*\b|\b567\b",
        "Istanza di vendita",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_cpc_vendita_forzata", deposit_role="atto_principale",
        evidence="titolo dell'istanza e richiesta di vendita del bene pignorato (art. 567 c.p.c.)",
    ),
    regola(
        "avviso_vendita",
        r"avviso\s+di\s+vendita(?:\s+.*)?",
        r"\bofferte?\b|\bprezzo\s+base\b|\bvendita\b|\bdelegat\w*\b|\bprofessionista\b",
        "Avviso di vendita",
        role="atto_ufficio", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_cpc_vendita_forzata", deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo dell'avviso e condizioni della vendita forzata (art. 490 c.p.c.)",
    ),
    regola(
        "decreto_trasferimento",
        r"decreto\s+di\s+trasferimento(?:\s+.*)?",
        r"\btrasferisce\b|\baggiudicatari\w*\b|\bimmobil\w*\b",
        "Decreto di trasferimento",
        role="provvedimento", section="provvedimenti", tipo=TipoDocumento.DECRETO,
        fonte="normattiva_cpc_vendita_forzata", deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo del decreto e trasferimento del bene all'aggiudicatario (art. 586 c.p.c.)",
    ),
    regola(
        "piano_riparto",
        r"(?:piano|progetto)\s+di\s+(?:riparto|distribuzione)(?:\s+.*)?",
        r"\bcreditor\w*\b|\bsomm\w+\b|\bripart\w+\b|\bdistribu\w+\b",
        "Piano di riparto",
        role="atto_ufficio", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_cpc_vendita_forzata", deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo del piano e distribuzione del ricavato ai creditori (art. 596 c.p.c.)",
    ),
    regola(
        "atto_intervento",
        r"(?:atto\s+di\s+|ricorso\s+per\s+)?intervento(?:\s+(?:nell.?\s*esecuzione|ex\s+art\.?\s*499).*)?",
        r"\binterven\w+\b|\bcreditor\w*\b|\b499\b|\bpignoramento\b",
        "Atto di intervento nell'esecuzione",
        role="atto_principale", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_cpc_intervento_esecuzione", deposit_role="atto_principale",
        evidence="titolo dell'atto e intervento del creditore (art. 499 c.p.c.)",
    ),
)

__all__ = ["REGOLE"]
