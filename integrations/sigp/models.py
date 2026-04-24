"""Modelli dati leggeri per il modulo SIGP."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SigpDepositoDraft:
    ufficio: str
    procedimento: str
    tipo_atto: str
    ambiente: str = "produzione"
    parti: list[dict] = field(default_factory=list)
    difensore: dict = field(default_factory=dict)
    allegati: list[dict] = field(default_factory=list)
