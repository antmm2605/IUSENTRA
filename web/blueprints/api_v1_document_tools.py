"""API React per unione PDF, archivi ZIP e acquisizione multipagina."""

from __future__ import annotations

import io
import json

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from web.blueprints.api_v1_react import _richiedi_auth
from web.services.document_tools import (
    DocumentToolError,
    UploadedDocument,
    create_zip,
    images_to_pdf,
    merge_pdfs,
    safe_output_name,
)


api_v1_document_tools = Blueprint("api_v1_document_tools", __name__)


def _uploads() -> list[UploadedDocument]:
    rows: list[UploadedDocument] = []
    for uploaded in request.files.getlist("files"):
        rows.append(
            UploadedDocument(
                name=str(uploaded.filename or "documento"),
                data=uploaded.read(),
            )
        )
    return rows


def _string_list(name: str) -> list[str]:
    values = request.form.getlist(name)
    if values:
        return [str(value or "") for value in values]
    raw = str(request.form.get(name) or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(value or "") for value in parsed] if isinstance(parsed, list) else []


def _integer_list(name: str) -> list[int]:
    result: list[int] = []
    for value in _string_list(name):
        try:
            result.append(int(value) % 360)
        except (TypeError, ValueError):
            result.append(0)
    return result


def _download(data: bytes, filename: str, mimetype: str, **headers: str | int) -> Response:
    response = send_file(
        io.BytesIO(data),
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store"
    for key, value in headers.items():
        response.headers[key.replace("_", "-")] = str(value)
    return response


def _handle_error(exc: Exception):
    if isinstance(exc, DocumentToolError):
        return jsonify({"ok": False, "message": str(exc)}), 400
    current_app.logger.exception("Operazione documentale non completata", exc_info=exc)
    return jsonify({"ok": False, "message": "Elaborazione del documento non completata."}), 500


@api_v1_document_tools.post("/merge")
@_richiedi_auth
def merge_documents():
    try:
        data, pages = merge_pdfs(_uploads())
        filename = safe_output_name(request.form.get("output_name", ""), "pdf", "documenti-uniti")
        return _download(
            data,
            filename,
            "application/pdf",
            X_Iusentra_Pages=pages,
            X_Iusentra_Operation="merge-pdf",
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.post("/zip")
@_richiedi_auth
def archive_documents():
    try:
        uploads = _uploads()
        data = create_zip(uploads, _string_list("logical_names"))
        filename = safe_output_name(request.form.get("output_name", ""), "zip", "documenti")
        return _download(
            data,
            filename,
            "application/zip",
            X_Iusentra_Files=len(uploads),
            X_Iusentra_Operation="create-zip",
        )
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.post("/multipage")
@_richiedi_auth
def build_multipage_document():
    try:
        data, pages = images_to_pdf(_uploads(), _integer_list("rotations"))
        filename = safe_output_name(request.form.get("output_name", ""), "pdf", "acquisizione-multipagina")
        return _download(
            data,
            filename,
            "application/pdf",
            X_Iusentra_Pages=pages,
            X_Iusentra_Operation="multipage-pdf",
        )
    except Exception as exc:
        return _handle_error(exc)
