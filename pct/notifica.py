"""
Compatibilita' per il vecchio modulo di notifiche telematiche.

Il percorso produttivo L. 53/1994 e' stato spostato in ``pct.notifiche_legali``.
Questo modulo resta importabile per non rompere import storici, ma non puo'
piu' generare relate o inviare PEC con oggetti non conformi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .firma import FirmaDigitale
from .pec import ClientPEC, ConfigPEC


@dataclass
class RelataDiNotifica:
    """Dati storici della relata, conservati solo per compatibilita' import."""

    notificante: str
    cf_notificante: str
    pec_notificante: str
    destinatario: str
    cf_destinatario: str
    pec_destinatario: str
    atto_notificato: str
    data_ora: str
    numero_procedimento: Optional[str] = None
    autorita_giudiziaria: Optional[str] = None


class LegacyNotificaTelematicaDeprecata(RuntimeError):
    """Raised when legacy notification code is invoked for a productive flow."""


class NotificaTelematica:
    """
    Vecchio facade PEC disattivato.

    Il motore ammesso e' ``pct.notifiche_legali`` perche' impone oggetto L. 53,
    relata separata, firma digitale, ricevuta completa, fonte PEC e attestazioni.
    """

    def __init__(self, config_pec: ConfigPEC, firma: Optional[FirmaDigitale] = None):
        self.pec = ClientPEC(config_pec)
        self.firma = firma

    def notifica(
        self,
        atto_path: str,
        pec_destinatario: str,
        relata: RelataDiNotifica,
        allegati: Optional[List[str]] = None,
    ) -> dict:
        raise LegacyNotificaTelematicaDeprecata(
            "pct.notifica.NotificaTelematica e' disattivato: usa pct.notifiche_legali "
            "per imporre oggetto L. 53/1994, relata separata, firma digitale, ricevuta completa, "
            "fonte PEC e attestazioni."
        )

    def _corpo_notifica(self, relata: RelataDiNotifica) -> str:
        raise LegacyNotificaTelematicaDeprecata(
            "Corpo PEC legacy disattivato: usa pct.notifiche_legali."
        )

    def genera_relata(self, relata: RelataDiNotifica, output_path: str) -> str:
        raise LegacyNotificaTelematicaDeprecata(
            "Generazione relata legacy disattivata: usa il motore parametrico pct.notifiche_legali."
        )
