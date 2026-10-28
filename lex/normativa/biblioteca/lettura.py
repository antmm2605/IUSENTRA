"""Lettura esatta dei testi della biblioteca, senza ricerca approssimata.

Il percorso del database e la scelta dei riferimenti spettano al chiamante fidato.
Non acquisisce testi, non decide pertinenza o applicabilita e non sceglie una
versione fra piu edizioni. I testi restituiti non sono abbreviati.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

from .fabbisogno import COLLEZIONE
from .identita import risolvi_articolo


def leggi_articoli(db: Path, riferimenti: list[dict]) -> dict:
    """Riferimenti: chiave della collezione, articolo, eventuale edizione/SHA.

    Nessuna deduzione del tipo di atto da N/AAAA: usa la chiave gia censita.
    Un risultato letto non e una Fonte approvata per il fascicolo.
    """
    if not isinstance(riferimenti, list) or len(riferimenti) > 64:
        raise ValueError("Richiesti al massimo 64 riferimenti")
    out, errors = [], []
    with sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        for pos, ref in enumerate(riferimenti, 1):
            if not isinstance(ref, dict):
                raise TypeError("Riferimento non valido")
            key, article = ref.get("chiave"), ref.get("articolo")
            requested_key = key
            literal = re.fullmatch(r"\('c', '([a-z0-9_]{1,100})'\)", key) if isinstance(key, str) else None
            if literal:
                key = literal.group(1)
                ref = dict(ref, chiave=key)
            if (not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_]{1,100}(?:/[0-9]{4})?", key)
                    or not isinstance(article, str) or not article.strip() or len(article) > 40):
                raise ValueError("Identita atto/articolo non valida")
            matches = risolvi_articolo(conn, ref)
            if len(matches) != 1 or not (matches[0][1]["article_text"] or "").strip():
                errors.append({"posizione": pos, "motivo": "Atto/articolo assente, edizione o partizione ambigua, oppure testo vuoto", "chiave": key, "articolo": article,
                               "candidati": [{"document_id": d["id"], "chiave": d["collection_name"].removeprefix(COLLEZIONE), "articolo": a["article_number"], "edizione": d.get("redazione_id")} for d,a in matches]})
                continue
            doc, row = matches[0]
            digest = hashlib.sha256(row["article_text"].encode()).hexdigest()
            if "sha256_atteso" in ref and ref["sha256_atteso"] != digest:
                errors.append({"posizione": pos, "motivo": "Impronta del testo cambiata", "chiave": key, "articolo": article})
                continue
            out.append({"posizione": pos, "chiave": doc["collection_name"].removeprefix(COLLEZIONE), "chiave_richiesta": requested_key, "articolo": row["article_number"],
                        "document_id": doc["id"], "article_id": row["id"], "testo": row["article_text"],
                        "sha256_testo": digest, "provenienza_archivio": dict(doc),
                        "testo_archiviato_senza_troncamento": True,
                        "applicabilita_al_fascicolo": "da_verificare"})
    return {"articoli": out, "errori": errors, "lettura_completa": not errors,
            "fonti_approvate_per_il_fascicolo": False}
