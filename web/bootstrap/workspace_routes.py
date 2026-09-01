"""Workspace intelligente routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, jsonify, request

from web.blueprints.react_shell import render_react_shell_response


def register_workspace_routes(
    app: Flask,
    *,
    get_workspace_intelligente: Callable[[], object],
    get_local_ai_service: Callable[[], object],
) -> None:
    """Register workspace overview and AI helper routes."""

    @app.route("/workspace-intelligente")
    def workspace_intelligente():
        return render_react_shell_response("regia-operativa")

    @app.route("/api/workspace-intelligente")
    def api_workspace_intelligente():
        try:
            horizon_days = max(int(request.args.get("giorni", 14) or 14), 1)
            return jsonify(get_workspace_intelligente().panoramica(horizon_days=horizon_days))
        except Exception as e:
            app.logger.exception("Errore api_workspace_intelligente: %s", e)
            return jsonify({"errore": str(e), "summary": {}, "actions": []}), 200

    @app.route("/api/workspace-intelligente/ai", methods=["POST"])
    def api_workspace_intelligente_ai():
        try:
            data = request.get_json(silent=True) or {}
            question = str(data.get("question", "") or "").strip()
            if not question:
                return jsonify({"ok": False, "errore": "Domanda mancante."}), 200
            horizon_days = max(int(data.get("giorni", 14) or 14), 1)
            overview = get_workspace_intelligente().panoramica(horizon_days=horizon_days)
            return jsonify(get_local_ai_service().ask_workspace(question=question, overview=overview))
        except Exception as e:
            app.logger.exception("Errore api_workspace_intelligente_ai: %s", e)
            return jsonify({"ok": False, "errore": str(e), "answer": "", "sources": []}), 200

    @app.route("/api/workspace-intelligente/ai/context", methods=["POST"])
    def api_workspace_intelligente_ai_context():
        try:
            data = request.get_json(silent=True) or {}
            question = str(data.get("question", "") or "").strip()
            if not question:
                return jsonify({"ok": False, "errore": "Domanda mancante."}), 200
            horizon_days = max(int(data.get("giorni", 14) or 14), 1)
            overview = get_workspace_intelligente().panoramica(horizon_days=horizon_days)
            return jsonify(
                get_local_ai_service().prepare_workspace_query(
                    question=question,
                    overview=overview,
                )
            )
        except Exception as e:
            app.logger.exception("Errore api_workspace_intelligente_ai_context: %s", e)
            return jsonify({"ok": False, "errore": str(e), "prompt": "", "sources": []}), 200
