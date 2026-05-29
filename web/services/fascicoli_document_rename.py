"""Route support for fascicolo document rename operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, flash, jsonify, redirect, request, url_for


def rinomina_documento_response(
    *,
    app: Flask,
    get_fascicoli: Callable[[], Any],
    audit: Callable[..., None],
    wants_json: Callable[[], bool],
    id_fasc: str,
    id_doc: str,
):
    """Rename a fascicolo document and return the expected HTML or JSON response."""

    gestore_fascicoli = get_fascicoli()
    payload = request.get_json(silent=True) or {}
    nome_file = str(
        payload.get("nome_file")
        or payload.get("nome")
        or request.form.get("nome_file")
        or request.form.get("nome")
        or ""
    )
    try:
        documento = gestore_fascicoli.rinomina_documento(id_fasc, id_doc, nome_file)
        audit(
            "fascicoli.documento.rinomina",
            "fascicolo",
            id_fasc,
            dettagli=f"doc {id_doc} - {documento.nome}",
        )
        messaggio = "Nome documento aggiornato."
        if wants_json():
            return jsonify(
                {
                    "ok": True,
                    "messaggio": messaggio,
                    "message": messaggio,
                    "documento_id": id_doc,
                    "nome_file": documento.nome,
                    "redirect_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#documenti",
                }
            )
        flash(messaggio, "success")
    except (ValueError, KeyError) as exc:
        app.logger.warning("Rinomina documento non valida id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
        msg = "Nome documento non aggiornato. Verifica il fascicolo e il nome file."
        if wants_json():
            return jsonify({"ok": False, "messaggio": msg, "message": msg}), 400
        flash(msg, "danger")
    except Exception as exc:
        app.logger.exception("Errore rinomina_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
        msg = "Rinomina documento non completata."
        if wants_json():
            return jsonify({"ok": False, "messaggio": msg, "message": msg}), 500
        flash(msg, "danger")
    return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc, focus="documenti"))
