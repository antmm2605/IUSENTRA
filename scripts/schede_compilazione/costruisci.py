"""Genera e verifica le schede di compilazione in ``pct/template_atti_schede/``.

Uso: python -m scripts.schede_compilazione.costruisci --db <codici_leggi.sqlite> [--controlla]

Le specifiche per materia stanno nei moduli di questa cartella (``GRUPPI``). Ogni scheda viene verificata:
modelli esistenti nel catalogo e coperti da una sola scheda, fonti ammesse, ogni articolo citato presente
nell'archivio «Codici e leggi» (``Lex fonti: <atto>``). Con ``--controlla`` non scrive nulla.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
CARTELLA = RADICE / "pct" / "template_atti_schede"
CATALOGO = RADICE / "pct" / "template_atti_catalogo_data" / "catalogo_master.json"
GRUPPI = ["civile_ordinario", "monitorio", "cautelare", "giudice_pace"]
FONTI = {"database", "archivio_letture", "documento", "calcolo", "avvocato", "lex"}
VERSIONE = "2026-10-19.2"
PRINCIPIO = ("I dati che il gestionale conosce li compila il software; Lex scrive le parti narrative solo con fatti "
             "del fascicolo e norme della biblioteca, e chiede all’avvocato solo ciò che manca.")


def scheda(id, titolo, template, base, campi, scrive_lex, astensione, modelli_compilatore=()) -> dict:
    from scripts.schede_compilazione.comuni import _norme
    return {"id": id, "titolo": titolo, "template": list(template), "base_normativa": _norme(base), "campi": campi,
            "scrive_lex": [{"blocco": b, "compito": c} for b, c in scrive_lex], "astensione": list(astensione),
            "versione": VERSIONE, "principio": PRINCIPIO, "modelli_compilatore": list(modelli_compilatore)}


def _articoli(db: Path) -> dict[str, set[str]]:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out: dict[str, set[str]] = {}
    for col, art in c.execute("SELECT d.collection_name, a.article_number FROM normative_articles a "
                              "JOIN normative_documents d ON d.id = a.document_id"):
        out.setdefault(col.removeprefix("Lex fonti: "), set()).add(art)
    return out


def raccogli() -> tuple[list[dict], dict[str, list[str]]]:
    nuove, estensioni = [], {}
    for nome in GRUPPI:
        mod = importlib.import_module(f"scripts.schede_compilazione.{nome}")
        nuove += mod.SCHEDE
        for sid, extra in getattr(mod, "ESTENSIONI", {}).items():
            estensioni.setdefault(sid, []).extend(extra)
    return nuove, estensioni


def verifica(schede: list[dict], articoli: dict[str, set[str]]) -> list[str]:
    catalogo = {t["id"] for t in json.loads(CATALOGO.read_text(encoding="utf-8"))["template"]}
    errori, visti = [], {}
    for s in schede:
        if not (s["campi"] and s["scrive_lex"] and s["astensione"] and s["base_normativa"]):
            errori.append(f"{s['id']}: scheda incompleta")
        for t in s["template"]:
            if t not in catalogo:
                errori.append(f"{s['id']}: modello {t} non nel catalogo")
            if t in visti:
                errori.append(f"{t}: coperto da {visti[t]} e da {s['id']}")
            visti[t] = s["id"]
        nomi = [c["campo"] for c in s["campi"]]
        if len(nomi) != len(set(nomi)):
            errori.append(f"{s['id']}: campi duplicati")
        norme = list(s["base_normativa"])
        for c in s["campi"]:
            if c["fonte"]["tipo"] not in FONTI:
                errori.append(f"{s['id']}.{c['campo']}: fonte {c['fonte']['tipo']}")
            norme += c.get("norma", [])
        for n in norme:
            if n["articolo"] not in articoli.get(n["atto"], set()):
                errori.append(f"{s['id']}: {n['atto']} art. {n['articolo']} non nell'archivio")
    return errori


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--controlla", action="store_true")
    a = ap.parse_args(argv)
    nuove, estensioni = raccogli()
    esistenti = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in CARTELLA.glob("*.json")}
    generate = {k for k, v in esistenti.items() if v.get("versione") == VERSIONE}
    for k in generate:  # schede prodotte da questo script: si rigenerano da capo
        del esistenti[k]
    for s in nuove:
        if s["id"] in esistenti:
            print(f"ERRORE: {s['id']} esiste già; usa ESTENSIONI"); return 1
    for sid, extra in estensioni.items():
        esistenti[sid]["template"] = list(dict.fromkeys(esistenti[sid]["template"] + extra))
    tutte = list(esistenti.values()) + nuove
    errori = verifica(tutte, _articoli(Path(a.db)))
    for e in errori:
        print("ERRORE:", e)
    coperti = sum(len(s["template"]) for s in tutte)
    print(f"schede: {len(tutte)} (nuove {len(nuove)}), modelli coperti: {coperti}")
    if errori:
        return 1
    if not a.controlla:
        for k in generate - {s["id"] for s in nuove}:
            (CARTELLA / f"{k}.json").unlink()
        for s in tutte:
            (CARTELLA / f"{s['id']}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
