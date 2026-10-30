"""Classificatore lineare piccolo per le voci del catalogo documentale.

TF-IDF sulle parole dell'intestazione del documento e regressione logistica multinomiale, scritti con numpy
(già dipendenza del prodotto): nessuna libreria di apprendimento, nessuna GPU, nessun servizio esterno. Gira sul
server, accanto ai documenti; il modello resta in memoria per la durata della misura.

Il classificatore non sostituisce le regole del catalogo: serve a trovare dove la pensa diversamente da loro,
cioè i documenti da mostrare per primi all'avvocato (art. 3 D.M. 44/2011 e art. 20 CAD per l'integrità dei
documenti letti; nessuna decisione automatica sul fascicolo).
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

# L'intestazione decide la natura dell'atto: titolo, ufficio, parti. Oltre, il corpo confonde le voci.
CARATTERI_LETTI = 4000
_PAROLA = re.compile(r"[a-z]{3,24}")
_SEME = 20261030


def parole(testo: str) -> list[str]:
    """Parole minuscole senza accenti dell'intestazione, più le coppie di parole consecutive."""
    grezzo = unicodedata.normalize("NFKD", str(testo or "")[:CARATTERI_LETTI].casefold())
    grezzo = "".join(car for car in grezzo if unicodedata.category(car) != "Mn")
    singole = _PAROLA.findall(grezzo)
    return singole + [f"{a}_{b}" for a, b in pairwise(singole)]


@dataclass(slots=True)
class Modello:
    voci: list[str]
    vocabolario: dict[str, int]
    idf: np.ndarray
    pesi: np.ndarray
    scarti: np.ndarray

    def probabilita(self, testi: Sequence[str], *, lotto: int = 512) -> np.ndarray:
        # A lotti: la matrice di tutti i documenti dello studio non sta in memoria accanto all'applicazione.
        parti = [_softmax(_vettori(testi[i:i + lotto], self.vocabolario, self.idf) @ self.pesi + self.scarti)
                 for i in range(0, len(testi), lotto)]
        return np.vstack(parti) if parti else np.zeros((0, len(self.voci)), dtype=np.float32)

    def predici(self, testi: Sequence[str]) -> list[tuple[str, float]]:
        p = self.probabilita(testi)
        indici = p.argmax(axis=1)
        return [(self.voci[i], float(p[riga, i])) for riga, i in enumerate(indici)]


def _vettori(testi: Sequence[str], vocabolario: dict[str, int], idf: np.ndarray) -> np.ndarray:
    x = np.zeros((len(testi), len(vocabolario)), dtype=np.float32)
    for riga, testo in enumerate(testi):
        for parola, n in Counter(parole(testo)).items():
            colonna = vocabolario.get(parola)
            if colonna is not None:
                x[riga, colonna] = 1.0 + math.log(n)
    x *= idf
    norme = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.where(norme == 0, 1.0, norme)


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def addestra(testi: Sequence[str], etichette: Sequence[str], *, massimo_parole: int = 5000, frequenza_minima: int = 3,
             epoche: int = 60, passo: float = 0.5, l2: float = 1e-4) -> Modello:
    """Addestramento deterministico: stesso insieme di esempi, stesso modello."""
    if len(testi) != len(etichette) or not testi:
        raise ValueError("Servono testi ed etichette in pari numero")
    voci = sorted(set(etichette))
    if len(voci) < 2:
        raise ValueError("Servono almeno due voci per addestrare")
    documenti = Counter()
    for testo in testi:
        documenti.update(set(parole(testo)))
    ammesse = sorted((p for p, n in documenti.items() if n >= frequenza_minima), key=lambda p: (-documenti[p], p))
    vocabolario = {p: i for i, p in enumerate(ammesse[:massimo_parole])}
    totale = len(testi)
    idf = np.array([math.log((1 + totale) / (1 + documenti[p])) + 1.0 for p in vocabolario], dtype=np.float32)
    x = _vettori(testi, vocabolario, idf)
    indice = {v: i for i, v in enumerate(voci)}
    y = np.zeros((totale, len(voci)), dtype=np.float32)
    y[np.arange(totale), [indice[e] for e in etichette]] = 1.0
    # Le voci rare pesano quanto le frequenti: altrimenti il modello impara solo le più comuni.
    frequenze = y.sum(axis=0)
    peso_esempio = (totale / (len(voci) * frequenze))[[indice[e] for e in etichette]].astype(np.float32)
    pesi = np.zeros((len(vocabolario), len(voci)), dtype=np.float32)
    scarti = np.zeros(len(voci), dtype=np.float32)
    generatore = np.random.default_rng(_SEME)
    lotto = 256
    for _ in range(epoche):
        ordine = generatore.permutation(totale)
        for inizio in range(0, totale, lotto):
            scelti = ordine[inizio:inizio + lotto]
            errore = (_softmax(x[scelti] @ pesi + scarti) - y[scelti]) * peso_esempio[scelti, None]
            pesi -= passo * (x[scelti].T @ errore / len(scelti) + l2 * pesi)
            scarti -= passo * errore.mean(axis=0)
    return Modello(voci=voci, vocabolario=vocabolario, idf=idf, pesi=pesi, scarti=scarti)


def in_verifica(chiave: str, *, quota: int = 20) -> bool:
    """Separazione stabile fra addestramento e verifica: dipende solo dall'identificativo del documento."""
    return int(hashlib.sha256(str(chiave).encode("utf-8")).hexdigest()[:8], 16) % 100 < quota


__all__ = ["CARATTERI_LETTI", "Modello", "addestra", "in_verifica", "parole"]
