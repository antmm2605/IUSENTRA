"""Procedura atti: scheda decisa dal codice e dall'avvocato, calcolatore di termini e importi, revisione indipendente
e stati della consegna. Libreria senza effetti: non chiama modelli, non scrive su disco, non attiva endpoint."""
from .percorso import Preparazione, SchedaNonUtilizzabile, impronte, prepara, validazione_valida, valuta

__all__ = ["Preparazione", "SchedaNonUtilizzabile", "impronte", "prepara", "validazione_valida", "valuta"]
