from dataclasses import dataclass
from pathlib import Path

from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.indexer import DocumentAIIndexer
from pct.document_intelligence.models import DocumentAIPageText
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


def _source(content: bytes = b"contenuto", *, filename: str = "atto.docx", source_type: str = "documenti_fascicolo"):
    return source_from_uploaded_document(
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        document_id="doc-src-1",
        filename=filename,
        content=content,
        source_type=source_type,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
