"""Strato di selezione del lettore: coordinate del PDF, nessuna interpretazione."""
from __future__ import annotations

from html import escape


def text_layers(data: bytes) -> list[str]:
    """Lo strato di testo selezionabile, pagina per pagina.

    E' un di piu' del lettore, non il lettore: se il PDF non si apre — un
    allegato PEC malformato, una busta con un flusso troncato — le pagine
    devono comunque comparire. Per questo un guasto qui non si propaga: si
    torna senza strato di testo e il lettore mostra le immagini.
    """
    import pymupdf as fitz

    layers: list[str] = []
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return []
    with document:
        for page in document:
            try:
                width, height = page.rect.width, page.rect.height
                from pct.document_intelligence.pdf_quality import has_only_signature_text
                words = [] if has_only_signature_text(page.get_text()) else page.get_text("words", sort=True)
            except Exception:
                # Una pagina illeggibile non toglie la selezione alle altre.
                layers.append('<span class="reader-no-text">Pagina senza strato di testo: la selezione richiede una lettura OCR disponibile.</span>')
                continue
            spans = []
            for word in words:
                box = fitz.Rect(word[:4]) * page.rotation_matrix
                if not word[4].strip() or width <= 0 or height <= 0:
                    continue
                style = (
                    f"left:{100 * box.x0 / width:.5f}%;top:{100 * box.y0 / height:.5f}%;"
                    f"width:{100 * box.width / width:.5f}%;height:{100 * box.height / height:.5f}%;"
                )
                spans.append(f'<span class="reader-word" style="{style}"><span>{escape(word[4])} </span></span>')
            if spans:
                layers.append('<div class="reader-text-layer">' + ''.join(spans) + '</div>')
            else:
                layers.append('<span class="reader-no-text">Pagina senza strato di testo: la selezione richiede una lettura OCR disponibile.</span>')
    return layers


def page_text_response(data: bytes, page_number: int):
    """Coordinate OCR della sola pagina richiesta, negli stessi permessi del lettore."""
    import hashlib
    import io
    import fitz
    import pytesseract
    from PIL import Image
    from flask import jsonify
    from web.services.registro_letture_runtime import tenant_corrente
    key = (tenant_corrente(), hashlib.sha256(data).hexdigest(), page_number)
    with _CACHE_LOCK:
        cached = _PAGE_CACHE.get(key)
        if cached is not None:
            _PAGE_CACHE.move_to_end(key)
            response = jsonify(cached)
            response.headers["Cache-Control"] = "private, no-store"
            return response
    with fitz.open(stream=data, filetype="pdf") as document:
        if page_number < 1 or page_number > len(document):
            return jsonify({"error": "Pagina non disponibile"}), 404
        page = document[page_number - 1]
        scale = min(3.0, (12000000 / max(1, page.rect.width * page.rect.height)) ** 0.5)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        from legal_ocr.motore.immagine import prepara_pagina
        from legal_ocr.motore.lettura import leggi_immagine
        with Image.open(io.BytesIO(pix.tobytes("png"))) as image:
            # Contrasto senza ritagli/rotazioni: le coordinate restano quelle
            # della pagina mostrata. Stesso motore governato dell'archivio OCR.
            prepared = prepara_pagina(image, raddrizza=False, ritaglia=False)
            reading = leggi_immagine(prepared.immagine, pytesseract=pytesseract, lingua="ita", dpi=prepared.dpi, con_pdf=False, timeout=30)
        words = []
        for word in reading.parole:
            if not str(word["text"]).strip() or word.get("conf", 0) < 0.35:
                continue
            words.append({"text": str(word["text"]), "x": 100 * word["left"] / prepared.immagine.width, "y": 100 * word["top"] / prepared.immagine.height, "w": 100 * word["width"] / prepared.immagine.width, "h": 100 * word["height"] / prepared.immagine.height})
    payload = {"words": words, "mode": "ocr", "message": "Testo OCR selezionabile: confronta i dati copiati con la pagina." if words else "OCR eseguito: nessun testo riconoscibile in questa pagina."}
    with _CACHE_LOCK:
        _PAGE_CACHE[key] = payload
        while len(_PAGE_CACHE) > 64:
            _PAGE_CACHE.popitem(last=False)
    response = jsonify(payload)
    response.headers["Cache-Control"] = "private, no-store"
    return response


from collections import OrderedDict
from threading import Lock
_PAGE_CACHE: OrderedDict = OrderedDict()
_CACHE_LOCK = Lock()
