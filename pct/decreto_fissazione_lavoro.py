"""Il decreto di fissazione dell'udienza nel rito del lavoro, riconosciuto dal suo contenuto.

Art. 415 c.p.c.: depositato il ricorso, il giudice fissa con decreto l'udienza di discussione (comma 2);
il ricorso, unitamente al decreto, deve essere notificato al convenuto a cura dell'attore entro dieci
giorni dalla data di pronuncia del decreto (comma 4, termine ordinatorio) e tra la notificazione e
l'udienza deve intercorrere un termine non minore di trenta giorni (comma 5; quaranta se la notifica è
all'estero, comma 6). Il decreto è quindi la fonte certa dell'obbligo «notificare ricorso e decreto»:
la sua data è la pronuncia e la sua udienza è la base del termine a ritroso.

Il riconoscimento vale solo con tutti e tre i segni nel testo: il richiamo all'art. 415 (o «giudice
del lavoro»), la disposizione «FISSA ... udienza» e una data d'udienza leggibile. Serve quando il
catalogo non ha riconosciuto il documento (collaudo 10/11/2026, difetto G-3: «Contenuto da
verificare», «Note di trattazione scritta»). Modulo puro.
"""

from __future__ import annotations

import re
from datetime import date

ETICHETTA = "Decreto di fissazione udienza (art. 415 c.p.c.)"
NORMA = "art. 415, commi 2, 4 e 5, c.p.c."

_LAVORO = re.compile(r"\bart\.?\s*415\b|\bgiudice\s+del\s+lavoro\b", re.IGNORECASE)
_FISSA = re.compile(r"\bFISSA\b[^.;]{0,160}?\budienza\b[^.;0-9]{0,40}?(?:del(?:l['’])?\s+)?(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", re.IGNORECASE)
_RICORSO_ESTRANEO = re.compile(r"\bricorso\s+ex\s+art\.?\s*414\b|\bvoglia\s+l['’]?ill\.?mo\b|\bP\.?\s*Q\.?\s*M\.?\b", re.IGNORECASE)


def udienza_fissata(testo: str) -> str:
    """La data dell'udienza fissata dal decreto (ISO), o stringa vuota se non è leggibile con certezza."""
    trovato = _FISSA.search(str(testo or "")[:6000])
    if not trovato:
        return ""
    giorno, mese, anno = (int(x) for x in trovato.groups())
    try:
        return date(anno, mese, giorno).isoformat()
    except ValueError:
        return ""


def e_decreto_fissazione_lavoro(testo: str) -> bool:
    """Vero per il decreto del giudice che fissa l'udienza di discussione ex art. 415 c.p.c.

    Il ricorso che chiede la fissazione («voglia l'Ill.mo Giudice fissare l'udienza») non è il decreto:
    il decreto è breve, comincia dall'intestazione dell'ufficio e non contiene le conclusioni della parte.
    """
    testo = str(testo or "")
    testata = testo[:6000]
    if len(testo) > 12000 or _RICORSO_ESTRANEO.search(testata):
        return False
    return bool(_LAVORO.search(testata) and udienza_fissata(testata))


__all__ = ["ETICHETTA", "NORMA", "e_decreto_fissazione_lavoro", "udienza_fissata"]
