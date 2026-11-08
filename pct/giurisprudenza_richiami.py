"""Precedente richiamato dalle altre pronunce pertinenti: sale nella classifica della ricerca testuale.

Il precedente guida di una materia ha spesso un testo lungo, che il bm25 penalizza, mentre le decisioni successive
lo citano per estremi («sentenza n. 29961 del 27 ottobre 2023», «n. 29961/2023»). Se almeno due altre pronunce della
rosa pertinente lo richiamano, lo si porta più in alto, di più quanti più lo citano. Nessuna pronuncia entra nella
rosa per questo motivo: si riordinano solo quelle già trovate dai termini della domanda. Base: art. 65 R.D. 12/1941
(funzione nomofilattica della Corte di cassazione) e art. 118 disp. att. c.p.c. (motivazione con riferimento a precedenti).
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

FINESTRA = 40          # pronunce della rosa di cui si leggono i testi per contare i richiami
MINIMO_RICHIAMI = 2    # un solo richiamo non fa un precedente seguito
PASSO = 4              # posizioni guadagnate per ogni richiamo
MASSIMO_RICHIAMI = 5


def _citazione(numero: Any, anno: Any) -> re.Pattern[str] | None:
    cifre = str(numero or "").strip().lstrip("0")
    anno = str(anno or "").strip()
    if not cifre.isdigit() or not re.fullmatch(r"(?:19|20)\d{2}", anno):
        return None
    # «n. 29961/2023», «n. 29961 del 2023», «n. 29961 del 27 ottobre 2023», «n. 29961 del 27/10/2023»
    return re.compile(rf"(?<![\d/.]){cifre}\s*(?:/\s*|del\s*(?:\d{{1,2}}\s*[a-zà-ù]+\s*|\d{{1,2}}[./]\d{{1,2}}[./])?){anno}(?!\d)",
                      re.IGNORECASE)


def conta_richiami(righe: list[dict[str, Any]], testi: dict[int, str]) -> dict[int, int]:
    """Per ogni pronuncia, quante altre pronunce della rosa la citano per numero e anno."""
    conteggi: dict[int, int] = {}
    for riga in righe:
        schema = _citazione(riga.get("numero_sentenza"), riga.get("anno_sentenza"))
        if schema is None:
            continue
        propria = int(riga["id"])
        conteggi[propria] = sum(1 for altra, testo in testi.items() if altra != propria and schema.search(testo))
    return conteggi


def riordina_per_richiami(righe: list[dict[str, Any]], conteggi: dict[int, int]) -> list[dict[str, Any]]:
    def chiave(coppia: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        posizione, riga = coppia
        richiami = conteggi.get(int(riga["id"]), 0)
        salto = PASSO * min(richiami, MASSIMO_RICHIAMI) if richiami >= MINIMO_RICHIAMI else 0
        return posizione - salto, posizione

    return [riga for _p, riga in sorted(enumerate(righe), key=chiave)]


def precedenti_richiamati_prima(conn: sqlite3.Connection, righe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Le prime pronunce della rosa con i precedenti richiamati più in alto; le altre restano nell'ordine dato."""
    testa, coda = righe[:FINESTRA], righe[FINESTRA:]
    if len(testa) < MINIMO_RICHIAMI + 1:
        return righe
    ids = [int(r["id"]) for r in testa]
    try:
        testi = {int(r[0]): str(r[1] or "") for r in conn.execute(
            f"SELECT id, testo_integrale FROM sentenze WHERE id IN ({','.join('?' for _ in ids)})", tuple(ids)).fetchall()}
    except sqlite3.Error:
        return righe  # senza testi la classifica resta quella dei termini
    return riordina_per_richiami(testa, conta_richiami(testa, testi)) + coda


__all__ = ["conta_richiami", "precedenti_richiamati_prima", "riordina_per_richiami"]
