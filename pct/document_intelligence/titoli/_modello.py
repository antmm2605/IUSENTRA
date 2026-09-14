"""Il modello di una regola d'identità dal titolo, condiviso da tutte le aree."""

from __future__ import annotations

from dataclasses import dataclass

from pct.fascicoli import TipoDocumento

CONFIDENZA_TITOLO = 96


@dataclass(frozen=True)
class RegolaTitolo:
    """Un tipo di atto: come si intitola, cosa lo conferma, come si cataloga.

    `titolo` è l'espressione della riga di titolo (dall'inizio riga, a meno
    della coda); `conferma` è il segnale che il corpo di quel tipo di atto
    contiene sempre: senza entrambi la regola non scatta. `fonte` è la norma
    che definisce l'atto, registrata fra le fonti del catalogo.
    """

    id: str
    titolo: str
    conferma: str
    label: str
    role: str
    section: str
    tipo: TipoDocumento
    deposit_role: str
    deposit_candidate: bool
    fonte: str
    evidence: str
    confidence: int = CONFIDENZA_TITOLO


def regola(
    id: str,
    titolo: str,
    conferma: str,
    label: str,
    *,
    role: str,
    section: str,
    tipo: TipoDocumento,
    fonte: str,
    evidence: str,
    deposit_role: str = "allegato",
    deposit_candidate: bool = True,
    confidence: int = CONFIDENZA_TITOLO,
) -> RegolaTitolo:
    return RegolaTitolo(
        id=id, titolo=titolo, conferma=conferma, label=label, role=role, section=section,
        tipo=tipo, deposit_role=deposit_role, deposit_candidate=deposit_candidate,
        fonte=fonte, evidence=evidence, confidence=confidence,
    )


__all__ = ["CONFIDENZA_TITOLO", "RegolaTitolo", "regola"]
