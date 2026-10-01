"""Banco di prova di Lex: esegue le domande dello studio di esempio e stampa l'esito.

Uso:
    python scripts/lex_banco_prova.py                 # tabella con esito per domanda
    python scripts/lex_banco_prova.py --dettaglio     # anche la risposta di Lex
    python scripts/lex_banco_prova.py --solo Q01,Q02  # solo alcune domande
    python scripts/lex_banco_prova.py --aggiorna-soglia
        registra le domande superate come nuova soglia (solo se non ne perde nessuna)
    python scripts/lex_banco_prova.py --verifica
        esce con errore se una domanda della soglia non è più superata (usato dal gate)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.lex_banco.valutazione import SOGLIA, carica_soglia, esegui_banco, riepilogo


def _riga(testo: str, larghezza: int) -> str:
    testo = " ".join(str(testo).split())
    return testo if len(testo) <= larghezza else testo[: larghezza - 1] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dettaglio", action="store_true")
    parser.add_argument("--solo", default="")
    parser.add_argument("--aggiorna-soglia", action="store_true")
    parser.add_argument("--verifica", action="store_true")
    parser.add_argument("--json", dest="json_path", default="")
    args = parser.parse_args()
    logging.disable(logging.WARNING)

    solo = {voce.strip() for voce in args.solo.split(",") if voce.strip()} or None
    esiti = esegui_banco(solo=solo)
    sintesi = riepilogo(esiti)

    for esito in esiti:
        stato = "OK " if esito.superata else "NO "
        print(f"{stato} {esito.id} [{esito.categoria:<9}] {_riga(esito.domanda, 70)}")
        if not esito.superata:
            print(f"        motivi: {'; '.join(esito.motivi)}")
        if args.dettaglio or not esito.superata:
            print(f"        Lex: {_riga(esito.risposta, 220)}")
    print()
    for categoria, voce in sorted(sintesi["per_categoria"].items()):
        print(f"  {categoria:<10} {voce['superate']:>2}/{voce['totale']}")
    print(f"\nSuperate: {sintesi['superate']}/{sintesi['totale']}")

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps({"riepilogo": sintesi, "esiti": [asdict(esito) for esito in esiti]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    soglia = set(carica_soglia().get("superate", []))
    superate = set(sintesi["superate_id"])
    perse = sorted(soglia - superate) if not solo else sorted((soglia & solo) - superate)
    if perse:
        print(f"\nREGRESSIONE: domande superate in precedenza e ora sbagliate: {', '.join(perse)}")
    if args.verifica:
        return 1 if perse else 0
    if args.aggiorna_soglia:
        if solo:
            print("--aggiorna-soglia richiede l'intero banco (senza --solo).")
            return 2
        if perse:
            print("Soglia non aggiornata: prima correggi le regressioni.")
            return 1
        SOGLIA.write_text(
            json.dumps({"superate": sorted(superate), "totale": sintesi["totale"]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Soglia aggiornata: {len(superate)}/{sintesi['totale']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
