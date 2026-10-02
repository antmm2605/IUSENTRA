"""Adattatore del lettore verso il salvataggio PDF già governato dal fascicolo."""
import io

from flask import g, jsonify, request, send_file

from web.services.viewer_edit_policy import motivo_sola_lettura, nuova_versione_ammessa


def register_viewer_editor_routes(app):
    def puo(permesso):
        user = g.get("utente_corrente")
        return bool(user and user.ha_permesso(permesso))

    @app.post("/api/v1/ui/fascicoli/<fid>/documenti/<did>/editor-visualizzatore/anteprima/<int:pagina>")
    def documento_editor_anteprima(fid, did, pagina):
        from pathlib import Path
        from pct.document_crypto import decrypt_doc
        from web.helpers import get_fascicoli
        from web.services.pdf_modificabile import DocumentoNonConvertibile, pdf_di_lavoro
        from web.services.pdf_overlay_editor import PdfOverlayError, apply_pdf_overlays, render_pdf_page_png

        if not puo("fascicoli.leggi") or not puo("fascicoli.scrivi"):
            return jsonify(ok=False, message="Permesso insufficiente."), 403
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            return jsonify(ok=False, message="Richiesta di anteprima non valida."), 400
        gestore = get_fascicoli()
        fascicolo = gestore.get(fid)
        doc = next((d for d in getattr(fascicolo, "documenti", []) if d.id == did), None)
        if not doc:
            return jsonify(ok=False, message="Documento non trovato."), 404
        motivo = motivo_sola_lettura(doc)
        if motivo:
            return jsonify(ok=False, message=motivo), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or body.get("expectedHash") != doc.hash_sha256:
            return jsonify(ok=False, message="Il documento è cambiato. Riaprilo prima di applicare altre modifiche."), 409
        annotations = body.get("annotations")
        if not isinstance(annotations, list) or not 1 <= len(annotations) <= 100:
            return jsonify(ok=False, message="Inserisci da 1 a 100 interventi."), 400
        if not nuova_versione_ammessa(doc) and any(not isinstance(a, dict) or a.get("type") == "replace" for a in annotations):
            return jsonify(ok=False, message="Il testo originale si modifica solo nei documenti prodotti dallo studio."), 403
        try:
            raw = decrypt_doc(Path(gestore.percorso_documento_lettura(fid, did)).read_bytes())
            lavoro = pdf_di_lavoro(doc, raw, originale_modificabile=nuova_versione_ammessa(doc))
            modificato, _ = apply_pdf_overlays(lavoro.dati, annotations)
            response = send_file(io.BytesIO(render_pdf_page_png(modificato, page_number=pagina)), mimetype="image/png")
            response.headers["Cache-Control"] = "no-store"
            return response
        except (PdfOverlayError, DocumentoNonConvertibile) as exc:
            return jsonify(ok=False, message=str(exc)), 400
        except Exception:
            app.logger.exception("Anteprima della modifica non disponibile")
            return jsonify(ok=False, message="Anteprima non disponibile. Nessuna modifica è stata salvata."), 500

    @app.route("/api/v1/ui/fascicoli/<fid>/documenti/<did>/editor-visualizzatore", methods=["GET", "POST"])
    def documento_editor_visualizzatore(fid, did):
        if request.method == "POST":
            import hashlib
            from pathlib import Path
            from pct.sync import FileLock
            from web.helpers import _cfg

            if not puo("fascicoli.leggi") or not puo("fascicoli.scrivi"):
                return jsonify(ok=False, message="Permesso insufficiente."), 403
            key = hashlib.sha256(f"{fid}:{did}".encode("utf-8")).hexdigest()
            lock = Path(_cfg("FASCICOLI_DB")).parent / ".editor-locks" / key
            try:
                # Il controllo della versione viene ripetuto dopo il lock:
                # due lettori non possono sovrascrivere lo stesso hash.
                with FileLock(str(lock)):
                    return _documento_editor_visualizzatore(fid, did)
            except Exception:
                app.logger.exception("Salvataggio del lettore non disponibile")
                return jsonify(ok=False, message="Salvataggio non disponibile. Le modifiche restano nel lettore."), 500
        return _documento_editor_visualizzatore(fid, did)

    def _documento_editor_visualizzatore(fid, did):
        from web.helpers import get_fascicoli

        if not puo("fascicoli.leggi"):
            return jsonify(ok=False, message="Permesso di consultazione insufficiente."), 403
        fascicolo = get_fascicoli().get(fid)
        documento = next((d for d in getattr(fascicolo, "documenti", []) if d.id == did), None)
        if not documento:
            return jsonify(ok=False, message="Documento non trovato."), 404
        motivo = motivo_sola_lettura(documento)
        if not motivo and not puo("fascicoli.scrivi"):
            motivo = "Non hai il permesso di modificare i documenti del fascicolo."
        if request.method == "GET":
            return jsonify(ok=True, editable=not bool(motivo), reason=motivo, studio=nuova_versione_ammessa(documento),
                           hash=documento.hash_sha256, versionCount=len(documento.versioni),
                           base=f"/api/editor/{fid}/{did}")
        if motivo:
            return jsonify(ok=False, message=motivo), 403
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            return jsonify(ok=False, message="Richiesta di salvataggio non valida."), 400
        body = request.get_json(silent=True)
        destinazioni = {"versione", "copia", "scarica"} if nuova_versione_ammessa(documento) else {"copia", "scarica"}
        if not isinstance(body, dict) or body.get("destinazione") not in destinazioni:
            return jsonify(ok=False, message="L’originale è protetto. Salva o scarica una copia per la condivisione."), 403
        if not body.get("expectedHash") or body["expectedHash"] != documento.hash_sha256:
            return jsonify(ok=False, message="Il documento è cambiato. Riaprilo prima di salvare altre modifiche."), 409
        annotations = body.get("annotations")
        if not isinstance(annotations, list) or not 1 <= len(annotations) <= 100:
            return jsonify(ok=False, message="Inserisci da 1 a 100 interventi per versione."), 400
        if not nuova_versione_ammessa(documento) and any(not isinstance(a, dict) or a.get("type") == "replace" for a in annotations):
            return jsonify(ok=False, message="Il testo originale si modifica solo nei documenti prodotti dallo studio."), 403
        # Si riusa integralmente la procedura nativa: cifratura, storico delle
        # versioni, SQL, audit, inventario delle letture e indicizzazione.
        return app.view_functions["api_editor_pdf_overlay"](fid, did)

    @app.get("/api/v1/ui/fascicoli/<fid>/documenti/<did>/editor-visualizzatore/testo/<int:pagina>")
    def documento_editor_testo(fid, did, pagina):
        from pathlib import Path
        from pct.document_crypto import decrypt_doc
        from web.helpers import get_fascicoli
        from web.services.pdf_overlay_editor import PdfOverlayError, pdf_text_spans
        from web.services.viewer_image_objects import writing_layout

        if not puo("fascicoli.leggi") or not puo("fascicoli.scrivi"):
            return jsonify(ok=False, message="Permesso insufficiente."), 403
        gestore = get_fascicoli()
        fascicolo = gestore.get(fid)
        doc = next((d for d in getattr(fascicolo, "documenti", []) if d.id == did), None)
        if not doc or not nuova_versione_ammessa(doc) or getattr(doc, "eliminato_il", ""):
            return jsonify(ok=False, message="Il testo si modifica solo nei PDF prodotti dallo studio, non firmati."), 403
        try:
            dati = decrypt_doc(Path(gestore.percorso_documento_lettura(fid, did)).read_bytes())
            return jsonify(ok=True, spans=pdf_text_spans(dati, pagina), layout=writing_layout(dati, pagina))
        except PdfOverlayError as exc:
            return jsonify(ok=False, message=str(exc)), 400
        except Exception:
            app.logger.exception("Testo del documento non disponibile")
            return jsonify(ok=False, message="Il testo non è disponibile. Nessuna modifica è stata salvata."), 500
