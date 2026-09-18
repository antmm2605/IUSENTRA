"""Le pagine del modulo come immagini, per mostrarle al cliente sul telefono."""

from __future__ import annotations

import base64

try:  # PyMuPDF e' dichiarato in requirements.txt
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Anteprime per il portale clienti
# ---------------------------------------------------------------------------

def anteprima_pagine(percorso: str, *, dpi: int = 130) -> list[dict]:
    """PNG in base64 di ogni pagina, con le dimensioni in punti."""
    doc = fitz.open(percorso)
    try:
        fuori = []
        zoom = dpi / 72.0
        for numero, pagina in enumerate(doc):
            pix = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            fuori.append({
                "pagina": numero,
                "larghezza": pagina.rect.width,
                "altezza": pagina.rect.height,
                "png": "data:image/png;base64,"
                       + base64.b64encode(pix.tobytes("png")).decode(),
            })
        return fuori
    finally:
        doc.close()
