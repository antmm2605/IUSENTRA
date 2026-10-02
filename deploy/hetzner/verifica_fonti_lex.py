"""Controllo dell'archivio Normattiva dopo il caricamento (eseguito DENTRO il container).

Uso (lo lancia carica_fonti_lex.sh):
    docker compose exec -T scheduler-worker python - --db /data/normativa/normattiva.sqlite \
        --documenti N --articoli N --chunk N [--righe-vettori N] < verifica_fonti_lex.py

Esce con 0 se i conteggi coincidono con quelli del pacchetto e la ricerca "art. 2043 c.c." funziona.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--documenti", type=int, default=-1)
    parser.add_argument("--articoli", type=int, default=-1)
    parser.add_argument("--chunk", type=int, default=-1)
    parser.add_argument("--righe-vettori", type=int, default=-1)
    parser.add_argument("--domanda", default="art. 2043 c.c.")
    args = parser.parse_args(argv)

    db = Path(args.db)
    if not db.is_file():
        print(f"KO database assente: {db}")
        return 1
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        def conta(sql: str) -> int:
            return int(conn.execute(sql).fetchone()[0])

        trovati = {
            "documenti": conta("SELECT COUNT(*) FROM normative_documents"),
            "articoli": conta("SELECT COUNT(*) FROM normative_articles"),
            "chunk": conta("SELECT COUNT(*) FROM normative_chunks"),
            "chunk_fts": conta("SELECT COUNT(*) FROM normative_fts_info"),
        }
        ha_2043 = conta("SELECT COUNT(*) FROM normative_articles WHERE article_number LIKE '2043%'") > 0
    finally:
        conn.close()
    print("conteggi:", json.dumps(trovati))
    errori: list[str] = []
    for nome in ("documenti", "articoli", "chunk"):
        atteso = getattr(args, nome)
        if atteso >= 0 and trovati[nome] != atteso:
            errori.append(f"{nome}: trovati {trovati[nome]}, attesi {atteso}")
    if trovati["chunk"] and trovati["chunk_fts"] != trovati["chunk"]:
        errori.append(f"indice FTS incompleto ({trovati['chunk_fts']}/{trovati['chunk']})")

    try:
        from lex.ricerca_giuridica.ibrida import MotoreRicercaNormattiva
        from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale
    except Exception as exc:  # immagine senza il modulo: il caricamento non va dichiarato riuscito
        print(f"KO moduli di ricerca non importabili: {exc}")
        return 1
    motore = MotoreRicercaNormattiva(db)
    try:
        risultati = motore.cerca(args.domanda, limite=5)
    except Exception as exc:
        risultati = []
        errori.append(f"ricerca fallita: {exc}")
    print(f"ricerca {args.domanda!r}: {len(risultati)} risultati")
    for r in risultati[:3]:
        print(f"   {str(r.get('titolo'))[:70]} | art. {r.get('articolo_o_chunk')} | {r.get('vigenza')}")
    if ha_2043 and not any("2043" in str(r.get("articolo_o_chunk") or "") for r in risultati):
        errori.append("la ricerca 'art. 2043 c.c.' non restituisce l'art. 2043")
    if not ha_2043 and not risultati and trovati["chunk"] == 0:
        errori.append("archivio vuoto")

    stato = motore.stato()
    print("semantica:", json.dumps({k: stato[k] for k in ("semantica_attiva", "motivo_semantica", "righe_vettori")}, ensure_ascii=False))
    if args.righe_vettori >= 0:
        indice = IndiceVettoriale.apri(motore.cartella_vettori)
        if indice is None:
            errori.append("indice vettoriale assente")
        elif indice.righe != args.righe_vettori:
            errori.append(f"righe vettori: trovate {indice.righe}, attese {args.righe_vettori}")
    if errori:
        for riga in errori:
            print("KO", riga)
        return 1
    print("OK archivio Normattiva verificato")
    return 0


if __name__ == "__main__":
    sys.exit(main())
