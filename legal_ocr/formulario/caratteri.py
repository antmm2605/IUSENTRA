"""Caratteri speciali: legature, apostrofi, virgolette, gradi e spazi invisibili.

Il motore ottico restituisce spesso caratteri tipograficamente "vicini" ma
diversi da quelli che un atto usa: la legatura «ﬁ» al posto di «fi», l'accento
acuto usato come apostrofo, l'ordinale «º» al posto del grado, spazi che non
sono spazi. Sono sostituzioni uno-a-uno, senza interpretazione del contenuto.
"""

from __future__ import annotations

import re
import unicodedata

from .regola import Regola, regola_regex

LEGATURE = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "ft",
    "ﬆ": "st",
    "ĳ": "ij",
    "œ": "oe",
    "æ": "ae",
}
# Segni che non hanno larghezza: il motore li produce dai bordi sporchi della
# scansione e finiscono dentro le parole spezzandole per l'indice e la ricerca.
INVISIBILI = "­​‌‍⁠﻿"
# Forme dell'apostrofo che l'OCR confonde fra loro; in un atto e' sempre l'apostrofo.
APOSTROFI = "`´‘’‛′ʼ"
VIRGOLETTE_APERTE = "“„‟«"
VIRGOLETTE_CHIUSE = "”»"


def _normalizza_unicode(testo: str) -> tuple[str, int]:
    """Composizione canonica: accento e lettera diventano un solo carattere."""
    composto = unicodedata.normalize("NFC", testo)
    return composto, int(composto != testo)


def _legature(testo: str) -> tuple[str, int]:
    quante = 0
    for legatura, lettere in LEGATURE.items():
        if legatura in testo:
            quante += testo.count(legatura)
            testo = testo.replace(legatura, lettere)
    return testo, quante


def _invisibili(testo: str) -> tuple[str, int]:
    quante = sum(testo.count(carattere) for carattere in INVISIBILI)
    if quante:
        testo = testo.translate({ord(carattere): None for carattere in INVISIBILI})
    spazi = testo.count(" ") + testo.count(" ") + testo.count(" ")
    if spazi:
        testo = testo.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    return testo, quante + spazi


_APOSTROFO = re.compile(f"[{re.escape(APOSTROFI)}]")
_DOPPIO_APOSTROFO = re.compile(r"(?<!')''(?!')")
_ORDINALE_DOPO_CIFRA = re.compile(r"(?<=\d)\s?[º˚]")
_SPAZI_MULTIPLI = re.compile(r"[ \t]{2,}")


REGOLE: tuple[Regola, ...] = (
    Regola("car.unicode.v1", "composizione dei caratteri accentati", "Accento e lettera separati ricomposti in un solo carattere.", _normalizza_unicode),
    Regola("car.legature.v1", "legature tipografiche", "Legature «ﬁ», «ﬂ» e simili sciolte nelle lettere che rappresentano.", _legature),
    Regola("car.invisibili.v1", "caratteri invisibili", "Trattini morbidi, spazi a larghezza zero e spazi unificatori rimossi.", _invisibili),
    regola_regex("car.apostrofo.v1", "apostrofi", "Accento acuto, accento grave e virgolette singole usati come apostrofo.", _APOSTROFO, "'"),
    regola_regex("car.virgolette.v1", "virgolette doppie", "Due apostrofi letti al posto delle virgolette.", _DOPPIO_APOSTROFO, '"'),
    regola_regex("car.grado.v1", "simbolo di grado", "Ordinale «º» dopo una cifra riportato al grado «°».", _ORDINALE_DOPO_CIFRA, "°"),
    regola_regex("car.spazi.v1", "spazi doppi", "Spazi ripetuti ridotti a uno.", _SPAZI_MULTIPLI, " "),
)

__all__ = ["APOSTROFI", "INVISIBILI", "LEGATURE", "REGOLE"]
