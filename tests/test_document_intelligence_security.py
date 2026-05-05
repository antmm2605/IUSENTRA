from pathlib import Path

import pytest

from pct.document_intelligence.security import (
    DocumentAIValidationError,
    assert_allowed_document_ai_extension,
    compute_sha256,
    safe_join_under_root,
    sanitize_filename,
    validate_document_file_type,
)


def test_document_ai_rifiuta_estensione_non_ammessa():
    with pytest.raises(DocumentAIValidationError):
        validate_document_file_type("script.exe", "application/octet-stream")


@pytest.mark.parametrize("filename", ["atto.pdf", "memoria.docx", "bozza.doc"])
def test_document_ai_accetta_formati_mvp(filename):
    assert validate_document_file_type(filename, None) in {"pdf", "docx", "doc"}


def test_document_ai_sanitize_filename_blocca_path_traversal():
    with pytest.raises(DocumentAIValidationError):
        sanitize_filename("../atto.pdf")
    with pytest.raises(DocumentAIValidationError):
        sanitize_filename("cartella\\atto.pdf")


def test_document_ai_safe_join_impedisce_uscita_root(tmp_path: Path):
    root = tmp_path / "data"
    inside = safe_join_under_root(root, "tenant", "file.pdf")
    assert inside == (root / "tenant" / "file.pdf").resolve()
    with pytest.raises(DocumentAIValidationError):
        safe_join_under_root(root, "..", "file.pdf")


def test_document_ai_sha256_stabile():
    assert compute_sha256(b"contenuto") == compute_sha256(b"contenuto")
    assert compute_sha256(b"contenuto") != compute_sha256(b"altro")


def test_document_ai_filename_vuoto_rifiutato():
    with pytest.raises(DocumentAIValidationError):
        sanitize_filename("")


def test_document_ai_assert_extension_normalizza():
    assert_allowed_document_ai_extension(".PDF")
