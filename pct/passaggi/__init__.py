"""Passaggi spiegabili e regole dello studio.

Ogni azione automatica del software si mostra come sequenza di passaggi con
regola, norma, prove e dati (``modello``); l'avvocato corregge un passaggio e
la correzione diventa una «regola dello studio» (``regole_studio``,
``correzione``) che il software applica ai casi simili (``applicazione``) senza
mai superare un vincolo di legge (``vincoli``). Persistenza in ``repository``;
adattatori dei produttori in ``produttori``.
"""

from .applicazione import Applicazione, applica_a_passaggio, applica_regole
from .correzione import CorrezioneRifiutata, regola_da_correzione
from .modello import Campo, Contesto, Dato, Passaggio, Prova, STATI, STATO_ESCLUSO
from .regole_studio import AMBITI, AZIONI, RegolaStudio
from .vincoli import Rifiuto, verifica_regola

__all__ = [
    "AMBITI", "AZIONI", "Applicazione", "Campo", "Contesto", "CorrezioneRifiutata", "Dato", "Passaggio", "Prova",
    "RegolaStudio", "Rifiuto", "STATI", "STATO_ESCLUSO", "applica_a_passaggio", "applica_regole", "regola_da_correzione",
    "verifica_regola",
]
