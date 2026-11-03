"""Semaforo dei motori pesanti: un solo motore alla volta per tutto il server, con coda per priorità.

Lo usano lo scheduler (corsie e sequenza notturna), il worker OCR e le letture in sfondo avviate dall'app; vive in
un SQLite sotto ``/data`` (condiviso dai container). Chi tiene il semaforo rinnova un «affitto» ogni 30 secondi:
se il processo muore l'affitto scade e il semaforo passa al primo in coda. Le richieste web non lo usano mai.
"""

from pct.semaforo_motori.motore import (
    PRIORITA_DIFFERIBILE,
    PRIORITA_SEQUENZA,
    PRIORITA_URGENTE,
    SemaforoOccupato,
    in_turno,
    motore_pesante,
    semaforo_predefinito,
)
from pct.semaforo_motori.archivio import Semaforo

__all__ = [
    "PRIORITA_DIFFERIBILE",
    "PRIORITA_SEQUENZA",
    "PRIORITA_URGENTE",
    "Semaforo",
    "SemaforoOccupato",
    "in_turno",
    "motore_pesante",
    "semaforo_predefinito",
]
