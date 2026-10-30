"""Atti del processo amministrativo e tributario oltre a ricorsi, motivi aggiunti e controdeduzioni.

Fonti: D.Lgs. 104/2010 (c.p.a.); D.Lgs. 546/1992 e Testo unico della giustizia
tributaria (D.Lgs. 175/2024); D.Lgs. 196/2003 per l'oscuramento dei dati.
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_TRIBUTI = r"\btribut\w+\b|\bcorte\s+di\s+giustizia\s+tributaria\b|\bagenzia\s+delle\s+entrate\b|\bente\s+impositore\b|\bcontribuent\w+\b"
_AMMINISTRATIVO = r"\bt\.a\.r\.|\btar\b|\btribunale\s+amministrativo\b|\bconsiglio\s+di\s+stato\b|\bamministrazion\w+\b|\bc\.p\.a\.|\b104/2010\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
          role: str = "istanza", tipo: TipoDocumento = TipoDocumento.MEMORIA):
    return regola(id, titolo, conferma, label, role=role, section="atti", tipo=tipo, fonte=fonte,
                  deposit_role="atto_principale", evidence=evidence)


REGOLE = (
    _atto(
        "istanza_prelievo",
        r"istanza\s+di\s+prelievo(?:\s+.*)?",
        _AMMINISTRATIVO + r"|\bprelievo\b|\burgenz\w+\b|\b71\b",
        "Istanza di prelievo",
        "titolo dell'istanza e urgenza della fissazione dell'udienza (art. 71, secondo comma, D.Lgs. 104/2010)",
        fonte="normattiva_cpa",
    ),
    _atto(
        "istanza_oscuramento_dati",
        r"istanza\s+di\s+(?:oscuramento|anonimizzazione)\s+(?:dei\s+)?dati(?:\s+(?:personali|identificativi))?(?:\s+.*)?|istanza\s+ex\s+art\.?\s*52(?:\s+d\.?\s*lgs\.?\s*196/2003)?(?:\s+.*)?",
        r"\boscurament\w+\b|\bdati\s+identificativ\w+\b|\bgeneralit\w+\b|\b52\b|\b196/2003\b",
        "Istanza di oscuramento dei dati personali",
        "titolo dell'istanza e oscuramento delle generalità nei provvedimenti (art. 52 D.Lgs. 196/2003)",
        fonte="normattiva_privacy_196_2003",
    ),
    _atto(
        "ricorso_incidentale_amministrativo",
        r"ricorso\s+incidentale(?:\s+.*)?",
        _AMMINISTRATIVO + r"|\bincidental\w+\b|\b42\b",
        "Ricorso incidentale",
        "titolo del ricorso e domanda della parte resistente o controinteressata (art. 42 D.Lgs. 104/2010)",
        fonte="normattiva_cpa", role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
    _atto(
        "istanza_sospensione_tributaria",
        r"istanza\s+di\s+sospensione(?:\s+(?:dell.?\s*)?(?:esecuzione|esecutivit[aà])\s+dell.?\s*atto(?:\s+impugnato)?)?(?:\s+(?:ex\s+art|ai\s+sensi).*)?",
        _TRIBUTI + r"|\b47\b|\bdanno\s+grave\s+e\s+irreparabile\b",
        "Istanza di sospensione dell'atto impugnato",
        "titolo dell'istanza e danno grave e irreparabile (art. 47 D.Lgs. 546/1992, ora D.Lgs. 175/2024)",
        fonte="normattiva_d_lgs_546_1992_tributario",
    ),
    _atto(
        "conciliazione_tributaria",
        r"(?:istanza|proposta)\s+di\s+conciliazione(?:\s+(?:giudiziale|tributaria|fuori\s+udienza))?(?:\s+.*)?",
        _TRIBUTI + r"|\bconcilia\w+\b|\b48\b",
        "Istanza di conciliazione tributaria",
        "titolo dell'istanza e conciliazione della controversia tributaria (artt. 48 e 48-bis D.Lgs. 546/1992, ora D.Lgs. 175/2024)",
        fonte="normattiva_d_lgs_546_1992_tributario",
    ),
    _atto(
        "pubblica_udienza_tributaria",
        r"istanza\s+di\s+(?:trattazione\s+in\s+)?pubblica\s+udienza(?:\s+.*)?|istanza\s+di\s+discussione\s+(?:in\s+)?pubblica\s+udienza(?:\s+.*)?",
        _TRIBUTI + r"|\bpubblica\s+udienza\b|\b33\b",
        "Istanza di trattazione in pubblica udienza",
        "titolo dell'istanza e discussione della controversia tributaria (art. 33 D.Lgs. 546/1992, ora D.Lgs. 175/2024)",
        fonte="normattiva_d_lgs_546_1992_tributario",
    ),
    _atto(
        "reclamo_mediazione_tributaria",
        r"reclamo(?:\s*[-/]\s*|\s+e\s+)mediazione(?:\s+tributaria)?(?:\s+.*)?|istanza\s+di\s+reclamo\s+(?:e\s+)?mediazione(?:\s+.*)?",
        _TRIBUTI + r"|\b17-?bis\b|\bmediazion\w+\b",
        "Reclamo-mediazione tributaria",
        "titolo dell'atto e reclamo con proposta di mediazione (art. 17-bis D.Lgs. 546/1992, abrogato dal D.Lgs. 220/2023 per gli atti notificati dal 4 gennaio 2024)",
        fonte="normattiva_d_lgs_220_2023_contenzioso_tributario", role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
)

__all__ = ["REGOLE"]
