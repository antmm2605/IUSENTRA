from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfReader

from pct.document_intelligence.extraction import _identity_image_pdf, extract_text_from_document, ExtractionResult


@pytest.mark.parametrize("format_name", ["PNG", "JPEG"])
@pytest.mark.parametrize("size", [(120, 90), (1423, 951)])
def test_identity_adapter_preserves_decoded_pixels(format_name, size):
    image = Image.new("RGB", size, (123, 34, 56))
    image.putpixel((9, 20), (2, 255, 200))
    source = BytesIO()
    image.save(source, format=format_name)
    with Image.open(BytesIO(source.getvalue())) as decoded:
        expected = decoded.convert("RGB").tobytes()
    page = PdfReader(BytesIO(_identity_image_pdf(source.getvalue()))).pages[0]
    pixels = page["/Resources"]["/XObject"]["/IdentitySource"]
    assert pixels.get_data() == expected
    assert tuple(map(float, page.mediabox[2:])) == tuple(round(v / 3, 5) for v in size)
    from legal_ocr.motore.fonte_identita import immagine_nativa_copertina
    native, audit = immagine_nativa_copertina(_identity_image_pdf(source.getvalue()), 0)
    assert native is not None, audit
    try:
        assert native.tobytes() == expected
    finally:
        native.close()


def test_identity_image_uses_same_pipeline_and_metadata(monkeypatch):
    from pct.document_intelligence import pdf_inspector_engine
    image = BytesIO()
    Image.new("RGB", (30, 60), "white").save(image, format="PNG")
    expected = ExtractionResult(True, "lettura", [], "shared", identity_sources=[{"page": 1}])
    def shared(content, *, identity_scan):
        assert identity_scan is True
        assert len(PdfReader(BytesIO(content)).pages) == 1
        return expected
    monkeypatch.setattr(pdf_inspector_engine, "extract_pdf_inspected", shared)
    assert extract_text_from_document(image.getvalue(), "upload.png", "png", identity_scan=True) is expected
    assert extract_text_from_document(image.getvalue(), "Carta identità.png", "png") is expected


def test_general_image_keeps_existing_extraction(monkeypatch):
    from pct.document_intelligence import extraction
    expected = ExtractionResult(True, "testo generale", [], "existing.image")
    monkeypatch.setattr(extraction, "_extract_with_unlimited_ocr_for_index", lambda *args: expected)
    monkeypatch.setattr(extraction, "_extract_identity_image", lambda *args: pytest.fail("Identità non richiesta"))
    assert extract_text_from_document(b"source", "fotografia.png", "png") is expected


def test_identity_adapter_does_not_drop_additional_frames():
    source = BytesIO()
    Image.new("RGB", (30, 60), "white").save(source, format="TIFF", save_all=True,
        append_images=[Image.new("RGB", (30, 60), "black")])
    result = extract_text_from_document(source.getvalue(), "documento.tiff", "tiff", identity_scan=True)
    assert not result.ok
    assert result.error_code == "identity_image_invalid"


def test_identity_adapter_corrects_exif_without_losing_pixels():
    source = BytesIO()
    image = Image.new("RGB", (30, 60), "white")
    exif = Image.Exif()
    exif[274] = 6
    image.save(source, format="PNG", exif=exif)
    page = PdfReader(BytesIO(_identity_image_pdf(source.getvalue()))).pages[0]
    assert tuple(map(float, page.mediabox[2:])) == (20, 10)


@pytest.mark.parametrize("extra", [b"", b"extra"])
def test_native_flate_rejects_excess_pixels_and_trailing_stream(extra):
    import zlib
    from pypdf import PdfWriter
    from legal_ocr.motore.fonte_identita import immagine_nativa_copertina
    source = BytesIO()
    Image.new("RGB", (30, 60), "white").save(source, format="PNG")
    writer = PdfWriter(clone_from=BytesIO(_identity_image_pdf(source.getvalue())))
    image = writer.pages[0]["/Resources"]["/XObject"]["/IdentitySource"].get_object()
    image._data = zlib.compress(b"x" * (30 * 60 * 3 + (1 if not extra else 0))) + extra
    output = BytesIO()
    writer.write(output)
    native, audit = immagine_nativa_copertina(output.getvalue(), 0)
    assert native is None
    assert "discordanti" in " ".join(audit)
