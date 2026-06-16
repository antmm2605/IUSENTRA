"""Anteprima comune per allegati e documenti firmati CAdES."""

from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from html import escape
from html.parser import HTMLParser
import mimetypes
from xml.dom import minidom

from pct.firme_cades import (
    inner_signed_name,
    inspect_signed_document_bytes,
    is_p7m_filename,
    payload_mime_from_bytes,
)


INLINE_PREVIEW_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "text/plain",
    "text/html",
    "application/xml",
    "text/xml",
}

@dataclass(slots=True)
class AttachmentPreviewPayload:
    data: bytes
    mimetype: str
    download_name: str
    extracted_from_signature: bool = False
    unavailable_reason: str = ""


def attachment_mimetype(nome_file: str, mime_salvato: str = "") -> str:
    saved = str(mime_salvato or "").strip()
    guessed = mimetypes.guess_type(str(nome_file or ""))[0] or ""
    if saved in {"", "application/octet-stream", "binary/octet-stream"} and guessed:
        return guessed
    return saved or guessed or "application/octet-stream"


def is_inline_preview_mime(mimetype: str) -> bool:
    mime = str(mimetype or "").split(";", 1)[0].strip().lower()
    return mime in INLINE_PREVIEW_MIME_TYPES


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "iso-8859-1", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
        except LookupError:
            continue
    return data.decode("utf-8", errors="replace")


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


def _preview_shell(*, title: str, subtitle: str, body: str) -> bytes:
    html = (
        '<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>"
        ":root{color-scheme:light;--ink:#172033;--muted:#5d6b82;--line:#dfe6ef;--soft:#f6f8fb;--brand:#1458d4}"
        "*{box-sizing:border-box}body{margin:0;background:var(--soft);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif}"
        ".wrap{max-width:1040px;margin:24px auto;padding:0 18px}"
        ".head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}"
        ".eyebrow{font-size:12px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:var(--brand);margin-bottom:4px}"
        "h1{font-size:22px;line-height:1.25;margin:0 0 4px;font-weight:800}p{line-height:1.55}"
        ".subtitle{color:var(--muted);font-size:14px;margin:0}.card{background:#fefefe;border:1px solid var(--line);border-radius:8px;padding:22px;box-shadow:0 8px 22px rgba(23,50,77,.08)}"
        "dl{display:grid;grid-template-columns:minmax(120px,170px) 1fr;gap:8px 16px;margin:0 0 18px}"
        "dt{font-weight:700;color:#42526b}dd{margin:0;word-break:break-word}"
        "pre{margin:0;white-space:pre-wrap;word-break:break-word;font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace;color:#111827}"
        ".body p{margin:0 0 12px}.body p:last-child{margin-bottom:0}ul{margin:0;padding-left:20px}.muted{color:var(--muted);font-size:13px}"
        "@media(max-width:700px){.wrap{margin:12px auto;padding:0 12px}.card{padding:16px}dl{grid-template-columns:1fr;gap:4px}h1{font-size:19px}}"
        "</style></head><body><main class=\"wrap\">"
        '<header class="head"><div>'
        f'<div class="eyebrow">{escape(subtitle)}</div>'
        f"<h1>{escape(title)}</h1>"
        "</div></header>"
        f'<section class="card">{body}</section>'
        "</main></body></html>"
    )
    return html.encode("utf-8")


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
    text = _decode_text(data).strip()
    if not text:
        return ""
    try:
        parsed = minidom.parseString(text.encode("utf-8"))
        return parsed.toprettyxml(indent="  ")
    except Exception:
        return text


def _render_xml_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
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


def _render_text_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    text = _decode_text(data)
    subtitle = "Documento di testo firmato" if signed else "Documento di testo"
    return AttachmentPreviewPayload(
        data=_preview_shell(
            title=nome_file,
            subtitle=subtitle,
            body=f'<article class="body">{_paragraphs_from_text(text)}</article>',
        ),
        mimetype="text/html; charset=utf-8",
        download_name=nome_file,
        extracted_from_signature=signed,
    )


def _render_eml_preview(nome_file: str, data: bytes, *, signed: bool) -> AttachmentPreviewPayload:
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
    except Exception:
        return _render_text_preview(nome_file, data, signed=signed)

    headers: list[tuple[str, str]] = []
    for key, label in (
        ("Subject", "Oggetto"),
        ("From", "Mittente"),
        ("To", "Destinatari"),
        ("Cc", "Cc"),
        ("Date", "Data"),
        ("Message-ID", "Message-ID"),
    ):
        value = str(message.get(key, "") or "").strip()
        if value:
            headers.append((label, value))

    plain_parts: list[str] = []
    attachments: list[tuple[str, str, int]] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = str(part.get_filename() or "").strip()
        disposition = str(part.get_content_disposition() or "").lower()
        content_type = str(part.get_content_type() or "application/octet-stream").lower()
        payload = part.get_payload(decode=True) or b""
        if filename or disposition == "attachment":
            attachments.append((filename or "allegato", content_type, len(payload)))
            continue
        if content_type == "text/plain":
            try:
                content = part.get_content()
                if isinstance(content, str) and content.strip():
                    plain_parts.append(content.strip())
                    continue
            except Exception:
                pass
            text = _decode_text(payload).strip()
            if text:
                plain_parts.append(text)
        elif content_type == "text/html":
            html_text = _decode_text(payload)
            text = _strip_html_to_text(html_text)
            if text.strip():
                plain_parts.append(text.strip())

    header_html = ""
    if headers:
        header_html = "<dl>" + "".join(
            f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in headers
        ) + "</dl>"
    body_text = "\n\n".join(plain_parts).strip()
    body_html = _paragraphs_from_text(body_text) if body_text else "<p><em>Il messaggio non contiene un corpo testuale leggibile.</em></p>"
    attachments_html = ""
    if attachments:
        rows = "".join(
            f"<li>{escape(name)} <span class=\"muted\">{escape(mime)}, {size} byte</span></li>"
            for name, mime, size in attachments
        )
        attachments_html = f"<h2>Allegati indicati nel messaggio</h2><ul>{rows}</ul>"

    subtitle = "Email PEC / EML firmata" if signed else "Email PEC / EML"
    return AttachmentPreviewPayload(
        data=_preview_shell(
            title=nome_file,
            subtitle=subtitle,
            body=f"{header_html}<h2>Corpo del messaggio</h2><article class=\"body\">{body_html}</article>{attachments_html}",
        ),
        mimetype="text/html; charset=utf-8",
        download_name=nome_file,
        extracted_from_signature=signed,
    )


def _render_supported_textual_preview(
    *,
    nome_file: str,
    data: bytes,
    mimetype: str,
    signed: bool,
) -> AttachmentPreviewPayload | None:
    lower = str(nome_file or "").lower()
    mime = str(mimetype or "").split(";", 1)[0].strip().lower()
    sample = data.lstrip()[:80]
    if lower.endswith(".eml") or mime == "message/rfc822":
        return _render_eml_preview(nome_file, data, signed=signed)
    if lower.endswith(".xml") or mime in {"application/xml", "text/xml"} or sample.startswith((b"<?xml", b"<DatiAtto", b"<Segnatura")):
        return _render_xml_preview(nome_file, data, signed=signed)
    if lower.endswith(".txt") or mime == "text/plain":
        return _render_text_preview(nome_file, data, signed=signed)
    return None


def build_attachment_preview_payload(
    *,
    nome_file: str,
    data: bytes,
    mime_salvato: str = "",
) -> AttachmentPreviewPayload:
    """Prepara il contenuto da mostrare inline.

    Per un file .pdf.p7m l'originale resta invariato per il download, ma
    l'anteprima usa il PDF interno quando il contenitore CAdES lo espone.
    """

    original_name = str(nome_file or "").strip() or "allegato"
    original_mime = attachment_mimetype(original_name, mime_salvato)
    if not is_p7m_filename(original_name):
        textual = _render_supported_textual_preview(
            nome_file=original_name,
            data=data,
            mimetype=original_mime,
            signed=False,
        )
        if textual:
            return textual
        return AttachmentPreviewPayload(
            data=data,
            mimetype=original_mime,
            download_name=original_name,
        )

    signed = inspect_signed_document_bytes(
        source_name=original_name,
        source_path="",
        data=data,
    )
    if signed.status.payload_available and signed.payload_bytes:
        preview_name = signed.status.payload_name or inner_signed_name(original_name)
        preview_mime = signed.status.payload_mime or payload_mime_from_bytes(signed.payload_bytes, preview_name)
        textual = _render_supported_textual_preview(
            nome_file=preview_name,
            data=signed.payload_bytes,
            mimetype=preview_mime,
            signed=True,
        )
        if textual:
            return textual
        if is_inline_preview_mime(preview_mime):
            return AttachmentPreviewPayload(
                data=signed.payload_bytes,
                mimetype=preview_mime,
                download_name=preview_name,
                extracted_from_signature=True,
            )
        return AttachmentPreviewPayload(
            data=data,
            mimetype=original_mime,
            download_name=original_name,
            unavailable_reason=(
                "Il file firmato è stato letto, ma il contenuto interno non è "
                "un formato visualizzabile direttamente nel browser."
            ),
        )

    return AttachmentPreviewPayload(
        data=data,
        mimetype=original_mime,
        download_name=original_name,
        unavailable_reason=(
            "Il file firmato non espone un PDF interno leggibile. Scarica il .p7m "
            "originale e verificalo con il software di firma."
        ),
    )
