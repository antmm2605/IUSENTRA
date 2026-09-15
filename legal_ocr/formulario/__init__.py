"""Formulario legale: le correzioni deterministiche al testo letto dalla macchina.

Il motore ottico legge lettere; un atto e' fatto di forme: «art. 163 c.p.c.»,
«D.Lgs. 28/2010», «R.G. n. 1234/2024», «€ 1.250,00», «Sez. VI», «perché»,
«a) … b) … c)». Le regole di questo pacchetto riportano il testo a quelle forme
senza interpretarlo: ogni regola ha un identificativo stabile, un'etichetta
per l'avvocato e un motivo, e il risultato dice quali regole sono intervenute e
quante volte. Cosi' il testo corretto resta verificabile contro la pagina.

Ordine di applicazione: prima i caratteri (legature, apostrofi, invisibili),
poi le abbreviazioni forensi, la punteggiatura, le strutture a forma fissa
(codice fiscale, partita IVA, CAP, IBAN, numero di ruolo, parole), le date, le cifre, i numeri romani, gli importi
in euro, gli accenti, che lavorano su parole gia' ripulite, e per ultimo il
lessico, che riporta al vocabolario le parole che non esistono.
"""

from __future__ import annotations

from . import abbreviazioni, accenti, caratteri, confusioni, date, lessico, numeri, numeri_romani, punteggiatura, valuta
from .regola import Esito, Regola, applica_regole

VERSIONE_FORMULARIO = "2026.09.15.formulario-legale.v3"

REGOLE: tuple[Regola, ...] = (
    *caratteri.REGOLE,
    *abbreviazioni.REGOLE,
    *punteggiatura.REGOLE,
    *confusioni.REGOLE,
    *date.REGOLE,
    *numeri.REGOLE,
    *numeri_romani.REGOLE,
    *valuta.REGOLE,
    *accenti.REGOLE,
    *lessico.REGOLE,
)

REGOLE_PER_ID: dict[str, Regola] = {regola.id: regola for regola in REGOLE}
ETICHETTE: dict[str, str] = {regola.id: regola.etichetta for regola in REGOLE}


def applica_formulario(testo: str) -> Esito:
    """Testo corretto e regole intervenute, con il numero di occorrenze."""
    return applica_regole(testo, REGOLE)


def etichetta(identificativo: str) -> str:
    """Nome leggibile della regola, per la pagina di revisione."""
    return ETICHETTE.get(identificativo, identificativo)


__all__ = ["ETICHETTE", "Esito", "REGOLE", "REGOLE_PER_ID", "Regola", "VERSIONE_FORMULARIO", "applica_formulario", "etichetta"]
