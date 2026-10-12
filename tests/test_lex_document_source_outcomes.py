"""Esiti puntuali delle fonti: nomi PEC, duplicati e registro SQL."""
from pathlib import Path

from pct.document_intelligence.indexer import DocumentAIIndexer
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.service import DocumentAIService
from pct.document_intelligence.sources import source_from_uploaded_document
from tests.test_document_intelligence_auto_indexing import FakeFascicoli, _context


def test_errori_prima_del_record_restano_distinti_oltre_il_limite_degli_avvisi(tmp_path: Path):
    repository = DocumentAIRepository.from_sqlite_db(tmp_path / "documenti.db")
    service = DocumentAIService(repository, FakeFascicoli())
    sources = []
    for index in range(14):
        source = source_from_uploaded_document(
            tenant_id="tenant-a", fascicolo_id="fas-1", document_id=f"fonte-{index}",
            filename="DEPOSITO TELEMATICO: stesso nome.eml", content=f"fonte-{index}".encode(),
            source_type="documenti_fascicolo", mime_type="message/rfc822",
        )
        source.content_bytes = None
        source.content_path = tmp_path / f"originale-assente-{index}.eml"
        sources.append(source)
    try:
        result = DocumentAIIndexer(service).process(
            tenant_id="tenant-a", fascicolo_id="fas-1", sources=sources, user_context=_context(),
        )
        assert result.summary.errors == 14
        assert result.summary.queued == 0
        assert len(result.summary.source_errors) == 14
        assert {item["source_id"] for item in result.summary.source_errors} == {s.source_id for s in sources}
        assert {item["sha256"] for item in result.summary.source_errors} == {s.sha256 for s in sources}
        assert all(item["error_code"] == "source_unavailable" for item in result.summary.source_errors)
        assert repository.list_documents("tenant-a", "fas-1") == []
    finally:
        repository.structured_db.close()


def test_registro_sola_lettura_non_crea_database_e_vede_commit(tmp_path):
    import sqlite3
    import pytest
    from pct.registro_letture import RegistroLetture

    path = tmp_path / "registro.db"
    with pytest.raises(FileNotFoundError):
        RegistroLetture(path, read_only=True)
    assert not path.exists()
    writable = RegistroLetture(path)
    with writable.connection() as conn:
        conn.execute("CREATE TABLE prova_commit (valore INTEGER)")
        conn.execute("INSERT INTO prova_commit VALUES (7)")
    readonly = RegistroLetture(path, read_only=True)
    with readonly.connection() as conn:
        assert conn.execute("SELECT valore FROM prova_commit").fetchone()[0] == 7
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO prova_commit VALUES (8)")
    assert readonly.letture("altro-studio", "fas-1", lettore="indice_documentale") == []


def test_esito_sql_con_nome_pec_e_impronta_cambiata(tmp_path, monkeypatch):
    from flask import Flask
    from pct.registro_letture import RegistroLetture, Oggetto
    from web.services import registro_letture_runtime
    from web.services.document_intelligence_runtime import _registra_indice_documentale
    from web.services.document_index_outcomes import summary_with_registered_outcomes

    repository = DocumentAIRepository.from_sqlite_db(tmp_path / "ai.db")
    service = DocumentAIService(repository, FakeFascicoli())
    registro = RegistroLetture(tmp_path / "registro.db")
    source = source_from_uploaded_document(tenant_id="tenant-a", fascicolo_id="fas-1",
        document_id="pec-a", filename="DEPOSITO: prova.eml", content=b"Subject: prova\n\nTesto",
        source_type="documenti_fascicolo", mime_type="message/rfc822")
    source.content_bytes = None
    source.content_path = tmp_path / "assente.eml"
    try:
        result = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
            sources=[source], user_context=_context())
        obj = Oggetto(tipo="documento", oggetto_id=source.source_id, nome=source.filename, sha256=source.sha256)
        with Flask(__name__).app_context():
            _registra_indice_documentale({"registro": registro, "tenant": "tenant-a", "oggetti": [obj], "impronta": "inventory"},
                result.summary, [source], service=service, tenant_id="tenant-a", fascicolo_id="fas-1", user_context=_context())
        readings = registro.letture("tenant-a", "fas-1", lettore="indice_documentale")
        assert len(readings) == 1 and readings[0].stato == "errore"
        assert readings[0].esito["error_code"] == "source_unavailable"
        monkeypatch.setattr(registro_letture_runtime, "registro_corrente",
            lambda **kwargs: RegistroLetture(tmp_path / "registro.db", read_only=True))
        projected = summary_with_registered_outcomes(service, "tenant-a", "fas-1", [source], _context())
        assert projected.errors == 1 and projected.queued == 0
        assert projected.source_errors[0]["filename"] == "DEPOSITO: prova.eml"
        source.sha256 = "changed-source"
        changed = summary_with_registered_outcomes(service, "tenant-a", "fas-1", [source], _context())
        assert changed.errors == 0 and changed.queued == 1
        assert registro.letture("tenant-b", "fas-1", lettore="indice_documentale") == []
    finally:
        repository.structured_db.close()


def test_stessa_impronta_fallita_non_rilegge_alias(tmp_path, monkeypatch):
    from pct.document_intelligence.sources import DocumentAISource
    repository = DocumentAIRepository.from_sqlite_db(tmp_path / "ai.db")
    service = DocumentAIService(repository, FakeFascicoli())
    sources = [source_from_uploaded_document(tenant_id="tenant-a", fascicolo_id="fas-1",
        document_id=name, filename="DEPOSITO: prova.eml", content=b"identico",
        source_type="documenti_fascicolo", mime_type="message/rfc822") for name in ("uno", "due")]
    calls = []
    def read(source):
        calls.append(source.source_id)
        raise FileNotFoundError("assente")
    monkeypatch.setattr(DocumentAISource, "read_bytes", read)
    try:
        result = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
            sources=sources, user_context=_context())
        assert calls == ["uno"]
        assert result.summary.errors == 2 and result.summary.queued == 0
        assert {item["document_id"] for item in result.summary.source_errors} == {"uno", "due"}
    finally:
        repository.structured_db.close()


def test_limite_riusa_acquisizione_configurata_e_preserva_override(monkeypatch):
    from flask import Flask
    from types import SimpleNamespace
    from web.services import document_intelligence_runtime as runtime
    monkeypatch.setattr(runtime, "fascicoli_db_path", lambda: "controllato")
    monkeypatch.setattr(runtime, "get_request_studio_db", lambda anchor: None)
    monkeypatch.setattr(runtime.DocumentAIRepository, "from_fascicoli_db", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(runtime, "get_fascicoli", lambda: FakeFascicoli())
    app = Flask(__name__)
    app.config["MAX_UPLOAD_MB"] = 50
    with app.app_context():
        assert runtime.build_document_ai_service().max_size_bytes == 50 * 1024 * 1024
        app.config["DOCUMENT_AI_MAX_UPLOAD_BYTES"] = 25 * 1024 * 1024
        assert runtime.build_document_ai_service().max_size_bytes == 25 * 1024 * 1024
        app.config.pop("DOCUMENT_AI_MAX_UPLOAD_BYTES")
        app.config["MAX_UPLOAD_MB"] = 8
        assert runtime.build_document_ai_service().max_size_bytes == 8 * 1024 * 1024
        import pytest
        app.config["MAX_UPLOAD_MB"] = 0
        with pytest.raises(ValueError, match="positivo"):
            runtime.build_document_ai_service()


def test_presidio_non_dichiara_tutti_letti_in_presenza_di_errori(monkeypatch):
    from web.services import document_intelligence_runtime as runtime
    from web.services.fascicolo_lettura_verifiche import verifica_documenti
    calls = []
    def summary(*args, **kwargs):
        calls.append(kwargs["process"])
        return {"total_documents": 14, "ready": 0, "errors": 14, "queued": 0,
                "source_errors": [{"error_code": "source_unavailable", "filename": "DEPOSITO: prova.eml"}]}
    monkeypatch.setattr(runtime, "build_lex_indexing_summary_payload", summary)
    result = verifica_documenti("fas-1", "tenant-a")
    assert calls == [False]
    assert result["errori"] == 14 and result["esito"] == "errori_presenti"
    assert result["da_acquisire"] == 1
    assert result["non_scaricati"] == ["DEPOSITO: prova.eml"]


def test_causa_versione_negativa_viene_riusata_senza_rilettura(tmp_path, monkeypatch):
    from pct.document_intelligence.sources import DocumentAISource
    repository = DocumentAIRepository.from_sqlite_db(tmp_path / "ai.db")
    service = DocumentAIService(repository, FakeFascicoli())
    source = source_from_uploaded_document(tenant_id="tenant-a", fascicolo_id="fas-1",
        document_id="fonte", filename="nota.txt", content=b"Testo originale verificabile.",
        source_type="documenti_fascicolo", mime_type="text/plain")
    try:
        first = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
            sources=[source], user_context=_context())
        assert first.summary.ready == 1
        record = repository.list_documents("tenant-a", "fas-1")[0]
        repository.mark_status("tenant-a", "fas-1", record.id, "error")
        repository.append_audit_event({"id": "errore-controllato", "tenant_id": "tenant-a", "fascicolo_id": "fas-1",
            "document_id": record.id, "version_id": record.current_version_id, "user_id": "test", "event_type": "document_ai.extraction.failed",
            "error_code": "email_reading_incomplete", "error_message": "Allegato cifrato: originale in chiaro necessario.",
            "timestamp": "2099-01-01T00:00:00Z"})
        monkeypatch.setattr(DocumentAISource, "read_bytes", lambda source: (_ for _ in ()).throw(AssertionError("Rilettura non autorizzata")))
        second = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
            sources=[source], user_context=_context())
        assert second.indexed == 0 and second.skipped == 1 and second.summary.errors == 1
        assert second.summary.source_errors[0]["error_code"] == "email_reading_incomplete"
        assert second.summary.source_errors[0]["message"] == "Allegato cifrato: originale in chiaro necessario."
        assert len(repository.list_versions("tenant-a", "fas-1", record.id)) == 1
        assert repository.latest_processing_error("tenant-b", "fas-1", record.id, record.current_version_id)["error_code"] == "source_processing_failed"
    finally:
        repository.structured_db.close()


def test_api_conserva_tutti_gli_esiti_puntuali_senza_campi_interni():
    from web.blueprints.api_v1_documenti_ai import _serialize_lex_indexing
    sources = [{"source_id": f"fonte-{i}", "document_id": f"doc-{i}", "sha256": f"hash-{i}",
                "filename": "DEPOSITO: prova.eml", "error_code": "source_unavailable",
                "message": "Fonte non disponibile.", "tenant_id": "interno", "percorso_interno": "/riservato"} for i in range(14)]
    payload = _serialize_lex_indexing({"errors": 14, "source_errors": sources})
    assert payload["errors"] == 14 and len(payload["source_errors"]) == 14
    assert {item["source_id"] for item in payload["source_errors"]} == {f"fonte-{i}" for i in range(14)}
    assert all("tenant_id" not in item and "percorso_interno" not in item for item in payload["source_errors"])


def test_fascicolo_react_usa_la_proiezione_condivisa_senza_avviare_letture(monkeypatch):
    from web.services import document_intelligence_runtime as runtime
    from web.services.react_fascicoli_bridge import _lex_indexing_summary
    calls = []
    payload = {"total_documents": 14, "errors": 14, "queued": 0,
               "source_errors": [{"document_id": str(i), "message": "Fonte assente."} for i in range(14)]}
    def projected(fid, **kwargs):
        calls.append((fid, kwargs))
        return payload
    monkeypatch.setattr(runtime, "build_lex_indexing_summary_payload", projected)
    assert _lex_indexing_summary("fascicolo-controllato") == payload
    assert calls == [("fascicolo-controllato", {"process": False, "apply_automations": False})]


def test_esito_pronto_corrente_prevale_sulla_causa_negativa_storica(tmp_path):
    from pct.document_intelligence.indexer import build_lex_indexing_summary
    from pct.document_intelligence.index_outcomes import source_identity
    repository = DocumentAIRepository.from_sqlite_db(tmp_path / "ai.db")
    source = source_from_uploaded_document(tenant_id="tenant-a", fascicolo_id="fas-1", document_id="fonte",
        filename="nota.txt", content=b"Documento corrente leggibile e verificabile.")
    try:
        service = DocumentAIService(repository, FakeFascicoli())
        DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1", sources=[source], user_context=_context())
        failure = {**source_identity(source), "document_id": source.source_id, "filename": source.filename,
                   "error_code": "source_processing_failed", "message": "Errore precedente."}
        summary = build_lex_indexing_summary(sources=[source], records=repository.list_documents("tenant-a", "fas-1"), source_errors=[failure])
        assert summary.ready == 1 and summary.errors == 0
        assert summary.source_errors == []
    finally:
        repository.structured_db.close()
