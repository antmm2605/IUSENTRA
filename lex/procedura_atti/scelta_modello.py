"""Proposta del modello d'atto (scheda) a partire dalla richiesta e dai fatti: elenco ordinato, decide l'avvocato.

Ogni scheda e' descritta dal suo titolo, dai motivi della base normativa e dalle voci del catalogo dei modelli
collegate (titolo, procedimento, sottobranca). Punteggio lessicale con lo stesso trattamento del testo della ricerca
normativa (stemming italiano, stopword) e peso inverso alla frequenza dei termini fra le schede. E' una proposta:
la scelta resta all'avvocato e rientra nella scheda decisa.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE
from lex.ricerca_giuridica.testo import termini_indice

CATALOGO = Path(__file__).resolve().parents[2] / "pct" / "template_atti_catalogo_data"


@lru_cache(maxsize=1)
def _catalogo() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(CATALOGO.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for t in d.get("template") or []:
            if isinstance(t, dict) and t.get("id"):
                out[str(t["id"])] = t
    return out


@lru_cache(maxsize=4)
def _indice(cartella: str) -> tuple[dict[str, Counter], dict[str, float], dict[str, str]]:
    docs: dict[str, Counter] = {}
    titoli: dict[str, str] = {}
    cat = _catalogo()
    for f in sorted(Path(cartella).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sid = str(d.get("id") or f.stem)
        parti = [str(d.get("titolo") or "")] * 3
        parti += [str(r.get("perche") or "") for r in d.get("base_normativa") or []]
        for tid in d.get("template") or []:
            t = cat.get(str(tid)) or {}
            parti += [str(t.get(k) or "") for k in ("titolo", "procedimento", "sottobranca", "macro_area")]
        docs[sid] = Counter(termini_indice(" ".join(parti)))
        titoli[sid] = str(d.get("titolo") or "")
    df = Counter(t for c in docs.values() for t in c)
    idf = {t: math.log(1 + len(docs) / n) for t, n in df.items()}
    return docs, idf, titoli


def proponi_modelli(richiesta: str, fatti: str = "", *, limite: int = 5, cartella: Path = CARTELLA_SCHEDE) -> list[dict]:
    docs, idf, titoli = _indice(str(cartella))
    q = Counter(termini_indice(richiesta))
    for t, n in Counter(termini_indice(fatti)).items():
        q[t] += 0.3 * n
    punteggi = []
    for sid, c in docs.items():
        s = sum(w * idf.get(t, 0.0) * (1 + math.log(c[t])) for t, w in q.items() if t in c)
        if s > 0:
            punteggi.append((s, sid))
    punteggi.sort(reverse=True)
    return [{"scheda": sid, "titolo": titoli[sid], "punteggio": round(s, 2)} for s, sid in punteggi[:limite]]
