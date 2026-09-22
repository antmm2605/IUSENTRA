"""Operazioni documentali transienti usate dalla superficie React.

I file caricati vengono elaborati in memoria e restituiti al browser. Nessun
contenuto viene persistito senza un'azione esplicita nel fascicolo.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader, PdfWriter


MAX_FILES = 80
MAX_FILE_BYTES = 60 * 1024 * 1024
MAX_TOTAL_BYTES = 180 * 1024 * 1024
MAX_PAGES = 1_500


class DocumentToolError(ValueError):
    """Errore leggibile prodotto da un'operazione documentale."""


@dataclass(frozen=True)
class UploadedDocument:
    name: str
    data: bytes


def safe_output_name(value: str, extension: str, fallback: str) -> str:
    raw = Path(str(value or "").strip()).name
    stem = Path(raw).stem if raw else fallback
    stem = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .") or fallback
    return f"{stem[:120]}.{extension.lstrip('.').lower()}"


def validate_uploads(files: Iterable[UploadedDocument], *, minimum: int = 1) -> list[UploadedDocument]:
    rows = list(files)
    if len(rows) < minimum:
        raise DocumentToolError(
            "Seleziona almeno due PDF da unire." if minimum == 2 else "Seleziona almeno un documento."
        )
    if len(rows) > MAX_FILES:
        raise DocumentToolError(f"Puoi elaborare al massimo {MAX_FILES} documenti per volta.")
    total = 0
    cleaned: list[UploadedDocument] = []
    for index, item in enumerate(rows, start=1):
        name = Path(str(item.name or "").strip()).name or f"documento-{index}"
        data = bytes(item.data or b"")
        if not data:
            raise DocumentToolError(f"Il file {name} è vuoto.")
        if len(data) > MAX_FILE_BYTES:
            raise DocumentToolError(f"Il file {name} supera 60 MB.")
        total += len(data)
        cleaned.append(UploadedDocument(name=name, data=data))
    if total > MAX_TOTAL_BYTES:
        raise DocumentToolError("I documenti selezionati superano complessivamente 180 MB.")
    return cleaned


def _pdf_reader(document: UploadedDocument) -> PdfReader:
    if not document.data.lstrip().startswith(b"%PDF-"):
        raise DocumentToolError(f"Il file {document.name} non è un PDF leggibile.")
    try:
        reader = PdfReader(io.BytesIO(document.data), strict=False)
        if reader.is_encrypted:
            raise DocumentToolError(
                f"Il PDF {document.name} è protetto o crittografato. Sostituiscilo con una copia leggibile."
            )
        return reader
    except DocumentToolError:
        raise
    except Exception as exc:
        raise DocumentToolError(
            f"Il PDF {document.name} è danneggiato o non leggibile."
        ) from exc


def merge_pdfs(files: Iterable[UploadedDocument]) -> tuple[bytes, int]:
    documents = validate_uploads(files, minimum=2)
    writer = PdfWriter()
    page_count = 0
    for document in documents:
        reader = _pdf_reader(document)
        page_count += len(reader.pages)
        if page_count > MAX_PAGES:
            raise DocumentToolError(f"Il documento risultante supera {MAX_PAGES} pagine.")
        for page in reader.pages:
            writer.add_page(page)
    writer.add_metadata({"/Producer": "IUSENTRA", "/Creator": "IUSENTRA"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), page_count


def create_zip(files: Iterable[UploadedDocument], logical_names: Iterable[str] | None = None) -> bytes:
    documents = validate_uploads(files)
    requested = list(logical_names or [])
    used: set[str] = set()
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for index, document in enumerate(documents):
            proposed = requested[index].strip() if index < len(requested) else ""
            source_suffixes = "".join(Path(document.name).suffixes)
            logical = Path(proposed).name if proposed else document.name
            if proposed and source_suffixes and not logical.casefold().endswith(source_suffixes.casefold()):
                logical += source_suffixes
            logical = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", " ", logical)
            logical = re.sub(r"\s+", " ", logical).strip(" .") or document.name
            key = logical.casefold()
            if key in used:
                raise DocumentToolError(f"Il nome {logical} è presente più volte nell'archivio.")
            used.add(key)
            archive.writestr(logical[:180], document.data)
    return output.getvalue()


A4_POINTS = (595.276, 841.89)


def _image_on_a4_page(data: bytes) -> bytes:
    """Pagina A4 (orientata come l'immagine) con l'immagine centrata e intera, senza ricampionarla."""
    import io

    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    try:
        with Image.open(io.BytesIO(data)) as immagine:
            larghezza_img, altezza_img = immagine.size
    except Exception as errore:
        raise DocumentToolError("Immagine non leggibile.") from errore
    if larghezza_img <= 0 or altezza_img <= 0:
        raise DocumentToolError("Immagine non leggibile.")

    orizzontale = larghezza_img > altezza_img
    larghezza, altezza = (A4_POINTS[1], A4_POINTS[0]) if orizzontale else A4_POINTS
    # L'immagine entra intera e mantiene le proporzioni: si scala sul lato che
    # tocca per primo il bordo, e si centra sull'altro.
    fattore = min(larghezza / larghezza_img, altezza / altezza_img)
    disegnata_larga = larghezza_img * fattore
    disegnata_alta = altezza_img * fattore

    uscita = io.BytesIO()
    foglio = canvas.Canvas(uscita, pagesize=(larghezza, altezza))
    foglio.drawImage(
        ImageReader(io.BytesIO(data)),
        (larghezza - disegnata_larga) / 2,
        (altezza - disegnata_alta) / 2,
        width=disegnata_larga,
        height=disegnata_alta,
        preserveAspectRatio=True,
        anchor="c",
    )
    foglio.showPage()
    foglio.save()
    return uscita.getvalue()


def _image_on_its_own_page(data: bytes) -> bytes:
    """Una pagina della misura esatta dell'immagine, a 72 punti per pollice.

    E' il comportamento senza formato dichiarato: la pagina prende le
    dimensioni dell'immagine invece di adattarla a un foglio.
    """
    import io

    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    try:
        with Image.open(io.BytesIO(data)) as immagine:
            larghezza, altezza = immagine.size
    except Exception as errore:
        raise DocumentToolError("Immagine non leggibile.") from errore
    if larghezza <= 0 or altezza <= 0:
        raise DocumentToolError("Immagine non leggibile.")

    uscita = io.BytesIO()
    foglio = canvas.Canvas(uscita, pagesize=(float(larghezza), float(altezza)))
    foglio.drawImage(ImageReader(io.BytesIO(data)), 0, 0, width=float(larghezza), height=float(altezza))
    foglio.showPage()
    foglio.save()
    return uscita.getvalue()


def images_to_pdf(
    files: Iterable[UploadedDocument],
    rotations: Iterable[int] | None = None,
    *,
    page_format: str = "",
) -> tuple[bytes, int]:
    """Immagini e PDF in un unico PDF; con ``page_format="a4"`` ogni immagine occupa una pagina A4."""
    if page_format not in {"", "a4"}:
        raise DocumentToolError("Formato di pagina non supportato.")
    documents = validate_uploads(files)
    angles = list(rotations or [])
    writer = PdfWriter()
    pages = 0
    for index, document in enumerate(documents):
        suffix = Path(document.name).suffix.lower()
        if suffix == ".pdf" or document.data.lstrip().startswith(b"%PDF-"):
            reader = _pdf_reader(document)
            for page in reader.pages:
                angle = angles[index] if index < len(angles) else 0
                if angle % 360:
                    page.rotate(angle % 360)
                writer.add_page(page)
                pages += 1
            continue
        try:
            if page_format == "a4":
                pdf_bytes = _image_on_a4_page(document.data)
            else:
                pdf_bytes = _image_on_its_own_page(document.data)
            reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        except Exception as exc:
            raise DocumentToolError(
                f"L'immagine {document.name} non è in un formato supportato."
            ) from exc
        for page in reader.pages:
            angle = angles[index] if index < len(angles) else 0
            if angle % 360:
                page.rotate(angle % 360)
            writer.add_page(page)
            pages += 1
        if pages > MAX_PAGES:
            raise DocumentToolError(f"Il documento risultante supera {MAX_PAGES} pagine.")
    if not pages:
        raise DocumentToolError("Nessuna pagina valida da acquisire.")
    writer.add_metadata({"/Producer": "IUSENTRA", "/Creator": "IUSENTRA"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), pages


def rotate_pdf_bytes(data: bytes, *, angle: int, name: str = "documento.pdf") -> tuple[bytes, int]:
    """Restituisce una copia PDF ruotata di tutte le pagine.

    L'operazione è intenzionalmente separata dal salvataggio nel fascicolo: qui
    si trasformano solo byte PDF chiari, mentre la route decide se e come
    registrarli nel repository tenant-aware.
    """

    normalized = int(angle or 0) % 360
    if normalized not in {90, 180, 270}:
        raise DocumentToolError("Scegli una rotazione di 90, 180 o 270 gradi.")
    reader = _pdf_reader(UploadedDocument(name=name, data=data))
    if len(reader.pages) > MAX_PAGES:
        raise DocumentToolError(f"Il documento supera {MAX_PAGES} pagine.")
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(normalized)
        writer.add_page(page)
    writer.add_metadata({"/Producer": "IUSENTRA", "/Creator": "IUSENTRA"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue(), len(reader.pages)
