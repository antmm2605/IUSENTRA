"""Le date scritte con lettere al posto delle cifre: «1O/O3/2O26» e' 10/03/2026.

Dentro un token a forma di data (giorno, mese, anno separati da barra, punto
o trattino, oppure anno-mese-giorno) il motore ottico confonde lo zero con la
O, l'uno con la l o la I, il cinque con la S, l'otto con la B, il due con la Z.
La correzione e' certa solo se il risultato e' una data del calendario con
l'anno a quattro cifre (1900-2099), se almeno meta' dei segni erano gia'
cifre vere, con al massimo una sostituzione per giorno e per mese e due
nell'anno (che deve avere almeno due cifre vere): cosi' «1O/O3/2O26» e
«1S/O8/2O2S» diventano date, mentre «SOS/OS/OO», «IS/OB/ZOZS», «l/S/BZ» o un
numero di protocollo non lo diventano mai. Fuori dai token a forma di data
non si tocca nulla.

Un riferimento normativo non è mai una data: «l. 69/2023» è la legge 69 del
2023 e «l. 5/2026» non è il 1° maggio 2026 (vedi `riferimenti_normativi.py`).

Formato di riferimento: giorno/mese/anno, come nei provvedimenti e nelle
comunicazioni di cancelleria (D.M. 44/2011, specifiche DGSIA: DataDeposito e
DataUdienza sono giorno-mese-anno).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .confusioni import LETTERA_PER_CIFRA_SICURE, a_cifre
from .regola import Regola, regola_regex
from .riferimenti_normativi import e_riferimento_normativo

_SEGNO = r"[\dOoIl|ÌSsBZz]"
_DATA_GREZZA = re.compile(rf"(?<![\w€])({_SEGNO}{{1,2}})\s*([./-])\s*({_SEGNO}{{1,2}})\s*[./-]\s*({_SEGNO}{{2,4}})(?![\w])")
_ISO_GREZZA = re.compile(rf"(?<![\w€])([12]{_SEGNO}{{3}})-({_SEGNO}{{2}})-({_SEGNO}{{2}})(?![\w])")
SOSTITUZIONI_ANNO_MASSIME = 2
ANNO_MINIMO, ANNO_MASSIMO = 1900, 2099


def _sostituzioni(token: str) -> int:
    return sum(1 for carattere in token if carattere in LETTERA_PER_CIFRA_SICURE)


def _cifre_vere(token: str) -> int:
    return sum(1 for carattere in token if carattere.isdigit())


def _anno_corretto(grezzo: str) -> str:
    """L'anno a quattro cifre se plausibile, altrimenti stringa vuota."""
    if len(grezzo) == 4:
        if _cifre_vere(grezzo) < 2 or _sostituzioni(grezzo) > SOSTITUZIONI_ANNO_MASSIME:
            return ""
        anno = a_cifre(grezzo)
        return anno if anno.isdigit() and ANNO_MINIMO <= int(anno) <= ANNO_MASSIMO else ""
    if len(grezzo) == 2 and grezzo.isdigit():
        valore = int(grezzo)
        return str(valore + (2000 if valore <= 49 else 1900))
    return ""


def _componente(grezzo: str, massimo: int) -> str:
    """Giorno o mese: al massimo una sostituzione, risultato fra 1 e `massimo`."""
    if _sostituzioni(grezzo) > 1:
        return ""
    valore = a_cifre(grezzo)
    if not valore.isdigit() or not 1 <= int(valore) <= massimo:
        return ""
    return valore


@dataclass(frozen=True, slots=True)
class DataCorretta:
    """Una data riconosciuta nel testo: com'era scritta, come si scrive, che data e'."""

    letto: str
    scritto: str
    data: date
    inizio: int
    fine: int
    sostituzioni: int
    forma: str  # numerica | iso | estesa


def data_da_componenti(giorno: str, mese: str, anno: str, *, separatore: str = "/", iso: bool = False) -> tuple[str, date] | None:
    """La data corretta da tre componenti grezzi, oppure None se la correzione non e' certa."""
    segni = giorno + mese + anno
    if _cifre_vere(segni) * 2 < len(segni):
        return None
    anno_ok = _anno_corretto(anno)
    mese_ok = _componente(mese, 12)
    giorno_ok = _componente(giorno, 31)
    if not (anno_ok and mese_ok and giorno_ok):
        return None
    try:
        valore = date(int(anno_ok), int(mese_ok), int(giorno_ok))
    except ValueError:
        return None
    anno_scritto = anno_ok if len(anno) == 4 else anno
    if iso:
        return f"{anno_scritto}-{mese_ok.zfill(2)}-{giorno_ok.zfill(2)}", valore
    return f"{giorno_ok}{separatore}{mese_ok}{separatore}{anno_scritto}", valore


def _normalizza_token(match: re.Match[str]) -> str:
    grezzo = match.group(0)
    if e_riferimento_normativo(match.string, match.start(), match.end()):
        return grezzo
    esito = data_da_componenti(match.group(1), match.group(3), match.group(4), separatore=match.group(2))
    if esito is None or _sostituzioni(grezzo) == 0:
        return grezzo
    return esito[0]


def _normalizza_iso(match: re.Match[str]) -> str:
    grezzo = match.group(0)
    if e_riferimento_normativo(match.string, match.start(), match.end()):
        return grezzo
    esito = data_da_componenti(match.group(3), match.group(2), match.group(1), iso=True)
    if esito is None or _sostituzioni(grezzo) == 0:
        return grezzo
    return esito[0]


def normalizza_data_ocr(testo: str) -> str:
    """Corregge O→0, l→1, S→5, B→8, Z→2 solo dentro i token a forma di data che restano date vere."""
    return _ISO_GREZZA.sub(_normalizza_iso, _DATA_GREZZA.sub(_normalizza_token, str(testo or "")))


# ── Date per esteso e orari ─────────────────────────────────────────────
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
_MESI_ABBREVIATI = {"gen": "gennaio", "feb": "febbraio", "mar": "marzo", "apr": "aprile", "mag": "maggio", "giu": "giugno", "lug": "luglio", "ago": "agosto", "set": "settembre", "sett": "settembre", "ott": "ottobre", "nov": "novembre", "dic": "dicembre"}
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


def _giorno_esteso(giorno: str) -> str:
    if giorno.casefold() == "primo" or (giorno[:1] == "1" and giorno[1:] in ("º", "°")):
        return "1"
    return _componente(giorno, 31)


def data_estesa_da_componenti(giorno: str, mese: str, anno: str) -> tuple[str, date] | None:
    canonico = mese_canonico(mese)
    giorno_ok = _giorno_esteso(giorno)
    anno_ok = _anno_corretto(anno) if len(anno) == 4 else ""
    if not (canonico and giorno_ok and anno_ok):
        return None
    try:
        valore = date(int(anno_ok), MESI.index(canonico) + 1, int(giorno_ok))
    except ValueError:
        return None
    return f"{giorno_ok} {canonico} {anno_ok}", valore


def _data_estesa(match: re.Match[str]) -> str:
    giorno, mese, anno = match.group("giorno"), match.group("mese"), match.group("anno")
    esito = data_estesa_da_componenti(giorno, mese, anno)
    if esito is None:
        return match.group(0)
    canonico = mese_canonico(mese)
    mese_scritto = canonico if mese.islower() or canonico != mese.casefold() else mese
    if mese[:1].isupper() and mese_scritto == canonico:
        mese_scritto = canonico.capitalize() if mese.istitle() else canonico
    giorno_cifre, _, anno_cifre = esito[0].split(" ")
    return f"{giorno_cifre} {mese_scritto} {anno_cifre}"


def _ora(match: re.Match[str]) -> str:
    return f"{match.group('pre')} {int(match.group('ora'))}:{match.group('minuti')}"


def trova_date(testo: str) -> list[DataCorretta]:
    """Le date vere scritte nel testo, nell'ordine in cui compaiono, con posizione e correzione.

    Un token a forma di data che non diventa una data del calendario con le
    regole sopra non e' una data e non compare: chi legge non lo vede ne' lo
    segnala.
    """
    testo = str(testo or "")
    trovate: list[DataCorretta] = []
    occupate: list[tuple[int, int]] = []

    def libera(inizio: int, fine: int) -> bool:
        return all(fine <= a or inizio >= b for a, b in occupate)

    for match in _ISO_GREZZA.finditer(testo):
        esito = data_da_componenti(match.group(3), match.group(2), match.group(1), iso=True)
        if esito is None or e_riferimento_normativo(testo, match.start(), match.end()):
            continue
        trovate.append(DataCorretta(match.group(0), esito[0], esito[1], match.start(), match.end(), _sostituzioni(match.group(0)), "iso"))
        occupate.append((match.start(), match.end()))
    for match in _DATA_ESTESA_GREZZA.finditer(testo):
        esito = data_estesa_da_componenti(match.group("giorno"), match.group("mese"), match.group("anno"))
        if esito is None or not libera(match.start(), match.end()) or e_riferimento_normativo(testo, match.start(), match.end()):
            continue
        trovate.append(DataCorretta(match.group(0), esito[0], esito[1], match.start(), match.end(), _sostituzioni(match.group("giorno") + match.group("anno")), "estesa"))
        occupate.append((match.start(), match.end()))
    for match in _DATA_GREZZA.finditer(testo):
        esito = data_da_componenti(match.group(1), match.group(3), match.group(4), separatore=match.group(2))
        if esito is None or not libera(match.start(), match.end()) or e_riferimento_normativo(testo, match.start(), match.end()):
            continue
        trovate.append(DataCorretta(match.group(0), esito[0], esito[1], match.start(), match.end(), _sostituzioni(match.group(0)), "numerica"))
        occupate.append((match.start(), match.end()))
    trovate.sort(key=lambda voce: voce.inizio)
    return trovate


REGOLE: tuple[Regola, ...] = (
    regola_regex("num.data_estesa.v1", "data per esteso", "Giorno e anno con lettere al posto delle cifre, mese letto male o abbreviato: «1O rnarzo 2O26» e' 10 marzo 2026.", _DATA_ESTESA_GREZZA, _data_estesa),
    regola_regex("num.ora.v1", "orario", "L'orario di udienza si scrive con i due punti: «ore 9.30» e' ore 9:30.", _ORA, _ora),
    regola_regex("num.data.v1", "data con lettere al posto delle cifre", "Dentro una data O, l, S, B e Z sono 0, 1, 5, 8 e 2, solo se ne esce una data vera.", _DATA_GREZZA, _normalizza_token),
    regola_regex("num.data_iso.v1", "data anno-mese-giorno con lettere", "Dentro una data ISO O, l, S, B e Z sono 0, 1, 5, 8 e 2, solo se ne esce una data vera.", _ISO_GREZZA, _normalizza_iso),
)

__all__ = ["DataCorretta", "MESI", "REGOLE", "SOSTITUZIONI_ANNO_MASSIME", "data_da_componenti", "data_estesa_da_componenti", "mese_canonico", "normalizza_data_ocr", "trova_date"]
