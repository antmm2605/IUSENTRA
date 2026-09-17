"""Lettore autenticato degli snapshot ufficiali del registro procedurale."""
from __future__ import annotations
import hashlib
import io
import json
from html import escape
from pathlib import Path
from flask import abort, current_app, make_response, request, send_file

def visualizza_fonte(source_id: str):
    base = Path(current_app.root_path).parent / "docs/specs/ministero/fonti-20260916"
    manifest = json.loads((base / "acquisizioni.json").read_text())
    entry = manifest.get(source_id)
    if not entry or not entry.get("file"):
        abort(404)
    path = (base / entry["file"]).resolve()
    if path.parent != base.resolve():
        abort(404)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        abort(503, description="La copia della fonte non coincide con l’impronta verificata.")
    from pct.procedura_fasi.fonti import fonte
    name = fonte(source_id).get("norma", source_id)
    if request.args.get("download") == "1":
        return send_file(io.BytesIO(data), download_name=path.name, as_attachment=True)
    if path.suffix == ".txt":
        paragraphs = "".join("<p>" + escape(p) + "</p>" for p in data.decode("utf-8").split("\n\n"))
        html = f"<!doctype html><html lang='it'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>{escape(name)}</title><style>body{{font:17px/1.65 system-ui,sans-serif;margin:0;padding:24px;color:#13243a;background:white}}main{{max-width:900px;margin:auto}}p{{white-space:pre-line}}a{{color:#0756d6}}</style><main><h1>{escape(name)}</h1><p>Testo acquisito da Normattiva il 16/09/2026, note all’art. 3 D.Lgs. 164/2024.</p>{paragraphs}<p><a href='{escape(entry['url'],quote=True)}' target='_blank' rel='noopener noreferrer'>Provenienza ufficiale</a></p></main></html>"
        response = make_response(html)
    else:
        from web.bootstrap.fascicoli_document_helpers import pdf_mobile_preview_html, pdf_page_count, render_pdf_page_png
        page = request.args.get("page")
        if page:
            try:
                if request.args.get("reader_text") == "1":
                    from web.services.pdf_reader_text import page_text_response
                    return page_text_response(data, int(page))
                rendered = render_pdf_page_png(data, int(page))
            except (ValueError, TypeError):
                abort(404)
            return send_file(io.BytesIO(rendered), mimetype="image/png")
        count = pdf_page_count(data)
        response = make_response(pdf_mobile_preview_html(nome_documento=name, page_urls=[f"{request.path}?page={i}" for i in range(1,count+1)], scarica_url=request.path+"?download=1", pdf_payload=data))
    response.headers["Cache-Control"] = "private, max-age=300"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
