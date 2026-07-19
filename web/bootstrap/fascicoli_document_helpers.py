"""Shared helpers for fascicolo document bootstrap routes."""

from __future__ import annotations

import io
from collections.abc import Callable
from email import policy
from email.parser import BytesParser
from html import escape
from pathlib import Path
from typing import Any

from flask import current_app, redirect, request, send_file, url_for

from pct.fascicoli import TipoDocumento
from pct.fascicolo_document_catalog import catalog_tipo_documento_per_nome

PREVIEW_EXTENSIONS = (
    ".xml.p7m",
    ".eml.p7m",
    ".txt.p7m",
    ".pdf.p7m",
    ".xml",
    ".eml",
    ".txt",
    ".pdf",
    ".p7m",
)


def estrai_pdf_da_raw(data: bytes) -> bytes | None:
    idx = data.find(b"%PDF")
    if idx < 0:
        return None
    eof_idx = data.rfind(b"%%EOF")
    if eof_idx > idx:
        return data[idx : eof_idx + 5]
    return data[idx:]


def nome_documento_operativo(documento: Any, percorso: Path, data: bytes | None = None) -> str:
    """Mantiene il titolo leggibile e recupera l'estensione del file acquisito."""

    display_name = str(getattr(documento, "nome", "") or "").strip()
    candidates = (
        display_name,
        str(getattr(documento, "nome_originale", "") or "").strip(),
        str(getattr(documento, "nome_portale", "") or "").strip(),
        percorso.name,
    )
    for candidate in candidates:
        lower_candidate = candidate.casefold()
        for extension in PREVIEW_EXTENSIONS:
            if not lower_candidate.endswith(extension):
                continue
            if display_name.casefold().endswith(extension):
                return display_name
            return f"{display_name or Path(candidate).stem}{candidate[-len(extension):]}"

    if data:
        try:
            message = BytesParser(policy=policy.default).parsebytes(data, headersonly=True)
            is_eml = bool(message.get("subject")) and bool(message.get("from")) and bool(message.get("to"))
        except (TypeError, ValueError):
            is_eml = False
        if is_eml:
            return f"{display_name or percorso.name}.eml"
    return display_name or percorso.name


def redirect_to_documenti_section(id_fasc: str):
    section = str(request.form.get("next_section") or "sezione-documenti-fascicolo").strip().lstrip("#")
    if not section.startswith("sezione-"):
        section = "sezione-documenti-fascicolo"
    return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc) + f"#{section}")


def contenuto_portale_bytes(item: dict) -> bytes:
    raw = item.get("contenuto") or b""
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return b""


def percorso_documento_lettura(gestore_fascicoli: Any, id_fasc: str, id_doc: str) -> Path:
    resolver = getattr(gestore_fascicoli, "percorso_documento_lettura", None)
    if callable(resolver):
        return Path(resolver(id_fasc, id_doc))
    return Path(gestore_fascicoli.percorso_documento(id_fasc, id_doc))


def wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def preview_unavailable_html(nome_documento: str, scarica_url: str) -> tuple[str, int, dict[str, str]]:
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">'
        '</head><body class="bg-light d-flex align-items-center justify-content-center" style="min-height:100vh">'
        '<div class="text-center p-4">'
        '<i class="bi bi-file-earmark-lock2 text-secondary" style="font-size:3rem"></i>'
        f'<h6 class="mt-3 mb-2">{nome_documento}</h6>'
        '<p class="text-muted small mb-3">Anteprima non disponibile per questo formato.<br>'
        "Scarica il file per visualizzarlo con il programma appropriato.</p>"
        f'<a href="{scarica_url}" class="btn btn-primary btn-sm">'
        '<i class="bi bi-download me-1"></i>Scarica documento</a>'
        "</div></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def preview_eml_html(
    *,
    nome_documento: str,
    html_body: str,
    meta: dict[str, Any],
    scarica_url: str,
) -> tuple[str, int, dict[str, str]]:
    attachments = meta.get("allegati") if isinstance(meta, dict) else []
    count = len(attachments) if isinstance(attachments, list) else 0
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        "<style>"
        "body{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f7f8fb;color:#172033}"
        ".wrap{max-width:980px;margin:24px auto;padding:0 18px}"
        ".toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px}"
        ".toolbar a{background:#17324d;color:#fff;text-decoration:none;padding:9px 13px;border-radius:8px;font-size:14px}"
        ".card{background:#fff;border:1px solid #dde3ec;border-radius:8px;padding:22px;box-shadow:0 8px 22px rgba(23,50,77,.08)}"
        "h1{font-size:22px;margin:0 0 14px}h2{font-size:17px;margin:22px 0 10px}"
        "dl{display:grid;grid-template-columns:150px 1fr;gap:8px 14px;margin:0 0 18px}"
        "dt{font-weight:700;color:#42526b}dd{margin:0;word-break:break-word}"
        "p{line-height:1.55}.meta{color:#5d6b82;font-size:13px}"
        "ul{padding-left:22px}small{color:#667085}"
        "</style></head><body><main class=\"wrap\">"
        '<div class="toolbar">'
        f"<div><strong>{escape(nome_documento)}</strong><div class=\"meta\">Messaggio EML originale"
        f"{' - ' + str(count) + ' allegati' if count else ''}</div></div>"
        f'<a href="{escape(scarica_url, quote=True)}">Scarica EML</a>'
        "</div>"
        f'<section class="card">{html_body}</section>'
        "</main></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def preview_text_html(
    *,
    nome_documento: str,
    text: str,
    scarica_url: str,
) -> tuple[str, int, dict[str, str]]:
    paragraphs = []
    current: list[str] = []
    for line in str(text or "").splitlines():
        if line.strip():
            current.append(escape(line))
            continue
        if current:
            paragraphs.append("<p>" + "<br>".join(current) + "</p>")
            current = []
    if current:
        paragraphs.append("<p>" + "<br>".join(current) + "</p>")
    body = "\n".join(paragraphs) if paragraphs else "<p><em>Documento di testo vuoto.</em></p>"
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        "<style>"
        "body{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f7f8fb;color:#172033}"
        ".wrap{max-width:980px;margin:24px auto;padding:0 18px}"
        ".toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px}"
        ".toolbar a{background:#17324d;color:#fff;text-decoration:none;padding:9px 13px;border-radius:8px;font-size:14px}"
        ".card{background:#fff;border:1px solid #dde3ec;border-radius:8px;padding:22px;box-shadow:0 8px 22px rgba(23,50,77,.08)}"
        "h1{font-size:22px;margin:0 0 14px}.meta{color:#5d6b82;font-size:13px}p{line-height:1.55;white-space:normal}"
        "</style></head><body><main class=\"wrap\">"
        '<div class="toolbar">'
        f"<div><strong>{escape(nome_documento)}</strong><div class=\"meta\">Documento TXT leggibile nel fascicolo</div></div>"
        f'<a href="{escape(scarica_url, quote=True)}">Scarica TXT</a>'
        "</div>"
        f'<section class="card"><h1>Documento di testo</h1>{body}</section>'
        "</main></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def preview_error_html(scarica_url: str) -> tuple[str, int, dict[str, str]]:
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">'
        '</head><body class="bg-light d-flex align-items-center justify-content-center" style="min-height:100vh">'
        '<div class="text-center p-4">'
        '<i class="bi bi-exclamation-triangle text-warning" style="font-size:3rem"></i>'
        '<h6 class="mt-3 mb-2">Impossibile visualizzare il documento</h6>'
        '<p class="text-muted small mb-3">Si e verificato un errore durante il caricamento.<br>'
        "Scarica il file per visualizzarlo con il programma appropriato.</p>"
        f'<a href="{scarica_url}" class="btn btn-primary btn-sm">'
        '<i class="bi bi-download me-1"></i>Scarica documento</a>'
        "</div></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def pdf_page_count(data: bytes) -> int:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Motore anteprima PDF non disponibile.") from exc
    doc = None
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        return max(0, int(len(doc)))
    finally:
        if doc is not None:
            doc.close()


def render_pdf_page_png(data: bytes, page_number: int, *, scale: float = 1.85) -> bytes:
    if page_number < 1:
        raise ValueError("Pagina PDF non valida.")
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Motore anteprima PDF non disponibile.") from exc
    doc = None
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        if page_number > len(doc):
            raise ValueError("Pagina PDF fuori intervallo.")
        page = doc[page_number - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return bytes(pix.tobytes("png"))
    finally:
        if doc is not None:
            doc.close()


def pdf_mobile_preview_html(
    *,
    nome_documento: str,
    page_urls: list[str],
    scarica_url: str,
) -> tuple[str, int, dict[str, str]]:
    escaped_name = escape(nome_documento)
    escaped_download = escape(scarica_url, quote=True)
    viewer_script = escape(url_for("static", filename="js/mobile-pdf-viewer.js"), quote=True)
    if page_urls:
        pages = "".join(
            '<figure class="page">'
            f'<figcaption>Pagina {index}</figcaption>'
            f'<img src="{escape(url, quote=True)}" alt="Pagina {index} di {escaped_name}" '
            f'loading="{"eager" if index == 1 else "lazy"}" decoding="async"'
            f'{" fetchpriority=\"high\"" if index == 1 else ""}>'
            "</figure>"
            for index, url in enumerate(page_urls, start=1)
        )
    else:
        pages = (
            '<section class="empty">'
            "<strong>Anteprima non disponibile</strong>"
            "<span>Il documento non contiene pagine PDF leggibili.</span>"
            "</section>"
        )
    html = (
        '<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=5,user-scalable=yes,viewport-fit=cover">'
        f"<title>{escaped_name}</title>"
        "<style>"
        ":root{color-scheme:light}"
        "*{box-sizing:border-box}"
        "html,body{width:100%;height:100%;max-width:100%;overflow:hidden}"
        "body{margin:0;background:#e5e7eb;color:#111827;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}"
        ".reader{min-width:0;width:100%;height:100dvh;max-width:100vw;display:grid;grid-template-rows:auto minmax(0,1fr);overflow:hidden}"
        "header{z-index:2;min-width:0;display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px 10px;padding:8px 10px;border-bottom:1px solid #e2e8f0;background:#fff}"
        "header strong{min-width:0;font-size:13px;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        ".reader-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:6px}"
        ".reader-toolbar a,.reader-toolbar button{flex:0 0 auto;min-width:36px;min-height:36px;display:inline-flex;align-items:center;justify-content:center;border:1px solid #d7dde8;border-radius:8px;background:#fff;color:#0f172a;padding:0 9px;font:850 12px/1 Inter,system-ui,sans-serif;text-decoration:none;cursor:pointer}"
        ".reader-toolbar a{color:#1d4ed8}.reader-toolbar button:disabled{opacity:.42;cursor:not-allowed}"
        ".reader-toolbar a:focus-visible,.reader-toolbar button:focus-visible{outline:3px solid rgba(37,99,235,.24);outline-offset:1px;border-color:#2563eb}"
        ".reader-toolbar__zoom{min-width:54px;color:#334155;font-variant-numeric:tabular-nums;text-align:center}"
        ".pages{--zoom:1;min-width:0;width:100%;max-width:100%;display:grid;gap:12px;padding:12px;align-content:start;overflow:auto;overscroll-behavior:contain;touch-action:pan-x pan-y;scrollbar-gutter:stable}"
        ".page{width:calc(100% * var(--zoom));min-width:0;max-width:none;margin:0;display:grid;gap:6px;justify-self:start}"
        ".page figcaption{color:#475569;font-size:11px;font-weight:850;text-transform:uppercase;letter-spacing:.03em}"
        ".page img{width:100%;max-width:none;height:auto;aspect-ratio:1/1.414;display:block;border:1px solid #d7dde8;border-radius:8px;background:#fff;box-shadow:0 10px 24px rgba(15,23,42,.12);user-select:none;-webkit-user-drag:none}"
        ".empty{min-height:70vh;display:grid;place-content:center;gap:6px;text-align:center;color:#475569}"
        ".empty strong{color:#111827;font-size:15px}"
        "@media(min-width:720px){.pages{max-width:900px;margin:0 auto;padding:18px}.page img{border-radius:10px}}"
        "@media(max-width:520px){header{grid-template-columns:1fr}header strong{white-space:normal}.reader-toolbar{justify-content:stretch}.reader-toolbar a{margin-left:auto}.reader-toolbar a,.reader-toolbar button{min-height:40px}}"
        "</style></head><body>"
        '<main class="reader">'
        f"<header><strong>{escaped_name}</strong>"
        '<nav class="reader-toolbar" aria-label="Controlli del documento">'
        '<button type="button" data-zoom-out title="Riduci" aria-label="Riduci documento">&minus;</button>'
        '<button type="button" data-zoom-reset title="Adatta alla larghezza" aria-label="Adatta documento alla larghezza">Adatta</button>'
        '<output class="reader-toolbar__zoom" data-zoom-value aria-live="polite">100%</output>'
        '<button type="button" data-zoom-in title="Ingrandisci" aria-label="Ingrandisci documento">+</button>'
        f'<a href="{escaped_download}" title="Scarica documento">Scarica</a>'
        "</nav></header>"
        f'<section class="pages" data-document-pages>{pages}</section>'
        f'</main><script src="{viewer_script}" defer></script></body></html>'
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def mobile_pdf_preview_response(
    *,
    preview_payload: bytes,
    id_fasc: str,
    id_doc: str,
    documento: Any,
    nome_download: str,
    audit: Callable[..., None],
) -> Any | None:
    if request.args.get("viewer") != "mobile":
        return None
    scarica_url = url_for("scarica_documento", id_fasc=id_fasc, id_doc=id_doc)
    raw_page = str(request.args.get("page") or "").strip()
    if raw_page:
        try:
            page_number = int(raw_page)
            png_payload = render_pdf_page_png(preview_payload, page_number)
        except Exception as exc:
            current_app.logger.warning(
                "Anteprima mobile PDF non disponibile id_fasc=%s id_doc=%s page=%s: %s",
                id_fasc,
                id_doc,
                raw_page,
                exc,
            )
            return preview_error_html(scarica_url)
        audit(
            "fascicoli.documento.visualizza.mobile",
            "fascicolo",
            id_fasc,
            dettagli=f"doc {id_doc} - {documento.nome} pagina {page_number}",
        )
        return send_file(
            io.BytesIO(png_payload),
            mimetype="image/png",
            as_attachment=False,
            download_name=f"{Path(nome_download).stem}-pagina-{page_number}.png",
        )
    try:
        total_pages = pdf_page_count(preview_payload)
        page_urls = [
            url_for("visualizza_documento", id_fasc=id_fasc, id_doc=id_doc, viewer="mobile", page=page)
            for page in range(1, total_pages + 1)
        ]
    except Exception as exc:
        current_app.logger.warning(
            "Lettore mobile PDF non disponibile id_fasc=%s id_doc=%s: %s",
            id_fasc,
            id_doc,
            exc,
        )
        return preview_error_html(scarica_url)
    audit(
        "fascicoli.documento.visualizza.mobile",
        "fascicolo",
        id_fasc,
        dettagli=f"doc {id_doc} - {documento.nome}",
    )
    return pdf_mobile_preview_html(
        nome_documento=nome_download or documento.nome,
        page_urls=page_urls,
        scarica_url=scarica_url,
    )


def payload_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "si", "s", "on"}


def classifica_tipo_documento(nome_file: str) -> TipoDocumento:
    catalog_tipo = catalog_tipo_documento_per_nome(nome_file)
    if catalog_tipo != TipoDocumento.ALTRO:
        return catalog_tipo
    nome = str(nome_file or "").casefold()
    rules: list[tuple[tuple[str, ...], TipoDocumento]] = [
        (("procura", "mandato"), TipoDocumento.PROCURA),
        (("ricorso",), TipoDocumento.RICORSO),
        (("citazione",), TipoDocumento.CITAZIONE),
        (("comparsa",), TipoDocumento.COMPARSA),
        (("memoria", "note autorizzate", "conclusionale", "replica"), TipoDocumento.MEMORIA),
        (("sentenza",), TipoDocumento.SENTENZA),
        (("ordinanza",), TipoDocumento.ORDINANZA),
        (("decreto",), TipoDocumento.DECRETO),
        (("notifica", "relata"), TipoDocumento.NOTIFICA),
        (("verbale", "udienza"), TipoDocumento.VERBALE),
        (("parcella", "fattura", "proforma", "nota spese"), TipoDocumento.PARCELLA),
        (("contratto", "accordo", "scrittura privata"), TipoDocumento.CONTRATTO),
        (("deposito", "busta", "rdac", "rac", "esito"), TipoDocumento.DEPOSITO_PCT),
        (("pec", "comunicazione", "cancelleria"), TipoDocumento.COMUNICAZIONE),
        (("allegato", "doc", "documento", "immagine", "foto", "pdf"), TipoDocumento.ALLEGATO),
    ]
    for tokens, tipo in rules:
        if any(token in nome for token in tokens):
            return tipo
    return TipoDocumento.ALTRO


def applica_modalita_portale(items: list[dict[str, Any]], *, scarica_originale: bool) -> list[dict[str, Any]]:
    modalita = "originale" if scarica_originale else "copia"
    patched: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        if not str(row.get("modalita_documento_portale") or "").strip():
            row["modalita_documento_portale"] = modalita
        if row.get("original_documento_portale") is None:
            row["original_documento_portale"] = bool(scarica_originale)
        patched.append(row)
    return patched
