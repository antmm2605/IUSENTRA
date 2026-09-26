#!/usr/bin/env python3
"""Prove sul campo delle letture automatiche (rassegne del 25-26/09/2026).

Esegue i due banchi di `pct/collaudo_ai` e scrive i risultati in una cartella:

- PEC ostili: le regole in produzione e, per ogni modello indicato, Lex senza e
  con marcatore di provenienza nel contesto (Lasso, «The Provenance Tax»);
- pagine anonimizzate: il cancello di ancoraggio sul lettore simulato e sui
  valori proposti da ogni modello (Reducto, valutazione per stadi).

Uso (Ollama locale, temperatura 0):

    python scripts/collaudo_ai.py --modelli qwen3:4b maternion/spark-x2.5:4b --uscita artifacts/collaudo-ai

Senza --modelli misura solo le regole e il lettore simulato (nessun modello).
I risultati di ogni lettura si aggiungono a `letture.jsonl` appena pronti: una
prova interrotta resta leggibile. `riepilogo.json` si scrive alla fine.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.collaudo_ai import valuta_pagine, valuta_pec  # noqa: E402
from pct.collaudo_ai.pagine_anonime import PAGINE  # noqa: E402
from pct.collaudo_ai.pec_ostili import corpus  # noqa: E402


def generatore(url: str, modello: str, *, fili: int, limite_token: int = 1024):
    def genera(domanda: str, schema: dict) -> str:
        corpo = json.dumps({
            "model": modello, "prompt": domanda, "stream": False, "format": schema, "think": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_thread": fili, "num_predict": limite_token},
        }).encode("utf-8")
        richiesta = urllib.request.Request(f"{url.rstrip('/')}/api/generate", data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(richiesta, timeout=1800) as risposta:  # noqa: S310 - Ollama locale
            return str(json.load(risposta).get("response") or "")
    return genera


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argomenti.add_argument("--modelli", nargs="*", default=[])
    argomenti.add_argument("--uscita", default="artifacts/collaudo-ai")
    argomenti.add_argument("--ollama", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    argomenti.add_argument("--fili", type=int, default=int(os.environ.get("COLLAUDO_FILI", "2")))
    argomenti.add_argument("--solo", choices=("pec", "pagine"), default=None)
    # Un modello piccolo può non chiudere mai il JSON: il limite di token evita
    # letture da mezz'ora (la risposta troncata si conta come non letta).
    argomenti.add_argument("--limite-token", type=int, default=1024)
    argomenti.add_argument("--senza-base", action="store_true", help="salta regole e lettore simulato")
    opzioni = argomenti.parse_args()

    uscita = Path(opzioni.uscita)
    uscita.mkdir(parents=True, exist_ok=True)
    letture = (uscita / "letture.jsonl").open("a", encoding="utf-8")

    def scrivi(banco: str, esito: dict) -> None:
        letture.write(json.dumps({"banco": banco, **esito}, ensure_ascii=False) + "\n")
        letture.flush()

    riepilogo: dict = {"avviata": time.strftime("%Y-%m-%d %H:%M:%S"), "pec": {}, "pagine": {}}
    pec = corpus()
    if opzioni.solo in (None, "pec") and not opzioni.senza_base:
        regole = [valuta_pec.valuta_regole(p) for p in pec]
        for esito in regole:
            scrivi("pec", esito.to_dict())
        riepilogo["pec"]["regole"] = valuta_pec.riepilogo(regole)
    if opzioni.solo in (None, "pagine") and not opzioni.senza_base:
        simulato = valuta_pagine.valuta_simulato()
        for esito in simulato:
            scrivi("pagine", esito.to_dict())
        riepilogo["pagine"]["simulato"] = valuta_pagine.riepilogo(simulato)

    for modello in opzioni.modelli:
        genera = generatore(opzioni.ollama, modello, fili=opzioni.fili, limite_token=opzioni.limite_token)
        if opzioni.solo in (None, "pec"):
            per_configurazione = {}
            for con_marcatore in (False, True):
                esiti = []
                for p in pec:
                    esito = valuta_pec.valuta_modello(p, genera, modello=modello, con_marcatore=con_marcatore)
                    esiti.append(esito)
                    scrivi("pec", esito.to_dict())
                    print(f"[pec] {esito.lettore} {p.id} {esito.secondi}s", flush=True)
                per_configurazione[con_marcatore] = esiti
                riepilogo["pec"][esiti[0].lettore] = valuta_pec.riepilogo(esiti)
            riepilogo["pec"][f"{modello} · differenza campi proposti col marcatore"] = valuta_pec.differenza_campi_proposti(
                per_configurazione[False], per_configurazione[True])
        if opzioni.solo in (None, "pagine"):
            esiti = []
            for pagina in PAGINE:
                esito = valuta_pagine.valuta_con_modello(pagina, genera, modello=modello)
                esiti.append(esito)
                scrivi("pagine", esito.to_dict())
                print(f"[pagine] {modello} {pagina.id} {esito.secondi}s", flush=True)
            riepilogo["pagine"][modello] = valuta_pagine.riepilogo(esiti)
        (uscita / "riepilogo.json").write_text(json.dumps(riepilogo, ensure_ascii=False, indent=2), encoding="utf-8")

    riepilogo["conclusa"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (uscita / "riepilogo.json").write_text(json.dumps(riepilogo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(riepilogo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
