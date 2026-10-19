"""Termini delle schede di compilazione calcolati dal software, non da Lex.

Un campo ``calcolo`` di una scheda può dichiarare ``termine``: evento da cui decorre (``base``), durata in
giorni o mesi, direzione (``avanti`` o ``ritroso``) e applicazione della sospensione feriale. Il calcolo usa
lo stesso motore dello scadenziario (``pct.termini_processuali.ItalianDeadlineCalculator``): art. 155 c.p.c.
(dies a quo escluso, proroga o anticipo se l'ultimo giorno è sabato o festivo) e L. 742/1969 (sospensione
dal 1° al 31 agosto). Lex riceve la data già calcolata e si limita a spiegarla.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from pct.termini_processuali import ItalianDeadlineCalculator

# Evento di partenza → fatti dell'archivio delle letture da cui leggerne la data
BASI = {
    "udienza": [{"categoria": "data", "campo": "udienza"}],
    "notifica": [{"categoria": "data", "campo": "notifica"}, {"categoria": "prova_notifica"}],
    "comunicazione": [{"categoria": "data", "campo": "comunicazione"}, {"categoria": "prova_notifica"}],
    "provvedimento": [{"categoria": "data", "campo": "provvedimento"}],
    "evento": [{"categoria": "data", "campo": "evento"}],
}
CHIAVI = {"base", "giorni", "mesi", "direzione", "feriale"}


def valida_termine(termine: dict[str, Any]) -> list[str]:
    """Errori di forma della dichiarazione ``termine`` di un campo."""
    errori = [f"chiave sconosciuta: {k}" for k in termine if k not in CHIAVI]
    if termine.get("base") not in BASI:
        errori.append(f"base non ammessa: {termine.get('base')}")
    if bool(termine.get("giorni")) == bool(termine.get("mesi")):
        errori.append("indicare giorni oppure mesi")
    if termine.get("direzione") not in ("avanti", "ritroso"):
        errori.append("direzione deve essere avanti o ritroso")
    if not isinstance(termine.get("feriale"), bool):
        errori.append("feriale deve essere vero o falso")
    return errori


def _data(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore)[:10])
    except ValueError:
        return None


def data_base(termine: dict[str, Any], fatti: Iterable[Any]) -> date | None:
    """La data dell'evento di partenza letta dai fatti non respinti, se presente."""
    for sel in BASI[termine["base"]]:
        for fatto in fatti:
            if getattr(fatto, "verifica", "") == "respinto" or getattr(fatto, "categoria", "") != sel["categoria"]:
                continue
            if sel.get("campo") and getattr(fatto, "campo", "") != sel["campo"]:
                continue
            giorno = _data(getattr(fatto, "valore", ""))
            if giorno:
                return giorno
    return None


def calcola(termine: dict[str, Any], base: date) -> dict[str, Any]:
    """Scadenza e spiegazione del termine a partire dalla data base."""
    unita = "months" if termine.get("mesi") else "days"
    valore = int(termine.get("mesi") or termine.get("giorni"))
    r = ItalianDeadlineCalculator().calculate(
        base, valore, "backward" if termine["direzione"] == "ritroso" else "forward",
        suspend_august=termine["feriale"], period_type=unita)
    return {"scadenza": r["deadline"], "base": base.isoformat(), "spiegazione": r["explanation"],
            "verifica_avvocato": bool(r.get("requiresLegalReview"))}
