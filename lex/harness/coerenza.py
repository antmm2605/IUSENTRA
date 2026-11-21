"""Controllo di coerenza dei fatti usati dall'analisi: quello che non torna diventa un dubbio dichiarato, non un'ipotesi.

Controlli (dalla valutazione sul testo libero del 21/11/2026):
- una data di notifica, consegna o ricezione uguale alla data di oggi o alla data del contratto;
- un importo zero;
- una somma «pagata» che non è nei fatti né è la somma dei pagamenti dei fatti;
- una scadenza già passata presentata come ancora da rispettare.
"""
from __future__ import annotations

import re
from datetime import date
from itertools import combinations

from .fatti import Fatti, euro
from .norme import piano

_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_EURO = re.compile(r"€\s?([\d.]+(?:,\d+)?)")
_EVENTO_PUNTUALE = re.compile(r"notificat\w*|notifica del|consegn\w*|ricevut\w*|ricezione")


def _data(m: re.Match) -> date | None:
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _valore(testo: str) -> float:
    return float(testo.replace(".", "").replace(",", "."))


def _data_contratto(f: Fatti) -> date | None:
    for e in f.eventi:
        if re.search(r"contratt|preliminare|appalto del|ordine del", piano(e.testo)):
            return e.data
    return None


def verifica(a, f: Fatti) -> list[str]:
    """Dubbi di coerenza sui punti dell'analisi (si aggiungono a ``a.dubbi`` dal chiamante)."""
    dubbi: list[str] = []
    contratto = _data_contratto(f)
    pagamenti = [i.valore for i in f.importi if re.search(r"pagat|versat|bonific|acconto|saldat", piano(i.contesto))]
    importi_fatti = {round(i.valore, 2) for i in f.importi}
    for p in [*a.termini, *a.conclusione, *a.inquadramento]:
        t = p.testo
        tp = piano(t)
        for m in _DATA.finditer(t):
            d = _data(m)
            prima = tp[max(0, m.start() - 40):m.start()]
            if d and _EVENTO_PUNTUALE.search(prima):
                if d == f.oggi:
                    dubbi.append(f"La data {m.group(0)} usata come notifica o consegna coincide con la data di oggi: "
                                 "verificare la data effettiva dell'evento (dato mancante).")
                elif contratto and d == contratto and not re.search(r"contratt|preliminare|appalto", prima):
                    dubbi.append(f"La data {m.group(0)} usata come notifica o consegna coincide con la data del contratto: "
                                 "verificare la data effettiva dell'evento (dato mancante).")
        for m in _EURO.finditer(t):
            v = _valore(m.group(1))
            if v == 0:
                dubbi.append("Un importo risulta pari a zero: il dato non è stato letto nei fatti e va indicato.")
            dopo_pagato = re.search(r"pagat\w*|versat\w*", tp[max(0, m.start() - 25):m.start()])
            if dopo_pagato and pagamenti and round(v, 2) not in importi_fatti and not any(
                    abs(sum(c) - v) < 0.01 for k in range(2, min(3, len(pagamenti)) + 1) for c in combinations(pagamenti, k)):
                dubbi.append(f"La somma pagata di {euro(v)} non risulta dai pagamenti dei fatti "
                             f"({', '.join(euro(x) for x in pagamenti)}): verificarla.")
    for p in a.termini:
        for m in re.finditer(r"entro (?:il )?(?:\w+ )?(\d{1,2}/\d{1,2}/\d{4})", p.testo):
            d = _data(_DATA.search(m.group(1)))
            if d and d < f.oggi and not re.search(r"tardiv|scadut|decors|maturat|decadut|oltre", piano(p.testo)):
                dubbi.append(f"Il termine del {m.group(1)} è già passato rispetto a oggi ({f.oggi.strftime('%d/%m/%Y')}): "
                             "verificare se è scaduto e con quali conseguenze.")
    return list(dict.fromkeys(dubbi))
