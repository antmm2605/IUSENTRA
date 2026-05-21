"""Inline editor routes extracted from the fascicoli monolith."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, url_for


def _wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def _richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def register_fascicoli_editor_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    audit: Callable[..., None],
    decrypt_doc: Callable[[bytes], bytes],
    encrypt_doc: Callable[[bytes], bytes],
    accoda_ocr: Callable[..., None],
) -> None:
    """Register inline editor and conversion routes for fascicolo documents."""

    def _cfg_data_path(key: str) -> str:
        paths = getattr(g, "data_paths", {}) or {}
        if paths and key in paths:
            return str(paths[key])
        if getattr(g, "tenant_context_missing", False):
            raise RuntimeError(
                "Contesto studio non disponibile per la richiesta corrente. "
                "Accesso ai dati bloccato per evitare letture cross-studio."
            )
        return str(app.config[key])

    def _indicizza_salvataggio_editor(*, id_fasc: str, document_id: str, filename: str, content: bytes) -> None:
        try:
            from pct.document_intelligence.sources import source_from_uploaded_document
            from web.services.document_intelligence_runtime import (
                build_document_ai_service,
                document_ai_tenant_id,
                document_ai_user_context,
            )

            tenant_id = document_ai_tenant_id()
            source = source_from_uploaded_document(
                tenant_id=tenant_id,
                fascicolo_id=id_fasc,
                document_id=document_id,
                filename=filename,
                content=content,
                source_type="editor_professionale",
                metadata={"trigger": "editor_salva"},
            )
            build_document_ai_service().process_lex_indexing_sources(
                tenant_id,
                id_fasc,
                [source],
                document_ai_user_context(),
                retry_errors=True,
            )
        except Exception as exc:
            app.logger.warning("Indicizzazione Lex editor non completata per %s/%s: %s", id_fasc, filename, exc)

    def _current_studio_timbro():
        try:
            from pct.studio_timbro import build_studio_timbro

            return build_studio_timbro(
                db_path=_cfg_data_path("STUDIO_TIMBRO_DB"),
                config_studio=getattr(g, "config_studio", None),
                app_config=app.config,
                postgres_dsn=str(app.config.get("POSTGRES_DSN", "") or ""),
            )
        except Exception:
            return None

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/editor")
    def editor_documento(id_fasc, id_doc):
        from pct.editor import estensione_editabile

        gestore_fascicoli = get_fascicoli()
        try:
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None) if fascicolo else None
            if documento and (documento.firmato_digitalmente or documento.nome.lower().endswith(".p7m")):
                return redirect(url_for("visualizza_documento", id_fasc=id_fasc, id_doc=id_doc))
        except Exception:
            fascicolo = None
            documento = None

        if not _richiede_vista_classica():
            from web.blueprints.react_shell import render_react_shell_response

            return render_react_shell_response(f"fascicoli/{id_fasc}/documenti/{id_doc}/editor")

        try:
            if not fascicolo:
                flash("Fascicolo non trovato.", "warning")
                return redirect(url_for("lista_fascicoli"))
            if not documento:
                flash("Documento non trovato.", "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            if not estensione_editabile(documento.nome):
                flash(
                    f"Formato '{documento.nome.split('.')[-1].upper()}' non supportato dall'editor.",
                    "warning",
                )
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            return render_template(
                "fascicoli/editor_documento.html",
                id_fasc=id_fasc,
                fasc=fascicolo,
                doc=documento,
                oggi=date.today(),
            )
        except Exception as exc:
            app.logger.exception("Errore editor_documento: %s", exc)
            flash("Documento non aperto nell'editor.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/converti-pdfa", methods=["POST"])
    def converti_documento_pdfa(id_fasc, id_doc):
        from pct.validazione import converti_pdfa

        gestore_fascicoli = get_fascicoli()
        try:
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                if _wants_json_response():
                    return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404
                flash("Fascicolo non trovato.", "warning")
                return redirect(url_for("lista_fascicoli"))
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                if _wants_json_response():
                    return jsonify({"ok": False, "messaggio": "Documento non trovato."}), 404
                flash("Documento non trovato.", "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            if not documento.nome.lower().endswith(".pdf"):
                if _wants_json_response():
                    return jsonify(
                        {
                            "ok": False,
                            "messaggio": f"La conversione PDF/A e' disponibile solo per file PDF (file: {documento.nome}).",
                        }
                    ), 400
                flash(
                    f"La conversione PDF/A è disponibile solo per file PDF (file: {documento.nome}).",
                    "warning",
                )
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            percorso = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
            esito = converti_pdfa(str(percorso))
            if esito["ok"]:
                msg = f"Documento convertito in PDF/A-2B con successo. {esito['messaggio']}"
                flash(msg, "success")
                audit("documento.converti_pdfa", id_fasc=id_fasc, id_doc=id_doc, nome=documento.nome)
                if _wants_json_response():
                    return jsonify({"ok": True, "messaggio": msg})
            else:
                msg = f"Conversione PDF/A non riuscita: {esito['messaggio']}"
                if _wants_json_response():
                    return jsonify({"ok": False, "messaggio": msg}), 400
                flash(msg, "danger")
        except Exception as exc:
            app.logger.exception("Errore converti_documento_pdfa: %s", exc)
            if _wants_json_response():
                return jsonify({"ok": False, "messaggio": "Conversione PDF/A non completata."}), 500
            flash("Errore durante la conversione.", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/api/editor/<id_fasc>/<id_doc>/html")
    def api_editor_carica_html(id_fasc, id_doc):
        from pct.editor import documento_to_html

        gestore_fascicoli = get_fascicoli()
        try:
            percorso = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            raw = decrypt_doc(percorso.read_bytes())
            html, avvisi, meta = documento_to_html(raw, documento.nome)
            return jsonify({"ok": True, "html": html, "avvisi": avvisi, "nome": documento.nome, "meta": meta})
        except Exception as exc:
            app.logger.exception("Errore api_editor_carica_html: %s", exc)
            return jsonify({"ok": False, "html": "<p>Documento non caricato.</p>", "avvisi": ["Documento non caricato."], "meta": {}})

    @app.route("/api/editor/<id_fasc>/<id_doc>/salva", methods=["POST"])
    def api_editor_salva(id_fasc, id_doc):
        from pct.editor import html_to_docx, html_to_pdf

        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "")
            auto = body.get("auto", False)

            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            nome = documento.nome
            ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""

            timbro = _current_studio_timbro()
            if ext == "docx":
                contenuto_raw = html_to_docx(html, titolo=nome.rsplit(".", 1)[0], studio_timbro=timbro)
                nome_salvato = nome
            elif ext == "pdf":
                contenuto_raw = html_to_pdf(html, titolo=nome.rsplit(".", 1)[0], studio_timbro=timbro)
                nome_salvato = nome
            else:
                contenuto_raw = html.encode("utf-8")
                nome_salvato = nome.rsplit(".", 1)[0] + ".html" if "." in nome else nome + ".html"

            doc_salvato = gestore_fascicoli.sostituisci_documento(
                id_fasc,
                id_doc,
                nome_file=nome_salvato,
                contenuto=encrypt_doc(contenuto_raw),
                caricato_da=utente.username if utente else "editor",
                note="Salvato dall'editor" + (" (auto)" if auto else ""),
            )
            accoda_ocr(
                percorso=str(gestore_fascicoli.percorso_documento(id_fasc, doc_salvato.id)),
                hash_sha256=doc_salvato.hash_sha256,
                id_fasc=id_fasc,
                id_doc=doc_salvato.id,
                nome_doc=doc_salvato.nome,
                tipo_doc=doc_salvato.tipo.value,
                index_path=_cfg_data_path("SEARCH_INDEX"),
            )
            _indicizza_salvataggio_editor(
                id_fasc=id_fasc,
                document_id=doc_salvato.id,
                filename=nome_salvato,
                content=contenuto_raw,
            )
            audit("fascicoli.documento.editor_salva", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {nome}")
            return jsonify({"ok": True, "auto": auto})
        except Exception as exc:
            app.logger.exception("Errore api_editor_salva: %s", exc)
            return jsonify({"ok": False, "errore": "Documento non salvato."})

    @app.route("/api/editor/<id_fasc>/<id_doc>/pdf", methods=["POST"])
    def api_editor_pdf(id_fasc, id_doc):
        from pct.editor import html_to_pdf

        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "<p></p>")
            fascicolo = get_fascicoli().get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            titolo = documento.nome.rsplit(".", 1)[0] if documento else "documento"
            pdf_bytes = html_to_pdf(html, titolo=titolo, studio_timbro=_current_studio_timbro())
            audit("fascicoli.documento.editor_pdf", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=titolo + ".pdf",
            )
        except ImportError as exc:
            return jsonify({"errore": "Generazione PDF non disponibile."}), 503
        except Exception as exc:
            app.logger.exception("Errore api_editor_pdf: %s", exc)
            return "Generazione PDF non completata.", 500

    @app.route("/api/editor/<id_fasc>/<id_doc>/docx", methods=["POST"])
    def api_editor_docx(id_fasc, id_doc):
        from pct.editor import html_to_docx

        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "<p></p>")
            fascicolo = get_fascicoli().get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            titolo = documento.nome.rsplit(".", 1)[0] if documento else "documento"
            docx_bytes = html_to_docx(html, titolo=titolo, studio_timbro=_current_studio_timbro())
            audit("fascicoli.documento.editor_docx", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
            return send_file(
                io.BytesIO(docx_bytes),
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                download_name=titolo + ".docx",
            )
        except ImportError as exc:
            return jsonify({"errore": "Generazione DOCX non disponibile."}), 503
        except Exception as exc:
            app.logger.exception("Errore api_editor_docx: %s", exc)
            return "Generazione DOCX non completata.", 500
