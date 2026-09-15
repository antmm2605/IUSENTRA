"""Il lessico dichiarato: le parole con cui il correttore può riportare una lettura.

Due elenchi, nessuna invenzione: il lessico forense (`forense.py`), scritto a
partire dal linguaggio dei codici e delle leggi che il gestionale già cita, e
il vocabolario italiano (`italiano.py`), che usa il dizionario di sistema
quando c'è e altrimenti resta al nucleo dichiarato. Il correttore
(`correttore.py`) cambia una parola solo quando la forma corretta è in uno dei
due e quella letta non c'è: fuori da questa regola non tocca nulla.
"""

from __future__ import annotations

from .correttore import VERSIONE_CORRETTORE, correggi_parola, correggi_testo
from .forense import FORMULE, FRASI, LESSICO, PROCESSO
from .italiano import ITALIANO_NUCLEO, dizionario_di_sistema, parole_conosciute

__all__ = [
    "FORMULE", "FRASI", "ITALIANO_NUCLEO", "LESSICO", "PROCESSO", "VERSIONE_CORRETTORE",
    "correggi_parola", "correggi_testo", "dizionario_di_sistema", "parole_conosciute",
]
