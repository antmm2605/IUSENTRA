"""Download con riprove per i recuperi in sfondo (prassi, testi della Giustizia amministrativa).

Un solo timeout o errore di rete non deve fermare il giro: si riprova due volte con attesa crescente, poi la voce
resta da ritentare e il giro passa alla successiva (decisione del 23/11/2026, dopo due giri della prassi interrotti
da ``TimeoutError: The read operation timed out``).
"""
from __future__ import annotations

import time
from typing import Any, Callable

ATTESE = (5.0, 15.0)


class ReteNonDisponibile(Exception):
    """La fonte non ha risposto dopo le riprove: la voce si ritenta al giro successivo."""


def scarica_con_riprove(scarica: Callable[[str], Any], url: str, *, attese: tuple[float, ...] = ATTESE,
                        dormi: Callable[[float], None] = time.sleep) -> Any:
    """La risposta di ``scarica(url)``; timeout, errori di rete e risposte 429/5xx si riprovano ``len(attese)`` volte."""
    ultimo = ""
    for tentativo in range(len(attese) + 1):
        if tentativo:
            dormi(attese[tentativo - 1])
        try:
            risposta = scarica(url)
        except Exception as exc:  # timeout, connessione chiusa, DNS: tutti transitori per una fonte pubblica
            ultimo = f"{type(exc).__name__}: {exc}"
            continue
        codice = int(getattr(risposta, "status_code", 200))
        if codice == 429 or codice >= 500:
            ultimo = f"risposta {codice}"
            continue
        return risposta
    raise ReteNonDisponibile(f"{ultimo} (dopo {len(attese) + 1} tentativi)")


__all__ = ["ATTESE", "ReteNonDisponibile", "scarica_con_riprove"]
