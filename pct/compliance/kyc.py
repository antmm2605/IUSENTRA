"""Antiriciclaggio / adeguata verifica della clientela (KYC).

Base normativa: D.Lgs. 231/2007 (adeguata verifica, titolare effettivo,
approccio basato sul rischio) e Regole Tecniche CNF in materia antiriciclaggio.
Qui calcoliamo un livello di rischio dai fattori dichiarati e controlliamo la
validità del documento identificativo. Non sostituisce la valutazione
dell'avvocato: la supporta e la rende tracciabile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    BASSO = "basso"
    MEDIO = "medio"
    ALTO = "alto"


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def _parse_date(value: str | date | None) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class IdentityDocument:
    tipo: str = ""          # carta_identita | passaporto | patente
    numero: str = ""
    scadenza: str = ""      # ISO o gg/mm/aaaa


@dataclass
class KycFactors:
    persona_giuridica: bool = False
    titolare_effettivo_identificato: bool = True
    pep: bool = False                       # persona politicamente esposta
    paese_alto_rischio: bool = False
    uso_contante_elevato: bool = False
    settore_alto_rischio: bool = False
    rapporto_a_distanza: bool = False       # cliente non incontrato di persona


def assess_risk(factors: KycFactors) -> tuple[RiskLevel, int, list[str]]:
    """Punteggio rischio con motivazioni. Pesi conservativi e spiegabili."""

    score = 0
    reasons: list[str] = []

    def add(points: int, reason: str) -> None:
        nonlocal score
        score += points
        reasons.append(reason)

    if factors.pep:
        add(3, "Persona politicamente esposta (PEP).")
    if factors.paese_alto_rischio:
        add(2, "Paese a rischio elevato.")
    if factors.uso_contante_elevato:
        add(2, "Uso di contante elevato.")
    if factors.persona_giuridica and not factors.titolare_effettivo_identificato:
        add(2, "Titolare effettivo non identificato per persona giuridica.")
    if factors.settore_alto_rischio:
        add(1, "Settore di attività a rischio.")
    if factors.rapporto_a_distanza:
        add(1, "Rapporto instaurato a distanza.")

    if score >= 5:
        level = RiskLevel.ALTO
    elif score >= 2:
        level = RiskLevel.MEDIO
    else:
        level = RiskLevel.BASSO
    return level, score, reasons


def document_expiry_status(document: IdentityDocument, *, today: date | None = None, warn_days: int = 30) -> dict[str, Any]:
    """Stato del documento: valido / in_scadenza / scaduto / non_indicato."""

    today = today or date.today()
    scad = _parse_date(document.scadenza)
    if not document.numero and not scad:
        return {"stato": "non_indicato", "scadenza": "", "giorni_residui": None}
    if scad is None:
        return {"stato": "non_indicato", "scadenza": "", "giorni_residui": None}
    giorni = (scad - today).days
    if giorni < 0:
        stato = "scaduto"
    elif giorni <= warn_days:
        stato = "in_scadenza"
    else:
        stato = "valido"
    return {"stato": stato, "scadenza": scad.isoformat(), "giorni_residui": giorni}


@dataclass
class KycRecord:
    cliente_id: str
    factors: KycFactors = field(default_factory=KycFactors)
    document: IdentityDocument = field(default_factory=IdentityDocument)
    note: str = ""

    def assess(self, *, today: date | None = None) -> dict[str, Any]:
        level, score, reasons = assess_risk(self.factors)
        doc = document_expiry_status(self.document, today=today)
        adeguata_verifica = doc["stato"] not in {"scaduto"} and (
            not self.factors.persona_giuridica or self.factors.titolare_effettivo_identificato
        )
        return {
            "clienteId": self.cliente_id,
            "livelloRischio": level.value,
            "punteggio": score,
            "motivazioni": reasons,
            "documento": doc,
            "titolareEffettivoIdentificato": self.factors.titolare_effettivo_identificato,
            "adeguataVerificaCompleta": bool(adeguata_verifica),
            "verificaRafforzataRichiesta": level == RiskLevel.ALTO,
        }


__all__ = [
    "RiskLevel",
    "IdentityDocument",
    "KycFactors",
    "KycRecord",
    "assess_risk",
    "document_expiry_status",
]
