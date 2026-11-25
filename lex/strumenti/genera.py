"""Rigenera ``lex/strumenti/mappa.json`` dal codice e stampa la copertura.

Uso: ``python -m lex.strumenti.genera`` (scrive) oppure ``python -m lex.strumenti.genera --controlla`` (esce con 1 se
il file non è aggiornato o la copertura ha lacune).
"""
from __future__ import annotations

import json
import sys

from .mappa import FILE_MAPPA, costruisci_mappa


def testo_mappa() -> str:
    return json.dumps(costruisci_mappa(), ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def lacune(cop: dict) -> list[str]:
    uscita = []
    for tipo, voce in cop.items():
        for chiave, etichetta in (("mancanti", "nel codice ma non in mappa"), ("inesistenti", "in mappa ma non nel codice")):
            for nome in voce.get(chiave, []):
                uscita.append(f"{tipo}: «{nome}» {etichetta}")
    return uscita


def main(argv: list[str]) -> int:
    testo = testo_mappa()
    cop = json.loads(testo)["copertura"]
    problemi = lacune(cop)
    if "--controlla" in argv:
        vecchio = FILE_MAPPA.read_text(encoding="utf-8") if FILE_MAPPA.exists() else ""
        if vecchio != testo:
            problemi.append("mappa.json non aggiornata: eseguire python -m lex.strumenti.genera")
    else:
        FILE_MAPPA.write_text(testo, encoding="utf-8")
    for tipo, voce in cop.items():
        if "nel_codice" in voce:
            print(f"{tipo}: {voce['in_mappa']}/{voce['nel_codice']} in mappa, {voce['fuori_mappa_dichiarati']} fuori mappa dichiarati")
    print("\n".join(problemi) or "copertura completa")
    return 1 if problemi else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
