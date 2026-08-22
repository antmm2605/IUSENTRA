from __future__ import annotations

import io
import zipfile
from pathlib import Path

import fitz
from flask import Flask, g
from pypdf import PdfReader, PdfWriter

from web.blueprints.api_v1_document_tools import api_v1_document_tools
from web.services.document_tools import (
    DocumentToolError,
    UploadedDocument,
    create_zip,
    images_to_pdf,
    merge_pdfs,
    safe_output_name,
)


def _pdf_bytes(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _png_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=320, height=240)
    page.draw_rect(fitz.Rect(20, 20, 300, 220), color=(0.1, 0.3, 0.8), fill=(0.9, 0.95, 1))
    output = page.get_pixmap(alpha=False).tobytes("png")
    document.close()
    return output


def _app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _authenticate():
        g.utente_corrente = object()

    app.register_blueprint(api_v1_document_tools, url_prefix="/api/v1/ui/document-tools")
    return app


def test_safe_output_name_rimuove_path_e_caratteri_non_ammessi():
    assert safe_output_name("../Pratica: Rossi?.PDF", "pdf", "documento") == "Pratica Rossi.pdf"
    assert safe_output_name("", "zip", "documenti") == "documenti.zip"


def test_merge_pdfs_rispetta_ordine_e_numero_pagine():
    merged, pages = merge_pdfs(
        [
            UploadedDocument("primo.pdf", _pdf_bytes(1)),
            UploadedDocument("secondo.pdf", _pdf_bytes(2)),
        ]
    )
    assert pages == 3
    assert len(PdfReader(io.BytesIO(merged)).pages) == 3


def test_merge_pdfs_rifiuta_file_non_pdf():
    try:
        merge_pdfs(
            [
                UploadedDocument("primo.pdf", _pdf_bytes()),
                UploadedDocument("testo.txt", b"testo"),
            ]
        )
    except DocumentToolError as exc:
        assert "non è un PDF" in str(exc)
    else:
        raise AssertionError("Il file non PDF doveva essere rifiutato.")


def test_create_zip_conserva_ordine_e_nomi_logici():
    result = create_zip(
        [UploadedDocument("a.pdf", b"A"), UploadedDocument("b.txt", b"B")],
        ["Atto principale", "Nota"],
    )
    with zipfile.ZipFile(io.BytesIO(result)) as archive:
        assert archive.namelist() == ["Atto principale.pdf", "Nota.txt"]
        assert archive.read("Atto principale.pdf") == b"A"


def test_create_zip_rifiuta_nomi_duplicati():
    try:
        create_zip(
            [UploadedDocument("a.pdf", b"A"), UploadedDocument("b.pdf", b"B")],
            ["Allegato.pdf", "allegato.pdf"],
        )
    except DocumentToolError as exc:
        assert "presente più volte" in str(exc)
    else:
        raise AssertionError("Il nome duplicato doveva essere rifiutato.")


def test_images_to_pdf_crea_documento_multipagina_e_applica_rotazione():
    result, pages = images_to_pdf(
        [UploadedDocument("pagina.png", _png_bytes()), UploadedDocument("allegato.pdf", _pdf_bytes())],
        [90, 180],
    )
    reader = PdfReader(io.BytesIO(result))
    assert pages == 2
    assert len(reader.pages) == 2
    assert reader.pages[0].rotation == 90

    assert reader.pages[1].rotation == 180

def test_superficie_react_collega_scanner_locale_e_route_documentali():
    root = Path(__file__).resolve().parents[1]
    component = (root / "frontend" / "src" / "components" / "DocumentToolsPage.tsx").read_text(encoding="utf-8")
    app_source = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    shell_source = (root / "web" / "blueprints" / "react_shell.py").read_text(encoding="utf-8")

    assert "acquireFromLocalScanner" in component
    assert "http://127.0.0.1:27272/scanner/acquire" in component
    assert "Acquisisci una pagina dallo scanner" in component
    assert "DocumentToolsPage" in app_source
    assert '"/strumenti-documentali"' in shell_source or "'/strumenti-documentali'" in shell_source



def test_api_merge_restituisce_pdf_scaricabile_e_metadati():
    client = _app().test_client()
    response = client.post(
        "/api/v1/ui/document-tools/merge",
        data={
            "output_name": "atto completo",
            "files": [
                (io.BytesIO(_pdf_bytes()), "atto.pdf"),
                (io.BytesIO(_pdf_bytes(2)), "allegato.pdf"),
            ],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["X-Iusentra-Pages"] == "3"
    assert "atto completo.pdf" in response.headers["Content-Disposition"]


def test_api_zip_segnala_errore_leggibile_senza_file():
    client = _app().test_client()
    response = client.post("/api/v1/ui/document-tools/zip", data={"output_name": "archivio"})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Seleziona almeno un documento."

