"""Read-only owner of the shared public SentenzeWeb corpus."""

import os
import re
import sqlite3
from pathlib import Path
from contextlib import closing
from urllib.parse import urlsplit

from pct.giurisprudenza_corpus import _COLONNE_RICERCA, GestioneCorpusGiurisprudenza


_SOURCE_NOTICE = re.compile(
    r"[!.,:;\s]*corte suprema di cassazione italgiureweb "
    r"la sentenza richiesta è in fase di (?:valutazione (?:per )?)?oscuramento(?:\s*\S{0,2})?"
)


def source_text_status(text):
    """Recognize observed source notices; never infer completeness from length."""
    normalized = " ".join(str(text or "").split()).casefold()
    if not normalized:
        return "empty"
    if normalized in {"in fase di valutazione oscuramento", "in fase di oscuramento"} or _SOURCE_NOTICE.fullmatch(normalized):
        return "source_notice"
    return "content_unreviewed"


def body_available(text):
    return source_text_status(text) == "content_unreviewed"


def text_provenance(text, documents):
    """Stored provenance tied to the active text, not an approval or new source read."""
    if not body_available(text):
        return {"text_source_url": "", "text_source_official": None}
    for document in sorted(documents, key=lambda item: bool(item.get("ufficiale")), reverse=True):
        if document.get("testo_estratto") != text or not document.get("valido", True):
            continue
        url = str(document.get("url_origine") or "")
        try:
            parsed = urlsplit(url)
            allowed = (parsed.scheme == "https" and parsed.hostname in {"www.italgiure.giustizia.it", "www.cortedicassazione.it", "www.misterlex.it"}
                       and not parsed.username and not parsed.password and parsed.port in {None, 443})
        except ValueError:
            allowed = False
        if allowed:
            return {"text_source_url": url, "text_source_official": bool(document.get("ufficiale"))}
    return {"text_source_url": "", "text_source_official": None}


class PublicSentenzeWebCorpus(GestioneCorpusGiurisprudenza):
    def __init__(self, path):
        self.db_path = str(Path(path).resolve(strict=True))
        with closing(self._connect()) as connection:
            foreign_sources = connection.execute(
                "SELECT count(*) FROM fonti_giurisprudenza WHERE codice != ?", ("cassazione_sentenzeweb",)
            ).fetchone()[0]
            if foreign_sources:
                raise ValueError("The shared corpus contains sources outside its public owner")

    def _guard_text_availability(self, rows):
        """One bounded read for selected hits, never a corpus scan or extraction."""
        if not rows:
            return rows
        ids = [int(row["id"]) for row in rows]
        states = {}
        texts = {}
        documents = {}
        with closing(self._connect()) as connection:
            for start in range(0, len(ids), 500):
                batch = ids[start:start + 500]
                placeholders = ",".join("?" for _ in batch)
                for row in connection.execute(f"SELECT id,testo_integrale FROM sentenze WHERE id IN ({placeholders})", batch):
                    texts[int(row["id"])] = str(row["testo_integrale"] or "")
                    states[int(row["id"])] = source_text_status(row["testo_integrale"])
                for row in connection.execute(
                    f"SELECT sentenza_id,ufficiale,url_origine,testo_estratto,valido FROM documenti_sentenza WHERE sentenza_id IN ({placeholders})", batch
                ):
                    documents.setdefault(int(row["sentenza_id"]), []).append(dict(row))
        for row in rows:
            ident = int(row["id"])
            state = states.get(ident, "empty")
            row["source_text_status"] = state
            row["testo_integrale_presente"] = state == "content_unreviewed"
            row.update(text_provenance(texts.get(ident, ""), documents.get(ident, [])))
        return rows

    def cerca_sentenze(self, **kwargs):
        return self._guard_text_availability(super().cerca_sentenze(**kwargs))

    def get_sentenza(self, sentenza_id):
        record = super().get_sentenza(sentenza_id)
        if record is None:
            return None
        state = source_text_status(record.get("testo_integrale"))
        record["source_text_status"] = state
        record.update(text_provenance(str(record.get("testo_integrale") or ""), record.get("documenti", [])))
        record["testo_integrale_presente"] = state == "content_unreviewed"
        if state != "content_unreviewed":
            # The source notice remains in its original document, not as decision text.
            record["testo_integrale"] = ""
        return record

    def can_cite_sentenza(self, record):
        if not record or not record.get("testo_integrale_presente"):
            return False
        if record.get("source_text_status") in {"empty", "source_notice"}:
            return False
        if "testo_integrale" in record and not body_available(record["testo_integrale"]):
            return False
        return super().can_cite_sentenza(record)

    def recent_acquisitions(self, limit=10):
        """Bounded initial list; this is acquisition order, not relevance ranking."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT {_COLONNE_RICERCA} FROM sentenze s ORDER BY s.id DESC LIMIT ?",
                (max(1, min(int(limit), 50)),),
            ).fetchall()
        return self._guard_text_availability([dict(row) for row in rows])

    def _connect(self):
        connection = sqlite3.connect(Path(self.db_path).as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection


def configured_corpus(config=None):
    config = config or {}
    directory = str(
        config.get("IUSENTRA_SENTENZEWEB_DIRECTORY") or os.getenv("IUSENTRA_SENTENZEWEB_DIRECTORY") or ""
    ).strip()
    path = Path(directory) / "giurisprudenza_corpus.db" if directory else None
    return PublicSentenzeWebCorpus(path) if path and path.is_file() else None
