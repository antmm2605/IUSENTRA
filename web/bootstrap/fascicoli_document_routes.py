"""Document routes extracted from the fascicoli monolith."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, request, send_file, url_for

from pct.document_management import normalize_document_tags
from pct.fascicoli import TipoDocumento
from web.services.signed_document_runtime import (
    build_document_signed_snapshot_from_bytes,
    build_document_version_candidates,
)


def _estrai_pdf_da_raw(data: bytes) -> bytes | None:
    """Cerca il contenuto PDF embedded nei byte raw."""
    idx = data.find(b"%PDF")
    if idx < 0:
        return None
    eof_idx = data.rfind(b"%%EOF")
    if eof_idx > idx:
        return data[idx : eof_idx + 5]
    return data[idx:]


def _preview_unavailable_html(nome_documento: str, scarica_url: str) -> tuple[str, int, dict[str, str]]:
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


def _preview_error_html(scarica_url: str) -> tuple[str, int, dict[str, str]]:
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">'
        '</head><body class="bg-light d-flex align-items-center justify-content-center" style="min-height:100vh">'
        '<div class="text-center p-4">'
        '<i class="bi bi-exclamation-triangle text-warning" style="font-size:3rem"></i>'
        '<h6 class="mt-3 mb-2">Impossibile visualizzare il documento</h6>'
        '<p class="text-muted small mb-3">Si è verificato un errore durante il caricamento.<br>'
        "Scarica il file per visualizzarlo con il programma appropriato.</p>"
        f'<a href="{scarica_url}" class="btn btn-primary btn-sm">'
        '<i class="bi bi-download me-1"></i>Scarica documento</a>'
        "</div></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# Ridefinizione esplicita per garantire testo UTF-8 corretto anche se una copia legacy
# del file contiene stringhe salvate con encoding errato.
def _preview_error_html(scarica_url: str) -> tuple[str, int, dict[str, str]]:
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">'
        '<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">'
        '</head><body class="bg-light d-flex align-items-center justify-content-center" style="min-height:100vh">'
        '<div class="text-center p-4">'
        '<i class="bi bi-exclamation-triangle text-warning" style="font-size:3rem"></i>'
        '<h6 class="mt-3 mb-2">Impossibile visualizzare il documento</h6>'
        '<p class="text-muted small mb-3">Si è verificato un errore durante il caricamento.<br>'
        "Scarica il file per visualizzarlo con il programma appropriato.</p>"
        f'<a href="{scarica_url}" class="btn btn-primary btn-sm">'
        '<i class="bi bi-download me-1"></i>Scarica documento</a>'
        "</div></body></html>"
    )
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


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
    applica_timbro_firma_visibile: Callable[[bytes, list[dict[str, Any]]], bytes],
) -> None:
    """Register fascicolo document upload, preview, import, and download routes."""

    @app.route("/fascicoli/<id_fasc>/documenti/carica", methods=["POST"])
    def carica_documento(id_fasc):
        gestore_fascicoli = get_fascicoli()
        if "file" not in request.files:
            flash("Nessun file selezionato.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        file = request.files["file"]
        if not file.filename:
            flash("Nome file non valido.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        form = request.form
        utente = g.utente_corrente
        try:
            raw = file.read()
            tipo_doc = TipoDocumento(form.get("tipo_doc", "ALTRO"))
            salva_documento_fascicolo(
                gf=gestore_fascicoli,
                id_fasc=id_fasc,
                nome_file=file.filename,
                raw=raw,
                tipo_doc=tipo_doc,
                note=form.get("note", ""),
                tags=normalize_document_tags(form.get("tags", "")),
                data_documento=form.get("data_documento", ""),
                firmato=form.get("firmato") == "1",
                caricato_da=utente.username if utente else "",
            )
            flash(f"Documento '{file.filename}' caricato.", "success")
            audit("fascicoli.documento.carica", "fascicolo", id_fasc, dettagli=f"file: {file.filename}")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
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
        except Exception as exc:
            app.logger.exception(
                "Errore aggiorna_metadati_documento id_fasc=%s id_doc=%s: %s",
                id_fasc,
                id_doc,
                exc,
            )
            flash(f"Impossibile aggiornare i metadati del documento: {exc}", "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc, focus="documenti"))

    @app.route("/fascicoli/<id_fasc>/documenti/importa-portale", methods=["POST"])
    def importa_documenti_portale(id_fasc):
        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        fonte = portale_ufficiale_label(fascicolo)
        note_importazione = (request.form.get("note_importazione", "") or "").strip()
        mantieni_albero_originale = str(request.form.get("mantieni_albero_originale") or "").strip().lower() in {
            "1",
            "true",
            "on",
            "si",
            "yes",
        }
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

        items = uploaded_items or staging_items
        if not items:
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
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        except Exception as exc:
            app.logger.exception("Errore importa_documenti_portale %s: %s", id_fasc, exc)
            flash(f"Errore importazione file ufficiali: {exc}", "danger")
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
            items = decode_portale_downloaded_items(data.get("files") or [])

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
            return jsonify({"ok": False, "errore": str(exc)}), 200
        except Exception as exc:
            app.logger.exception("Errore api_importa_documenti_portale %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/scarica")
    def scarica_documento(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        try:
            percorso = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            data = decrypt_doc(percorso.read_bytes())
            audit("fascicoli.documento.scarica", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {documento.nome}")
            return send_file(io.BytesIO(data), as_attachment=True, download_name=documento.nome)
        except Exception as exc:
            app.logger.exception("Errore scarica_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            flash(f"Impossibile scaricare il documento: {exc}", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/visualizza")
    def visualizza_documento(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        try:
            percorso = gestore_fascicoli.percorso_documento(id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            data = decrypt_doc(percorso.read_bytes())
            firma_payload = firma_payload_corrente_o_sibling(percorso, documento.nome, data)
            preview_payload = data
            preview_name = documento.nome

            if documento.nome.lower().endswith(".p7m"):
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
                        pdf_raw = _estrai_pdf_da_raw(firma_payload)
                        if pdf_raw and pdf_raw.startswith(b"%PDF"):
                            preview_payload = pdf_raw
                            preview_name = nome_preview
                        else:
                            contenuto_versione = payload_preview_da_versioni_documento(gestore_fascicoli, documento)
                            if contenuto_versione:
                                preview_payload = contenuto_versione
                                preview_name = nome_preview

            preview = mime_preview_documento(preview_name, preview_payload)
            if not preview:
                pdf_raw = _estrai_pdf_da_raw(data) or _estrai_pdf_da_raw(firma_payload)
                if pdf_raw:
                    preview_payload = pdf_raw
                    preview_name = nome_preview_documento(documento.nome) or "documento.pdf"
                    preview = ("application/pdf", preview_name)

            if not preview:
                scarica_url = url_for("scarica_documento", id_fasc=id_fasc, id_doc=id_doc)
                return _preview_unavailable_html(documento.nome, scarica_url)

            if documento.nome.lower().endswith(".p7m") and preview_payload.startswith(b"%PDF"):
                try:
                    from pct.firma import analizza_firma_documento

                    firme = analizza_firma_documento(firma_payload, documento.nome)
                except Exception:
                    firme = []
                preview_payload = applica_timbro_firma_visibile(preview_payload, firme)

            mime, nome_download = preview
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
            return _preview_error_html(scarica_url)

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
            return jsonify({"firme": [], "errore": str(exc)})

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/elimina", methods=["POST"])
    def elimina_documento(id_fasc, id_doc):
        try:
            get_fascicoli().rimuovi_documento(id_fasc, id_doc)
            flash("Documento eliminato.", "success")
        except KeyError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
