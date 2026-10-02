"""Lettura anonima e statica di collegamenti pubblici nel lettore dello studio."""
from html import escape
from functools import lru_cache
from time import time
from urllib.parse import urljoin, urlsplit, urlencode, unquote

from flask import current_app, make_response, request

from pct.mediazione_public_sources import fetch_public, public_url


@lru_cache(maxsize=4)
def _public_snapshot(target, interval):
    # Solo contenuti pubblici: niente cookie, credenziali o dati dello studio.
    return fetch_public(target, max_bytes=8_000_000)


def web_preview():
    from bs4 import BeautifulSoup
    from web.services.signed_attachment_preview import _preview_shell
    from web.services.signed_attachment_preview_word import _safe_doc_html

    target = str(request.args.get("url") or "")
    status = 200
    try:
        target = public_url(target)
        page = _public_snapshot(target, int(time()) // 300)
        target = page["url"]
        if page["status"] != 200:
            raise ValueError("La fonte ha risposto senza fornire il contenuto richiesto.")
        content_type = page["content_type"].lower()
        if page["body"].startswith(b"%PDF") or "application/pdf" in content_type:
            from web.bootstrap.fascicoli_document_helpers import pdf_mobile_preview_html, pdf_page_count, render_pdf_page_png
            from flask import send_file
            from io import BytesIO
            payload = page["body"]
            name = unquote(urlsplit(target).path.rsplit("/", 1)[-1]) or "Documento web.pdf"
            if request.args.get("download") == "1":
                return send_file(BytesIO(payload), mimetype="application/pdf", as_attachment=True, download_name=name)
            if request.args.get("page"):
                if request.args.get("reader_text") == "1":
                    from web.services.pdf_reader_text import page_text_response
                    return page_text_response(payload, int(request.args["page"]))
                return send_file(BytesIO(render_pdf_page_png(payload, int(request.args["page"]))), mimetype="image/png")
            count = pdf_page_count(payload)
            urls = [request.path + "?" + urlencode({"url": target, "page": number}) for number in range(1, count + 1)]
            return pdf_mobile_preview_html(nome_documento=name, page_urls=urls, scarica_url=request.path + "?" + urlencode({"url": target, "download": 1}), pdf_payload=payload)
        if "html" in content_type:
            soup = BeautifulSoup(page["body"], "html.parser")
            title = soup.title.get_text(" ", strip=True)[:200] if soup.title else urlsplit(target).hostname
            for node in soup.find_all(["script", "style", "form", "iframe", "object", "embed", "noscript"]):
                node.decompose()
            # Le immagini remote non devono aprire richieste di tracciamento né
            # produrre segnaposto rotti nella lettura statica della fonte.
            for image in soup.find_all("img"):
                alternative = str(image.get("alt") or "").strip()
                image.replace_with(alternative) if alternative else image.decompose()
            for navigation in soup.find_all("nav"):
                navigation.decompose()
            for item in soup.find_all("li"):
                if not item.get_text(strip=True):
                    item.decompose()
            for link in soup.find_all("a", href=True):
                link["href"] = urljoin(target, link["href"])
            readable = soup.find("main") or soup.body or soup
            body = _safe_doc_html(str(readable))
        elif "text/plain" in content_type:
            title = urlsplit(target).hostname
            body = "<pre>" + escape(page["body"].decode("utf-8", errors="replace")) + "</pre>"
        else:
            raise ValueError("Questo contenuto web richiede un formato di lettura ancora da integrare.")
        body = '<p class="muted">Lettura del contenuto pubblico della fonte, senza accesso agli account del sito.</p>' + body
    except Exception as exc:
        current_app.logger.warning("Lettore collegamento web: %s", type(exc).__name__)
        status = 422
        title = "Collegamento non leggibile"
        reason = str(exc) if isinstance(exc, ValueError) else "La fonte non ha risposto entro il tempo previsto."
        body = "<p role=\"alert\">" + escape(reason) + "</p><p>Il documento di partenza resta aperto. Puoi riprovare il caricamento della fonte.</p>"
    response = make_response(_preview_shell(title=str(title), subtitle=target[:2048], body=body), status)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
    return response
