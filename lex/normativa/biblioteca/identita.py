"""Identita degli articoli gia censiti, comprese partizioni e alias storici.

Non sceglie un'edizione o un allegato per somiglianza. Restituisce tutti i
riscontri reali; una lettura e possibile soltanto quando il riscontro e unico.
"""
from __future__ import annotations

import re
import sqlite3

from .fabbisogno import COLLEZIONE, norm_articolo


def documenti_per_chiave(conn: sqlite3.Connection, chiave: str) -> list[dict]:
    cursor = conn.cursor()
    cursor.row_factory = sqlite3.Row
    exact = [dict(d) for d in cursor.execute("SELECT * FROM normative_documents WHERE collection_name=?", (COLLEZIONE + chiave,))]
    if exact:
        return exact
    # Compatibilita con vecchie etichette serializzate male: nessuna eval.
    literal = re.fullmatch(r"\('c', '([a-z0-9_]+)'\)", chiave)
    if literal:
        return documenti_per_chiave(conn, literal[1])
    if chiave == "codice_deontologico_forense":
        return [dict(d) for d in cursor.execute("SELECT * FROM normative_documents WHERE collection_name LIKE ?", (COLLEZIONE + "codice_deontologico_forense_%",))]
    from lex.ricerca_giuridica.testo import CODICI_PER_CHIAVE

    code = CODICI_PER_CHIAVE.get(chiave)
    if code and code.numero:
        return [dict(d) for d in cursor.execute("SELECT * FROM normative_documents WHERE numero=? AND data_atto=?", (code.numero, code.data_atto))]
    typed = re.fullmatch(r"(legge|dlgs|dpr|dl|rd)_(\d+)_(\d{4})",chiave)
    if typed:
        from .riferimenti import fonte_per_chiave

        source=fonte_per_chiave(chiave)
        prefix=source.urn.rsplit(":",1)[0]+":"+typed[3]+"-"
        docs=[dict(d) for d in cursor.execute("SELECT * FROM normative_documents WHERE numero=? AND data_atto>=? AND data_atto<?",
                  (typed[2],typed[3]+"-01-01",str(int(typed[3])+1)+"-01-01"))]
        return [d for d in docs if str(d.get("urn") or "").startswith(prefix)]
    number = re.fullmatch(r"(\d+)/(\d{4})", chiave)
    if number:
        # Il numero/anno non determina il tipo: tutti i riscontri restano distinti.
        return [dict(d) for d in cursor.execute("SELECT * FROM normative_documents WHERE numero=? AND data_atto>=? AND data_atto<?", (number[1],number[2]+"-01-01",str(int(number[2])+1)+"-01-01"))]
    return []


def risolvi_articolo(conn: sqlite3.Connection, riferimento: dict) -> list[tuple[dict, dict]]:
    docs = documenti_per_chiave(conn, riferimento["chiave"])
    if "data_riferimento" in riferimento:
        from lex.normativa.applicabilita import data_iso
        from lex.normativa.provenienza_edizione import edizione_archiviata,riscontro_alla_data
        import json
        when=data_iso(riferimento["data_riferimento"])
        filtered=[]
        for doc in docs:
            raw=conn.execute("SELECT metadata_json FROM normative_chunks WHERE document_id=? ORDER BY id LIMIT 1",(doc["id"],)).fetchone()
            try:metadata=json.loads(raw[0] or "{}") if raw else {}
            except (ValueError,TypeError):continue
            if riscontro_alla_data(edizione_archiviata(metadata,doc),when) is True:
                filtered.append(doc)
        docs=filtered
    if "edizione" in riferimento:
        docs = [d for d in docs if d.get("redazione_id") == riferimento["edizione"]]
    if riferimento.get("titolo_atto"):
        docs = [d for d in docs if d.get("titolo") == riferimento["titolo_atto"]]
    if len({d.get("urn") for d in docs}) > 1:
        return []  # omonimia numero/anno fra atti diversi
    if "edizione" not in riferimento and len({d.get("redazione_id") for d in docs}) > 1:
        return []  # un allegato mancante non autorizza a scegliere un'altra edizione
    cursor = conn.cursor(); cursor.row_factory = sqlite3.Row
    matches = []
    for doc in docs:
        for raw in cursor.execute("SELECT id,article_number,article_text FROM normative_articles WHERE document_id=?", (doc["id"],)):
            row = dict(raw)
            if norm_articolo(row["article_number"]) != norm_articolo(riferimento["articolo"]):
                continue
            prefix = riferimento.get("inizio_testo")
            if prefix and not (row["article_text"] or "").startswith(prefix):
                continue
            matches.append((doc, row))
    return matches


def chiave_partizione(chiave:str,partizione:str,localizzatore:str="")->str:
    """Identificatore tecnico compatibile col lettore; non un alias normativo."""
    import hashlib
    prefix=re.sub(r"[^a-z0-9_]","_",chiave.casefold())[:65]
    digest=hashlib.sha256((chiave+"|"+partizione+"|"+localizzatore).encode()).hexdigest()[:16]
    return prefix+"_parte_"+digest


def numero_articolo(value):
    value = re.sub(r"^\s*art(?:icolo)?\.?\s*", "", str(value or ""), flags=re.IGNORECASE).strip()
    value = re.sub(r"(?<=\w)\.$", "", value)
    decimal = re.fullmatch(r"[0-9]{1,5}(?:[ .-]?[a-z]{2,24})?(?:\.[0-9]{1,4})?", value, re.IGNORECASE)
    historical = re.fullmatch(r"[0-9]{1,5}/[0-9]{1,5}",value)
    roman = re.fullmatch(r"([ivxlcdm]+)(?:[ .-]?(bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies|terdecies))?",value,re.I)
    if roman and not re.fullmatch(r"M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})",roman[1].upper()):roman=None
    if not (decimal or historical or roman):
        raise ValueError("Indica un singolo articolo da leggere.")
    return norm_articolo(value)


def espressione_numero_articolo_sql(colonna: str = 'article_number') -> str:
    """Espressione condivisa fra indice offline e filtro del catalogo."""
    if colonna not in {'article_number','a.article_number'}:
        raise ValueError('Colonna normativa non ammessa')
    raw = f"lower(trim({colonna}))"
    senza_prefisso = (f"CASE WHEN {raw} LIKE 'articolo%' THEN substr({raw},9) "
                     f"WHEN {raw} LIKE 'art.%' THEN substr({raw},5) "
                     f"WHEN {raw} LIKE 'art %' THEN substr({raw},5) ELSE {raw} END")
    return f"replace(replace(rtrim(trim({senza_prefisso}),'.'),'-',''),' ','')"


def indicizza_numeri_articolo(conn: sqlite3.Connection) -> str:
    """Migrazione esplicita offline: mai richiamata da una consultazione GET."""
    nome='idx_normative_article_numero_riscontrato'
    conn.execute(f'CREATE INDEX IF NOT EXISTS {nome} ON normative_articles ('+espressione_numero_articolo_sql()+')')
    return nome
