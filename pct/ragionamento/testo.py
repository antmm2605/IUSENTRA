"""Strumenti di lettura del testo: date, numeri di ruolo, frasi. Nessuna regola giuridica qui."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

_DATA = re.compile(r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4}|\d{2})(?!\d)")
_MESI = {m: i for i, m in enumerate(("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                      "settembre", "ottobre", "novembre", "dicembre"), 1)}
_DATA_LETTERE = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(_MESI) + r")\s+(\d{4})", re.I)
_RG = re.compile(r"(?<![\d/])(0*\d{1,6})\s*/\s*(\d{4}|\d{2})(?![\d/])")


def pulito(testo: object) -> str:
    return " ".join(str(testo or "").split()).strip()


def semplice(testo: object) -> str:
    """Minuscolo, senza accenti e con gli apostrofi uniformi: per confrontare, mai per mostrare."""
    grezzo = unicodedata.normalize("NFKD", pulito(testo).replace("’", "'").replace("¿", "'"))
    return "".join(c for c in grezzo if not unicodedata.combining(c)).casefold()


def giorno(valore: object) -> date | None:
    testo = pulito(valore)[:10]
    try:
        return date.fromisoformat(testo)
    except ValueError:
        return None


def data_it(valore: object) -> str:
    d = valore if isinstance(valore, date) else giorno(valore)
    return d.strftime("%d/%m/%Y") if d else ""


def _anno(a: str) -> int:
    n = int(a)
    return n + 2000 if n < 100 else n


def date_nel_testo(testo: str) -> list[tuple[int, int, date]]:
    """Le date scritte nel testo (gg.mm.aaaa, gg/mm/aa, «16 dicembre 2026») con la loro posizione."""
    trovate: list[tuple[int, int, date]] = []
    for m in _DATA.finditer(testo):
        try:
            trovate.append((m.start(), m.end(), date(_anno(m.group(3)), int(m.group(2)), int(m.group(1)))))
        except ValueError:
            continue
    for m in _DATA_LETTERE.finditer(testo):
        try:
            trovate.append((m.start(), m.end(), date(int(m.group(3)), _MESI[m.group(2).casefold()], int(m.group(1)))))
        except ValueError:
            continue
    return sorted(trovate)


def rg_normale(numero: object, anno: object = "") -> str:
    """«792/25» e «792/2025» sono lo stesso ruolo: si confrontano come «792/2025»."""
    testo = pulito(numero)
    m = _RG.search(testo) if "/" in testo else None
    if m:
        return f"{int(m.group(1))}/{_anno(m.group(2))}"
    if testo.isdigit() and pulito(anno).isdigit():
        return f"{int(testo)}/{_anno(pulito(anno))}"
    return ""


def ruoli_nel_testo(testo: str) -> list[tuple[int, str]]:
    """I numeri di ruolo scritti nel testo, con la posizione; le date non sono ruoli."""
    date_spans = [(a, b) for a, b, _ in date_nel_testo(testo)]
    esito = []
    for m in _RG.finditer(testo):
        if any(a <= m.start() < b for a, b in date_spans):
            continue
        esito.append((m.start(), f"{int(m.group(1))}/{_anno(m.group(2))}"))
    return esito


def frasi(testo: str) -> list[tuple[int, str]]:
    """Il testo diviso in periodi (punto, punto e virgola o a capo seguiti da maiuscola), con la posizione.

    Il punto delle date (16.12.2026) e delle abbreviazioni (art., c.p.c., dott.) non chiude il periodo.
    """
    esito: list[tuple[int, str]] = []
    inizio = 0
    for m in re.finditer(r"(?:[.;]|\n)\s+(?=[A-ZÀ-Ý])", testo):
        prima = testo[max(0, m.start() - 6):m.start() + 1].casefold()
        if re.search(r"(art|artt|c\.p\.c|c\.c|dott|dott\.ssa|avv|sig|n|nn|proc|ss|cfr|lett|co)\.$", prima):
            continue
        esito.append((inizio, testo[inizio:m.end()]))
        inizio = m.end()
    esito.append((inizio, testo[inizio:]))
    return [(p, f) for p, f in esito if f.strip()]


__all__ = ["data_it", "date_nel_testo", "frasi", "giorno", "pulito", "rg_normale", "ruoli_nel_testo", "semplice"]
