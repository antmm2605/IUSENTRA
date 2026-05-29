"""Portali telematici acquisition routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
import re
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
    _importa_file_assistiti_portale: Callable[[str, dict[str, Any]], dict[str, Any]],
    _portal_assistant_start: Callable[[str, dict[str, Any]], dict[str, Any]],
    _portal_assistant_open: Callable[[str, str], dict[str, Any]],
    _portal_assistant_watch_downloads: Callable[[str, str], dict[str, Any]],
    _portal_assistant_status: Callable[[str, str], dict[str, Any]],
    _portal_assistant_collect: Callable[[str, str, dict[str, Any]], dict[str, Any]],
    _portal_assistant_close: Callable[..., dict[str, Any]],
    _deposito_precheck_assistito: Callable[[str, dict[str, Any]], dict[str, Any]],
    _deposito_prepara_assistito: Callable[[str, dict[str, Any]], dict[str, Any]],
    _deposito_assistant_start: Callable[[str, dict[str, Any]], dict[str, Any]],
    _deposito_importa_ricevute_assistito: Callable[[str, dict[str, Any]], dict[str, Any]],
    _deposito_finalizza_assistito: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> None:
    """Register guided acquisition routes for PST, PDP, PAT, and PTT."""

    def _richiede_vista_classica() -> bool:
        return request.args.get("_legacy") == "1"

    def _vista_classica_args() -> dict[str, str]:
        return {"_legacy": "1"} if _richiede_vista_classica() else {}

    def _portale_public_error(portale: str, operation: str) -> str:
        key = str(portale or "").strip().lower()
        if operation == "search" and key == "pat":
            return "Portale dell'Avvocato non disponibile. Verifica l'accesso ufficiale e riprova."
        if operation == "search" and key == "ptt":
            return "PTT / SIGIT non disponibile tramite Telecontenzioso. Verifica l'accesso ufficiale e riprova."
        if operation == "search" and key == "pst":
            return "Ricerca PST non completata: verifica il sotto-procedimento o riprova dal Local Signer del browser."
        if operation == "preview":
            return "Anteprima non completata tramite Local Signer del browser. Verifica selezione e sessione ufficiale."
        if operation in {"import", "import_payload", "import_file"}:
            return "Importazione non completata: non sono arrivati file reali, oppure sono presenti solo catalogo o metadati."
        if operation == "assistant_start" and key == "pst":
            return "PST usa il canale diretto interno: apri la ricerca guidata PST dallo stesso fascicolo."
        if operation.startswith("assistant"):
            return "Sessione assistita del portale non completata. Verifica l'accesso ufficiale e riprova."
        if operation.startswith("deposito"):
            return "Deposito assistito non completato. Verifica ricevute, documenti e sessione ufficiale."
        if operation == "status":
            return "Stato del portale non disponibile. Riprova tra poco."
        if operation == "analyze":
            return "Analisi importazione non completata. Verifica selezione e anteprima."
        return "Operazione non completata. Verifica i dati e riprova."

    def _portale_public_error_from_exception(portale: str, operation: str, exc: Exception) -> str:
        base = _portale_public_error(portale, operation)
        detail = str(exc or "").strip()
        lowered = detail.lower()
        if not detail:
            return base
        if "timeout connessione" in lowered or "timed out" in lowered:
            return (
                "Scaricamento dal PST non completato: il portale ufficiale non ha risposto "
                "entro il tempo massimo. Riprova tra qualche minuto dalla stessa schermata; "
                "se la sessione è ancora valida non dovrai ripetere tutta la ricerca."
            )
        if "401" in lowered or "unauthorized" in lowered or "autenticazione pst" in lowered:
            return (
                "Accesso PST non completato: il certificato non è stato accettato oppure "
                "il PIN non è stato confermato sul PC. Riavvia Local Signer, controlla la "
                "finestra del dispositivo e riprova."
            )
        if "soap fault" in lowered or "non può eseguire" in lowered or "non puo' eseguire" in lowered:
            return (
                "Il portale ufficiale ha rifiutato l'operazione per autorizzazioni o ruolo "
                "del certificato. Verifica che il dispositivo sia quello abilitato per quel fascicolo."
            )
        if "non sono arrivati file reali" in lowered or "solo catalogo" in lowered or "metadati" in lowered:
            return (
                "Scaricamento dal PST non completato: il fascicolo espone documenti, ma dal portale ufficiale "
                "non sono arrivati file reali al Local Signer. IUSENTRA non importa solo catalogo "
                "o metadati senza PDF/documenti effettivi."
            )
        if "lotto scaricato non contiene file documentali" in lowered:
            return (
                "Scaricamento dal PST non completato: il lotto ricevuto non contiene file documentali "
                "riconducibili al catalogo del fascicolo."
            )
        if "blocchi da risolvere" in lowered:
            return (
                "Importazione non completata: ci sono controlli bloccanti da risolvere nella verifica "
                "prima dell'importazione."
            )
        if "fascicolo locale selezionato non trovato" in lowered or "non è compatibile" in lowered or "non compatibile" in lowered:
            return "Importazione non completata: il fascicolo locale selezionato non è compatibile."
        return base

    def _clean_query_value(name: str) -> str:
        return str(request.args.get(name) or "").strip()

    def _normalise_document_match(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if raw.endswith(".pdf.p7m"):
            raw = raw[:-4]
        elif raw.endswith(".p7m") and ".pdf" not in raw:
            raw = raw[:-4]
        return re.sub(r"[^a-z0-9]+", "", raw)

    def _target_document_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
        body = payload if isinstance(payload, dict) else {}
        target = body.get("target_document") if isinstance(body.get("target_document"), dict) else {}
        return {
            "singleDocument": bool(target.get("singleDocument") or target.get("single_document")),
            "documento": str(target.get("documento") or target.get("nome") or target.get("documento_portale") or "").strip(),
            "idDocumento": str(target.get("idDocumento") or target.get("id_documento") or "").strip(),
            "hash": str(target.get("hash") or target.get("sha256") or "").strip().lower(),
            "pecId": str(target.get("pecId") or target.get("pec_id") or "").strip(),
        }

    def _coerce_request_mapping(data: dict[str, Any]) -> dict[str, str]:
        mapping_raw = dict(data.get("mapping") or {})
        fallback_target = str(
            data.get("target_fascicolo_id")
            or data.get("fascicolo_locale_id")
            or data.get("fascicolo_id")
            or data.get("id_fasc")
            or ""
        ).strip()
        if fallback_target and not str(mapping_raw.get("target_fascicolo_id") or "").strip():
            mapping_raw["target_fascicolo_id"] = fallback_target
        if str(mapping_raw.get("target_fascicolo_id") or "").strip():
            requested_mode = str(mapping_raw.get("mode") or "").strip()
            if not requested_mode or requested_mode == "create_new":
                mapping_raw["mode"] = "update_existing"
        return _coerce_mapping(mapping_raw)

    def _filter_target_document_rows(documenti: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
        if not target.get("singleDocument"):
            return documenti
        name_key = _normalise_document_match(target.get("documento"))
        id_key = str(target.get("idDocumento") or "").strip()
        sha_key = str(target.get("hash") or "").strip().lower()
        filtered = []
        for row in documenti:
            if not isinstance(row, dict):
                continue
            row_names = {
                _normalise_document_match(row.get("nome")),
                _normalise_document_match(row.get("nome_documento")),
                _normalise_document_match(row.get("filename")),
                _normalise_document_match(row.get("name")),
            }
            row_ids = {
                str(row.get("id_documento") or "").strip(),
                str(row.get("id_documento_portale") or "").strip(),
                str(row.get("id_cat") or "").strip(),
                str(row.get("id_repeatto") or "").strip(),
                str(row.get("msg_id") or "").strip(),
            }
            row_hash = str(row.get("sha256") or row.get("hash_sha256") or "").strip().lower()
            if (name_key and name_key in row_names) or (id_key and id_key in row_ids) or (sha_key and sha_key == row_hash):
                filtered.append(row)
        return filtered

    @app.route("/portali/<portale>/acquisizione", methods=["GET"])
    def portale_acquisizione_wizard(portale: str):
        try:
            spec = _spec_portale_acquisizione(portale)
        except KeyError:
            flash("Portale non supportato.", "warning")
            return redirect(url_for("dashboard"))

        id_fasc = str(
            request.args.get("id_fasc")
            or request.args.get("fascicolo_id")
            or request.args.get("target_fascicolo_id")
            or ""
        ).strip()
        requested_mode = str(request.args.get("mode") or "").strip().lower()
        if requested_mode not in {"create_new", "attach_existing", "update_existing"}:
            requested_mode = ""
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
        initial_target_id = linked_fascicolo.id if linked_fascicolo else id_fasc
        initial_mode = requested_mode or ("update_existing" if linked_fascicolo else "create_new")
        if initial_mode == "create_new":
            initial_target_id = ""
        elif initial_target_id:
            initial_mode = "update_existing" if initial_mode == "update_existing" else "attach_existing"
        wizard_initial_mapping = (
            {"mode": initial_mode, "target_fascicolo_id": initial_target_id}
        )
        wizard_initial_query = {
            "ufficio": _clean_query_value("ufficio"),
            "ufficioCodice": _clean_query_value("ufficio_codice"),
            "numero": _clean_query_value("numero"),
            "anno": _clean_query_value("anno"),
            "assistito": _clean_query_value("assistito"),
            "controparte": _clean_query_value("controparte"),
            "oggetto": _clean_query_value("oggetto") or _clean_query_value("documento") or _clean_query_value("documento_portale"),
        }
        wizard_target_document = {
            "singleDocument": _clean_query_value("single_document") in {"1", "true", "si", "sì"},
            "documento": _clean_query_value("documento") or _clean_query_value("documento_portale"),
            "idDocumento": _clean_query_value("id_documento"),
            "hash": _clean_query_value("hash"),
            "pecId": _clean_query_value("pec_id"),
        }
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
            wizard_initial_query=wizard_initial_query,
            wizard_target_document=wizard_target_document,
            wizard_focus=wizard_focus,
            oggi=date.today(),
        )

    @app.route("/polisWeb/acquisizione", methods=["GET"])
    def polisweb_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="pst", **_vista_classica_args()))

    @app.route("/pdp/acquisizione", methods=["GET"])
    def pdp_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="pdp", **_vista_classica_args()))

    @app.route("/pat/acquisizione", methods=["GET"])
    def pat_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="pat", **_vista_classica_args()))

    @app.route("/sigit/acquisizione", methods=["GET"])
    def sigit_acquisizione_redirect():
        return redirect(url_for("portale_acquisizione_wizard", portale="ptt", **_vista_classica_args()))

    @app.route("/api/portali/<portale>/acquisizione/status", methods=["GET"])
    def api_portale_acquisizione_status(portale: str):
        try:
            return jsonify({"ok": True, "status": _build_access_status_payload(portale)})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_status(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "status"), "status": {}}), 200

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
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "search"), "results": []}), 200

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
            documenti = _filter_target_document_rows(documenti, _target_document_from_payload(data))
            preview = _build_portale_preview(portale, selection, documenti)
            return jsonify({"ok": True, "preview": preview, "pst_session": data.get("pst_session") or {}})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_preview(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "preview"), "preview": {}}), 200

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
            mapping = _coerce_request_mapping(data)
            analysis = _analyze_portale_import(portale, selection, preview, options, mapping)
            return jsonify({"ok": True, "analysis": analysis})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_analyze(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "analyze"), "analysis": {}}), 200

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
            mapping = _coerce_request_mapping(data)
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
            return jsonify({"ok": False, "errore": _portale_public_error_from_exception(portale, "import", e)}), 200

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
            mapping = _coerce_request_mapping(data)
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
            return jsonify({"ok": False, "errore": _portale_public_error_from_exception(portale, "import_payload", e)}), 200

    @app.route("/api/portali/<portale>/acquisizione/importa-file", methods=["POST"])
    def api_portale_acquisizione_importa_file(portale: str):
        try:
            _spec_portale_acquisizione(portale)
            data = request.get_json(silent=True) or {}
            result = _importa_file_assistiti_portale(portale, data)
            return jsonify({"ok": True, "result": result, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_acquisizione_importa_file(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error_from_exception(portale, "import_file", e)}), 200

    @app.route("/api/portali/<portale>/assistant/start", methods=["POST"])
    def api_portale_assistant_start(portale: str):
        try:
            data = request.get_json(silent=True) or {}
            result = _portal_assistant_start(portale, data)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_assistant_start(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "assistant_start")}), 400

    @app.route("/api/portali/<portale>/assistant/<session_id>/status", methods=["GET"])
    def api_portale_assistant_status(portale: str, session_id: str):
        try:
            result = _portal_assistant_status(portale, session_id)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_assistant_status(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "assistant_status")}), 404

    @app.route("/api/portali/<portale>/assistant/<session_id>/open", methods=["POST"])
    def api_portale_assistant_open(portale: str, session_id: str):
        try:
            result = _portal_assistant_open(portale, session_id)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_assistant_open(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "assistant_open")}), 400

    @app.route("/api/portali/<portale>/assistant/<session_id>/watch-downloads", methods=["POST"])
    def api_portale_assistant_watch_downloads(portale: str, session_id: str):
        try:
            result = _portal_assistant_watch_downloads(portale, session_id)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_assistant_watch_downloads(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "assistant_watch")}), 400

    @app.route("/api/portali/<portale>/assistant/<session_id>/collect", methods=["POST"])
    def api_portale_assistant_collect(portale: str, session_id: str):
        try:
            data = request.get_json(silent=True) or {}
            result = _portal_assistant_collect(portale, session_id, data)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_assistant_collect(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "assistant_collect")}), 400

    @app.route("/api/portali/<portale>/assistant/<session_id>/close", methods=["POST"])
    def api_portale_assistant_close(portale: str, session_id: str):
        try:
            result = _portal_assistant_close(portale, session_id, cancel=False)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_assistant_close(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "assistant_close")}), 400

    @app.route("/api/portali/<portale>/assistant/<session_id>/cancel", methods=["POST"])
    def api_portale_assistant_cancel(portale: str, session_id: str):
        try:
            result = _portal_assistant_close(portale, session_id, cancel=True)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_assistant_cancel(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "assistant_cancel")}), 400

    @app.route("/api/portali/<portale>/deposito/precheck", methods=["POST"])
    def api_portale_deposito_precheck(portale: str):
        try:
            data = request.get_json(silent=True) or {}
            result = _deposito_precheck_assistito(portale, data)
            return jsonify(result)
        except Exception as e:
            app.logger.exception("Errore api_portale_deposito_precheck(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "deposito_precheck")}), 400

    @app.route("/api/portali/<portale>/deposito/prepara", methods=["POST"])
    def api_portale_deposito_prepara(portale: str):
        try:
            data = request.get_json(silent=True) or {}
            result = _deposito_prepara_assistito(portale, data)
            return jsonify(result)
        except Exception as e:
            app.logger.exception("Errore api_portale_deposito_prepara(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "deposito_prepara")}), 400

    @app.route("/api/portali/<portale>/deposito/assistant/start", methods=["POST"])
    def api_portale_deposito_assistant_start(portale: str):
        try:
            data = request.get_json(silent=True) or {}
            result = _deposito_assistant_start(portale, data)
            return jsonify({"ok": True, **result})
        except Exception as e:
            app.logger.exception("Errore api_portale_deposito_assistant_start(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "deposito_assistant_start")}), 400

    @app.route("/api/portali/<portale>/deposito/importa-ricevute", methods=["POST"])
    def api_portale_deposito_importa_ricevute(portale: str):
        try:
            data = request.get_json(silent=True) or {}
            result = _deposito_importa_ricevute_assistito(portale, data)
            return jsonify(result)
        except Exception as e:
            app.logger.exception("Errore api_portale_deposito_importa_ricevute(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "deposito_importa_ricevute")}), 400

    @app.route("/api/portali/<portale>/deposito/finalizza", methods=["POST"])
    def api_portale_deposito_finalizza(portale: str):
        try:
            data = request.get_json(silent=True) or {}
            result = _deposito_finalizza_assistito(portale, data)
            return jsonify(result)
        except Exception as e:
            app.logger.exception("Errore api_portale_deposito_finalizza(%s): %s", portale, e)
            return jsonify({"ok": False, "errore": _portale_public_error(portale, "deposito_finalizza")}), 400
