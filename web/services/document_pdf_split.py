"""Estrazione di pagine PDF in memoria, senza modificare la fonte."""
from __future__ import annotations

import io
import re

from web.services.document_tools import (
    MAX_PAGES, DocumentToolError, UploadedDocument, _pdf_reader, validate_uploads,
)


def selected_pages(selection: str, total: int) -> list[int]:
    """Indici da zero nell'ordine richiesto; rifiuta ambiguità e duplicati."""
    if not selection or len(selection) > 10000:
        raise DocumentToolError("Indica le pagine da estrarre, per esempio 1-3, 5.")
    result: list[int] = []
    seen: set[int] = set()
    for token in selection.split(','):
        match = re.fullmatch(r'\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?', token)
        if not match:
            raise DocumentToolError("Usa numeri e intervalli separati da virgole, per esempio 1-3, 5.")
        # Il limite lessicale evita numeri arbitrariamente grandi prima di int().
        if len(match[1]) > 6 or (match[2] and len(match[2]) > 6):
            raise DocumentToolError(f"Le pagine devono essere comprese tra 1 e {total}.")
        first, last = int(match[1]), int(match[2] or match[1])
        if not 1 <= first <= last <= total:
            raise DocumentToolError(f"Le pagine devono essere comprese tra 1 e {total}, con intervalli in ordine crescente.")
        if len(result) + last - first + 1 > MAX_PAGES:
            raise DocumentToolError(f"Puoi estrarre al massimo {MAX_PAGES} pagine per operazione.")
        for page in range(first - 1, last):
            if page in seen:
                raise DocumentToolError(f"La pagina {page + 1} è selezionata più volte. Correggi gli intervalli.")
            result.append(page)
            seen.add(page)
    return result


def split_pdf(files: list[UploadedDocument], selection: str) -> tuple[bytes, int]:
    validate_uploads(files)
    if len(files) != 1:
        raise DocumentToolError("Per dividere un PDF seleziona un solo documento.")
    try:
        from pypdf import PdfWriter
        reader = _pdf_reader(files[0])
        total = len(reader.pages)
        if not total or total > MAX_PAGES:
            raise DocumentToolError(f"Il PDF deve contenere da 1 a {MAX_PAGES} pagine.")
        pages = selected_pages(selection, total)
        writer = PdfWriter()
        for page in pages:
            writer.add_page(reader.pages[page])
        writer.add_metadata({"/Producer": "IUSENTRA", "/Creator": "IUSENTRA - estrazione pagine"})
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue(), len(pages)
    except DocumentToolError:
        raise
    except Exception as exc:
        raise DocumentToolError("Il PDF non può essere diviso: controlla che non sia danneggiato.") from exc
