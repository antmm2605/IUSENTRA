"""Sentenze della giustizia amministrativa (OpenGA, open data) armonizzate per Lex e per la strategia.

Uso: python scripts/precedenti/openga.py --csv <cartella con i CSV *-sentenze-*.csv> --out <cartella>

Fonte: https://openga.giustizia-amministrativa.it (CKAN; dati pubblicati senza licenza espressa, quindi aperti
ai sensi dell'art. 52, comma 2, D.Lgs. 82/2005). I file contengono metadati, non il testo delle sentenze:
sede, sezione, numero, date, rito, oggetto del ricorso ed esito. Produce:
  sentenze_ga.jsonl  una riga per sentenza, senza doppioni, esito normalizzato, oggetto ripulito da dati personali
  esiti_ga.json      esiti per rito (e per sede), base per indicare all'avvocato come vanno ricorsi dello stesso tipo
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10**8)
CATEGORIE = [("PARTE ACCOGLIE", "accolto in parte"), ("ACCOGLIE IN PARTE", "accolto in parte"),
             ("ACCOLTO IN PARTE", "accolto in parte"), ("PARZIALMENTE", "accolto in parte"),
             ("ACCOLT", "accolto"), ("ACCOGLIE", "accolto"),
             ("RESPINGE", "respinto"), ("RIGETTA", "respinto"), ("INAMMISSIBIL", "inammissibile"),
             ("IRRICEVIBIL", "irricevibile"), ("IMPROCEDIBIL", "improcedibile"), ("CESSATA MATERIA", "cessata materia del contendere"),
             ("DIFETTO DI GIURISDIZIONE", "difetto di giurisdizione"), ("ESTINT", "estinto"), ("RINUNZIA", "estinto"),
             ("COMMISSARIO AD ACTA", "commissario ad acta"), ("INCOMPETENZA", "incompetenza")]
PERSONALI = [(re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"), "[codice fiscale]"),
             (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[email]"),
             (re.compile(r"\b(?:\+39\s?)?\d{3}[\s.]?\d{6,7}\b"), "[telefono]"),
             (re.compile(r"\b(SIG(?:\.|NOR)?A?|SIG\.RA|DOTT\.?(?:SSA)?|AVV\.?|ING\.?|GEOM\.?)\s+[A-ZÀ-Ü'][A-ZÀ-Ü' ]{2,40}", re.I), r"\1 [nome]")]


def categoria(esito: str) -> str:
    e = (esito or "").upper()
    return next((nome for chiave, nome in CATEGORIE if chiave in e), "altro")


def ripulisci(oggetto: str) -> str:
    testo = " ".join((oggetto or "").split())
    for regex, sost in PERSONALI:
        testo = regex.sub(sost, testo)
    return testo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    visti, righe = set(), 0
    per_rito: dict[str, Counter] = defaultdict(Counter)
    per_sede_rito: dict[str, Counter] = defaultdict(Counter)
    with open(out / "sentenze_ga.jsonl", "w", encoding="utf-8") as f:
        for path in sorted(Path(a.csv).glob("*-sentenze-*.csv")):
            with open(path, encoding="utf-8", errors="replace") as h:
                for x in csv.DictReader(h):
                    chiave = (x.get("CODICE_SEDE"), x.get("NUMERO_PROVVEDIMENTO"))
                    if chiave in visti or not x.get("NUMERO_PROVVEDIMENTO"):
                        continue
                    visti.add(chiave)
                    cat = categoria(x.get("ESITO_PROVVEDIMENTO", ""))
                    rito = (x.get("TIPO_RICORSO") or "non indicato").strip()
                    voce = {"sede": x.get("NOME_SEDE"), "sezione": x.get("NOME_SEZIONE"), "numero": x.get("NUMERO_PROVVEDIMENTO"),
                            "ricorso": x.get("NUMERO_RICORSO"), "data_pubblicazione": x.get("DATA_PUBBLICAZIONE"),
                            "data_deposito_ricorso": x.get("DATA_DEPOSITO_RICORSO"), "rito": rito,
                            "oggetto": ripulisci(x.get("OGGETTO_RICORSO", "")), "esito": (x.get("ESITO_PROVVEDIMENTO") or "").strip(),
                            "esito_categoria": cat, "definisce": x.get("FLG_DEFINISCE") == "D",
                            "fonte": "Giustizia amministrativa, OpenGA"}
                    f.write(json.dumps(voce, ensure_ascii=False) + "\n")
                    righe += 1
                    if voce["definisce"]:
                        per_rito[rito][cat] += 1
                        per_sede_rito[f"{voce['sede']} | {rito}"][cat] += 1

    def tabella(cont: dict[str, Counter], minimo: int) -> dict:
        res = {}
        for k, c in cont.items():
            tot = sum(c.values())
            if tot >= minimo:
                res[k] = {"decisioni": tot, "esiti": dict(c.most_common()),
                          "accolto_almeno_in_parte_pct": round(100 * (c["accolto"] + c["accolto in parte"] + c["commissario ad acta"]) / tot, 1)}  # in ottemperanza la nomina del commissario presuppone l’accoglimento
        return dict(sorted(res.items(), key=lambda kv: -kv[1]["decisioni"]))

    (out / "esiti_ga.json").write_text(json.dumps({"per_rito": tabella(per_rito, 30), "per_sede_e_rito": tabella(per_sede_rito, 30)},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"sentenze: {righe}, riti: {len(per_rito)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
