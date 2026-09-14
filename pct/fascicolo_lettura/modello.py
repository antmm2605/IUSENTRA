"""I dati che alimentano la lettura e la forma del suo risultato.

La lettura lavora su dati semplici — dizionari e liste già serializzati — e non
sa nulla di Flask, di repository o di come quei dati siano stati raccolti. Così
la stessa lettura vale per Lex, per la pagina del fascicolo e per i test, e un
fascicolo di prova si costruisce a mano in poche righe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class DatiLettura:
    """Tutto ciò che il fascicolo sa di sé, nella forma in cui lo espone."""

    fascicolo: dict[str, Any] = field(default_factory=dict)
    documenti: list[dict[str, Any]] = field(default_factory=list)
    catalogo: list[dict[str, Any]] = field(default_factory=list)
    attivita: list[dict[str, Any]] = field(default_factory=list)
    depositi: list[dict[str, Any]] = field(default_factory=list)
    notifiche: list[dict[str, Any]] = field(default_factory=list)
    scadenze: list[dict[str, Any]] = field(default_factory=list)
    appuntamenti: list[dict[str, Any]] = field(default_factory=list)
    conformita: dict[str, Any] = field(default_factory=dict)
    regia: dict[str, Any] = field(default_factory=dict)
    economico: dict[str, Any] = field(default_factory=dict)
    parti: list[dict[str, Any]] = field(default_factory=list)
    oggi: date | None = None


@dataclass
class Evento:
    """Un fatto del fascicolo, datato e ricondotto alla sua prova."""

    data: str
    categoria: str
    titolo: str
    dettaglio: str = ""
    esito: str = ""
    fonte: str = ""
    fonte_id: str = ""

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "categoria": self.categoria,
            "titolo": self.titolo,
            "dettaglio": self.dettaglio,
            "esito": self.esito,
            "fonte": self.fonte,
            "fonte_id": self.fonte_id,
        }


@dataclass
class Passo:
    """Un prossimo passaggio, con la sua urgenza e la ragione che lo sostiene."""

    urgenza: int  # 0 = scaduto/bloccante, 1 = entro pochi giorni, 2 = prossimo, 3 = di governo
    azione: str
    motivo: str = ""
    entro: str = ""
    fonte: str = ""

    def come_dizionario(self) -> dict[str, Any]:
        return {"urgenza": self.urgenza, "azione": self.azione, "motivo": self.motivo, "entro": self.entro, "fonte": self.fonte}


__all__ = ["DatiLettura", "Evento", "Passo"]
