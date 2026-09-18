"""Rotte di importazione documenti dai portali ufficiali.

Stanno in un modulo loro perche' sono una responsabilita' distinta dal
caricamento manuale e dalla consultazione: leggono il pacchetto scaricato dal
portale, ne espandono il contenuto, lo salvano nel fascicolo e lo indicizzano.
Il download resta a carico dell'avvocato sul portale autenticato, come impone
il Portale Servizi Telematici.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, jsonify, redirect, request, url_for

from web.bootstrap.fascicoli_document_helpers import (
    applica_modalita_portale,
    contenuto_portale_bytes,
    payload_bool,
    wants_json_response,
)
from web.services.document_lex_indexing import indicizza_documento_lex
from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache


def register_fascicoli_document_import_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    audit: Callable[..., None],
    salva_documento_fascicolo: Callable[..., Any],
    portale_ufficiale_label: Callable[[Any], str],
    espandi_file_importato_portale: Callable[..., list[dict[str, Any]]],
    pst_import_dir_for_fascicolo: Callable[[Any], Any],
    leggi_staging_documenti_portale: Callable[[Any], tuple[list[dict[str, Any]], Any]],
    salva_albero_originale_documenti_portale: Callable[[Any, list[dict[str, Any]]], str],
    importa_documenti_portale_items: Callable[..., dict[str, Any]],
    decode_portale_downloaded_items: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> None:
    """Registra le due rotte di import (form e API) dei documenti di portale."""
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
                indicizza_documento_lex(
                    app,
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
                indicizza_documento_lex(
                    app,
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


__all__ = ["register_fascicoli_document_import_routes"]
