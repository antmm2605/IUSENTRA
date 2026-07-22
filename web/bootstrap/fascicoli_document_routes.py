"""Document routes extracted from the fascicoli monolith."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, request, send_file, url_for

from pct.document_management import normalize_document_tags
from pct.document_intelligence.sources import source_from_uploaded_document
from pct.fascicoli import TipoDocumento
from web.bootstrap.fascicoli_document_helpers import (
    applica_modalita_portale,
    classifica_tipo_documento,
    contenuto_portale_bytes,
    estrai_pdf_da_raw,
    mobile_pdf_preview_response,
    mobile_rich_preview_response,
    nome_documento_operativo,
    payload_bool,
    percorso_documento_lettura,
    preview_error_html,
    preview_unavailable_html,
    redirect_to_documenti_section,
    wants_json_response,
)
from web.services.fascicoli_document_rename import rinomina_documento_response
from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache
from web.services.signed_document_runtime import (
    build_document_signed_snapshot_from_bytes,
    build_document_version_candidates,
)


def register_fascicoli_document_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_indice: Callable[[], Any],
    audit: Callable[..., None],
    salva_documento_fascicolo: Callable[..., Any],
    portale_ufficiale_label: Callable[[Any], str],
    espandi_file_importato_portale: Callable[..., list[dict[str, Any]]],
    pst_import_dir_for_fascicolo: Callable[[Any], Any],
    leggi_staging_documenti_portale: Callable[[Any], tuple[list[dict[str, Any]], Any]],
    salva_albero_originale_documenti_portale: Callable[[Any, list[dict[str, Any]]], str],
    importa_documenti_portale_items: Callable[..., dict[str, Any]],
    decode_portale_downloaded_items: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    decrypt_doc: Callable[[bytes], bytes],
    firma_payload_corrente_o_sibling: Callable[[Any, str, bytes], bytes],
    estrai_contenuto_p7m_per_preview: Callable[[bytes], bytes | None],
    nome_preview_documento: Callable[[str], str],
    mime_preview_documento: Callable[[str, bytes], tuple[str, str] | None],
    payload_preview_da_versioni_documento: Callable[[Any, Any], bytes | None],
    applica_timbro_firma_visibile: Callable[[bytes, list[dict[str, Any]], Any], bytes],
) -> None:
    """Register fascicolo document upload, preview, import, and download routes."""

    def _indicizza_documento_lex(
        *,
        id_fasc: str,
        document_id: str,
        filename: str,
        content: bytes,
        source_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
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
                source_type=source_type,
                metadata=metadata or {},
            )
            service = build_document_ai_service()
            service.process_lex_indexing_sources(
                tenant_id,
                id_fasc,
                [source],
                document_ai_user_context(),
                retry_errors=True,
            )
        except Exception as exc:
            app.logger.warning("Indicizzazione Lex non completata per %s/%s: %s", id_fasc, filename, exc)

    @app.route("/fascicoli/<id_fasc>/documenti/carica", methods=["POST"])
    def carica_documento(id_fasc):
        gestore_fascicoli = get_fascicoli()
        files = [
            storage
            for field_name in ("files", "file")
            for storage in request.files.getlist(field_name)
            if storage and storage.filename
        ]
        if not files:
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": "Nessun file selezionato."}), 400
            flash("Nessun file selezionato.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        form = request.form
        utente = g.utente_corrente
        modalita_raw = str(form.get("classificazione_modalita") or form.get("classificazione") or "").strip().lower()
        manuale = modalita_raw == "manuale" or (not modalita_raw and bool(form.get("tipo_doc")))
        documenti_creati = []
        try:
            for index, storage in enumerate(files):
                raw = storage.read()
                if not raw:
                    continue
                tipo_value = (
                    form.get(f"tipo_doc_{index}")
                    or form.get(f"tipo_doc_{storage.filename}")
                    or form.get("tipo_doc")
                    or ""
                )
                if manuale and tipo_value:
                    try:
                        tipo_doc = TipoDocumento(tipo_value)
                    except ValueError as exc:
                        raise ValueError("Tipo documento non valido.") from exc
                else:
                    tipo_doc = classifica_tipo_documento(storage.filename)
                documento = salva_documento_fascicolo(
                    gf=gestore_fascicoli,
                    id_fasc=id_fasc,
                    nome_file=storage.filename,
                    raw=raw,
                    tipo_doc=tipo_doc,
                    note=form.get("note", ""),
                    tags=normalize_document_tags(form.get("tags", "")),
                    data_documento=form.get("data_documento", ""),
                    firmato=form.get("firmato") == "1",
                    caricato_da=utente.username if utente else "",
                    fonte_documento="CARICAMENTO_STUDIO",
                    nome_originale=storage.filename,
                )
                documenti_creati.append(documento)
                _indicizza_documento_lex(
                    id_fasc=id_fasc,
                    document_id=getattr(documento, "id", "") or storage.filename,
                    filename=storage.filename,
                    content=raw,
                    source_type="documenti_fascicolo",
                    metadata={
                        "trigger": "upload_documenti_fascicolo",
                        "classificazione_modalita": "manuale" if manuale else "auto",
                        "tipo_documento": tipo_doc.value,
                    },
                )
            if not documenti_creati:
                raise ValueError("I file selezionati sono vuoti o non leggibili.")
            count = len(documenti_creati)
            msg = f"Caricato {count} documento." if count == 1 else f"Caricati {count} documenti."
            flash(msg, "success")
            audit("fascicoli.documento.carica", "fascicolo", id_fasc, dettagli=f"{count} file")
            clear_react_fascicoli_list_cache()
            if wants_json_response():
                return jsonify(
                    {
                        "ok": True,
                        "messaggio": msg,
                        "message": msg,
                        "documento_id": getattr(documenti_creati[0], "id", ""),
                        "documenti_id": [getattr(doc, "id", "") for doc in documenti_creati],
                        "redirect_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#documenti",
                    }
                )
        except (ValueError, KeyError) as exc:
            app.logger.warning("Caricamento documento non valido id_fasc=%s: %s", id_fasc, exc)
            msg = "Documento non caricato. Verifica fascicolo, nome file e formato."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 400
            flash(msg, "danger")
        except Exception as exc:
            app.logger.exception("Errore carica_documento id_fasc=%s: %s", id_fasc, exc)
            msg = "Archivio documenti momentaneamente occupato. Riprova tra pochi secondi."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 503
            flash(msg, "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/metadati", methods=["POST"])
    def aggiorna_metadati_documento(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        try:
            gestore_fascicoli.aggiorna_documento_metadati(
                id_fasc,
                id_doc,
                note=request.form.get("note"),
                data_documento=request.form.get("data_documento"),
                tags=normalize_document_tags(request.form.get("tags", "")),
            )
            audit(
                "fascicoli.documento.metadati",
                "fascicolo",
                id_fasc,
                dettagli=f"doc {id_doc}",
            )
            flash("Metadati documento aggiornati.", "success")
            clear_react_fascicoli_list_cache()
        except Exception as exc:
            app.logger.exception(
                "Errore aggiorna_metadati_documento id_fasc=%s id_doc=%s: %s",
                id_fasc,
                id_doc,
                exc,
            )
            flash("Impossibile aggiornare i metadati del documento. Verifica i dati e riprova.", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc, focus="documenti"))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/rinomina", methods=["POST"])
    def rinomina_documento(id_fasc, id_doc):
        response = rinomina_documento_response(
            app=app,
            get_fascicoli=get_fascicoli,
            audit=audit,
            wants_json=wants_json_response,
            id_fasc=id_fasc,
            id_doc=id_doc,
        )
        clear_react_fascicoli_list_cache()
        return response

    @app.route("/fascicoli/<id_fasc>/documenti/importa-portale", methods=["POST"])
    def importa_documenti_portale(id_fasc):
        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        fonte = portale_ufficiale_label(fascicolo)
        note_importazione = (request.form.get("note_importazione", "") or "").strip()
        mantieni_albero_originale = payload_bool(request.form.get("mantieni_albero_originale"), False)
        scarica_originale_portale = payload_bool(request.form.get("scarica_originale_portale"), False)
        uploaded_items: list[dict[str, Any]] = []

        for storage in request.files.getlist("files"):
            if not storage or not storage.filename:
                continue
            payload = storage.read()
            if not payload:
                continue
            uploaded_items.extend(
                espandi_file_importato_portale(
                    nome_file=storage.filename,
                    contenuto=payload,
                    data_documento=date.today().isoformat(),
                    origine=f"upload:{storage.filename}",
                )
            )

        staging_items: list[dict[str, Any]] = []
        staging_dir = pst_import_dir_for_fascicolo(fascicolo)
        usa_staging = not uploaded_items
        if usa_staging:
            staging_items, staging_dir = leggi_staging_documenti_portale(fascicolo)

        items = applica_modalita_portale(
            uploaded_items or staging_items,
            scarica_originale=scarica_originale_portale,
        )
        if not items:
            if wants_json_response():
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": f"Nessun file ufficiale trovato. Seleziona i download del {fonte} oppure riprova dopo averli copiati nella inbox tecnica del fascicolo.",
                    }
                ), 400
            flash(
                f"Nessun file ufficiale trovato. Seleziona i download del {fonte} oppure riprova dopo averli copiati nella inbox tecnica del fascicolo.",
                "warning",
            )
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        try:
            albero_originale_salvato = ""
            if mantieni_albero_originale and uploaded_items:
                albero_originale_salvato = salva_albero_originale_documenti_portale(fascicolo, uploaded_items)
            esito_import = importa_documenti_portale_items(
                gf=gestore_fascicoli,
                fasc=fascicolo,
                items=items,
                note_importazione=note_importazione,
                usa_staging=usa_staging,
                staging_dir=staging_dir if usa_staging else None,
            )
            for index, item in enumerate(items):
                _indicizza_documento_lex(
                    id_fasc=id_fasc,
                    document_id=str(item.get("id_documento_portale") or item.get("id_documento") or item.get("origine") or index),
                    filename=str(item.get("nome") or item.get("nome_file_originale") or f"documento-portale-{index}.pdf"),
                    content=contenuto_portale_bytes(item),
                    source_type="portale_telematico",
                    metadata={"trigger": "import_portale", "id_deposito_esterno": str(item.get("id_deposito_esterno") or "")},
                )
            agganciati = len(esito_import["depositi_agganciati"])
            msg = f"Importati {esito_import['documenti_importati']} file ufficiali da {fonte}."
            if agganciati:
                msg += f" {agganciati} deposit" + ("o ufficiale aggiornato." if agganciati == 1 else "i ufficiali aggiornati.")
            if esito_import["lotto_generico"]:
                msg += " Alcuni file sono stati registrati in un lotto documentale locale."
            if esito_import["staging_archived"]:
                msg += " Inbox temporanea archiviata."
            if albero_originale_salvato:
                msg += " Albero tecnico originale archiviato."
            flash(msg, "success")
            clear_react_fascicoli_list_cache()
            if wants_json_response():
                return jsonify(
                    {
                        "ok": True,
                        "messaggio": msg,
                        "documenti_importati": esito_import["documenti_importati"],
                        "depositi_agganciati": agganciati,
                        "redirect_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#documenti",
                    }
                )
        except (ValueError, KeyError) as exc:
            app.logger.warning("Import documenti portale non valido %s: %s", id_fasc, exc)
            msg = "Importazione non completata. Verifica file selezionati e fascicolo."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 400
            flash(msg, "danger")
        except Exception as exc:
            app.logger.exception("Errore importa_documenti_portale %s: %s", id_fasc, exc)
            msg = "Importazione file ufficiali non completata. Verifica il pacchetto e riprova."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 500
            flash(msg, "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/api/fascicoli/<id_fasc>/documenti/importa-portale", methods=["POST"])
    def api_importa_documenti_portale(id_fasc):
        try:
            gestore_fascicoli = get_fascicoli()
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 200

            data = request.get_json(silent=True) or {}
            note_importazione = (data.get("note_importazione", "") or "").strip()
            mantieni_albero_originale = bool(data.get("mantieni_albero_originale"))
            scarica_originale_portale = payload_bool(data.get("scarica_originale_portale"), False)
            items = applica_modalita_portale(
                decode_portale_downloaded_items(data.get("files") or []),
                scarica_originale=scarica_originale_portale,
            )

            if not items:
                return jsonify({"ok": False, "errore": "Nessun file valido ricevuto dal Local Signer."}), 200

            albero_originale_salvato = ""
            if mantieni_albero_originale:
                albero_originale_salvato = salva_albero_originale_documenti_portale(fascicolo, items)

            esito_import = importa_documenti_portale_items(
                gf=gestore_fascicoli,
                fasc=fascicolo,
                items=items,
                note_importazione=note_importazione,
            )
            for index, item in enumerate(items):
                _indicizza_documento_lex(
                    id_fasc=id_fasc,
                    document_id=str(item.get("id_documento_portale") or item.get("id_documento") or item.get("origine") or index),
                    filename=str(item.get("nome") or item.get("nome_file_originale") or f"documento-portale-{index}.pdf"),
                    content=contenuto_portale_bytes(item),
                    source_type="portale_telematico",
                    metadata={"trigger": "api_import_portale", "id_deposito_esterno": str(item.get("id_deposito_esterno") or "")},
                )
            clear_react_fascicoli_list_cache()
            return (
                jsonify(
                    {
                        "ok": True,
                        "documenti_importati": esito_import["documenti_importati"],
                        "depositi_agganciati": len(esito_import["depositi_agganciati"]),
                        "lotto_generico": esito_import["lotto_generico"],
                        "albero_originale_salvato": bool(albero_originale_salvato),
                        "redirect_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc),
                    }
                ),
                200,
            )
        except (ValueError, KeyError) as exc:
            app.logger.warning("API import documenti portale non valido %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": "Importazione non completata. Verifica file selezionati e fascicolo."}), 200
        except Exception as exc:
            app.logger.exception("Errore api_importa_documenti_portale %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": "Importazione file ufficiali non completata. Verifica il pacchetto e riprova."}), 200

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/scarica")
    def scarica_documento(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        try:
            percorso = percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            data = decrypt_doc(percorso.read_bytes())
            download_name = nome_documento_operativo(documento, percorso, data)
            audit("fascicoli.documento.scarica", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {documento.nome}")
            return send_file(io.BytesIO(data), as_attachment=True, download_name=download_name)
        except Exception as exc:
            app.logger.exception("Errore scarica_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            flash("Impossibile scaricare il documento. Verifica il fascicolo e riprova.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/visualizza")
    def visualizza_documento(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        try:
            percorso = percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            data = decrypt_doc(percorso.read_bytes())
            operational_name = nome_documento_operativo(documento, percorso, data)
            if payload_bool(request.args.get("download"), False):
                audit(
                    "fascicoli.documento.scarica",
                    "fascicolo",
                    id_fasc,
                    dettagli=f"doc {id_doc} — {documento.nome}",
                )
                return send_file(io.BytesIO(data), as_attachment=True, download_name=operational_name)
            firma_payload = firma_payload_corrente_o_sibling(percorso, operational_name, data)
            preview_payload = data
            preview_name = operational_name
            lower_name = operational_name.casefold()

            if lower_name.endswith((".xml", ".xml.p7m", ".eml", ".eml.p7m", ".txt", ".txt.p7m")) and request.args.get("viewer") != "mobile":
                from web.services.signed_attachment_preview import build_attachment_preview_payload

                signed_payload = firma_payload if lower_name.endswith(".p7m") else data
                preview_document = build_attachment_preview_payload(
                    nome_file=operational_name,
                    data=signed_payload,
                    mime_salvato="",
                )
                scarica_url = url_for("scarica_documento", id_fasc=id_fasc, id_doc=id_doc)
                if preview_document.unavailable_reason:
                    return preview_unavailable_html(operational_name, scarica_url)
                audit("fascicoli.documento.visualizza", "fascicolo", id_fasc, dettagli=f"doc {id_doc} - {documento.nome}")
                return send_file(
                    io.BytesIO(preview_document.data),
                    mimetype=preview_document.mimetype,
                    as_attachment=False,
                    download_name=preview_document.download_name,
                )

            if lower_name.endswith(".p7m"):
                contenuto_estratto = estrai_contenuto_p7m_per_preview(firma_payload)
                if contenuto_estratto:
                    preview_payload = contenuto_estratto
                    preview_name = nome_preview_documento(documento.nome)
                else:
                    nome_preview = nome_preview_documento(documento.nome)
                    if mime_preview_documento(nome_preview, data):
                        preview_payload = data
                        preview_name = nome_preview
                    else:
                        pdf_raw = estrai_pdf_da_raw(firma_payload)
                        if pdf_raw and pdf_raw.startswith(b"%PDF"):
                            preview_payload = pdf_raw
                            preview_name = nome_preview
                        else:
                            contenuto_versione = payload_preview_da_versioni_documento(gestore_fascicoli, documento)
                            if contenuto_versione:
                                preview_payload = contenuto_versione
                                preview_name = nome_preview

            mobile_response, preview_payload, preview_name = mobile_rich_preview_response(
                preview_payload=preview_payload,
                preview_name=preview_name,
                mime_salvato=(mime_preview_documento(preview_name, preview_payload) or ("", ""))[0],
                id_fasc=id_fasc,
                id_doc=id_doc,
                documento=documento,
                audit=audit,
            )
            if mobile_response is not None:
                return mobile_response

            preview = mime_preview_documento(preview_name, preview_payload)
            if not preview:
                pdf_raw = estrai_pdf_da_raw(data) or estrai_pdf_da_raw(firma_payload)
                if pdf_raw:
                    preview_payload = pdf_raw
                    preview_name = nome_preview_documento(documento.nome) or "documento.pdf"
                    preview = ("application/pdf", preview_name)

            if not preview:
                scarica_url = url_for("scarica_documento", id_fasc=id_fasc, id_doc=id_doc)
                return preview_unavailable_html(documento.nome, scarica_url)

            if operational_name.casefold().endswith(".p7m") and preview_payload.startswith(b"%PDF"):
                try:
                    from pct.firma import analizza_firma_documento

                    firme = analizza_firma_documento(firma_payload, documento.nome)
                except Exception:
                    firme = []
                preview_payload = applica_timbro_firma_visibile(preview_payload, firme, documento)

            mime, nome_download = preview
            if mime == "application/pdf" and request.args.get("viewer") == "mobile":
                mobile_response = mobile_pdf_preview_response(
                    preview_payload=preview_payload,
                    id_fasc=id_fasc,
                    id_doc=id_doc,
                    documento=documento,
                    nome_download=nome_download,
                    audit=audit,
                )
                if mobile_response is not None:
                    return mobile_response
            audit("fascicoli.documento.visualizza", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {documento.nome}")
            return send_file(
                io.BytesIO(preview_payload),
                mimetype=mime,
                as_attachment=False,
                download_name=nome_download,
            )
        except Exception as exc:
            app.logger.exception("Errore visualizza_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            try:
                scarica_url = url_for("scarica_documento", id_fasc=id_fasc, id_doc=id_doc)
            except Exception:
                scarica_url = "#"
            return preview_error_html(scarica_url)

    @app.route("/api/fascicoli/<id_fasc>/documenti/<id_doc>/info-firma")
    def api_info_firma_documento(id_fasc, id_doc):
        if g.utente_corrente is None:
            return jsonify({"firme": [], "errore": "Non autenticato"}), 401
        try:
            gestore_fascicoli = get_fascicoli()
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"firme": [], "errore": "Fascicolo non trovato"}), 404
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                return jsonify({"firme": [], "errore": "Documento non trovato"}), 404
            percorso = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
            data = decrypt_doc(percorso.read_bytes())
            from pct.firma import analizza_firma_documento

            firme = analizza_firma_documento(data, documento.nome)
            signed_snapshot = build_document_signed_snapshot_from_bytes(
                source_name=documento.nome,
                source_path=str(percorso),
                data=data,
                version_candidates=build_document_version_candidates(
                    gestore_fascicoli,
                    documento,
                    decrypt_doc=decrypt_doc,
                ),
            )
            return jsonify(
                {
                    "firme": firme,
                    "nome": documento.nome,
                    "signed_status": (signed_snapshot or {}).get("signed_status"),
                    "signed_ui": (signed_snapshot or {}).get("ui_status"),
                }
            )
        except Exception as exc:
            app.logger.exception("Errore api_info_firma_documento: %s", exc)
            return jsonify({"firme": [], "errore": "Lettura firme non completata. Verifica il documento e riprova."})

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/elimina", methods=["POST"])
    def elimina_documento(id_fasc, id_doc):
        try:
            get_fascicoli().rimuovi_documento(id_fasc, id_doc)
            msg = "Documento eliminato dal fascicolo."
            flash(msg, "success")
            clear_react_fascicoli_list_cache()
            if wants_json_response():
                return jsonify(
                    {
                        "ok": True,
                        "messaggio": msg,
                        "redirect_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#documenti",
                    }
                )
        except KeyError as exc:
            app.logger.warning("Eliminazione documento non valida id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            msg = "Documento non trovato nel fascicolo."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 404
            flash(msg, "danger")
        except Exception as exc:
            app.logger.exception("Errore elimina_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            msg = "Archivio documenti momentaneamente occupato. Riprova tra pochi secondi."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 503
            flash(msg, "danger")
        return redirect_to_documenti_section(id_fasc)

    @app.route("/fascicoli/<id_fasc>/documenti/elimina-multipla", methods=["POST"])
    def elimina_documenti_multipli(id_fasc):
        ids_raw = str(request.form.get("documenti_ids") or "").strip()
        ids_doc = [item.strip() for item in ids_raw.split(",") if item.strip()]
        if not ids_doc:
            flash("Seleziona almeno un documento da eliminare.", "warning")
            return redirect_to_documenti_section(id_fasc)

        gestore_fascicoli = get_fascicoli()
        rimossi = 0
        errori: list[str] = []
        for id_doc in dict.fromkeys(ids_doc):
            try:
                gestore_fascicoli.rimuovi_documento(id_fasc, id_doc)
                rimossi += 1
            except KeyError as exc:
                app.logger.warning("Documento da eliminare non trovato id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
                errori.append("Documento non trovato nel fascicolo.")
            except Exception as exc:
                app.logger.exception("Errore elimina_documenti_multipli id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
                errori.append("Archivio documenti momentaneamente occupato.")

        if rimossi:
            clear_react_fascicoli_list_cache()
            audit(
                "fascicoli.documento.elimina_multipla",
                "fascicolo",
                id_fasc,
                dettagli=f"{rimossi} documenti",
            )
            flash(
                f"{rimossi} document{'o' if rimossi == 1 else 'i'} eliminat{'o' if rimossi == 1 else 'i'} dal fascicolo.",
                "success",
            )
        if errori:
            flash("Alcuni documenti non sono stati eliminati: " + "; ".join(errori[:3]), "warning")
        return redirect_to_documenti_section(id_fasc)
