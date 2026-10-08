import json
import sqlite3
from types import SimpleNamespace

import pytest

from pct.document_intelligence.models import DocumentAIRecord, DocumentAIVersion, DocumentAIText, DocumentAIPageText
from pct.document_intelligence.read_view import SQLDocumentAIReader, source_snapshot
from pct.document_intelligence.repository import DocumentAIRepository
from pct.rag_source_provenance import checked_rows, verify_sources, verify_current_sql, provenance_snapshot
from pct.rag_source_reconciliation import recover_sql_proofs, record_recovered_proofs
from pct.rag_embedding_provenance import verified_for_embedding
from pct import local_embedding_index, embeddinggemma2
from pct.rag_sql_document import index_original_source


@pytest.fixture
def source(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db", storage_root=tmp_path / "blobs")
    repo.create_document_record(DocumentAIRecord(
        "ai", "tenant", "case", "Sentenza.pdf", "Sentenza.pdf", "pdf", "application/pdf",
        10, "a" * 64, "ready", "v1", 1, "controlled", "2026-10-08", "2026-10-08"))
    repo.create_version(DocumentAIVersion("v1", "tenant", "case", "ai", 1, "upload",
        "controlled.pdf", None, None, "a" * 64, "controlled", "2026-10-08"))
    repo.save_extracted_text(DocumentAIText("ai", "v1", "tenant", "case",
        "Il giudice liquida € 260,00 in favore del difensore.", [], "pdf-native", "2026-10-08"))
    row = dict(id="chunk", document_id="rag", source_type="fascicolo_documento",
        source_id="original", practice_id="case", text="€ 260,00 in favore del difensore.",
        metadata_json=json.dumps(dict(tenant_id="tenant", source_document_id="original",
            content_sha256="a" * 64, document_ai_id="ai", version_id="v1")))
    try:
        yield repo, row
    finally:
        repo.close()


@pytest.mark.parametrize("defect", [None, "tenant", "hash", "ambiguous", "ai_id", "source_id", "version", "pages"])
def test_shared_writer_uses_original_sql_source(source, defect):
    repo, _ = source
    docs = [SimpleNamespace(id="original", nome="Sentenza.pdf", hash_contenuto_sha256="a"*64)]
    metadata = dict(tenant_id="tenant", sha256="a"*64, document_id="ai")
    if defect == "tenant":
        metadata["tenant_id"] = "other"
    elif defect == "hash":
        metadata["sha256"] = "b"*64
    elif defect == "ambiguous":
        docs.append(SimpleNamespace(id="copy", nome="Sentenza.pdf", hash_contenuto_sha256="a"*64))
    elif defect == "ai_id":
        metadata["document_id"] = "missing"
    elif defect == "source_id":
        metadata["source_id"] = "missing"
    elif defect == "version":
        repo.set_current_version("tenant", "case", "ai", "v2")
    elif defect == "pages":
        repo.save_extracted_text(DocumentAIText("ai", "v1", "tenant", "case",
            "Il giudice liquida € 260,00 in favore del difensore.",
            [DocumentAIPageText(1, "Solo € 260,00")], "pdf-native", "2026-10-08"))
    calls = []

    def index(**kwargs):
        calls.append(kwargs)
        return {"status": "indexed", "document_id": "rag"}

    result = index_original_source(SimpleNamespace(id="case", documenti=docs), repo,
        SimpleNamespace(index_text_document=index), tenant="tenant", metadata=metadata)
    if defect:
        assert not calls and result["status"] == "waiting_for_text" and result["reason"]
    else:
        assert result["status"] == "indexed"
        assert calls[0]["source_type"] == "fascicolo_documento" and calls[0]["source_id"] == "original"
        assert calls[0]["text"] == "Il giudice liquida € 260,00 in favore del difensore."
        assert result["proof"]["version_id"] == "v1"


@pytest.mark.parametrize("defect,reason", [
    ("none", ""), ("tenant", "provenienza_sql_non_registrata"),
    ("missing", "fonte_non_presente_nel_fascicolo_sql"),
    ("hash", "impronta_fonte_cambiata_o_assente"),
    ("version", "estrazione_sql_non_corrente"),
    ("binary", "testo_documentale_non_verificato"),
    ("amount", "passaggio_non_presente_nel_testo_sql"),
    ("derived", "fonte_derivata_senza_prova_documentale"),
    ("derived_other_tenant", "provenienza_sql_non_registrata"),
])
def test_current_sql_source_is_required(source, defect, reason):
    repo, row = source
    doc = dict(id="original", hash_contenuto_sha256="a" * 64)
    if defect == "tenant":
        metadata = json.loads(row["metadata_json"])
        metadata["tenant_id"] = "other"
        row["metadata_json"] = json.dumps(metadata)
    elif defect == "missing":
        doc = None
    elif defect == "hash":
        doc["hash_contenuto_sha256"] = "b" * 64
    elif defect == "version":
        repo.set_current_version("tenant", "case", "ai", "v2")
    elif defect == "binary":
        extracted = repo.get_extracted_text("tenant", "case", "ai", "v1")
        extracted.extraction_engine = "binary-best-effort"
        repo.save_extracted_text(extracted)
    elif defect == "amount":
        row["text"] = "€ 500,00 in favore del difensore."
    elif defect.startswith("derived"):
        row["source_type"] = "lex_sentenza_tribunale"
        if defect == "derived_other_tenant":
            metadata = json.loads(row["metadata_json"])
            metadata["tenant_id"] = "other"
            row["metadata_json"] = json.dumps(metadata)
    accepted, checks = verify_sources([row], tenant="tenant", source_lookup=lambda *args: doc,
                                     repository=SQLDocumentAIReader(repo.structured_db))
    assert checks[0]["reason"] == reason
    assert accepted == ([] if reason else [row])


def test_cached_citation_rechecked_and_rejections_persisted(source):
    repo, row = source
    source_doc = dict(id="original", hash_contenuto_sha256="a" * 64)
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE rag_documents(id TEXT,source_type TEXT,source_id TEXT,sha256 TEXT);")
    conn.execute("CREATE TABLE rag_chunks(id TEXT PRIMARY KEY,document_id TEXT,practice_id TEXT,text TEXT,metadata_json TEXT)")
    conn.execute("INSERT INTO rag_chunks VALUES ('chunk','rag','case',?,?)", (row["text"], row["metadata_json"]))
    conn.execute("INSERT INTO rag_documents VALUES ('rag','fascicolo_documento','original','rag-sha')")
    conn.commit()
    reader = SQLDocumentAIReader(repo.structured_db)
    def verifier(rows):
        return verify_sources(rows, tenant="tenant", source_lookup=lambda *args: source_doc, repository=reader)
    assert len(checked_rows(conn, [row], verifier=verifier, model="controlled")) == 1
    source_doc["hash_contenuto_sha256"] = "b" * 64
    for _ in range(2):
        assert checked_rows(conn, [row], verifier=verifier, model="controlled") == []
    checks = conn.execute("SELECT verified,reason FROM rag_source_checks ORDER BY verified").fetchall()
    assert checks == [(0, "impronta_fonte_cambiata_o_assente"), (1, "")]
    assert provenance_snapshot(conn, "controlled")["excluded_chunks"] == 1
    source_doc["hash_contenuto_sha256"] = "a" * 64
    assert len(checked_rows(conn, [row], verifier=verifier, model="controlled")) == 1
    assert provenance_snapshot(conn, "controlled")["verified_chunks"] == 1
    assert provenance_snapshot(conn, "controlled")["excluded_chunks"] == 0
    assert conn.execute("SELECT COUNT(*) FROM rag_source_checks").fetchone()[0] == 2
    conn.execute("UPDATE rag_chunks SET text='Passaggio modificato'")
    conn.commit()
    assert provenance_snapshot(conn, "controlled")["verified_chunks"] == 0
    assert provenance_snapshot(conn, "controlled")["reasons"] == [
        {"reason": "passaggio_rag_modificato", "chunks": 1}]
    conn.execute("UPDATE rag_chunks SET text=?", (row["text"],))
    conn.commit()
    assert provenance_snapshot(conn, "controlled")["verified_chunks"] == 0
    assert len(checked_rows(conn, [row], verifier=verifier, model="controlled")) == 1
    assert provenance_snapshot(conn, "controlled")["verified_chunks"] == 1
    conn.execute("UPDATE rag_documents SET sha256='nuova-impronta'")
    conn.commit()
    assert provenance_snapshot(conn, "controlled")["verified_chunks"] == 0
    assert provenance_snapshot(conn, "controlled")["reasons"] == [
        {"reason": "fonte_rag_modificata", "chunks": 1}]
    conn.execute("DELETE FROM rag_chunks")
    conn.commit()
    assert provenance_snapshot(conn, "controlled")["checked_chunks"] == 0
    assert conn.execute("SELECT COUNT(*) FROM rag_source_checks").fetchone()[0] == 2
    conn.close()


def test_shared_sql_check_reads_inventory_and_native_text(source):
    repo, row = source
    core = repo.structured_db
    core.conn.execute("CREATE TABLE IF NOT EXISTS fascicoli(id TEXT PRIMARY KEY,documenti_json TEXT)")
    core.conn.execute("INSERT INTO fascicoli VALUES (?,?)", ("case", json.dumps([
        dict(id="original", hash_contenuto_sha256="a" * 64)])))
    core.conn.commit()
    accepted, checks = verify_current_sql([row], tenant="tenant", core=core)
    assert accepted == [row] and checks[0]["reason"] == ""


def test_historical_proof_recovery_requires_current_original_and_audit(source):
    repo, row = source
    core = repo.structured_db
    core.conn.execute("CREATE TABLE IF NOT EXISTS fascicoli(id TEXT PRIMARY KEY,documenti_json TEXT)")
    core.conn.execute("INSERT INTO fascicoli VALUES (?,?)", ("case", json.dumps([
        dict(id="original", hash_contenuto_sha256="a" * 64)])))
    core.conn.commit()
    row["metadata_json"] = json.dumps({"page_from": 1})
    recovered = recover_sql_proofs([row], tenant="tenant", core=core)
    assert len(recovered) == 1
    assert json.loads(recovered[0]["metadata_json"])["version_id"] == "v1"
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE rag_chunks(id TEXT PRIMARY KEY,text TEXT,metadata_json TEXT)")
    conn.execute("INSERT INTO rag_chunks VALUES (?,?,?)", (row["id"], row["text"], row["metadata_json"]))
    conn.commit()
    assert record_recovered_proofs(conn, [row], recovered) == 1
    assert record_recovered_proofs(conn, [row], recovered) == 0
    assert conn.execute("SELECT COUNT(*) FROM rag_source_reconciliation").fetchone()[0] == 1
    assert conn.execute("SELECT text FROM rag_chunks").fetchone()[0] == row["text"]
    assert recover_sql_proofs([{**row, "text": "€ 500,00"}], tenant="tenant", core=core) == []
    assert recover_sql_proofs([{**row, "metadata_json": json.dumps({"tenant_id": "other"})}],
                             tenant="tenant", core=core) == []
    conn.close()


def test_negative_embedding_waits_for_verified_new_evidence(source):
    repo, row = source
    conn = sqlite3.connect(":memory:")
    conn.executescript("""CREATE TABLE rag_documents(id TEXT PRIMARY KEY,source_type TEXT,source_id TEXT,sha256 TEXT,parse_state TEXT);
        CREATE TABLE rag_chunks(id TEXT PRIMARY KEY,document_id TEXT,text TEXT,metadata_json TEXT,embedding_state TEXT,practice_id TEXT DEFAULT 'case');""")
    conn.execute("INSERT INTO rag_documents VALUES ('rag','fascicolo_documento','original','rag-sha','parsed')")
    original_text = row["text"]
    row.update(document_sha256="rag-sha", parse_state="parsed", text="€ 500,00 al difensore.")
    conn.execute("INSERT INTO rag_chunks(id,document_id,text,metadata_json,embedding_state) VALUES (?,?,?,?,?)", (row["id"], "rag", row["text"], row["metadata_json"], "pending"))
    conn.commit()
    local_embedding_index.ensure_schema(conn)
    def verifier(rows):
        return verify_sources(rows, tenant="tenant", repository=SQLDocumentAIReader(repo.structured_db),
                              source_lookup=lambda *args: dict(hash_contenuto_sha256="a" * 64))
    accepted, rejected, changed = verified_for_embedding(conn, [row], verifier=verifier)
    assert accepted == [] and rejected == 1 and changed == 0
    generation = conn.execute("SELECT status,reason FROM rag_embedding_generations").fetchone()
    assert generation == ("invalid", "source_provenance:passaggio_non_presente_nel_testo_sql")
    assert conn.execute("SELECT embedding_state FROM rag_chunks").fetchone()[0] == "pending"
    row["text"] = original_text
    conn.execute("UPDATE rag_chunks SET text=?,embedding_state='pending'", (original_text,))
    conn.commit()
    accepted, rejected, changed = verified_for_embedding(conn, [row], verifier=verifier)
    assert len(accepted) == 1 and rejected == changed == 0
    assert conn.execute("SELECT status FROM rag_embedding_generations").fetchone()[0] == "building"
    assert conn.execute("SELECT model FROM rag_embedding_generations").fetchone()[0] == embeddinggemma2.MODEL
    with pytest.raises(ValueError, match="obbligatorio"):
        verified_for_embedding(conn, [row], verifier=None)
    conn.close()


def test_metadata_event_retries_negative_once_without_consuming_legacy_queue(source):
    repo, row = source
    conn = sqlite3.connect(":memory:")
    conn.executescript("""CREATE TABLE rag_documents(id TEXT PRIMARY KEY,source_type TEXT,source_id TEXT,sha256 TEXT,parse_state TEXT);
        CREATE TABLE rag_chunks(id TEXT PRIMARY KEY,document_id TEXT,text TEXT,metadata_json TEXT,embedding_state TEXT,practice_id TEXT);""")
    conn.execute("INSERT INTO rag_documents VALUES ('rag','fascicolo_documento','original','rag-sha','parsed')")
    valid_metadata = row["metadata_json"]
    row.update(document_sha256="rag-sha", parse_state="parsed", metadata_json="{}")
    conn.execute("INSERT INTO rag_chunks VALUES (?,?,?,?,?,?)", (row["id"], "rag", row["text"], "{}", "pending", "case"))
    conn.commit()
    local_embedding_index.ensure_schema(conn)

    def verifier(rows):
        return verify_sources(rows, tenant="tenant", repository=SQLDocumentAIReader(repo.structured_db),
                              source_lookup=lambda *args: dict(hash_contenuto_sha256="a" * 64))

    def pending():
        condition = local_embedding_index.pending_condition(conn)
        return conn.execute("SELECT COUNT(*) FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id WHERE " + condition,
                            (embeddinggemma2.MODEL,)).fetchone()[0]

    assert verified_for_embedding(conn, [row], verifier=verifier)[1] == 1
    assert pending() == 0
    # Un nuovo riscontro ancora insufficiente deve essere esaminato una volta.
    row["metadata_json"] = '{"tenant_id":"tenant"}'
    conn.execute("UPDATE rag_chunks SET metadata_json=?", (row["metadata_json"],))
    conn.commit()
    assert pending() == 1
    assert verified_for_embedding(conn, [row], verifier=verifier)[1] == 1
    assert pending() == 0
    # Arriva la provenienza completa dello stesso testo e della stessa impronta.
    row["metadata_json"] = valid_metadata
    conn.execute("UPDATE rag_chunks SET metadata_json=?", (valid_metadata,))
    conn.commit()
    assert pending() == 1
    accepted, rejected, changed = verified_for_embedding(conn, [row], verifier=verifier)
    assert accepted == [row] and rejected == changed == 0
    assert conn.execute("SELECT status FROM rag_embedding_generations").fetchone()[0] == "building"
    assert conn.execute("SELECT embedding_state FROM rag_chunks").fetchone()[0] == "pending"
    conn.close()


def test_metadata_changed_during_check_is_not_delivered_to_embedder(source):
    repo, row = source
    conn = sqlite3.connect(":memory:")
    conn.executescript("""CREATE TABLE rag_documents(id TEXT PRIMARY KEY,source_type TEXT,source_id TEXT,sha256 TEXT);
        CREATE TABLE rag_chunks(id TEXT PRIMARY KEY,document_id TEXT,text TEXT,metadata_json TEXT);""")
    conn.execute("INSERT INTO rag_documents VALUES ('rag','fascicolo_documento','original','rag-sha')")
    conn.execute("INSERT INTO rag_chunks VALUES (?,?,?,?)", (row["id"], "rag", row["text"], row["metadata_json"]))
    conn.commit()
    row["document_sha256"] = "rag-sha"
    def verifier(rows):
        result = verify_sources(rows, tenant="tenant", repository=SQLDocumentAIReader(repo.structured_db),
                                source_lookup=lambda *args: dict(hash_contenuto_sha256="a" * 64))
        conn.execute("UPDATE rag_chunks SET metadata_json='{}'")
        conn.commit()
        return result
    accepted, rejected, changed = verified_for_embedding(conn, [row], verifier=verifier)
    assert accepted == [] and rejected == 0 and changed == 1
    conn.close()


def test_inventory_and_extraction_share_readonly_wal_snapshot(tmp_path):
    db = tmp_path / "studio.db"
    writer = sqlite3.connect(db)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE evidence(id TEXT PRIMARY KEY, value TEXT)")
    writer.execute("INSERT INTO evidence VALUES ('source','v1')")
    writer.commit()
    try:
        with source_snapshot(SimpleNamespace(db_path=db)) as snapshot:
            assert snapshot.conn.execute("SELECT value FROM evidence").fetchone()[0] == "v1"
            writer.execute("UPDATE evidence SET value='v2'")
            writer.commit()
            assert snapshot.conn.execute("SELECT value FROM evidence").fetchone()[0] == "v1"
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                snapshot.conn.execute("DELETE FROM evidence")
        with source_snapshot(SimpleNamespace(db_path=db)) as snapshot:
            assert snapshot.conn.execute("SELECT value FROM evidence").fetchone()[0] == "v2"
    finally:
        writer.close()


def test_sql_reader_does_not_initialize_storage(source, monkeypatch):
    repo, row = source
    monkeypatch.setattr(DocumentAIRepository, "_ensure_sql_schema", lambda *args: pytest.fail("Migrazione in consultazione"))
    monkeypatch.setattr(DocumentAIRepository, "_load_json", lambda *args: pytest.fail("Lettura JSON storico"))
    reader = SQLDocumentAIReader(repo.structured_db)
    assert reader.get_document("tenant", "case", "ai").sha256 == "a" * 64
    assert reader.get_document("other", "case", "ai") is None
    assert not hasattr(reader, "create_document_record")
    with pytest.raises(ValueError):
        SQLDocumentAIReader(SimpleNamespace())
