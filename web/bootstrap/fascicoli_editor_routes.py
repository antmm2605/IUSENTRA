"""Inline editor routes extracted from the fascicoli monolith."""

from __future__ import annotations

import hashlib
import io
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, url_for

from web.services.security_redaction import redacted_json_response
from web.services.document_edit_policy import motivo_blocco_editor, pdf_studio_modificabile
from web.services.document_word_fonts import SourceFontCoverageError
from web.services.editor_document_indexing import indicizza_salvataggio_editor as _indicizza_salvataggio_editor


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

    from web.bootstrap.editor_language_export_routes import register_editor_language_export_routes

    register_editor_language_export_routes(app, get_fascicoli=get_fascicoli, audit=audit)
    from web.bootstrap.editor_new_document_routes import register_editor_new_document_routes

    register_editor_new_document_routes(app, get_fascicoli=get_fascicoli, audit=audit, encrypt_doc=encrypt_doc)
    from web.bootstrap.editor_linked_fields_routes import register_editor_linked_fields_routes

    linked_context = register_editor_linked_fields_routes(app, get_fascicoli=get_fascicoli)
    from web.bootstrap.editor_personal_template_routes import register_editor_personal_template_routes

    register_editor_personal_template_routes(app, audit=audit, resolve_context=linked_context)

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

    def _registra_documento_aggiornato(id_fasc: str, documento: Any) -> None:
        try:
            from web.services.registro_letture_runtime import documento_aggiornato

            documento_aggiornato(id_fasc, documento)
        except Exception as exc:
            app.logger.debug("Registro letture non aggiornato per %s: %s", id_fasc, exc)

    def _percorso_documento_lettura(gestore_fascicoli: Any, id_fasc: str, id_doc: str) -> Path:
        resolver = getattr(gestore_fascicoli, "percorso_documento_lettura", None)
        if callable(resolver):
            return Path(resolver(id_fasc, id_doc))
        return Path(gestore_fascicoli.percorso_documento(id_fasc, id_doc))

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

    from web.bootstrap.editor_finalize_routes import register_editor_finalize_routes

    def _editor_tenant_timbro():
        from pct.postgres_runtime_support import database_config_to_dsn, resolve_runtime_postgres_dsn
        from pct.studio_timbro import build_studio_timbro

        tenant = getattr(g, 'tenant', None)
        dsn = database_config_to_dsn(getattr(tenant, 'database', None)) if tenant is not None else resolve_runtime_postgres_dsn()
        if tenant is not None and not dsn and resolve_runtime_postgres_dsn():
            raise RuntimeError('Archivio timbro dello studio non disponibile')
        return build_studio_timbro(db_path=_cfg_data_path('STUDIO_TIMBRO_DB'), config_studio=getattr(g, 'config_studio', None), app_config=app.config, postgres_dsn=dsn)

    register_editor_finalize_routes(app, get_fascicoli=get_fascicoli, audit=audit, encrypt_doc=encrypt_doc, get_timbro=_editor_tenant_timbro)

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/editor")
    def editor_documento(id_fasc, id_doc):
        from pct.editor import estensione_editabile

        gestore_fascicoli = get_fascicoli()
        try:
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None) if fascicolo else None
            # Firmati e buste .p7m si aprono nell'editor React in «modifica su copia»:
            # l'originale resta intatto. La vista classica non la gestisce.
            if documento and _richiede_vista_classica() and (documento.firmato_digitalmente or documento.nome.lower().endswith(".p7m")):
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
            if str(getattr(documento, "fonte_documento", "") or "").strip().upper() == "PORTALE_TELEMATICO":
                msg = "Il documento acquisito dal portale viene conservato nella forma ricevuta e non può essere riconvertito."
                if _wants_json_response():
                    return jsonify({"ok": False, "messaggio": msg}), 400
                flash(msg, "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            if bool(getattr(documento, "firmato_digitalmente", False)):
                msg = "Il documento è già firmato e non può essere riconvertito."
                if _wants_json_response():
                    return jsonify({"ok": False, "messaggio": msg}), 400
                flash(msg, "warning")
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            percorso = gestore_fascicoli.percorso_documento_lettura(id_fasc, id_doc)
            contenuto_originale = decrypt_doc(percorso.read_bytes())
            with tempfile.TemporaryDirectory(prefix="iusentra-pdfa-") as tmp_dir:
                temp_path = Path(tmp_dir) / Path(documento.nome).name
                temp_path.write_bytes(contenuto_originale)
                esito = converti_pdfa(str(temp_path))
                contenuto_convertito = temp_path.read_bytes() if esito.get("ok") else b""
            if esito["ok"]:
                from pct.validazione import verifica_pdfa

                with tempfile.TemporaryDirectory(prefix="iusentra-pdfa-") as tmp_dir:
                    controllo_path = Path(tmp_dir) / "convertito.pdf"
                    controllo_path.write_bytes(contenuto_convertito)
                    controllo = verifica_pdfa(str(controllo_path))
                if not controllo.get("conforme"):
                    msg = "La conversione non ha prodotto un PDF/A riconoscibile: il documento non è stato modificato."
                    if _wants_json_response():
                        return jsonify({"ok": False, "messaggio": msg}), 422
                    flash(msg, "warning")
                    return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
                utente = getattr(g, "utente_corrente", None)
                gestore_fascicoli.sostituisci_documento(
                    id_fasc,
                    id_doc,
                    nome_file=documento.nome,
                    contenuto=encrypt_doc(contenuto_convertito),
                    caricato_da=getattr(utente, "username", "") or "conversione PDF/A",
                    note="Convertito in PDF/A-2B",
                    preserve_version_snapshot=True,
                    hash_contenuto_sha256=hashlib.sha256(contenuto_convertito).hexdigest(),
                )
                versione = str(controllo.get("versione") or "PDF/A-2B")
                documento_aggiornato = next((d for d in gestore_fascicoli.get(id_fasc).documenti if d.id == id_doc), documento)
                gestore_fascicoli.aggiorna_documento_metadati(
                    id_fasc, id_doc, tags=[*(getattr(documento_aggiornato, "tags", []) or []), versione])
                msg = f"Documento convertito in {versione}: la versione precedente resta nello storico del documento."
                from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache

                clear_react_fascicoli_list_cache()
                flash(msg, "success")
                audit(
                    "documento.converti_pdfa",
                    "fascicolo",
                    id_fasc,
                    dettagli=f"doc {id_doc} - {documento.nome}",
                )
                if _wants_json_response():
                    return jsonify({"ok": True, "messaggio": msg})
            else:
                msg = str(esito.get("messaggio") or "Conversione PDF/A non riuscita.")
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
            percorso = _percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            raw = decrypt_doc(percorso.read_bytes())
            html, avvisi, meta = documento_to_html(raw, documento.nome)
            return redacted_json_response({"ok": True, "html": html, "avvisi": avvisi, "nome": documento.nome, "meta": meta})
        except Exception as exc:
            app.logger.exception("Errore api_editor_carica_html: %s", exc)
            return jsonify({"ok": False, "html": "<p>Documento non caricato.</p>", "avvisi": ["Documento non caricato."], "meta": {}})

    @app.route("/api/editor/<id_fasc>/<id_doc>/salva", methods=["POST"])
    def api_editor_salva(id_fasc, id_doc):
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
            if ext == "pdf":
                return jsonify(
                    {
                        "ok": False,
                        "errore": (
                            "Il PDF resta in anteprima nativa: l'editor non lo ricostruisce "
                            "in HTML per non alterare il documento originale."
                        ),
                    }
                ), 409

            blocco = motivo_blocco_editor(documento)
            if blocco:
                return jsonify({"ok": False, "errore": blocco}), 403

            # Il salvataggio riproduce il contenuto dell'editor: la carta
            # intestata si inserisce nella redazione, non durante l'export.
            from pct.editor_export import esporta_documento_editor
            from web.services.editor_word_source import editor_word_source
            contenuto_raw = esporta_documento_editor(html, formato='docx', titolo=nome.rsplit(".", 1)[0],
                fonte_word=editor_word_source(gestore_fascicoli, id_fasc, documento, decrypt_doc))
            nome_salvato = (nome.rsplit(".", 1)[0] if "." in nome else nome) + ".docx"

            doc_salvato = gestore_fascicoli.sostituisci_documento(
                id_fasc,
                id_doc,
                nome_file=nome_salvato,
                contenuto=encrypt_doc(contenuto_raw),
                caricato_da=utente.username if utente else "editor",
                note="Salvato dall'editor" + (" (auto)" if auto else ""),
                hash_contenuto_sha256=hashlib.sha256(contenuto_raw).hexdigest(),
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
            _registra_documento_aggiornato(id_fasc, doc_salvato)
            _indicizza_salvataggio_editor(
                id_fasc=id_fasc,
                document_id=doc_salvato.id,
                filename=nome_salvato,
                content=contenuto_raw,
            )
            audit("fascicoli.documento.editor_salva", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {nome}")
            return jsonify({"ok": True, "auto": auto, "nome": nome_salvato, "formato": "docx"})
        except SourceFontCoverageError as error:
            return jsonify({"ok": False, "errore": str(error)}), 422
        except Exception as exc:
            app.logger.exception("Errore api_editor_salva: %s", exc)
            return jsonify({"ok": False, "errore": "Documento non salvato."})

    @app.route("/api/editor/<id_fasc>/<id_doc>/anteprima-stampa", methods=["POST"])
    @app.route("/api/editor/<id_fasc>/<id_doc>/pdf", methods=["POST"])
    def api_editor_pdf(id_fasc, id_doc):
        try:
            body = request.get_json(force=True) or {}
            html = body.get("html", "<p></p>")
            gestore_fascicoli = get_fascicoli()
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            titolo = documento.nome.rsplit(".", 1)[0] if documento else "documento"
            if documento and Path(documento.nome).suffix.lower() == ".pdf":
                percorso = _percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
                contenuto_originale = decrypt_doc(percorso.read_bytes())
                audit("fascicoli.documento.editor_pdf_originale", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
                if request.path.endswith("/anteprima-stampa"):
                    from pct.editor_export import anteprima_stampa_pdf
                    return app.response_class(anteprima_stampa_pdf(contenuto_originale), mimetype="text/html")
                return send_file(
                    io.BytesIO(contenuto_originale),
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name=documento.nome,
                )
            from pct.editor_export import esporta_documento_editor

            from web.services.editor_word_source import editor_word_source
            pdf_bytes = esporta_documento_editor(html, formato="pdf", titolo=titolo,
                fonte_word=editor_word_source(gestore_fascicoli, id_fasc, documento, decrypt_doc))
            audit("fascicoli.documento.editor_pdf", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
            if request.path.endswith("/anteprima-stampa"):
                from pct.editor_export import anteprima_stampa_pdf
                return app.response_class(anteprima_stampa_pdf(pdf_bytes), mimetype="text/html")
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=titolo + ".pdf",
            )
        except ImportError:
            return jsonify({"errore": "Generazione PDF non disponibile."}), 503
        except SourceFontCoverageError as error:
            return jsonify({"errore": str(error)}), 422
        except Exception as exc:
            app.logger.exception("Errore api_editor_pdf: %s", exc)
            return "Generazione PDF non completata.", 500

    @app.route("/api/editor/<id_fasc>/<id_doc>/pdf-meta")
    def api_editor_pdf_meta(id_fasc, id_doc):
        from web.services.pdf_overlay_editor import PdfOverlayError, pdf_page_infos

        gestore_fascicoli = get_fascicoli()
        try:
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                return jsonify({"ok": False, "errore": "Documento non disponibile."}), 404
            lavoro = _pdf_di_lavoro(gestore_fascicoli, id_fasc, id_doc, documento)
            pdf_bytes = lavoro.dati
            pages = [
                {"number": info.number, "width": info.width, "height": info.height}
                for info in pdf_page_infos(pdf_bytes)
            ]
            return jsonify({"ok": True, "pageCount": len(pages), "pages": pages, "origine": lavoro.origine,
                            "soloCopia": lavoro.solo_copia, "nomeCopia": lavoro.nome_copia})
        except PdfOverlayError as exc:
            return jsonify({"ok": False, "errore": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore api_editor_pdf_meta: %s", exc)
            return jsonify({"ok": False, "errore": "Metadati PDF non disponibili."}), 500

    @app.route("/api/editor/<id_fasc>/<id_doc>/pdf-pagina/<int:page_number>.png")
    def api_editor_pdf_pagina_png(id_fasc, id_doc, page_number: int):
        from web.services.pdf_overlay_editor import PdfOverlayError, render_pdf_page_png

        gestore_fascicoli = get_fascicoli()
        try:
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                return jsonify({"ok": False, "errore": "Documento non disponibile."}), 404
            png_bytes = render_pdf_page_png(_pdf_di_lavoro(gestore_fascicoli, id_fasc, id_doc, documento).dati, page_number=page_number)
            return send_file(io.BytesIO(png_bytes), mimetype="image/png", as_attachment=False)
        except PdfOverlayError as exc:
            return jsonify({"ok": False, "errore": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore api_editor_pdf_pagina_png: %s", exc)
            return jsonify({"ok": False, "errore": "Pagina PDF non renderizzata."}), 500

    def _pdf_di_lavoro(gestore_fascicoli, id_fasc, id_doc, documento):
        """Il PDF su cui lavora l'editor: il PDF stesso, quello dentro la busta .p7m o l'email impaginata."""
        from web.services.pdf_modificabile import DocumentoNonConvertibile, pdf_di_lavoro
        from web.services.pdf_overlay_editor import PdfOverlayError

        percorso = _percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
        try:
            return pdf_di_lavoro(
                documento, decrypt_doc(percorso.read_bytes()),
                originale_modificabile=pdf_studio_modificabile(documento), studio_timbro=_current_studio_timbro(),
            )
        except DocumentoNonConvertibile as exc:
            raise PdfOverlayError(str(exc)) from exc

    def _nome_della_copia(nome: str, fascicolo) -> str:
        """Un nome che dice che e' una copia, e che nel fascicolo non c'e' gia'.

        Chiamarla come l'originale, in un fascicolo, e' il modo piu' rapido per
        depositare quella sbagliata: due file con lo stesso nome e nessuno che
        si ricorda quale porta gli omissis.
        """
        radice = Path(nome or "documento.pdf")
        gambo = radice.stem or "documento"
        coda = radice.suffix or ".pdf"
        presi = {str(getattr(d, "nome", "")).lower()
                 for d in (getattr(fascicolo, "documenti", None) or [])}
        proposta = f"{gambo} (copia){coda}"
        numero = 2
        while proposta.lower() in presi:
            proposta = f"{gambo} (copia {numero}){coda}"
            numero += 1
        return proposta

    @app.route("/api/editor/<id_fasc>/<id_doc>/pdf-overlay", methods=["POST"])
    def api_editor_pdf_overlay(id_fasc, id_doc):
        from web.services.pdf_overlay_editor import PdfOverlayError, apply_pdf_overlays

        gestore_fascicoli = get_fascicoli()
        utente = g.utente_corrente
        try:
            body = request.get_json(force=True) or {}
            annotations = body.get("annotations") or []
            if not isinstance(annotations, list):
                return jsonify({"ok": False, "errore": "Modifiche PDF non valide."}), 400
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                return jsonify({"ok": False, "errore": "Documento non disponibile."}), 404
            lavoro = _pdf_di_lavoro(gestore_fascicoli, id_fasc, id_doc, documento)
            contenuto_raw, count = apply_pdf_overlays(lavoro.dati, annotations)

            # Dove finisce il risultato. Sovrascrivere e' comodo finche' si
            # aggiunge un timbro; per una copia da mandare a qualcuno, o per
            # una versione con gli omissis, l'originale deve restare dov'e'.
            destinazione = str(body.get("destinazione") or "versione").strip().lower()
            if destinazione not in ("versione", "copia", "scarica"):
                destinazione = "versione"
            if destinazione == "versione" and lavoro.solo_copia:
                # Firmati, buste .p7m, email e documenti arrivati da portali o PEC
                # sono prove: l'originale non si sostituisce, il lavoro va in copia.
                destinazione = "copia"

            if destinazione == "scarica":
                audit("fascicoli.documento.editor_pdf_overlay", "fascicolo", id_fasc,
                      dettagli=f"doc {id_doc} — {count} interventi scaricati")
                return send_file(
                    io.BytesIO(contenuto_raw),
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name=_nome_della_copia(lavoro.nome_copia, fascicolo),
                )

            if destinazione == "copia":
                doc_salvato = gestore_fascicoli.aggiungi_documento(
                    id_fasc,
                    nome_file=_nome_della_copia(lavoro.nome_copia, fascicolo),
                    tipo=documento.tipo,
                    contenuto=encrypt_doc(contenuto_raw),
                    note=f"Copia con {count} interventi dell'editor PDF sicuro.",
                    caricato_da=utente.username if utente else "editor_pdf",
                    hash_contenuto_sha256=hashlib.sha256(contenuto_raw).hexdigest(),
                )
            else:
                doc_salvato = gestore_fascicoli.sostituisci_documento(
                    id_fasc,
                    id_doc,
                    nome_file=documento.nome,
                    contenuto=encrypt_doc(contenuto_raw),
                    caricato_da=utente.username if utente else "editor_pdf",
                    note=f"Modificato con editor PDF sicuro: {count} interventi overlay.",
                    hash_contenuto_sha256=hashlib.sha256(contenuto_raw).hexdigest(),
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
            _registra_documento_aggiornato(id_fasc, doc_salvato)
            _indicizza_salvataggio_editor(
                id_fasc=id_fasc,
                document_id=doc_salvato.id,
                filename=doc_salvato.nome,
                content=contenuto_raw,
            )
            audit("fascicoli.documento.editor_pdf_overlay", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {count} interventi")
            return jsonify(
                {
                    "ok": True,
                    "annotations": count,
                    "message": (
                        f"Copia creata nel fascicolo: {doc_salvato.nome}."
                        if destinazione == "copia"
                        else "PDF salvato come nuova versione con modifiche native a overlay."
                    ),
                    "destinazione": destinazione,
                    "documento": {
                        "id": doc_salvato.id,
                        "nome": doc_salvato.nome,
                        "hash": doc_salvato.hash_sha256,
                        "versioni": len(getattr(doc_salvato, "versioni", []) or []),
                    },
                }
            )
        except PdfOverlayError as exc:
            return jsonify({"ok": False, "errore": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore api_editor_pdf_overlay: %s", exc)
            return jsonify({"ok": False, "errore": "Modifica PDF non salvata."}), 500

    @app.route("/api/editor/<id_fasc>/<id_doc>/importa", methods=["POST"])
    def api_editor_importa(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        utente = getattr(g, "utente_corrente", None)
        try:
            storage = request.files.get("documento") or request.files.get("file")
            if not storage or not getattr(storage, "filename", ""):
                return jsonify({"ok": False, "messaggio": "Seleziona un documento PDF, Word, HTML o testo."}), 400
            filename = str(storage.filename or "").strip()
            extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            allowed = {"pdf", "docx", "doc", "html", "htm", "txt", "md"}
            if extension not in allowed:
                return jsonify({"ok": False, "messaggio": "Formato non supportato dall'anteprima editor."}), 400
            raw = storage.read()
            if not raw:
                return jsonify({"ok": False, "messaggio": "Il documento selezionato è vuoto."}), 400
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                return jsonify({"ok": False, "messaggio": "Documento non trovato."}), 404
            if getattr(documento, "firmato_digitalmente", False) or str(getattr(documento, "nome", "")).lower().endswith(".p7m"):
                return jsonify({"ok": False, "messaggio": "Documento firmato: usa la funzione di sostituzione controllata dal fascicolo."}), 400
            if Path(str(getattr(documento, "nome", ""))).suffix.lower() != ".pdf":
                blocco = motivo_blocco_editor(documento)
                if blocco:
                    return jsonify({"ok": False, "messaggio": blocco}), 403

            doc_salvato = gestore_fascicoli.sostituisci_documento(
                id_fasc,
                id_doc,
                nome_file=filename,
                contenuto=encrypt_doc(raw),
                caricato_da=utente.username if utente else "editor",
                note="Importato nell'anteprima editor",
                hash_contenuto_sha256=hashlib.sha256(raw).hexdigest(),
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
            _registra_documento_aggiornato(id_fasc, doc_salvato)
            _indicizza_salvataggio_editor(
                id_fasc=id_fasc,
                document_id=doc_salvato.id,
                filename=filename,
                content=raw,
            )
            audit("fascicoli.documento.editor_importa", "fascicolo", id_fasc, dettagli=f"doc {id_doc} - {filename}")
            editable_after_import = extension in {"docx", "html", "htm", "txt", "md"}
            message = (
                "Documento importato: puoi modificarlo nell'anteprima."
                if editable_after_import
                else "PDF importato e collegato: resta salvabile come originale se non convertibile in modo affidabile."
            )
            return jsonify(
                {
                    "ok": True,
                    "message": message,
                    "messaggio": message,
                    "documento": {"id": doc_salvato.id, "nome": doc_salvato.nome, "editable": editable_after_import},
                    "reload": True,
                }
            )
        except Exception as exc:
            app.logger.exception("Errore api_editor_importa: %s", exc)
            return jsonify({"ok": False, "messaggio": "Documento non importato nell'editor."}), 500
