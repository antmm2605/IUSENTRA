"""Quanto vale una lettura: testo sicuro e forme forensi riconoscibili.

Una pagina viene letta con piu' impostazioni e si tiene la migliore. Non basta
contare i caratteri (una lettura sbagliata produce molto testo spazzatura a
bassa confidenza) e non basta la confidenza media (tre parole sicure sarebbero
la lettura migliore): le due misure si moltiplicano, e le forme che un atto
contiene sempre (numero di ruolo, «art.», date, importi, PEC, codice fiscale)
valgono di piu' dei segni che un atto non contiene mai.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

_FORME_FORENSI: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"\btribunale\s+di\s+[a-zàèéìòù' ]+", re.IGNORECASE), 8.0),
    (re.compile(r"\b(?:proc\.?\s*n\.?|r\.?\s*g\.?|rgac|rgnr)\s*[\w./-]+", re.IGNORECASE), 14.0),
    (re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"), 12.0),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.IGNORECASE), 14.0),
    (re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"), 8.0),
    (re.compile(r"(?:euro|€)\s*[.,]?\s*\d", re.IGNORECASE), 8.0),
    (re.compile(r"\b(?:artt?\.?|d\.?p\.?r\.?|d\.?lgs\.?|c\.p\.c\.|c\.p\.p\.|c\.c\.)\B", re.IGNORECASE), 8.0),
)
_SEGNI_SPURI = re.compile(r"[|~{}_\[\]^\\]")
_CONSONANTI_IMPOSSIBILI = re.compile(r"\b[bcdfghjklmnpqrstvwxz]{7,}\b", re.IGNORECASE)


def punteggio_parole(parole: Sequence[dict[str, Any]]) -> float:
    """Quantita' di testo pesata dalla confidenza e dalla quota di parole leggibili."""
    if not parole:
        return 0.0
    caratteri = sum(len(str(parola.get("text") or "")) for parola in parole)
    confidenze = [float(parola.get("conf") or 0.0) for parola in parole if float(parola.get("conf") or 0.0) > 0]
    media = sum(confidenze) / len(confidenze) if confidenze else 0.0
    leggibili = sum(1 for parola in parole if float(parola.get("conf") or 0.0) >= 0.60) / len(parole)
    return caratteri * (0.35 + 0.65 * media) * (0.5 + 0.5 * leggibili)


def bonus_forense(testo: str) -> float:
    """Punti in piu' per le forme di un atto, in meno per i segni che un atto non ha."""
    punti = 0.0
    for espressione, peso in _FORME_FORENSI:
        punti += len(espressione.findall(testo)) * peso
    punti -= len(_SEGNI_SPURI.findall(testo)) * 0.75
    punti -= len(_CONSONANTI_IMPOSSIBILI.findall(testo)) * 0.5
    return punti


def punteggio_lettura(parole: Sequence[dict[str, Any]], testo: str = "") -> float:
    """Punteggio complessivo di una lettura, per scegliere fra piu' configurazioni."""
    return punteggio_parole(parole) + bonus_forense(testo or " ".join(str(parola.get("text") or "") for parola in parole))


def confidenza_media(parole: Sequence[dict[str, Any]]) -> float:
    valori = [float(parola.get("conf") or 0.0) for parola in parole if float(parola.get("conf") or 0.0) > 0]
    return sum(valori) / len(valori) if valori else 0.0


__all__ = ["bonus_forense", "confidenza_media", "punteggio_lettura", "punteggio_parole"]
