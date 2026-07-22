"""Renderer Word e validazione OOXML per il lettore documenti interno."""

from __future__ import annotations

from html import escape
import io
from pathlib import PurePosixPath
from urllib.parse import urlsplit
import zipfile

from web.services.signed_attachment_preview import (
    AttachmentPreviewPayload,
    _preview_shell,
    _textual_unavailable,
    _zip_declared_directory,
    attachment_mimetype,
)
from web.services.signed_attachment_preview_text import _paragraphs_from_text, _strip_html_to_text


MAX_DOCX_EMBEDDED_IMAGE_BYTES = 8 * 1024 * 1024
MAX_OOXML_SOURCE_BYTES = 40 * 1024 * 1024
MAX_OOXML_FILES = 512
MAX_OOXML_MEMBER_BYTES = 20 * 1024 * 1024
MAX_OOXML_TOTAL_BYTES = 80 * 1024 * 1024
MAX_OOXML_CENTRAL_DIRECTORY_BYTES = 8 * 1024 * 1024
MAX_OOXML_COMPRESSION_RATIO = 250
MAX_DOCUMENT_HTML_CHARACTERS = 2_000_000

_DOC_HTML_ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
_DOC_HTML_DROP_CONTENT_TAGS = {
    "audio",
    "button",
    "canvas",
    "embed",
    "form",
    "iframe",
    "input",
    "math",
    "meta",
    "noscript",
    "object",
    "script",
    "select",
    "style",
    "svg",
    "template",
    "textarea",
    "video",
}
_DOC_HTML_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-")
_DOC_HTML_DATA_IMAGE_PREFIXES = (
    "data:image/gif;base64,",
    "data:image/jpeg;base64,",
    "data:image/jpg;base64,",
    "data:image/png;base64,",
    "data:image/webp;base64,",
)


def _safe_doc_fragment(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 128 or raw[0] not in _DOC_HTML_ID_CHARS:
        return ""
    return raw if all(char in _DOC_HTML_ID_CHARS for char in raw) else ""


def _safe_doc_href(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048 or any(ord(char) < 32 for char in raw):
        return ""
    if raw.startswith("#"):
        fragment = _safe_doc_fragment(raw[1:])
        return f"#{fragment}" if fragment else ""
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"https", "mailto", "tel"}:
        return ""
    return raw


def _safe_doc_image_src(value: object) -> str:
    raw = str(value or "").strip()
    lowered = raw.casefold()
    if not any(lowered.startswith(prefix) for prefix in _DOC_HTML_DATA_IMAGE_PREFIXES):
        return ""
    payload = raw.split(",", 1)[1] if "," in raw else ""
    compact_payload = "".join(payload.splitlines())
    if len(compact_payload) > (MAX_DOCX_EMBEDDED_IMAGE_BYTES * 4 // 3) + 8:
        return ""
    if not payload or any(
        char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\r\n"
        for char in payload
    ):
        return ""
    return raw


def _safe_doc_numeric_attr(value: object, *, maximum: int = 1000) -> str:
    raw = str(value or "").strip()
    if not raw.isdigit():
        return ""
    number = int(raw)
    return str(number) if 1 <= number <= maximum else ""


def _safe_doc_html(value: str) -> str:
    """Riduce l'HTML Mammoth a un allowlist statica priva di codice eseguibile."""

    source = str(value or "")
    try:
        from bs4 import BeautifulSoup, Comment  # type: ignore

        soup = BeautifulSoup(source, "html.parser")
        for comment in soup.find_all(string=lambda item: isinstance(item, Comment)):
            comment.extract()
        for tag in list(soup.find_all(list(_DOC_HTML_DROP_CONTENT_TAGS))):
            tag.decompose()
        for tag in list(soup.find_all(True)):
            name = str(getattr(tag, "name", "") or "").casefold()
            if name not in _DOC_HTML_ALLOWED_TAGS:
                tag.unwrap()
                continue

            safe_attrs: dict[str, str] = {}
            fragment = _safe_doc_fragment(tag.attrs.get("id"))
            if fragment:
                safe_attrs["id"] = fragment
            if name == "a":
                href = _safe_doc_href(tag.attrs.get("href"))
                if href:
                    safe_attrs["href"] = href
                    safe_attrs["rel"] = "nofollow noopener noreferrer"
                title = str(tag.attrs.get("title") or "").strip()[:500]
                if title:
                    safe_attrs["title"] = title
            elif name == "img":
                src = _safe_doc_image_src(tag.attrs.get("src"))
                if src:
                    safe_attrs["src"] = src
                alt = str(tag.attrs.get("alt") or "").strip()[:1000]
                if alt:
                    safe_attrs["alt"] = alt
                title = str(tag.attrs.get("title") or "").strip()[:500]
                if title:
                    safe_attrs["title"] = title
            elif name in {"td", "th"}:
                for attribute in ("colspan", "rowspan"):
                    numeric = _safe_doc_numeric_attr(tag.attrs.get(attribute), maximum=100)
                    if numeric:
                        safe_attrs[attribute] = numeric
            elif name == "ol":
                start = _safe_doc_numeric_attr(tag.attrs.get("start"), maximum=100000)
                if start:
                    safe_attrs["start"] = start
            tag.attrs = safe_attrs
        return "".join(str(child) for child in soup.contents).strip()
    except Exception:
        text = _strip_html_to_text(source)
        return _paragraphs_from_text(text) if text else ""


def _validate_ooxml_document(data: bytes) -> str:
    if len(data) > MAX_OOXML_SOURCE_BYTES:
        return "Il documento Word supera il limite previsto per l'anteprima interna."
    declared = _zip_declared_directory(data)
    if declared is None:
        return "Il documento Word non contiene una struttura OOXML valida."
    declared_entries, central_size, _central_offset = declared
    if declared_entries > MAX_OOXML_FILES:
        return "Il documento Word contiene troppi elementi per un'anteprima sicura."
    if central_size > MAX_OOXML_CENTRAL_DIRECTORY_BYTES:
        return "La struttura del documento Word supera il limite di sicurezza previsto."

    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_OOXML_FILES:
                return "Il documento Word contiene troppi elementi per un'anteprima sicura."
            total_size = 0
            names: set[str] = set()
            for info in members:
                member_name = str(info.filename or "").replace("\\", "/")
                member_path = PurePosixPath(member_name)
                if (
                    not member_name
                    or member_name.startswith("/")
                    or ".." in member_path.parts
                    or (member_path.parts and ":" in member_path.parts[0])
                ):
                    return "Il documento Word contiene un percorso interno non sicuro."
                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    return "Il documento Word contiene un collegamento interno non sicuro."
                if info.flag_bits & 0x1:
                    return "Il documento Word contiene elementi cifrati non visualizzabili."
                if info.file_size > MAX_OOXML_MEMBER_BYTES:
                    return "Un elemento del documento Word supera il limite di visualizzazione."
                total_size += info.file_size
                if total_size > MAX_OOXML_TOTAL_BYTES:
                    return "Il documento Word supera il limite complessivo di decompressione."
                if info.file_size and (
                    not info.compress_size
                    or info.file_size / info.compress_size > MAX_OOXML_COMPRESSION_RATIO
                ):
                    return "Il documento Word presenta una compressione anomala."
                names.add(member_name)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return "Il documento Word non contiene una struttura OOXML valida."

    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        return "Il file non contiene un documento Word OOXML leggibile."
    return ""


def render_docx_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    invalid_reason = _validate_ooxml_document(data)
    if invalid_reason:
        return _textual_unavailable(
            nome_file=nome_file,
            data=data,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            signed=signed,
            reason=f"{invalid_reason} Scarica l'originale per verificarlo.",
        )
    try:
        import mammoth  # type: ignore

        result = mammoth.convert_to_html(io.BytesIO(data))
        converted_html = str(getattr(result, "value", "") or "")
        if len(converted_html) > MAX_DOCUMENT_HTML_CHARACTERS:
            raise ValueError("Conversione Word oltre il limite previsto per l'anteprima.")
        html_body = _safe_doc_html(converted_html)
        messages = [
            str(getattr(message, "message", "") or "").strip()
            for message in getattr(result, "messages", []) or []
            if str(getattr(message, "message", "") or "").strip()
        ]
        notes = ""
        if messages:
            notes = (
                '<p class="muted">Note di conversione: '
                + escape("; ".join(messages[:3]))
                + ("…" if len(messages) > 3 else "")
                + "</p>"
            )
        if html_body:
            return AttachmentPreviewPayload(
                data=_preview_shell(
                    title=nome_file,
                    subtitle="Documento Word firmato" if signed else "Documento Word",
                    body=f'{notes}<article class="word-doc">{html_body}</article>',
                ),
                mimetype="text/html; charset=utf-8",
                download_name=nome_file,
                extracted_from_signature=signed,
            )
    except Exception:
        pass

    try:
        from pct.document_intelligence.extraction import extract_text_from_document

        result = extract_text_from_document(data, nome_file, "docx")
        if result.ok and result.text.strip():
            return AttachmentPreviewPayload(
                data=_preview_shell(
                    title=nome_file,
                    subtitle="Documento Word firmato" if signed else "Documento Word",
                    body=f'<article class="body">{_paragraphs_from_text(result.text)}</article>',
                ),
                mimetype="text/html; charset=utf-8",
                download_name=nome_file,
                extracted_from_signature=signed,
            )
    except Exception:
        pass

    return AttachmentPreviewPayload(
        data=data,
        mimetype=attachment_mimetype(nome_file),
        download_name=nome_file,
        extracted_from_signature=signed,
        unavailable_reason="Il documento Word non può essere convertito in anteprima interna su questo server.",
    )


def render_doc_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    try:
        from pct.document_intelligence.extraction import extract_text_from_document

        result = extract_text_from_document(data, nome_file, "doc")
        if result.ok and result.text.strip():
            return AttachmentPreviewPayload(
                data=_preview_shell(
                    title=nome_file,
                    subtitle="Documento Word 97-2003 firmato" if signed else "Documento Word 97-2003",
                    body=f'<article class="body">{_paragraphs_from_text(result.text)}</article>',
                ),
                mimetype="text/html; charset=utf-8",
                download_name=nome_file,
                extracted_from_signature=signed,
            )
    except Exception:
        pass
    return AttachmentPreviewPayload(
        data=data,
        mimetype=attachment_mimetype(nome_file),
        download_name=nome_file,
        extracted_from_signature=signed,
        unavailable_reason="Il documento DOC non può essere convertito in anteprima interna su questo server.",
    )


__all__ = ["render_doc_preview", "render_docx_preview"]
