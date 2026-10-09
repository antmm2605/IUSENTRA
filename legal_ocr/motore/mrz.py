"""Controlli locali ICAO 9303 condivisi da lettura e orientamento TD1.

Nessuna riparazione dei caratteri OCR e nessun confronto con dati attesi.
"""
from __future__ import annotations

import re


def cifra_controllo(value: str, digit: str) -> bool:
    if not digit.isascii() or not digit.isdigit() or len(digit) != 1:
        return False
    if not re.fullmatch(r'[A-Z0-9<]+', value):
        return False
    values = [0 if char == '<' else int(char) if char.isdigit() else ord(char) - 55 for char in value]
    return sum(number * (7, 3, 1)[index % 3] for index, number in enumerate(values)) % 10 == int(digit)


def td1_verificata(first: str, second: str, names: str) -> bool:
    if (len(first) < 15 or len(second) < 18 or '<<' not in names
            or not re.fullmatch(r'[IAC][A-Z<][A-Z<]{3}[A-Z0-9<]{9}[0-9]', first[:15])
            or not re.fullmatch(r'[0-9]{7}[A-Z0-9<][0-9]{7}[A-Z0-9<]{3}', second[:18])
            or not re.fullmatch(r'[A-Z<]+', names)
            or not cifra_controllo(first[5:14], first[14])
            or not cifra_controllo(second[:6], second[6])
            or not cifra_controllo(second[8:14], second[14])):
        return False
    if len(first) == 30 and len(second) == 30:
        return cifra_controllo(first[5:30] + second[:7] + second[8:15] + second[18:29], second[29])
    return True


def righe_td1_complete(text: str) -> tuple[str, str, str] | None:
    """Tre righe complete, con tutti i controlli numerici, senza normalizzazioni.

Il modello può restituire una riga unica separata da spazi. La scelta della
rotazione richiede entrambe le righe numeriche complete di 30 caratteri.
    """
    tokens = str(text or '').upper().split()
    for index in range(len(tokens) - 2):
        first, second, names = tokens[index:index + 3]
        if len(first) == 30 and len(second) == 30 and 24 <= len(names) <= 30 and td1_verificata(first, second, names):
            return first, second, names
    return None
