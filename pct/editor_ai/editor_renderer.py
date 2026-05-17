"""Rendering e lettura del documento reale dell'editor IUSENTRA."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Callable

from pct.editor import documento_to_html
from pct.fascicoli import TipoDocumento

from .models import AttoDraftPlan
from .validators import EditorAIValidationError, clean_text


_UNSAFE_TAG_RE = re.compile(r"<\s*(script|style|iframe|object|embed|link|meta)\b.*?</\s*\1\s*>", re.IGNORECASE | re.DOTALL)
_UNSAFE_SINGLE_RE = re.compile(r"<\s*(script|style|iframe|object|embed|link|meta)\b[^>]*>", re.IGNORECASE)
_EVENT_ATTR_RE = re.compile(r"\s+on[a-zA-Z]+\s*=\s*(['\"]).*?\1", re.IGNORECASE | re.DOTALL)
_JS_ATTR_RE = re.compile(r"(href|src)\s*=\s*(['\"])\s*javascript:[^'\"]*\2", re.IGNORECASE)


def sanitize_editor_html(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return "<p></p>"
    clean = _UNSAFE_TAG_RE.sub("", clean)
    clean = _UNSAFE_SINGLE_RE.sub("", clean)
    clean = _EVENT_ATTR_RE.sub("", clean)
    clean = _JS_ATTR_RE.sub(r'\1=""', clean)
    return clean or "<p></p>"


def text_to_editor_html(value: str) -> str:
    lines = str(value or "").replace("\r\n", "\n").split("\n")
    blocks: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            blocks.append(f"<h3>{html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            blocks.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            blocks.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        else:
            blocks.append(f"<p>{html.escape(stripped)}</p>")
    return "\n".join(blocks) or "<p></p>"


def legal_markdown_to_editor_html(value: str) -> str:
    """Converte una bozza Markdown di Lex in HTML governato dall'editor."""

    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return "<p></p>"
    if _looks_like_html(raw):
        return sanitize_editor_html(raw)

    blocks: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    list_items: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        body = "<br>".join(_inline_markdown_to_editor_html(line) for line in paragraph)
        blocks.append(f"<p>{body}</p>")
        paragraph.clear()

    def flush_list() -> None:
        nonlocal list_type
        if not list_type or not list_items:
            list_type = None
            list_items.clear()
            return
        tag = "ol" if list_type == "ol" else "ul"
        blocks.append(f"<{tag}>" + "".join(f"<li>{item}</li>" for item in list_items) + f"</{tag}>")
        list_type = None
        list_items.clear()

    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if stripped == "---":
            flush_paragraph()
            flush_list()
            blocks.append("<hr>")
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if numbered or bullet:
            flush_paragraph()
            target_type = "ol" if numbered else "ul"
            if list_type and list_type != target_type:
                flush_list()
            list_type = target_type
            list_items.append(_inline_markdown_to_editor_html((numbered or bullet).group(1)))
            continue

        flush_list()

        if stripped.startswith("### "):
            flush_paragraph()
            blocks.append(f"<h3>{_inline_markdown_to_editor_html(stripped[4:])}</h3>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            blocks.append(f"<h2>{_inline_markdown_to_editor_html(stripped[3:])}</h2>")
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            blocks.append(f"<h1>{_inline_markdown_to_editor_html(stripped[2:])}</h1>")
            continue

        bold_only = re.match(r"^\*\*([^*]+)\*\*$", stripped)
        if bold_only:
            flush_paragraph()
            heading = _inline_markdown_to_editor_html(bold_only.group(1))
            tag = "h1" if not any(block.startswith("<h1>") for block in blocks) else "h2"
            blocks.append(f"<{tag}>{heading}</{tag}>")
            continue

        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    return sanitize_editor_html("\n".join(blocks) or "<p></p>")


def _inline_markdown_to_editor_html(value: str) -> str:
    clean = html.escape(str(value or "").strip())
    clean = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", clean)
    clean = re.sub(r"`([^`]+)`", r"<code>\1</code>", clean)
    return clean


def _looks_like_html(content: str) -> bool:
    lowered = (content or "").strip().lower()
    return any(
        tag in lowered
        for tag in ("<p", "<div", "<h1", "<h2", "<h3", "<ul", "<ol", "<li", "<table", "<blockquote", "<br", "<hr")
    )


def ensure_editor_html(content: str, plan: AttoDraftPlan) -> str:
    raw = str(content or "").strip()
    if not raw:
        raw = _fallback_html_from_plan(plan)
    if "<" not in raw or ">" not in raw:
        raw = text_to_editor_html(raw)
    return sanitize_editor_html(raw)


def _fallback_html_from_plan(plan: AttoDraftPlan) -> str:
    parts = [f"<h1>{html.escape(plan.title)}</h1>"]
    for section in plan.sections:
        tag = f"h{max(1, min(section.level + 1, 4))}"
        parts.append(f"<{tag}>{html.escape(section.heading)}</{tag}>")
        parts.append(
            "<p>[DATO DA COMPLETARE: contenuto della sezione da verificare con i documenti del fascicolo.]</p>"
        )
    return "\n".join(parts)


def build_editor_snapshot(*, document_id: str, filename: str, html_content: str, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "editor_document_id": clean_text(document_id),
        "filename": clean_text(filename),
        "html": sanitize_editor_html(html_content),
        "warnings": list(warnings or []),
    }


def create_editor_document(
    *,
    fascicoli_repository: Any,
    fascicolo_id: str,
    title: str,
    html_content: str,
    created_by: str,
    encrypt: Callable[[bytes], bytes] | None = None,
) -> dict[str, Any]:
    if fascicoli_repository is None:
        raise EditorAIValidationError("Repository fascicoli non disponibile.")
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_text(title).lower()).strip("._-") or "atto_lex"
    filename = f"{safe_title[:80]}.html"
    raw = sanitize_editor_html(html_content).encode("utf-8")
    content = encrypt(raw) if callable(encrypt) else raw
    document = fascicoli_repository.aggiungi_documento(
        fascicolo_id,
        filename,
        TipoDocumento.ATTO_GIUDIZIARIO,
        content,
        note="Bozza creata con Lex nell'editor professionale",
        tags=["lex", "atto-ai", "bozza"],
        caricato_da=created_by,
        fonte_documento="EDITOR_AI_LEX",
        nome_originale=filename,
    )
    return {
        "document_id": document.id,
        "filename": document.nome,
        "open_url": f"/fascicoli/{fascicolo_id}/documenti/{document.id}/editor",
        "snapshot": build_editor_snapshot(document_id=document.id, filename=document.nome, html_content=html_content),
    }


def read_editor_document_for_lex(
    *,
    fascicoli_repository: Any,
    fascicolo_id: str,
    editor_document_id: str,
    decrypt: Callable[[bytes], bytes] | None = None,
) -> dict[str, Any]:
    if fascicoli_repository is None:
        raise EditorAIValidationError("Repository fascicoli non disponibile.")
    fascicolo = fascicoli_repository.get(fascicolo_id)
    if not fascicolo:
        raise EditorAIValidationError("Fascicolo non trovato.")
    document = next((doc for doc in getattr(fascicolo, "documenti", []) or [] if clean_text(getattr(doc, "id", "")) == editor_document_id), None)
    if not document:
        raise EditorAIValidationError("Documento editor non trovato.")
    path = fascicoli_repository.percorso_documento(fascicolo_id, editor_document_id)
    raw = Path(path).read_bytes()
    if callable(decrypt):
        raw = decrypt(raw)
    html_content, warnings, meta = documento_to_html(raw, getattr(document, "nome", "documento.html"))
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = clean_text(html.unescape(text))
    return {
        "editor_document_id": editor_document_id,
        "filename": getattr(document, "nome", ""),
        "html": sanitize_editor_html(html_content),
        "text": text,
        "warnings": list(warnings),
        "meta": dict(meta or {}),
    }
