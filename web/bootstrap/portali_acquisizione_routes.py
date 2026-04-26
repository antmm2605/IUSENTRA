"""Portali telematici acquisition routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for


def register_portali_acquisizione_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    _spec_portale_acquisizione: Callable[[str], dict[str, Any]],
    _pdp_penale_workspace_url_for_fascicolo: Callable[[str], str],
    _build_access_status_payload: Callable[[str], dict[str, Any]],
    _search_fascicoli_portale_server: Callable[[str, dict[str, Any]], Any],
    _preview_documenti_portale_server: Callable[[str, dict[str, Any]], list[dict[str, Any]]],
    _build_portale_preview: Callable[[str, dict[str, Any], list[dict[str, Any]]], dict[str, Any]],
    _coerce_import_options: Callable[[dict[str, Any]], dict[str, Any]],
    _coerce_mapping: Callable[[dict[str, Any]], dict[str, Any]],
    _analyze_portale_import: Callable[[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
    _normalize_authorized_portale_payload: Callable[[str, dict[str, Any]], dict[str, Any]],
    _importa_o_collega_fascicolo_portale: Callable[..., dict[str, Any]],
) -> None:
    """Register guided acquisition routes for PST, PDP, PAT, and PTT."""

    @app.route("/portali/<portale>/acquisizione", methods=["GET"])
    def portale_acquisizione_wizard(portale: str):
        try:
            spec = _spec_portale_acquisizione(portale)
        except KeyError:
            flash("Portale non supportato.", "warning")
            return redirect(url_for("dashboard"))
        id_fasc = str(request.args.get("id_fasc") or "").strip()
        wizard_focus = str(request.args.get("focus") or "").strip().lower()
        linked_fascicolo = get_fascicoli().get(id_fasc) if id_fasc else None
        linked_fascicolo_url = (
            url_for("dettaglio_fascicolo", id_fasc=linked_fascicolo.id) if linked_fascicolo else ""
        )
        linked_workflow_url = ""
        if portale == "pdp" and linked_fascicolo:
            linked_workflow_url = _pdp_penale_workspace_url_for_fascicolo(linked_fascicolo.id)
        wizard_return_url = linked_fascicolo_url or url_for(spec["home_endpoint"])
        wizard_return_label = "Torna al fascicolo" if linked_fascicolo else "Torna al portale"
        wizard_initial_mapping = (
            {"mode": "update_existing", "target_fascicolo_id": linked_fascicolo.id}
            if linked_fascicolo
            else {"mode": "create_new", "target_fascicolo_id": ""}
        )
        return render_template(
            "portale/acquisizione_wizard.html",
            spec=spec,
            wizard_status=_build_access_status_payload(portale),
            wizard_portale=portale,
            linked_fascicolo=linked_fascicolo,
            linked_fascicolo_url=linked_fascicolo_url,
            linked_workflow_url=linked_workflow_url,
            wizard_return_url=wizard_return_url,
            wizard_return_label=wizard_return_label,
            wizard_initial_mapping=wizard_initial_mapping,
            wizard_focus=wizard_focus,
            oggi=date.today(),
        )

    @app.route("/polisWeb/acquisizione", methods=["GET"])
    def polisweb_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="pst"))

    @app.route("/pdp/acquisizione", methods=["GET"])
    def pdp_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="pdp"))

    @app.route("/pat/acquisizione", methods=["GET"])
    def pat_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="pat"))

    @app.route("/sigit/acquisizione", methods=["GET"])
    def sigit_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="ptt"))

    @app.route("/api/portali/<portale>/acquisizione/status", methods=["GET"])
    def api_portale_acquisizione_status(portale: str):
        try:
            return jsonify({"ok": True, "status": _build_access_status_payload(portale)})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_status(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": str(e), "status": {}}), 200

    @app.route("/api/portali/<portale>/acquisizione/search", methods=["POST"])
    def api_portale_acquisizione_search(portale: str):
        try:
            _spec_portale_acquisizione(portale)
            data = request.get_json(silent=True) or {}
            search_result = _search_fascicoli_portale_server(portale, data)
            if isinstance(search_result, dict):
                risultati = search_result.get("results") or search_result.get("fascicoli") or []
                pst_session = search_result.get("pst_session") or data.get("pst_session") or {}
            else:
                risultati = search_result
                pst_session = data.get("pst_session") or {}
            return jsonify({"ok": True, "results": risultati, "pst_session": pst_session})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_search(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": str(e), "results": []}), 200

    @app.route("/api/portali/<portale>/acquisizione/preview", methods=["POST"])
    def api_portale_acquisizione_preview(portale: str):
        try:
            _spec_portale_acquisizione(portale)
            data = request.get_json(silent=True) or {}
            selection = dict(data.get("selection") or {})
            if not selection:
                raise ValueError("Fascicolo non selezionato.")
            if isinstance(data.get("pst_session"), dict):
                selection["pst_session"] = data.get("pst_session")
            if isinstance(data.get("snapshot"), dict):
                selection["snapshot"] = data.get("snapshot")
            documenti = data.get("documenti")
            if not isinstance(documenti, list):
                documenti = _preview_documenti_portale_server(portale, selection)
            preview = _build_portale_preview(portale, selection, documenti)
            return jsonify({"ok": True, "preview": preview, "pst_session": data.get("pst_session") or {}})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_preview(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": str(e), "preview": {}}), 200

    @app.route("/api/portali/<portale>/acquisizione/analyze", methods=["POST"])
    def api_portale_acquisizione_analyze(portale: str):
        try:
            _spec_portale_acquisizione(portale)
            data = request.get_json(silent=True) or {}
            selection = dict(data.get("selection") or {})
            preview = dict(data.get("preview") or {})
            if not selection or not preview:
                raise ValueError("Selezione o anteprima mancanti.")
            options = _coerce_import_options(dict(data.get("options") or {}), portale=portale)
            mapping = _coerce_mapping(dict(data.get("mapping") or {}))
            analysis = _analyze_portale_import(portale, selection, preview, options, mapping)
            return jsonify({"ok": True, "analysis": analysis})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_analyze(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": str(e), "analysis": {}}), 200

    @app.route("/api/portali/<portale>/acquisizione/import", methods=["POST"])
    def api_portale_acquisizione_import(portale: str):
        try:
            _spec_portale_acquisizione(portale)
            data = request.get_json(silent=True) or {}
            selection = dict(data.get("selection") or {})
            preview = dict(data.get("preview") or {})
            if not selection or not preview:
                raise ValueError("Selezione o anteprima mancanti.")
            options = _coerce_import_options(dict(data.get("options") or {}), portale=portale)
            mapping = _coerce_mapping(dict(data.get("mapping") or {}))
            downloaded_files_raw = data.get("downloaded_files")
            downloaded_files = downloaded_files_raw if isinstance(downloaded_files_raw, list) else []
            result = _importa_o_collega_fascicolo_portale(
                portale,
                selection,
                preview,
                options,
                mapping,
                downloaded_files=downloaded_files,
            )
            return jsonify({"ok": True, "result": result, "pst_session": data.get("pst_session") or {}, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_import(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": str(e)}), 200

    @app.route("/api/portali/<portale>/acquisizione/importa-payload", methods=["POST"])
    def api_portale_acquisizione_importa_payload(portale: str):
        try:
            _spec_portale_acquisizione(portale)
            data = request.get_json(silent=True) or {}
            raw_payload = data.get("payload") or data.get("raw_payload") or data
            normalized = _normalize_authorized_portale_payload(portale, dict(raw_payload or {}))
            selection = dict(normalized.get("selection") or {})
            preview = dict(normalized.get("preview") or {})
            if not selection or not preview:
                raise ValueError("Payload autorizzato non riconoscibile.")
            options = _coerce_import_options(dict(data.get("options") or {}), portale=portale)
            mapping_raw = dict(data.get("mapping") or {})
            fascicolo_locale_id = str(data.get("fascicolo_locale_id") or "").strip()
            if fascicolo_locale_id and not mapping_raw.get("target_fascicolo_id"):
                mapping_raw["mode"] = "update_existing"
                mapping_raw["target_fascicolo_id"] = fascicolo_locale_id
            mapping = _coerce_mapping(mapping_raw)
            downloaded_files_raw = data.get("downloaded_files")
            downloaded_files = downloaded_files_raw if isinstance(downloaded_files_raw, list) else []
            result = _importa_o_collega_fascicolo_portale(
                portale,
                selection,
                preview,
                options,
                mapping,
                downloaded_files=downloaded_files,
            )
            return jsonify({"ok": True, "normalized": normalized, "result": result, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_importa_payload(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": str(e)}), 200
