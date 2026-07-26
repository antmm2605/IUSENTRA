from __future__ import annotations

import base64
import io
import json
import mimetypes
import re
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    import mammoth
except Exception:  # pragma: no cover - dipendenza opzionale in alcuni ambienti
    mammoth = None

try:
    import pdfplumber
except Exception:  # pragma: no cover - dipendenza opzionale in alcuni ambienti
    pdfplumber = None


MAX_ATTACHMENTS = 4
MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024
MAX_EXCERPT_CHARS = 6000
MAX_PROMPT_CHARS = 18000

_TEXT_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "text/html",
    "application/xhtml+xml",
}


def _normalize_text(value: str) -> str:
    text = str(value or "").replace("\r", "").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class _PlainTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self.parts.append(data)


def _strip_html(value: str) -> str:
    parser = _PlainTextHTMLParser()
    try:
        parser.feed(str(value or ""))
        parser.close()
        return _normalize_text(" ".join(parser.parts))
    except Exception:
        return _normalize_text(str(value or ""))


def _guess_mime_type(name: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    if Path(name).suffix.lower() == ".md":
        return "text/markdown"
    if Path(name).suffix.lower() == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    guessed, _ = mimetypes.guess_type(name)
    return guessed or "application/octet-stream"


def _decode_base64(value: str) -> bytes:
    raw = str(value or "")
    if "," in raw and raw.lstrip().lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def _extract_pdf_text(data: bytes) -> tuple[str, int]:
    if pdfplumber is None:
        raise ValueError("pdfplumber non disponibile per leggere PDF locali.")

    page_texts: list[str] = []
    page_count = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = _normalize_text(page.extract_text() or "")
            if text:
                page_texts.append(text)
    if not page_texts:
        raise ValueError("PDF senza testo estraibile. Per i PDF immagine usa il flusso OCR del gestionale.")
    return "\n\n".join(page_texts), page_count


def _extract_docx_text(data: bytes) -> str:
    if mammoth is None:
        raise ValueError("mammoth non disponibile per leggere DOCX locali.")
    result = mammoth.extract_raw_text(io.BytesIO(data))
    text = _normalize_text(result.value or "")
    if not text:
        raise ValueError("DOCX senza testo estraibile.")
    return text


def _extract_text(name: str, mime_type: str, data: bytes) -> tuple[str, int | None]:
    if mime_type in {"text/plain", "text/markdown", "text/csv"}:
        return _normalize_text(data.decode("utf-8", errors="replace")), 1
    if mime_type == "application/json":
        raw = data.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            return _normalize_text(json.dumps(parsed, ensure_ascii=False, indent=2)), 1
        except Exception:
            return _normalize_text(raw), 1
    if mime_type in {"text/html", "application/xhtml+xml"}:
        return _strip_html(data.decode("utf-8", errors="replace")), 1
    if mime_type == "application/pdf":
        return _extract_pdf_text(data)
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(data), 1
    raise ValueError(f"Formato non supportato per Lex: {mime_type or Path(name).suffix.lower() or 'sconosciuto'}")


def parse_attachment_payloads(payloads: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    attachments: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for raw in list(payloads or [])[:MAX_ATTACHMENTS]:
        name = str(raw.get("name") or "documento").strip() or "documento"
        mime_type = _guess_mime_type(name, str(raw.get("mime_type") or raw.get("type") or "").strip() or None)
        try:
            data = _decode_base64(str(raw.get("content_base64") or ""))
            if not data:
                raise ValueError("Contenuto vuoto.")
            if len(data) > MAX_ATTACHMENT_BYTES:
                raise ValueError("Documento troppo grande per Lex. Limite 12 MB per file.")
            extracted_text, page_count = _extract_text(name, mime_type, data)
            if not extracted_text:
                raise ValueError("Documento senza testo utile.")
            excerpt = extracted_text[:MAX_EXCERPT_CHARS].strip()
            attachments.append(
                {
                    "id": uuid.uuid4().hex,
                    "name": name,
                    "mime_type": mime_type,
                    "size_bytes": len(data),
                    "page_count": page_count,
                    "text_excerpt": excerpt,
                    "text_chars": len(extracted_text),
                    "truncated": len(extracted_text) > len(excerpt),
                }
            )
        except Exception as exc:
            errors.append({"name": name, "error": str(exc)})
    return attachments, errors


def build_attachment_prompt_block(attachments: list[dict[str, Any]] | None) -> str:
    valid = [item for item in list(attachments or []) if str(item.get("text_excerpt") or "").strip()]
    if not valid:
        return ""

    lines = [
        "",
        "═══ DOCUMENTI CARICATI DALL'UTENTE ═══",
        "Usa i documenti seguenti come contesto operativo aggiuntivo, senza ignorare il fascicolo o la conversazione corrente.",
    ]
    consumed = 0
    for index, item in enumerate(valid[:MAX_ATTACHMENTS], start=1):
        excerpt = str(item.get("text_excerpt") or "").strip()
        remaining = MAX_PROMPT_CHARS - consumed
        if remaining <= 0:
            break
        snippet = excerpt[:remaining].strip()
        consumed += len(snippet)
        meta = [
            f"Documento {index}: {item.get('name') or 'Documento'}",
            f"tipo {item.get('mime_type') or 'n.d.'}",
        ]
        if item.get("page_count"):
            meta.append(f"pagine {item['page_count']}")
        lines.append(f"[{' · '.join(meta)}]")
        lines.append(snippet)
        if item.get("truncated"):
            lines.append("(Estratto abbreviato per mantenere la risposta rapida.)")
        lines.append("")

    lines.append("═══ FINE DOCUMENTI CARICATI ═══")
    return "\n".join(part for part in lines if part is not None).strip()
