from __future__ import annotations

import re
from typing import Protocol

from .models import EngineRun, PageArtifact
from .unlimited_ocr import UnlimitedOcrEngine


class OcrEngine(Protocol):
    name: str

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        ...


class TesseractOcrEngine:
    name = "tesseract"

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        try:
            import pytesseract  # type: ignore
            from pytesseract import Output  # type: ignore
        except Exception as exc:
            return EngineRun(self.name, "tesseract:unavailable", [], "", [], language, 0.0, errors=[f"Tesseract non disponibile: {exc}"])
        tokens: list[dict] = []
        page_texts: list[str] = []
        offset = 0
        for page in pages:
            data = pytesseract.image_to_data(page.image_path, lang=language, output_type=Output.DICT)
            words: list[str] = []
            for index, raw in enumerate(data.get("text") or []):
                token = str(raw or "").strip()
                if not token:
                    continue
                try:
                    conf = max(0.0, min(1.0, float(data.get("conf", ["-1"])[index]) / 100.0))
                except (TypeError, ValueError):
                    conf = 0.0
                start = offset + len(" ".join(words)) + (1 if words else 0)
                words.append(token)
                tokens.append({"token": token, "start": start, "end": start + len(token), "confidence": conf, "bbox": [int(data.get("left", [0])[index]), int(data.get("top", [0])[index]), int(data.get("width", [0])[index]), int(data.get("height", [0])[index])], "line_id": f"p{page.page}-l{data.get('line_num', [0])[index]}", "page": page.page})
            page_text = " ".join(words) or page.text_hint
            page_texts.append(page_text)
            offset += len(page_text) + 1
        return EngineRun(self.name, _version(pytesseract), tokens, "\n".join(page_texts).strip(), page_texts, language, 0.95 if tokens else 0.0)


class NativeTextFallbackEngine:
    name = "native-text-fallback"

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        tokens: list[dict] = []
        texts: list[str] = []
        offset = 0
        for page in pages:
            text = str(page.text_hint or "")
            texts.append(text)
            for match in re.finditer(r"\S+", text):
                token = match.group(0)
                tokens.append({"token": token, "start": offset + match.start(), "end": offset + match.end(), "confidence": 0.96, "bbox": [0, 0, max(1, len(token) * 8), 12], "line_id": f"p{page.page}-native", "page": page.page})
            offset += len(text) + 1
        warnings = [] if any(t.strip() for t in texts) else ["Nessun testo nativo disponibile per il fallback locale."]
        return EngineRun(self.name, "native-text-fallback:2026.05.24", tokens, "\n".join(texts).strip(), texts, language, 0.99 if tokens else 0.0, warnings=warnings)


class StaticLowConfidenceEngine:
    name = "static-low-confidence"

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        page = pages[0].page if pages else 1
        tokens = [{"token": "lettura", "start": 0, "end": 7, "confidence": 0.42, "bbox": [0, 0, 40, 10], "line_id": "p1-low", "page": page}, {"token": "incerta", "start": 8, "end": 15, "confidence": 0.44, "bbox": [45, 0, 42, 10], "line_id": "p1-low", "page": page}]
        return EngineRun(self.name, "static-low-confidence:2026.05.24", tokens, "lettura incerta", ["lettura incerta"], language, 0.2)


class EasyOcrEngine:
    """Adapter EasyOCR (motore generale, locale). Reale se installato, fallback se assente.

    Il modello viene caricato una sola volta e riusato (cache modelli). Se la
    libreria non è installata, ritorna un EngineRun con errori: la catena di
    fallback della pipeline passa al motore successivo (nessun silenzio).
    """

    name = "easyocr"
    _reader_cache: dict[str, object] = {}

    def _reader(self, language: str):
        langs = ["it"] if language.startswith("it") else [language[:2] or "en"]
        key = ",".join(langs)
        if key not in self._reader_cache:
            import easyocr  # type: ignore

            self._reader_cache[key] = easyocr.Reader(langs, gpu=False)
        return self._reader_cache[key]

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        try:
            reader = self._reader(language)
        except Exception as exc:
            return EngineRun(self.name, "easyocr:unavailable", [], "", [], language, 0.0, errors=[f"EasyOCR non disponibile: {exc}"])
        tokens: list[dict] = []
        page_texts: list[str] = []
        offset = 0
        for page in pages:
            words: list[str] = []
            try:
                detections = reader.readtext(page.image_path)
            except Exception as exc:
                return EngineRun(self.name, "easyocr:error", tokens, "\n".join(page_texts), page_texts, language, 0.0, errors=[f"EasyOCR errore lettura: {exc}"])
            for box, raw, conf in detections:
                token = str(raw or "").strip()
                if not token:
                    continue
                xs = [int(point[0]) for point in box]
                ys = [int(point[1]) for point in box]
                start = offset + len(" ".join(words)) + (1 if words else 0)
                words.append(token)
                tokens.append({"token": token, "start": start, "end": start + len(token), "confidence": max(0.0, min(1.0, float(conf or 0.0))), "bbox": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)], "line_id": f"p{page.page}-easyocr", "page": page.page})
            page_text = " ".join(words) or page.text_hint
            page_texts.append(page_text)
            offset += len(page_text) + 1
        return EngineRun(self.name, "easyocr:installed", tokens, "\n".join(page_texts).strip(), page_texts, language, 0.9 if tokens else 0.0)


class PaddleOcrEngine:
    """Adapter PP-OCR/PaddleOCR (motore generale, locale). Reale se installato, fallback se assente."""

    name = "paddleocr"
    _engine_cache: dict[str, object] = {}

    def _engine(self, language: str):
        lang = "it" if language.startswith("it") else (language[:2] or "en")
        if lang not in self._engine_cache:
            from paddleocr import PaddleOCR  # type: ignore

            self._engine_cache[lang] = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        return self._engine_cache[lang]

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        try:
            engine = self._engine(language)
        except Exception as exc:
            return EngineRun(self.name, "paddleocr:unavailable", [], "", [], language, 0.0, errors=[f"PaddleOCR non disponibile: {exc}"])
        tokens: list[dict] = []
        page_texts: list[str] = []
        offset = 0
        for page in pages:
            words: list[str] = []
            try:
                result = engine.ocr(page.image_path, cls=True) or []
            except Exception as exc:
                return EngineRun(self.name, "paddleocr:error", tokens, "\n".join(page_texts), page_texts, language, 0.0, errors=[f"PaddleOCR errore lettura: {exc}"])
            for block in result:
                for line in block or []:
                    box, (raw, conf) = line[0], line[1]
                    token = str(raw or "").strip()
                    if not token:
                        continue
                    xs = [int(point[0]) for point in box]
                    ys = [int(point[1]) for point in box]
                    start = offset + len(" ".join(words)) + (1 if words else 0)
                    words.append(token)
                    tokens.append({"token": token, "start": start, "end": start + len(token), "confidence": max(0.0, min(1.0, float(conf or 0.0))), "bbox": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)], "line_id": f"p{page.page}-paddle", "page": page.page})
            page_text = " ".join(words) or page.text_hint
            page_texts.append(page_text)
            offset += len(page_text) + 1
        return EngineRun(self.name, "paddleocr:installed", tokens, "\n".join(page_texts).strip(), page_texts, language, 0.9 if tokens else 0.0)


class ExternalAdapterUnavailableEngine:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        return EngineRun(
            self.name,
            f"{self.name}:adapter-unavailable",
            [],
            "",
            [],
            language,
            0.0,
            errors=[f"Motore esterno {self.name} non configurato per policy local-first."],
        )


def build_engine(name: str) -> OcrEngine:
    clean = str(name or "").strip().lower()
    if clean in {"tesseract", "tesseract-local"}:
        return TesseractOcrEngine()
    if clean in {"native", "native-text", "native-text-fallback", "fallback"}:
        return NativeTextFallbackEngine()
    if clean == "static-low-confidence":
        return StaticLowConfidenceEngine()
    if clean in {"easyocr", "easy-ocr"}:
        return EasyOcrEngine()
    if clean in {"paddleocr", "paddle", "ppocr", "pp-ocr"}:
        return PaddleOcrEngine()
    if clean in {"unlimited-ocr", "unlimited_ocr", "unlimitedocr", "baidu-unlimited-ocr"}:
        return UnlimitedOcrEngine()
    if clean in {"abbyy", "google-vision", "google_vision", "trocr", "cloud"}:
        return ExternalAdapterUnavailableEngine(clean)
    raise ValueError(f"Motore OCR non configurato o non locale: {name}")


def _version(pytesseract: object) -> str:
    try:
        return f"tesseract:{pytesseract.get_tesseract_version()}"
    except Exception:
        return "tesseract:unknown"
