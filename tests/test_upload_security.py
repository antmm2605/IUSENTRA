from __future__ import annotations

from core.security.upload_validator import validate_upload


ALLOWED_EXT = (".pdf", ".xml", ".png", ".p7m")
ALLOWED_MIME = ("application/pdf", "application/xml", "image/png", "application/pkcs7-mime")


def test_valid_pdf_upload_is_accepted() -> None:
    result = validate_upload(
        "atto.pdf",
        b"%PDF-1.7\nbody",
        allowed_extensions=ALLOWED_EXT,
        allowed_mime_types=ALLOWED_MIME,
        max_size_mb=1,
    )
    assert result.ok
    assert result.mime_type == "application/pdf"


def test_rejects_path_traversal_and_empty_file() -> None:
    traversal = validate_upload(
        "../atto.pdf",
        b"%PDF-1.7",
        allowed_extensions=ALLOWED_EXT,
        allowed_mime_types=ALLOWED_MIME,
        max_size_mb=1,
    )
    empty = validate_upload(
        "atto.pdf",
        b"",
        allowed_extensions=ALLOWED_EXT,
        allowed_mime_types=ALLOWED_MIME,
        max_size_mb=1,
    )
    assert not traversal.ok
    assert not empty.ok


def test_rejects_fake_pdf_and_malicious_xml() -> None:
    fake_pdf = validate_upload(
        "atto.pdf",
        b"not a pdf",
        allowed_extensions=ALLOWED_EXT,
        allowed_mime_types=ALLOWED_MIME,
        max_size_mb=1,
    )
    xxe = validate_upload(
        "dati.xml",
        b"<!DOCTYPE foo [ <!ENTITY xxe SYSTEM 'file:///etc/passwd'> ]><foo />",
        allowed_extensions=ALLOWED_EXT,
        allowed_mime_types=ALLOWED_MIME,
        max_size_mb=1,
    )
    assert not fake_pdf.ok
    assert not xxe.ok


def test_rejects_dangerous_double_extension_and_size() -> None:
    dangerous = validate_upload(
        "atto.exe.pdf",
        b"%PDF-1.7",
        allowed_extensions=ALLOWED_EXT,
        allowed_mime_types=ALLOWED_MIME,
        max_size_mb=1,
    )
    too_big = validate_upload(
        "atto.pdf",
        b"%PDF-1.7" + b"x" * (2 * 1024 * 1024),
        allowed_extensions=ALLOWED_EXT,
        allowed_mime_types=ALLOWED_MIME,
        max_size_mb=1,
    )
    assert not dangerous.ok
    assert not too_big.ok
