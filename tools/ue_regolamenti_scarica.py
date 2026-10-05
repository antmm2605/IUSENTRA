"""Scarica i regolamenti UE dall'Ufficio delle pubblicazioni e li divide in articoli (vedi lex/normativa/ue_regolamenti.py).

Uso:
    python tools/ue_regolamenti_scarica.py --cache data/normativa/ue_cache                   # solo resoconto
    python tools/ue_regolamenti_scarica.py --cache ... --aggiorna                            # riscrive le righe nel JSONL del repository
    python tools/ue_regolamenti_scarica.py --cache ... --copie /percorso/fonti/integrate     # un JSONL per atto (reg_ue_AAAA_N.jsonl)
    python tools/ue_regolamenti_scarica.py --cache ... --solo 32012R1215 32008R0593 --originale --offline

Per ogni atto: testo consolidato piu' recente (se l'URI CELEX consolidato risponde e la divisione passa i controlli),
altrimenti testo originale della GUUE. Gli XHTML restano in cache: ``--offline`` rilegge solo quelli.
Un atto con errori (numerazione, articoli vuoti, intestazioni nel testo) non viene scritto. Codice di uscita 1 se
almeno un atto ha errori.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

from lex.normativa.integrazione_leggi import FILE_PREDEFINITO  # noqa: E402
from lex.normativa.ue_regolamenti import (  # noqa: E402
    REGOLAMENTI,
    REGOLAMENTI_PER_CELEX,
    URI_CELEX,
    prepara,
    righe_jsonl,
    sostituisci_nel_jsonl,
    ultimo_articolo,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", required=True, help="cartella degli XHTML scaricati")
    parser.add_argument("--solo", nargs="*", default=None, help="CELEX degli atti (default: tutti quelli del catalogo)")
    parser.add_argument("--originale", action="store_true", help="solo testo originale GUUE (niente consolidati)")
    parser.add_argument("--offline", action="store_true", help="nessun download: usa solo la cache")
    parser.add_argument("--oggi", default="", help="data limite dei consolidati (AAAA-MM-GG, default oggi)")
    parser.add_argument("--aggiorna", action="store_true", help="riscrive le righe di questi atti nel JSONL (--jsonl)")
    parser.add_argument("--jsonl", default=str(FILE_PREDEFINITO), help="JSONL delle leggi integrate")
    parser.add_argument("--copie", default="", help="cartella dove scrivere un JSONL per atto (reg_ue_AAAA_N.jsonl)")
    parser.add_argument("--json", action="store_true", help="resoconto in JSON")
    args = parser.parse_args(argv)

    scelti = [REGOLAMENTI_PER_CELEX[c] for c in args.solo] if args.solo else list(REGOLAMENTI)
    cache = Path(args.cache)
    raccolto = dt.date.today().isoformat()
    nuove: list[dict] = []
    resoconto: list[dict] = []
    errori_totali = 0
    for reg in scelti:
        esito = prepara(reg, cache, consolidato=not args.originale, offline=args.offline, oggi=args.oggi)
        voce = {"celex": reg.celex, "nome": reg.nome, "chiave": reg.chiave, "celex_usato": esito.celex_usato,
                "versione": f"consolidato al {esito.consolidato_al}" if esito.consolidato_al else "originale GUUE",
                "articoli": len(esito.atto.articoli) if esito.atto else 0,
                "ultimo_articolo": ultimo_articolo(esito.atto) if esito.atto else 0,
                "soppressi": esito.soppressi, "note": esito.note, "errori": esito.errori,
                "sigla": esito.atto.sigla if esito.atto else "", "data_atto": esito.atto.data_atto if esito.atto else ""}
        resoconto.append(voce)
        if not esito.valido:
            errori_totali += 1
            continue
        righe = righe_jsonl(esito.atto, chiave=reg.chiave, url=URI_CELEX.format(celex=esito.celex_usato),
                            consolidato_al=esito.consolidato_al, raccolto_il=raccolto)
        nuove.extend(righe)
        if args.copie:
            cartella = Path(args.copie)
            cartella.mkdir(parents=True, exist_ok=True)
            (cartella / f"{reg.chiave}.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in righe), encoding="utf-8")
    if args.aggiorna and nuove:
        tolte, aggiunte = sostituisci_nel_jsonl(Path(args.jsonl), nuove)
        resoconto.append({"jsonl": args.jsonl, "righe_tolte": tolte, "righe_aggiunte": aggiunte})
    if args.json:
        print(json.dumps(resoconto, ensure_ascii=False, indent=1))
    else:
        for voce in resoconto:
            if "jsonl" in voce:
                print(f"{voce['jsonl']}: tolte {voce['righe_tolte']} righe, aggiunte {voce['righe_aggiunte']}")
                continue
            stato = "OK " if not voce["errori"] else "ERR"
            print(f"{stato} {voce['sigla'] or voce['celex']:<20} {voce['nome'][:38]:<38} {voce['articoli']:>4} articoli "
                  f"(ultimo {voce['ultimo_articolo']}) {voce['versione']} [{voce['celex_usato']}]")
            for nota in voce["note"]:
                print(f"      nota: {nota}")
            for errore in voce["errori"]:
                print(f"      ERRORE: {errore}")
    return 1 if errori_totali else 0


if __name__ == "__main__":
    raise SystemExit(main())
