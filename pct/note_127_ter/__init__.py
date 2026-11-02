"""Decreto di trattazione scritta che sostituisce «l'udienza già fissata» (art. 127-ter c.p.c.).

Caso reale del 02/11/2026: la cancelleria comunica via PEC un decreto che dispone la
sostituzione dell'udienza già fissata con il deposito di note scritte e assegna un termine
perentorio «sino alla data della predetta udienza». Il decreto non scrive nessuna data: la
data è quella dell'udienza già presente nel fascicolo.

Questo pacchetto fa il lavoro preparatorio dell'avvocato, senza mai sostituirne le scelte:

* ``decreto``: riconosce il decreto e ciò che dispone (art. 127-ter c.p.c.);
* ``udienza_riferita``: individua l'udienza sostituita, solo se è una e futura (Europe/Rome);
* ``proposta``: il termine perentorio proposto in bozza, mai scritto in silenzio;
* ``adempimenti``: le indicazioni del decreto per le note e la prova della notifica
  (art. 19-bis Provv. DGSIA 16/04/2014, oggi art. 26 Specifiche DGSIA 7/8/2024, in attuazione
  dell'art. 34 D.M. 44/2011; artt. 16-decies e 16-undecies D.L. 179/2012);
* ``esame_pec``: l'esame del decreto arrivato con la comunicazione di cancelleria;
* ``udienza_cartolare``: l'udienza sostituita diventa «cartolare» (``pct/udienze/tipi.py``).

Il deposito delle note resta un atto dell'avvocato: firma digitale (art. 12 D.M. 44/2011) e
busta telematica non sono toccati da questo pacchetto.
"""

from .decreto import DecretoNoteScritte, riconosci_decreto
from .proposta import CODICE_NOTE_127_TER, PropostaNote, proposta_note, termine_equivalente
from .udienza_riferita import UdienzaRiferita, udienza_riferita

__all__ = [
    "CODICE_NOTE_127_TER",
    "DecretoNoteScritte",
    "PropostaNote",
    "UdienzaRiferita",
    "proposta_note",
    "riconosci_decreto",
    "termine_equivalente",
    "udienza_riferita",
]
