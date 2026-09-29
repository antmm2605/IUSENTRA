"""Posizione debitoria e documenti del credito.

- Art. 633 c.p.c.: il decreto ingiuntivo richiede un credito di somma liquida ed esigibile provato per
  iscritto; art. 634: le fatture e gli estratti delle scritture contabili sono prova scritta.
- D.Lgs. 231/2002 (transazioni commerciali): interessi moratori dal giorno successivo alla scadenza
  (art. 4) e indennizzo forfettario di 40 euro per ciascun credito (art. 6 c. 2).
- Art. 4 c. 2 D.Lgs. 231/2002: senza termine pattuito, gli interessi decorrono dopo trenta giorni dal
  ricevimento della fattura.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

STATI: dict[str, str] = {
    "da_diffidare": "Da diffidare",
    "diffidato": "Diffida inviata (art. 1219 c.c.)",
    "ricorso_da_depositare": "Ricorso per decreto ingiuntivo da depositare (art. 633 c.p.c.)",
    "ricorso_depositato": "Ricorso depositato",
    "decreto_emesso": "Decreto ingiuntivo emesso: notifica entro 60 giorni (art. 644)",
    "decreto_notificato": "Decreto notificato: 40 giorni per l'opposizione (art. 641)",
    "opposto": "Decreto opposto (art. 645): giudizio ordinario",
    "esecutivo": "Decreto esecutivo (artt. 642 e 647)",
    "precetto_notificato": "Precetto notificato: 10 giorni per pagare, efficacia 90 giorni (artt. 480-481)",
    "pignoramento": "Pignoramento eseguito",
    "chiusa_pagata": "Chiusa: pagata",
    "chiusa_transatta": "Chiusa: transazione",
    "chiusa_irrecuperabile": "Chiusa: credito irrecuperabile",
}


@dataclass
class DocumentoCredito:
    numero: str = ""
    data: str = ""
    scadenza: str = ""
    importo: float = 0.0

    def decorrenza_interessi(self) -> date | None:
        """Giorno da cui corrono gli interessi: dopo la scadenza, o 30 giorni dalla data se manca."""
        try:
            if self.scadenza:
                return date.fromisoformat(self.scadenza) + timedelta(days=1)
            if self.data:
                return date.fromisoformat(self.data) + timedelta(days=31)
        except ValueError:
            return None
        return None


@dataclass
class Evento:
    stato: str
    data: str
    nota: str = ""
    utente: str = ""
    registrato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class Posizione:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10].upper())
    lotto: str = ""
    creditore_id: str = ""
    creditore: str = ""
    debitore: str = ""
    debitore_codice: str = ""  # codice fiscale o partita IVA
    debitore_indirizzo: str = ""
    debitore_pec: str = ""
    commerciale: bool = True  # transazione commerciale (D.Lgs. 231/2002)
    documenti: list[DocumentoCredito] = field(default_factory=list)
    acconti: float = 0.0
    stato: str = "da_diffidare"
    eventi: list[Evento] = field(default_factory=list)
    fascicolo_id: str = ""
    note: str = ""
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def capitale(self) -> float:
        return round(sum(d.importo for d in self.documenti) - self.acconti, 2)

    @property
    def chiusa(self) -> bool:
        return self.stato.startswith("chiusa_")

    def to_dict(self) -> dict[str, Any]:
        dati = asdict(self)
        dati["capitale"] = self.capitale
        dati["stato_etichetta"] = STATI.get(self.stato, self.stato)
        return dati

    @classmethod
    def from_dict(cls, dati: dict[str, Any]) -> "Posizione":
        dati = {k: v for k, v in dict(dati).items() if k in cls.__dataclass_fields__}
        dati["documenti"] = [DocumentoCredito(**{k: v for k, v in d.items() if k in DocumentoCredito.__dataclass_fields__})
                             for d in dati.get("documenti") or [] if isinstance(d, dict)]
        dati["eventi"] = [Evento(**{k: v for k, v in e.items() if k in Evento.__dataclass_fields__})
                          for e in dati.get("eventi") or [] if isinstance(e, dict)]
        return cls(**dati)


__all__ = ["STATI", "DocumentoCredito", "Evento", "Posizione"]
