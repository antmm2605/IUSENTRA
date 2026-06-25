from __future__ import annotations

import os
import re
from pathlib import Path
from shutil import which
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
        tess_config = _configure_tesseract_runtime(pytesseract)
        try:
            version = _version(pytesseract)
        except Exception as exc:
            return EngineRun(self.name, "tesseract:unavailable", [], "", [], language, 0.0, errors=[f"Tesseract non disponibile: {exc}"])
        lang = _resolve_tesseract_language(pytesseract, language, tess_config)
        tokens: list[dict] = []
        page_texts: list[str] = []
        warnings: list[str] = []
        offset = 0
        for page in pages:
            candidate = _read_tesseract_page_best(
                pytesseract,
                Output,
                page,
                lang=lang,
                base_config=tess_config,
                offset=offset,
                line_prefix="tesseract",
            )
            if candidate["warnings"]:
                warnings.extend(candidate["warnings"])
            page_text = str(candidate["text"] or page.text_hint or "")
            tokens.extend(candidate["tokens"])
            page_texts.append(page_text)
            offset += len(page_text) + 1
        if not tokens and not any(text.strip() for text in page_texts):
            warnings.append("Tesseract eseguito ma senza testo leggibile.")
        return EngineRun(
            self.name,
            version,
            tokens,
            "\n".join(page_texts).strip(),
            page_texts,
            language,
            0.95 if tokens else 0.0,
            warnings=warnings,
        )


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


class HybridLocalOcrEngine:
    """Fallback efficiente: testo PDF nativo quando affidabile, Tesseract solo sulle scansioni."""

    name = "local-hybrid-ocr"

    def run(self, pages: list[PageArtifact], *, language: str = "ita") -> EngineRun:
        try:
            import pytesseract  # type: ignore
            from pytesseract import Output  # type: ignore
        except Exception as exc:
            native = NativeTextFallbackEngine().run(pages, language=language)
            native.engine = self.name
            native.version = "local-hybrid-ocr:native-only"
            native.warnings.append(f"Tesseract non disponibile per pagine scansionate: {exc}")
            return native

        tess_config = _configure_tesseract_runtime(pytesseract)
        warnings: list[str] = []
        try:
            tess_version = _version(pytesseract)
        except Exception as exc:
            native = NativeTextFallbackEngine().run(pages, language=language)
            native.engine = self.name
            native.version = "local-hybrid-ocr:native-only"
            native.warnings.append(f"Tesseract non disponibile per pagine scansionate: {exc}")
            return native
        lang = _resolve_tesseract_language(pytesseract, language, tess_config)
        tokens: list[dict] = []
        page_texts: list[str] = []
        offset = 0
        native_count = 0
        ocr_count = 0
        for page in pages:
            native_text = str(page.text_hint or "")
            if _native_text_is_good(native_text):
                native_count += 1
                page_text = native_text
                _append_text_tokens(tokens, page_text, page=page.page, offset=offset, confidence=0.96, line_id=f"p{page.page}-native")
                page_texts.append(page_text)
                offset += len(page_text) + 1
                continue
            ocr_count += 1
            candidate = _read_tesseract_page_best(
                pytesseract,
                Output,
                page,
                lang=lang,
                base_config=tess_config,
                offset=offset,
                line_prefix="hybrid",
            )
            if candidate["warnings"]:
                warnings.extend(candidate["warnings"])
            page_text = str(candidate["text"] or native_text)
            tokens.extend(candidate["tokens"])
            if not candidate["tokens"]:
                warnings.append(f"Pagina {page.page}: OCR locale eseguito senza testo leggibile.")
            page_texts.append(page_text)
            offset += len(page_text) + 1
        if not any(text.strip() for text in page_texts):
            warnings.append("Fallback ibrido locale eseguito ma senza testo leggibile.")
        return EngineRun(
            self.name,
            f"local-hybrid-ocr:native={native_count} tesseract={ocr_count} {tess_version}",
            tokens,
            "\n".join(page_texts).strip(),
            page_texts,
            language,
            0.95 if tokens else 0.0,
            warnings=warnings,
        )


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
    if clean in {"local-hybrid-ocr", "hybrid-local-ocr", "native-tesseract", "ocr-fallback"}:
        return HybridLocalOcrEngine()
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
        raise


def _configure_tesseract_runtime(pytesseract: object) -> str:
    command = _resolve_tesseract_command()
    pytesseract_module = getattr(pytesseract, "pytesseract", None)
    if command and pytesseract_module is not None and hasattr(pytesseract_module, "tesseract_cmd"):
        pytesseract_module.tesseract_cmd = command
    tessdata_dir = _resolve_tessdata_dir(command)
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
    return ""


def _resolve_tesseract_command() -> str:
    configured = os.environ.get("IUSENTRA_TESSERACT_CMD", "").strip()
    if configured and Path(configured).is_file():
        return configured
    discovered = which("tesseract")
    if discovered:
        return discovered
    for root in (
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        os.environ.get("LOCALAPPDATA", ""),
    ):
        if not root:
            continue
        candidate = Path(root) / "Tesseract-OCR" / "tesseract.exe"
        if candidate.is_file():
            return str(candidate)
    return ""


def _resolve_tessdata_dir(command: str) -> str:
    candidates: list[Path] = []
    for name in ("IUSENTRA_TESSDATA_PREFIX", "TESSDATA_PREFIX"):
        configured = os.environ.get(name, "").strip().strip('"')
        if configured:
            candidates.append(Path(configured))
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        candidates.append(Path(local_app_data) / "IUSENTRA" / "tessdata")
    if command:
        candidates.append(Path(command).resolve().parent / "tessdata")
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob("*.traineddata")):
            return str(candidate)
    return ""


def _resolve_tesseract_language(pytesseract: object, preferred: str, config: str) -> str:
    clean = str(preferred or "ita").strip() or "ita"
    get_languages = getattr(pytesseract, "get_languages", None)
    if not callable(get_languages):
        return clean
    try:
        languages = set(get_languages(config=config))
    except TypeError:
        languages = set(get_languages())
    except Exception:
        return clean
    if clean in languages:
        return clean
    if clean.startswith("it") and "ita" in languages:
        return "ita"
    if "eng" in languages:
        return "eng"
    return next(iter(sorted(languages)), clean)


def _native_text_is_good(text: str) -> bool:
    normalized = str(text or "").strip()
    if len(normalized) < 120:
        return False
    cid_ratio = normalized.count("(cid:") / max(1, len(normalized))
    alpha_ratio = sum(1 for char in normalized if char.isalpha()) / max(1, len(normalized))
    return cid_ratio == 0 and alpha_ratio >= 0.35


def _append_text_tokens(tokens: list[dict], text: str, *, page: int, offset: int, confidence: float, line_id: str) -> None:
    for match in re.finditer(r"\S+", text):
        token = match.group(0)
        tokens.append(
            {
                "token": token,
                "start": offset + match.start(),
                "end": offset + match.end(),
                "confidence": confidence,
                "bbox": [0, 0, max(1, len(token) * 8), 12],
                "line_id": line_id,
                "page": page,
            }
        )


def _read_tesseract_page_best(
    pytesseract: object,
    output_type: object,
    page: PageArtifact,
    *,
    lang: str,
    base_config: str,
    offset: int,
    line_prefix: str,
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    warnings: list[str] = []
    for config_name, config in _tesseract_config_variants(base_config):
        try:
            data = pytesseract.image_to_data(page.image_path, lang=lang, config=config, output_type=output_type.DICT)
        except TypeError:
            data = pytesseract.image_to_data(page.image_path, lang=lang, output_type=output_type.DICT)
        except Exception as exc:
            warnings.append(f"Pagina {page.page}: Tesseract {config_name} non completato ({exc}).")
            continue
        candidate = _candidate_from_tesseract_data(
            data,
            page=page.page,
            offset=offset,
            line_id=f"p{page.page}-{line_prefix}-{config_name}",
        )
        candidate["config"] = config_name
        candidate["score"] = _score_ocr_text(str(candidate.get("text") or ""), candidate.get("avg_confidence", 0.0))
        candidates.append(candidate)
    if not candidates:
        return {"text": "", "tokens": [], "warnings": warnings}
    best = max(candidates, key=lambda item: float(item.get("score") or 0.0))
    if not best.get("tokens"):
        warnings.append(f"Pagina {page.page}: nessuna configurazione Tesseract ha prodotto token.")
    return {"text": best.get("text") or "", "tokens": best.get("tokens") or [], "warnings": warnings}


def _tesseract_config_variants(base_config: str) -> list[tuple[str, str]]:
    prefix = (base_config.strip() + " ") if base_config.strip() else ""
    return [
        ("psm6", prefix + "--oem 1 --psm 6 -c preserve_interword_spaces=1"),
        ("psm4", prefix + "--oem 1 --psm 4 -c preserve_interword_spaces=1"),
        ("psm3", prefix + "--oem 1 --psm 3 -c preserve_interword_spaces=1"),
        ("psm11", prefix + "--oem 1 --psm 11 -c preserve_interword_spaces=1"),
    ]


def _candidate_from_tesseract_data(data: dict, *, page: int, offset: int, line_id: str) -> dict[str, object]:
    tokens: list[dict] = []
    words: list[str] = []
    confidences: list[float] = []
    texts = list(data.get("text") or [])
    for index, raw in enumerate(texts):
        token = str(raw or "").strip()
        if not token:
            continue
        try:
            conf = max(0.0, min(1.0, float(data.get("conf", ["-1"])[index]) / 100.0))
        except (TypeError, ValueError):
            conf = 0.0
        start = offset + len(" ".join(words)) + (1 if words else 0)
        words.append(token)
        confidences.append(conf)
        tokens.append(
            {
                "token": token,
                "start": start,
                "end": start + len(token),
                "confidence": conf,
                "bbox": [
                    int(data.get("left", [0])[index]),
                    int(data.get("top", [0])[index]),
                    int(data.get("width", [0])[index]),
                    int(data.get("height", [0])[index]),
                ],
                "line_id": f"{line_id}-{data.get('line_num', [0])[index]}",
                "page": page,
            }
        )
    text = " ".join(words)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return {"text": text, "tokens": tokens, "avg_confidence": avg_confidence}


def _score_ocr_text(text: str, avg_confidence: object) -> float:
    normalized = str(text or "")
    lower = normalized.lower()
    score = min(len(normalized), 2500) / 120.0
    try:
        score += float(avg_confidence or 0.0) * 25.0
    except (TypeError, ValueError):
        pass
    weighted_patterns = [
        (r"\btribunale\s+di\s+[a-zàèéìòù' ]+", 8),
        (r"\b(proc\.?\s*n\.?|r\.?\s*g\.?|rgac)\s*[\w./-]+", 14),
        (r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", 12),
        (r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", 14),
        (r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b", 8),
        (r"\b(?:euro|€)\s*\d", 8),
        (r"\b(?:art\.?|dpr|c\.p\.c\.|c\.c\.)\b", 8),
    ]
    for pattern, weight in weighted_patterns:
        score += len(re.findall(pattern, normalized, flags=re.IGNORECASE)) * weight
    score -= len(re.findall(r"[|~{}_\[\]]", normalized)) * 0.75
    score -= len(re.findall(r"\b[bcdfghjklmnpqrstvwxyz]{7,}\b", lower)) * 0.5
    return score
