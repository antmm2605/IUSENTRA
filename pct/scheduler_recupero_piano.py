"""Un solo recupero al giorno del piano del giorno dopo un riavvio del worker.

Verifica del 02/11/2026: il recupero post-avvio ricostruiva da capo il piano di tutti gli studi a ogni
riavvio dopo le 06:00, senza contare i tentativi. Se il riavvio era causato dalla memoria esaurita, la
ricostruzione poteva causarne un altro, e così via. Ora il tentativo del giorno (data di Roma) si annota
prima di partire: un secondo riavvio nella stessa giornata non lo ripete, e il piano resta affidato al
cron delle 05:30 del giorno dopo o alla richiesta manuale dalla console.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)
NOME_FILE = "recupero_piano_del_giorno.json"


def _percorso(cartella: str | Path) -> Path:
    return Path(cartella) / NOME_FILE


def recupero_gia_tentato(cartella: str | Path, giorno: date) -> bool:
    try:
        dati = json.loads(_percorso(cartella).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except Exception as exc:
        logger.warning("[scheduler] Annotazione del recupero del piano illeggibile: %s", exc)
        return False
    return str(dati.get("giorno") or "") == giorno.isoformat()


def annota_tentativo(cartella: str | Path, giorno: date) -> bool:
    """Annota il tentativo prima di partire; False se non si può scrivere (allora il recupero non parte)."""
    percorso = _percorso(cartella)
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        temporaneo = percorso.with_suffix(".tmp")
        temporaneo.write_text(json.dumps({"giorno": giorno.isoformat()}), encoding="utf-8")
        temporaneo.replace(percorso)
        return True
    except Exception as exc:
        logger.error("[scheduler] Recupero del piano non annotato, quindi non avviato: %s", exc)
        return False
