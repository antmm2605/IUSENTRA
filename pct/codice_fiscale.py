"""
pct/codice_fiscale.py — Decodifica del Codice Fiscale italiano.

Estrae: data di nascita, sesso, luogo di nascita, provincia.
"""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from typing import Optional

# Mappa mese: lettera CF → numero mese
_MESI = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "H": 6,
    "L": 7, "M": 8, "P": 9, "R": 10, "S": 11, "T": 12,
}

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@lru_cache(maxsize=1)
def _carica_belfiore() -> dict:
    path = os.path.join(_DATA_DIR, "belfiore.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def decodifica(cf: str) -> Optional[dict]:
    """
    Decodifica un codice fiscale di 16 caratteri.

    Ritorna un dict con:
        sesso          : "M" | "F"
        data_nascita   : "YYYY-MM-DD"  (stringa ISO)
        luogo_nascita  : nome comune o paese estero
        provincia_nascita : sigla provincia (2 lettere) | "EE" per esteri
        eta            : anni compiuti (int)
        belfiore       : codice Belfiore grezzo (4 char)

    Ritorna None se il CF è malformato.
    """
    if not cf:
        return None
    cf = cf.upper().strip()
    if len(cf) != 16:
        return None

    # --- Anno ---
    try:
        anno_2 = int(cf[6:8])
    except ValueError:
        return None

    # Convenzione: anno >= 00 → si assume 2000 se anno_2 <= anno_corrente%100,
    # altrimenti 1900.  Es: anno_2=80 → 1980; anno_2=05 → 2005.
    anno_corrente = date.today().year % 100
    anno = (2000 + anno_2) if anno_2 <= anno_corrente else (1900 + anno_2)

    # --- Mese ---
    lettera_mese = cf[8].upper()
    mese = _MESI.get(lettera_mese)
    if mese is None:
        return None

    # --- Giorno e sesso ---
    try:
        giorno_raw = int(cf[9:11])
    except ValueError:
        return None
    if giorno_raw > 40:
        sesso = "F"
        giorno = giorno_raw - 40
    else:
        sesso = "M"
        giorno = giorno_raw

    # Validità base del giorno
    if not (1 <= giorno <= 31):
        return None

    try:
        data_nascita = date(anno, mese, giorno)
    except ValueError:
        return None

    # --- Età ---
    oggi = date.today()
    eta = oggi.year - data_nascita.year - (
        (oggi.month, oggi.day) < (data_nascita.month, data_nascita.day)
    )

    # --- Codice Belfiore → luogo ---
    belfiore = cf[11:15].upper()
    lookup = _carica_belfiore()
    entry = lookup.get(belfiore)
    if entry:
        luogo = entry[0]
        provincia = entry[1]
    else:
        luogo = belfiore   # fallback: mostra il codice grezzo
        provincia = ""

    return {
        "sesso": sesso,
        "data_nascita": data_nascita.isoformat(),
        "luogo_nascita": luogo,
        "provincia_nascita": provincia,
        "eta": eta,
        "belfiore": belfiore,
    }
