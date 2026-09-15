"""Le date scritte con lettere al posto delle cifre: «1O/O3/2O26» e' 10/03/2026.

Dentro un token a forma di data (giorno, mese, anno separati da barra, punto
o trattino, oppure anno-mese-giorno) il motore ottico confonde lo zero con la
O, l'uno con la l o la I, il cinque con la S, l'otto con la B, il due con la Z.
Qui la correzione e' certa perche' la forma e' quella di una data; fuori dai
token a forma di data non si tocca nulla, e un token senza nemmeno una cifra
non e' una data (SOS/OS non lo e').
"""

from __future__ import annotations

import re

from .confusioni import a_cifre
from .regola import Regola, regola_regex

_SEGNO = r"[\dOoIl|ÌSsBZz]"
_DATA_GREZZA = re.compile(rf"(?<![\w€])({_SEGNO}{{1,2}})\s*([./-])\s*({_SEGNO}{{1,2}})\s*[./-]\s*({_SEGNO}{{2,4}})(?![\w])")
_ISO_GREZZA = re.compile(rf"(?<![\w€])([12]{_SEGNO}{{3}})-({_SEGNO}{{2}})-({_SEGNO}{{2}})(?![\w])")


def _normalizza_token(match: re.Match[str]) -> str:
    grezzo = match.group(0)
    if not any(carattere.isdigit() for carattere in grezzo):
        return grezzo
    separatore = match.group(2)
    return f"{a_cifre(match.group(1))}{separatore}{a_cifre(match.group(3))}{separatore}{a_cifre(match.group(4))}"


def _normalizza_iso(match: re.Match[str]) -> str:
    grezzo = match.group(0)
    if not any(carattere.isdigit() for carattere in grezzo):
        return grezzo
    return f"{a_cifre(match.group(1))}-{a_cifre(match.group(2))}-{a_cifre(match.group(3))}"


def normalizza_data_ocr(testo: str) -> str:
    """Corregge O→0, l→1, S→5, B→8, Z→2 solo dentro i token a forma di data."""
    return _ISO_GREZZA.sub(_normalizza_iso, _DATA_GREZZA.sub(_normalizza_token, str(testo or "")))


# ── Date per esteso e orari ─────────────────────────────────────────────
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
_MESI_ABBREVIATI = {"gen": "gennaio", "feb": "febbraio", "mar": "marzo", "apr": "aprile", "mag": "maggio", "giu": "giugno", "lug": "luglio", "ago": "agosto", "set": "settembre", "sett": "settembre", "ott": "ottobre", "nov": "novembre", "dic": "dicembre"}
# Il nome del mese come lo scrive il lettore: «rn» al posto di «m», «c» al posto di «e», «l» al posto di «i».
_MESE_LETTO = re.compile(r"(?<![\w])([a-zà-ù]{3,10})(?![\w])", re.IGNORECASE)
_DATA_ESTESA_GREZZA = re.compile(
    rf"(?<![\w])(?P<giorno>{_SEGNO}{{1,2}}|primo|1[º°])\s+(?P<mese>[a-zà-ùA-ZÀ-Ù]{{3,10}})\.?\s+(?P<anno>{_SEGNO}{{4}})(?![\w])"
)
_ORA = re.compile(r"(?<![\w])(?P<pre>ore|alle\s+ore|alle|h\.?)\s*(?P<ora>[01]?\d|2[0-3])\s*[.,]\s*(?P<minuti>[0-5]\d)(?![\w:.,]\d)", re.IGNORECASE)


def mese_canonico(letto: str) -> str:
    """Il mese scritto bene, se il token letto e' un mese (anche abbreviato o con un errore di lettura)."""
    import difflib

    token = str(letto or "").strip(".").casefold()
    if not token:
        return ""
    if token in MESI:
        return token
    if token in _MESI_ABBREVIATI:
        return _MESI_ABBREVIATI[token]
    ripulito = token.replace("rn", "m").replace("|", "l")
    if ripulito in MESI:
        return ripulito
    vicini = difflib.get_close_matches(ripulito, MESI, n=1, cutoff=0.82)
    return vicini[0] if vicini and len(ripulito) >= 4 else ""


def _data_estesa(match: re.Match[str]) -> str:
    giorno, mese, anno = match.group("giorno"), match.group("mese"), match.group("anno")
    canonico = mese_canonico(mese)
    if not canonico:
        return match.group(0)
    if giorno.casefold() == "primo" or giorno[:1] == "1" and giorno[1:] in ("º", "°"):
        giorno_cifre = "1"
    else:
        giorno_cifre = a_cifre(giorno)
    anno_cifre = a_cifre(anno)
    if not (giorno_cifre.isdigit() and anno_cifre.isdigit() and 1 <= int(giorno_cifre) <= 31):
        return match.group(0)
    mese_scritto = canonico if mese.islower() or mese_canonico(mese) != mese.casefold() else mese
    if mese[:1].isupper() and mese_scritto == canonico:
        mese_scritto = canonico.capitalize() if mese.istitle() else canonico
    return f"{giorno_cifre} {mese_scritto} {anno_cifre}"


def _ora(match: re.Match[str]) -> str:
    return f"{match.group('pre')} {int(match.group('ora'))}:{match.group('minuti')}"


REGOLE: tuple[Regola, ...] = (
    regola_regex("num.data_estesa.v1", "data per esteso", "Giorno e anno con lettere al posto delle cifre, mese letto male o abbreviato: «1O rnarzo 2O26» e' 10 marzo 2026.", _DATA_ESTESA_GREZZA, _data_estesa),
    regola_regex("num.ora.v1", "orario", "L'orario di udienza si scrive con i due punti: «ore 9.30» e' ore 9:30.", _ORA, _ora),
    regola_regex("num.data.v1", "data con lettere al posto delle cifre", "Dentro una data O, l, S, B e Z sono 0, 1, 5, 8 e 2.", _DATA_GREZZA, _normalizza_token),
    regola_regex("num.data_iso.v1", "data anno-mese-giorno con lettere", "Dentro una data ISO O, l, S, B e Z sono 0, 1, 5, 8 e 2.", _ISO_GREZZA, _normalizza_iso),
)

__all__ = ["MESI", "REGOLE", "mese_canonico", "normalizza_data_ocr"]
