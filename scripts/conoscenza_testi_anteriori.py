"""Testi anteriori alla riforma del processo civile (d.lgs. 149/2022) per le norme citate nelle schede di istituto.

Molto contenzioso pendente segue ancora il rito anteriore: per ogni norma delle schede il cui testo vigente porta la
nota Normattiva del d.lgs. 10 ottobre 2022, n. 149, si scarica da Normattiva (Akoma Ntoso, multivigenza) il testo
vigente al 17/10/2022, il giorno prima dell'entrata in vigore del decreto, e lo si registra in
``lex/conoscenza/dati/testi_anteriori.json`` con URL, data di vigenza e impronta. La decorrenza del testo nuovo non si
presume: si riporta la nota di aggiornamento letta nel testo vigente dell'articolo. Un articolo che al 17/10/2022 non
esisteva (introdotto dalla riforma) si registra come tale.

Non si importa nella biblioteca di consultazione: lì l'edizione più recente sostituisce le precedenti e un testo
del 2022 prenderebbe il posto di quello vigente.

Uso: python scripts/conoscenza_testi_anteriori.py [--elenco]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))
os.environ.setdefault("LEX_HARNESS_ARCHIVIO_VIVO", "0")

VIGENZA = "20221017"
RIFORMA = re.compile(r"D\.\s?Lgs\.\s*10 ottobre 2022,\s*n\.\s*149", re.I)
NOTA = re.compile(r"AGGIORNAMENTO \(\d+\)\s*Il D\.\s?Lgs\.\s*10 ottobre 2022,\s*n\.\s*149[^-]{0,900}", re.I)
USCITA = RADICE / "lex" / "conoscenza" / "dati" / "testi_anteriori.json"


def norme_toccate() -> dict[str, dict]:
    from lex.conoscenza.consultazione import schede
    from lex.harness.norme import NORME, testo_norma

    uso: dict[str, set] = defaultdict(set)
    for s in schede():
        for f in s["fonti"]:
            if f["tipo"] == "norma":
                uso[f["chiave"]].add(s["id"])
    out = {}
    for k in sorted(uso):
        t = testo_norma(k)
        if t is None or not RIFORMA.search(t.testo):
            continue
        urn = re.search(r"(urn:nir:[^~]+)~art", t.url or "")
        note = sorted({" ".join(m.group(0).split()) for m in NOTA.finditer(t.testo)})
        out[k] = {"citazione": NORME[k].citazione, "urn": urn.group(1) if urn else "", "url_vigente": t.url,
                  "decorrenza_letta": note, "schede": sorted(uso[k])}
    return out


def _numero(chiave: str) -> str:
    return chiave.split(":", 1)[1].replace(".", "").lower()


def acquisisci(norme: dict[str, dict]) -> dict:
    from lex.normativa.biblioteca.fabbisogno import norm_articolo
    from lex.normativa.biblioteca.normattiva_akn import converti, nuovo_opener, scarica

    opener = nuovo_opener()
    per_atto: dict[str, list[str]] = defaultdict(list)
    for k, v in norme.items():
        per_atto[v["urn"]].append(k)
    registrate, esiti = {}, []
    for urn, chiavi in per_atto.items():
        if not urn:
            esiti.append({"chiavi": chiavi, "esito": "URN non deducibile dall'URL Normattiva"})
            continue
        try:
            atto = scarica(urn, VIGENZA, opener=opener, timeout=180)
            righe = converti(atto, chiavi[0].split(":")[0], dt.date.today().isoformat())
        except Exception as exc:  # noqa: BLE001 - l'esito si registra e si prosegue con gli altri atti
            esiti.append({"urn": urn, "chiavi": chiavi, "esito": f"non scaricato: {type(exc).__name__}: {str(exc)[:160]}"})
            continue
        articoli = {norm_articolo(str(r.get("articolo") or "")).replace(".", "").lower(): r for r in righe}
        for k in chiavi:
            r = articoli.get(_numero(k))
            base = {"citazione": norme[k]["citazione"], "vigente_al": f"{VIGENZA[6:]}/{VIGENZA[4:6]}/{VIGENZA[:4]}",
                    "urn": urn, "decorrenza_letta": norme[k]["decorrenza_letta"], "schede": norme[k]["schede"],
                    "sha256_akn": atto.sha256_xml}
            if r is None or not str(r.get("testo") or "").strip():
                registrate[k] = {**base, "stato": "assente al 17/10/2022 (articolo introdotto dalla riforma)"}
            else:
                testo = " ".join(str(r["testo"]).split())
                registrate[k] = {**base, "stato": "testo anteriore", "testo": testo,
                                 "versione": hashlib.sha256(testo.encode()).hexdigest()[:16],
                                 "url": f"https://www.normattiva.it/uri-res/N2Ls?{urn}~art{_numero(k)}!vig=2022-10-17"}
        esiti.append({"urn": urn, "chiavi": chiavi, "esito": "scaricato", "articoli_atto": len(righe)})
    return {"metodo": __doc__.split("\n\n")[1].replace("\n", " "), "vigenza": VIGENZA,
            "acquisito_il": dt.date.today().isoformat(), "esiti": esiti, "norme": registrate}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--elenco", action="store_true")
    a = ap.parse_args()
    norme = norme_toccate()
    per = defaultdict(list)
    for k in norme:
        per[k.split(":")[0]].append(k.split(":")[1])
    print(f"{len(norme)} norme delle schede con la nota del d.lgs. 149/2022")
    for atto, v in per.items():
        print(f"  {atto}: {len(v)} — {', '.join(v)}")
    if a.elenco:
        return 0
    dati = acquisisci(norme)
    USCITA.write_text(json.dumps(dati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    conta = defaultdict(int)
    for v in dati["norme"].values():
        conta[v["stato"]] += 1
    print(json.dumps({"registrate": len(dati["norme"]), "per_stato": conta,
                      "atti_non_scaricati": [e for e in dati["esiti"] if e["esito"] != "scaricato"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
