"""Banco di prova: quale classificatore cataloga meglio i documenti, sugli stessi documenti mai visti.

Uso (dopo `valuta.py` sul modello di base e su quello addestrato):
    python banco.py --pacchetto ~/iusentra-addestramento/pacchetto \
        --risultati qwen_base=~/iusentra-addestramento/misura-base \
        --risultati qwen_addestrato=~/iusentra-addestramento/misura \
        --uscita ~/iusentra-addestramento/banco

Confronta, gruppo per gruppo:
- `regole`: la proposta delle regole del catalogo (sui gruppi «verifica» e «banco_inventati» è il riferimento
  stesso, quindi lì misura solo quanto gli altri le riproducono);
- `spark`: la seconda lettura di Lex già registrata nel catalogo, sui soli documenti che ha letto;
- `lineare`: il classificatore piccolo del server (TF-IDF e regressione logistica), addestrato qui sugli stessi
  esempi di Qwen;
- ogni modello passato con `--risultati` (le `predizioni.jsonl` di `valuta.py`).

Gruppi decisivi: `verifica_decisioni` (disaccordi decisi con `--decisioni`) e `verifica_avvocato` (decisioni
dell'avvocato nel catalogo). Oltre all'accuratezza complessiva si riporta la
media per voce, che non lascia nascondere le voci rare dietro le frequenti. Esce solo con conteggi.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dati import applica_decisioni, gruppo, leggi_pacchetto

GRUPPI = ("verifica_decisioni", "verifica_avvocato", "verifica", "banco_inventati")


def _classificatore_lineare():
    """Il modulo del server, caricato dal file: nessun pacchetto del prodotto da importare sul PC."""
    percorso = Path(__file__).resolve().parents[2] / "pct" / "document_intelligence" / "verita" / "classificatore.py"
    spec = importlib.util.spec_from_file_location("classificatore_catalogo", percorso)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # le dataclass del modulo cercano il proprio modulo fra quelli caricati
    spec.loader.exec_module(modulo)
    return modulo


def punteggio(righe: list[dict], scelte: dict[str, str]) -> dict:
    """Giuste su valutate e media per voce, solo sulle righe che il classificatore ha valutato."""
    per_voce: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    giuste = valutate = 0
    for riga in righe:
        scelta = scelte.get(riga["id"])
        if scelta is None:
            continue
        valutate += 1
        esatto = int(scelta == riga["voce"])
        giuste += esatto
        per_voce[riga["voce"]][0] += esatto
        per_voce[riga["voce"]][1] += 1
    media_voci = sum(g / n for g, n in per_voce.values()) / len(per_voce) if per_voce else 0.0
    return {"valutate": valutate, "giuste": giuste,
            "accuratezza": round(100 * giuste / valutate, 1) if valutate else None,
            "media_per_voce": round(100 * media_voci, 1) if per_voce else None, "voci": len(per_voce)}


def tabella(risultati: dict[str, dict[str, dict]]) -> str:
    righe = ["| Classificatore | " + " | ".join(GRUPPI) + " |", "|---|" + "---|" * len(GRUPPI)]
    for nome, gruppi in risultati.items():
        celle = []
        for g in GRUPPI:
            p = gruppi.get(g) or {}
            celle.append("—" if not p.get("valutate") else
                         f"{p['accuratezza']}% ({p['giuste']}/{p['valutate']}), per voce {p['media_per_voce']}%")
        righe.append(f"| {nome} | " + " | ".join(celle) + " |")
    return "\n".join(righe)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pacchetto", type=Path, required=True)
    parser.add_argument("--risultati", action="append", default=[], help="nome=cartella con predizioni.jsonl")
    parser.add_argument("--uscita", type=Path, required=True)
    parser.add_argument("--decisioni", type=Path, help="JSONL delle decisioni sui disaccordi (verifica decisiva)")
    args = parser.parse_args()

    _prefisso, righe, manifesto = leggi_pacchetto(args.pacchetto)
    righe = applica_decisioni(righe, args.decisioni)
    prova = {g: gruppo(righe, g) for g in GRUPPI}
    scelte: dict[str, dict[str, str]] = {
        "regole": {r["id"]: r.get("voce_regole", "") for g in GRUPPI for r in prova[g]},
        "spark": {r["id"]: r["voce_spark"] for g in GRUPPI for r in prova[g] if r.get("voce_spark")},
    }
    addestramento = gruppo(righe, "addestramento")
    lineare = _classificatore_lineare()
    modello = lineare.addestra([r["testo"] for r in addestramento], [r["voce"] for r in addestramento],
                               massimo_parole=12000)
    da_valutare = [r for g in GRUPPI for r in prova[g]]
    scelte["lineare"] = {r["id"]: voce for r, (voce, _p) in zip(da_valutare, modello.predici([r["testo"] for r in da_valutare]))}
    for voce in args.risultati:
        nome, _, cartella = voce.partition("=")
        file = Path(cartella).expanduser() / "predizioni.jsonl"
        scelte[nome] = {p["id"]: p["etichetta"] for p in map(json.loads, file.read_text(encoding="utf-8").splitlines()) if p}

    risultati = {nome: {g: punteggio(prova[g], s) for g in GRUPPI} for nome, s in scelte.items()}
    args.uscita.mkdir(parents=True, exist_ok=True)
    (args.uscita / "banco.json").write_text(json.dumps({"pacchetto": manifesto, "risultati": risultati},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    testo = tabella(risultati)
    (args.uscita / "banco.md").write_text(testo + "\n", encoding="utf-8")
    print(testo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
