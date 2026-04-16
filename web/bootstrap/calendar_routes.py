"""Calendar feed and calendar settings routes extracted from web.app."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date, timedelta
from urllib.parse import quote

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for

from pct.agenda import TipoAppuntamento


def register_calendar_routes(
    app: Flask,
    *,
    cfg_data_path: Callable[[str], str],
    get_agenda: Callable[[], object],
    get_scadenziario: Callable[[], object],
    get_calendar_sync: Callable[[], object],
) -> None:
    """Register iCal feed and calendar subscription settings routes."""

    def _cal_token_dir() -> str:
        agenda_db = cfg_data_path("AGENDA_DB")
        return os.path.dirname(os.path.abspath(agenda_db))

    def _cal_token_valido(token: str) -> bool:
        from pct.cal_token import get_token

        try:
            return get_token(_cal_token_dir()).get("token") == token
        except Exception:
            return False

    def _get_base_url() -> str:
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            return configured
        base = request.host_url.rstrip("/")
        if base.startswith("http://"):
            base = "https://" + base[len("http://") :]
        return base

    @app.route("/agenda/export.ics")
    def agenda_ical():
        from pct.ical import agenda_to_ical

        studio_nome = app.config.get("STUDIO_NOME", "IUSENTRA")
        base_url = request.host_url.rstrip("/").replace("http://", "https://", 1)
        ical_str = agenda_to_ical(get_agenda().tutti(), studio_nome=studio_nome, base_url=base_url)
        return Response(
            ical_str,
            mimetype="text/calendar; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=agenda.ics"},
        )

    @app.route("/scadenziario/export.ics")
    def scadenziario_ical():
        from pct.ical import scadenze_to_ical

        studio_nome = app.config.get("STUDIO_NOME", "IUSENTRA")
        ical_str = scadenze_to_ical(get_scadenziario().tutte(), studio_nome=studio_nome)
        return Response(
            ical_str,
            mimetype="text/calendar; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=scadenze.ics"},
        )

    @app.route("/calendario/completo/export.ics")
    def calendario_completo_ical():
        from pct.ical import agenda_scadenze_to_ical

        studio_nome = app.config.get("STUDIO_NOME", "IUSENTRA")
        ical_str = agenda_scadenze_to_ical(
            get_agenda().tutti(),
            get_scadenziario().tutte(),
            studio_nome=studio_nome,
            base_url=_get_base_url(),
        )
        return Response(
            ical_str,
            mimetype="text/calendar; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=calendario-completo.ics"},
        )

    @app.route("/cal/<token>/agenda.ics")
    def cal_feed_agenda(token):
        if not _cal_token_valido(token):
            return Response("Token non valido.", status=403, mimetype="text/plain")
        from pct.ical import agenda_to_ical

        studio_nome = app.config.get("STUDIO_NOME", "IUSENTRA")
        ical_str = agenda_to_ical(
            get_agenda().tutti(),
            studio_nome=studio_nome,
            base_url=_get_base_url(),
        )
        return Response(
            ical_str,
            mimetype="text/calendar; charset=utf-8",
            headers={"Cache-Control": "no-cache, no-store"},
        )

    @app.route("/cal/<token>/scadenze.ics")
    def cal_feed_scadenze(token):
        if not _cal_token_valido(token):
            return Response("Token non valido.", status=403, mimetype="text/plain")
        from pct.ical import scadenze_to_ical

        studio_nome = app.config.get("STUDIO_NOME", "IUSENTRA")
        ical_str = scadenze_to_ical(get_scadenziario().tutte(), studio_nome=studio_nome)
        return Response(
            ical_str,
            mimetype="text/calendar; charset=utf-8",
            headers={"Cache-Control": "no-cache, no-store"},
        )

    @app.route("/cal/<token>/completo.ics")
    def cal_feed_completo(token):
        if not _cal_token_valido(token):
            return Response("Token non valido.", status=403, mimetype="text/plain")
        from pct.ical import agenda_scadenze_to_ical

        studio_nome = app.config.get("STUDIO_NOME", "IUSENTRA")
        ical_str = agenda_scadenze_to_ical(
            get_agenda().tutti(),
            get_scadenziario().tutte(),
            studio_nome=studio_nome,
            base_url=_get_base_url(),
        )
        return Response(
            ical_str,
            mimetype="text/calendar; charset=utf-8",
            headers={"Cache-Control": "no-cache, no-store"},
        )

    @app.route("/impostazioni/calendario")
    def impostazioni_calendario():
        from pct.cal_token import get_token

        token_data = get_token(_cal_token_dir())
        token = token_data["token"]
        base = _get_base_url()
        calendar_sync = get_calendar_sync()
        agenda = get_agenda()
        feeds = {
            "agenda": f"{base}/cal/{token}/agenda.ics",
            "scadenze": f"{base}/cal/{token}/scadenze.ics",
            "completo": f"{base}/cal/{token}/completo.ics",
        }
        gcal_completo = (
            "https://calendar.google.com/calendar/r/settings/addbyurl"
            f"?url={quote(feeds['completo'], safe='')}"
        )
        profili = calendar_sync.list_profiles()
        return render_template(
            "impostazioni/calendario.html",
            token=token,
            token_creato=token_data.get("creato_il", ""),
            feeds=feeds,
            gcal_url=gcal_completo,
            profili_sync=profili,
            profili_attivi=sum(1 for profilo in profili if profilo.get("enabled", True)),
            eventi_agenda=len(agenda.tutti()),
        )

    @app.route("/impostazioni/calendario/rigenera", methods=["POST"])
    def rigenera_token_calendario():
        from pct.cal_token import rigenera_token

        rigenera_token(_cal_token_dir())
        flash(
            "Collegamento calendario aggiornato. Ricorda di aggiornare i link nei tuoi calendari esterni.",
            "success",
        )
        return redirect(url_for("impostazioni_calendario"))

    @app.route("/impostazioni/calendario/profili", methods=["POST"])
    def crea_profilo_calendario():
        calendar_sync = get_calendar_sync()
        nome = (request.form.get("nome", "") or "").strip() or "Calendario esterno"
        source_url = (request.form.get("source_url", "") or "").strip()
        provider = (request.form.get("provider", "") or "").strip() or "webcal"
        default_tipo = request.form.get("default_tipo", TipoAppuntamento.ALTRO.value)
        reminder_raw = request.form.get("default_reminder_minuti", "60")
        try:
            reminder = max(int(reminder_raw or 60), 0)
        except (TypeError, ValueError):
            reminder = 60
        if not source_url:
            flash("Inserisci l'URL del calendario remoto.", "warning")
            return redirect(url_for("impostazioni_calendario"))
        try:
            preview = calendar_sync.preview_remote_calendar(source_url)
            profile = calendar_sync.create_profile(
                nome=nome,
                provider=provider,
                source_url=preview["source_url"],
                default_tipo=default_tipo,
                default_reminder_minuti=reminder,
                enabled=True,
            )
            flash(f"Profilo calendario '{profile['nome']}' creato.", "success")
        except Exception as exc:
            app.logger.exception("Errore crea profilo calendario: %s", exc)
            flash(f"Impossibile creare il profilo calendario: {exc}", "danger")
        return redirect(url_for("impostazioni_calendario"))

    @app.route("/impostazioni/calendario/profili/<profile_id>/sync", methods=["POST"])
    def sync_profilo_calendario(profile_id):
        calendar_sync = get_calendar_sync()
        try:
            report = calendar_sync.sync_profile(profile_id, agenda=get_agenda())
            flash(
                "Sincronizzazione completata: "
                f"{report['created']} creati, {report['updated']} aggiornati, "
                f"{report['skipped']} saltati, {report['conflicts']} conflitti.",
                "success",
            )
        except Exception as exc:
            app.logger.exception("Errore sync profilo calendario %s: %s", profile_id, exc)
            try:
                calendar_sync.mark_sync_error(profile_id, str(exc))
            except Exception:
                pass
            flash(f"Sincronizzazione non riuscita: {exc}", "danger")
        return redirect(url_for("impostazioni_calendario"))

    @app.route("/impostazioni/calendario/profili/<profile_id>/toggle", methods=["POST"])
    def toggle_profilo_calendario(profile_id):
        calendar_sync = get_calendar_sync()
        try:
            profilo = calendar_sync.get_profile(profile_id)
            if not profilo:
                flash("Profilo calendario non trovato.", "warning")
                return redirect(url_for("impostazioni_calendario"))
            calendar_sync.update_profile(profile_id, enabled=not bool(profilo.get("enabled", True)))
            flash("Profilo calendario aggiornato.", "success")
        except Exception as exc:
            app.logger.exception("Errore toggle profilo calendario %s: %s", profile_id, exc)
            flash(f"Impossibile aggiornare il profilo: {exc}", "danger")
        return redirect(url_for("impostazioni_calendario"))

    @app.route("/impostazioni/calendario/profili/<profile_id>/elimina", methods=["POST"])
    def elimina_profilo_calendario(profile_id):
        calendar_sync = get_calendar_sync()
        try:
            calendar_sync.delete_profile(profile_id)
            flash("Profilo calendario eliminato.", "success")
        except Exception as exc:
            app.logger.exception("Errore elimina profilo calendario %s: %s", profile_id, exc)
            flash(f"Impossibile eliminare il profilo: {exc}", "danger")
        return redirect(url_for("impostazioni_calendario"))

    @app.route("/api/scadenze/urgenti")
    def api_scadenze_urgenti():
        """Conta le scadenze aperte entro 7 giorni."""
        try:
            oggi_str = date.today().isoformat()
            soglia = (date.today() + timedelta(days=7)).isoformat()
            n = sum(
                1
                for scadenza in get_scadenziario().tutte()
                if getattr(scadenza, "data_scadenza", "")
                and oggi_str <= scadenza.data_scadenza <= soglia
                and getattr(scadenza, "stato", None)
                and scadenza.stato.value not in ("COMPLETATO", "ANNULLATO", "SCADUTO")
            )
            return jsonify({"n": n})
        except Exception as exc:
            app.logger.exception("api_scadenze_urgenti: %s", exc)
            return jsonify({"n": 0})
