"""Lettore fatture basato sul renderer documentale unico dello studio."""
from __future__ import annotations
import io
from typing import Any
from flask import request, send_file, url_for, make_response


def fatturazione_pdf_preview_response(pdf_bytes: bytes, filename: str) -> Any | None:
    if request.args.get("viewer") != "mobile":
        return None
    from web.bootstrap.fascicoli_document_helpers import pdf_mobile_preview_html, pdf_page_count, render_pdf_page_png
    download_url = url_for(request.endpoint, **(request.view_args or {}), download=1)
    try:
        raw_page = str(request.args.get("page") or "").strip()
        if raw_page:
            page = int(raw_page)
            if page < 1:
                raise ValueError("Pagina non valida")
            response = send_file(io.BytesIO(render_pdf_page_png(pdf_bytes, page)), mimetype="image/png")
        else:
            pages = pdf_page_count(pdf_bytes)
            page_urls = [url_for(request.endpoint, **(request.view_args or {}), viewer="mobile", page=index, v=request.args.get("v", "")) for index in range(1, pages + 1)]
            response = make_response(pdf_mobile_preview_html(nome_documento=filename, page_urls=page_urls, scarica_url=download_url, pdf_payload=pdf_bytes))
    except (ValueError, RuntimeError):
        response = make_response("<!doctype html><html lang='it'><meta charset='utf-8'><title>Anteprima documento</title><p>Anteprima non disponibile. Controlla i dati della fattura e riprova.</p></html>", 422)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response
