"""
pct/codice_fiscale.py — Decodifica del Codice Fiscale italiano.

Estrae: data di nascita, sesso, luogo di nascita, provincia.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date
from functools import lru_cache
from typing import Optional

# Mappa mese: lettera CF → numero mese
_MESI = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "H": 6,
    "L": 7, "M": 8, "P": 9, "R": 10, "S": 11, "T": 12,
}
_MESI_INV = {value: key for key, value in _MESI.items()}
_VOCALI = "AEIOU"
_PARI = {str(i): i for i in range(10)} | {chr(65 + i): i for i in range(26)}
_DISPARI = {
    "0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17, "8": 19, "9": 21,
    "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17, "I": 19, "J": 21,
    "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3, "Q": 6, "R": 8, "S": 12, "T": 14,
    "U": 16, "V": 10, "W": 22, "X": 25, "Y": 24, "Z": 23,
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


def _normalizza_testo(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z]", "", ascii_text.upper())


def _codice_nome(value: str, *, nome: bool = False) -> str:
    text = _normalizza_testo(value)
    consonanti = [ch for ch in text if ch not in _VOCALI]
    vocali = [ch for ch in text if ch in _VOCALI]
    if nome and len(consonanti) >= 4:
        base = [consonanti[0], consonanti[2], consonanti[3]]
    else:
        base = (consonanti + vocali)[:3]
    return "".join(base).ljust(3, "X")


def _checksum(primi_15: str) -> str:
    totale = 0
    for index, char in enumerate(primi_15.upper()):
        totale += _DISPARI[char] if index % 2 == 0 else _PARI[char]
    return chr(65 + (totale % 26))


def _parse_data(value: str | date) -> date | None:
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _indice_belfiore() -> dict[tuple[str, str], str]:
    indice: dict[tuple[str, str], str] = {}
    for codice, entry in _carica_belfiore().items():
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        luogo = _normalizza_testo(str(entry[0]))
        provincia = str(entry[1] or "").upper().strip()
        indice[(luogo, provincia)] = codice
        indice.setdefault((luogo, ""), codice)
    return indice


def trova_belfiore(luogo_nascita: str, provincia_nascita: str = "") -> Optional[dict]:
    """Trova il codice Belfiore a partire da luogo e, se disponibile, provincia."""
    luogo = _normalizza_testo(luogo_nascita)
    provincia = str(provincia_nascita or "").upper().strip()
    if not luogo:
        return None
    codice = _indice_belfiore().get((luogo, provincia)) or _indice_belfiore().get((luogo, ""))
    if not codice:
        return None
    entry = _carica_belfiore().get(codice) or ["", ""]
    return {"belfiore": codice, "luogo_nascita": entry[0], "provincia_nascita": entry[1]}


def calcola(
    *,
    cognome: str,
    nome: str,
    sesso: str,
    data_nascita: str | date,
    luogo_nascita: str,
    provincia_nascita: str = "",
) -> Optional[dict]:
    """Calcola il codice fiscale ordinario per persone fisiche italiane/estere.

    Non gestisce omocodie: il risultato va sempre verificato dall'operatore con
    il documento fiscale ufficiale.
    """
    nascita = _parse_data(data_nascita)
    luogo = trova_belfiore(luogo_nascita, provincia_nascita)
    sesso_norm = str(sesso or "").upper().strip()
    if not (cognome and nome and nascita and luogo and sesso_norm in {"M", "F"}):
        return None
    giorno = nascita.day + (40 if sesso_norm == "F" else 0)
    primi_15 = (
        f"{_codice_nome(cognome)}"
        f"{_codice_nome(nome, nome=True)}"
        f"{nascita.year % 100:02d}"
        f"{_MESI_INV[nascita.month]}"
        f"{giorno:02d}"
        f"{luogo['belfiore']}"
    )
    codice_fiscale = f"{primi_15}{_checksum(primi_15)}"
    return {
        "codice_fiscale": codice_fiscale,
        "sesso": sesso_norm,
        "data_nascita": nascita.isoformat(),
        "luogo_nascita": luogo["luogo_nascita"],
        "provincia_nascita": luogo["provincia_nascita"],
        "belfiore": luogo["belfiore"],
        "omocodia": False,
        "nota": "Calcolo ordinario senza gestione omocodia; verificare con documento fiscale ufficiale.",
    }


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
