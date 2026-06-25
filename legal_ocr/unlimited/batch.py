from __future__ import annotations

import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legal_document_ingestion.evidence_hash import sha256_bytes
from legal_document_ingestion.repository import safe_join, sanitize_filename
from legal_ocr.models import PageArtifact

from .client import UnlimitedOcrClient
from .config import UnlimitedOcrSettings

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass(slots=True)
class UnlimitedOcrJob:
    index: int
    image_path: str
    output_path: str = ""
    page_number: int = 1


@dataclass(slots=True)
class UnlimitedOcrBatchResult:
    ok: bool
    mode: str
    total_jobs: int
    successful_jobs: int
    total_chars: int
    wall_time_seconds: float
    chars_per_second: float
    results: list[dict[str, Any]] = field(default_factory=list)


def collect_dataset_images(image_dir: str | Path) -> list[str]:
    root = Path(image_dir)
    if not root.is_dir():
        return []
    images = [
        str(path)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(images, key=lambda item: Path(item).stat().st_size, reverse=True)


def pdf_to_page_artifacts(pdf_path: str | Path, *, output_dir: str | Path | None = None, dpi: int = 300) -> list[PageArtifact]:
    import fitz  # type: ignore

    source = Path(pdf_path)
    target_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="iusentra_unlimited_pdf_"))
    target_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(source))
    pages: list[PageArtifact] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for index, page in enumerate(doc, start=1):
        target = safe_join(target_dir, f"{sanitize_filename(source.stem)}_page_{index:04d}.png")
        page.get_pixmap(matrix=matrix, alpha=False).save(target)
        data = target.read_bytes()
        rect = page.rect
        pages.append(
            PageArtifact(
                page=index,
                image_path=str(target),
                sha256=sha256_bytes(data),
                width=max(1, int(rect.width * dpi / 72)),
                height=max(1, int(rect.height * dpi / 72)),
                source_kind="raster",
                text_hint=page.get_text("text") or "",
                preprocessing=[f"unlimited-pdf-render:{dpi}dpi"],
            )
        )
    doc.close()
    return pages


def build_jobs_from_pages(pages: list[PageArtifact], *, output_dir: str | Path | None = None, stem: str = "documento") -> list[UnlimitedOcrJob]:
    jobs: list[UnlimitedOcrJob] = []
    for index, page in enumerate(pages, start=1):
        output_path = ""
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            output_path = str(Path(output_dir) / f"{sanitize_filename(stem)}_page_{index:04d}.md")
        jobs.append(UnlimitedOcrJob(index=index, image_path=page.image_path, output_path=output_path, page_number=page.page))
    return jobs


def build_jobs_from_target(target: str | Path, *, output_dir: str | Path | None = None, dpi: int = 300) -> tuple[str, list[UnlimitedOcrJob]]:
    path = Path(target)
    if path.is_dir():
        jobs = [
            UnlimitedOcrJob(index=index, image_path=image_path, output_path=_output_for_image(image_path, root=path, output_dir=output_dir), page_number=index)
            for index, image_path in enumerate(collect_dataset_images(path), start=1)
        ]
        return "dataset_images", jobs
    if path.suffix.lower() == ".pdf":
        pages = pdf_to_page_artifacts(path, output_dir=Path(output_dir) / "_pages" if output_dir else None, dpi=dpi)
        return "pdf_pages", build_jobs_from_pages(pages, output_dir=output_dir, stem=path.stem)
    if path.suffix.lower() in IMAGE_SUFFIXES:
        output_path = str(Path(output_dir) / f"{sanitize_filename(path.stem)}.md") if output_dir else ""
        return "dataset_images", [UnlimitedOcrJob(index=1, image_path=str(path), output_path=output_path, page_number=1)]
    raise ValueError("Target Unlimited-OCR non supportato: usare PDF, immagine o cartella immagini.")


def run_batch(jobs: list[UnlimitedOcrJob], *, settings: UnlimitedOcrSettings, client: UnlimitedOcrClient | None = None) -> UnlimitedOcrBatchResult:
    client = client or UnlimitedOcrClient(settings)
    wall_start = time.perf_counter()
    results: list[dict[str, Any]] = []

    def _run(job: UnlimitedOcrJob) -> dict[str, Any]:
        page = _page_from_job(job)
        result = client.generate_for_pages([page])
        text = str(result.get("text") or "")
        if job.output_path and text.strip():
            Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(job.output_path).write_text(text, encoding="utf-8")
        return {
            "index": job.index,
            "image_path": job.image_path,
            "output_path": job.output_path,
            "ok": bool(result.get("ok")),
            "chars": len(text),
            "elapsed_ms": result.get("elapsed_ms"),
            "attempts": result.get("attempts"),
            "error": result.get("error") or "",
            "text": text,
        }

    with ThreadPoolExecutor(max_workers=settings.concurrency) as executor:
        futures = {executor.submit(_run, job): job for job in jobs}
        for future in as_completed(futures):
            results.append(future.result())

    wall_time = max(0.001, time.perf_counter() - wall_start)
    total_chars = sum(int(item.get("chars") or 0) for item in results)
    successful = sum(1 for item in results if bool(item.get("ok")))
    return UnlimitedOcrBatchResult(
        ok=successful == len(jobs) if jobs else False,
        mode="batch",
        total_jobs=len(jobs),
        successful_jobs=successful,
        total_chars=total_chars,
        wall_time_seconds=round(wall_time, 3),
        chars_per_second=round(total_chars / wall_time, 2),
        results=sorted(results, key=lambda item: int(item.get("index") or 0)),
    )


def _page_from_job(job: UnlimitedOcrJob) -> PageArtifact:
    path = Path(job.image_path)
    return PageArtifact(
        page=job.page_number,
        image_path=str(path),
        sha256=sha256_bytes(path.read_bytes()),
        width=1,
        height=1,
        source_kind="raster",
        text_hint="",
        preprocessing=["unlimited-batch-job"],
    )


def _output_for_image(image_path: str, *, root: Path, output_dir: str | Path | None) -> str:
    if not output_dir:
        return ""
    rel = os.path.relpath(image_path, root)
    stem = Path(rel).with_suffix("").as_posix().replace("/", "__")
    return str(Path(output_dir) / f"{sanitize_filename(stem)}.md")
