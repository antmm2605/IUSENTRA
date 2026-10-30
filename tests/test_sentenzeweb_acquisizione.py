import gzip
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from tools import sentenzeweb_importa as acquisition


def decision(suffix="1O", number="1", text=None):
    return {
        "id": "snciv20262" + suffix,
        "kind": "snciv",
        "anno": "2026",
        "numdec": number,
        "szdec": "2",
        "pd": "20261014",
        "datdec": "20261013",
        "tipoprov": "Ordinanza",
        "ocr": [text or ("Testo ufficiale di prova. " * 60)],
        "_version_": 3,
    }


class Response:
    status_code = 200

    def __init__(self, data):
        self.content = json.dumps(data).encode()
        self.url = acquisition.URL

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, size):
        yield self.content


class Session:
    def __init__(self, documents):
        self.documents = documents
        self.headers = {}
        self.calls = []

    def get(self, url, *, params, verify, timeout, allow_redirects, stream):
        assert url == acquisition.URL and verify and not allow_redirects and stream
        self.calls.append(dict(params))
        if params.get("sort") == "_version_ desc":
            return Response({"response": {"docs": [{"_version_": 3}]}})
        changed = not params["fq"].startswith("_version_:{3 ")
        documents = self.documents if changed else []
        page = documents if params["cursorMark"] == "*" else []
        return Response(
            {
                "response": {"numFound": len(documents), "docs": page},
                "nextCursorMark": "C" if page else params["cursorMark"],
            }
        )


def options(tmp_path, **changes):
    values = {
        "directory": str(tmp_path / "corpus"),
        "ca_bundle": "verified-system-and-intermediate.pem",
        "incremental": False,
        "rows": 100,
        "max_pages": 1,
        "interval": 1,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def connect(a):
    return sqlite3.connect(str(acquisition.Path(a.directory) / "giurisprudenza_corpus.db"))


def setup(monkeypatch, documents):
    session = Session(documents)
    monkeypatch.setattr(acquisition.requests, "Session", lambda: session)
    monkeypatch.setattr(acquisition.time, "sleep", lambda _: None)
    monkeypatch.setattr(acquisition.shutil, "disk_usage", lambda _: SimpleNamespace(free=100 * 1024**3))
    return session


def test_resume_and_incremental_do_not_duplicate_unchanged_documents(tmp_path, monkeypatch):
    session = setup(monkeypatch, [decision(), decision("2O", "2")])
    a = options(tmp_path)
    acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT seen,status FROM sentenzeweb_progress").fetchone() == (2, "running")
    acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT count(*) FROM sentenze").fetchone()[0] == 2
        assert c.execute("SELECT status FROM sentenzeweb_progress").fetchone()[0] == "complete"
    a.incremental = True
    acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT seen,status FROM sentenzeweb_progress").fetchone() == (0, "complete")
    acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT count(*) FROM sentenze").fetchone()[0] == 2
        assert c.execute("SELECT count(*) FROM sentenzeweb_receipts").fetchone()[0] == 2
        assert c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        for sha, path in c.execute("SELECT sha256,path FROM sentenzeweb_pages"):
            assert hashlib.sha256(gzip.decompress(acquisition.Path(path).read_bytes())).hexdigest() == sha
    assert any(call.get("cursorMark") == "C" for call in session.calls)


def test_variants_retained_without_duplicate_case_or_false_short_text(tmp_path, monkeypatch):
    short = decision("1I", text="in fase di valutazione oscuramento")
    setup(monkeypatch, [short, decision()])
    a = options(tmp_path)
    acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT count(*) FROM sentenze").fetchone()[0] == 1
        assert c.execute("SELECT count(*),sum(valido) FROM documenti_sentenza").fetchone() == (2, 1)
        assert c.execute("SELECT count(*) FROM sentenzeweb_receipts").fetchone()[0] == 2
        assert c.execute("SELECT count(DISTINCT native_uuid) FROM sentenzeweb_aliases").fetchone()[0] == 1
        assert c.execute("SELECT length(testo_integrale) FROM sentenze").fetchone()[0] > 500


def test_bad_identity_does_not_advance_cursor_or_commit_judgments(tmp_path, monkeypatch):
    bad = decision()
    bad["anno"] = "not-year"
    setup(monkeypatch, [decision("2O", "2"), bad])
    a = options(tmp_path)
    with pytest.raises(ValueError, match="identity"):
        acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT cursor,seen FROM sentenzeweb_progress").fetchone() == ("*", 0)
        assert c.execute("SELECT count(*) FROM sentenze").fetchone()[0] == 0
    assert list((acquisition.Path(a.directory) / "originali").glob("*.json.gz"))


def test_low_physical_space_stops_before_network_download(tmp_path, monkeypatch):
    session = setup(monkeypatch, [decision()])
    monkeypatch.setattr(acquisition.shutil, "disk_usage", lambda _: SimpleNamespace(free=1024))
    with pytest.raises(RuntimeError, match="space"):
        acquisition.run(options(tmp_path))
    assert session.calls == []


def test_second_worker_is_rejected_before_network(tmp_path, monkeypatch):
    session = setup(monkeypatch, [decision()])
    a = options(tmp_path)
    acquisition.Path(a.directory).mkdir()
    with acquisition.FileLock(str(acquisition.Path(a.directory) / "acquisizione.lock")), pytest.raises(BlockingIOError):
        acquisition.run(a)
    assert session.calls == []


def test_short_actual_text_is_not_excluded_by_length(tmp_path, monkeypatch):
    short = "La Corte rigetta il ricorso."
    setup(monkeypatch, [decision(text=short)])
    a = options(tmp_path)
    acquisition.run(a)
    with connect(a) as connection:
        assert connection.execute("SELECT testo_integrale,testo_integrale_presente FROM sentenze").fetchone() == (
            short,
            1,
        )
        assert connection.execute("SELECT testo_estratto FROM documenti_sentenza").fetchone()[0] == short


def test_source_read_retries_transient_failures_but_never_tls_or_identity(monkeypatch):
    import requests

    from tools import sentenzeweb_importa as collector
    waits = []
    monkeypatch.setattr(collector.time, "sleep", waits.append)
    calls = []
    def transient():
        calls.append(1)
        if len(calls) < 3:
            raise requests.exceptions.ConnectionError("source disconnected")
        return "official response"
    assert collector.retry_transient_read(transient) == "official response"
    assert len(calls) == 3 and waits == [2, 4]
    for failure in (requests.exceptions.SSLError("TLS invalid"), ValueError("identity invalid")):
        attempts = []
        def forbidden_retry(failure=failure, attempts=attempts):
            attempts.append(1)
            raise failure
        with pytest.raises(type(failure)):
            collector.retry_transient_read(forbidden_retry)
        assert len(attempts) == 1


def test_case_identity_lookup_uses_all_existing_unique_index_fields(tmp_path):
    import sqlite3

    from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "cases.db"))
    corpus.salva_sentenza({"uuid_interno": "lookup-test", "fonte_codice": "cassazione_sentenzeweb",
        "fonte_nome": "SentenzeWeb", "organo_giudicante": "Corte di Cassazione — civile",
        "sezione": "2", "numero_sentenza": "123", "anno_sentenza": 2026, "data_deposito": "2026-10-14"})
    sql = "SELECT s.* FROM sentenze s JOIN fonti_giurisprudenza f ON f.id=s.fonte_id WHERE f.codice=? AND s.organo_giudicante=? AND COALESCE(s.sezione,'')=? AND COALESCE(s.numero_sentenza,'')=? AND COALESCE(s.anno_sentenza,0)=? AND COALESCE(s.data_deposito,'')=?"
    args = ("cassazione_sentenzeweb", "Corte di Cassazione — civile", "2", "123", 2026, "2026-10-14")
    with sqlite3.connect(corpus.db_path) as connection:
        plan = " ".join(row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql, args))
        assert plan.count("<expr>=?") == 4
        assert len(connection.execute(sql, args).fetchall()) == 1
        assert not connection.execute(sql, (*args[:-1], "2026-10-15")).fetchall()
        assert not connection.execute(sql, (*args[:3], "124", *args[4:])).fetchall()


@pytest.mark.parametrize("change_content", [False, True])
def test_incremental_metadata_correction_updates_same_case_without_text_duplication(tmp_path, monkeypatch, change_content):
    doc = decision()
    class RevisionSession(Session):
        def get(self, url, **kwargs):
            params = kwargs["params"]
            if params.get("sort") == "_version_ desc":
                return Response({"response": {"docs": [{"_version_": self.documents[0]["_version_"]}]}})
            lower = int(params["fq"].split("{")[1].split()[0])
            changed = [d for d in self.documents if d["_version_"] > lower]
            page = changed if params["cursorMark"] == "*" else []
            return Response({"response": {"numFound": len(changed), "docs": page},
                             "nextCursorMark": "C" if page else params["cursorMark"]})
    setup(monkeypatch, [doc])
    monkeypatch.setattr(acquisition.requests, "Session", lambda: RevisionSession([doc]))
    a = options(tmp_path, max_pages=0)
    acquisition.run(a)
    previous_text = " ".join(doc["ocr"][0].split())
    doc = {**doc, "_version_": 4, "datdec": "20261012"}
    if change_content:
        doc["ocr"] = ["Nuova versione ufficiale sintetica. " * 60]
    a.incremental = True
    acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT data_decisione FROM sentenze").fetchone()[0] == "2026-10-12"
        assert c.execute("SELECT count(*) FROM sentenze").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM documenti_sentenza").fetchone()[0] == (2 if change_content else 1)
        assert c.execute("SELECT testo_integrale FROM sentenze").fetchone()[0] == " ".join(doc["ocr"][0].split())
        assert previous_text in {row[0] for row in c.execute("SELECT testo_estratto FROM documenti_sentenza")}
        assert c.execute("SELECT source_version FROM sentenzeweb_receipts").fetchone()[0] == 4
        before = c.execute("SELECT hash_contenuto,updated_at FROM sentenze").fetchone()
    acquisition.run(a)
    with connect(a) as c:
        assert c.execute("SELECT hash_contenuto,updated_at FROM sentenze").fetchone() == before
        assert c.execute("SELECT count(*) FROM sentenze").fetchone()[0] == 1


@pytest.mark.parametrize("text", [
    "in fase di valutazione oscuramento",
    "CORTE SUPREMA DI CASSAZIONE ITALGIUREWEB La sentenza richiesta è in fase di oscuramento",
    "!CORTE SUPREMA DI CASSAZIONE ITALGIUREWEB La sentenza richiesta è in fase di oscuramentoI",
    "!CORTE SUPREMA DI CASSAZIONE ITALGIUREWEB La sentenza richiesta è in fase di oscuramento*",
    "CORTE SUPREMA DI CASSAZIONE ITALGIUREWEB La sentenza richiesta è in fase di oscuramento CO",
    "CORTE SUPREMA DI CASSAZIONE\nITALGIUREWEB\nLa sentenza richiesta è in fase di valutazione per oscuramento",
])
def test_official_redaction_notices_are_not_decision_bodies(text):
    assert acquisition.body_available(text) is False


@pytest.mark.parametrize("text", [
    "P.Q.M. Rigetta il ricorso.",
    "La Corte rileva che la sentenza richiesta è in fase di oscuramento e decide sul ricorso.",
    "CORTE SUPREMA DI CASSAZIONE ITALGIUREWEB La sentenza richiesta è in fase di oscuramento. Il ricorso è rigettato.",
])
def test_short_decision_or_quoted_notice_is_not_discarded(text):
    assert acquisition.body_available(text) is True
