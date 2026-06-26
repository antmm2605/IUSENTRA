"""Contratto ministeriale del messaggio PEC di deposito."""

from __future__ import annotations

import re
from typing import Any


_DEPOSITO_SUBJECT_RE = re.compile(r"^DEPOSITO\s+\S", re.IGNORECASE)


def normalizza_oggetto_deposito_pec(value: Any) -> str:
    """Compatta spazi e ritorna l'oggetto PEC pronto per il controllo."""

    return " ".join(str(value or "").strip().split())


def oggetto_deposito_pec_conforme(value: Any) -> bool:
    """True se l'oggetto rispetta la sintassi ministeriale: DEPOSITO + spazio + testo."""

    return bool(_DEPOSITO_SUBJECT_RE.match(normalizza_oggetto_deposito_pec(value)))


def dettaglio_oggetto_deposito_pec(value: Any) -> str:
    """Restituisce una motivazione operativa per oggetti PEC non conformi."""

    if oggetto_deposito_pec_conforme(value):
        return "Oggetto PEC conforme alla sintassi ministeriale DEPOSITO <testo libero>."
    return (
        "Oggetto PEC non conforme: deve iniziare con 'DEPOSITO', contenere uno spazio "
        "e avere testo libero non vuoto dopo lo spazio."
    )
