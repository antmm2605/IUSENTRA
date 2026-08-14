"""Trash routes for fascicolo documents."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, flash, g, jsonify, request, url_for

from web.bootstrap.fascicoli_document_helpers import redirect_to_documenti_section, wants_json_response
from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache


def register_fascicoli_document_trash_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    audit: Callable[..., None],
) -> None:
    """Register trash, restore, and permanent deletion routes."""

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/elimina", methods=["POST"])
    def elimina_documento(id_fasc, id_doc):
        try:
            utente = g.utente_corrente
            eliminato_da = str(
                getattr(utente, "nome_completo", "")
                or getattr(utente, "username", "")
                or ""
            ).strip()
            get_fascicoli().rimuovi_documento(id_fasc, id_doc, eliminato_da=eliminato_da)
            msg = "Documento spostato nel cestino."
            flash(msg, "success")
            audit("fascicoli.documento.cestino", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
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

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/ripristina", methods=["POST"])
    def ripristina_documento(id_fasc, id_doc):
        try:
            get_fascicoli().ripristina_documento(id_fasc, id_doc)
            msg = "Documento ripristinato nel fascicolo."
            flash(msg, "success")
            audit("fascicoli.documento.ripristina", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
            clear_react_fascicoli_list_cache()
            if wants_json_response():
                return jsonify({"ok": True, "messaggio": msg})
        except KeyError as exc:
            app.logger.warning("Ripristino documento non valido id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            msg = "Documento non trovato nel cestino."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 404
            flash(msg, "danger")
        except Exception as exc:
            app.logger.exception("Errore ripristina_documento id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            msg = "Ripristino non completato. Riprova tra pochi secondi."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 503
            flash(msg, "danger")
        return redirect_to_documenti_section(id_fasc)

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/elimina-definitivamente", methods=["POST"])
    def elimina_documento_definitivamente(id_fasc, id_doc):
        try:
            get_fascicoli().elimina_documento_definitivamente(id_fasc, id_doc)
            msg = "Documento eliminato definitivamente."
            flash(msg, "success")
            audit("fascicoli.documento.elimina_definitiva", "fascicolo", id_fasc, dettagli=f"doc {id_doc}")
            clear_react_fascicoli_list_cache()
            if wants_json_response():
                return jsonify({"ok": True, "messaggio": msg})
        except KeyError as exc:
            app.logger.warning("Eliminazione definitiva non valida id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            msg = "Documento non trovato nel cestino."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 404
            flash(msg, "danger")
        except Exception as exc:
            app.logger.exception("Errore elimina_documento_definitivamente id_fasc=%s id_doc=%s: %s", id_fasc, id_doc, exc)
            msg = "Eliminazione definitiva non completata. Riprova tra pochi secondi."
            if wants_json_response():
                return jsonify({"ok": False, "messaggio": msg}), 503
            flash(msg, "danger")
        return redirect_to_documenti_section(id_fasc)

    @app.route("/fascicoli/<id_fasc>/documenti/elimina-multipla", methods=["POST"])
    def elimina_documenti_multipli(id_fasc):
        ids_doc = [item.strip() for item in str(request.form.get("documenti_ids") or "").split(",") if item.strip()]
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
            audit("fascicoli.documento.elimina_multipla", "fascicolo", id_fasc, dettagli=f"{rimossi} documenti")
            flash(
                f"{rimossi} document{'o' if rimossi == 1 else 'i'} eliminat{'o' if rimossi == 1 else 'i'} dal fascicolo.",
                "success",
            )
        if errori:
            flash("Alcuni documenti non sono stati eliminati: " + "; ".join(errori[:3]), "warning")
        return redirect_to_documenti_section(id_fasc)
