"""Telematico dashboard routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from flask import Flask, jsonify, render_template, url_for
from web.services.telematico_control_tower import build_telematico_control_tower


def register_telematico_dashboard_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_telematico: Callable[[], object],
    _backfill_telematico_from_existing_fascicoli: Callable[[], dict[str, int]],
    _build_access_status_payload: Callable[[str], dict],
    _telematico_dashboard_warning_message: Callable[[Exception], str],
) -> None:
    """Register telematico dashboard and connection status routes."""

    @app.route("/api/telematico/connection-status", methods=["GET"])
    def api_telematico_connection_status():
        try:
            cards = []
            for portale in ("pst", "pdp", "pat", "ptt"):
                payload = _build_access_status_payload(portale)
                spec = dict(payload.get("spec") or {})
                cards.append(
                    {
                        "portale": portale,
                        "label": spec.get("label"),
                        "color": spec.get("color"),
                        "status_text": payload.get("status_text"),
                        "environment_label": payload.get("environment_label"),
                        "demo_mode": bool(payload.get("demo_mode")),
                        "pkcs11_mode": bool(payload.get("pkcs11_mode")),
                        "browser_channel_required": bool(payload.get("browser_channel_required")),
                        "last_sync_at": payload.get("last_sync_at"),
                    }
                )
            return jsonify({"ok": True, "cards": cards})
        except Exception as e:
            app.logger.exception("Errore api_telematico_connection_status: %s", e)
            return jsonify({"ok": False, "errore": str(e), "cards": []}), 200

    @app.route("/telematico", methods=["GET"])
    def telematico_dashboard():
        try:
            backfill_summary = {"processed": 0, "failed": 0}
            dashboard_notices = []
            try:
                backfill_summary = _backfill_telematico_from_existing_fascicoli()
            except Exception as e:
                app.logger.exception("Errore backfill telematico_dashboard: %s", e)
                backfill_summary = {"processed": 0, "failed": 1}

            stats = {"totale": 0, "per_service": {}}
            recent_cases = []
            recent_events = []
            read_warning = ""
            try:
                repo = get_telematico()
                stats = repo.case_stats()
                recent_cases = repo.list_cases(limit=18)
                recent_events = repo.list_recent_events(limit=12)
            except Exception as e:
                app.logger.exception("Errore lettura telematico_dashboard: %s", e)
                read_warning = _telematico_dashboard_warning_message(e)

            service_map = {
                "pst": "polisweb_consultazione",
                "pdp": "pdp_penale",
                "pat": "pat_siga",
                "ptt": "ptt_sigit",
            }
            routes_map = {
                "pst": ("polisWeb_home", "pst"),
                "pdp": ("pdp_home", "pdp"),
                "pat": ("pat_home", "pat"),
                "ptt": ("sigit_home", "ptt"),
            }
            connection_cards = []
            for portale in ("pst", "pdp", "pat", "ptt"):
                payload = _build_access_status_payload(portale)
                spec = dict(payload.get("spec") or {})
                service_stats = dict((stats.get("per_service") or {}).get(service_map[portale]) or {})
                home_endpoint, wizard_portale = routes_map[portale]
                connection_cards.append(
                    {
                        "portale": portale,
                        "spec": spec,
                        "status_text": payload.get("status_text"),
                        "environment_label": payload.get("environment_label"),
                        "demo_mode": bool(payload.get("demo_mode")),
                        "pkcs11_mode": bool(payload.get("pkcs11_mode")),
                        "browser_channel_required": bool(payload.get("browser_channel_required")),
                        "last_sync_at": payload.get("last_sync_at"),
                        "last_import_log_id": payload.get("last_import_log_id"),
                        "totale": int(service_stats.get("totale") or 0),
                        "import_completed": int(service_stats.get("import_completed") or 0),
                        "attention_needed": int(service_stats.get("attention_needed") or 0),
                        "home_url": url_for(home_endpoint),
                        "acquisizione_url": url_for("portale_acquisizione_wizard", portale=wizard_portale),
                    }
                )
            fascicoli_index = {fasc.id: fasc for fasc in get_fascicoli().tutti()}
            for row in recent_cases:
                fasc = fascicoli_index.get(str(row.get("practice_id") or ""))
                row["practice_url"] = url_for("dettaglio_fascicolo", id_fasc=row["practice_id"]) if fasc else ""
                row["practice_title"] = getattr(fasc, "titolo", "") if fasc else ""
                row["practice_number"] = getattr(fasc, "numero", "") if fasc else ""
                row["service_label"] = {
                    "polisweb_consultazione": "PST / PolisWeb",
                    "pdp_penale": "PDP Penale",
                    "pat_siga": "PAT / SIGA",
                    "ptt_sigit": "PTT / SIGIT",
                }.get(str(row.get("service_code") or ""), str(row.get("service_code") or ""))
            for row in recent_events:
                fasc = fascicoli_index.get(str(row.get("practice_id") or ""))
                row["practice_url"] = url_for("dettaglio_fascicolo", id_fasc=row["practice_id"]) if fasc else ""
                row["practice_title"] = getattr(fasc, "titolo", "") if fasc else ""
            control_tower = {
                "summary": {
                    "totale": 0,
                    "pending_outcomes": 0,
                    "imports_incomplete": 0,
                    "warnings": 0,
                    "blocked": 0,
                },
                "channel_cards": [],
                "pending_outcomes": [],
                "incomplete_imports": [],
                "warning_cases": [],
                "predeposito": [],
                "blocked_cases": [],
                "recent_events": [],
            }
            try:
                control_tower = build_telematico_control_tower(
                    get_telematico=get_telematico,
                    get_fascicoli=get_fascicoli,
                )
            except Exception as e:
                app.logger.exception("Errore control tower telematico_dashboard: %s", e)
                if not read_warning:
                    read_warning = _telematico_dashboard_warning_message(e)
            if backfill_summary.get("failed", 0):
                dashboard_notices.append(
                    {
                        "tone": "warning",
                        "title": "Allineamento parziale",
                        "body": (
                            "Allineamento telematico eseguito in modalita' protetta: alcuni fascicoli "
                            "non sono stati aggiornati, ma la cabina resta operativa."
                        ),
                    }
                )
            if read_warning:
                dashboard_notices.append(
                    {
                        "tone": "warning",
                        "title": "Archivio telematico presidiato",
                        "body": read_warning,
                    }
                )
            return render_template(
                "telematico_dashboard.html",
                oggi=date.today(),
                stats=stats,
                connection_cards=connection_cards,
                recent_cases=recent_cases,
                recent_events=recent_events,
                control_tower=control_tower,
                dashboard_notices=dashboard_notices,
            )
        except Exception as e:
            app.logger.exception("Errore telematico_dashboard: %s", e)
            return render_template(
                "telematico_dashboard.html",
                oggi=date.today(),
                stats={"totale": 0, "per_service": {}},
                connection_cards=[],
                recent_cases=[],
                recent_events=[],
                control_tower={
                    "summary": {
                        "totale": 0,
                        "pending_outcomes": 0,
                        "imports_incomplete": 0,
                        "warnings": 0,
                        "blocked": 0,
                    },
                    "channel_cards": [],
                    "pending_outcomes": [],
                    "incomplete_imports": [],
                    "warning_cases": [],
                    "predeposito": [],
                    "blocked_cases": [],
                    "recent_events": [],
                },
                dashboard_notices=[
                    {
                        "tone": "warning",
                        "title": "Modalita' ridotta",
                        "body": (
                            "Cabina telematica temporaneamente disponibile in modalita' ridotta. "
                            "Riprova tra poco o verifica il registro applicativo."
                        ),
                    }
                ],
            )
