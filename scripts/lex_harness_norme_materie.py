"""Istantanea delle norme delle fattispecie per materia dalla biblioteca di consultazione (testo vigente Normattiva).

Uso: python scripts/lex_harness_norme_materie.py <codici_leggi.sqlite>

Per ogni voce di ``lex/harness/norme_materie.py`` legge, in sola lettura, l'edizione più recente dell'atto (prima le
edizioni «VIGENTE_AL:<data>» acquisite con ``scripts/biblioteca_vigente.py aggiorna``, poi quella con più articoli) e
l'articolo con il numero indicato; scrive ``lex/harness/dati/norme_vigenti_materie.json`` con testo, URN Normattiva,
data della vigenza, impronta SHA-256. Un articolo abrogato o non trovato va fra i «mancanti»: l'harness non lo afferma.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from lex.harness.norme import ISTANTANEA_MATERIE  # noqa: E402
from lex.harness.norme_materie import NORME_MATERIE  # noqa: E402


def _documento(conn: sqlite3.Connection, urn: str) -> tuple[int, str] | None:
    righe = conn.execute(
        "SELECT d.id, coalesce(d.vigenza,''), count(a.id) n FROM normative_documents d JOIN normative_articles a "
        "ON a.document_id=d.id WHERE d.urn LIKE ? GROUP BY d.id", (f"%{urn}",)).fetchall()
    if not righe:
        return None
    # edizione «VIGENTE_AL» più recente; a parità, quella con più articoli
    migliore = max(righe, key=lambda r: (r[1].startswith("VIGENTE_AL:"), r[1] if r[1].startswith("VIGENTE_AL:") else "", r[2]))
    return migliore[0], migliore[1]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    db = Path(sys.argv[1])
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    norme, mancanti = {}, {}
    for chiave, _estremi, citazione, _rubrica, urn, numero in NORME_MATERIE:
        doc = _documento(conn, urn)
        if doc is None:
            mancanti[chiave] = "atto non presente nella biblioteca"
            continue
        r = conn.execute("SELECT id, article_text FROM normative_articles WHERE document_id=? AND article_number=? "
                         "ORDER BY length(article_text) DESC LIMIT 1", (doc[0], numero)).fetchone()
        if r is None:
            mancanti[chiave] = f"articolo {numero} non trovato nell'edizione {doc[0]}"
            continue
        testo = " ".join((r[1] or "").split())
        if re.search(r"\(\(\s*(?:ARTICOLO|PROVVEDIMENTO) ABROGAT", testo[:200]):
            mancanti[chiave] = "articolo abrogato nel testo vigente"
            continue
        titolo = conn.execute("SELECT titolo FROM normative_documents WHERE id=?", (doc[0],)).fetchone()[0] or ""
        vig = doc[1][len("VIGENTE_AL:"):] if doc[1].startswith("VIGENTE_AL:") else ""
        agg = date.fromisoformat(vig).strftime("%d/%m/%Y") if vig else ""
        norme[chiave] = {"citazione": citazione, "testo": testo,
                         "url": f"https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:{urn}~art{numero}"
                         if not urn.startswith("unione") else "",
                         "titolo_atto": titolo, "aggiornamento": agg, "vigente": True, "document_id": str(doc[0]),
                         "article_id": str(r[0]), "origine": "biblioteca di consultazione (testo vigente Normattiva)",
                         "sha256": hashlib.sha256(testo.encode()).hexdigest()}
    uscita = {"generata_il": date.today().isoformat(), "archivio": str(db), "norme": norme, "mancanti": mancanti}
    ISTANTANEA_MATERIE.write_text(json.dumps(uscita, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(norme)} norme, {len(mancanti)} mancanti")
    for k, v in mancanti.items():
        print("  MANCA", k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
