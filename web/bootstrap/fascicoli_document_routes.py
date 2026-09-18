"""Caricamento e modifica dei documenti del fascicolo.

Qui restano il caricamento manuale, i metadati, la rinomina e la rotazione.
Le altre responsabilita' hanno un modulo proprio: l'import dai portali in
`fascicoli_document_import_routes`, la consultazione (scarico, anteprima,
firme) in `fascicoli_document_view_routes`, il cestino in
`fascicoli_document_trash_routes`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, request, url_for

from pct.document_management import normalize_document_tags
from pct.fascicoli import TipoDocumento
from web.bootstrap.fascicoli_document_helpers import (
    classifica_tipo_documento,
    nome_documento_operativo,
    percorso_documento_lettura,
    wants_json_response,
)
from web.bootstrap.fascicoli_document_import_routes import register_fascicoli_document_import_routes
from web.bootstrap.fascicoli_document_trash_routes import register_fascicoli_document_trash_routes
from web.bootstrap.fascicoli_document_view_routes import register_fascicoli_document_view_routes
from web.services.document_lex_indexing import indicizza_documento_lex
from web.services.fascicoli_document_rename import rinomina_documento_response
from web.services.ricevuta_pagopa_runtime import registra_ricevuta_pagopa
from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache
from web.services.document_tools import DocumentToolError, rotate_pdf_bytes

def register_fascicoli_document_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_indice: Callable[[], Any],
    get_practice_engine: Callable[[], Any],
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
        ricevute_riconosciute = 0
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
                # Chi ha appena pagato sul portale trascina la ricevuta nel
                # fascicolo come farebbe con qualsiasi altro file: se e' una RT
                # valida secondo lo schema ministeriale, il pagamento viene
                # registrato senza che l'avvocato debba scegliere una via
                # speciale. Un file che RT non e' resta un documento come gli
                # altri: non si indovina un pagamento da un nome.
                ricevute_riconosciute += registra_ricevuta_pagopa(
                    gestore_fascicoli, id_fasc, documento, storage.filename, raw,
                )
                indicizza_documento_lex(
                    app,
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
            if ricevute_riconosciute:
                msg += (
                    " Riconosciuta la ricevuta telematica del pagamento: il contributo unificato risulta versato."
                    if ricevute_riconosciute == 1
                    else f" Riconosciute {ricevute_riconosciute} ricevute telematiche di pagamento."
                )
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

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/ruota", methods=["POST"])
    def salva_rotazione_documento(id_fasc, id_doc):
        gestore_fascicoli = get_fascicoli()
        try:
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404
            documento = next((doc for doc in fascicolo.documenti if doc.id == id_doc), None)
            if not documento:
                return jsonify({"ok": False, "messaggio": "Documento non trovato."}), 404
            payload = request.get_json(silent=True) or request.form or {}
            rotation = int(payload.get("rotation") or payload.get("angolo") or 0) % 360
            if rotation not in {90, 180, 270}:
                return jsonify({"ok": False, "messaggio": "Scegli una rotazione di 90, 180 o 270 gradi."}), 400
            percorso = percorso_documento_lettura(gestore_fascicoli, id_fasc, id_doc)
            data = decrypt_doc(percorso.read_bytes())
            operational_name = nome_documento_operativo(documento, percorso, data)
            lower_name = operational_name.casefold()
            if lower_name.endswith((".p7m", ".enc")) or bool(getattr(documento, "firmato_digitalmente", False)):
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": (
                            "Il documento è firmato o imbustato: puoi ruotarlo per leggerlo, "
                            "ma IUSENTRA non altera la firma salvando una copia modificata."
                        ),
                    }
                ), 400
            if not data.lstrip().startswith(b"%PDF-"):
                return jsonify(
                    {
                        "ok": False,
                        "messaggio": "La rotazione salvata è disponibile per PDF non firmati.",
                    }
                ), 400
            rotated_payload, pages = rotate_pdf_bytes(data, angle=rotation, name=operational_name)
            stem = Path(operational_name).stem or Path(str(getattr(documento, "nome", "") or "documento")).stem or "documento"
            rotated_name = f"{stem} - ruotato {rotation} gradi.pdf"
            utente = getattr(g, "utente_corrente", None)
            tags = list(dict.fromkeys([*(getattr(documento, "tags", []) or []), "rotazione"]))
            rotated_doc = salva_documento_fascicolo(
                gf=gestore_fascicoli,
                id_fasc=id_fasc,
                nome_file=rotated_name,
                raw=rotated_payload,
                tipo_doc=getattr(documento, "tipo", TipoDocumento.ALLEGATO) or TipoDocumento.ALLEGATO,
                note=f"Copia ruotata di {rotation} gradi da «{operational_name}».",
                tags=tags,
                data_documento=str(getattr(documento, "data_documento", "") or ""),
                firmato=False,
                caricato_da=getattr(utente, "username", "") if utente else "",
                fonte_documento="COPIA_RUOTATA_DA_LETTORE",
                nome_originale=rotated_name,
                pdfa_profile="2b",
                preserva_contenuto_originale=True,
            )
            indicizza_documento_lex(
                app,
                id_fasc=id_fasc,
                document_id=getattr(rotated_doc, "id", "") or rotated_name,
                filename=rotated_name,
                content=rotated_payload,
                source_type="documenti_fascicolo",
                metadata={
                    "trigger": "salva_rotazione_lettore",
                    "source_document_id": id_doc,
                    "rotation": rotation,
                },
                blocking=False,
            )
            audit(
                "fascicoli.documento.ruota",
                "fascicolo",
                id_fasc,
                dettagli=f"doc {id_doc} -> {getattr(rotated_doc, 'id', '')} rotazione {rotation}",
            )
            clear_react_fascicoli_list_cache()
            preview_url = url_for("visualizza_documento", id_fasc=id_fasc, id_doc=getattr(rotated_doc, "id", ""))
            return jsonify(
                {
                    "ok": True,
                    "messaggio": f"Copia ruotata salvata nel fascicolo ({pages} pagine).",
                    "documento_id": getattr(rotated_doc, "id", ""),
                    "nome": rotated_name,
                    "preview_url": url_for(
                        "visualizza_documento",
                        id_fasc=id_fasc,
                        id_doc=getattr(rotated_doc, "id", ""),
                        viewer="mobile",
                    ),
                    "desktop_preview_url": preview_url,
                    "download_url": url_for("scarica_documento", id_fasc=id_fasc, id_doc=getattr(rotated_doc, "id", "")),
                }
            )
        except DocumentToolError as exc:
            return jsonify({"ok": False, "messaggio": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore salva_rotazione_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            return jsonify({"ok": False, "messaggio": "Rotazione non salvata. Verifica il documento e riprova."}), 500
    register_fascicoli_document_import_routes(
        app,
        get_fascicoli=get_fascicoli,
        audit=audit,
        salva_documento_fascicolo=salva_documento_fascicolo,
        portale_ufficiale_label=portale_ufficiale_label,
        espandi_file_importato_portale=espandi_file_importato_portale,
        pst_import_dir_for_fascicolo=pst_import_dir_for_fascicolo,
        leggi_staging_documenti_portale=leggi_staging_documenti_portale,
        salva_albero_originale_documenti_portale=salva_albero_originale_documenti_portale,
        importa_documenti_portale_items=importa_documenti_portale_items,
        decode_portale_downloaded_items=decode_portale_downloaded_items,
    )
    register_fascicoli_document_view_routes(
        app,
        get_fascicoli=get_fascicoli,
        get_practice_engine=get_practice_engine,
        audit=audit,
        decrypt_doc=decrypt_doc,
        firma_payload_corrente_o_sibling=firma_payload_corrente_o_sibling,
        estrai_contenuto_p7m_per_preview=estrai_contenuto_p7m_per_preview,
        nome_preview_documento=nome_preview_documento,
        mime_preview_documento=mime_preview_documento,
        payload_preview_da_versioni_documento=payload_preview_da_versioni_documento,
        applica_timbro_firma_visibile=applica_timbro_firma_visibile,
    )
    register_fascicoli_document_trash_routes(app, get_fascicoli=get_fascicoli, audit=audit)
