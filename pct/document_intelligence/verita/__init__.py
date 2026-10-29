"""Etichette certe dei documenti del fascicolo: la verità di riferimento per misurare e addestrare il catalogo.

Una catalogazione proposta dalle regole o da un modello è un'ipotesi. Qui si raccolgono solo le etichette che il
software conosce con certezza, con la loro fonte:

- livello A, **dichiarate nel deposito telematico**: classificazione e tipo atto del Portale dei Servizi
  Telematici per gli atti e i provvedimenti importati (D.M. 44/2011, art. 14; Specifiche tecniche DGSIA);
- livello B, **decise dall'avvocato**: correzione manuale o conferma singola dopo aver letto la prova. La conferma
  massiva non è un'etichetta: attesta che una prova esiste, non che l'avvocato abbia letto quel documento.

Gli XML con struttura ministeriale o FatturaPA si riconoscono già con certezza dalla struttura: si contano a parte e
non servono ad addestrare. Nessun testo dei documenti esce da qui: solo identificativi, voci e conteggi.
"""

from .censimento import censisci, riepilogo, voce_pubblicabile
from .decisioni import etichette_dalle_decisioni
from .depositi import etichette_dai_depositi
from .modello import LIVELLO_AVVOCATO, LIVELLO_DEPOSITO, EtichettaCerta
from .portale import chiave_portale, etichetta_dal_portale

__all__ = [
    "LIVELLO_AVVOCATO",
    "LIVELLO_DEPOSITO",
    "EtichettaCerta",
    "censisci",
    "chiave_portale",
    "etichetta_dal_portale",
    "etichette_dai_depositi",
    "etichette_dalle_decisioni",
    "riepilogo",
    "voce_pubblicabile",
]
