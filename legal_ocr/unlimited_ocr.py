from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from .models import EngineRun, PageArtifact
from .unlimited.client import UnlimitedOcrClient
from .unlimited.config import UnlimitedOcrSettings


class UnlimitedOcrEngine:
    """Adapter legal-grade per Unlimited-OCR self-hosted.

    Replica la logica utile della repo Baidu dentro una struttura nostra:
    PDF/immagini -> payload OpenAI-compatible -> parsing lungo -> benchmark.
    In IUSENTRA aggiunge un passaggio native-first per efficienza: le pagine con
    testo PDF buono non consumano GPU, quelle scansionate vanno al servizio AI.
    """

    name = "unlimited-ocr"

    def __init__(self, *, client: UnlimitedOcrClient | None = None, settings: UnlimitedOcrSettings | None = None) -> None:
        self.settings = settings or UnlimitedOcrSettings.from_env()
        self.client = client or UnlimitedOcrClient(self.settings)

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        readiness = self.settings.readiness()
        if not readiness["ok"]:
            return EngineRun(
                self.name,
                "unlimited-ocr:not-ready",
                [],
                "",
                [],
                language,
                0.0,
                warnings=list(readiness.get("warnings") or []),
                errors=[str(readiness.get("reason") or "Unlimited-OCR non pronto.")],
            )

        started = time.perf_counter()
        native_pages, ocr_pages, page_warnings = split_native_and_ocr_pages(
            pages,
            max_pages=self.settings.max_pages,
            max_image_bytes=self.settings.max_image_bytes,
        )
        if not native_pages and not ocr_pages:
            return EngineRun(
                self.name,
                "unlimited-ocr:no-pages",
                [],
                "",
                [],
                language,
                0.0,
                warnings=page_warnings,
                errors=["Nessuna pagina leggibile o inviabile a Unlimited-OCR."],
            )

        model_text = ""
        attempts = 0
        error = ""
        if ocr_pages:
            result = self.client.generate_for_pages(ocr_pages)
            model_text = _normalize_text(str(result.get("text") or ""))
            attempts = int(result.get("attempts") or 0)
            error = str(result.get("error") or "")
            if not model_text:
                return EngineRun(
                    self.name,
                    "unlimited-ocr:error",
                    [],
                    "",
                    [],
                    language,
                    0.0,
                    warnings=page_warnings,
                    errors=[error or "Unlimited-OCR non ha restituito testo per le pagine scansionate."],
                )

        page_texts = compose_page_texts(pages, native_pages=native_pages, model_text=model_text)
        combined = _normalize_text("\n\n".join(text for text in page_texts if text.strip()))
        if not combined:
            return EngineRun(
                self.name,
                "unlimited-ocr:empty",
                [],
                "",
                [],
                language,
                0.0,
                warnings=page_warnings,
                errors=["La lettura ibrida non ha prodotto testo utile."],
            )

        tokens = tokens_from_text_by_page(page_texts, pages, confidence=self.settings.synthetic_confidence)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        native_count = len(native_pages)
        ocr_count = len(ocr_pages)
        warnings = [
            *list(readiness.get("warnings") or []),
            *page_warnings,
            (
                "Coordinate native non disponibili dall'endpoint Unlimited-OCR: "
                "le parti AI usano confidenza sintetica prudente e richiedono QC/HIL se il contesto lo impone."
            ),
        ]
        version = (
            f"unlimited-ocr:hybrid-native-first model={self.settings.model} "
            f"native_pages={native_count} ai_pages={ocr_count} attempts={attempts} elapsed_ms={elapsed_ms}"
        )
        return EngineRun(
            self.name,
            version,
            tokens,
            combined,
            page_texts,
            language,
            self.settings.synthetic_confidence,
            warnings=warnings,
        )


def split_native_and_ocr_pages(
    pages: list[PageArtifact],
    *,
    max_pages: int,
    max_image_bytes: int,
) -> tuple[list[PageArtifact], list[PageArtifact], list[str]]:
    native_pages: list[PageArtifact] = []
    ocr_pages: list[PageArtifact] = []
    warnings: list[str] = []
    for page in pages[:max_pages]:
        if _native_text_is_good(page.text_hint):
            native_pages.append(page)
            continue
        try:
            size = Path(page.image_path).stat().st_size
        except OSError as exc:
            warnings.append(f"Pagina {page.page} non leggibile per Unlimited-OCR: {exc}.")
            continue
        if size > max_image_bytes:
            warnings.append(f"Pagina {page.page} esclusa da Unlimited-OCR: immagine oltre il limite configurato.")
            continue
        ocr_pages.append(page)
    if len(pages) > max_pages:
        warnings.append(f"Documento limitato a {max_pages} pagine per il benchmark Unlimited-OCR.")
    return native_pages, ocr_pages, warnings


def compose_page_texts(pages: list[PageArtifact], *, native_pages: list[PageArtifact], model_text: str) -> list[str]:
    native_by_page = {page.page: _normalize_text(page.text_hint) for page in native_pages}
    page_texts: list[str] = []
    model_inserted = False
    for page in pages:
        if page.page in native_by_page:
            page_texts.append(native_by_page[page.page])
        elif model_text and not model_inserted:
            page_texts.append(model_text)
            model_inserted = True
        else:
            page_texts.append("")
    if model_text and not model_inserted:
        page_texts.append(model_text)
    return page_texts


def tokens_from_text_by_page(page_texts: list[str], pages: list[PageArtifact], *, confidence: float) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    global_offset = 0
    for index, text in enumerate(page_texts):
        page_number = pages[index].page if index < len(pages) else index + 1
        for match in re.finditer(r"\S+", text):
            token = match.group(0)
            tokens.append(
                {
                    "token": token,
                    "start": global_offset + match.start(),
                    "end": global_offset + match.end(),
                    "confidence": confidence,
                    "bbox": [],
                    "line_id": f"p{page_number}-unlimited-hybrid",
                    "page": page_number,
                    "bbox_source": "native_or_unlimited_ocr_without_coordinates",
                }
            )
        global_offset += len(text) + 1
    return tokens


def _native_text_is_good(text: str) -> bool:
    normalized = _normalize_text(text)
    if len(normalized) < 120:
        return False
    cid_ratio = normalized.count("(cid:") / max(1, len(normalized))
    alpha_ratio = sum(1 for char in normalized if char.isalpha()) / max(1, len(normalized))
    return cid_ratio == 0 and alpha_ratio >= 0.35


def _normalize_text(value: str) -> str:
    text = str(value or "").replace("\ufeff", "").replace("\r", "").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
