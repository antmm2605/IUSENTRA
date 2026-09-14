"""Crisi d'impresa, insolvenza e sovraindebitamento (D.Lgs. 14/2019)."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

REGOLE = (
    regola(
        "ricorso_liquidazione_giudiziale",
        r"ricorso\s+per\s+(?:l.?\s*apertura\s+della\s+)?liquidazione\s+giudiziale(?:\s+.*)?|ricorso\s+per\s+(?:la\s+)?dichiarazione\s+di\s+fallimento(?:\s+.*)?|istanza\s+di\s+fallimento(?:\s+.*)?",
        r"\binsolven\w+\b|\bdebitor\w+\b|\bcreditor\w+\b|\bliquidazione\s+giudiziale\b|\bfalliment\w+\b",
        "Ricorso per l'apertura della liquidazione giudiziale",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_codice_crisi_14_2019", deposit_role="atto_principale",
        evidence="titolo del ricorso e stato di insolvenza (artt. 37 e 40 CCII)",
    ),
    regola(
        "insinuazione_passivo",
        r"(?:domanda|istanza|ricorso)\s+di\s+(?:ammissione|insinuazione)\s+al\s+passivo(?:\s+.*)?|insinuazione\s+al\s+passivo(?:\s+.*)?",
        r"\bcurator\w+\b|\bpassivo\b|\bcredit\w+\b|\bprivileg\w+\b|\bchirograf\w+\b",
        "Domanda di ammissione al passivo",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_codice_crisi_14_2019", deposit_role="atto_principale",
        evidence="titolo della domanda e credito insinuato (art. 201 CCII)",
    ),
    regola(
        "stato_passivo",
        r"(?:progetto\s+di\s+)?stato\s+passivo(?:\s+.*)?|decreto\s+di\s+esecutivit[aà]\s+dello\s+stato\s+passivo(?:\s+.*)?",
        r"\bcurator\w+\b|\besecutiv\w+\b|\bcreditor\w+\b|\bammess\w+\b|\bescluss\w+\b",
        "Stato passivo",
        role="atto_ufficio", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_crisi_14_2019", deposit_role="fuori_busta", deposit_candidate=False,
        evidence="titolo del documento e verifica dei crediti (art. 204 CCII)",
    ),
    regola(
        "piano_sovraindebitamento",
        r"(?:piano|proposta)\s+(?:del\s+consumatore|di\s+ristrutturazione\s+dei\s+debiti)(?:\s+.*)?",
        r"\bsovraindebit\w+\b|\bdebit\w+\b|\bgestore\s+della\s+crisi\b|\bocc\b|\bconsumatore\b",
        "Piano di ristrutturazione dei debiti del consumatore",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_codice_crisi_14_2019", deposit_role="atto_principale",
        evidence="titolo del piano e sovraindebitamento (art. 67 CCII)",
    ),
    regola(
        "concordato_preventivo",
        r"(?:domanda|ricorso|proposta)\s+di\s+concordato\s+preventivo(?:\s+.*)?|piano\s+di\s+concordato(?:\s+.*)?",
        r"\bconcordat\w+\b|\bcreditor\w+\b|\bcommissario\b|\bpiano\b",
        "Domanda di concordato preventivo",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="normattiva_codice_crisi_14_2019", deposit_role="atto_principale",
        evidence="titolo della domanda e proposta ai creditori (art. 84 CCII)",
    ),
)

__all__ = ["REGOLE"]
