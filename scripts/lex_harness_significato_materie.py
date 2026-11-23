"""Esporta l'indice per la ricerca per significato delle regole per materia in lex/harness/dati/significato_regole_materie.json.

Uso: python scripts/lex_harness_significato_materie.py
Formato: [{"regola", "materia", "nome", "lato": "attivo|passivo|entrambi", "sinonimi": [...], "situazioni": [...]}].
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from lex.harness.fattispecie.materie import indice_significato  # noqa: E402

USCITA = RADICE / "lex" / "harness" / "dati" / "significato_regole_materie.json"


def main() -> int:
    voci = indice_significato()
    USCITA.write_text(json.dumps({"formato": "regola, materia, nome, lato, sinonimi, situazioni", "regole": voci},
                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(voci), "regole")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
