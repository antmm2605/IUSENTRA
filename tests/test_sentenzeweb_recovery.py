import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from pct.sentenzeweb_recovery import alternative_url, parse_alternative
from web.services.sentenzeweb_runtime import read_text, search, variants


IDENTITY = {"organo_giudicante": "Corte di Cassazione — civile", "sezione": "2",
            "numero_sentenza": "26870", "anno_sentenza": 2026,
            "data_deposito": "2026-10-14", "data_decisione": "2026-10-13"}
HTML = ("<div><h1>Corte di Cassazione, sez. II Civile, Ordinanza n.26870 del 14/10/2026</h1>"
        "<div class='card bg-light'><p>LA CORTE SUPREMA DI CASSAZIONE</p>"
        "<p>Motivazione controllata.</p><p>P.Q.M. Rigetta il ricorso.</p>"
        "<p>Così deciso in Roma il 13 ottobre 2026.</p>"
        "<p>Depositato in Cancelleria il 14 ottobre 2026</p></div></div>").encode()


def parsed(html=HTML):
    return parse_alternative(html, identity=IDENTITY, source_url=alternative_url(IDENTITY))


def prepare(tmp_path, source="cassazione_sentenzeweb"):
    path = tmp_path / "giurisprudenza_corpus.db"
    owner = GestioneCorpusGiurisprudenza(str(path))
    original = "in fase di valutazione oscuramento"
    record = owner.salva_sentenza({**IDENTITY, "uuid_interno": "sentenzeweb:snciv2026226870O",
        "fonte_codice": source, "fonte_nome": "Fonte controllata", "tipo_fonte": "ufficiale",
        "tipo_provvedimento": "ordinanza", "titolo": "Cassazione 26870/2026",
        "testo_integrale": "", "testo_integrale_presente": False,
        "stato_verifica": "parzialmente_verificata",
        "documenti": [{"tipo_documento": "testo_plain", "titolo": "Originale conservato",
            "testo_estratto": original, "sha256": hashlib.sha256(original.encode()).hexdigest(),
            "url_origine": "https://www.italgiure.giustizia.it/sncass/", "ufficiale": True, "valido": False}]})
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sentenzeweb_progress(seen INTEGER,expected INTEGER,status TEXT,id INTEGER)")
        conn.execute("INSERT INTO sentenzeweb_progress VALUES(1,1,'complete',1)")
        conn.execute("CREATE TABLE sentenzeweb_receipts(source_id TEXT PRIMARY KEY,source_version INTEGER)")
        conn.execute("INSERT INTO sentenzeweb_receipts VALUES('snciv2026226870O',3)")
        conn.execute("CREATE TABLE sentenzeweb_aliases(source_id TEXT PRIMARY KEY,native_uuid TEXT)")
        conn.execute("INSERT INTO sentenzeweb_aliases VALUES('snciv2026226870O','sentenzeweb:snciv2026226870O')")
    return owner, record["id"], {"IUSENTRA_SENTENZEWEB_DIRECTORY": str(tmp_path)}


def append(owner, case_id, proof=None, identity=None):
    proof = proof or parsed()
    return owner.append_public_transcription(case_id, identity=identity or IDENTITY,
        text=proof["text"], text_sha256=proof["text_sha256"], source_url=proof["source_url"], source_html=HTML, promote_active=True)


def test_published_transcription_is_identity_bound_and_not_official():
    proof = parsed()
    assert proof["text"].startswith("LA CORTE SUPREMA")
    assert proof["professional_approval"] is False and proof["official"] is False
    assert proof["html_sha256"] == hashlib.sha256(HTML).hexdigest()


@pytest.mark.parametrize("before,after", [
    ("n.26870", "n.26871"), ("14/10/2026", "14/10/2025"),
    ("sez. II Civile", "sez. III Civile"), ("sez. II Civile", "sez. II Penale"),
    ("P.Q.M.", "Dispositivo assente"), ("13 ottobre 2026", "13 ottobre 2025"),
    ("14 ottobre 2026", "14 ottobre 2025"),
])
def test_wrong_identity_or_incomplete_transcription_is_rejected(before, after):
    with pytest.raises(ValueError):
        parsed(HTML.replace(before.encode(), after.encode()))


@pytest.mark.parametrize("url", [
    "https://www.misterlex.it.evil.invalid/cassazione-civile/2026/26870/",
    "https://user:password@www.misterlex.it/cassazione-civile/2026/26870/",
    "http://www.misterlex.it/cassazione-civile/2026/26870/",
    "https://www.misterlex.it/cassazione-penale/2026/26870/",
])
def test_other_host_credentials_or_branch_cannot_be_used_as_provenance(url):
    with pytest.raises(ValueError):
        parse_alternative(HTML, identity=IDENTITY, source_url=url)


def test_append_preserves_original_ids_and_survives_reload_without_duplicates(tmp_path):
    owner, case_id, config = prepare(tmp_path)
    original_ids = [row["id"] for row in owner.get_sentenza(case_id)["documenti"]]
    first = append(owner, case_id)
    second = append(owner, case_id)
    assert first["inserted"] and first["active_text_updated"]
    assert not second["inserted"] and not second["active_text_updated"]
    loaded = owner.get_sentenza(case_id)
    assert len(loaded["documenti"]) == 2
    assert all(any(row["id"] == ident for row in loaded["documenti"]) for ident in original_ids)
    assert loaded["documenti"][0]["testo_estratto"] == "in fase di valutazione oscuramento"
    assert loaded["stato_verifica"] == "parzialmente_verificata"
    response = search(config, "26870/2026")["records"][0]
    assert response["textAvailable"] and response["textSourceOfficial"] is False
    assert response["textSourceUrl"] == alternative_url(IDENTITY)
    assert read_text(config, case_id) == " ".join(parsed()["text"].split())
    assert any(row["official"] is False for row in variants(config, case_id)["documents"])


def test_concurrent_workers_append_one_transcription(tmp_path):
    owner, case_id, _ = prepare(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: append(owner, case_id), range(2)))
    assert sum(row["inserted"] for row in results) == 1
    assert len(owner.get_sentenza(case_id)["documenti"]) == 2


def test_digest_or_parent_mismatch_does_not_modify_archive(tmp_path):
    owner, case_id, _ = prepare(tmp_path)
    proof = parsed()
    with pytest.raises(ValueError, match="digest"):
        append(owner, case_id, {**proof, "text_sha256": "0" * 64})
    with pytest.raises(ValueError):
        append(owner, case_id, identity={**IDENTITY, "sezione": "3"})
    assert len(owner.get_sentenza(case_id)["documenti"]) == 1
    assert owner.get_sentenza(case_id)["testo_integrale"] == ""


def test_recovery_cannot_write_into_a_private_source(tmp_path):
    owner, case_id, _ = prepare(tmp_path, "manuale_interno")
    with pytest.raises(ValueError, match="shared public"):
        append(owner, case_id)
    assert owner.get_sentenza(case_id)["testo_integrale"] == ""


def test_default_preserves_active_text_until_explicit_activation(tmp_path):
    owner, case_id, _ = prepare(tmp_path)
    proof = parsed()
    result = owner.append_public_transcription(case_id, identity=IDENTITY,
        text=proof["text"], text_sha256=proof["text_sha256"], source_url=proof["source_url"], source_html=HTML)
    assert result["inserted"] and not result["active_text_updated"]
    assert owner.get_sentenza(case_id)["testo_integrale"] == ""
    assert len(owner.get_sentenza(case_id)["documenti"]) == 2


def test_recovery_receipt_links_official_identity_and_both_preserved_originals(tmp_path):
    owner, case_id, _ = prepare(tmp_path)
    append(owner, case_id)
    append(owner, case_id)
    with sqlite3.connect(tmp_path / "giurisprudenza_corpus.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM sentenzeweb_recovery_receipts").fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row["source_id"] == "snciv2026226870O" and row["source_version"] == 3
        assert row["native_id"] == case_id and row["provider"] == "misterlex"
        assert hashlib.sha256((tmp_path / row["html_path"]).read_bytes()).hexdigest() == row["html_sha256"]
        assert hashlib.sha256((tmp_path / row["text_path"]).read_bytes()).hexdigest() == row["text_sha256"]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


class PublicResponse:
    def __init__(self, html=HTML, status=200, media="text/html; charset=utf-8", url=None):
        self.html, self.status_code = html, status
        self.headers = {"Content-Type": media}
        self.url = url or alternative_url(IDENTITY)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, size):
        yield self.html


class PublicSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_fetch_is_bounded_identity_checked_and_does_not_follow_redirects():
    from pct.sentenzeweb_recovery import fetch_alternative
    session = PublicSession(PublicResponse())
    proof = fetch_alternative(IDENTITY, session=session)
    assert proof["source_html"] == HTML
    assert proof["text_sha256"] == parsed()["text_sha256"]
    assert len(session.calls) == 1
    assert session.calls[0][1]["allow_redirects"] is False
    assert session.calls[0][1]["timeout"] == (10, 30)


@pytest.mark.parametrize("response", [
    PublicResponse(status=302), PublicResponse(status=403), PublicResponse(status=429),
    PublicResponse(status=500), PublicResponse(media="application/pdf"),
    PublicResponse(url="https://other.invalid/"), PublicResponse(html=b"layout changed"),
])
def test_failed_public_read_is_not_accepted_or_retried(response):
    from pct.sentenzeweb_recovery import fetch_alternative
    session = PublicSession(response)
    with pytest.raises(ValueError):
        fetch_alternative(IDENTITY, session=session)
    assert len(session.calls) == 1


def test_excessive_public_source_is_rejected_before_parse():
    from pct.sentenzeweb_recovery import fetch_alternative
    with pytest.raises(ValueError, match="bounded"):
        fetch_alternative(IDENTITY, session=PublicSession(PublicResponse()), max_bytes=10)


def test_queue_does_not_repeat_unchanged_success_or_failure_and_new_source_reopens(tmp_path):
    from pct.sentenzeweb_recovery import enqueue_recovery, recover_pending
    owner, case_id, _ = prepare(tmp_path)
    def seed(version):
        with sqlite3.connect(owner.db_path) as connection:
            enqueue_recovery(connection, case_id, version)
    calls = []
    def fetch(identity):
        calls.append(identity["id"])
        return {**parsed(), "source_html": HTML}
    seed(3)
    result = recover_pending(owner, fetch=fetch)
    assert result["recovered"] == 1 and calls == [case_id]
    seed(3)
    assert recover_pending(owner, fetch=fetch)["processed"] == 0
    seed(4)
    def failed(identity):
        raise ValueError("identity differs")
    assert recover_pending(owner, fetch=failed)["needs_evidence"] == 1
    seed(4)
    assert recover_pending(owner, fetch=fetch)["processed"] == 0
    assert len(owner.get_sentenza(case_id)["documenti"]) == 2
    seed(5)
    assert recover_pending(owner, fetch=fetch)["recovered"] == 1
    assert len(owner.get_sentenza(case_id)["documenti"]) == 2


def test_available_body_is_not_fetched_again(tmp_path):
    from pct.sentenzeweb_recovery import enqueue_recovery, recover_pending
    owner, case_id, _ = prepare(tmp_path)
    append(owner, case_id)
    with sqlite3.connect(owner.db_path) as connection:
        enqueue_recovery(connection, case_id, 3)
    result = recover_pending(owner, fetch=lambda _: pytest.fail("already available"))
    assert result["already_available"] == 1


@pytest.mark.parametrize("limit,interval", [(0,2), (1001,2), (1,0)])
def test_recovery_refuses_unbounded_or_unthrottled_work(tmp_path, limit, interval):
    from pct.sentenzeweb_recovery import recover_pending
    owner, _, _ = prepare(tmp_path)
    with pytest.raises(ValueError):
        recover_pending(owner, limit=limit, interval=interval)


def test_reader_restores_preserved_paragraphs_and_all_source_words(tmp_path):
    from web.services.sentenzeweb_reader import reader_document
    owner, case_id, config = prepare(tmp_path)
    document_id = append(owner, case_id)["document_id"]
    document = reader_document(config, case_id, document_id)
    assert document["text"] == parsed()["text"]
    assert document["text_source_official"] is False
    assert any(block["kind"] == "heading" and "P.Q.M" in block["text"] for block in document["blocks"])
    assert "".join("".join(block["text"].split()) for block in document["blocks"]) == "".join(document["text"].split())
    assert reader_document(config, case_id+999, document_id) is None
    assert reader_document(config, case_id, document_id+999) is None


def test_reader_refuses_corrupted_preserved_file(tmp_path):
    from pathlib import Path
    from web.services.sentenzeweb_reader import reader_document
    owner, case_id, config = prepare(tmp_path)
    document_id = append(owner, case_id)["document_id"]
    (Path(owner.db_path).parent / "recuperi" / (parsed()["text_sha256"] + ".txt")).write_text("changed")
    with pytest.raises(ValueError, match="digest"):
        reader_document(config, case_id, document_id)


def test_reader_html_is_escaped_authenticated_and_raw_text_remains_available(tmp_path):
    from pathlib import Path
    from flask import Flask, g
    from web.blueprints.giurisprudenza import giurisprudenza
    owner, case_id, config = prepare(tmp_path)
    document_id = append(owner, case_id)["document_id"]
    root = Path(__file__).resolve().parents[1]
    app = Flask(__name__, template_folder=str(root / "web/templates"))
    app.config.update(config)
    app.register_blueprint(giurisprudenza)
    app.add_url_rule("/login", "login", lambda: "login")
    app.add_template_filter(lambda value: "14/10/2026", "data_it")
    logged_in = [False]
    @app.before_request
    def login():
        if logged_in[0]:
            g.utente_corrente = {"id": "test"}
    url = f"/giurisprudenza/sentenzeweb/{case_id}/documenti/{document_id}/testo"
    with app.test_client() as client:
        assert client.get(url).status_code == 302
        logged_in[0] = True
        redirect_response = client.get(url)
        assert redirect_response.status_code == 302
        assert 'sentenzeweb=' in redirect_response.headers['Location']
        response = client.get(url + '?embed=source')
        assert response.status_code == 200 and response.mimetype == "text/html"
        assert b"Trascrizione da fonte non ufficiale" in response.data
        assert b"Sezioni del provvedimento" in response.data
        assert b"14/10/2026" in response.data
        assert "default-src 'none'" in response.headers["Content-Security-Policy"]
        plain = client.get(url + "?format=txt")
        assert plain.mimetype == "text/plain"
        assert plain.get_data(as_text=True) == " ".join(parsed()["text"].split())


def test_next_official_source_update_preserves_original_and_recovered_variant_ids(tmp_path):
    owner, case_id, _ = prepare(tmp_path)
    appended = append(owner, case_id)
    before = owner.get_sentenza(case_id)
    ids = {row["id"] for row in before["documenti"]}
    owner.salva_sentenza({**before, "titolo": "Metadati aggiornati dalla fonte",
                         "documenti": [row for row in before["documenti"] if row["ufficiale"]]})
    after = owner.get_sentenza(case_id)
    assert ids == {row["id"] for row in after["documenti"]}
    assert appended["document_id"] in ids


def test_reader_recognizes_source_heading_split_across_inline_lines():
    from web.services.sentenzeweb_reader import text_blocks
    text = "RILEVATO\nCHE:\n1. Il fatto.\nCONSIDERATO\nCHE:\n1. Il diritto. P.Q.M. Rigetta."
    blocks = text_blocks(text)
    assert [row["text"] for row in blocks if row["kind"] == "heading"] == ["RILEVATO CHE:", "CONSIDERATO CHE:", "P.Q.M."]
    assert "".join("".join(row["text"].split()) for row in blocks) == "".join(text.split())
