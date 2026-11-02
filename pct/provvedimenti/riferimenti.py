"""I dati in ingresso da cui si contano i termini: udienza, comunicazione, pronuncia, pubblicazione.

Ogni dato porta la sua fonte (il provvedimento, l'agenda del fascicolo, la PEC di
cancelleria), perché il passaggio mostrato all'avvocato dica da dove viene la data.
Un dato assente resta assente: la regola che ne ha bisogno diventa una domanda.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Riferimenti:
    oggi: date
    udienza: date | None = None
    udienza_ora: str = ""
    udienza_fonte: str = ""  # «provvedimento» | «fascicolo»
    udienza_candidate: tuple[date, ...] = ()
    id_appuntamento: str = ""
    modalita: str = ""
    comunicata_il: date | None = None
    pronuncia: date | None = None
    pubblicazione: date | None = None
    prove_tipo: dict[str, str] = field(default_factory=dict)

    def dato_udienza(self) -> tuple[str, str, str]:
        quando = f"{self.udienza:%d/%m/%Y}" + (f" ore {self.udienza_ora}" if self.udienza_ora else "") if self.udienza else ""
        fonte = "provvedimento" if self.udienza_fonte == "provvedimento" else "agenda e scadenziario del fascicolo"
        return ("Udienza", quando, fonte)

    def dato_evento(self, evento: str) -> tuple[date | None, tuple[str, str, str] | None]:
        """Il giorno da cui decorre il termine e il dato da mostrare, se noto."""
        valore = {"comunicazione": self.comunicata_il, "pronuncia": self.pronuncia, "pubblicazione": self.pubblicazione}.get(evento)
        if valore is None:
            return None, None
        fonte = {"comunicazione": "consegna della PEC di cancelleria", "pronuncia": "data in calce al provvedimento",
                 "pubblicazione": "data di deposito della sentenza"}[evento]
        return valore, (f"Data di {evento}", f"{valore:%d/%m/%Y}", fonte)

    def domanda_udienza(self, cosa: str) -> str:
        if len(self.udienza_candidate) > 1:
            elenco = ", ".join(f"{d:%d/%m/%Y}" for d in self.udienza_candidate)
            return f"{cosa} si conta dall'udienza, ma le udienze future sono più d'una ({elenco}): indicare quale."
        return f"{cosa} si conta dall'udienza, ma il provvedimento non la indica e il fascicolo non ha un'udienza futura certa: indicarne la data."

    @staticmethod
    def domanda_evento(evento: str, cosa: str) -> str:
        if evento == "notificazione":
            return f"{cosa} decorre dalla notificazione, che la comunicazione di cancelleria non sostituisce: indicare la data di notifica."
        return f"{cosa} decorre dalla {evento}, che non si legge con certezza: indicarne la data."


__all__ = ["Riferimenti"]
