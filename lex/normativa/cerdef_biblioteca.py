"""Vista in sola lettura degli atti CeRDEF già conservati in Normattiva."""
from contextlib import closing, contextmanager
import os
import re
from pathlib import Path

from lex.normativa.consultazione import COLLECTION, _catalogue_row, _connect, dettaglio
from lex.retrieval.normativa_catalog import runtime_general_path

# ID separati dagli ID dei due proprietari SQLite. Restano esatti anche in JSON.
ID_BASE = 10**12


def is_linked(identifier):
    return ID_BASE < identifier < 2 * ID_BASE


@contextmanager
def _linked_connection():
    index = os.getenv("IUSENTRA_BIBLIOTECA_CERDEF_INDICE")
    if not index:
        yield None
        return
    path = Path(index).resolve(strict=True)
    with closing(_connect(runtime_general_path())) as connection:
        connection.execute("ATTACH DATABASE ? AS cerdef", (path.as_uri()+"?mode=ro",))
        connection.execute("PRAGMA query_only=ON")
        yield connection


def linked_catalogue():
    with _linked_connection() as connection:
        if connection is None:
            return []
        rows = connection.execute("""
            SELECT d.id, d.titolo AS title, d.urn, d.redazione_id AS updated_at, d.xml_entry,
                   d.numero,d.data_atto,d.data_pubblicazione,i.articoli AS articles,i.tipo
            FROM cerdef.atti i JOIN normative_documents d ON d.id=i.document_id AND d.xml_sha256=i.sha256
            ORDER BY d.titolo COLLATE NOCASE, d.id
        """)
        catalogue = []
        for row in rows:
            item = dict(row)
            identifier = item["id"]
            item["collection"] = f"{COLLECTION}cerdef_{identifier}"
            year = item["data_atto"][:4]
            item["title"] = f"{item.pop('tipo').capitalize()} {item['numero']}/{year} — {item['title']}"
            item = _catalogue_row(item)
            item["id"] += ID_BASE
            catalogue.append(item)
        return catalogue


def _article_presentation(number, title, text):
    """Pulisce le etichette di importazione lasciando intatto il testo della fonte."""
    prefix = re.match(r"^Art(?:icolo)?\.?\s+", number, re.IGNORECASE)
    display_number = number[prefix.end():].strip().rstrip(".") if prefix else number
    if not re.match(r"^1\s+(?:Art\.|La Camera dei deputati\b)", title or "", re.IGNORECASE):
        return display_number, title
    same_number = re.escape(display_number)
    heading = re.match(
        rf"^Art\.\s*{same_number}\.\s*1\s+(?:La Camera dei deputati\b.{{0,500}}?)?"
        rf"Art\.\s*{same_number}\s+([^\n]{{1,180}}?)\s+1\.",
        text or "",
        flags=re.IGNORECASE,
    )
    return display_number, heading[1].strip() if heading else ""


def linked_articles(identifier, *, query="", article="", offset=0):
    document_id = identifier - ID_BASE
    with _linked_connection() as connection:
        if connection is None:
            return {"items": [], "total": 0, "act_id": identifier}
        where = ["i.document_id=?", "length(trim(coalesce(a.article_text,'')))>0"]
        params = [document_id]
        if article.strip():
            from lex.normativa.biblioteca.identita import numero_articolo, espressione_numero_articolo_sql
            where.append(espressione_numero_articolo_sql("a.article_number") + "=?")
            params.append(numero_articolo(article))
        if query.strip():
            from lex.ricerca_giuridica.testo import testo_indice
            terms = testo_indice(query[:300]).split()[:12]
            if not terms:
                return {"items": [], "total": 0, "act_id": identifier}
            where.append("""a.id IN (
                SELECT c.article_id FROM normative_fts f JOIN normative_chunks c ON c.id=f.rowid
                WHERE normative_fts MATCH ?
            )""")
            params.append(" AND ".join('"' + t.replace('"', '""') + '"' for t in terms))
        sql = """FROM cerdef.atti i
            JOIN normative_documents d ON d.id=i.document_id AND d.xml_sha256=i.sha256
            JOIN normative_articles a ON a.document_id=d.id WHERE """ + " AND ".join(where)
        total = connection.execute("SELECT count(*) " + sql, params).fetchone()[0]
        rows = connection.execute(
            "SELECT a.id,a.article_number AS number,a.article_title AS title,a.article_text AS body,d.titolo AS act_title "
            + sql + " ORDER BY a.id LIMIT 30 OFFSET ?", [*params, max(0, offset)]
        )
        items = []
        for row in rows:
            item = dict(row, id=row["id"] + ID_BASE)
            item["number"], item["title"] = _article_presentation(item["number"], item["title"], item.pop("body"))
            items.append(item)
    return {"items": items, "total": total, "act_id": identifier}


def linked_article(identifier):
    article_id = identifier - ID_BASE
    with _linked_connection() as connection:
        if connection is None or not connection.execute("""
            SELECT 1 FROM normative_articles a JOIN normative_documents d ON a.document_id=d.id
            JOIN cerdef.atti i ON i.document_id=d.id AND d.xml_sha256=i.sha256 WHERE a.id=? AND length(trim(coalesce(a.article_text,'')))>0
        """, (article_id,)).fetchone():
            return None
    item = dettaglio(runtime_general_path(), article_id, includi_archivio_generale=True)
    if item is not None:
        item["id"] = identifier
        item["number"], item["title"] = _article_presentation(item["number"], item["title"], item["text"])
    return item

