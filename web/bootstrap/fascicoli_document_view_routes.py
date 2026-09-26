"""Rotte di consultazione dei documenti del fascicolo.

Scaricare, visualizzare in anteprima e leggere le firme di un documento sono
una responsabilita' sola — mostrare all'avvocato cio' che il fascicolo gia'
contiene — e stanno qui, separate dal caricamento e dall'import di portale.
Ogni consultazione lascia il suo riscontro nel registro operativo.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

from flask import Flask, abort, flash, g, jsonify, redirect, request, send_file, url_for

from web.bootstrap.fascicoli_document_helpers import (
    estrai_pdf_da_raw,
    mobile_pdf_preview_response,
    mobile_rich_preview_response,
    nome_documento_operativo,
    payload_bool,
    percorso_documento_lettura,
    preview_error_html,
    preview_unavailable_html,
)
from web.services.signed_document_runtime import (
    build_document_signed_snapshot_from_bytes,
    build_document_version_candidates,
)


def register_fascicoli_document_view_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_practice_engine: Callable[[], Any],
    audit: Callable[..., None],
    decrypt_doc: Callable[[bytes], bytes],
    firma_payload_corrente_o_sibling: Callable[[Any, str, bytes], bytes],
    estrai_contenuto_p7m_per_preview: Callable[[bytes], bytes | None],
    nome_preview_documento: Callable[[str], str],
    mime_preview_documento: Callable[[str, bytes], tuple[str, str] | None],
    payload_preview_da_versioni_documento: Callable[[Any, Any], bytes | None],
    applica_timbro_firma_visibile: Callable[[bytes, list[dict[str, Any]], Any], bytes],
) -> None:
    """Registra scarico, anteprima e informazioni di firma di un documento."""
    def _record_document_operational_audit(
        *,
        fascicolo_id: str,
        document_id: str,
        documento: Any,
        event_type: str,
    ) -> None:
        """Registra un riscontro SQL di consultazione senza fingere prova WORM."""
        try:
            utente = getattr(g, "utente_corrente", None)
            actor = str(
                getattr(utente, "username", "")
                or getattr(utente, "id", "")
                or ""
            ).strip()
            nome = str(getattr(documento, "nome", "") or "Documento del fascicolo").strip()
            action = "download" if event_type == "DOC_DOWNLOADED" else "view"
            label = "Documento scaricato" if action == "download" else "Documento consultato"
            get_practice_engine().audit(
                str(fascicolo_id or ""),
                event_type,
                actor=actor,
                message=f"{label}: {nome}",
                payload={
                    "document_id": str(document_id or ""),
                    "document_name": nome,
                    "source_action": action,
                },
            )
        except Exception as exc:
            # Il documento già autorizzato deve restare fruibile anche se il
            # solo registro operativo è temporaneamente indisponibile.
            app.logger.warning(
                "Audit operativo documento non registrato %s/%s: %s",
                fascicolo_id,
                document_id,
                exc,
            )

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/scarica")
    def scarica_documento(id_fasc, id_doc):
        utente = getattr(g, "utente_corrente", None)
        if utente is None or not utente.ha_permesso("fascicoli.leggi"):
            abort(403)
        gestore_fascicoli = get_fascicoli()
        try:
            percorso = percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            data = decrypt_doc(percorso.read_bytes())
            download_name = nome_documento_operativo(documento, percorso, data)
            _record_document_operational_audit(
                fascicolo_id=id_fasc,
                document_id=id_doc,
                documento=documento,
                event_type="DOC_DOWNLOADED",
            )
            audit("fascicoli.documento.scarica", "fascicolo", id_fasc, dettagli=f"doc {id_doc} — {documento.nome}")
            return send_file(io.BytesIO(data), as_attachment=True, download_name=download_name)
        except Exception as exc:
            app.logger.exception("Errore scarica_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            flash("Impossibile scaricare il documento. Verifica il fascicolo e riprova.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/visualizza")
    def visualizza_documento(id_fasc, id_doc):
        utente = getattr(g, "utente_corrente", None)
        if utente is None or not utente.ha_permesso("fascicoli.leggi"):
            abort(403)
        gestore_fascicoli = get_fascicoli()
        try:
            percorso = percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
            fascicolo = gestore_fascicoli.get(id_fasc)
            documento = next(doc for doc in fascicolo.documenti if doc.id == id_doc)
            data = decrypt_doc(percorso.read_bytes())
            operational_name = nome_documento_operativo(documento, percorso, data)
            if payload_bool(request.args.get("download"), False):
                _record_document_operational_audit(
                    fascicolo_id=id_fasc,
                    document_id=id_doc,
                    documento=documento,
                    event_type="DOC_DOWNLOADED",
                )
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
                _record_document_operational_audit(
                    fascicolo_id=id_fasc,
                    document_id=id_doc,
                    documento=documento,
                    event_type="DOC_VIEWED",
                )
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
                if not request.args.get("page"):
                    _record_document_operational_audit(
                        fascicolo_id=id_fasc,
                        document_id=id_doc,
                        documento=documento,
                        event_type="DOC_VIEWED",
                    )
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
                    if not request.args.get("page"):
                        _record_document_operational_audit(
                            fascicolo_id=id_fasc,
                            document_id=id_doc,
                            documento=documento,
                            event_type="DOC_VIEWED",
                        )
                    return mobile_response
            _record_document_operational_audit(
                fascicolo_id=id_fasc,
                document_id=id_doc,
                documento=documento,
                event_type="DOC_VIEWED",
            )
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


__all__ = ["register_fascicoli_document_view_routes"]
