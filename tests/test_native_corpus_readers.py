import importlib
from pathlib import Path
from types import SimpleNamespace
import hashlib
import sqlite3
import pytest

from pct.giurisprudenza_corpus import SCHEMA_GIURISPRUDENZA_CORPUS
import pct.giurisprudenza_corpus as native
from web.services import giurisprudenza_native_runtime as runtime

@pytest.fixture
def corpus(tmp_path):
    db=tmp_path/"corpus.sqlite";owner=native.GestioneCorpusGiurisprudenza(str(db),schema_path=SCHEMA_GIURISPRUDENZA_CORPUS)
    for code,number,text in [("curia","1","Prima fonte, responsabilità."),("hudoc","1","Seconda fonte, responsabilità.")]:
        owner.salva_sentenza({"uuid_interno":code+":1","fonte_codice":code,"fonte_nome":code,"titolo":code+" 1/2026","organo_giudicante":code,"numero_sentenza":number,"anno_sentenza":2026,"testo_integrale":text,"testo_integrale_presente":True,"data_deposito":"2026-10-30","hash_contenuto":hashlib.sha256(text.encode()).hexdigest()})
    return native.GestioneCorpusGiurisprudenza(str(db),read_only=True)

@pytest.mark.parametrize("query",["","1/2026","responsabilità"])
@pytest.mark.parametrize("source",["curia","hudoc"])
def test_source_filter_applies_to_recent_exact_and_fulltext(corpus,query,source):
    result=runtime.search(corpus,source=source,query=query)
    assert len(result["records"])==1
    assert result["records"][0]["title"]==source+" 1/2026"

@pytest.mark.parametrize("source",["","other","curia' OR 1=1 --"])
def test_invalid_source_is_not_silently_broadened(corpus,source):
    with pytest.raises(ValueError):runtime.search(corpus,source=source)

def test_readonly_owner_never_creates_missing_storage(tmp_path):
    with pytest.raises(FileNotFoundError):native.GestioneCorpusGiurisprudenza(str(tmp_path/"missing"/"db.sqlite"),read_only=True)
    assert not (tmp_path/"missing").exists()

def test_readonly_owner_denies_writes(corpus):
    with corpus._connect() as c:
        assert c.execute("pragma query_only").fetchone()[0]==1
        with pytest.raises(sqlite3.OperationalError):c.execute("delete from sentenze")

def test_current_studio_owner_cannot_return_other_studio_text(corpus,tmp_path):
    other=native.GestioneCorpusGiurisprudenza(str(tmp_path/"other.sqlite"),schema_path=SCHEMA_GIURISPRUDENZA_CORPUS)
    other.salva_sentenza({"uuid_interno":"other:1","fonte_codice":"curia","titolo":"Altra fonte","testo_integrale":"Solo nell'altro studio","testo_integrale_presente":True})
    text=runtime.reader_document(corpus,1)["text"]
    assert "Solo nell'altro studio" not in text
    assert runtime.reader_document(corpus,99999) is None

def test_pdf_digest_and_symlink_guards(tmp_path):
    raw=b"%PDF-1.7\nsource";sha=hashlib.sha256(raw).hexdigest();folder=tmp_path/"fonti_ufficiali";folder.mkdir();file=folder/(sha+".pdf");file.write_bytes(raw);db=tmp_path/"db.sqlite";db.touch()
    document={"id":1,"valido":True,"path_locale":"fonti_ufficiali/"+sha+".pdf","sha256":sha}
    owner=SimpleNamespace(db_path=str(db),get_sentenza=lambda _: {"documenti":[document]})
    with runtime.open_pdf(owner,1,1) as stream:assert stream.read()==raw
    assert runtime.open_pdf(owner,1,2) is None
    file.write_bytes(b"%PDF-tampered")
    with pytest.raises(ValueError):runtime.open_pdf(owner,1,1)
    file.unlink();file.symlink_to(tmp_path/"outside.pdf")
    with pytest.raises(OSError):runtime.open_pdf(owner,1,1)

@pytest.mark.parametrize("path",["/tmp/outside.pdf","../outside.pdf","fonti_ufficiali/wrong.pdf"])
def test_pdf_path_cannot_escape_owner(tmp_path,path):
    owner=SimpleNamespace(db_path=str(tmp_path/"db.sqlite"),get_sentenza=lambda _: {"documenti":[{"id":1,"valido":True,"path_locale":path,"sha256":"a"*64}]})
    with pytest.raises(ValueError):runtime.open_pdf(owner,1,1)


@pytest.fixture
def app(corpus,monkeypatch):
    import sys
    from flask import Flask,g
    sys.modules["web.services.giurisprudenza_native_runtime"]=runtime
    routes=importlib.import_module("web.blueprints.giurisprudenza")
    monkeypatch.setattr(routes,"_native_corpus_owner",lambda:corpus)
    root=Path(__file__).resolve().parents[1]
    app=Flask(__name__,template_folder=str(root/"web/templates"),static_folder=str(root/"web/static"));app.register_blueprint(routes.giurisprudenza)
    app.add_url_rule("/login","login",lambda:"login")
    app.add_template_filter(lambda value:value,"data_it")
    app.config["TEST_LOGGED_IN"]=True
    app.config["TEST_CAN_READ"]=True
    @app.before_request
    def authenticate():
        if app.config["TEST_LOGGED_IN"]:g.utente_corrente=SimpleNamespace(id="authenticated-studio-user",ha_permesso=lambda _permission:app.config["TEST_CAN_READ"])
    return app


@pytest.mark.parametrize("url",["/giurisprudenza/corpus/api?fonte=curia","/giurisprudenza/corpus/1/testo?embed=source","/giurisprudenza/corpus/1/documenti/1/pdf"])
def test_all_native_routes_require_authentication(app,url):
    app.config["TEST_LOGGED_IN"]=False
    response=app.test_client().get(url)
    assert response.status_code==302 and "/login" in response.headers["Location"]


def test_native_api_reads_filtered_stored_rows(app):
    response=app.test_client().get("/giurisprudenza/corpus/api?fonte=curia&q=1/2026")
    assert response.status_code==200 and response.json["source"]=="curia"
    assert len(response.json["records"])==1 and response.json["records"][0]["title"]=="curia 1/2026"
    assert "no-store" in response.headers["Cache-Control"]


def test_native_reader_is_internal_escaped_and_plaintext_preserved(app,corpus):
    with app.test_client() as client:
        response=client.get("/giurisprudenza/corpus/1/testo")
        assert response.status_code==302 and "corpus_documento=1" in response.headers["Location"]
        response=client.get("/giurisprudenza/corpus/1/testo?embed=source")
        assert response.status_code==200 and b"curia 1/2026" in response.data
        assert "default-src 'none'" in response.headers["Content-Security-Policy"]
        assert client.get("/giurisprudenza/corpus/1/testo?embed=source&format=txt").get_data(as_text=True)==corpus.get_sentenza(1)["testo_integrale"]
        assert client.get("/giurisprudenza/corpus/99999/testo?embed=source").status_code==404


@pytest.mark.parametrize("official",[True,False])
def test_pdf_range_is_streamed_from_canonical_document(app,corpus,official):
    raw=b"%PDF-1.7\noriginal public source";sha=hashlib.sha256(raw).hexdigest();folder=Path(corpus.db_path).parent/"fonti_ufficiali";folder.mkdir();(folder/(sha+".pdf")).write_bytes(raw)
    writer=native.GestioneCorpusGiurisprudenza(corpus.db_path,schema_path=SCHEMA_GIURISPRUDENZA_CORPUS)
    record=writer.salva_sentenza({"uuid_interno":"pdf:1","fonte_codice":"curia","titolo":"Documento PDF","testo_integrale":"Fonte PDF","documenti":[{"tipo_documento":"pdf_ufficiale" if official else "allegato","sha256":sha,"path_locale":"fonti_ufficiali/"+sha+".pdf","valido":True,"ufficiale":official}]})
    sid=record["id"];did=record["documenti"][0]["id"]
    with app.test_client() as client:
        response=client.get(f"/giurisprudenza/corpus/{sid}/documenti/{did}/pdf",headers={"Range":"bytes=0-4"})
        assert response.status_code==206 and response.data==b"%PDF-"
        assert response.headers["Content-Range"]==f"bytes 0-4/{len(raw)}"
        assert client.get(f"/giurisprudenza/corpus/1/documenti/{did}/pdf").status_code==404
        (folder/(sha+".pdf")).write_bytes(b"%PDF-tampered")
        assert client.get(f"/giurisprudenza/corpus/{sid}/documenti/{did}/pdf").status_code==503


def test_native_corpus_revision_tracks_current_studio_and_wal_only(tmp_path,monkeypatch):
    from flask import Flask
    import web.services.tenant_paths as tenant_paths
    from pct.giurisprudenza_corpus import derive_corpus_db_path
    revision=importlib.import_module("web.services.operational_live_sources")
    storage=tmp_path/"current"/"giurisprudenza.json";storage.parent.mkdir();db=Path(derive_corpus_db_path(str(storage)));db.write_bytes(b"one");wal=Path(str(db)+"-wal");wal.write_bytes(b"wal")
    other=tmp_path/"other_corpus.db";other.write_bytes(b"other")
    monkeypatch.setattr(tenant_paths,"tenant_data_path",lambda key,require_tenant=True:str(storage) if key=="GIURISPRUDENZA_DB" else "")
    monkeypatch.delenv("IUSENTRA_SENTENZEWEB_DIRECTORY",raising=False)
    with Flask(__name__).app_context():
        before=revision.legal_source_file_revision();wal.write_bytes(b"changed-wal")
        after=revision.legal_source_file_revision()
    assert str(db) in [row[0] for row in before] and str(wal) in [row[0] for row in before]
    assert before!=after and str(other) not in [row[0] for row in after]


def test_native_reader_escapes_stored_titles_and_body(app,corpus):
    writer=native.GestioneCorpusGiurisprudenza(corpus.db_path,schema_path=SCHEMA_GIURISPRUDENZA_CORPUS)
    record=writer.salva_sentenza({"uuid_interno":"escaped:1","fonte_codice":"curia","titolo":"<img src=x onerror=alert(1)>","testo_integrale":"<script>alert(1)</script>","testo_integrale_presente":True})
    response=app.test_client().get(f"/giurisprudenza/corpus/{record['id']}/testo?embed=source")
    assert response.status_code==200 and b"<script>" not in response.data and b"<img src=x" not in response.data
    assert b"&lt;script&gt;" in response.data


@pytest.mark.parametrize("url",["javascript:alert(1)","http://example.test","https://user:secret@example.test","https://example.test:444/a"])
def test_reader_does_not_publish_unsafe_source_urls(url):
    assert runtime._source_url(url)==""


def test_native_api_does_not_use_client_tenant_override(app):
    response=app.test_client().get("/giurisprudenza/corpus/api?fonte=curia&tenant=other&studio=other")
    assert response.status_code==200 and len(response.json["records"])==1
    assert response.json["records"][0]["title"]=="curia 1/2026"


@pytest.mark.parametrize("url",["/giurisprudenza/corpus/api?fonte=curia","/giurisprudenza/corpus/1/testo?embed=source","/giurisprudenza/corpus/1/documenti/1/pdf"])
def test_logged_in_user_without_legal_read_permission_cannot_access_corpus(app,url):
    app.config["TEST_CAN_READ"]=False
    assert app.test_client().get(url).status_code==403


@pytest.fixture
def real_pdf_record(corpus):
    from io import BytesIO
    from pypdf import PdfWriter
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    writer.add_blank_page(width=200, height=300)
    writer.write(buffer)
    raw = buffer.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    folder = Path(corpus.db_path).parent / "fonti_ufficiali"
    folder.mkdir()
    path = folder / (sha + ".pdf")
    path.write_bytes(raw)
    owner = native.GestioneCorpusGiurisprudenza(corpus.db_path, schema_path=SCHEMA_GIURISPRUDENZA_CORPUS)
    record = owner.salva_sentenza({"uuid_interno": "pdf:real", "fonte_codice": "curia",
        "titolo": "PDF a pagine", "testo_integrale": "Documento conservato", "documenti": [{
        "tipo_documento": "pdf_ufficiale", "sha256": sha, "path_locale": "fonti_ufficiali/"+sha+".pdf",
        "valido": True, "ufficiale": True}]})
    return record["id"], record["documenti"][0]["id"], path, raw


def test_pdf_uses_existing_page_reader_and_preserves_original(app, real_pdf_record):
    sid, did, path, raw = real_pdf_record
    base = f"/giurisprudenza/corpus/{sid}/documenti/{did}"
    client = app.test_client()
    preview = client.get(base + "/pdf?viewer=mobile")
    assert preview.status_code == 200 and preview.mimetype == "text/html"
    assert preview.headers["X-Iusentra-Pdf-Reader"] == "1"
    assert "no-store" in preview.headers["Cache-Control"]
    assert (base + "/pagine/1.png").encode() in preview.data
    assert (base + "/pagine/2.png").encode() in preview.data
    assert b"data-document-pages" in preview.data
    page = client.get(base + "/pagine/2.png")
    assert page.status_code == 200 and page.mimetype == "image/png"
    assert page.data.startswith(b"\x89PNG")
    assert client.get(base + "/pagine/3.png").status_code == 422
    assert client.get(base + "/pdf").data == raw == path.read_bytes()


def test_pdf_pages_fail_closed_on_tampering_or_wrong_record(app, real_pdf_record):
    sid, did, path, _raw = real_pdf_record
    client = app.test_client()
    assert client.get(f"/giurisprudenza/corpus/1/documenti/{did}/pagine/1.png").status_code == 404
    path.write_bytes(b"%PDF-tampered")
    assert client.get(f"/giurisprudenza/corpus/{sid}/documenti/{did}/pdf?viewer=mobile").status_code == 503
    assert client.get(f"/giurisprudenza/corpus/{sid}/documenti/{did}/pagine/1.png").status_code == 503


@pytest.mark.parametrize("logged_in, can_read, status", [(False, True, 302), (True, False, 403)])
def test_pdf_pages_enforce_same_permissions_as_text(app, logged_in, can_read, status):
    app.config["TEST_LOGGED_IN"] = logged_in
    app.config["TEST_CAN_READ"] = can_read
    assert app.test_client().get("/giurisprudenza/corpus/1/documenti/1/pagine/1.png").status_code == status


@pytest.mark.parametrize("method,suffix", [
    ("get", "traduzione-info"), ("post", "traduzioni"),
    ("post", "traduzioni/" + "a"*32 + "/passo"),
    ("get", "traduzioni/" + "a"*32 + "/stato"),
    ("get", "traduzioni/" + "a"*32 + "?embed=source"),
])
@pytest.mark.parametrize("logged_in,can_read,status", [(False,True,302),(True,False,403)])
def test_translation_routes_enforce_legal_permissions(app, method, suffix, logged_in, can_read, status):
    app.config["TEST_LOGGED_IN"] = logged_in
    app.config["TEST_CAN_READ"] = can_read
    response = getattr(app.test_client(), method)("/giurisprudenza/corpus/1/" + suffix)
    assert response.status_code == status


def test_translation_reader_is_internal_and_escapes_both_languages(app, monkeypatch):
    from web.services import giurisprudenza_translation as translations
    data = {"titolo":"<img src=x onerror=alert(1)>", "parti":[{
        "originale":"<script>original</script>", "traduzione":"<script>tradotto</script>", "avviso":""}],
        "source_language":"fr", "avvisi":0, "modello":"test", "motore":"test",
        "revisione":"pinned", "source_sha256":"a"*64, "originale_url":"/giurisprudenza/corpus/1/testo?embed=source"}
    monkeypatch.setattr(translations,"document",lambda owner,sid,identity:data)
    client=app.test_client();url="/giurisprudenza/corpus/1/traduzioni/"+"a"*32
    redirect_response=client.get(url)
    assert redirect_response.status_code==302 and "corpus_traduzione=" in redirect_response.headers["Location"]
    response=client.get(url+"?embed=source")
    assert response.status_code==200
    assert b"<script>" not in response.data and b"<img src=x" not in response.data
    assert b"&lt;script&gt;original" in response.data and b"&lt;script&gt;tradotto" in response.data
    assert b"non ufficiale" in response.data and b"Originale" in response.data
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "no-store" in response.headers["Cache-Control"]
    assert client.get("/giurisprudenza/corpus/1/traduzioni/not-a-translation?embed=source").status_code==404


def test_translation_api_rejects_invalid_payload_and_unavailable_worker_without_leaks(app, monkeypatch):
    from web.services import giurisprudenza_translation as translations
    client=app.test_client();url="/giurisprudenza/corpus/1/traduzioni"
    assert client.post(url,json=["fr"]).status_code==400
    def unavailable(*args,**kwargs):raise OSError("private worker location and credentials must not be shown")
    monkeypatch.setattr(translations,"start",unavailable)
    response=client.post(url,json={"lingua":"fr"})
    assert response.status_code==503 and response.json["ok"] is False
    assert b"credentials" not in response.data and b"private worker" not in response.data
    assert "no-store" in response.headers["Cache-Control"]
