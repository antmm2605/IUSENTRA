"""Processo tributario: d.lgs. 546/1992 fino al 31/12/2026, testo unico della giustizia tributaria dal 1° gennaio 2027.

Testo vigente del d.lgs. 175/2024 (biblioteca di consultazione, edizione vigente al 24/11/2026): l'art. 131 dispone che
le disposizioni del testo unico si applicano dal 1° gennaio 2027 e l'art. 130 abroga da quella data il d.lgs. 546/1992.
Ogni articolo del testo unico richiama nella rubrica l'articolo del d.lgs. 546/1992 che riproduce («Art. 67. Termine per
la proposizione del ricorso (articolo 21 del decreto legislativo n. 546 del 1992)»): la tavola qui sotto viene da lì.

- prima del 1° gennaio 2027 l'analisi cita il d.lgs. 546/1992 e avverte che gli atti compiuti dal 2027 si fondano sul
  testo unico;
- dal 1° gennaio 2027 ogni riferimento al d.lgs. 546/1992 passa all'articolo corrispondente del testo unico, solo se le
  stesse parole si leggono nel testo unico; altrimenti resta un dubbio esplicito.
"""
from __future__ import annotations

import re
from datetime import date

from .modello import Analisi, Punto, Rif
from .norme import NORME, contiene

DECORRENZA = date(2027, 1, 1)
# articolo del d.lgs. 546/1992 -> articolo del d.lgs. 175/2024 (dalle rubriche del testo unico)
TAVOLA = {"18": "64", "21": "67", "22": "68", "38": "87", "47": "96", "51": "105", "52": "106", "53": "107"}


def _cita_546(a: Analisi) -> bool:
    punti = a.punti() + [x for x in a.avvertenze if isinstance(x, Punto)]
    return any(r.chiave.startswith("dlgs546:") for p in punti for r in p.rif)


def _testo(s: str) -> str:
    def sost(m: re.Match) -> str:
        nuovi = [TAVOLA.get(n) for n in re.findall(r"\d+(?:-bis)?", m.group(1))]
        if not all(nuovi):
            return m.group(0)
        return ("artt. " if len(nuovi) > 1 else "art. ") + " e ".join(nuovi) + " d.lgs. 175/2024"
    # Elenco «12», «12 e 14», «12, 13 e 14»: il separatore è obbligatorio fra un numero e l'altro, così il motore
    # delle espressioni regolari non prova tutti i modi di spezzare le cifre («0000…»: tempo esponenziale, CodeQL py/redos).
    return re.sub(r"\bartt?\. (\d+(?:-bis)?(?:(?:, | e )\d+(?:-bis)?)*) d\.lgs\. 546/1992", sost, s)


def applica(a: Analisi, oggi: date) -> None:
    if not _cita_546(a):
        return
    if oggi < DECORRENZA:
        a.avvertenze.append(Punto(
            "Dal 1° gennaio 2027 si applica il testo unico della giustizia tributaria, che da quella data abroga il "
            "d.lgs. 546/1992: un atto del processo compiuto dal 2027 (per esempio un ricorso notificato a gennaio) va "
            "fondato sul testo unico, che ripete il termine di sessanta giorni (art. 67) e la costituzione entro trenta "
            "giorni (art. 68).",
            [Rif("dlgs175:131", "si applicano dal"), Rif("dlgs175:130", "il decreto legislativo 31 dicembre 1992, n. 546"),
             Rif("dlgs175:67", "entro sessanta giorni dalla data di notificazione dell'atto impugnato"),
             Rif("dlgs175:68", "entro trenta giorni dalla proposizione del ricorso")]))
        return
    for p in a.punti() + [x for x in a.avvertenze if isinstance(x, Punto)]:
        nuovi = []
        for r in p.rif:
            numero = r.chiave.split(":", 1)[1] if r.chiave.startswith("dlgs546:") else ""
            chiave = f"dlgs175:{TAVOLA.get(numero, '')}"
            if numero and chiave in NORME and contiene(chiave, r.ancora):
                nuovi.append(Rif(chiave, r.ancora))
            else:
                if numero:
                    a.dubbi.append(f"{NORME[r.chiave].citazione} è abrogato dal 1° gennaio 2027 (art. 130 d.lgs. 175/2024) "
                                   "e la corrispondenza nel testo unico non è verificata: controllare l'articolo vigente.")
                nuovi.append(r)
        p.rif = nuovi
        p.testo = _testo(p.testo)
    a.rimedio, a.bozza = _testo(a.rimedio), _testo(a.bozza)
    a.cosa_fare = [_testo(x) for x in a.cosa_fare]
    a.avvertenze.append(Punto("Il d.lgs. 546/1992 è abrogato dal 1° gennaio 2027: le norme citate sono quelle del testo "
                              "unico della giustizia tributaria.",
                              [Rif("dlgs175:131", "si applicano dal"),
                               Rif("dlgs175:130", "il decreto legislativo 31 dicembre 1992, n. 546")]))
