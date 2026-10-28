"""Norme richieste dalle schede dei modelli d'atto e loro presenza nella biblioteca «Codici e leggi».

Le schede (``pct/template_atti_schede/*.json``) dichiarano la base normativa dell'atto e la norma di ogni campo
obbligatorio. Qui si raccolgono quei riferimenti e si controlla, nell'edizione piu' recente di ogni atto della
biblioteca (``codici_leggi.sqlite``, collezioni ``Lex fonti: <chiave>``), che atto e articolo esistano.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

CARTELLA_SCHEDE = Path(__file__).resolve().parents[3] / "pct" / "template_atti_schede"
COLLEZIONE = "Lex fonti: "


def norm_articolo(valore: str) -> str:
    v = re.sub(r"^art(?:icolo)?\.?\s*", "", str(valore or "").strip().lower())
    return re.sub(r"[\s\-]", "", v).strip(".")


@dataclass(frozen=True)
class Riferimento:
    scheda: str
    atto: str
    articolo: str
    perche: str
    origine: str  # "base_normativa" | "campo:<nome>"


def riferimenti_schede(cartella: Path = CARTELLA_SCHEDE, *, solo_scheda: str = "") -> list[Riferimento]:
    out: list[Riferimento] = []
    if solo_scheda:
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", solo_scheda):
            raise ValueError("Identificatore della scheda non valido")
        files = [Path(cartella) / (solo_scheda + ".json")]
    else:
        files = sorted(Path(cartella).glob("*.json"))
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        sid = str(d.get("id") or f.stem)
        for r in d.get("base_normativa") or []:
            out.append(Riferimento(sid, str(r["atto"]), str(r["articolo"]), str(r.get("perche") or ""), "base_normativa"))
        for c in d.get("campi") or []:
            for r in c.get("norma") or []:
                out.append(Riferimento(sid, str(r["atto"]), str(r["articolo"]), str(r.get("perche") or ""),
                                       f"campo:{c.get('campo')}"))
    return out


@dataclass
class Presenza:
    atti: dict[str, int] = field(default_factory=dict)  # chiave -> id del documento piu' recente
    articoli: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def presenza_biblioteca(db: Path, *, chiavi: set[str] | None = None) -> Presenza:
    p = Presenza()
    if not Path(db).is_file():
        return p
    with closing(sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True, timeout=10)) as conn:
        for doc_id, coll in conn.execute(
                "SELECT d.id, d.collection_name FROM normative_documents d WHERE d.collection_name LIKE ? AND d.id = ("
                "SELECT x.id FROM normative_documents x WHERE x.collection_name = d.collection_name "
                "ORDER BY x.redazione_id DESC, x.id DESC LIMIT 1)", (COLLEZIONE + "%",)):
            p.atti[coll[len(COLLEZIONE):]] = int(doc_id)
        ids = list(p.atti.items())
        inverso = {v: k for k, v in ids}
        relevant_ids=[doc_id for key,doc_id in ids if chiavi is None or key in chiavi]
        for start in range(0,len(relevant_ids),500):
            batch=relevant_ids[start:start+500]
            for doc_id, numero in conn.execute("SELECT document_id, article_number FROM normative_articles WHERE document_id IN ("+",".join("?" for _ in batch)+")",batch):
                p.articoli[inverso[doc_id]].add(norm_articolo(numero))
    return p


@dataclass
class Fabbisogno:
    atti_mancanti: dict[str, list[Riferimento]]
    articoli_mancanti: list[Riferimento]
    presenti: int
    totale: int


def calcola_fabbisogno(db: Path, riferimenti: list[Riferimento] | None = None) -> Fabbisogno:
    refs = riferimenti if riferimenti is not None else riferimenti_schede()
    pres = presenza_biblioteca(db,chiavi={r.atto for r in refs})
    atti: dict[str, list[Riferimento]] = defaultdict(list)
    articoli: list[Riferimento] = []
    presenti = 0
    for r in refs:
        if r.atto not in pres.atti:
            atti[r.atto].append(r)
        elif norm_articolo(r.articolo) not in pres.articoli[r.atto]:
            articoli.append(r)
        else:
            presenti += 1
    return Fabbisogno(dict(atti), articoli, presenti, len(refs))
