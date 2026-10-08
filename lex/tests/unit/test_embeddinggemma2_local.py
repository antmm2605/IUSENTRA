"""Guardrail shardabili: nessun download, modello finto solo per contratti tecnici."""
from __future__ import annotations

import threading
import time
import sqlite3
import subprocess
import sys
import os
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from deploy.embeddinggemma2.server import InferenceGate
from pct import embeddinggemma2
from pct import local_embedding_index
from pct.local_ai import _bounded_text_parts, _embedding_validation_reason


@pytest.mark.parametrize("runtime", ["sentence_transformers", "litert"])
def test_profilo_nuovo_distinto_e_documento_intero(runtime):
    env = dict(os.environ, IUSENTRA_EMBEDDING_RUNTIME=runtime,
               IUSENTRA_EMBEDDING_PROVIDER="embeddinggemma2_local")
    code = '''
from pct import embeddinggemma2 as e
from lex.ricerca_giuridica.embedding import testo_documento, PREFISSO_DOMANDA
body = "testo " * 1000 + "dispositivo finale euro 260"
prepared = testo_documento("Sentenza", body)
assert prepared.endswith("dispositivo finale euro 260")
assert PREFISSO_DOMANDA == e.QUERY_PREFIX
if e.RUNTIME == "litert":
    assert prepared.startswith(e.DOCUMENT_PREFIX)
    assert "q4-qat-litert0180-segments768-mean" in e.MODEL
else:
    assert prepared.startswith("title: Sentenza | text: ")
    assert "text-f32" in e.MODEL
'''
    subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=30)


def test_prefisso_e_limite_precedente_preservati(monkeypatch):
    from lex.ricerca_giuridica.embedding import testo_documento
    monkeypatch.delenv("IUSENTRA_EMBEDDING_PROVIDER", raising=False)
    assert testo_documento("Sentenza", "abcdef", massimo=3) == "title: Sentenza | text: abc"


def test_timeout_locale_non_moltiplica_i_tentativi_del_job(monkeypatch):
    from lex.ricerca_giuridica.embedding import OllamaEmbedder
    calls = []
    embedder = OllamaEmbedder(modello=embeddinggemma2.MODEL, tentativi=4)
    def fail(texts):
        calls.append(texts)
        raise TimeoutError("worker locale occupato")
    monkeypatch.setattr(embedder, "_embed_una_volta", fail)
    with pytest.raises(RuntimeError) as failure:
        embedder.embed(["Documento completo"])
    assert isinstance(failure.value.__cause__, TimeoutError)
    assert calls == [["Documento completo"]]
    assert not embedder.testi_ridotti


def test_documento_lungo_cede_turno_senza_perdere_finale():
    from deploy.embeddinggemma2 import litert_encoder as adapter
    calls = []
    class Model:
        def compute_embedding(self, text, options):
            calls.append(text)
            return SimpleNamespace(embedding=[1.0] + [0.0] * 767)
    encoder = adapter.LiteRTEncoder.__new__(adapter.LiteRTEncoder)
    encoder.model = Model()
    encoder.gate = InferenceGate()
    encoder.document_options = object()
    encoder.query_options = object()
    body = "prima pagina\n" * 130 + "dispositivo finale: € 260,00"
    vector = encoder.embed([adapter.DOCUMENT_PREFIX + body])[0]
    assert "".join(text[len(adapter.DOCUMENT_PREFIX):] for text in calls) == body
    assert len(calls) > 1
    assert max(len(text) - len(adapter.DOCUMENT_PREFIX) for text in calls) <= 768
    assert vector == [1.0] + [0.0] * 767
    assert encoder.gate.busy is False and encoder.gate.pending == []


@pytest.mark.parametrize("url", [
    "https://example.com", "http://example.com", "http://localhost@evil.example",
    "http://localhost:11140/path", "http://localhost?target=external",
])
def test_endpoint_esterno_rifiutato(monkeypatch, url):
    monkeypatch.setenv("IUSENTRA_EMBEDDING_LOCAL_URL", url)
    with pytest.raises(ValueError):
        embeddinggemma2.base_url()


def test_trasporto_versionato_e_lotti(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        def raise_for_status(self):
            pass

        def json(self):
            return {"model": embeddinggemma2.MODEL, "embeddings": [[1.0] + [0.0] * 767] * len(calls[-1])}

    def post(self, url, *, json, timeout, allow_redirects):
        assert self.trust_env is False
        assert allow_redirects is False
        calls.append(json["input"])
        assert json["model"] == embeddinggemma2.MODEL
        assert timeout[1] == 120
        return Response()

    monkeypatch.setenv("IUSENTRA_EMBEDDING_LOCAL_URL", "http://localhost:11140")
    monkeypatch.setenv("HTTP_PROXY", "http://external.example:8080")
    monkeypatch.setenv("ALL_PROXY", "http://external.example:8080")
    monkeypatch.setattr("requests.Session.post", post)
    result = embeddinggemma2.LocalEmbeddingClient().embed_texts(embeddinggemma2.MODEL, ["testo"] * 33)
    assert [len(c) for c in calls] == [16, 16, 1]
    assert len(result["embeddings"]) == 33


@pytest.mark.parametrize("model,vector", [
    ("embeddinggemma:300m", [0.0] * 768),
    (embeddinggemma2.MODEL, [0.0] * 512),
    (embeddinggemma2.MODEL, [float("nan")] * 768),
    (embeddinggemma2.MODEL, [0.0] * 768),
])
def test_non_scrivere_vettori_incompatibili(monkeypatch, model, vector):
    class Response:
        status_code = 200
        def raise_for_status(self):
            pass

        def json(self):
            return {"model": model, "embeddings": [vector]}

    monkeypatch.setattr("requests.Session.post", lambda *_args, **_kwargs: Response())
    with pytest.raises(ValueError):
        embeddinggemma2.LocalEmbeddingClient().embed_texts(embeddinggemma2.MODEL, ["testo"])


def test_domanda_precede_indicizzazione_in_attesa():
    gate = InferenceGate()
    order = []

    def enter(query):
        with gate.slot(query):
            order.append(query)

    with gate.slot(False):
        doc = threading.Thread(target=enter, args=(False,))
        query = threading.Thread(target=enter, args=(True,))
        doc.start()
        query.start()
        deadline = time.monotonic() + 1
        while len(gate.pending) != 2 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(gate.pending) == 2
    doc.join(timeout=1)
    query.join(timeout=1)
    assert order == [True, False]


def index_fixture():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE rag_documents(id TEXT PRIMARY KEY, sha256 TEXT,parse_state TEXT,source_type TEXT,source_id TEXT);
        CREATE TABLE rag_chunks(id TEXT PRIMARY KEY,document_id TEXT,practice_id TEXT,
            section_type TEXT,ordinal INTEGER,page_from INTEGER,page_to INTEGER,
            metadata_json TEXT,text TEXT,embedding_state TEXT,embedding_json TEXT);
        INSERT INTO rag_documents VALUES ('doc','source-sha','parsed','fascicolo_documento','original');
    """)
    text = "Sentenza: spese liquidate al difensore. " * 180
    conn.execute("INSERT INTO rag_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 ("chunk", "doc", "case", "dispositivo", 1, 2, 2, "{}", text, "embedded", "legacy-vector"))
    conn.commit()
    local_embedding_index.ensure_schema(conn)
    row = dict(id="chunk",text=text,document_sha256="source-sha",parse_state="parsed")
    return conn,row


class Client:
    def embed_texts(self, model, texts):
        return {"embeddings": [[1.0]+[0.0]*767 for _ in texts]}


def test_budget_riporta_chunk_gia_salvati(monkeypatch):
    conn, row = index_fixture()
    row["text"] = "Sentenza: spese liquidate al difensore."
    conn.execute("UPDATE rag_chunks SET text=?", (row["text"],))
    conn.execute("INSERT INTO rag_chunks SELECT 'second',document_id,practice_id,section_type,2,page_from,page_to,metadata_json,text,embedding_state,embedding_json FROM rag_chunks")
    conn.commit()
    clock = [0]
    monkeypatch.setattr(local_embedding_index.time, "monotonic", lambda: clock[0])

    class TimedClient(Client):
        def embed_texts(self, model, texts):
            clock[0] = 61
            return super().embed_texts(model, texts)

    with pytest.raises(TimeoutError) as failure:
        local_embedding_index.build_chunks(conn, [row, {**row, "id": "second"}],
            split=_bounded_text_parts, validate=_embedding_validation_reason, client=TimedClient(), deadline=60)
    assert failure.value.embedding_progress["embedded"] == 1
    assert conn.execute("SELECT status FROM rag_embedding_generations WHERE chunk_id='chunk'").fetchone()[0] == "embedded"


def test_lotti_condividono_budget_e_contano_progressi_parziali():
    from pct.local_ai import LocalAIService
    service = object.__new__(LocalAIService)
    service._embedding_provider = lambda: embeddinggemma2.PROVIDER
    deadlines = []
    payloads = iter([
        {"status": "ready", "embedded": 0, "invalid": 8, "pending_remaining": 2},
        {"status": "pending", "embedded": 1, "invalid": 0, "pending_remaining": 1},
    ])

    def batch(**kwargs):
        deadlines.append(kwargs["_deadline"])
        return next(payloads)

    service.embed_pending_chunks = batch
    result = service.embed_all_pending_chunks()
    assert len(deadlines) == 2 and deadlines[0] == deadlines[1]
    assert result["status"] == "pending" and result["embedded_total"] == 1 and result["batches"] == 2


def build(conn, row, client=None):
    return local_embedding_index.build_chunks(conn,[row],split=_bounded_text_parts,
                                              validate=_embedding_validation_reason,client=client or Client())


def test_migrazione_conserva_testo_vettori_precedenti_e_prova():
    conn,row = index_fixture()
    assert build(conn,row)["embedded"] == 1
    vectors = local_embedding_index.vector_rows(conn,practice_id="case")
    assert len(vectors)>1
    assert all(v["page_from"]==2 and v["document_id"]=="doc" for v in vectors)
    assert "".join(v["text"] for v in vectors)==row["text"]
    assert conn.execute("SELECT embedding_json FROM rag_chunks").fetchone()[0]=="legacy-vector"
    assert build(conn,row)["unchanged"] == 1
    assert local_embedding_index.vector_rows(conn,practice_id="other-case")==[]


@pytest.mark.parametrize("legacy_state", ["pending", "embedded", "invalid"])
def test_candidate_generation_preserves_legacy_work_queue(legacy_state, monkeypatch):
    from pct.local_ai import LocalAIService
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", embeddinggemma2.PROVIDER)
    conn, row = index_fixture()
    service = object.__new__(LocalAIService)
    conn.execute("UPDATE rag_chunks SET embedding_state=?", (legacy_state,))
    conn.commit()
    assert service._pending_chunks_count(conn) == 1
    assert build(conn, row)["embedded"] == 1
    assert tuple(conn.execute("SELECT embedding_state,embedding_json FROM rag_chunks").fetchone()) == (legacy_state, "legacy-vector")
    assert conn.execute("SELECT status FROM rag_embedding_generations").fetchone()[0] == "embedded"
    assert service._pending_chunks_count(conn) == 0
    assert service._pending_chunks_count(conn, practice_id="another-case") == 0
    conn.execute("UPDATE rag_chunks SET text='Testo modificato'")
    conn.commit()
    assert service._pending_chunks_count(conn) == 1
    conn.close()


def test_budget_preserva_segmenti_e_ripresa_della_generazione(monkeypatch):
    conn, row = index_fixture()
    row["text"] *= 4
    conn.execute("UPDATE rag_chunks SET text=?", (row["text"],))
    conn.commit()
    clock = [0]
    monkeypatch.setattr(local_embedding_index, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    class BudgetClient(Client):
        def embed_texts(self, model, texts):
            clock[0] = 61
            return super().embed_texts(model, texts)
    with pytest.raises(TimeoutError, match="Budget"):
        local_embedding_index.build_chunks(conn, [row], split=_bounded_text_parts,
            validate=_embedding_validation_reason, client=BudgetClient(), deadline=60)
    assert conn.execute("SELECT status FROM rag_embedding_generations").fetchone()[0] == "building"
    assert conn.execute("SELECT COUNT(*) FROM rag_embedding_segments").fetchone()[0] == 16
    assert local_embedding_index.vector_rows(conn) == []
    resumed = []
    class ResumeClient(Client):
        def embed_texts(self, model, texts):
            resumed.extend(texts)
            return super().embed_texts(model, texts)
    assert build(conn, row, ResumeClient())["embedded"] == 1
    assert len(resumed) == len(_bounded_text_parts(row["text"], max_chars=768))-16
    assert local_embedding_index.vector_rows(conn)


def test_fonte_cambiata_esclude_vettore_precedente_e_lo_aggiorna():
    conn,row = index_fixture()
    build(conn,row)
    conn.execute("UPDATE rag_chunks SET text='Nuovo dispositivo'")
    conn.commit()
    assert local_embedding_index.vector_rows(conn)==[]
    row["text"] = "Nuovo dispositivo"
    build(conn,row)
    rows = local_embedding_index.vector_rows(conn)
    assert len(rows)==1 and rows[0]["text"]==row["text"]
    conn.execute("DELETE FROM rag_chunks")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM rag_embedding_segments").fetchone()[0]==0


def test_modifica_concorrente_durante_inferenza_non_pubblica_prova():
    conn,row = index_fixture()

    class ChangingClient(Client):
        def embed_texts(self,model,texts):
            conn.execute("UPDATE rag_documents SET sha256='replaced'")
            conn.commit()
            return super().embed_texts(model,texts)

    assert build(conn,row,ChangingClient())["changed_source"]==1
    assert local_embedding_index.vector_rows(conn)==[]


def test_errore_persistente_non_ripete_la_stessa_fonte():
    conn,row = index_fixture()
    row["text"] = "PCTENC contenuto cifrato"
    conn.execute("UPDATE rag_chunks SET text=?",(row["text"],))
    conn.commit()
    assert build(conn,row)["invalid"]==1
    assert build(conn,row)["unchanged"]==1
    assert local_embedding_index.vector_rows(conn)==[]


def test_revoca_della_lettura_durante_inferenza_non_pubblica_il_chunk():
    conn,row=index_fixture()

    class RevokingClient(Client):
        def embed_texts(self,model,texts):
            conn.execute("UPDATE rag_documents SET parse_state='needs_ocr'")
            conn.commit()
            return super().embed_texts(model,texts)

    assert build(conn,row,RevokingClient())["changed_source"]==1
    assert conn.execute("SELECT status FROM rag_embedding_generations").fetchone()[0]=="building"
    assert local_embedding_index.vector_rows(conn)==[]


def test_ripresa_non_ricalcola_i_segmenti_gia_confermati():
    conn,row = index_fixture()
    row["text"] *= 15
    conn.execute("UPDATE rag_chunks SET text=?",(row["text"],))
    conn.commit()
    calls=[]

    class InterruptedClient(Client):
        def embed_texts(self,model,texts):
            calls.append(texts)
            if len(calls)==2:
                raise ConnectionError("Interruzione controllata")
            return super().embed_texts(model,texts)

    with pytest.raises(ConnectionError):
        build(conn,row,InterruptedClient())
    assert conn.execute("SELECT COUNT(*) FROM rag_embedding_segments").fetchone()[0]==16
    assert local_embedding_index.vector_rows(conn)==[]
    before=calls[0]
    calls.clear()

    class ResumingClient(Client):
        def embed_texts(self,model,texts):
            calls.extend(texts)
            return super().embed_texts(model,texts)

    assert build(conn,row,ResumingClient())["embedded"]==1
    assert len(calls)==len(_bounded_text_parts(row["text"],max_chars=local_embedding_index.SEGMENT_CHARS))-16
    assert len(local_embedding_index.vector_rows(conn))==len(_bounded_text_parts(row["text"],max_chars=local_embedding_index.SEGMENT_CHARS))
    assert len(before)==16


def test_lex_non_accorcia_testo_rifiutato(monkeypatch):
    from lex.ricerca_giuridica.embedding import OllamaEmbedder
    monkeypatch.setenv("IUSENTRA_EMBEDDING_LOCAL_URL","http://localhost:11140")
    calls=[]

    def fail(self,model,texts):
        calls.append(texts)
        raise ValueError("Testo rifiutato")

    monkeypatch.setattr(embeddinggemma2.LocalEmbeddingClient,"embed_texts",fail)
    text="Documento completo"*200
    with pytest.raises(RuntimeError):
        OllamaEmbedder(modello=embeddinggemma2.MODEL,tentativi=1).embed([text])
    assert calls==[[text]]


def test_modello_locale_non_sostituisce_la_chat_ne_riprende_vecchi_vettori(monkeypatch):
    from pct.local_ai import LocalAIService
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER",embeddinggemma2.PROVIDER)
    service=object.__new__(LocalAIService)
    result=service._resolve_effective_models(
        settings=SimpleNamespace(chat_model="gemma3:1b",embed_model="embeddinggemma:300m"),
        hardware={"profile":"weak"},policy={},
        installed_models=[{"name":"gemma3:1b"},{"name":"embeddinggemma:300m"}],
    )
    assert result["chat_model"]=="gemma3:1b"
    assert result["embed_model"]==embeddinggemma2.MODEL


def test_factory_multi_studio_non_usa_il_repository_globale():
    from flask import Flask
    from lex.providers.local_ai_service import _cfg_data_path
    app=Flask(__name__)
    app.config.update(MULTI_TENANT=True,LOCAL_AI_DB="global.db")
    with app.test_request_context():
        with pytest.raises(RuntimeError,match="Contesto studio"):
            _cfg_data_path("LOCAL_AI_DB")
    with app.app_context():
        with pytest.raises(RuntimeError,match="Contesto studio"):
            _cfg_data_path("LOCAL_AI_DB")


def test_contatori_non_dichiarano_indicizzata_una_fonte_cambiata(monkeypatch):
    from pct.local_ai import LocalAIService
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER",embeddinggemma2.PROVIDER)
    conn,row=index_fixture()
    service=object.__new__(LocalAIService)
    counts={"documents_total":1,"chunks_total":1,"chunks_embedded":1,"chunks_pending":0}
    assert service._effective_embedding_counts(conn,counts)["chunks_pending"]==1
    build(conn,row)
    assert service._effective_embedding_counts(conn,counts)["chunks_embedded"]==1
    conn.execute("UPDATE rag_chunks SET text='Testo modificato'")
    conn.commit()
    actual=service._effective_embedding_counts(conn,counts)
    assert actual["chunks_embedded"]==0 and actual["chunks_pending"]==1


def test_ai_disabilitata_non_avvia_inferenza_ne_indicizzazione(monkeypatch):
    from pct.local_ai import LocalAIService
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER",embeddinggemma2.PROVIDER)
    service=object.__new__(LocalAIService)
    service._load_settings=lambda: SimpleNamespace(enabled=False,embed_model="embeddinggemma:300m")
    service._embedding_client=lambda settings: pytest.fail("Inferenza avviata con AI disabilitata")
    service._connect=lambda: pytest.fail("Indicizzazione avviata con AI disabilitata")
    assert service.embed_pending_chunks()=={
        "status":"disabled","embedded":0,"embedding_provider":embeddinggemma2.PROVIDER,
    }


def test_segnaposto_font_non_sono_testo_letto():
    assert "CID" in _embedding_validation_reason("(cid:99)(cid:111)(cid:109)")
    assert _embedding_validation_reason("Società, perché: € 260,00, oltre spese generali.") is None


def test_ripresa_migrazione_valida_la_dimensione_del_checkpoint(tmp_path, monkeypatch):
    from scripts import migra_embeddinggemma2_locale as migration
    conn, row = index_fixture()
    build(conn, row)
    root = tmp_path / "studio"
    root.mkdir()
    db = root / "local_ai.db"
    with sqlite3.connect(db) as dest:
        conn.backup(dest)
    conn.close()
    monkeypatch.setattr(embeddinggemma2, "configured", lambda: True)
    # La segmentazione differente era la causa reale delle rivalutazioni:
    # simulare una regola dipendente dalla dimensione, non l'inferenza.
    monkeypatch.setattr(migration, "_embedding_validation_reason",
                        lambda part: "dimensione_diversa" if len(part) > 768 else None)
    for iteration in range(2):
        result = migration.migrate(db, tmp_path / "backup.db", root, source_verifier=lambda rows: (rows, []))
        assert result["examined"] == 0
        assert result["unchanged"] == (1 if iteration == 0 else 0)
        assert result["visited"] == (1 if iteration == 0 else 0)
        assert result["completed"] is True
        assert result["embedded"] == result["invalid"] == 0


def test_migrazione_limita_anche_le_righe_gia_elaborate(tmp_path, monkeypatch):
    from scripts import migra_embeddinggemma2_locale as migration
    conn, row = index_fixture()
    build(conn, row)
    for number in (2, 3):
        conn.execute("INSERT INTO rag_chunks SELECT ?,document_id,practice_id,section_type,?,"
                     "page_from,page_to,metadata_json,text,embedding_state,embedding_json "
                     "FROM rag_chunks WHERE id='chunk'", (f"chunk-{number}", number))
        conn.commit()
        build(conn, {**row, "id": f"chunk-{number}"})
    root = tmp_path / "studio"
    root.mkdir()
    db = root / "local_ai.db"
    with sqlite3.connect(db) as dest:
        conn.backup(dest)
    conn.close()
    monkeypatch.setattr(embeddinggemma2, "configured", lambda: True)
    for expected_cursor in (1, 2, 3):
        report = migration.migrate(db, tmp_path / "backup.db", root, limit=1,
                                   source_verifier=lambda rows: (rows, []))
        assert report["visited"] == report["unchanged"] == 1
        assert report["last_rowid"] == expected_cursor
        assert report["completed"] is (expected_cursor == 3)
    assert migration.migrate(db, tmp_path / "backup.db", root, limit=1,
                              source_verifier=lambda rows: (rows, []))["visited"] == 0


def test_migrazione_registra_fonte_non_provata_senza_inferenza(tmp_path, monkeypatch):
    from scripts import migra_embeddinggemma2_locale as migration
    conn, row = index_fixture()
    root = tmp_path / "studio"
    root.mkdir()
    db = root / "local_ai.db"
    with sqlite3.connect(db) as dest:
        conn.backup(dest)
    conn.close()
    monkeypatch.setattr(embeddinggemma2, "configured", lambda: True)
    monkeypatch.setattr(local_embedding_index, "build_chunks", lambda *a, **k: pytest.fail("Inferenza senza prova"))
    def rejected(rows):
        return [], [dict(chunk_id=rows[0]["id"], reason="fonte_non_presente_nel_fascicolo_sql")]
    report = migration.migrate(db, tmp_path / "backup.db", root, source_verifier=rejected)
    assert report["provenance_excluded"] == report["visited"] == 1
    assert report["examined"] == report["embedded"] == 0
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT embedding_json FROM rag_chunks").fetchone()[0] == "legacy-vector"
        assert conn.execute("SELECT verified,reason FROM rag_source_current").fetchone() == (
            0, "fonte_non_presente_nel_fascicolo_sql")


@pytest.mark.parametrize("backend", ["SQLITE", "POSTGRESQL"])
def test_migrazione_live_rifiuta_cartella_storica_e_sql_estraneo(tmp_path, backend):
    from pct.tenant import GestioneTenant, StudioLegale, DatabaseConfig
    from pct.storage_postgres import build_postgres_dsn
    from scripts.migra_embeddinggemma2_locale import resolve_live_core

    registry = tmp_path / "tenants.json"
    studio = StudioLegale(slug="studio-test", storage_key="tenant-corrente",
                         db_config=DatabaseConfig(mode=backend, host="localhost",
                            db_name="controllato", utente="test", password="solo-test",
                            connessione_ok=True, core_runtime_enabled=True).to_dict())
    registry.write_text(json.dumps({studio.slug: studio.to_dict()}), encoding="utf-8")
    manager = GestioneTenant(str(registry))
    paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
    root = Path(paths["STUDIO_DB"]).parent
    db = Path(paths["LOCAL_AI_DB"])
    db.parent.mkdir(parents=True)
    db.touch()
    core = Path(paths["STUDIO_DB"])
    core.touch()
    dsn = build_postgres_dsn(host="localhost", port=5432, db_name="controllato",
                            user="test", password="solo-test", ssl=False) if backend == "POSTGRESQL" else ""
    kwargs = dict(registry=registry, tenant=studio.slug, db=db, tenant_root=root,
                  core_db=core if backend == "SQLITE" else None, dsn=dsn)
    live = resolve_live_core(**kwargs)
    assert (live.dsn == dsn) if dsn else live.db_path == core
    old = root.parent / studio.slug
    old.mkdir()
    old_core = old / "studio.db"
    old_core.touch()
    with pytest.raises(ValueError, match="Repository o radice"):
        resolve_live_core(**{**kwargs, "tenant_root": old})
    with pytest.raises(ValueError, match="corrente"):
        resolve_live_core(**{**kwargs, "core_db": old_core})
    with pytest.raises(ValueError, match="Studio non presente"):
        resolve_live_core(**{**kwargs, "tenant": "altro-studio"})
    if dsn:
        with pytest.raises(ValueError, match="Connessione diversa"):
            resolve_live_core(**{**kwargs, "dsn": dsn.replace("controllato", "estraneo")})


def test_ricerca_segmenti_restituisce_un_solo_chunk_con_citazione():
    from pct.local_ai import LocalAIService
    conn, row = index_fixture()
    build(conn, row)
    service = object.__new__(LocalAIService)
    results = service._vector_rows(
        conn, [1.0] + [0.0] * 767, "case", None, 8,
        embedding_provider=embeddinggemma2.PROVIDER, embedding_model=embeddinggemma2.MODEL,
    )
    assert len(results) == 1
    assert results[0]["id"] == results[0]["source_chunk_id"] == "chunk"
    assert results[0]["segment_id"].startswith("chunk:")
    assert results[0]["document_id"] == "doc" and results[0]["page_from"] == 2
    assert results[0]["vector_score"] == 1.0


def test_cache_float32_si_riprende_senza_ricalcolo_ne_modifica_degli_originali():
    conn, row = index_fixture()
    build(conn, row)
    original = conn.execute("SELECT text,embedding_json FROM rag_chunks").fetchone()
    vectors = conn.execute("SELECT ordinal,embedding_json FROM rag_embedding_segments ORDER BY ordinal").fetchall()
    conn.execute("UPDATE rag_embedding_segments SET embedding_f32=NULL")
    conn.commit()
    assert local_embedding_index.prepare_binary_vectors(conn, limit=2) == 2
    assert local_embedding_index.prepare_binary_vectors(conn, limit=128) == len(vectors) - 2
    assert local_embedding_index.prepare_binary_vectors(conn) == 0
    assert tuple(conn.execute("SELECT text,embedding_json FROM rag_chunks").fetchone()) == tuple(original)
    assert [tuple(r) for r in conn.execute("SELECT ordinal,embedding_json FROM rag_embedding_segments ORDER BY ordinal")] == [tuple(r) for r in vectors]
    assert all(len(r[0]) == 768 * 4 for r in conn.execute("SELECT embedding_f32 FROM rag_embedding_segments"))


def test_cache_float32_rifiuta_vettori_corrotti():
    conn, row = index_fixture()
    build(conn, row)
    conn.execute("UPDATE rag_embedding_segments SET embedding_f32=NULL,embedding_json='[1]'")
    conn.commit()
    with pytest.raises(ValueError, match="Vettore locale non valido"):
        local_embedding_index.prepare_binary_vectors(conn)
    assert conn.execute("SELECT COUNT(*) FROM rag_embedding_segments WHERE embedding_f32 IS NOT NULL").fetchone()[0] == 0


def test_ricerca_testuale_rispetta_esiti_e_impronte_del_modello_corrente(monkeypatch):
    from pct.local_ai import LocalAIService
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", embeddinggemma2.PROVIDER)
    conn, row = index_fixture()
    conn.execute("CREATE VIRTUAL TABLE rag_chunks_fts USING fts5(text)")
    conn.execute("INSERT INTO rag_chunks_fts(rowid,text) SELECT rowid,text FROM rag_chunks")
    conn.commit()
    build(conn, row)
    service = object.__new__(LocalAIService)
    # Il testo lungo è interamente indicizzato dal profilo nuovo; lo stato
    # negativo del precedente non ne deve impedire il recupero verificato.
    conn.execute("UPDATE rag_chunks SET embedding_state='invalid'")
    assert len(service._fts_rows(conn, "sentenza", "case", None, 8)) == 1
    conn.execute("UPDATE rag_embedding_generations SET status='invalid'")
    assert service._fts_rows(conn, "sentenza", "case", None, 8) == []
    conn.execute("UPDATE rag_embedding_generations SET status='embedded'")
    conn.execute("UPDATE rag_documents SET sha256='changed-source'")
    assert service._fts_rows(conn, "sentenza", "case", None, 8) == []
    conn.execute("UPDATE rag_documents SET sha256='source-sha'")
    conn.execute("UPDATE rag_chunks SET text=text || ' rettifica'")
    assert service._fts_rows(conn, "sentenza", "case", None, 8) == []


@pytest.mark.parametrize("operation", ["health", "embed_texts"])
def test_reindirizzamento_non_puo_trasmettere_testi_fuori_host(monkeypatch, operation):
    class Redirect:
        status_code = 307

        def raise_for_status(self):
            pass

        def json(self):
            pytest.fail("Un reindirizzamento non è una risposta locale verificata")

    def request(session, *args, **kwargs):
        assert session.trust_env is False and kwargs["allow_redirects"] is False
        return Redirect()

    monkeypatch.setattr("requests.Session.get", request)
    monkeypatch.setattr("requests.Session.post", request)
    client = embeddinggemma2.LocalEmbeddingClient()
    with pytest.raises(ValueError, match="reindirizzare"):
        if operation == "health":
            client.health()
        else:
            client.embed_texts(embeddinggemma2.MODEL, ["Testo privato dello studio"])
