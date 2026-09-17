"""Formati italiani e pulizia del testo per la lettura del fascicolo."""

from __future__ import annotations

import re
from html import unescape
from datetime import date, datetime
from typing import Any

MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")


def pulisci(valore: Any) -> str:
    return " ".join(unescape(str(valore or "")).split()).strip()


def data_da(valore: Any) -> date | None:
    """Data da ISO, con o senza ora, o da gg/mm/aaaa; None se illeggibile."""
    testo = pulisci(valore)
    if not testo:
        return None
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    corrispondenza = re.match(r"^(\d{4})-(\d{2})-(\d{2})", testo)
    if corrispondenza:
        try:
            return date(int(corrispondenza.group(1)), int(corrispondenza.group(2)), int(corrispondenza.group(3)))
        except ValueError:
            return None
    corrispondenza = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", testo)
    if corrispondenza:
        try:
            return date(int(corrispondenza.group(3)), int(corrispondenza.group(2)), int(corrispondenza.group(1)))
        except ValueError:
            return None
    return None


def data_it(valore: Any) -> str:
    giorno = data_da(valore)
    return giorno.strftime("%d/%m/%Y") if giorno else ""


def dataora_it(valore: Any) -> str:
    testo = pulisci(valore)
    giorno = data_da(testo)
    if not giorno:
        return ""
    ora = re.search(r"T(\d{2}):(\d{2})", testo)
    return f"{giorno.strftime('%d/%m/%Y')} ore {ora.group(1)}:{ora.group(2)}" if ora else giorno.strftime("%d/%m/%Y")


def euro(valore: Any) -> str:
    try:
        numero = float(valore or 0)
    except (TypeError, ValueError):
        return ""
    if not numero:
        return ""
    return "€ " + f"{numero:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def elenco(voci: list[str], congiunzione: str = "e") -> str:
    puliti = [pulisci(v) for v in voci if pulisci(v)]
    if not puliti:
        return ""
    if len(puliti) == 1:
        return puliti[0]
    return ", ".join(puliti[:-1]) + f" {congiunzione} " + puliti[-1]


def plurale(numero: int, singolare: str, plurale_: str) -> str:
    return f"{numero} {singolare if numero == 1 else plurale_}"


__all__ = ["MESI", "data_da", "data_it", "dataora_it", "elenco", "euro", "plurale", "pulisci"]
