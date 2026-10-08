"""API React per unione PDF, archivi ZIP, acquisizione multipagina e OCR di pagina."""

from __future__ import annotations

import base64
import io
import json
import time

from flask import Blueprint, Response, current_app, jsonify, request, send_file, url_for, render_template_string

from web.blueprints.api_v1_react import _audit_event, _richiedi_auth
from web.helpers import get_clienti, get_fascicoli
from web.services.document_pdf_split import split_pdf
from web.services.document_ocr import recognize_page
from web.services.document_ocr_documento import come_payload, conta_pagine, riconosci_pagina
from web.services.documento_testo_riconosciuto import docx_da_testo, pdf_da_testo
from web.services.document_tools import (
    DocumentToolError,
    UploadedDocument,
    create_zip,
    images_to_pdf,
    merge_pdfs,
    safe_output_name,
)
from web.services.fascicolo_documento_ocr import documenti_riconoscibili, leggi_documento
from web.services.fascicolo_lookup import cerca_fascicoli_per_cliente


api_v1_document_tools = Blueprint("api_v1_document_tools", __name__)


@api_v1_document_tools.get("/fonts")
@_richiedi_auth
def document_font_catalog():
    from web.services.document_font_library import font_library
    try:
        fonts, _ = font_library()
        return jsonify(ok=True, fonts=fonts)
    except (OSError, ValueError, RuntimeError) as exc:
        return _handle_error(exc)


@api_v1_document_tools.get("/fonts/<token>/<kind>")
@_richiedi_auth
def document_font_file(token, kind):
    from web.services.document_font_library import resolve_font_file
    if kind not in {'file', 'license'}:
        return jsonify(ok=False, message="Risorsa del carattere non trovata."), 404
    path = resolve_font_file(token, kind == 'license')
    if path is None:
        return jsonify(ok=False, message="Carattere non disponibile nella libreria."), 404
    response = send_file(path, mimetype='text/plain; charset=utf-8' if kind == 'license'
                         else 'font/otf' if path.suffix == '.otf' else 'font/ttf', max_age=86400)
    response.headers['Cache-Control'] = 'private, max-age=86400'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


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
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.headers.get("X-Iusentra-Result-Links") == "1":
        from web.services.document_tools_cache import store_result, TTL
        token = store_result(data, filename, mimetype)
        response.headers["X-Iusentra-Expires"] = str(int(time.time() + TTL))
        response.headers["X-Iusentra-Download"] = url_for("api_v1_document_tools.document_tool_result_download", token=token)
        if mimetype == "application/pdf":
            response.headers["X-Iusentra-Preview"] = url_for("api_v1_document_tools.document_tool_result_preview", token=token, rotationScope="page")
    for key, value in headers.items():
        response.headers[key.replace("_", "-")] = str(value)
    return response


def _handle_error(exc: Exception):
    if isinstance(exc, DocumentToolError):
        return jsonify({"ok": False, "message": str(exc)}), 400
    current_app.logger.exception("Operazione documentale non completata", exc_info=exc)
    return jsonify({"ok": False, "message": "Elaborazione del documento non completata."}), 500


def _result_error(exc):
    if not isinstance(exc, DocumentToolError):
        return _handle_error(exc)
    html = render_template_string('''<!doctype html><html lang="it"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <style>body{margin:0;padding:24px;font:15px/1.6 system-ui;color:oklch(.25 .022 255);background:oklch(.99 .008 96)}main{max-width:65ch}h1{font-size:20px;margin:0 0 12px}p{overflow-wrap:anywhere}</style>
      </head><body><main role="alert"><h1>Copia temporanea non disponibile</h1><p>{{ message }}</p>
      <p>Chiudi questa vista e genera di nuovo il documento nella pagina degli strumenti.</p></main></body></html>''', message=str(exc))
    return html,400,{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}


@api_v1_document_tools.get("/results/<token>/scarica")
@_richiedi_auth
def document_tool_result_download(token):
    try:
        from web.services.document_tools_cache import read_result
        data, filename, mimetype = read_result(token)
        _audit_event("documenti.copia_generata_scaricata", "strumenti_documentali", "", "Download copia temporanea")
        return _download(data, filename, mimetype)
    except Exception as exc:
        return _result_error(exc)


@api_v1_document_tools.get("/results/<token>/visualizza")
@_richiedi_auth
def document_tool_result_preview(token):
    try:
        from web.services.document_tools_cache import read_result
        from web.bootstrap.fascicoli_document_helpers import pdf_page_count, pdf_mobile_preview_html, render_pdf_page_png
        data, filename, mimetype = read_result(token)
        if mimetype != "application/pdf":
            raise DocumentToolError("Il lettore documentale richiede un PDF.")
        raw_page = request.args.get("page")
        if raw_page is not None:
            try:
                page = int(raw_page)
            except (TypeError, ValueError):
                raise DocumentToolError("Pagina non valida.") from None
            if not 1 <= page <= pdf_page_count(data):
                raise DocumentToolError("Pagina non presente nel documento.")
            if request.args.get("reader_text") == "1":
                from web.services.pdf_reader_text import page_text_response
                return page_text_response(data,page)
            response = send_file(io.BytesIO(render_pdf_page_png(data,page)),mimetype="image/png",max_age=0)
        else:
            total = pdf_page_count(data)
            if not 1 <= total <= 1500:
                raise DocumentToolError("Numero di pagine non valido per il lettore.")
            html,status,headers = pdf_mobile_preview_html(nome_documento=filename,pdf_payload=data,
                page_urls=[url_for("api_v1_document_tools.document_tool_result_preview",token=token,page=i) for i in range(1,total+1)],
                scarica_url=url_for("api_v1_document_tools.document_tool_result_download",token=token))
            _audit_event("documenti.copia_generata_visualizzata", "strumenti_documentali", "", f"{total} pagine")
            response = current_app.make_response((html,status,headers))
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        return response
    except Exception as exc:
        return _result_error(exc)


@api_v1_document_tools.post("/preview")
@_richiedi_auth
def preview_uploaded_pdf():
    """Consulta la fonte caricata senza riscriverla o archiviarla nel fascicolo."""
    try:
        from web.blueprints.api_v1_react import _session_user_can
        if not (_session_user_can("admin.leggi") or _session_user_can("fascicoli.leggi")):
            return jsonify({"ok": False, "message": "Non hai il permesso di usare gli strumenti documentali."}), 403
        from web.services.document_tools import MAX_FILE_BYTES, MAX_PAGES, _pdf_reader, validate_uploads
        from web.services.document_tools_cache import store_result, TTL
        uploads = request.files.getlist("files")
        if len(uploads) != 1:
            raise DocumentToolError("Per visualizzare seleziona un solo PDF.")
        uploaded = uploads[0]
        document = UploadedDocument(str(uploaded.filename or "documento.pdf"), uploaded.read(MAX_FILE_BYTES + 1))
        validate_uploads([document])
        total = len(_pdf_reader(document).pages)
        if not 1 <= total <= MAX_PAGES:
            raise DocumentToolError(f"Il PDF deve contenere da 1 a {MAX_PAGES} pagine.")
        filename = safe_output_name(document.name, "pdf", "documento")
        token = store_result(document.data, filename, "application/pdf")
        _audit_event("documenti.anteprima_caricata", "strumenti_documentali", "", f"{total} pagine, fonte invariata")
        response = jsonify({"ok": True, "previewHref": url_for("api_v1_document_tools.document_tool_result_preview", token=token, rotationScope="page"),
                            "expiresAt": int(time.time() + TTL) * 1000})
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.post("/split")
@_richiedi_auth
def split_document():
    try:
        from web.services.document_tools import MAX_FILE_BYTES
        uploads = request.files.getlist("files")
        if len(uploads) != 1:
            raise DocumentToolError("Per dividere un PDF seleziona un solo documento.")
        uploaded = uploads[0]
        data = uploaded.read(MAX_FILE_BYTES + 1)
        result, pages = split_pdf([UploadedDocument(str(uploaded.filename or "documento.pdf"), data)], str(request.form.get("pages") or ""))
        filename = safe_output_name(request.form.get("output_name", ""), "pdf", "pagine-estratte")
        _audit_event("documenti.pagine_estratte", "strumenti_documentali", "", f"{pages} pagine estratte")
        return _download(result, filename, "application/pdf", X_Iusentra_Pages=pages, X_Iusentra_Files=1, X_Iusentra_Operation="split-pdf")
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.post("/word")
@_richiedi_auth
def convert_document_to_word():
    try:
        from web.blueprints.api_v1_react import _session_user_can
        from web.services.document_pdf_word import DOCX_MIME, convert_pdf_to_word
        from web.services.document_tools import MAX_FILE_BYTES
        if not (_session_user_can("admin.leggi") or _session_user_can("fascicoli.leggi")):
            return jsonify({"ok": False, "message": "Non hai il permesso di usare gli strumenti documentali."}), 403
        uploads = request.files.getlist("files")
        if len(uploads) != 1:
            raise DocumentToolError("Per convertire in Word seleziona un solo PDF.")
        uploaded = uploads[0]
        data, pages, preview = convert_pdf_to_word(UploadedDocument(str(uploaded.filename or "documento.pdf"), uploaded.read(MAX_FILE_BYTES + 1)), request.form.get('review', ''))
        filename = safe_output_name(request.form.get("output_name", ""), "docx", "documento-convertito")
        _audit_event("documenti.pdf_convertito_word", "strumenti_documentali", "", f"{pages} pagine convertite, originale conservato")
        response = _download(data, filename, DOCX_MIME, X_Iusentra_Pages=pages, X_Iusentra_Files=1, X_Iusentra_Operation="pdf-word")
        if request.headers.get("X-Iusentra-Result-Links") == "1":
            from web.services.document_tools_cache import store_result
            preview_token = store_result(preview, filename + '.pdf', 'application/pdf')
            response.headers['X-Iusentra-Preview'] = url_for('api_v1_document_tools.document_tool_result_preview', token=preview_token, rotationScope='page')
        return response
    except Exception as exc:
        return _handle_error(exc)


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
        page_format = str(request.form.get("page_format") or "").strip().lower()
        data, pages = images_to_pdf(_uploads(), _integer_list("rotations"), page_format=page_format)
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


@api_v1_document_tools.post("/ocr-page")
@_richiedi_auth
def recognize_document_page():
    """OCR di una pagina acquisita: PDF ricercabile in memoria, nessun salvataggio."""
    try:
        uploaded = request.files.get("file")
        if uploaded is None:
            raise DocumentToolError("Nessuna pagina ricevuta.")
        try:
            rotation = int(request.form.get("rotation") or 0) % 360
        except (TypeError, ValueError):
            rotation = 0
        raddrizza = str(request.form.get("deskew") or "1").strip() not in {"0", "false", "no"}
        result = recognize_page(uploaded.read(), rotation, raddrizza=raddrizza)
        response = jsonify(
            {
                "ok": True,
                "pdf_base64": base64.b64encode(result.pdf).decode("ascii"),
                "paragraphs": result.paragraphs,
                "characters": result.characters,
                "dpi": result.dpi,
                # Struttura riconosciuta: l'editor la usa per reinserire il testo
                # con la forma del documento invece che come blocco unico.
                "blocks": result.blocks,
                "figures": result.figures,
                "tables": result.tables,
                "confidence": result.confidence,
                "engine": result.engine,
                "steps": list(result.steps),
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.get("/fascicoli")
@_richiedi_auth
def search_matters():
    """Fascicoli che corrispondono al nome del cliente cercato.

    L'avvocato salva il documento acquisito cercando per come chiama le cose:
    nome e cognome del cliente, non l'identificativo del fascicolo.
    """
    try:
        try:
            limite = int(request.args.get("limit") or 20)
        except (TypeError, ValueError):
            limite = 20
        risultati = cerca_fascicoli_per_cliente(
            request.args.get("q") or "",
            gestore_fascicoli=get_fascicoli,
            gestore_clienti=get_clienti,
            limite=max(1, min(limite, 50)),
        )
        response = jsonify({"ok": True, "results": risultati})
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.get("/fascicoli/<id_fasc>/documenti-riconoscibili")
@_richiedi_auth
def list_recognisable_documents(id_fasc: str):
    """Documenti gia' nel fascicolo su cui si puo' riconoscere il testo."""
    try:
        response = jsonify({"ok": True, "documents": documenti_riconoscibili(get_fascicoli(), id_fasc)})
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.post("/ocr-documento")
@_richiedi_auth
def recognize_document_page_of_file():
    """Riconosce una pagina di un documento del fascicolo o di un file caricato.

    Una pagina per richiesta: un atto di quaranta pagine non puo' stare in una
    sola risposta senza far scadere la richiesta, e cosi' l'avvocato vede
    l'avanzamento e puo' fermarsi appena ha quello che gli serve. Nessun
    contenuto viene salvato: la copia ricercabile nasce solo se la conferma.
    """
    try:
        try:
            pagina = int(request.form.get("pagina") or 1)
        except (TypeError, ValueError):
            pagina = 1
        raddrizza = str(request.form.get("deskew") or "1").strip() not in {"0", "false", "no"}

        fascicolo_id = str(request.form.get("fascicolo_id") or "").strip()
        documento_id = str(request.form.get("documento_id") or "").strip()
        uploaded = request.files.get("file")
        if fascicolo_id and documento_id:
            nome, contenuto = leggi_documento(get_fascicoli(), fascicolo_id, documento_id)
            if pagina <= 1:
                _audit_event(
                    "fascicoli.documento.riconoscimento_testo",
                    "fascicolo",
                    fascicolo_id,
                    f"doc {documento_id} — {nome}",
                )
        elif uploaded is not None:
            nome = str(uploaded.filename or "documento.pdf")
            contenuto = uploaded.read()
        else:
            raise DocumentToolError("Scegli un documento del fascicolo oppure carica un file.")

        totale = conta_pagine(contenuto, nome)
        esito = riconosci_pagina(contenuto, nome, pagina, raddrizza=raddrizza)
        response = jsonify(
            {
                "ok": True,
                "nome": nome,
                "pagine_totali": totale,
                "pagina": come_payload(esito),
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception as exc:
        return _handle_error(exc)


@api_v1_document_tools.post("/documento-testo-riconosciuto")
@_richiedi_auth
def build_recognised_text_document():
    """Il testo riconosciuto e corretto diventa un `.docx` apribile nell'editor.

    La revisione serve a correggere; l'editor serve a lavorare. Il passaggio fra
    le due cose e' un documento vero, non un appunto: quello che l'avvocato ha
    corretto qui e' esattamente quello che si aprira' nell'editor del fascicolo.
    """
    try:
        html = str(request.form.get("html") or "")
        nome = str(request.form.get("nome") or "documento")
        formato = str(request.form.get("formato") or "docx").strip().lower()
        if formato == "pdf":
            dati, filename = pdf_da_testo(html, nome)
            return _download(dati, filename, "application/pdf", X_Iusentra_Operation="documento-testo-riconosciuto-pdf")
        dati, filename = docx_da_testo(html, nome)
        return _download(
            dati,
            filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            X_Iusentra_Operation="documento-testo-riconosciuto",
        )
    except Exception as exc:
        return _handle_error(exc)
