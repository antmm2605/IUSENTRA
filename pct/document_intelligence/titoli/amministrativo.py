"""Atti del processo amministrativo e provvedimenti della pubblica amministrazione."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_AMMINISTRATIVO = r"\btribunale\s+amministrativo\b|\bt\.?\s*a\.?\s*r\.?\b|\bconsiglio\s+di\s+stato\b|\bamministrazione\s+resistente\b|\bprovvedimento\s+impugnato\b|\bc\.?\s*p\.?\s*a\.?\b"

REGOLE = (
    regola(
        "ricorso_tar",
        r"ricorso(?:\s+.*)?",
        r"\btribunale\s+amministrativo\s+regionale\b|\bt\.a\.r\.\b|\btar\s+(?:per\s+)?(?:il\s+|la\s+)?[a-z]+\b",
        "Ricorso al TAR",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_cpa_ricorso", deposit_role="atto_principale",
        evidence="titolo del ricorso e tribunale amministrativo adito (art. 40 c.p.a.)",
    ),
    regola(
        "motivi_aggiunti",
        r"(?:ricorso\s+per\s+)?motivi\s+aggiunti(?:\s+.*)?",
        _AMMINISTRATIVO + r"|\bricorso\s+principale\b",
        "Motivi aggiunti",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_cpa_ricorso", deposit_role="atto_principale",
        evidence="titolo dell'atto e impugnazione di ulteriori provvedimenti (art. 43 c.p.a.)",
    ),
    regola(
        "istanza_cautelare_amministrativa",
        r"(?:istanza|domanda)\s+(?:cautelare|di\s+sospensione(?:\s+dell.?\s*efficacia)?)(?:\s+.*)?",
        _AMMINISTRATIVO + r"|\bpericulum\b|\bfumus\b",
        "Domanda cautelare",
        role="atto_principale", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_cpa_ricorso", deposit_role="atto_principale",
        evidence="titolo dell'istanza e richiesta di misura cautelare (art. 55 c.p.a.)",
    ),
    regola(
        "appello_consiglio_stato",
        r"(?:ricorso\s+in\s+|atto\s+di\s+)?appello(?:\s+.*)?",
        r"\bconsiglio\s+di\s+stato\b|\bsentenza\s+del\s+t\.?\s*a\.?\s*r\.?\b",
        "Appello al Consiglio di Stato",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_cpa_ricorso", deposit_role="atto_principale",
        evidence="titolo dell'appello e giudice di secondo grado (art. 100 c.p.a.)",
    ),
    regola(
        "ricorso_straordinario",
        r"ricorso\s+straordinario(?:\s+al\s+presidente\s+della\s+repubblica)?(?:\s+.*)?",
        r"\bpresidente\s+della\s+repubblica\b|\bstraordinari\w*\b|\b1199\b",
        "Ricorso straordinario al Presidente della Repubblica",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_dpr_1199_1971_ricorso_straordinario", deposit_role="atto_principale",
        evidence="titolo del ricorso e rimedio straordinario (art. 8 D.P.R. 1199/1971)",
    ),
    regola(
        "istanza_accesso_atti",
        r"(?:istanza|richiesta|domanda)\s+di\s+accesso(?:\s+(?:agli\s+atti|ai\s+documenti|civico|documentale))?(?:\s+.*)?",
        r"\baccesso\b|\bdocument\w+\s+amministrativ\w+\b|\b241\b|\b33/2013\b|\bpubblica\s+amministrazione\b",
        "Istanza di accesso agli atti",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="normattiva_legge_241_1990_procedimento", deposit_role="allegato",
        evidence="titolo dell'istanza e diritto di accesso (art. 22 L. 241/1990; art. 5 D.Lgs. 33/2013)",
    ),
    regola(
        "preavviso_rigetto",
        r"(?:preavviso|comunicazione)\s+(?:di\s+)?(?:rigetto|diniego)(?:\s+.*)?|comunicazione\s+dei\s+motivi\s+ostativi(?:\s+.*)?",
        r"\b10[\s.-]*bis\b|\bmotivi\s+ostativi\b|\bosservazion\w*\b|\brigett\w+\b",
        "Preavviso di rigetto",
        role="atto_amministrativo", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="normattiva_legge_241_1990_procedimento", deposit_role="allegato",
        evidence="titolo della comunicazione e motivi ostativi (art. 10-bis L. 241/1990)",
    ),
    regola(
        "provvedimento_amministrativo",
        r"(?:determinazione|determina)(?:\s+dirigenziale)?(?:\s+.*)?|deliberazione(?:\s+.*)?|delibera(?:\s+.*)?|ordinanza\s+(?:sindacale|del\s+sindaco|dirigenziale)(?:\s+.*)?|permesso\s+di\s+costruire(?:\s+.*)?|provvedimento\s+di\s+diniego(?:\s+.*)?|decreto\s+(?:del\s+sindaco|dirigenziale|del\s+prefetto|prefettizio)(?:\s+.*)?",
        r"\bcomune\s+di\b|\bregione\b|\bprovincia\b|\bdirigente\b|\bresponsabile\s+del\s+(?:procedimento|servizio)\b|\bsindaco\b|\bprefett\w*\b|\bgiunta\b|\bconsiglio\s+comunale\b",
        "Provvedimento amministrativo",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_legge_241_1990_procedimento", deposit_role="allegato",
        evidence="titolo del provvedimento e amministrazione emanante (art. 3 L. 241/1990)",
    ),
    regola(
        "verbale_accertamento_cds",
        r"verbale\s+di\s+(?:accertamento|contestazione)(?:\s+.*)?|verbale\s+n\.?\s*\d+(?:\s+.*)?",
        r"\bcodice\s+della\s+strada\b|\bart\.?\s*20[01]\b|\bsanzione\s+amministrativa\b|\btarga\b|\bveicol\w*\b|\bpolizia\s+(?:locale|municipale|stradale)\b",
        "Verbale di accertamento di violazione",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.VERBALE,
        fonte="normattiva_codice_strada_285_1992", deposit_role="allegato",
        evidence="titolo del verbale e sanzione amministrativa (artt. 200 e 201 C.d.S.)",
    ),
    regola(
        "ordinanza_ingiunzione",
        r"ordinanza[\s-]*ingiunzione(?:\s+.*)?",
        r"\b689\b|\bsanzione\s+amministrativa\b|\bingiunge\b|\bprefett\w*\b",
        "Ordinanza-ingiunzione",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ORDINANZA,
        fonte="normattiva_legge_689_1981_sanzioni", deposit_role="allegato",
        evidence="titolo dell'ordinanza e sanzione amministrativa (art. 18 L. 689/1981)",
    ),
    regola(
        "opposizione_ordinanza_ingiunzione",
        r"(?:ricorso\s+in\s+|atto\s+di\s+)?opposizione\s+(?:a|ad|avverso)\s+(?:ordinanza[\s-]*ingiunzione|verbale|sanzione\s+amministrativa)(?:\s+.*)?",
        r"\b689\b|\bsanzione\s+amministrativa\b|\bordinanza[\s-]*ingiunzione\b|\bverbale\b|\bgiudice\s+di\s+pace\b",
        "Opposizione a sanzione amministrativa",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_d_lgs_150_2011_art_6_opposizione", deposit_role="atto_principale",
        evidence="titolo dell'opposizione e sanzione impugnata (art. 6 D.Lgs. 150/2011)",
    ),
)

__all__ = ["REGOLE"]
