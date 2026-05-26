from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.indexer import DocumentAIIndexer
from pct.document_intelligence.models import DocumentAIPageText, DocumentAIRecord
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.service import DocumentAIService
from pct.document_intelligence.sources import source_from_uploaded_document


@dataclass
class FakeUser:
    id: str = "user-1"

    def ha_permesso(self, permission: str) -> bool:
        return permission in {"fascicoli.leggi", "fascicoli.scrivi"}


class FakeFascicoli:
    def get(self, fascicolo_id: str):
        return {"id": fascicolo_id} if fascicolo_id == "fas-1" else None


def _context():
    return {"user": FakeUser(), "user_id": "user-1"}


def _service(tmp_path: Path) -> DocumentAIService:
    repo = DocumentAIRepository(tmp_path / "documenti_ai.json", tmp_path / "storage")
    return DocumentAIService(repo, FakeFascicoli())


def _source(
    content: bytes = b"contenuto",
    *,
    document_id: str = "doc-src-1",
    filename: str = "atto.docx",
    source_type: str = "documenti_fascicolo",
    mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
):
    return source_from_uploaded_document(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        document_id=document_id,
        filename=filename,
        content=content,
        source_type=source_type,
        mime_type=mime_type,
        metadata={"trigger": source_type},
    )


def _patch_extraction(monkeypatch):
    monkeypatch.setattr(
        "pct.document_intelligence.service.extract_text_from_document",
        lambda *_args: ExtractionResult(
            ok=True,
            text="Testo indicizzato del fascicolo",
            pages=[DocumentAIPageText(page_number=1, text="Testo indicizzato del fascicolo")],
            extraction_engine="test-indexer",
        ),
    )


def test_documento_fascicolo_non_indicizzato_risulta_in_coda(tmp_path: Path):
    service = _service(tmp_path)
    summary = DocumentAIIndexer(service).summarize(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[_source()],
        user_context=_context(),
    )

    assert summary.total_documents == 1
    assert summary.queued == 1
    assert summary.status == "working"


def test_aggiorna_indice_processa_documenti_pendenti(tmp_path: Path, monkeypatch):
    _patch_extraction(monkeypatch)
    service = _service(tmp_path)

    result = DocumentAIIndexer(service).process(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[_source()],
        user_context=_context(),
    )

    assert result.indexed == 1
    assert result.summary.ready == 1
    assert result.summary.status == "ready"
    assert service.repository.list_documents("tenant-a", "fas-1")[0].status == "ready"


def test_aggiorna_indice_processa_pdf_p7m_come_pdf(tmp_path: Path, monkeypatch):
    calls = []

    def _fake_extraction(content, filename, file_type):
        calls.append((filename, file_type, bytes(content[:4])))
        return ExtractionResult(
            ok=True,
            text="Testo PDF firmato indicizzato",
            pages=[DocumentAIPageText(page_number=1, text="Testo PDF firmato indicizzato")],
            extraction_engine="test-indexer",
        )

    monkeypatch.setattr("pct.document_intelligence.service.extract_text_from_document", _fake_extraction)
    service = _service(tmp_path)

    result = DocumentAIIndexer(service).process(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[_source(b"%PDF-1.7\ncontenuto", filename="atto.pdf.p7m", mime_type="application/pdf")],
        user_context=_context(),
    )

    assert result.indexed == 1
    assert result.summary.ready == 1
    assert calls == [("atto.pdf.p7m", "pdf", b"%PDF")]
    assert service.repository.list_documents("tenant-a", "fas-1")[0].file_type == "pdf"


def test_aggiorna_indice_processa_txt_ed_eml(tmp_path: Path, monkeypatch):
    calls = []

    def _fake_extraction(content, filename, file_type):
        calls.append((filename, file_type, bytes(content[:12])))
        return ExtractionResult(
            ok=True,
            text=f"Testo indicizzato da {filename}",
            pages=[DocumentAIPageText(page_number=1, text=f"Testo indicizzato da {filename}")],
            extraction_engine="test-indexer",
        )

    monkeypatch.setattr("pct.document_intelligence.service.extract_text_from_document", _fake_extraction)
    service = _service(tmp_path)

    result = DocumentAIIndexer(service).process(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[
            _source(
                b"Nota testuale",
                document_id="doc-txt",
                filename="nota.txt",
                mime_type="text/plain",
            ),
            _source(
                b"Subject: Prova\r\n\r\nCorpo email",
                document_id="doc-eml",
                filename="messaggio.eml",
                mime_type="message/rfc822",
            ),
        ],
        user_context=_context(),
    )

    assert result.indexed == 2
    assert result.summary.ready == 2
    assert [call[:2] for call in calls] == [("nota.txt", "txt"), ("messaggio.eml", "eml")]
    indexed_types = {record.original_filename: record.file_type for record in service.repository.list_documents("tenant-a", "fas-1")}
    assert indexed_types == {"nota.txt": "txt", "messaggio.eml": "eml"}


def test_documento_importato_da_portale_viene_indicizzato(tmp_path: Path, monkeypatch):
    _patch_extraction(monkeypatch)
    service = _service(tmp_path)

    result = DocumentAIIndexer(service).process(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[_source(source_type="portale_telematico")],
        user_context=_context(),
    )

    assert result.indexed == 1
    assert result.summary.ready == 1


def test_hash_invariato_non_reindicizza(tmp_path: Path, monkeypatch):
    _patch_extraction(monkeypatch)
    service = _service(tmp_path)
    source = _source()
    indexer = DocumentAIIndexer(service)
    indexer.process(tenant_id="tenant-a", fascicolo_id="fas-1", sources=[source], user_context=_context())

    result = indexer.process(tenant_id="tenant-a", fascicolo_id="fas-1", sources=[source], user_context=_context())

    assert result.indexed == 0
    assert result.skipped == 1
    assert result.summary.ready == 1


def test_processing_vecchio_viene_recuperato_e_reindicizzato(tmp_path: Path, monkeypatch):
    _patch_extraction(monkeypatch)
    service = _service(tmp_path)
    source = _source(b"contenuto bloccato", filename="atto.pdf", mime_type="application/pdf")
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0).isoformat()
    service.repository.create_document_record(
        DocumentAIRecord(
            id="docai-stale",
            tenant_id="tenant-a",
            fascicolo_id="fas-1",
            original_filename=source.filename,
            safe_filename=source.safe_filename,
            file_type=source.file_type,
            mime_type=source.mime_type,
            size_bytes=source.size_bytes,
            sha256=source.sha256,
            status="processing",
            current_version_id=None,
            page_count=None,
            created_by="worker",
            created_at=old_ts,
            updated_at=old_ts,
        )
    )

    summary = DocumentAIIndexer(service).summarize(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[source],
        user_context=_context(),
    )
    result = DocumentAIIndexer(service).process(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[source],
        user_context=_context(),
    )

    assert summary.stale == 1
    assert result.indexed == 1
    assert result.summary.ready == 1


def test_hash_cambiato_marca_stale(tmp_path: Path, monkeypatch):
    _patch_extraction(monkeypatch)
    service = _service(tmp_path)
    source = _source(b"contenuto originale", filename="atto.docx")
    DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1", sources=[source], user_context=_context())

    changed = _source(b"contenuto aggiornato", filename="atto.docx")
    summary = DocumentAIIndexer(service).summarize(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        sources=[changed],
        user_context=_context(),
    )

    assert summary.stale == 1
    assert summary.status == "stale"
