"""Strumenti di testo condivisi: normalizzazione, numeri in lettere, estratti di prova.

Nessuna interpretazione giuridica qui: solo il modo uniforme di leggere il testo del
provvedimento (apostrofi tipografici, spazi, numeri scritti in lettere come «dieci»).
Le date si leggono solo con ``legal_ocr.formulario.date.trova_date``, che esclude i
riferimenti normativi («D.Lgs. 10/10/2022») e le date impossibili.
"""

from __future__ import annotations

import re
from datetime import date

NUMERI = {
    "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "nove": 9,
    "dieci": 10, "quindici": 15, "venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60,
    "settanta": 70, "novanta": 90, "centoventi": 120,
}
#: un numero di giorni scritto in cifre o in lettere, anche «gg.»
NUMERO = r"(\d{1,3}|" + "|".join(sorted(NUMERI, key=len, reverse=True)) + r")"
GIORNI = r"(?:giorni|gg\.?)"


def normalizza(testo: str) -> str:
    """Spazi singoli e apostrofi semplici: le espressioni regolari leggono un solo alfabeto."""
    pulito = str(testo or "").replace("’", "'").replace("‘", "'").replace("`", "'")
    pulito = pulito.replace("“", '"').replace("”", '"').replace(" ", " ")
    return " ".join(pulito.split())


def numero(valore: str) -> int | None:
    valore = str(valore or "").strip().lower()
    if valore.isdigit():
        return int(valore)
    return NUMERI.get(valore)


def estratto(testo: str, inizio: int, fine: int, margine: int = 70) -> str:
    """La prova: il passaggio letto, con un po' di contesto, mai più di ~300 caratteri."""
    a, b = max(0, inizio - margine), min(len(testo), fine + margine)
    corpo = testo[a:b].strip()
    return ("…" if a else "") + corpo[:300] + ("…" if b < len(testo) else "")


def date_vere(testo: str) -> list[tuple[date, int, int, str]]:
    """Le date del calendario scritte nel testo, con anno a quattro cifre: (data, inizio, fine, scritto)."""
    from legal_ocr.formulario.date import trova_date

    trovate = []
    for voce in trova_date(testo):
        if voce.forma == "numerica" and len(re.split(r"[./-]", voce.letto)[-1].strip()) != 4:
            continue
        trovate.append((voce.data, voce.inizio, voce.fine, voce.letto))
    return trovate


_RE_ORA = re.compile(r"\bore\s+(\d{1,2})(?:\s*[.:,]\s*(\d{2}))?\b", re.I)


def ora_dopo(testo: str, posizione: int, finestra: int = 40) -> str:
    """L'orario scritto subito dopo una data («12/01/2027 ore 9.30» → «09:30»)."""
    trovata = _RE_ORA.search(testo[posizione:posizione + finestra])
    if trovata is None:
        return ""
    ore, minuti = int(trovata.group(1)), int(trovata.group(2) or 0)
    return f"{ore:02d}:{minuti:02d}" if ore < 24 and minuti < 60 else ""


__all__ = ["GIORNI", "NUMERI", "NUMERO", "date_vere", "estratto", "normalizza", "numero", "ora_dopo"]
