"""Pronunce che citano ogni norma, dagli archivi della giurisprudenza in sola lettura (fuori dalle richieste).

Perché non bastava ``scripts/lex_harness_giurisprudenza.py``: cercava la domanda in testo libero («art. 2043 c.c.
Risarcimento per fatto illecito») con radici, OR e ordinamento bm25 su 8,6 GB di SentenzeWeb: oltre 110 s per
norma. Una pronuncia che applica una norma la cita con le sue parole: qui si cerca la CITAZIONE come frase FTS5
(«2043 c.c.», «2043 cod. civ.», «2043 del codice civile»; per le leggi numero, anno e articolo vicini), che sui
due archivi risponde in centesimi di secondo, e si leggono solo le righe scelte per chiave primaria.

Si scrivono solo gli estremi e l'indirizzo ufficiale (niente testo delle pronunce). Le pronunce scelte sono le più
recenti dell'archivio che contengono la citazione: la scheda lo dichiara.

Uso: python scripts/sentenze_per_norma.py --cassazione DB --consulta DB [--norme harness|codici] [--uscita FILE]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

PER_NORMA = 3
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


def _connetti(percorso: str) -> sqlite3.Connection:
    uri = Path(percorso).resolve().as_uri()
    try:
        conn = sqlite3.connect(uri + "?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        conn = sqlite3.connect(uri + "?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def metadati(conn: sqlite3.Connection) -> dict[int, tuple]:
    """Estremi di tutte le pronunce, letti una volta da un indice che li contiene (senza toccare i testi).

    Leggere una riga per chiave primaria costa molto: l'URL viene dopo il testo integrale e SQLite deve
    attraversarne le pagine. Gli estremi per scegliere si prendono dall'indice; l'URL solo per le scelte.
    """
    colonne = "id, organo_giudicante, sezione, numero_sentenza, anno_sentenza, data_deposito"
    for sql in (f"SELECT {colonne} FROM sentenze INDEXED BY idx_sentenze_web_acquisizione_temporaneo",
                f"SELECT {colonne} FROM sentenze"):
        try:
            return {int(r[0]): tuple(r[1:]) for r in conn.execute(sql)}
        except sqlite3.OperationalError:
            continue
    return {}


def pronunce(conn: sqlite3.Connection, archivio: str, domande: list[str], estremi: dict[int, tuple],
             limite: int = PER_NORMA) -> list[dict]:
    ids: set[int] = set()
    for domanda in domande:
        try:
            ids.update(r[0] for r in conn.execute("SELECT rowid FROM sentenze_fts WHERE sentenze_fts MATCH ?", (domanda,)))
        except sqlite3.OperationalError:
            continue
    candidate = [(i, estremi[i]) for i in ids if i in estremi and estremi[i][2] and estremi[i][3]]
    candidate.sort(key=lambda v: (str(v[1][4] or ""), str(v[1][3])), reverse=True)
    uscita = []
    for ident, (organo, sezione, numero, anno, data) in candidate[:limite]:
        url = conn.execute("SELECT url_pagina_ufficiale, url_pdf_ufficiale FROM sentenze WHERE id=?", (ident,)).fetchone()
        uscita.append({"archivio": archivio, "organo": str(organo or ""), "sezione": str(sezione or ""),
                       "numero": str(numero).lstrip("0") or "0", "anno": str(anno), "data": str(data or ""),
                       "url": str((url[0] or url[1]) if url else ""), "massima": ""})
    return uscita


def elenco_norme(quali: str) -> list[tuple[str, str]]:
    from lex.harness.norme import NORME

    norme = [(k, n.estremi) for k, n in NORME.items()]
    if quali == "harness":
        return norme
    extra = [(f"cost:{n}", "") for n in range(1, 140)]
    return norme + [v for v in extra if v[0] not in dict(norme)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cassazione", required=True)
    ap.add_argument("--consulta", required=True)
    ap.add_argument("--norme", default="harness", choices=("harness", "estese"))
    ap.add_argument("--uscita", default=str(RADICE / "lex/harness/dati/giurisprudenza_per_norma.json"))
    ap.add_argument("--pausa", type=float, default=0.2)
    args = ap.parse_args()
    archivi = [("Cassazione (SentenzeWeb)", _connetti(args.cassazione)),
               ("archivio dello studio (Consulta e fonti pubbliche)", _connetti(args.consulta))]
    estremi = {}
    for nome, conn in archivi:
        inizio = time.monotonic()
        estremi[nome] = metadati(conn)
        print(f"{nome}: {len(estremi[nome])} pronunce in {time.monotonic() - inizio:.0f} s", flush=True)
    uscita = Path(args.uscita)
    indice = json.loads(uscita.read_text(encoding="utf-8")) if uscita.is_file() else {"norme": {}}
    for chiave, estremi in elenco_norme(args.norme):
        domande = interrogazioni(chiave, estremi)
        if not domande:
            continue
        inizio = time.monotonic()
        trovate = [p for nome, conn in archivi for p in pronunce(conn, nome, domande, estremi[nome])]
        indice["norme"][chiave] = trovate
        print(f"{chiave}: {len(trovate)} pronunce in {time.monotonic() - inizio:.1f} s", flush=True)
        time.sleep(args.pausa)
    indice.update({"generato_il": date.today().strftime("%d/%m/%Y"), "archivi": [n for n, _ in archivi],
                   "metodo": "citazione della norma cercata come frase negli archivi; pronunce più recenti che la citano"})
    uscita.parent.mkdir(parents=True, exist_ok=True)
    uscita.write_text(json.dumps(indice, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(indice['norme'])} norme -> {uscita}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
