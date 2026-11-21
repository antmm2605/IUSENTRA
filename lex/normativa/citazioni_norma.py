"""Come si cita una norma nelle pronunce: frasi FTS5 per cercarle negli archivi della giurisprudenza.

Una pronuncia che applica una norma la cita con le sue parole («art. 2043 c.c.», «art. 2043 cod. civ.»,
«dell'art. 2043 del codice civile»; per le leggi articolo, numero e anno vicini). Cercare la citazione come frase
risponde in centesimi di secondo anche su 8,6 GB; la domanda in testo libero con ordinamento bm25 superava i 110 s.
"""
from __future__ import annotations

import re

_CODICI = {
    "cc": ("{n} c c", "{n} cod civ", "{n} del codice civile", "{n} codice civile"),
    "cpc": ("{n} c p c", "{n} cod proc civ", "{n} del codice di procedura civile", "{n} codice di procedura civile"),
    "cp": ("{n} c p", "{n} cod pen", "{n} del codice penale", "{n} codice penale"),
    "cpp": ("{n} c p p", "{n} cod proc pen", "{n} del codice di procedura penale"),
    "cost": ("{n} cost", "{n} della costituzione"),
    "cpa": ("{n} c p a", "{n} cod proc amm", "{n} del codice del processo amministrativo"),
}
# «155 c.p.» è anche l'inizio di «155 c.p.c.» e «155 c.p.p.»: si escludono le pronunce che citano gli altri codici.
_ESCLUSI = {"cp": ("{n} c p c", "{n} c p p", "{n} c p a")}
_SIGLE_LEGGE = {"l": "legge", "dl": "decreto legge", "dlgs": "decreto legislativo", "dpr": "presidente della repubblica",
                "rd": "regio decreto"}


def _frase(testo: str) -> str:
    return '"' + " ".join(re.findall(r"[0-9a-zà-ù]+", testo.lower())) + '"'


def interrogazioni(chiave: str, estremi: str = "") -> list[str]:
    prefisso, articolo = chiave.split(":", 1)
    numero = re.sub(r"([0-9]+)([a-z]+)", r"\1 \2", articolo)  # 66bis -> «66 bis»
    if prefisso in _CODICI:
        esclusi = " ".join(f"NOT {_frase(e.format(n=numero))}" for e in _ESCLUSI.get(prefisso, ()))
        return [f"{_frase(v.format(n=numero))} {esclusi}".strip() for v in _CODICI[prefisso]]
    legge = re.match(r"(l|dl|dlgs|dpr|rd)(\d+)$", prefisso)
    anno = re.search(r"/(\d{4})", estremi or "")
    if not legge or not anno:
        return []
    # «art. 13 del d.P.R. n. 115 del 2002», «art. 13 d.P.R. 115/2002»: articolo, numero e anno vicini.
    return [f'NEAR({_frase("art " + numero)} "{legge.group(2)}" "{anno.group(1)}", 8)']


