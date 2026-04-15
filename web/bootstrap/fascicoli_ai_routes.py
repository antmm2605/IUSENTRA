"""AI routes for fascicolo context extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, jsonify, request


def register_fascicoli_ai_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_agenda: Callable[[], object],
    get_scadenziario: Callable[[], object],
    get_workspace_intelligente: Callable[[], object],
    get_local_ai_service: Callable[[], object],
    cfg_data_path: Callable[[str], str],
    build_fascicolo_workspace: Callable[..., dict],
) -> None:
    """Register AI endpoints that operate on a fascicolo."""

    @app.route("/api/fascicoli/<id_fasc>/ai", methods=["POST"])
    def api_fascicolo_ai(id_fasc):
        try:
            data = request.get_json(silent=True) or {}
            question = str(data.get("question", "") or "").strip()
            if not question:
                return jsonify({"ok": False, "errore": "Domanda mancante."}), 200
            fascicolo = get_fascicoli().get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 200
            agenda = get_agenda()
            scadenze_fascicolo = get_scadenziario().tutte(id_fascicolo=id_fasc, solo_aperte=False)
            appuntamenti = agenda.cerca(testo=fascicolo.numero_rg) if getattr(fascicolo, "numero_rg", "") else []
            workspace_fascicolo = build_fascicolo_workspace(
                fascicolo,
                apps=appuntamenti,
                scadenze=scadenze_fascicolo,
            )
            intelligenza_fascicolo = get_workspace_intelligente().per_fascicolo(
                fascicolo,
                apps=appuntamenti,
                scadenze=scadenze_fascicolo,
            )
            result = get_local_ai_service().ask_fascicolo(
                fascicolo=fascicolo,
                documents_dir=cfg_data_path("FASCICOLI_DOCS"),
                question=question,
                apps=appuntamenti,
                scadenze=scadenze_fascicolo,
                workspace=workspace_fascicolo,
                intelligenza=intelligenza_fascicolo,
                auto_index=data.get("auto_index"),
            )
            return jsonify(result)
        except Exception as exc:
            app.logger.exception("Errore api_fascicolo_ai(%s): %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": str(exc), "answer": "", "sources": []}), 200

    @app.route("/api/fascicoli/<id_fasc>/ai/context", methods=["POST"])
    def api_fascicolo_ai_context(id_fasc):
        try:
            data = request.get_json(silent=True) or {}
            question = str(data.get("question", "") or "").strip()
            if not question:
                return jsonify({"ok": False, "errore": "Domanda mancante."}), 200
            fascicolo = get_fascicoli().get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 200
            agenda = get_agenda()
            scadenze_fascicolo = get_scadenziario().tutte(id_fascicolo=id_fasc, solo_aperte=False)
            appuntamenti = agenda.cerca(testo=fascicolo.numero_rg) if getattr(fascicolo, "numero_rg", "") else []
            workspace_fascicolo = build_fascicolo_workspace(
                fascicolo,
                apps=appuntamenti,
                scadenze=scadenze_fascicolo,
            )
            intelligenza_fascicolo = get_workspace_intelligente().per_fascicolo(
                fascicolo,
                apps=appuntamenti,
                scadenze=scadenze_fascicolo,
            )
            result = get_local_ai_service().prepare_fascicolo_query(
                fascicolo=fascicolo,
                documents_dir=cfg_data_path("FASCICOLI_DOCS"),
                question=question,
                apps=appuntamenti,
                scadenze=scadenze_fascicolo,
                workspace=workspace_fascicolo,
                intelligenza=intelligenza_fascicolo,
                auto_index=data.get("auto_index"),
            )
            return jsonify(result)
        except Exception as exc:
            app.logger.exception("Errore api_fascicolo_ai_context(%s): %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": str(exc), "prompt": "", "sources": []}), 200

    @app.route("/api/fascicoli/<id_fasc>/ai/reindex", methods=["POST"])
    def api_fascicolo_ai_reindex(id_fasc):
        try:
            fascicolo = get_fascicoli().get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 200
            service = get_local_ai_service()
            result = service.reindex_fascicolo(
                fascicolo,
                cfg_data_path("FASCICOLI_DOCS"),
                force=True,
            )
            return jsonify({"ok": True, "result": result, "status_payload": service.health_snapshot()})
        except Exception as exc:
            app.logger.exception("Errore api_fascicolo_ai_reindex(%s): %s", id_fasc, exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200
