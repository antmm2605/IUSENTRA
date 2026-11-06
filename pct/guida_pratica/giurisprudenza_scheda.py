"""Giurisprudenza di una scheda della Guida pratica, solo dall'archivio del software (fonti certe).

1. Ogni citazione di giurisprudenza della scheda si cerca nell'archivio: Cassazione 2021-2026 per anno, numero e
   sezione; le decisioni anteriori sono vere se una decisione dell'archivio le richiama (tabella
   ``sentenza_precedenti``); la Corte costituzionale nel suo archivio ufficiale. Una citazione che non risulta non è
   mostrata come fonte.
2. Per le norme della scheda si cercano nell'archivio le decisioni che le applicano (tabella ``sentenza_norme``):
   prima quelle che applicano più norme della scheda insieme, poi le Sezioni Unite, poi le più recenti.
Le tabelle sono alimentate dal lettore delle citazioni (``pct/giurisprudenza_alimentazione.py``).
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

_CASS = re.compile(r"^Cass\.?\s*(?P<ramo>(?:civ\.|pen\.|sez\.\s*lav\.|lav\.)?)\s*(?P<su>S\.?\s?U\.?|Sez\.?\s*Un\.?)?\s*(?:n\.\s*)?(?P<num>\d{1,6})/(?P<anno>\d{4})", re.IGNORECASE)
_COST = re.compile(r"^(?:Corte\s+Cost\.?|C\.\s?Cost\.?)\s*(?:sent\.\s*|ord\.\s*)?(?:n\.\s*)?(?P<num>\d{1,4})/(?P<anno>\d{4})", re.IGNORECASE)
_GIURISPRUDENZA = re.compile(r"^(?:Cass|Corte\s+Cost|C\.\s?Cost|CGUE|Cons\.|TAR|Trib|App\.|Corte EDU)", re.IGNORECASE)
_SIGLA_LEGGE = re.compile(r"^(?P<tipo>D\.Lgs\.|D\.P\.R\.|D\.L\.|L\.)\s*(?P<num>\d{1,5})/(?P<anno>\d{4})")


def e_giurisprudenza(voce: dict[str, Any]) -> bool:
    return bool(_GIURISPRUDENZA.match(str(voce.get("fonte", "")).strip()))


def sigla_norma(fonte: str) -> str:
    """«D.Lgs. 165/2001 (TUPI)» -> «D.Lgs. 165/2001»; i codici restano come sono («c.c.», «c.p.c.»)."""
    testo = re.sub(r"\([^)]*\)", "", str(fonte or "")).strip()
    m = _SIGLA_LEGGE.match(testo)
    return f"{m['tipo']} {int(m['num'])}/{m['anno']}" if m else testo


def _apri(percorso: str | Path | None) -> sqlite3.Connection | None:
    if not percorso or not Path(percorso).is_file():
        return None
    connessione = sqlite3.connect(Path(percorso).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    connessione.execute("PRAGMA query_only=ON")
    return connessione


def _cerca_cassazione(db, num: str, anno: int, *, su: bool, ramo: str):
    if anno >= 2021:
        for organo, sezione, url in db.execute("SELECT organo_giudicante, sezione, url_pagina_ufficiale FROM sentenze WHERE anno_sentenza=? AND numero_sentenza IN (?,?)",
                                              (anno, num, num.zfill(5))):
            if su and sezione != "U" or "pen" in ramo and "penale" not in organo or ("civ" in ramo or "lav" in ramo) and "civile" not in organo:
                continue
            return {"verificata": True, "url": url, "come": f"{organo}, sezione {sezione}: decisione presente nell'archivio SentenzeWeb"}
        return None
    riga = db.execute("SELECT s.organo_giudicante, s.numero_sentenza, s.anno_sentenza, s.url_pagina_ufficiale FROM sentenza_precedenti p "
                      "JOIN sentenze s ON s.id=p.sentenza_id WHERE p.anno_sentenza=? AND p.numero_sentenza=? AND (?=0 OR p.sezione='U') LIMIT 1",
                      (anno, str(int(num)), 1 if su else 0)).fetchone()
    if riga:
        return {"verificata": True, "url": riga[3], "come": f"richiamata da {riga[0]}, n. {riga[1]}/{riga[2]} (archivio SentenzeWeb)"}
    return None


def verifica_citazioni(voci: Iterable[dict[str, Any]], *, cassazione: str | Path | None, costituzionale: str | Path | None) -> list[dict[str, Any]]:
    """Esito della verifica di ogni citazione di giurisprudenza della scheda."""
    esiti = []
    with closing(_apri(cassazione) or sqlite3.connect(":memory:")) as cass, closing(_apri(costituzionale) or sqlite3.connect(":memory:")) as cost:
        for voce in voci:
            fonte = re.sub(r"\([^)]*\)", "", str(voce.get("fonte", ""))).strip()
            esito = None
            m, k = _CASS.match(fonte), _COST.match(fonte)
            try:
                if m:
                    esito = _cerca_cassazione(cass, m["num"].lstrip("0") or "0", int(m["anno"]), su=bool(m["su"]), ramo=(m["ramo"] or "").lower())
                elif k:
                    riga = cost.execute("SELECT url_pagina_ufficiale FROM sentenze WHERE anno_sentenza=? AND numero_sentenza=? LIMIT 1",
                                        (int(k["anno"]), str(int(k["num"])))).fetchone()
                    esito = {"verificata": True, "url": riga[0], "come": "pronuncia presente nell'archivio della Corte costituzionale"} if riga else None
            except sqlite3.OperationalError:
                esito = None  # archivio assente o non ancora alimentato: la citazione resta non verificata
            esiti.append({"citazione": voce.get("fonte"), "descrizione": voce.get("descrizione", ""),
                          **(esito or {"verificata": False, "motivo": "non risulta nell'archivio di giurisprudenza del software"})})
    return esiti


def decisioni_per_norme(norme: list[tuple[str, str]], *, cassazione: str | Path | None, limite: int = 3) -> list[dict[str, Any]]:
    """Decisioni dell'archivio che applicano le norme della scheda, con quante e quali ne applicano."""
    chiavi = [(sigla_norma(f), str(a).strip()) for f, a in norme if f and a]
    db = _apri(cassazione)
    if not chiavi or db is None:
        return []
    with closing(db):
        condizione = " OR ".join("(n.sigla=? AND n.articolo=?)" for _ in chiavi)
        parametri = [valore for chiave in chiavi for valore in chiave]
        try:
            righe = db.execute(
                f"SELECT s.id, s.organo_giudicante, s.sezione, s.numero_sentenza, s.anno_sentenza, s.data_deposito, s.url_pagina_ufficiale, "
                f"GROUP_CONCAT(DISTINCT n.sigla || ' art. ' || n.articolo) AS applicate, COUNT(DISTINCT n.id) AS quante "
                f"FROM norme n JOIN sentenza_norme sn ON sn.norma_id=n.id JOIN sentenze s ON s.id=sn.sentenza_id "
                f"WHERE {condizione} GROUP BY s.id ORDER BY quante DESC, (s.sezione='U') DESC, COALESCE(s.data_deposito,'') DESC LIMIT ?",
                [*parametri, limite]).fetchall()
        except sqlite3.OperationalError:
            return []
    return [{"decisione": f"Cass. {'SU' if r[2] == 'U' else ('pen.' if 'penale' in r[1] else ('lav.' if r[2] == 'L' else 'civ.'))} {int(r[3])}/{r[4]}",
             "organo": r[1], "sezione": r[2], "data_deposito": r[5], "url": r[6], "norme_applicate": sorted(str(r[7]).split(",")),
             "perche": f"applica {r[8]} delle norme della scheda" + (" (Sezioni Unite)" if r[2] == "U" else "")} for r in righe]
