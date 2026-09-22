"""Le pagine di un PDF come immagini, senza PyMuPDF.

Il rendering era sparso in quattro punti, ognuno con la sua variante di
`get_pixmap`. Qui ce n'e' uno solo, e sta sopra PDFium invece che sopra MuPDF.

La ragione non e' tecnica ma di licenza: PyMuPDF e' sotto AGPL-3.0, e IUSENTRA
viene servito agli studi attraverso la rete. PDFium ha una licenza BSD e
pypdfium2 sta fra Apache-2.0 e BSD-3: si incorporano senza obblighi di
apertura. Questo modulo e' il primo pezzo della sostituzione; il resto di
PyMuPDF resta dov'e' finche' non viene migrato a sua volta.

Il rendering e' puro: legge e disegna, non modifica mai il documento.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Oltre questo ingrandimento un'anteprima diventa un'immagine enorme senza
#: aggiungere niente di leggibile.
SCALA_MASSIMA = 3.0
SCALA_MINIMA = 0.5


class RenderingPdfError(ValueError):
    """Il PDF non si apre, o la pagina chiesta non c'e'."""


@dataclass(frozen=True)
class DimensioniPagina:
    numero: int
    larghezza: float
    altezza: float


def _documento(origine: bytes | str | Path):
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - dipendenza dichiarata
        raise RenderingPdfError("Motore di rendering PDF non disponibile.") from exc
    try:
        if isinstance(origine, (str, Path)):
            return pdfium.PdfDocument(str(origine))
        return pdfium.PdfDocument(origine)
    except Exception as exc:
        raise RenderingPdfError("PDF non apribile per il rendering.") from exc


def _scala_ammessa(valore: float | None, predefinita: float) -> float:
    try:
        scala = float(valore if valore else predefinita)
    except (TypeError, ValueError):
        scala = predefinita
    return max(SCALA_MINIMA, min(scala, SCALA_MASSIMA))


def _png_da_pagina(pagina: Any, scala: float) -> bytes:
    immagine = pagina.render(scale=scala).to_pil()
    buffer = io.BytesIO()
    immagine.save(buffer, format="PNG")
    return buffer.getvalue()


def dimensioni_pagine(origine: bytes | str | Path) -> list[DimensioniPagina]:
    """Numero, larghezza e altezza di ogni pagina, in punti."""
    documento = _documento(origine)
    try:
        return [
            DimensioniPagina(
                numero=indice + 1,
                larghezza=float(documento[indice].get_width()),
                altezza=float(documento[indice].get_height()),
            )
            for indice in range(len(documento))
        ]
    finally:
        documento.close()


def pagina_png(
    origine: bytes | str | Path,
    *,
    numero_pagina: int,
    scala: float | None = None,
    predefinita: float = 1.85,
) -> bytes:
    """Una pagina sola come PNG. Le pagine si contano da uno."""
    documento = _documento(origine)
    try:
        if numero_pagina < 1 or numero_pagina > len(documento):
            raise RenderingPdfError("Pagina PDF non disponibile.")
        return _png_da_pagina(documento[numero_pagina - 1], _scala_ammessa(scala, predefinita))
    finally:
        documento.close()


def pagine_png(origine: bytes | str | Path, *, dpi: int = 130) -> list[dict[str, Any]]:
    """Tutte le pagine come PNG, con le dimensioni in punti.

    Il dpi si traduce in ingrandimento sui 72 punti per pollice del PDF.
    """
    scala = _scala_ammessa(max(1, int(dpi or 130)) / 72.0, 1.0)
    documento = _documento(origine)
    try:
        fuori: list[dict[str, Any]] = []
        for indice in range(len(documento)):
            pagina = documento[indice]
            fuori.append(
                {
                    "pagina": indice,
                    "larghezza": float(pagina.get_width()),
                    "altezza": float(pagina.get_height()),
                    "png": _png_da_pagina(pagina, scala),
                }
            )
        return fuori
    finally:
        documento.close()


__all__ = [
    "SCALA_MASSIMA",
    "SCALA_MINIMA",
    "DimensioniPagina",
    "RenderingPdfError",
    "dimensioni_pagine",
    "pagina_png",
    "pagine_png",
]
