"""OCR di pagina e PDF A4 dell'acquisizione: guardrail tecnici, non prove hardware."""

from __future__ import annotations

import base64
import io
import shutil
import subprocess

import fitz
import pytest
from flask import Flask, g
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from web.blueprints import api_v1_document_tools as blueprint_module
from web.blueprints.api_v1_document_tools import api_v1_document_tools
from web.services import document_ocr
from web.services.document_ocr import OcrPageResult, page_dpi, paragraphs_from_pdf
from web.services.document_tools import DocumentToolError, UploadedDocument, images_to_pdf


def _app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _authenticate():
        g.utente_corrente = object()

    app.register_blueprint(api_v1_document_tools, url_prefix="/api/v1/ui/document-tools")
    return app


def _jpeg(width: int = 827, height: int = 1169, lines: tuple[str, ...] = ()) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    for index, line in enumerate(lines):
        draw.text((80, 120 + (index * 48)), line, fill="black", font=font)
    output = io.BytesIO()
    image.save(output, "JPEG", quality=92)
    return output.getvalue()


def _text_pdf(blocks: list[tuple[float, float, str]]) -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    for x, y, text in blocks:
        page.insert_text((x, y), text, fontsize=12)
    data = document.tobytes()
    document.close()
    return data


def test_page_dpi_fa_rientrare_la_pagina_in_a4():
    assert page_dpi(1654, 2339) == 200
    assert page_dpi(2339, 1654) == 200
    assert page_dpi(2480, 3508) == 300
    assert page_dpi(100, 100) == 72
    assert page_dpi(20000, 28000) == 600


def test_paragrafi_uniscono_righe_vicine_e_ricompongono_la_sillabazione():
    pdf = _text_pdf([
        (72, 100, "TRIBUNALE DI BARI"),
        (72, 160, "Il sottoscritto chiede la fissa-"),
        (72, 174, "zione dell'udienza."),
        (72, 240, "Procura alle liti."),
    ])
    assert paragraphs_from_pdf(pdf) == [
        "TRIBUNALE DI BARI",
        "Il sottoscritto chiede la fissazione dell'udienza.",
        "Procura alle liti.",
    ]


@pytest.mark.parametrize(
    ("data", "message"),
    [(b"", "vuota"), (b"%PDF-1.7 non immagine", "leggibile")],
)
def test_pagina_non_valida_viene_respinta_con_messaggio_italiano(monkeypatch, data, message):
    monkeypatch.setattr(document_ocr, "_tesseract", lambda: object())
    with pytest.raises(DocumentToolError, match=message):
        document_ocr.recognize_page(data)


def test_dizionario_italiano_mancante_blocca_senza_ripiegare_su_altre_lingue(monkeypatch):
    class FakeTesseract:
        @staticmethod
        def get_languages(config=""):
            return ["eng", "osd"]

    monkeypatch.setattr(document_ocr, "_LANGUAGE_READY", False)
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", FakeTesseract)
    with pytest.raises(DocumentToolError, match="dizionario italiano"):
        document_ocr.recognize_page(_jpeg())


def test_rotazione_oraria_e_dpi_passati_al_motore(monkeypatch):
    seen = {}

    class FakeTesseract:
        @staticmethod
        def image_to_pdf_or_hocr(image, lang, extension, config, timeout):
            seen.update(size=image.size, lang=lang, extension=extension, config=config, timeout=timeout)
            return _text_pdf([(72, 100, "Pagina riconosciuta")])

    monkeypatch.setattr(document_ocr, "_tesseract", lambda: FakeTesseract)
    result = document_ocr.recognize_page(_jpeg(827, 1169), rotation=90)
    assert seen["size"] == (1169, 827)
    assert seen["lang"] == "ita" and seen["extension"] == "pdf"
    assert seen["config"] == f"--dpi {page_dpi(1169, 827)}"
    assert result.paragraphs == ["Pagina riconosciuta"]
    assert result.characters == len("Paginariconosciuta")


def test_api_ocr_pagina_restituisce_pdf_e_paragrafi_senza_salvare(monkeypatch):
    pdf = _text_pdf([(72, 100, "Atto acquisito")])
    calls = []

    def fake_recognize(data, rotation):
        calls.append((len(data), rotation))
        return OcrPageResult(pdf=pdf, paragraphs=["Atto acquisito"], dpi=200)

    monkeypatch.setattr(blueprint_module, "recognize_page", fake_recognize)
    response = _app().test_client().post(
        "/api/v1/ui/document-tools/ocr-page",
        data={"file": (io.BytesIO(_jpeg()), "pagina.jpg"), "rotation": "450"},
        content_type="multipart/form-data",
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert payload["ok"] is True and payload["paragraphs"] == ["Atto acquisito"]
    assert base64.b64decode(payload["pdf_base64"]).startswith(b"%PDF-")
    assert calls == [(len(_jpeg()), 90)]


def test_api_ocr_pagina_senza_file_risponde_errore_leggibile():
    response = _app().test_client().post("/api/v1/ui/document-tools/ocr-page", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "message": "Nessuna pagina ricevuta."}


def test_pdf_multipagina_a4_mantiene_immagine_intera_e_orientamento():
    data, pages = images_to_pdf(
        [UploadedDocument("verticale.jpg", _jpeg(827, 1169)), UploadedDocument("orizzontale.jpg", _jpeg(1169, 827))],
        [0, 90],
        page_format="a4",
    )
    reader = PdfReader(io.BytesIO(data))
    assert pages == 2
    first, second = reader.pages
    assert (round(float(first.mediabox.width)), round(float(first.mediabox.height))) == (595, 842)
    assert (round(float(second.mediabox.width)), round(float(second.mediabox.height))) == (842, 595)
    assert second.rotation == 90


def test_formato_pagina_sconosciuto_respinto():
    with pytest.raises(DocumentToolError, match="Formato di pagina"):
        images_to_pdf([UploadedDocument("pagina.jpg", _jpeg())], page_format="lettera")


def _italian_tesseract_available() -> bool:
    if not shutil.which("tesseract"):
        return False
    try:
        output = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=20, check=False)
    except Exception:
        return False
    return "ita" in output.stdout.split()


@pytest.mark.skipif(not _italian_tesseract_available(), reason="Tesseract con dizionario italiano non installato")
def test_ocr_reale_in_italiano_produce_pdf_a4_ricercabile(monkeypatch):
    monkeypatch.setattr(document_ocr, "_LANGUAGE_READY", False)
    result = document_ocr.recognize_page(_jpeg(1654, 2339, ("TRIBUNALE ORDINARIO DI BARI", "Procura alle liti conferita all'avvocato.")))
    text = " ".join(result.paragraphs)
    assert "TRIBUNALE" in text and "Procura" in text
    with fitz.open(stream=result.pdf, filetype="pdf") as document:
        assert round(document[0].rect.width) == 595
        assert "BARI" in document[0].get_text()
