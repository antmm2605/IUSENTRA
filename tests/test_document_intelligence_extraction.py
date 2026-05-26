from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from pct.document_intelligence.extraction import extract_document_text, extract_text_from_document


def test_document_ai_extraction_docx_semplice(tmp_path: Path):
    pytest.importorskip("docx")
    from docx import Document

    document = Document()
    document.add_paragraph("Clausola contrattuale principale")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Parte"
    table.rows[0].cells[1].text = "Valore"
    target = tmp_path / "atto.docx"
    document.save(target)

    result = extract_document_text(target, "docx")

    assert result.error is None
    assert result.extraction_engine in {"python-docx", "mammoth"}
    assert "Clausola contrattuale principale" in result.text
    assert "Parte" in result.text


def test_document_ai_extraction_doc_legacy_testuale(tmp_path: Path):
    target = tmp_path / "memoria.doc"
    target.write_bytes(b"\xd0\xcf\x11\xe0\x00\x00Memoria difensiva cliente Rossi contro Bianchi")

    result = extract_document_text(target, "doc")

    assert result.error is None
    assert result.extraction_engine in {"antiword", "libreoffice", "doc.binary-text", "doc.rtf"}
    assert "Memoria difensiva" in result.text


def test_document_ai_extraction_pdf_semplice(tmp_path: Path):
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    target = tmp_path / "atto.pdf"
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Testo PDF fascicolo")
    pdf.showPage()
    pdf.save()
    target.write_bytes(buffer.getvalue())

    result = extract_document_text(target, "pdf")

    assert result.error is None
    assert result.extraction_engine in {"pdfplumber", "pypdf"}
    assert result.page_count == 1
    assert "Testo PDF fascicolo" in result.text


def test_document_ai_extraction_pdf_p7m_leggibile_come_pdf(tmp_path: Path):
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    target = tmp_path / "atto.pdf.p7m"
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Testo PDF firmato leggibile")
    pdf.showPage()
    pdf.save()
    target.write_bytes(buffer.getvalue())

    result = extract_document_text(target, "pdf")

    assert result.error is None
    assert result.extraction_engine in {"p7m:pdfplumber", "p7m:pypdf"}
    assert result.page_count == 1
    assert "Testo PDF firmato leggibile" in result.text
    assert any("estensione .p7m" in warning for warning in result.warnings)


def test_document_ai_extraction_pdf_scansionato_usa_ocr_quando_il_testo_manca(monkeypatch):
    class FakePdfPlumberPage:
        def extract_text(self):
            return ""

    class FakePdfPlumberDocument:
        pages = [FakePdfPlumberPage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeBitmap:
        def to_pil(self):
            return object()

        def close(self):
            return None

    class FakePdfiumPage:
        def render(self, *, scale: float):
            assert scale >= 1.0
            return FakeBitmap()

        def close(self):
            return None

    class FakePdfiumDocument:
        def __init__(self, content: bytes):
            assert content.startswith(b"%PDF")

        def __len__(self):
            return 1

        def __getitem__(self, index: int):
            assert index == 0
            return FakePdfiumPage()

        def close(self):
            return None

    monkeypatch.setitem(
        sys.modules,
        "pdfplumber",
        SimpleNamespace(open=lambda _stream: FakePdfPlumberDocument()),
    )
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=FakePdfiumDocument))
    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        SimpleNamespace(
            image_to_string=lambda _image, lang: "Nota Ufficio Spoglio V Sez. penale R.G. 9966/2026"
        ),
    )

    result = extract_text_from_document(b"%PDF-1.7\n% scansione", "ordinanza.pdf", "pdf")

    assert result.ok is True
    assert result.extraction_engine == "pdfplumber+ocr"
    assert result.pages[0].page_number == 1
    assert "R.G. 9966/2026" in result.text
    assert any("OCR applicato" in warning for warning in result.warnings)


def test_document_ai_extraction_p7m_esterno_usa_payload_firmato(tmp_path: Path, monkeypatch):
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Testo estratto dal payload firmato")
    pdf.showPage()
    pdf.save()
    pdf_payload = buffer.getvalue()

    class _Status:
        payload_available = True
        payload_name = "atto.pdf"
        message = "Contenuto firmato estratto."

    class _Signed:
        status = _Status()
        payload_bytes = pdf_payload

    monkeypatch.setattr(
        "pct.firme_cades.inspect_signed_document_bytes",
        lambda **_kwargs: _Signed(),
    )
    target = tmp_path / "atto.pdf.p7m"
    target.write_bytes(b"PKCS7 signed envelope")

    result = extract_document_text(target, "pdf")

    assert result.error is None
    assert result.extraction_engine in {"p7m:pdfplumber", "p7m:pypdf"}
    assert "Testo estratto dal payload firmato" in result.text
    assert "Contenuto firmato estratto." in result.warnings


def test_document_ai_extraction_formato_non_supportato_controllata(tmp_path: Path):
    target = tmp_path / "programma.exe"
    target.write_bytes(b"contenuto")

    result = extract_document_text(target, "exe")

    assert result.error is not None
    assert result.text == ""
    assert result.extraction_engine == "unsupported"


def test_document_ai_extraction_txt_utf8(tmp_path: Path):
    target = tmp_path / "note-fascicolo.txt"
    target.write_text("Promemoria fascicolo\nCredito € 1.200", encoding="utf-8")

    result = extract_document_text(target, "txt")

    assert result.error is None
    assert result.extraction_engine.startswith("text:")
    assert "Promemoria fascicolo" in result.text
    assert "Credito € 1.200" in result.text


def test_document_ai_extraction_eml_con_corpo_e_allegato_txt(tmp_path: Path):
    message = EmailMessage()
    message["Subject"] = "Diffida inviata"
    message["From"] = "avvocato@example.it"
    message["To"] = "cliente@example.it"
    message["Date"] = "Mon, 18 May 2026 10:00:00 +0200"
    message.set_content("Corpo email con termine per adempiere.")
    message.add_attachment(
        "Testo allegato per Lex".encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename="allegato.txt",
    )
    target = tmp_path / "messaggio.eml"
    target.write_bytes(message.as_bytes())

    result = extract_document_text(target, "eml")

    assert result.error is None
    assert result.extraction_engine == "email.message"
    assert "Oggetto: Diffida inviata" in result.text
    assert "Corpo email con termine per adempiere." in result.text
    assert "[Allegato: allegato.txt]" in result.text
    assert "Testo allegato per Lex" in result.text


def test_document_ai_extraction_doc_legacy_controllata(tmp_path: Path):
    target = tmp_path / "atto.doc"
    target.write_bytes(b"DOC legacy")

    result = extract_document_text(target, "doc")

    assert result.error is not None
    assert result.text == ""
    assert any("DOC" in warning for warning in result.warnings)
