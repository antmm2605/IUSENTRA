"""
Importer XML Normattiva -> SQLite + JSONL chunks per Lex AI.

Uso tipico:
    python tools/normattiva_import.py --raw-dir data/normativa/raw --db data/normativa/normattiva.sqlite --jsonl data/normativa/index/normattiva_chunks.jsonl
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator, Any
from zipfile import ZipFile, BadZipFile
import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import sys

try:
    from lxml import etree
except Exception:  # pragma: no cover
    etree = None
    import xml.etree.ElementTree as ET

from lex.normativa.relevance_rules import detect_topics, relevance_score, topic_names


NIR_NS = {
    "nir": "http://www.normeinrete.it/nir/2.2/",
    "h": "http://www.w3.org/HTML/1998/html4",
}

TEXTUAL_ARTICLE_RE = re.compile(
    r"\bArt\.\s*(?P<number>\d{1,4})(?:[\s.-]+(?P<suffix>bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\s*[.)-]",
    flags=re.I,
)


@dataclass
class ArticleRecord:
    article_number: str | None
    article_title: str | None
    article_text: str
    topics: list[str]
    relevance_score: float


@dataclass
class DocumentRecord:
    collection_name: str
    zip_path: str
    xml_entry: str
    tipo_atto: str | None
    numero: str | None
    data_atto: str | None
    data_pubblicazione: str | None
    titolo: str | None
    urn: str | None
    redazione_id: str | None
    vigenza: str | None
    xml_sha256: str
    text_content: str
    topics: list[str]
    relevance_score: float
    is_relevant: bool
    articles: list[ArticleRecord]


@dataclass
class ImportStats:
    zip_files: int = 0
    xml_seen: int = 0
    documents_imported: int = 0
    documents_skipped_not_relevant: int = 0
    articles_imported: int = 0
    chunks_written: int = 0
    errors: int = 0


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def norm_date(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return clean_text(value) or None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def infer_collection_from_zip(zip_path: Path) -> str:
    name = zip_path.stem
    # Esempio: Regolamenti_ministeriali_XML_ORIGINALE_2026-04-26
    name = re.sub(r"_XML_(ORIGINALE|VIGENTE)_\d{4}-\d{2}-\d{2}$", "", name, flags=re.I)
    name = name.replace("_", " ")
    return clean_text(name) or zip_path.stem


def infer_vigenza_from_name(value: str) -> str | None:
    m = re.search(r"_(ORIGINALE|VIGENTE)_", value, flags=re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r"VIGENZA[_-](\d{4}-\d{2}-\d{2}|\d{8})", value, flags=re.I)
    if m:
        return "VIGENTE"
    return None


def infer_tipo_atto_from_entry(entry: str) -> str | None:
    base = Path(entry).name
    prefix = base.split("_")[0] if "_" in base else None
    if prefix and len(prefix) > 2:
        return clean_text(prefix.title())
    # Se il file è dentro una cartella tipo DECRETO_20250311_67
    parts = entry.replace("\\", "/").split("/")
    if len(parts) > 1:
        first = parts[0].split("_")[0]
        if first:
            return clean_text(first.title())
    return None


def parse_xml(xml_bytes: bytes, *, zip_path: Path, entry: str, collection_name: str) -> DocumentRecord:
    if etree is not None:
        parser = etree.XMLParser(recover=True, huge_tree=True, encoding="utf-8")
        root = etree.fromstring(xml_bytes, parser=parser)
        xpath = lambda expr: root.xpath(expr, namespaces=NIR_NS)
        string = lambda expr: clean_text(root.xpath(f"string({expr})", namespaces=NIR_NS))

        titolo = string(".//nir:titoloDoc")
        data_atto = norm_date(string(".//nir:dataDoc/@norm") or string(".//nir:dataDoc"))
        numero = string(".//nir:numDoc")
        tipo_atto = string(".//nir:tipoDoc") or infer_tipo_atto_from_entry(entry)
        urn = string(".//nir:urn/@valore")
        redazione_id = string(".//nir:redazione/@id")
        data_pubblicazione = norm_date(string(".//nir:pubblicazione/@norm"))
        full_text = clean_text(" ".join(root.xpath(".//text()")))

        articles: list[ArticleRecord] = []
        for art in root.xpath(".//*[local-name()='articolo']"):
            art_num = clean_text(" ".join(art.xpath("./*[local-name()='num']//text()"))) or None
            art_text = clean_text(" ".join(art.xpath(".//text()")))
            art_title = _guess_article_title(art_text, art_num)
            art_matches = detect_topics(titolo or "", art_text, collection_name=collection_name)
            articles.append(ArticleRecord(
                article_number=art_num,
                article_title=art_title,
                article_text=art_text,
                topics=topic_names(art_matches),
                relevance_score=relevance_score(art_matches),
            ))
        articles = _merge_textual_articles(
            articles,
            extract_textual_article_records(full_text, source_title=titolo or "", collection_name=collection_name),
        )
    else:
        root = ET.fromstring(xml_bytes)  # type: ignore[name-defined]
        titolo = _find_text_et(root, "titoloDoc")
        data_atto = norm_date(_find_attr_et(root, "dataDoc", "norm") or _find_text_et(root, "dataDoc"))
        numero = _find_text_et(root, "numDoc")
        tipo_atto = _find_text_et(root, "tipoDoc") or infer_tipo_atto_from_entry(entry)
        urn = _find_attr_et(root, "urn", "valore")
        redazione_id = _find_attr_et(root, "redazione", "id")
        data_pubblicazione = norm_date(_find_attr_et(root, "pubblicazione", "norm"))
        full_text = clean_text(" ".join(root.itertext()))
        articles = extract_textual_article_records(full_text, source_title=titolo or "", collection_name=collection_name)

    matches = detect_topics(titolo or "", full_text[:50000], collection_name=collection_name)
    score = relevance_score(matches)
    topics = topic_names(matches)

    return DocumentRecord(
        collection_name=collection_name,
        zip_path=str(zip_path),
        xml_entry=entry,
        tipo_atto=tipo_atto,
        numero=numero or None,
        data_atto=data_atto,
        data_pubblicazione=data_pubblicazione,
        titolo=titolo or None,
        urn=urn or None,
        redazione_id=redazione_id or None,
        vigenza=infer_vigenza_from_name(zip_path.name) or infer_vigenza_from_name(entry),
        xml_sha256=sha256_bytes(xml_bytes),
        text_content=full_text,
        topics=topics,
        relevance_score=score,
        is_relevant=score > 0,
        articles=articles,
    )


def _guess_article_title(article_text: str, art_num: str | None) -> str | None:
    text = article_text
    if art_num:
        text = text.replace(art_num, "", 1).strip()
    # Prende una riga/titolo breve iniziale, evitando testi troppo lunghi.
    parts = re.split(r"(?<=\.)\s+|\s{2,}", text)
    for part in parts[:6]:
        part = clean_text(part)
        if 4 <= len(part) <= 140 and not re.match(r"^\d+\.?$", part):
            return part
    return None


def extract_textual_article_records(
    text: str,
    *,
    source_title: str = "",
    collection_name: str = "",
) -> list[ArticleRecord]:
    """Estrae articoli quando Normattiva codifica il corpo come paragrafi HTML.

    Alcuni codici storici arrivano con pochi nodi NIR ``articolo`` e il testo
    vero dentro paragrafi ``h:p``. Questo splitter conserva il comportamento
    XML esistente ma rende indicizzabili gli articoli del corpo normativo.
    """
    cleaned = clean_text(text)
    matches = list(TEXTUAL_ARTICLE_RE.finditer(cleaned))
    records: list[ArticleRecord] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        article_text = clean_text(cleaned[match.start() : end])
        if len(article_text) < 24:
            continue
        number = _article_number_from_match(match)
        article_title = _guess_article_title(article_text, number)
        matches_topics = detect_topics(source_title, article_text, collection_name=collection_name)
        records.append(
            ArticleRecord(
                article_number=number,
                article_title=article_title,
                article_text=article_text,
                topics=topic_names(matches_topics),
                relevance_score=relevance_score(matches_topics),
            )
        )
    return records


def _article_number_from_match(match: re.Match[str]) -> str:
    suffix = clean_text(match.group("suffix")).lower()
    number = clean_text(match.group("number"))
    return f"Art. {number}{f' {suffix}' if suffix else ''}."


def _merge_textual_articles(existing: list[ArticleRecord], textual: list[ArticleRecord]) -> list[ArticleRecord]:
    if not textual:
        return existing
    seen = {
        (
            clean_text(article.article_number).lower(),
            clean_text(article.article_text)[:220].lower(),
        )
        for article in existing
    }
    merged = list(existing)
    for article in textual:
        key = (clean_text(article.article_number).lower(), clean_text(article.article_text)[:220].lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(article)
    return merged


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_text_et(root: Any, local_name: str) -> str | None:
    for elem in root.iter():
        if _local_name(elem.tag) == local_name:
            return clean_text(" ".join(elem.itertext()))
    return None


def _find_attr_et(root: Any, local_name: str, attr: str) -> str | None:
    for elem in root.iter():
        if _local_name(elem.tag) == local_name:
            return elem.attrib.get(attr)
    return None


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS normative_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_name TEXT,
            zip_path TEXT,
            xml_entry TEXT,
            tipo_atto TEXT,
            numero TEXT,
            data_atto TEXT,
            data_pubblicazione TEXT,
            titolo TEXT,
            urn TEXT,
            redazione_id TEXT,
            vigenza TEXT,
            xml_sha256 TEXT UNIQUE,
            topics TEXT,
            relevance_score REAL DEFAULT 0,
            is_relevant INTEGER DEFAULT 0,
            text_content TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS normative_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            article_number TEXT,
            article_title TEXT,
            article_text TEXT,
            topics TEXT,
            relevance_score REAL DEFAULT 0,
            embedding_id TEXT,
            FOREIGN KEY(document_id) REFERENCES normative_documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS normative_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            article_id INTEGER,
            chunk_key TEXT UNIQUE,
            chunk_text TEXT NOT NULL,
            metadata_json TEXT,
            embedding_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(document_id) REFERENCES normative_documents(id) ON DELETE CASCADE,
            FOREIGN KEY(article_id) REFERENCES normative_articles(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS normative_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_dir TEXT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            zip_files INTEGER NOT NULL DEFAULT 0,
            xml_seen INTEGER NOT NULL DEFAULT 0,
            documents_imported INTEGER NOT NULL DEFAULT 0,
            chunks_written INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            report_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE VIEW IF NOT EXISTS normattiva_documents AS SELECT * FROM normative_documents;
        CREATE VIEW IF NOT EXISTS normattiva_articles AS SELECT * FROM normative_articles;
        CREATE VIEW IF NOT EXISTS normattiva_chunks AS SELECT * FROM normative_chunks;

        CREATE INDEX IF NOT EXISTS idx_normative_documents_collection ON normative_documents(collection_name);
        CREATE INDEX IF NOT EXISTS idx_normative_documents_topics ON normative_documents(topics);
        CREATE INDEX IF NOT EXISTS idx_normative_articles_document ON normative_articles(document_id);
        CREATE INDEX IF NOT EXISTS idx_normative_chunks_document ON normative_chunks(document_id);
        """
    )
    conn.commit()


def insert_document(conn: sqlite3.Connection, doc: DocumentRecord, *, store_full_text: bool) -> int | None:
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO normative_documents
            (collection_name, zip_path, xml_entry, tipo_atto, numero, data_atto, data_pubblicazione,
             titolo, urn, redazione_id, vigenza, xml_sha256, topics, relevance_score, is_relevant, text_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.collection_name,
                doc.zip_path,
                doc.xml_entry,
                doc.tipo_atto,
                doc.numero,
                doc.data_atto,
                doc.data_pubblicazione,
                doc.titolo,
                doc.urn,
                doc.redazione_id,
                doc.vigenza,
                doc.xml_sha256,
                safe_json(doc.topics),
                doc.relevance_score,
                1 if doc.is_relevant else 0,
                doc.text_content if store_full_text else None,
            ),
        )
        if cur.rowcount == 0:
            existing = conn.execute("SELECT id FROM normative_documents WHERE xml_sha256 = ?", (doc.xml_sha256,)).fetchone()
            return int(existing[0]) if existing else None
        return int(cur.lastrowid)
    except sqlite3.Error as exc:
        raise RuntimeError(f"Errore inserimento documento {doc.xml_entry}: {exc}") from exc


def insert_articles_and_chunks(
    conn: sqlite3.Connection,
    doc_id: int,
    doc: DocumentRecord,
    *,
    jsonl_file,
    max_chunk_chars: int,
    only_relevant_articles: bool,
) -> tuple[int, int]:
    articles_count = 0
    chunks_count = 0

    source_title = doc.titolo or doc.xml_entry
    base_meta = {
        "source": "Normattiva Open Data",
        "collection_name": doc.collection_name,
        "tipo_atto": doc.tipo_atto,
        "numero": doc.numero,
        "data_atto": doc.data_atto,
        "data_pubblicazione": doc.data_pubblicazione,
        "titolo": doc.titolo,
        "urn": doc.urn,
        "redazione_id": doc.redazione_id,
        "vigenza": doc.vigenza,
        "zip_path": doc.zip_path,
        "xml_entry": doc.xml_entry,
        "document_sha256": doc.xml_sha256,
        "topics": doc.topics,
        "relevance_score": doc.relevance_score,
    }

    if doc.articles:
        for index, article in enumerate(doc.articles, start=1):
            if only_relevant_articles and doc.is_relevant and article.relevance_score == 0 and doc.relevance_score < 3:
                continue
            cur = conn.execute(
                """
                INSERT INTO normative_articles
                (document_id, article_number, article_title, article_text, topics, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    article.article_number,
                    article.article_title,
                    article.article_text,
                    safe_json(article.topics),
                    article.relevance_score,
                ),
            )
            article_id = int(cur.lastrowid)
            articles_count += 1
            meta = dict(base_meta)
            meta.update({
                "article_number": article.article_number,
                "article_title": article.article_title,
                "article_id": article_id,
                "article_topics": article.topics,
                "article_relevance_score": article.relevance_score,
            })
            for chunk_index, chunk_text in enumerate(chunk_texts(article.article_text, max_chunk_chars=max_chunk_chars), start=1):
                chunk_key = f"normattiva:{doc.xml_sha256}:art{index}:chunk{chunk_index}"
                chunks_count += insert_chunk(conn, doc_id, article_id, chunk_key, chunk_text, meta, jsonl_file)
    else:
        for chunk_index, chunk_text in enumerate(chunk_texts(doc.text_content, max_chunk_chars=max_chunk_chars), start=1):
            chunk_key = f"normattiva:{doc.xml_sha256}:doc:chunk{chunk_index}"
            chunks_count += insert_chunk(conn, doc_id, None, chunk_key, chunk_text, base_meta, jsonl_file)

    return articles_count, chunks_count


def insert_chunk(conn: sqlite3.Connection, doc_id: int, article_id: int | None, chunk_key: str, chunk_text: str, metadata: dict[str, Any], jsonl_file) -> int:
    metadata_json = safe_json(metadata)
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO normative_chunks
        (document_id, article_id, chunk_key, chunk_text, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (doc_id, article_id, chunk_key, chunk_text, metadata_json),
    )
    if cur.rowcount:
        payload = {
            "id": chunk_key,
            "text": chunk_text,
            "metadata": metadata,
        }
        jsonl_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 1
    return 0


def chunk_texts(text: str, *, max_chunk_chars: int = 1800) -> Iterator[str]:
    text = clean_text(text)
    if not text:
        return
    if len(text) <= max_chunk_chars:
        yield text
        return

    sentences = re.split(r"(?<=[.;:!?])\s+", text)
    buf: list[str] = []
    size = 0
    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        if size + len(s) + 1 > max_chunk_chars and buf:
            yield clean_text(" ".join(buf))
            # piccola sovrapposizione: mantiene l'ultima frase come contesto
            buf = buf[-1:]
            size = sum(len(x) for x in buf)
        buf.append(s)
        size += len(s) + 1
    if buf:
        yield clean_text(" ".join(buf))


def iter_zip_xml(zip_path: Path) -> Iterator[tuple[str, bytes]]:
    with ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if name.lower().endswith(".xml"):
                yield name, z.read(name)


def import_raw_dir(
    *,
    raw_dir: Path,
    db_path: Path,
    jsonl_path: Path,
    min_score: float = 1.0,
    only_relevant: bool = True,
    store_full_text: bool = False,
    max_chunk_chars: int = 1800,
    limit: int | None = None,
) -> ImportStats:
    stats = ImportStats()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    zip_files = sorted(raw_dir.glob("*.zip"))
    stats.zip_files = len(zip_files)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn)
    run_id = conn.execute(
        "INSERT INTO normative_sync_runs(raw_dir, status) VALUES (?, ?)",
        (str(raw_dir), "running"),
    ).lastrowid
    conn.commit()

    with jsonl_path.open("w", encoding="utf-8") as jf:
        for zip_path in zip_files:
            collection_name = infer_collection_from_zip(zip_path)
            print(f"\nZIP: {zip_path.name}")
            try:
                for entry, xml_bytes in iter_zip_xml(zip_path):
                    if limit is not None and stats.xml_seen >= limit:
                        conn.execute(
                            """
                            UPDATE normative_sync_runs
                            SET finished_at=CURRENT_TIMESTAMP, status=?, zip_files=?, xml_seen=?,
                                documents_imported=?, chunks_written=?, errors=?, report_json=?
                            WHERE id=?
                            """,
                            (
                                "ok",
                                stats.zip_files,
                                stats.xml_seen,
                                stats.documents_imported,
                                stats.chunks_written,
                                stats.errors,
                                safe_json(asdict(stats)),
                                run_id,
                            ),
                        )
                        conn.commit()
                        conn.close()
                        return stats
                    stats.xml_seen += 1
                    try:
                        doc = parse_xml(xml_bytes, zip_path=zip_path, entry=entry, collection_name=collection_name)
                        if only_relevant and doc.relevance_score < min_score:
                            stats.documents_skipped_not_relevant += 1
                            continue
                        doc.is_relevant = doc.relevance_score >= min_score
                        doc_id = insert_document(conn, doc, store_full_text=store_full_text)
                        if doc_id is None:
                            continue
                        stats.documents_imported += 1
                        a_count, c_count = insert_articles_and_chunks(
                            conn,
                            doc_id,
                            doc,
                            jsonl_file=jf,
                            max_chunk_chars=max_chunk_chars,
                            only_relevant_articles=True,
                        )
                        stats.articles_imported += a_count
                        stats.chunks_written += c_count
                        if stats.documents_imported % 100 == 0:
                            conn.commit()
                            print(f"  importati: {stats.documents_imported} documenti, chunks: {stats.chunks_written}")
                    except Exception as exc:
                        stats.errors += 1
                        print(f"  ERRORE XML {entry}: {exc}", file=sys.stderr)
            except BadZipFile as exc:
                stats.errors += 1
                print(f"ERRORE ZIP {zip_path}: {exc}", file=sys.stderr)
            conn.commit()

    conn.execute(
        """
        UPDATE normative_sync_runs
        SET finished_at=CURRENT_TIMESTAMP, status=?, zip_files=?, xml_seen=?,
            documents_imported=?, chunks_written=?, errors=?, report_json=?
        WHERE id=?
        """,
        (
            "ok" if stats.errors == 0 else "completed_with_errors",
            stats.zip_files,
            stats.xml_seen,
            stats.documents_imported,
            stats.chunks_written,
            stats.errors,
            safe_json(asdict(stats)),
            run_id,
        ),
    )
    conn.commit()
    conn.close()
    return stats


def write_report(stats: ImportStats, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(stats)
    payload["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cli_main() -> None:
    parser = argparse.ArgumentParser(description="Importa XML Normattiva scaricati in SQLite + JSONL per Lex AI")
    parser.add_argument("--raw-dir", default="data/normativa/raw", help="Cartella con ZIP Normattiva")
    parser.add_argument("--db", default="data/normativa/normattiva.sqlite", help="Database SQLite output")
    parser.add_argument("--jsonl", default="data/normativa/index/normattiva_chunks.jsonl", help="File JSONL chunks per RAG")
    parser.add_argument("--report", default="data/normativa/reports/normattiva_import_report.json", help="Report import")
    parser.add_argument("--min-score", type=float, default=1.0, help="Soglia rilevanza")
    parser.add_argument("--include-not-relevant", action="store_true", help="Importa anche norme non rilevanti")
    parser.add_argument("--store-full-text", action="store_true", help="Salva testo completo in SQLite; aumenta molto il DB")
    parser.add_argument("--max-chunk-chars", type=int, default=1800, help="Dimensione massima chunk RAG")
    parser.add_argument("--limit", type=int, default=None, help="Limita numero XML per test")
    args = parser.parse_args()

    stats = import_raw_dir(
        raw_dir=Path(args.raw_dir),
        db_path=Path(args.db),
        jsonl_path=Path(args.jsonl),
        min_score=args.min_score,
        only_relevant=not args.include_not_relevant,
        store_full_text=args.store_full_text,
        max_chunk_chars=args.max_chunk_chars,
        limit=args.limit,
    )
    write_report(stats, Path(args.report))
    print("\nImport completato")
    print(json.dumps(asdict(stats), ensure_ascii=False, indent=2))
    print(f"DB: {args.db}")
    print(f"JSONL: {args.jsonl}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    cli_main()
