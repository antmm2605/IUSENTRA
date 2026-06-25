from __future__ import annotations

import io
import math
import os
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from legal_document_ingestion.evidence_hash import sha256_bytes
from legal_document_ingestion.repository import safe_join, sanitize_filename

from .models import PageArtifact

TEXT_SUFFIXES = {".txt", ".csv", ".json", ".xml", ".eml"}


def rasterize_document(data: bytes, filename: str, pages_dir: str | Path) -> list[PageArtifact]:
    suffix = Path(filename or "").suffix.lower()
    target_dir = Path(pages_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if suffix == ".pdf" or data[:4] == b"%PDF":
        return _rasterize_pdf(data, target_dir)
    if suffix in TEXT_SUFFIXES:
        return [_write_text_placeholder(data, filename, target_dir)]
    return _rasterize_image(data, target_dir)


def _rasterize_pdf(data: bytes, pages_dir: Path) -> list[PageArtifact]:
    try:
        import fitz  # type: ignore
    except Exception:
        return [_write_text_placeholder(b"", "documento.txt", pages_dir)]
    doc = fitz.open(stream=data, filetype="pdf")
    pages: list[PageArtifact] = []
    scale = _float_env("IUSENTRA_LEGAL_OCR_RENDER_SCALE", default=3.0, minimum=2.0, maximum=6.0)
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        pages.extend(_write_preprocessed_pages(image, pages_dir, index, text_hint=page.get_text("text") or ""))
    return pages


def _rasterize_image(data: bytes, pages_dir: Path) -> list[PageArtifact]:
    image = Image.open(io.BytesIO(data))
    if getattr(image, "n_frames", 1) > 1:
        pages: list[PageArtifact] = []
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            pages.extend(_write_preprocessed_pages(image.copy(), pages_dir, index + 1, text_hint=""))
        return pages
    return _write_preprocessed_pages(image, pages_dir, 1, text_hint="")


def _write_text_placeholder(data: bytes, filename: str, pages_dir: Path) -> PageArtifact:
    text = data.decode("utf-8", errors="ignore")
    image = Image.new("L", (1200, 1600), "white")
    target = safe_join(pages_dir, f"page_001_{sanitize_filename(filename)}.png")
    image.save(target)
    return PageArtifact(1, str(target), sha256_bytes(target.read_bytes()), image.width, image.height, "text", text, ["text-placeholder"])


def _write_preprocessed_pages(image: Image.Image, pages_dir: Path, page_number: int, *, text_hint: str) -> list[PageArtifact]:
    prepared = _preprocess_image(image)
    candidates = _split_two_up(prepared)
    pages: list[PageArtifact] = []
    for split_index, candidate in enumerate(candidates, start=1):
        suffix = "" if len(candidates) == 1 else f"_{split_index}"
        target = safe_join(pages_dir, f"page_{page_number:03d}{suffix}.png")
        candidate.save(target)
        pages.append(
            PageArtifact(
                page_number if len(candidates) == 1 else (page_number * 10 + split_index),
                str(target),
                sha256_bytes(target.read_bytes()),
                candidate.width,
                candidate.height,
                "raster",
                text_hint,
                ["grayscale", "adaptive-contrast", "sharpen-for-ocr"] + (["page-split"] if len(candidates) > 1 else []),
            )
        )
    return pages


def _preprocess_image(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Sharpness(gray).enhance(1.8)
    return ImageEnhance.Contrast(gray).enhance(1.08)


def _split_two_up(image: Image.Image) -> list[Image.Image]:
    width, height = image.size
    if width < height * 1.35:
        return [image]
    return [image.crop((0, 0, math.floor(width / 2), height)), image.crop((math.floor(width / 2), 0, width, height))]


def _float_env(name: str, *, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(os.getenv(name, "") or "").strip() or default)
    except ValueError:
        value = default
    return min(max(value, minimum), maximum)
