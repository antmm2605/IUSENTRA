"""Riallinea gli articoli dell'archivio Normattiva divisi male dalla vecchia regola (vedi lex/normativa/riallinea_articoli.py).

Uso:
    python tools/normattiva_riallinea.py --db data/normativa/normattiva.sqlite --analizza   # solo resoconto
    python tools/normattiva_riallinea.py --db data/normativa/normattiva.sqlite              # corregge
    python tools/normattiva_riallinea.py --db ... --vettori                                 # e aggiorna i vettori

Idempotente: su un archivio gia' corretto non cambia nulla. Nel job notturno gira dopo l'import Open Data.
Codice di uscita 0 anche quando non c'e' nulla da fare; 1 solo se il database non si apre.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

from lex.normativa.riallinea_articoli import riallinea  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True)
    parser.add_argument("--analizza", action="store_true", help="solo resoconto, nessuna modifica")
    parser.add_argument("--vettori", action="store_true", help="aggiorna subito l'indice vettoriale (se Ollama risponde)")
    parser.add_argument("--cartella-vettori", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    db = Path(args.db)
    if not db.exists():
        print(f"ERRORE: database non trovato: {db}", file=sys.stderr)
        return 1
    esito = riallinea(db, applica=not args.analizza)
    if args.json:
        print(json.dumps(esito.to_dict(), ensure_ascii=False, indent=1))
    else:
        for riga in esito.dettagli:
            print(f"  {riga}")
        print(
            f"Riallineamento articoli{' (solo analisi)' if args.analizza else ''}: {esito.documenti_esaminati} documenti "
            f"esaminati, {esito.documenti_con_difetti} con difetti, {esito.documenti_riallineati} riallineati, "
            f"{esito.documenti_saltati} saltati; articoli {esito.articoli_prima} -> {esito.articoli_dopo}; "
            f"{esito.chunk_inseriti} chunk, {esito.fts_indicizzati} indicizzati FTS in {esito.secondi}s"
        )
    if args.vettori and esito.documenti_riallineati and not args.analizza:
        cartella = args.cartella_vettori or str(db.parent / "vettori_normattiva")
        comando = [sys.executable, "-m", "lex.ricerca_giuridica.indice_vettoriale", "aggiorna", "--db", str(db),
                   "--out", cartella, "--se-disponibile", "--solo-esistente"]
        print("Aggiorno l'indice vettoriale: " + " ".join(comando))
        if subprocess.run(comando, cwd=str(RADICE)).returncode != 0:
            print("ATTENZIONE: aggiornamento dei vettori non riuscito; ci pensera' il passaggio notturno.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
