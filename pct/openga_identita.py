"""Identità del risultato selezionato dal solo catalogo pubblico corrente."""
import re
import sqlite3
from contextlib import closing
from pathlib import Path


def identita_catalogo(path, payload):
    keys = ("relazione_id", "resource_id", "resource_sha256")
    if any(not isinstance(payload.get(k), str) or not 0 < len(payload[k]) <= 256 for k in keys):
        raise ValueError("Riferimento al catalogo non valido.")
    if not re.fullmatch(r"[a-f0-9]{64}", payload["resource_sha256"]):
        raise ValueError("Impronta del catalogo non valida.")
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT a.sede,a.nome_sede,a.tipo,a.numero,a.anno,a.ricorso
            FROM attive a JOIN risorse s ON s.id=a.risorsa
            WHERE a.relazione=? AND a.risorsa=? AND s.sha256=? LIMIT 2
        """, tuple(payload[k] for k in keys)).fetchall()
    if len(rows) != 1:
        raise ValueError("Risultato non più presente o ambiguo: ripeti la ricerca.")
    return dict(rows[0])
