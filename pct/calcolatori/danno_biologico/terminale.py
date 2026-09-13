"""Danno non patrimoniale c.d. terminale — Milano 2024.

E' l'unica posta liquidabile iure proprio alla vittima di lesioni mortali
quando il decesso non e' immediato ma segue un apprezzabile lasso di tempo
(Cass. Sez. Un. 22 luglio 2015 n. 15350).

Struttura della tabella pubblicata: i primi tre giorni si liquidano in via
equitativa entro un tetto complessivo, senza personalizzazione; dal quarto
giorno la tabella indica sia l'importo pro die sia l'importo gia' cumulato dal
quarto giorno a quello in esame, e su questa seconda parte opera l'aumento per
massimo sconvolgimento fino al 50 per cento.
"""
from __future__ import annotations

from typing import Any, Dict

from pct.calcolatori.danno_biologico import tabelle

GIORNO_MINIMO_TABELLATO = 4


def _dati() -> Dict[str, Any]:
    return tabelle.carica(tabelle.MILANO_2024_TERMINALE)


def giorno_massimo() -> int:
    return int(_dati()["giorno_massimo"])


def massimo_primi_tre_giorni() -> float:
    return float(_dati()["primi_tre_giorni_massimo"])


def personalizzazione_massima() -> int:
    return int(_dati()["personalizzazione_massima_pct"])


def importo_pro_die(giorno: int) -> float:
    """Importo del singolo giorno, dal quarto in poi."""
    return float(_dati()["importo_pro_die"][str(min(giorno, giorno_massimo()))])


def importo_cumulato(giorni: int) -> float:
    """Importo complessivo dal quarto giorno al giorno indicato."""
    if giorni < GIORNO_MINIMO_TABELLATO:
        return 0.0
    return float(_dati()["importo_cumulato_dal_quarto_giorno"][str(min(giorni, giorno_massimo()))])
