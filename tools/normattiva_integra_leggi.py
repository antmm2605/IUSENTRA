"""Integra nell'archivio Normattiva le leggi ordinarie essenziali (vedi lex/normativa/integrazione_leggi.py).

Uso:
    python tools/normattiva_integra_leggi.py --db data/normativa/normattiva.sqlite
    python tools/normattiva_integra_leggi.py --db ... --jsonl lex/normativa/integrazioni/leggi_essenziali.jsonl --vettori
    python tools/normattiva_integra_leggi.py --db ... --verifica

Nel job notturno dello scheduler gira dopo l'import Open Data e prima dell'aggiornamento dei vettori;
con --vettori lancia subito ``indice_vettoriale aggiorna --se-disponibile --solo-esistente`` (serve Ollama).
Codice di uscita 0 anche quando non c'e' nulla da fare; 1 solo per errori di lettura del file o del database.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

from lex.normativa.integrazione_leggi import FILE_PREDEFINITO, integra, verifica  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="database normattiva.sqlite")
    parser.add_argument("--jsonl", default=str(FILE_PREDEFINITO), help="file degli articoli (default: quello del repository)")
    parser.add_argument("--vigenza", default=os.getenv("IUSENTRA_NORMATTIVA_VIGENZA", "VIGENTE"),
                        help="vigenza dell'archivio: i testi integrati sono VIGENTI, con ORIGINALE non si fa nulla")
    parser.add_argument("--solo", nargs="*", default=None, help="chiavi degli atti da integrare (default: tutti)")
    parser.add_argument("--vettori", action="store_true", help="aggiorna subito l'indice vettoriale (se Ollama risponde)")
    parser.add_argument("--cartella-vettori", default="", help="cartella dell'indice vettoriale (default: <db>/../vettori_normattiva)")
    parser.add_argument("--verifica", action="store_true", help="solo controllo: articoli presenti e tre ricerche di prova")
    parser.add_argument("--json", action="store_true", help="stampa l'esito in JSON")
    args = parser.parse_args(argv)

    db = Path(args.db)
    if args.verifica:
        if not db.exists():
            print(f"ERRORE: database non trovato: {db}", file=sys.stderr)
            return 1
        for riga in verifica(db, jsonl=args.jsonl):
            print(riga)
        return 0

    try:
        esito = integra(db, jsonl=args.jsonl, vigenza_archivio=args.vigenza, solo_chiavi=args.solo)
    except (OSError, ValueError) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(esito.to_dict(), ensure_ascii=False, indent=1))
    else:
        for riga in esito.dettagli or []:
            print(f"  {riga}")
        print(
            f"Integrazione leggi essenziali: {esito.atti_inseriti} inseriti, {esito.atti_sostituiti} aggiornati, "
            f"{esito.atti_gia_presenti} gia' presenti, {esito.atti_saltati} saltati; "
            f"{esito.articoli_inseriti} articoli, {esito.chunk_inseriti} chunk, {esito.fts_indicizzati} indicizzati FTS"
        )
    if args.vettori and (esito.atti_inseriti or esito.atti_sostituiti):
        cartella = args.cartella_vettori or str(db.parent / "vettori_normattiva")
        comando = [sys.executable, "-m", "lex.ricerca_giuridica.indice_vettoriale", "aggiorna", "--db", str(db),
                   "--out", cartella, "--se-disponibile", "--solo-esistente"]
        print("Aggiorno l'indice vettoriale: " + " ".join(comando))
        completato = subprocess.run(comando, cwd=str(RADICE))
        if completato.returncode != 0:
            print("ATTENZIONE: aggiornamento dei vettori non riuscito; ci pensera' il passaggio notturno.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
