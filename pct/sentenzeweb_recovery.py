"""Verified public alternatives: identity-bound transcription, never legal approval."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from pct.sentenzeweb_corpus import body_available

MONTHS = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
SECTIONS = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI", "7": "VII", "L": "Lavoro", "U": "Unite", "F": "Feriale"}


def alternative_url(identity):
    kind = str(identity.get("organo_giudicante") or "")
    branch = "civile" if kind == "Corte di Cassazione — civile" else "penale" if kind == "Corte di Cassazione — penale" else None
    number, year = str(identity.get("numero_sentenza") or ""), str(identity.get("anno_sentenza") or "")
    if not branch or not re.fullmatch(r"[0-9]{1,7}", number) or not re.fullmatch(r"20[0-9]{2}", year):
        raise ValueError("Unproven public decision identity")
    return f"https://www.misterlex.it/cassazione-{branch}/{year}/{int(number)}/"


def _date_words(value):
    day = date.fromisoformat(value)
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def parse_alternative(html, *, identity, source_url):
    expected = alternative_url(identity)
    parsed = urlsplit(source_url)
    if source_url != expected or parsed.username or parsed.password:
        raise ValueError("Unexpected transcription source")
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    if heading is None:
        raise ValueError("Source layout does not expose decision identity")
    title = " ".join(heading.get_text(" ", strip=True).split())
    deposited = date.fromisoformat(str(identity["data_deposito"]))
    number = int(identity["numero_sentenza"])
    if not re.search(rf"\bn\.\s*0*{number}\s+del\s+{deposited:%d/%m/%Y}\b", title):
        raise ValueError("Decision number or deposit date differs")
    branch = "Civile" if "— civile" in identity["organo_giudicante"] else "Penale"
    section = SECTIONS.get(str(identity.get("sezione") or ""))
    if not section or not re.search(rf"\bsez\.\s*(?:Sezioni\s+)?{re.escape(section)}(?:-\d)?\s+{branch}\b", title, re.I):
        raise ValueError("Court branch or section differs")
    cards = [node for node in heading.parent.find_all("div", recursive=False) if "card" in (node.get("class") or [])]
    if not cards:
        raise ValueError("Source layout does not expose the decision body")
    text = cards[0].get_text("\n", strip=True)
    if not body_available(text) or "CORTE SUPREMA DI CASSAZIONE" not in text[:700].upper():
        raise ValueError("No decision body in the published transcription")
    if not re.search(r"\bP\s*\.\s*Q\s*\.\s*M\s*\.?", text):
        raise ValueError("Decision dispositive section missing")
    normalized = " ".join(text.casefold().split())
    tail = normalized[-2000:]
    if _date_words(str(identity["data_deposito"])) not in tail:
        raise ValueError("Body deposit date differs or is missing")
    if identity.get("data_decisione") and _date_words(str(identity["data_decisione"])) not in tail:
        raise ValueError("Body decision date differs or is missing")
    return {
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "html_sha256": hashlib.sha256(html).hexdigest(),
        "source_url": expected,
        "source_title": title,
        "official": False,
        "professional_approval": False,
        "completeness_professionally_verified": False,
    }


def fetch_alternative(identity, *, session=None, max_bytes=8 * 1024 * 1024):
    """Read one published transcription; never follow redirects or retry sends."""
    import requests

    url = alternative_url(identity)
    own_session = session is None
    session = session or requests.Session()
    try:
        with session.get(url, timeout=(10, 30), stream=True, allow_redirects=False,
                         headers={"User-Agent": "IUSENTRA-public-source-verifier/2.458.1"}) as response:
            if response.status_code != 200:
                raise ValueError(f"Public source HTTP {response.status_code}")
            if response.url != url or "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Unexpected source URL or media type")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise ValueError("Public transcription exceeds bounded source size")
        html = bytes(data)
        proof = parse_alternative(html, identity=identity, source_url=url)
        return {**proof, "source_html": html}
    finally:
        if own_session:
            session.close()


QUEUE_SCHEMA = """CREATE TABLE IF NOT EXISTS sentenzeweb_recovery_queue (
    native_id INTEGER PRIMARY KEY REFERENCES sentenze(id) ON DELETE RESTRICT,
    source_version INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','recovered','needs_evidence')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""


def enqueue_recovery(connection, native_id, source_version):
    """An explicit source event queues one identity, unchanged attempts stay recorded."""
    connection.execute(QUEUE_SCHEMA)
    connection.execute("""INSERT INTO sentenzeweb_recovery_queue(native_id,source_version,status)
        VALUES(?,?,'pending') ON CONFLICT(native_id) DO UPDATE SET
        source_version=excluded.source_version,status='pending',attempts=0,last_error='',
        updated_at=CURRENT_TIMESTAMP
        WHERE excluded.source_version<>sentenzeweb_recovery_queue.source_version""",
        (int(native_id), int(source_version)))


def recover_pending(owner, *, limit=25, interval=2.0, fetch=None, promote_active=False):
    """Bounded missing-source work; caller holds the native acquisition lock."""
    import shutil
    import time
    from contextlib import closing

    if not 1 <= limit <= 1000 or interval < 1:
        raise ValueError("Recovery request outside bounded rate or batch")
    fetch = fetch or fetch_alternative
    with closing(owner._connect()) as connection, connection:
        connection.execute(QUEUE_SCHEMA)
        rows = connection.execute("""SELECT q.native_id,q.source_version,s.* FROM sentenzeweb_recovery_queue q
            JOIN sentenze s ON s.id=q.native_id WHERE q.status='pending'
            ORDER BY q.native_id LIMIT ?""", (limit,)).fetchall()
    result = {"processed": 0, "recovered": 0, "needs_evidence": 0, "already_available": 0}
    for offset, row in enumerate(rows):
        if offset:
            time.sleep(interval)
        identity = dict(row)
        if shutil.disk_usage(Path(owner.db_path).parent).free < 1024 ** 3:
            raise RuntimeError("Public recovery requires at least 1GiB free")
        if body_available(identity.get("testo_integrale")):
            status, error = "recovered", ""
            result["already_available"] += 1
        else:
            try:
                proof = fetch(identity)
                owner.append_public_transcription(row["native_id"], identity=identity,
                    text=proof["text"], text_sha256=proof["text_sha256"], source_html=proof["source_html"],
                    source_url=proof["source_url"], promote_active=promote_active)
                status, error = "recovered", ""
                result["recovered"] += 1
            except (ValueError, OSError) as exc:
                # Persist type only: provider HTML and private environment details never enter this queue.
                status, error = "needs_evidence", type(exc).__name__
                result["needs_evidence"] += 1
        with closing(owner._connect()) as connection, connection:
            connection.execute("""UPDATE sentenzeweb_recovery_queue SET status=?,attempts=attempts+1,
                last_error=?,updated_at=CURRENT_TIMESTAMP WHERE native_id=? AND source_version=?""",
                (status, error, row["native_id"], row["source_version"]))
        result["processed"] += 1
    return result
