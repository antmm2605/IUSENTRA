from pct.document_intelligence.models import DocumentAIVersion, utc_now
from pct.document_intelligence.versioning import (
    build_document_storage_relative_path,
    build_extracted_text_relative_path,
    next_version_number,
)


def _version(number: int) -> DocumentAIVersion:
    return DocumentAIVersion(
        id=f"ver-{number}",
        tenant_id="tenant-a",
        fascicolo_id="fas-1",
        document_id="doc-1",
        version_number=number,
        source="upload",
        storage_path=f"tenant-a/fascicoli/fas-1/documenti_ai/doc-1/v{number}/atto.pdf",
        extracted_text_path=None,
        pdf_preview_path=None,
        sha256="a" * 64,
        created_by="user-1",
        created_at=utc_now(),
    )


def test_document_ai_next_version_number_lista_vuota():
    assert next_version_number([]) == 1


def test_document_ai_next_version_number_incrementa():
    assert next_version_number([_version(1), _version(3)]) == 4


def test_document_ai_storage_path_relativo_e_tenant_aware():
    path = build_document_storage_relative_path("tenant-a", "fas-1", "doc-1", 2, "atto.pdf")

    assert not path.startswith("/")
    assert ":" not in path
    assert "tenant-a" in path
    assert "fas-1" in path
    assert "doc-1" in path
    assert "/v2/" in path
    assert path.endswith("/atto.pdf")


def test_document_ai_extracted_text_path_relativo_corretto():
    path = build_extracted_text_relative_path("tenant-a", "fas-1", "doc-1", 1)

    assert not path.startswith("/")
    assert path == "tenant-a/fascicoli/fas-1/documenti_ai/doc-1/v1/extracted_text.json"
