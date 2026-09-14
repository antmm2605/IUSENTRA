from __future__ import annotations

import os  # noqa: F401 - i test controllano la variabile TESSDATA_PREFIX tramite questo modulo
import re
from typing import Protocol

from .models import EngineRun, PageArtifact
from .motore import runtime as _runtime
from .motore.lettura import leggi_immagine as _leggi_immagine
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
    versione = _runtime.versione(pytesseract)
    if not versione:
        raise RuntimeError("Tesseract non disponibile")
    return versione


def _resolve_tesseract_command() -> str:
    return _runtime.comando_tesseract()


def _resolve_tessdata_dir(command: str) -> str:
    return _runtime.cartella_tessdata(command)


def _configure_tesseract_runtime(pytesseract: object) -> str:
    """Compatibilita': il runtime e' quello unico in `legal_ocr.motore.runtime`."""
    return _runtime.configura(pytesseract, comando=_resolve_tesseract_command())


def _resolve_tesseract_language(pytesseract: object, preferred: str, config: str) -> str:
    return _runtime.lingua_disponibile(pytesseract, preferred, config)


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
    """La pagina letta dal motore unico, nella forma dei token della pipeline probatoria."""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        return {"text": "", "tokens": [], "warnings": [f"Pagina {page.page}: Pillow non disponibile ({exc})."]}
    try:
        with Image.open(page.image_path) as immagine:
            lettura = _leggi_immagine(immagine.convert("L"), pytesseract=pytesseract, lingua=lang, con_pdf=False)
    except Exception as exc:
        return {"text": "", "tokens": [], "warnings": [f"Pagina {page.page}: Tesseract non completato ({exc})."]}
    warnings = [f"Pagina {page.page}: {avviso}" for avviso in lettura.avvisi]
    tokens: list[dict] = []
    words: list[str] = []
    for parola in lettura.parole:
        token = str(parola.get("text") or "")
        start = offset + len(" ".join(words)) + (1 if words else 0)
        words.append(token)
        tokens.append(
            {
                "token": token,
                "start": start,
                "end": start + len(token),
                "confidence": float(parola.get("conf") or 0.0),
                "bbox": [int(parola.get("left") or 0), int(parola.get("top") or 0), int(parola.get("width") or 0), int(parola.get("height") or 0)],
                "line_id": f"p{page.page}-{line_prefix}-{lettura.configurazione.replace(' ', '_')}-{parola.get('line', 0)}",
                "page": page.page,
            }
        )
    if not tokens:
        warnings.append(f"Pagina {page.page}: nessuna configurazione Tesseract ha prodotto token.")
    return {"text": " ".join(words), "tokens": tokens, "warnings": warnings}


def _score_ocr_text(text: str, avg_confidence: object) -> float:
    """Compatibilita': il punteggio di una lettura e' quello del motore unico."""
    from .motore.punteggio import bonus_forense

    normalized = str(text or "")
    score = min(len(normalized), 2500) / 120.0
    try:
        score += float(avg_confidence or 0.0) * 25.0
    except (TypeError, ValueError):
        pass
    return score + bonus_forense(normalized)
