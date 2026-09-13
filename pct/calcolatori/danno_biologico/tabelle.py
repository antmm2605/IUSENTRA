"""Caricamento dei dati tabellari da ``pct/data/tabelle_danno``.

I valori restano in JSON e non nel codice: sono dati ufficiali datati, che si
aggiornano quando esce un nuovo decreto o una nuova edizione, non logica di
calcolo. Il caricamento e' memorizzato una volta sola per processo.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

from pct.calcolatori.danno_biologico.fonti import FonteTabella

_CARTELLA_DATI = Path(__file__).resolve().parents[2] / "data" / "tabelle_danno"

ART_139 = "art_139_cap"
TUN_2025 = "tun_dpr_12_2025"
MILANO_2024 = "milano_2024"
MILANO_2024_PREMORIENZA = "milano_2024_premorienza"
MILANO_2024_TERMINALE = "milano_2024_terminale"
MILANO_2024_PARENTALE = "milano_2024_parentale"
MILANO_2024_CONSENSO = "milano_2024_consenso_informato"
MILANO_2024_DIFFAMAZIONE = "milano_2024_diffamazione"
MILANO_2024_CAPITALIZZAZIONE = "milano_2024_capitalizzazione"


@lru_cache(maxsize=None)
def carica(identificativo: str) -> Dict[str, Any]:
    """Restituisce i dati grezzi della tabella indicata."""
    percorso = _CARTELLA_DATI / f"{identificativo}.json"
    if not percorso.is_file():
        raise FileNotFoundError(f"Tabella di liquidazione non disponibile: {identificativo}")
    with percorso.open(encoding="utf-8") as sorgente:
        return json.load(sorgente)


@lru_cache(maxsize=None)
def fonte(identificativo: str) -> FonteTabella:
    return FonteTabella.da_dati(carica(identificativo))


def mappa_numerica(dati: Dict[str, Any], chiave: str) -> Dict[int, float]:
    """Converte in interi le chiavi di una mappa punto/eta' letta dal JSON."""
    return {int(k): float(v) for k, v in dati[chiave].items()}


def mappa_terne(dati: Dict[str, Any], chiave: str) -> Dict[int, Tuple[float, float, float]]:
    """Come :func:`mappa_numerica`, per le mappe a tre valori (min/med/max)."""
    return {int(k): (float(v[0]), float(v[1]), float(v[2])) for k, v in dati[chiave].items()}
