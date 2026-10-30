"""Bounded, resumable acquisition of public SentenzeWeb into the native corpus.
No private tenant data, new HTTP service, authentication bypass or TLS weakening.
"""

import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import hmac
import ipaddress
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests


@contextmanager
def FileLock(path, timeout=0):
    with open(path, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from pct.sentenzeweb_corpus import body_available
from pct.sentenzeweb_recovery import enqueue_recovery

URL = "https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select"


def scalar(x):
    return x[0] if isinstance(x, list) and x else x


def retry_transient_read(operation):
    """Retry only idempotent source reads, never TLS or identity failures."""
    for attempt in range(5):
        try:
            return operation()
        except requests.exceptions.SSLError:
            raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as exc:
            if attempt == 4:
                raise
            print(json.dumps({"source_read_retry": attempt + 1, "error_type": type(exc).__name__}), flush=True)
            time.sleep(2 ** (attempt + 1))

def payload(d, url):
    ident = scalar(d.get("id"))
    kind = scalar(d.get("kind"))
    year = str(scalar(d.get("anno")) or "")
    num = str(scalar(d.get("numdec")) or "")
    if (
        not ident
        or not re.fullmatch(r"sn(civ|pen)[A-Za-z0-9]+", ident)
        or kind not in ("snciv", "snpen")
        or not re.fullmatch(r"\d{4}", year)
        or not num.isdigit()
    ):
        raise ValueError("Unproven judgment identity")
    text = d.get("ocr") or ""
    text = "\n".join(text) if isinstance(text, list) else str(text)

    def date(x):
        x = str(scalar(x) or "")
        return dt.date.fromisoformat(f"{x[:4]}-{x[4:6]}-{x[6:]}").isoformat() if x else ""

    url = URL + "?" + urlencode({"q": "id:" + ident, "rows": 1, "wt": "json"})
    bodyhash = hashlib.sha256(text.encode()).hexdigest()
    sourcehash = hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    typ = str(scalar(d.get("tipoprov")) or "").lower()
    typ = typ if typ in ("sentenza", "ordinanza", "decreto") else "provvedimento"
    return {
        "uuid_interno": "sentenzeweb:" + ident,
        "fonte_codice": "cassazione_sentenzeweb",
        "fonte_nome": "Corte di Cassazione — SentenzeWeb",
        "tipo_fonte": "ufficiale",
        "organo_giudicante": "Corte di Cassazione — " + ("civile" if kind == "snciv" else "penale"),
        "numero_sentenza": num,
        "anno_sentenza": int(year),
        "sezione": str(scalar(d.get("szdec")) or ""),
        "tipo_provvedimento": typ,
        "data_deposito": date(d.get("pd")),
        "data_decisione": date(d.get("datdec")),
        "titolo": f"Cassazione {kind} {num}/{year}",
        "testo_integrale": text,
        "testo_integrale_presente": bool(text.strip()),
        "fonte_ufficiale_confermata": True,
        "pdf_ufficiale_presente": False,
        "stato_verifica": "parzialmente_verificata",
        "url_pagina_ufficiale": url,
        "hash_contenuto": sourcehash,
        "relatore": str(scalar(d.get("relatore")) or ""),
        "presidente": str(scalar(d.get("presidente")) or ""),
    }, bodyhash


def run(a):
    root = Path(a.directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    with FileLock(str(root / "acquisizione.lock"), timeout=0):
        db = root / "giurisprudenza_corpus.db"
        corpus = GestioneCorpusGiurisprudenza(str(db))
        c = sqlite3.connect(db, timeout=30)
        c.row_factory = sqlite3.Row
        c.executescript(
            """CREATE TABLE IF NOT EXISTS sentenzeweb_transport_receipts(page_sha256 TEXT PRIMARY KEY,transport TEXT NOT NULL,peer TEXT NOT NULL);CREATE TABLE IF NOT EXISTS sentenzeweb_aliases(source_id TEXT PRIMARY KEY,native_uuid TEXT NOT NULL,proof_text_sha256 TEXT NOT NULL,acquired_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS sentenzeweb_progress(id INTEGER PRIMARY KEY CHECK(id=1),lower_version INTEGER NOT NULL,upper_version INTEGER NOT NULL,cursor TEXT NOT NULL,expected INTEGER NOT NULL,seen INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,last_version INTEGER NOT NULL DEFAULT 0);CREATE TABLE IF NOT EXISTS sentenzeweb_pages(sha256 TEXT PRIMARY KEY,path TEXT NOT NULL,records INTEGER NOT NULL,acquired_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS sentenzeweb_receipts(source_id TEXT PRIMARY KEY,source_version INTEGER NOT NULL,text_sha256 TEXT NOT NULL,text_chars INTEGER NOT NULL,original_page_sha256 TEXT NOT NULL,acquired_at TEXT NOT NULL);"""
        )
        c.commit()
        session = requests.Session()
        session.headers["User-Agent"] = "IUSENTRA-SentenzeWeb/1.0 (bounded public corpus acquisition)"
        bridge_url = os.getenv("IUSENTRA_SENTENZEWEB_BRIDGE_URL", "").strip()
        target_url = URL
        if bridge_url:
            parsed = urlsplit(bridge_url)
            valid_host = ipaddress.ip_address(parsed.hostname or "0.0.0.0") in ipaddress.ip_network("100.64.0.0/10")
            token = os.getenv("IUSENTRA_SENTENZEWEB_BRIDGE_TOKEN", "")
            if (
                not valid_host
                or parsed.scheme != "http"
                or parsed.port != 8094
                or parsed.path != "/sentenzeweb"
                or parsed.query
                or parsed.fragment
                or parsed.username
                or not token
            ):
                raise ValueError("Invalid private source bridge configuration")
            target_url = bridge_url
            session.trust_env = False
            session.headers["Authorization"] = "Bearer " + token

        def fetch_once(params):
            if shutil.disk_usage(root).free < 10 * 1024**3 or (
                Path("/mnt/c").is_mount() and shutil.disk_usage("/mnt/c").free < 20 * 1024**3
            ):
                raise RuntimeError("Free space below protected ext4/physical-Windows margin")
            with session.get(
                target_url,
                params=params,
                verify=a.ca_bundle,
                timeout=(10, 50 if bridge_url else 35),
                allow_redirects=False,
                stream=True,
            ) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"Official source HTTP {r.status_code}; no automatic loop")
                content = bytearray()
                for part in r.iter_content(65536):
                    content.extend(part)
                    if len(content) > 32 * 1024**2:
                        raise RuntimeError("Response exceeds 32MiB")
                if bridge_url and (
                    r.headers.get("X-IUSENTRA-Source-Transport") != "official-tls-verified"
                    or not hmac.compare_digest(
                        r.headers.get("X-IUSENTRA-Body-SHA256", ""), hashlib.sha256(content).hexdigest()
                    )
                ):
                    raise ValueError("Private source response lacks matching provenance/integrity receipt")
                return json.loads(content), bytes(content), r.url

        def fetch(params):
            return retry_transient_read(lambda: fetch_once(params))

        state = c.execute("SELECT * FROM sentenzeweb_progress WHERE id=1").fetchone()
        if state and state["status"] == "complete":
            if not a.incremental:
                raise RuntimeError("History already completed; use incremental explicitly")
            lower = state["upper_version"]
            state = None
        else:
            lower = 0
        if state is None:
            top, _, _ = fetch(
                {"q": "kind:(snciv OR snpen)", "rows": 1, "sort": "_version_ desc", "fl": "_version_", "wt": "json"}
            )
            upper = int(top["response"]["docs"][0]["_version_"])
            c.execute(
                "INSERT OR REPLACE INTO sentenzeweb_progress VALUES(1,?,?,?,0,0,?,?)",
                (lower, upper, "*", "running", lower),
            )
            c.commit()
            state = c.execute("SELECT * FROM sentenzeweb_progress").fetchone()
        pages = 0
        while a.max_pages == 0 or pages < a.max_pages:
            state = c.execute("SELECT * FROM sentenzeweb_progress").fetchone()
            params = {
                "q": "kind:(snciv OR snpen)",
                "fq": f"_version_:{{{state['lower_version']} TO {state['upper_version']}]",
                "rows": a.rows,
                "sort": "id asc",
                "cursorMark": state["cursor"],
                "wt": "json",
            }
            data, raw, url = fetch(params)
            response = data["response"]
            docs = response["docs"]
            nxt = data.get("nextCursorMark")
            assert nxt, "No server cursor; stopping"
            digest = hashlib.sha256(raw).hexdigest()
            archive = root / "originali"
            archive.mkdir(exist_ok=True)
            dst = archive / (digest + ".json.gz")
            if not dst.exists():
                with dst.open("xb") as f:
                    f.write(gzip.compress(raw, mtime=0))
                    f.flush()
                    os.fsync(f.fileno())
            if hashlib.sha256(gzip.decompress(dst.read_bytes())).hexdigest() != digest:
                raise RuntimeError("Original archive hash mismatch")
            material = [payload(d, url) for d in docs]
            # One native case envelope retains EVERY official document variant.
            # Distinct source IDs are not assumed to be interchangeable legal texts.
            groups = {}
            aliases = {}
            native = []
            for d, (p, h) in zip(docs, material):
                key = (
                    p["organo_giudicante"],
                    p["sezione"],
                    p["numero_sentenza"],
                    p["anno_sentenza"],
                    p["data_deposito"],
                )
                groups.setdefault(key, []).append((d, p, h))
            for key, variants in groups.items():
                old = c.execute(
                    "SELECT s.* FROM sentenze s JOIN fonti_giurisprudenza f ON f.id=s.fonte_id WHERE f.codice=? AND s.organo_giudicante=? AND COALESCE(s.sezione,'')=? AND COALESCE(s.numero_sentenza,'')=? AND COALESCE(s.anno_sentenza,0)=? AND COALESCE(s.data_deposito,'')=?",
                    ("cassazione_sentenzeweb",) + key,
                ).fetchone()
                chosen = max(
                    variants,
                    key=lambda v: (
                        body_available(v[1]["testo_integrale"]),
                        int(v[0]["_version_"]),
                        len(v[1]["testo_integrale"]),
                    ),
                )[1].copy()
                canonical = old["uuid_interno"] if old else variants[0][1]["uuid_interno"]
                chosen["uuid_interno"] = canonical
                documents = {}
                if old:
                    for doc in c.execute(
                        "SELECT * FROM documenti_sentenza WHERE sentenza_id=?", (old["id"],)
                    ).fetchall():
                        documents[(doc["url_origine"], doc["sha256"])] = dict(doc)
                    if not body_available(chosen["testo_integrale"]) and body_available(old["testo_integrale"]):
                        for field in (
                            "testo_integrale",
                            "url_pagina_ufficiale",
                            "tipo_provvedimento",
                            "data_decisione",
                        ):
                            chosen[field] = old[field]
                for d, p, h in variants:
                    documents[(p["url_pagina_ufficiale"], h)] = {
                        "titolo": d["id"] + " — " + str(scalar(d.get("tipoprov")) or ""),
                        "tipo_documento": "testo_plain",
                        "mime_type": "text/plain",
                        "url_origine": p["url_pagina_ufficiale"],
                        "sha256": h,
                        "testo_estratto": p["testo_integrale"],
                        "testo_estratto_chars": len(p["testo_integrale"]),
                        "ufficiale": True,
                        "scaricato": True,
                        "valido": body_available(p["testo_integrale"]),
                    }
                    aliases[d["id"]] = canonical
                # Explicit pending-redaction placeholders are preserved as source documents but never
                # advertised as a full decision body by the native corpus.
                if not body_available(chosen["testo_integrale"]):
                    chosen["testo_integrale"] = ""
                chosen["testo_integrale_presente"] = bool(chosen["testo_integrale"])
                chosen["documenti"] = list(documents.values())
                chosen["hash_contenuto"] = hashlib.sha256(
                    json.dumps(
                        {
                            "record": {k: v for k, v in chosen.items() if k not in {"hash_contenuto", "documenti"}},
                            "documents": [
                                {
                                    **{k: " ".join(str(doc.get(k) or "").split()) for k in
                                       ("titolo", "tipo_documento", "mime_type", "url_origine", "sha256")},
                                    **{k: bool(doc.get(k)) for k in ("ufficiale", "scaricato", "valido")},
                                    "testo_estratto_chars": int(doc.get("testo_estratto_chars") or 0),
                                }
                                for _, doc in sorted(documents.items())
                            ],
                        }, sort_keys=True
                    ).encode()
                ).hexdigest()
                native.append(chosen)
            counts = corpus.salva_sentenze_blocco(native, salta_invariate=True)
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            with c:
                c.execute(
                    "INSERT OR IGNORE INTO sentenzeweb_transport_receipts VALUES(?,?,?)",
                    (
                        digest,
                        "official-tls-via-authorized-pc-tailscale" if bridge_url else "official-tls-direct",
                        urlsplit(target_url).hostname,
                    ),
                )
                c.execute("INSERT OR IGNORE INTO sentenzeweb_pages VALUES(?,?,?,?)", (digest, str(dst), len(docs), now))
                for d, (p, h) in zip(docs, material):
                    c.execute(
                        "INSERT OR REPLACE INTO sentenzeweb_receipts VALUES(?,?,?,?,?,?)",
                        (d["id"], int(d["_version_"]), h, len(p["testo_integrale"]), digest, now),
                    )
                    c.execute(
                        "INSERT OR REPLACE INTO sentenzeweb_aliases VALUES(?,?,?,?)",
                        (d["id"], aliases.get(d["id"], p["uuid_interno"]), h, now),
                    )
                for item in native:
                    if not body_available(item["testo_integrale"]):
                        parent = c.execute("SELECT id FROM sentenze WHERE uuid_interno=?",
                                           (item["uuid_interno"],)).fetchone()
                        version = max(int(d["_version_"]) for d in docs
                                      if aliases.get(d["id"]) == item["uuid_interno"])
                        enqueue_recovery(c, parent[0], version)
                done = nxt == state["cursor"]
                seen = state["seen"] + len(docs)
                status = (
                    "complete" if done and seen == response["numFound"] else "coverage_changed" if done else "running"
                )
                c.execute(
                    "UPDATE sentenzeweb_progress SET cursor=?,expected=?,seen=?,status=? WHERE id=1",
                    (nxt, response["numFound"], seen, status),
                )
            pages += 1
            print(
                json.dumps(
                    {"page": pages, "records": seen, "expected": response["numFound"], "status": status, **counts}
                ),
                flush=True,
            )
            if done:
                break
            time.sleep(a.interval)
        print(json.dumps(dict(c.execute("SELECT * FROM sentenzeweb_progress").fetchone())), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--directory", required=True)
    p.add_argument("--ca-bundle", required=True)
    p.add_argument("--rows", type=int, default=100)
    p.add_argument("--max-pages", type=int, default=0)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--incremental", action="store_true")
    a = p.parse_args()
    assert 1 <= a.rows <= 100 and a.interval >= 1
    try:
        run(a)
    except BlockingIOError:
        print(json.dumps({"status": "already_running"}), flush=True)
        sys.exit(75)
