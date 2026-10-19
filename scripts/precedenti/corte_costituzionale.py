"""Pronunce e massime della Corte costituzionale (open data, CC BY-SA 3.0) armonizzate per Lex.

Uso: python scripts/precedenti/corte_costituzionale.py --raw <cartella open data> --db <codici_leggi.sqlite> --out <file.jsonl>

Fonte: https://dati.cortecostituzionale.it (pronunce e massime in JSON, testo in codifica cp1252). Per ogni
pronuncia: ECLI, data di deposito, esito letto dal dispositivo, norme oggetto riconosciute nel dispositivo e
collegate alle raccolte della biblioteca «Codici e leggi» quando l'atto è presente, massime ufficiali.
Le pronunce costituzionali non contengono dati personali da trattare oltre le iniziali già usate dalla Corte.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
from pathlib import Path

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                    "settembre", "ottobre", "novembre", "dicembre"], 1)}
CODICI = {"codice di procedura civile": "codice_procedura_civile", "codice civile": "codice_civile",
          "codice di procedura penale": "codice_procedura_penale", "codice penale": "codice_penale",
          "codice della strada": "codice_strada", "codice del processo amministrativo": "codice_processo_amministrativo"}
TIPI = {"legge": "legge", "decreto legislativo": "decreto.legislativo", "decreto-legge": "decreto.legge",
        "d.lgs.": "decreto.legislativo", "d.l.": "decreto.legge", "d.p.r.": "decreto.del.presidente.della.repubblica", "l.": "legge",
        "decreto del presidente della repubblica": "decreto.del.presidente.della.repubblica", "regio decreto": "regio.decreto"}
RIF = re.compile(r"(?:artt?\.)\s*([\d\-a-z, e]+?)(?:,\s*comma[^,]*)?,?\s+(?:del(?:la|l')?\s+)"
                 r"(codice di procedura civile|codice civile|codice di procedura penale|codice penale|codice della strada|"
                 r"codice del processo amministrativo|legge|decreto legislativo|decreto-legge|decreto del presidente della repubblica|regio decreto|d\.lgs\.|d\.l\.|d\.P\.R\.|l\.)"
                 r"(?:\s+(\d{1,2})\s+(" + "|".join(MESI) + r")\s+(\d{4}),\s*n\.\s*(\d+))?", re.I)
ESITI = [("illegittimit", "illegittimità"), ("non fondat", "non fondata"), ("inammissibil", "inammissibile"),
         ("manifestamente infondat", "manifestamente infondata"), ("estint", "estinto")]


def _carica(cartella: Path, schema: str) -> list[dict]:
    righe = []
    for f in sorted(cartella.rglob(schema)):
        dati = json.loads(f.read_bytes().decode("cp1252"))
        righe += dati if isinstance(dati, list) else next(iter(dati.values()))
    return righe


def _indice_biblioteca(db: Path) -> dict[tuple[str, str, str], str]:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    indice = {}
    try:
        for col, urn in c.execute("SELECT collection_name, urn FROM normative_documents"):
            m = re.match(r"urn:nir:stato:([a-z.]+):(\d{4}-\d{2}-\d{2});(\d+)", urn or "")
            if m:
                indice[m.groups()] = col.removeprefix("Lex fonti: ")
    finally:
        c.close()
    return indice


def _pulisci(testo: str) -> str:
    return " ".join(html.unescape(testo or "").replace("&#13;", " ").split())


def norme_oggetto(dispositivo: str, indice: dict) -> list[dict]:
    out = []
    for m in RIF.finditer(dispositivo):
        articoli = [a for a in re.split(r",|\se\s", m.group(1)) if re.match(r"\s*\d+", a)]
        tipo = m.group(2).lower()
        if m.group(6) == "87" and m.group(5) == "1953":
            continue  # art. 27 L. 87/1953: norma sul giudizio costituzionale, non oggetto della questione
        if tipo in CODICI:
            chiave = CODICI[tipo]
        elif m.group(6):
            data = f"{m.group(5)}-{MESI[m.group(4).lower()]:02d}-{int(m.group(3)):02d}"
            chiave = indice.get((TIPI[tipo], data, m.group(6)))
        else:
            continue
        for a in articoli:
            art = re.sub(r"\s|-", "", a.strip())
            voce = {"atto": chiave, "articolo": art} if chiave else {"atto_non_in_biblioteca": f"{tipo} n. {m.group(6)}/{m.group(5)}", "articolo": art}
            if voce not in out:
                out.append(voce)
    return out


def esito(dispositivo: str) -> list[str]:
    testo = dispositivo.lower()
    return [nome for chiave, nome in ESITI if chiave in testo]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    raw = Path(a.raw)
    indice = _indice_biblioteca(Path(a.db))
    massime = {(m["anno_pronuncia"], m["numero_pronuncia"]): m for m in _carica(raw, "Cc_OpenData_Massime_*.json")}
    n = collegate = 0
    with open(a.out, "w", encoding="utf-8") as f:
        for p in _carica(raw, "Cc_Opendata_Pronunce_*.json"):
            disp = _pulisci(p.get("dispositivo", ""))
            norme = norme_oggetto(disp, indice)
            m = massime.get((p["anno_pronuncia"], p["numero_pronuncia"]), {})
            voce = {"ecli": p.get("ecli"), "anno": p["anno_pronuncia"], "numero": p["numero_pronuncia"],
                    "tipo": {"S": "sentenza", "O": "ordinanza"}.get(p.get("tipologia_pronuncia"), p.get("tipologia_pronuncia")),
                    "data_deposito": p.get("data_deposito"), "giudizio": m.get("tipologia_giudizio", ""),
                    "esito": esito(disp), "norme_oggetto": norme, "dispositivo": disp,
                    "massime": [{"titolo": _pulisci(x.get("titolo")), "testo": _pulisci(x.get("testo"))} for x in m.get("massime", [])],
                    "fonte": "Corte costituzionale, open data (CC BY-SA 3.0)"}
            f.write(json.dumps(voce, ensure_ascii=False) + "\n")
            n += 1
            collegate += any("atto" in x for x in norme)
    print(f"pronunce: {n}, con norme collegate alla biblioteca: {collegate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
