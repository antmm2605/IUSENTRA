"""Il contesto che le regole leggono: il modello in costruzione, senza nessun accesso a dati esterni."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..eventi import Comunicazione, DepositoEseguito
from ..modello import Atto, Rito, TermineAssegnato, Udienza
from ..notifiche import NotificaEseguita
from ..provvedimenti import Ordine


@dataclass
class Contesto:
    fascicolo_id: str
    rg: str
    ufficio: str
    rito: Rito
    posizione: str  # attiva (attore, ricorrente, creditore), passiva, ignota
    atti: list[Atto]
    udienze: list[Udienza]
    termini: list[TermineAssegnato]
    ordini: list[tuple[Atto, Ordine]]
    notifiche: list[NotificaEseguita]
    depositi: list[DepositoEseguito]
    comunicazioni: list[Comunicazione]
    oggi: date
    fascicolo: dict = field(default_factory=dict)
    consegne_verificate: dict[str, dict[str, str]] = field(default_factory=dict)

    notifiche_storiche: dict[str, tuple[str, str]] = field(default_factory=dict)
    # I fascicoli della stessa vicenda (FontiCausa.collegati), per il titolo esecutivo e il precetto (collegamenti).
    collegati: list[dict] = field(default_factory=list)
    collegamenti_trovati: list[dict] = field(default_factory=list)

    def atto(self, oggetto_id: str) -> Atto | None:
        return next((a for a in self.atti if a.id == oggetto_id), None)

    def della_causa(self) -> list[Atto]:
        return [a for a in self.atti if a.appartenenza == "causa"]


def chi(onerato: str, posizione: str) -> str:
    """La parte onerata letta nell'atto, riferita a noi: noi, controparte, tutte_le_parti, terzo, ignoto."""
    if onerato in {"tutte_le_parti", "terzo"}:
        return onerato
    if onerato == "parte_attiva":
        return {"attiva": "noi", "passiva": "controparte"}.get(posizione, "ignoto")
    if onerato == "parte_passiva":
        return {"attiva": "controparte", "passiva": "noi"}.get(posizione, "ignoto")
    return "ignoto"


__all__ = ["Contesto", "chi"]
