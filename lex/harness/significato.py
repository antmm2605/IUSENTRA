"""Ricerca per significato sulle regole dell'harness: secondo segnale accanto al riconoscimento della fattispecie.

Ogni regola ha un nome, dei sinonimi e delle situazioni tipiche scritte con le parole del cliente
(fattispecie/significato_regole.py per le regole principali, fattispecie/significato_materie.py per le regole di materia).
La domanda normalizzata si confronta con questi testi su n-grammi di caratteri (tolleranti a refusi, flessioni e parole
spezzate), con pesi TF-IDF. Le parole di contesto (tribunale, PCT, avvocato, città…) non pesano. La ricerca non decide mai
da sola: propone le scelte quando le regole tacciono o sono in parità.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from .normalizzazione import normalizza_richiesta
from .norme import piano

_CONTESTO = re.compile(r"\b(?:tribunale|giudice|corte|pct|telematic\w*|deposit\w*|avvocat\w*|cliente|clienti|studio|collega|"
                       r"assist\w*|signor\w*|dottor\w*|oggi|ieri|domani|mese|mesi|anno|anni|giorni|euro|via|piazza|"
                       r"il|lo|la|i|gli|le|un|una|uno|di|da|del|della|dei|delle|in|nel|nella|con|per|su|tra|fra|che|e|o|"
                       r"mi|ci|si|ti|vi|ne|non|come|cosa|quando|dove|perche|posso|possiamo|devo|dobbiamo|parere|consulenza|vorrei|sapere|"
                       r"domanda|chiedo|aiuto|fare|fatto|caso|situazione)\b")
_N = (3, 4, 5)


# Aree per le proposte: una domanda di precisazione propone solo strumenti della stessa area del più vicino.
_AREA_PREFISSI = {"pi": "lavoro", "prev": "lavoro", "lav": "lavoro", "es": "esecuzione", "mon": "esecuzione", "civ": "processo",
                  "cau": "processo", "pos": "diritti reali", "pen": "penale", "ban": "impresa", "soc": "impresa",
                  "crisi": "impresa", "priv": "impresa", "con": "contratti", "rc": "responsabilita", "suc": "successioni",
                  "dr": "diritti reali", "fam": "famiglia", "loc": "locazione", "cons": "contratti", "str": "stragiudiziale",
                  "trib": "tributario", "imm": "amministrativo", "amm": "amministrativo", "cds": "sanzioni"}
_AREA_REGOLE = {
    **dict.fromkeys(("opposizione_precetto", "termini_precetto", "pignoramento_terzi", "ricerca_beni", "opposizione_atti_esecutivi",
                     "esecuzione_contro_pa", "decreto_ingiuntivo", "notifica_decreto_ingiuntivo", "opposizione_decreto_ingiuntivo"),
                    "esecuzione"),
    **dict.fromkeys(("sfratto_morosita", "sfratto_finita_locazione", "rilascio", "negoziazione_locazione_inadatta",
                     "procedibilita_locazione", "restituzione_canone_non_registrato", "sanatoria_morosita", "opposizione_convalida",
                     "opposizione_sfratto_commerciale", "causa_locazione"), "locazione"),
    **dict.fromkeys(("sequestro_conservativo", "sequestro_ante_causam", "comparsa_risposta", "rito_semplificato",
                     "competenza_pagamento", "negoziazione_obbligatoria", "mediazione_obbligatoria"), "processo"),
    **dict.fromkeys(("garanzia_conformita", "caparra_confirmatoria", "recesso_contratto", "vizi_appalto", "consumatore",
                     "diffida_commerciale", "diffida_messa_mora", "diffida_1454"), "contratti"),
    **dict.fromkeys(("disconoscimento_paternita", "separazione_giudiziale", "divorzio_tempi", "figlio_maggiorenne",
                     "modifica_condizioni", "negoziazione_familiare", "ordini_protezione"), "famiglia"),
    "chiamato_nel_possesso": "successioni", "lite_condominio": "diritti reali", "impugnazione_delibera": "diritti reali",
    "sinistro_stradale": "responsabilita",
    **dict.fromkeys(("impugnazione_licenziamento", "crediti_lavoro", "competenza_lavoro", "appello_lavoro",
                     "ricorso_dipendente_pubblico"), "lavoro"),
    **dict.fromkeys(("ricorso_tar", "motivi_aggiunti", "appalti_120", "accesso_atti", "silenzio", "ottemperanza",
                     "permesso_soggiorno", "ricorso_straordinario"), "amministrativo"),
    **dict.fromkeys(("ordinanza_ingiunzione", "opposizione_verbale_cds"), "sanzioni"),
    **dict.fromkeys(("ricorso_tributario", "reclamo_mediazione_tributaria", "sospensione_tributaria", "appello_tributario"),
                    "tributario"),
    **dict.fromkeys(("termine_querela", "impugnazione_penale"), "penale"),
}


def area(regola: str) -> str:
    return _AREA_REGOLE.get(regola) or _AREA_PREFISSI.get(regola.split("_", 1)[0], "altro")


@dataclass(frozen=True)
class Voce:
    regola: str
    nome: str
    lato: str | None
    testo: str


def _testo(t: str) -> str:
    t = piano(t)
    t = re.sub(r"\d+", " ", t)
    return " ".join(_CONTESTO.sub(" ", t).split())


def _ngrammi(t: str) -> Counter:
    c: Counter = Counter()
    for parola in t.split():
        w = f" {parola} "
        for n in _N:
            for i in range(max(1, len(w) - n + 1)):
                c[w[i:i + n]] += 1
    return c


@lru_cache(maxsize=1)
def voci() -> tuple[Voce, ...]:
    from .fattispecie import REGOLE

    nomi_attivi = {r[0] for r in REGOLE}
    out: list[Voce] = []
    try:
        from .fattispecie.significato_regole import NOMI, SIGNIFICATO

        for regola, (lato, sinonimi, situazioni) in SIGNIFICATO.items():
            out.append(Voce(regola, NOMI.get(regola, regola), lato, " ".join([NOMI.get(regola, ""), *sinonimi, *situazioni])))
    except ImportError:
        pass
    try:
        from .fattispecie.materie import indice_significato

        for x in indice_significato():
            out.append(Voce(x["regola"], x["nome"], x["lato"], " ".join([x["nome"], *x["sinonimi"], *x["situazioni"]])))
    except ImportError:
        pass
    return tuple(v for v in out if v.regola in nomi_attivi)


@lru_cache(maxsize=1)
def _indice() -> tuple[dict[str, float], list[tuple[Voce, dict[str, float], float]]]:
    documenti = [(v, _ngrammi(_testo(v.testo))) for v in voci()]
    df: Counter = Counter()
    for _, c in documenti:
        df.update(c.keys())
    n = max(len(documenti), 1)
    idf = {g: math.log((1 + n) / (1 + d)) + 1 for g, d in df.items()}
    vettori = []
    for v, c in documenti:
        w = {g: (1 + math.log(f)) * idf[g] for g, f in c.items()}
        vettori.append((v, w, math.sqrt(sum(x * x for x in w.values())) or 1.0))
    return idf, vettori


def cerca(domanda: str, k: int = 4) -> list[tuple[Voce, float]]:
    """Le k regole più vicine per significato, con la somiglianza del coseno (0-1)."""
    idf, vettori = _indice()
    c = _ngrammi(_testo(normalizza_richiesta(domanda)))
    q = {g: (1 + math.log(f)) * idf.get(g, 0.0) for g, f in c.items() if g in idf}
    nq = math.sqrt(sum(x * x for x in q.values())) or 1.0
    punteggi = []
    for v, w, nw in vettori:
        s = sum(x * w.get(g, 0.0) for g, x in q.items()) / (nq * nw)
        punteggi.append((v, s))
    punteggi.sort(key=lambda vs: vs[1], reverse=True)
    return punteggi[:k]


_STRUMENTO = re.compile(r"\(strumento:\s*([^)]+)\)\s*$")


def strumento_indicato(domanda: str) -> str | None:
    """La regola scelta dall'avvocato fra le proposte («… (strumento: nome)»), se c'è."""
    m = _STRUMENTO.search(domanda.strip())
    if not m:
        return None
    nome = piano(m.group(1))
    return next((v.regola for v in voci() if piano(v.nome) == nome), None)
