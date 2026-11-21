"""Valutazione sul testo libero del widget (stesso ingresso di /api/assistente/chat): i 22 casi dell'avvocato scritti
come li scrive l'avvocato, valutati con i criteri delle schede (punteggio.valuta_caso).

Uso: python -m tests.lex_collaudo.testo_libero [ID ...]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from lex.harness.http import payload_harness
from tests.lex_collaudo.punteggio import carica_casi, valuta_caso

LIBERO = Path(__file__).with_name("casi_avvocato_testo_libero.json")


def risposte(ids: list[str] | None = None) -> list[dict]:
    os.environ.setdefault("LEX_HARNESS_GIURISPRUDENZA", "0")
    attese = {c["id"]: c for c in carica_casi()}
    uscita = []
    for caso in json.loads(LIBERO.read_text(encoding="utf-8"))["casi"]:
        if ids and caso["id"] not in ids:
            continue
        t0 = time.monotonic()
        p = payload_harness(caso["domanda"])
        testo = str((p or {}).get("answer") or "")
        esito = valuta_caso(attese[caso["id"]], testo)
        uscita.append({"id": caso["id"], "corretto": esito.corretto, "mancanze": esito.mancanze,
                       "regola": ((p or {}).get("lex_harness") or {}).get("rule"), "secondi": round(time.monotonic() - t0, 2),
                       "testo": testo})
    return uscita


if __name__ == "__main__":
    righe = risposte(sys.argv[1:] or None)
    for r in righe:
        print(r["id"], "OK" if r["corretto"] else "NO", r["regola"], r["secondi"], "; ".join(r["mancanze"])[:300])
    print(f"corretti {sum(r['corretto'] for r in righe)}/{len(righe)}")
