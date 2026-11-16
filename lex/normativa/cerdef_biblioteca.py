"""Vista in sola lettura degli atti CeRDEF già conservati in Normattiva."""
from contextlib import closing, contextmanager
from functools import partial
import hashlib
import os
import re
from pathlib import Path

from lex.normativa.consultazione import COLLECTION, _catalogue_row, _connect, dettaglio
from lex.retrieval.normativa_catalog import biblioteca_studio_path, runtime_general_path

# ID separati dagli ID dei due proprietari SQLite. Restano esatti anche in JSON.
ID_BASE = 10**12
VIGENTE_BASE = 3 * ID_BASE
STORICO_ORIGINALE_BASE = 4 * ID_BASE


def is_linked(identifier):
    return ID_BASE < identifier < 5 * ID_BASE and identifier not in (2 * ID_BASE, VIGENTE_BASE, STORICO_ORIGINALE_BASE)


_ARCHIVI = {
    2 * ID_BASE: ("IUSENTRA_BIBLIOTECA_CERDEF_ARCHIVIO", "cerdef-archivio.sqlite"),
    VIGENTE_BASE: ("IUSENTRA_BIBLIOTECA_VIGENTE_DB", "vigente.sqlite"),
    STORICO_ORIGINALE_BASE: ("IUSENTRA_BIBLIOTECA_ORIGINALI_DB", "originali.sqlite"),
}
_INDICI = {
    ID_BASE: ("IUSENTRA_BIBLIOTECA_CERDEF_INDICE", "cerdef-indice.sqlite"),
    2 * ID_BASE: ("IUSENTRA_BIBLIOTECA_CERDEF_INDICE_ARCHIVIO", "cerdef-archivio-indice.sqlite"),
    VIGENTE_BASE: ("IUSENTRA_BIBLIOTECA_VIGENTE_INDICE", "vigente-indice.sqlite"),
    STORICO_ORIGINALE_BASE: ("IUSENTRA_BIBLIOTECA_ORIGINALI_INDICE", "originali-indice.sqlite"),
}


def _fonte(configurazione):
    variabile, nome = configurazione
    configurata = os.getenv(variabile)
    if configurata:
        return Path(configurata)
    studio = biblioteca_studio_path()
    if studio and (studio / nome).is_file():
        return studio / nome
    return None


def linked_archive(identifier):
    base = identifier // ID_BASE * ID_BASE
    if base == ID_BASE:
        return runtime_general_path(), base
    path = _fonte(_ARCHIVI[base])
    if path is None:
        raise FileNotFoundError("L’edizione richiesta non è disponibile.")
    return path, base


def fonti_catalogo(base):
    index = _fonte(_INDICI[base])
    if not index:
        return None
    database, _ = linked_archive(base + 1)
    return Path(index), database


@contextmanager
def _linked_connection(base=ID_BASE, *, source=None):
    source = source if source is not None else fonti_catalogo(base)
    if source is None:
        yield None
        return
    index, database = source
    path = index.resolve(strict=True)
    with closing(_connect(database)) as connection:
        connection.execute("ATTACH DATABASE ? AS cerdef", (path.as_uri()+"?mode=ro",))
        connection.execute("PRAGMA query_only=ON")
        yield connection


def linked_catalogue():
    return _catalogue(ID_BASE) + _catalogue(2 * ID_BASE)


def alias_originali_storici():
    with _linked_connection(STORICO_ORIGINALE_BASE) as connection:
        aliases = {} if connection is None else {
            old: STORICO_ORIGINALE_BASE + original
            for old, original in connection.execute("SELECT id_precedente,id_originale FROM cerdef.alias_storici")
        }
    return aliases


def originali_storici():
    return _catalogue(STORICO_ORIGINALE_BASE), alias_originali_storici()


def riscontro_vigente(numero_atti):
    with _linked_connection(VIGENTE_BASE) as connection:
        if connection is None:
            return None
        row = connection.execute("SELECT data, atti_richiesti FROM cerdef.riscontro").fetchone()
        esaminate = connection.execute(
            "SELECT count(*) FROM (SELECT DISTINCT codice,gu FROM cerdef.esiti)"
        ).fetchone()[0]
    if row is None:
        return None
    return {"data": row[0], "atti_richiesti": row[1], "atti_esaminati": esaminate,
            "atti_con_testo_verificato": numero_atti}


def vigente_catalogue():
    items = _catalogue(VIGENTE_BASE)
    return items, riscontro_vigente(len(items))


def _catalogue(base, *, source=None):
    with _linked_connection(base, source=source) as connection:
        if connection is None:
            return []
        rows = connection.execute("""
            SELECT d.id, d.titolo AS title, d.urn, d.redazione_id AS updated_at, d.xml_entry,
                   d.numero,d.data_atto,d.data_pubblicazione,i.articoli AS articles,i.tipo
            FROM cerdef.atti i CROSS JOIN normative_documents d ON d.id=i.document_id AND d.xml_sha256=i.sha256
            ORDER BY d.titolo COLLATE NOCASE, d.id
        """)
        replacements = set()
        if connection.execute(
            "SELECT 1 FROM cerdef.sqlite_master WHERE type='table' AND name='catalogo_sostituito'"
        ).fetchone():
            replacements = {
                row[0] for row in connection.execute("SELECT document_id FROM cerdef.catalogo_sostituito")
            }
        notices = set()
        if connection.execute(
            "SELECT 1 FROM cerdef.sqlite_master WHERE type='table' AND name='catalogo_avvisi'"
        ).fetchone():
            notices = {
                row[0] for row in connection.execute("SELECT document_id FROM cerdef.catalogo_avvisi")
            }
        catalogue = []
        for row in rows:
            if row["id"] in replacements:
                continue
            item = dict(row)
            identifier = item["id"]
            collection_key = f"cerdef_{identifier}"
            if (item["urn"] or "").startswith("urn:nir:unione.europea:regolamento:") and item["numero"]:
                collection_key = f'reg_ue_{item["data_atto"][:4]}_{item["numero"]}'
            elif (item["urn"] or "").startswith("urn:cnf:codice.deontologico:"):
                collection_key = "codice_deontologico_forense_2026"
            item["collection"] = f"{COLLECTION}{collection_key}"
            year = item["data_atto"][:4]
            kind = item.pop("tipo").replace(".", " ").capitalize()
            number = str(item["numero"] or "").strip()
            reference = f"{number}/{year}" if number and number != "0" else item["data_atto"]
            edition = " [edizione archiviata]" if base == 2 * ID_BASE else ""
            if base == STORICO_ORIGINALE_BASE:
                edition = " [edizione originaria archiviata]"
            if identifier in notices:
                edition = " [avviso di abrogazione; testo storico non incluso]"
            prefix = f"{kind} {reference}"
            title = item["title"]
            initial, separator, rest = title.partition(" — ")
            if separator and initial.casefold() == prefix.casefold():
                prefix, title = initial, rest
            item["title"] = f"{prefix}{edition} — {title}"
            item = _catalogue_row(item)
            item["id"] += base
            catalogue.append(item)
        return catalogue


def _rubrica_acn(rubrica, testo, documento_sha256):
    """Recupera la rubrica assente della versione ACN confrontata con il PDF."""
    if rubrica or documento_sha256 != "a26d46b2b763f41272e47ad0c31084ae46aa11f51d775e4e924ef6c06acb8994":
        return rubrica
    heading = re.match(r"^\((.{1,220}?)\)\s+1\.", testo)
    return heading[1] if heading else rubrica


def _article_presentation(number, title, text):
    """Pulisce le etichette di importazione lasciando intatto il testo della fonte."""
    prefix = re.match(r"^Art(?:icolo)?\.?\s+", number, re.IGNORECASE)
    display_number = number[prefix.end():].strip().rstrip(".") if prefix else number
    if not (title or "").strip():
        heading = re.match(
            rf"^\s*Art(?:icolo)?\.?\s+{re.escape(display_number)}[.\s]+"
            r"\(([^()\n]{1,180})\)\s*(?:[.\n]|$)",
            text or "",
            flags=re.IGNORECASE,
        )
        if heading and any(char.isalpha() for char in heading[1]):
            return display_number, heading[1].strip()
        return display_number, title
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


def ricerca_storica(database, *, query="", article="", category="", offset=0):
    from lex.normativa.consultazione import articoli
    if not (query.strip() or article.strip()):
        return {"items": [], "total": 0, "act_id": 0}
    search = dict(query=query, article=article, category=category)
    readers = [partial(articoli, database, escludi_atti=tuple(alias_originali_storici()))]
    readers.extend(partial(linked_articles, 0, archive_base=base)
                   for base in (ID_BASE, 2 * ID_BASE, STORICO_ORIGINALE_BASE))
    items, total = [], 0
    for read in readers:
        remaining = 30 - len(items)
        result = read(**search, offset=offset, limit=max(1, remaining))
        total += result["total"]
        items.extend(result["items"][:remaining])
        offset = max(0, offset - result["total"])
    return {"items": items, "total": total, "act_id": 0}


def linked_articles(identifier, *, query="", article="", offset=0, vigente=False,
                    category="", archive_base=None, limit=30):
    if vigente and identifier and not VIGENTE_BASE < identifier < 4 * ID_BASE:
        return {"items": [], "total": 0, "act_id": identifier}
    base = VIGENTE_BASE if vigente else archive_base or linked_archive(identifier)[1]
    document_id = identifier - base if identifier else None
    if document_id is None and not (query.strip() or article.strip()):
        return {"items": [], "total": 0, "act_id": identifier}
    category_documents = None
    if category and (vigente or archive_base is not None):
        category_documents = [item["id"] - base for item in _catalogue(base) if item["category"] == category]
        if not category_documents:
            return {"items": [], "total": 0, "act_id": identifier}
    with _linked_connection(base) as connection:
        if connection is None:
            return {"items": [], "total": 0, "act_id": identifier}
        where = ["length(trim(coalesce(a.article_text,'')))>0"]
        params = []
        if document_id is None and connection.execute(
            "SELECT 1 FROM cerdef.sqlite_master WHERE name='catalogo_sostituito' AND type='table'"
        ).fetchone():
            where.append("NOT EXISTS (SELECT 1 FROM cerdef.catalogo_sostituito s WHERE s.document_id=i.document_id)")
        if document_id is not None:
            where.append("i.document_id=?")
            params.append(document_id)
        if category_documents is not None:
            where.append("i.document_id IN (" + ",".join("?" for _ in category_documents) + ")")
            params.extend(category_documents)
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
            "SELECT a.id,a.article_number AS number,a.article_title AS title,a.article_text AS body,d.titolo AS act_title,d.xml_sha256 AS document_sha256 "
            + sql + " ORDER BY a.id LIMIT ? OFFSET ?", [*params, limit, max(0, offset)]
        )
        items = []
        for row in rows:
            item = dict(row, id=row["id"] + base)
            body = item.pop("body")
            title = _rubrica_acn(item["title"], body, item.pop("document_sha256"))
            item["number"], item["title"] = _article_presentation(item["number"], title, body)
            if base == STORICO_ORIGINALE_BASE:
                part = connection.execute("SELECT parte FROM cerdef.parti WHERE article_id=?", (row["id"],)).fetchone()
                if part and part[0] != "corpo_principale":
                    item["title"] = f"{part[0]} · {item['title']}" if item["title"] else part[0]
            items.append(item)
    return {"items": items, "total": total, "act_id": identifier}


# Puntuali Normattiva del 13/11/2026: la data vale esclusivamente per i corpi confrontati.
_RISCONTRI_ARTICOLI_VIGENTI = {
    ("urn:nir:stato:regio.decreto:1942-03-16;262", "2043"):
        "d103379584946b25b239b1b8f926ffee6a92fbb0021552dbe73d9fea9a075dbf",
    ("urn:nir:stato:regio.decreto:1940-10-28;1443", "155"):
        "3cba1fdfd8bc3e7826b225f684684b8717a40f035db02984fe4afa5bd174ccbe",
}


def linked_article(identifier):
    database, base = linked_archive(identifier)
    article_id = identifier - base
    with _linked_connection(base) as connection:
        if connection is None or not connection.execute("""
            SELECT 1 FROM normative_articles a JOIN normative_documents d ON a.document_id=d.id
            JOIN cerdef.atti i ON i.document_id=d.id AND d.xml_sha256=i.sha256 WHERE a.id=? AND length(trim(coalesce(a.article_text,'')))>0
        """, (article_id,)).fetchone():
            return None
    item = dettaglio(database, article_id, includi_archivio_generale=True)
    if item is not None:
        title = _rubrica_acn(item["title"], item["text"], item.get("document_sha256"))
        item["number"], item["title"] = _article_presentation(item["number"], title, item["text"])
        if base == VIGENTE_BASE:
            with _linked_connection(base) as connection:
                reviewed = None
                if connection.execute(
                    "SELECT 1 FROM cerdef.sqlite_master WHERE type='table' AND name='riscontri_atti'"
                ).fetchone():
                    reviewed = connection.execute(
                        """SELECT r.data FROM cerdef.riscontri_atti r
                           JOIN cerdef.atti i ON i.document_id=r.document_id AND i.sha256=r.sha256
                           WHERE r.document_id=? AND r.sha256=?""",
                        (item["document_id"], item["document_sha256"]),
                    ).fetchone()
                if reviewed is None:
                    reviewed = connection.execute("SELECT data FROM cerdef.riscontro").fetchone()
                if reviewed is not None:
                    item["verified_as_of"] = reviewed[0]
                expected = _RISCONTRI_ARTICOLI_VIGENTI.get((item["urn"], item["number"]))
                if expected and hashlib.sha256(item["text"].encode()).hexdigest() == expected:
                    item["verified_as_of"] = max(item.get("verified_as_of", ""), "2026-11-13")

        item["id"] = identifier
    return item

