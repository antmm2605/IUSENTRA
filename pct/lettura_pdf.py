"""Il testo di un PDF, senza PyMuPDF.

I nomi cominciano con `leggi_` e non con `testo_`: pytest raccoglie come test
qualunque funzione il cui nome inizi per `test`, e un modulo importato in un
file di prova finiva per essere eseguito come se fosse una batteria di test.

Per leggere il testo di un PDF non serve un motore di rendering: serve un
lettore. Qui si usa pdfplumber, che e' gia' fra le dipendenze ed e' sotto
licenza MIT, al posto di PyMuPDF che e' AGPL-3.0 — e IUSENTRA viene servito
agli studi attraverso la rete.

Questo modulo legge e basta: non rende immagini e non modifica il documento.
Per le immagini c'e' `pct.rendering_pdf`.
"""

from __future__ import annotations

import io
from pathlib import Path


class LetturaPdfError(ValueError):
    """Il PDF non si apre, o non si lascia leggere."""


def _sorgente(origine: bytes | str | Path):
    if isinstance(origine, (str, Path)):
        return str(origine)
    return io.BytesIO(origine)


def leggi_testo(origine: bytes | str | Path, *, separatore: str = "\n") -> str:
    """Tutto il testo del documento, pagina dopo pagina.

    Una pagina senza testo estraibile — una scansione — contribuisce con una
    stringa vuota: sta a chi chiama decidere se mandarla all'OCR.
    """
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dipendenza dichiarata
        raise LetturaPdfError("Lettore PDF non disponibile.") from exc
    try:
        with pdfplumber.open(_sorgente(origine)) as documento:
            return separatore.join((pagina.extract_text() or "") for pagina in documento.pages)
    except Exception as exc:
        raise LetturaPdfError("PDF non leggibile.") from exc


def leggi_testo_pagine(origine: bytes | str | Path) -> list[str]:
    """Il testo di ogni pagina, nell'ordine del documento."""
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dipendenza dichiarata
        raise LetturaPdfError("Lettore PDF non disponibile.") from exc
    try:
        with pdfplumber.open(_sorgente(origine)) as documento:
            return [(pagina.extract_text() or "") for pagina in documento.pages]
    except Exception as exc:
        raise LetturaPdfError("PDF non leggibile.") from exc


__all__ = ["LetturaPdfError", "leggi_testo", "leggi_testo_pagine"]
