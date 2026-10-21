"""Scambio PDF con l'editor indipendente: nessuna conversione e nessun OCR."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from uuid import UUID

from flask import g, jsonify, request, send_file

from pct.prima_nota_transition import prima_nota_source_lock
from web.services.viewer_edit_policy import nuova_versione_ammessa

MAX_NATIVE_PDF_BYTES = 64 * 1024 * 1024


def validate_native_pdf(content: bytes) -> None:
    import fitz
    from pct.document_signature_state import document_bytes_have_real_digital_signature

    if not content.startswith(b"%PDF-") or len(content) > MAX_NATIVE_PDF_BYTES:
        raise ValueError("Il file deve essere un PDF valido entro 64 MiB.")
    if document_bytes_have_real_digital_signature(content, "documento.pdf"):
        raise ValueError("Il PDF firmato resta in sola lettura: la firma e l’originale sono preservati.")
    try:
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.is_encrypted or not pdf.page_count:
                raise ValueError("Il PDF è cifrato oppure non contiene pagine.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Il PDF modificato non è leggibile. La fonte è preservata.") from exc


def register_editor_native_pdf_routes(app, *, get_fascicoli, decrypt_doc, encrypt_doc, audit, document_updated):
    @app.after_request
    def independent_pdf_editor_headers(response):
        if request.path.startswith("/static/vendor/pdfcraft-direct/"):
            # Il frame è in un'origine opaca (sandbox senza same-origin).
            # Solo risorse pubbliche del componente, mai API o documenti.
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; "
                "font-src 'self' data:; connect-src 'self' blob:; "
                "frame-ancestors 'self'; base-uri 'none'; form-action 'none'; object-src 'none'"
            )
        return response

    @app.route("/api/v1/ui/fascicoli/<fid>/documenti/<did>/pdf-diretto", methods=["GET", "POST"])
    def editor_native_pdf(fid, did):
        user = g.get("utente_corrente")
        if not user or not all(user.ha_permesso(p) for p in ("fascicoli.leggi", "fascicoli.scrivi")):
            return jsonify(ok=False, message="Non hai il permesso di modificare questo documento."), 403
        if getattr(g, "tenant_context_missing", False):
            return jsonify(ok=False, message="Lo studio corrente non è disponibile."), 403

        if request.method == "POST":
            if request.headers.get("X-Requested-With") != "XMLHttpRequest":
                return jsonify(ok=False, message="Richiesta di salvataggio non valida."), 400
            try:
                command = str(UUID(request.form.get("commandId", "")))
                expected = request.form.get("expectedHash", "")
                if not re.fullmatch(r"[0-9a-f]{64}", expected):
                    raise ValueError("La versione di partenza non è valida. Riapri il documento.")
                upload = request.files.get("file")
                if upload is None:
                    raise ValueError("Il PDF modificato non è stato ricevuto.")
                content = upload.read(MAX_NATIVE_PDF_BYTES + 1)
                validate_native_pdf(content)
            except (ValueError, TypeError) as exc:
                return jsonify(ok=False, message=str(exc)), 400
        else:
            expected = request.args.get("expectedHash", "")

        try:
            repo = get_fascicoli()
            if repo._studio_db is None:
                raise RuntimeError("Archivio SQL non disponibile")
            anchor = (getattr(g, "data_paths", {}) or {}).get("FASCICOLI_DB")
            if not anchor:
                raise RuntimeError("Percorso dello studio non disponibile")
            # Lock dello stesso oggetto tra processi. Nessun percorso dal client.
            lock_key = hashlib.sha256(f"{fid}:{did}".encode()).hexdigest()
            with prima_nota_source_lock(str(Path(anchor).parent / ".editor-locks" / lock_key)):
                matter = repo.get(fid)
                document = next((d for d in getattr(matter, "documenti", []) if d.id == did), None)
                if document is None or getattr(document, "eliminato_il", ""):
                    return jsonify(ok=False, message="Documento non trovato nello studio corrente."), 404
                if not nuova_versione_ammessa(document):
                    return jsonify(ok=False, message="La modifica diretta richiede un PDF dello studio non firmato. L’originale resta preservato."), 403

                repeated = False
                if request.method == "POST":
                    digest = hashlib.sha256(content).hexdigest()
                    marker = "pdf-native:" + command
                    same_command = marker in str(getattr(document, "note", ""))
                    repeated = (same_command
                                and getattr(document, "hash_contenuto_sha256", "") == digest
                                and str(getattr(document, "caricato_da", "")) == user.username)
                    if same_command and not repeated:
                        return jsonify(ok=False, message="Questa richiesta è già stata usata per una modifica diversa."), 409
                if request.method == "POST" and expected != document.hash_sha256 and not repeated:
                    return jsonify(ok=False, message="Il documento è stato modificato da un’altra sessione. Le tue modifiche restano aperte: riapri la versione corrente prima di sostituirla."), 409
                if request.method == "GET":
                    path = Path(repo.percorso_documento_lettura(fid, did))
                    if path.stat().st_size > MAX_NATIVE_PDF_BYTES + 1024:
                        raise ValueError("Il documento supera il limite di 64 MiB.")
                    original = decrypt_doc(path.read_bytes())
                    validate_native_pdf(original)
                    response = send_file(io.BytesIO(original), mimetype="application/pdf")
                    from urllib.parse import quote

                    response.headers["X-PDF-Name"] = quote(document.nome)
                    response.headers["X-PDF-Revision"] = document.hash_sha256
                    response.headers["Cache-Control"] = "no-store"
                    return response

                if not repeated:
                    document = repo.sostituisci_documento(
                        fid, did, nome_file=document.nome, contenuto=encrypt_doc(content),
                        caricato_da=user.username, note="Modifica diretta PDF; " + marker,
                        hash_contenuto_sha256=digest,
                    )
                    document_updated(fid, document)
                audit("fascicoli.documento.editor_pdf_nativo", "fascicolo", fid,
                      dettagli=f"doc {did}; comando {command}; ripetizione {repeated}; sha256 {digest}")
                return jsonify(ok=True, hash=document.hash_sha256, alreadyPresent=repeated,
                               message="PDF salvato nel fascicolo. La versione precedente è conservata.")
        except ValueError as exc:
            return jsonify(ok=False, message=str(exc)), 400
        except Exception:
            app.logger.exception("Modifica PDF nativa non confermata")
            return jsonify(ok=False, message="Salvataggio non confermato. Le modifiche restano nell’editor: riprova la stessa richiesta."), 503
