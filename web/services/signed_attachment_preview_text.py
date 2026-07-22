"""Renderer testuali e MIME per il lettore documenti interno."""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from html import escape
from html.parser import HTMLParser
from xml.dom import minidom

from web.services.signed_attachment_preview import (
    AttachmentPreviewPayload,
    _decode_text,
    _preview_shell,
    _textual_unavailable,
)


MAX_TEXT_PREVIEW_SOURCE_BYTES = 8 * 1024 * 1024
MAX_TEXT_PREVIEW_CHARACTERS = 1_000_000
MAX_MIME_SOURCE_BYTES = 32 * 1024 * 1024
MAX_MIME_PARTS = 256
MAX_MIME_BODY_BYTES = 2 * 1024 * 1024
MAX_MIME_ATTACHMENTS = 128
MAX_MIME_HEADER_CHARACTERS = 4_096


def _bounded_text(
    data: bytes,
    *,
    maximum_bytes: int = MAX_TEXT_PREVIEW_SOURCE_BYTES,
) -> tuple[str, bool]:
    truncated = len(data) > maximum_bytes
    text = _decode_text(data[:maximum_bytes])
    if len(text) > MAX_TEXT_PREVIEW_CHARACTERS:
        text = text[:MAX_TEXT_PREVIEW_CHARACTERS]
        truncated = True
    return text, truncated


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "head", "meta", "link"}:
            self.skip_depth += 1
        if tag.lower() in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "head", "meta", "link"} and self.skip_depth:
            self.skip_depth -= 1
        if tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(part.strip() for part in self.parts if part.strip())


def _strip_html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        return parser.text()
    except Exception:
        return ""


def _paragraphs_from_text(text: str) -> str:
    blocks = []
    current: list[str] = []
    for line in str(text or "").splitlines():
        if line.strip():
            current.append(escape(line))
            continue
        if current:
            blocks.append("<p>" + "<br>".join(current) + "</p>")
            current = []
    if current:
        blocks.append("<p>" + "<br>".join(current) + "</p>")
    return "\n".join(blocks) if blocks else "<p><em>Documento senza testo leggibile.</em></p>"


def _format_xml_text(data: bytes) -> str:
    text, _truncated = _bounded_text(data)
    text = text.strip()
    if not text:
        return ""
    try:
        parsed = minidom.parseString(text.encode("utf-8"))
        return parsed.toprettyxml(indent="  ")
    except Exception:
        return text


def render_xml_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    if len(data) > MAX_TEXT_PREVIEW_SOURCE_BYTES:
        return _textual_unavailable(
            nome_file=nome_file,
            data=data,
            mimetype="application/xml",
            signed=signed,
            reason=(
                "Il documento XML supera il limite previsto per l'anteprima interna. "
                "Scarica l'originale per verificarlo."
            ),
        )
    xml_text = _format_xml_text(data)
    subtitle = "Documento XML firmato" if signed else "Documento XML"
    body = (
        f'<p class="muted">{"Contenuto estratto dal file firmato e mostrato in sola lettura." if signed else "Contenuto XML mostrato in sola lettura."}</p>'
        f"<pre>{escape(xml_text) if xml_text else 'Documento XML vuoto.'}</pre>"
    )
    return AttachmentPreviewPayload(
        data=_preview_shell(title=nome_file, subtitle=subtitle, body=body),
        mimetype="text/html; charset=utf-8",
        download_name=nome_file,
        extracted_from_signature=signed,
    )


def render_text_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    text, truncated = _bounded_text(data)
    subtitle = "Documento di testo firmato" if signed else "Documento di testo"
    note = (
        '<p class="muted">Il testo è stato abbreviato per mantenere rapido il lettore. '
        "Scarica l'originale per consultarlo integralmente.</p>"
        if truncated
        else ""
    )
    return AttachmentPreviewPayload(
        data=_preview_shell(
            title=nome_file,
            subtitle=subtitle,
            body=f'{note}<article class="body">{_paragraphs_from_text(text)}</article>',
        ),
        mimetype="text/html; charset=utf-8",
        download_name=nome_file,
        extracted_from_signature=signed,
    )


def render_html_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    source, truncated = _bounded_text(data)
    text = _strip_html_to_text(source)
    subtitle = "Documento HTML firmato" if signed else "Documento HTML"
    note = (
        '<p class="muted">Il testo è stato abbreviato per mantenere rapido il lettore. '
        "Scarica l'originale per consultarlo integralmente.</p>"
        if truncated
        else ""
    )
    return AttachmentPreviewPayload(
        data=_preview_shell(
            title=nome_file,
            subtitle=subtitle,
            body=f'{note}<article class="body">{_paragraphs_from_text(text)}</article>',
        ),
        mimetype="text/html; charset=utf-8",
        download_name=nome_file,
        extracted_from_signature=signed,
    )


def render_eml_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    if len(data) > MAX_MIME_SOURCE_BYTES:
        return _textual_unavailable(
            nome_file=nome_file,
            data=data,
            mimetype="message/rfc822",
            signed=signed,
            reason=(
                "Il messaggio MIME supera il limite previsto per l'anteprima interna. "
                "Scarica l'originale per verificarlo."
            ),
        )
    if data.count(b"\n--") > MAX_MIME_PARTS * 2:
        return _textual_unavailable(
            nome_file=nome_file,
            data=data,
            mimetype="message/rfc822",
            signed=signed,
            reason=(
                "Il messaggio MIME contiene troppe parti per un'anteprima sicura. "
                "Scarica l'originale per verificarlo."
            ),
        )
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
    except Exception:
        return render_text_preview(nome_file, data, signed=signed)

    headers: list[tuple[str, str]] = []
    for key, label in (
        ("Subject", "Oggetto"),
        ("From", "Mittente"),
        ("To", "Destinatari"),
        ("Cc", "Cc"),
        ("Date", "Data"),
        ("Message-ID", "Message-ID"),
    ):
        value = str(message.get(key, "") or "").strip()[:MAX_MIME_HEADER_CHARACTERS]
        if value:
            headers.append((label, value))

    plain_parts: list[str] = []
    attachments: list[tuple[str, str, int]] = []
    body_bytes = 0
    preview_truncated = False
    try:
        for part_index, part in enumerate(message.walk()):
            if part_index >= MAX_MIME_PARTS:
                preview_truncated = True
                break
            if part.is_multipart():
                continue
            filename = str(part.get_filename() or "").strip()
            disposition = str(part.get_content_disposition() or "").lower()
            content_type = str(part.get_content_type() or "application/octet-stream").lower()
            payload = part.get_payload(decode=True) or b""
            if filename or disposition == "attachment":
                if len(attachments) < MAX_MIME_ATTACHMENTS:
                    attachments.append((filename or "allegato", content_type, len(payload)))
                else:
                    preview_truncated = True
                continue
            remaining_body_bytes = max(0, MAX_MIME_BODY_BYTES - body_bytes)
            if remaining_body_bytes <= 0:
                preview_truncated = True
                continue
            bounded_payload = payload[:remaining_body_bytes]
            body_bytes += len(bounded_payload)
            if len(payload) > len(bounded_payload):
                preview_truncated = True
            if content_type == "text/plain":
                text = _decode_text(bounded_payload).strip()
                if text:
                    plain_parts.append(text)
            elif content_type == "text/html":
                text = _strip_html_to_text(_decode_text(bounded_payload))
                if text.strip():
                    plain_parts.append(text.strip())
    except Exception:
        return _textual_unavailable(
            nome_file=nome_file,
            data=data,
            mimetype="message/rfc822",
            signed=signed,
            reason=(
                "Il messaggio MIME non può essere preparato in modo sicuro per l'anteprima. "
                "Scarica l'originale per verificarlo."
            ),
        )

    header_html = ""
    if headers:
        header_html = "<dl>" + "".join(
            f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in headers
        ) + "</dl>"
    body_text = "\n\n".join(plain_parts).strip()
    body_html = (
        _paragraphs_from_text(body_text)
        if body_text
        else "<p><em>Il messaggio non contiene un corpo testuale leggibile.</em></p>"
    )
    attachments_html = ""
    if attachments:
        rows = "".join(
            f'<li>{escape(name)} <span class="muted">{escape(mime)}, {size} byte</span></li>'
            for name, mime, size in attachments
        )
        attachments_html = f"<h2>Allegati indicati nel messaggio</h2><ul>{rows}</ul>"
    truncation_html = (
        '<p class="muted">L’anteprima è stata abbreviata per mantenere rapido il lettore. '
        "Scarica l'originale per consultare tutte le parti del messaggio.</p>"
        if preview_truncated
        else ""
    )

    subtitle = "Email PEC / EML firmata" if signed else "Email PEC / EML"
    return AttachmentPreviewPayload(
        data=_preview_shell(
            title=nome_file,
            subtitle=subtitle,
            body=(
                f'{truncation_html}{header_html}<h2>Corpo del messaggio</h2>'
                f'<article class="body">{body_html}</article>{attachments_html}'
            ),
        ),
        mimetype="text/html; charset=utf-8",
        download_name=nome_file,
        extracted_from_signature=signed,
    )


__all__ = [
    "render_eml_preview",
    "render_html_preview",
    "render_text_preview",
    "render_xml_preview",
]
