"""Tratti redazionali dai ricorsi depositati, senza riutilizzare testo o dati del caso."""
from __future__ import annotations

import re
from statistics import median
from typing import Iterable

_SEZIONI = {
    "fatti": re.compile(r"^(?:in fatto|fatto|premess[oa]|premesse(?: in fatto)?)$"),
    "diritto": re.compile(r"^(?:in diritto|diritto|motivi(?: del ricorso| in diritto)?)$"),
    "conclusioni": re.compile(r"^(?:conclusioni|chiede|per questi motivi|p\s*\.?\s*q\s*\.?\s*m\.?)$"),
    "documenti": re.compile(r"^(?:documenti|indice dei documenti|produzioni(?: documentali)?|si produce|si allega)$"),
}
_FORMULE = {
    "premessa": r"\bpremesso che\b",
    "esposizione_diritto": r"\bin punto di diritto\b",
    "richiesta_al_giudice": r"\bvoglia (?:l[’']|il |la )",
    "articolazione_subordinata": r"\bin via subordinata\b",
    "richiesta_spese": r"\bcon vittoria (?:di|delle) spese\b",
}
_ELENCO = re.compile(r"^\s*(?:\d{1,2}[.)]|[a-z][)]|[•–])\s+", re.I)


def tratti_del_ricorso(testo: str) -> dict:
    righe = [r.strip() for r in testo.splitlines() if r.strip()]
    parole = re.findall(r"\b[^\W\d_]+\b", testo)
    if len(parole) < 150:
        return {}
    sezioni = []
    titoli = []
    for riga in righe:
        if len(riga) > 60:
            continue
        normalizzata = re.sub(r"^\d{1,2}[.)]\s*", "", riga).strip(" .:-–")
        for nome, schema in _SEZIONI.items():
            if nome not in sezioni and schema.fullmatch(normalizzata.casefold()):
                sezioni.append(nome)
                titoli.append(normalizzata.isupper())
                break
    if not sezioni:
        return {}
    frasi = [len(f.split()) for f in re.split(r"(?<=[.!?])\s+", testo) if len(f.split()) >= 5]
    return {
        "formule": [k for k, pattern in _FORMULE.items() if re.search(pattern, testo, re.I)],
        "struttura": sezioni,
        "titoli_in_maiuscolo": sum(titoli) > len(titoli) / 2,
        "elenchi_numerati": sum(bool(_ELENCO.match(r)) for r in righe) >= 3,
        "parole_per_frase": round(median(frasi)) if frasi else 0,
    }


def aggrega_stile(esempi: Iterable[dict]) -> dict:
    esempi = list(esempi)
    if len(esempi) < 2:
        return {}
    strutture: dict[tuple, int] = {}
    for esempio in esempi:
        pattern = tuple(esempio.get("struttura") or ())
        strutture[pattern] = strutture.get(pattern, 0) + 1
    prevalente = max(strutture, key=lambda p: (strutture[p], len(p)))
    return {
        "ricorsi_depositati_esaminati": len(esempi),
        "formule_ricorrenti": [formula for formula in _FORMULE
                               if sum(formula in (x.get("formule") or []) for x in esempi) >= 2],
        "struttura_ricorrente": list(prevalente) if strutture[prevalente] >= 2 else [],
        "titoli_in_maiuscolo": sum(bool(x.get("titoli_in_maiuscolo")) for x in esempi) > len(esempi) / 2,
        "elenchi_numerati": sum(bool(x.get("elenchi_numerati")) for x in esempi) > len(esempi) / 2,
        "parole_per_frase": round(median(x.get("parole_per_frase", 0) for x in esempi)),
    }
