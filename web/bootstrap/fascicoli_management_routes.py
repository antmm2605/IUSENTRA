"""Fascicoli management routes extracted from web.app."""

from __future__ import annotations

import io
import mimetypes
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from pct.fascicoli import StatoFascicolo, TipoFascicolo
from web.blueprints.react_shell import render_react_shell_response
from web.services.fascicoli_management_runtime import build_quadro_fascicolo_context


def _richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def _wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def register_fascicoli_management_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_soggetti: Callable[[], Any],
    get_config_studio: Callable[[], Any],
    cliente_accessibile: Callable[..., bool],
    audit: Callable[..., None],
    sync_pubblica: Callable[..., None],
    build_responsabile_conformita_fascicolo: Callable[..., Any],
    fascicolo_form_correction_context: Callable[[], dict[str, Any]],
) -> None:
    """Register management, archive, and API routes for fascicoli."""

    def _avvocato_titolare_studio() -> str:
        try:
            config_manager = get_config_studio()
            studio = getattr(getattr(config_manager, "config", None), "studio", None)
            avvocato = str(getattr(studio, "avvocato", "") or "").strip()
            if avvocato:
                return avvocato
        except Exception:
            pass
        return str(
            app.config.get("STUDIO_AVVOCATO")
            or app.config.get("PCT_STUDIO_AVVOCATO")
            or ""
        ).strip()

    @app.route("/fascicoli/<id_fasc>/copertina")
    def copertina_fascicolo(id_fasc: str):
        try:
            gf = get_fascicoli()
            gc = get_clienti()
            fascicolo = gf.get(id_fasc)
            if not fascicolo:
                flash("Fascicolo non trovato.", "warning")
                return redirect(url_for("lista_fascicoli"))
            cliente = gc.get(fascicolo.id_cliente) if fascicolo.id_cliente else None
            if fascicolo.id_cliente and not cliente_accessibile(fascicolo.id_cliente):
                flash("Non hai accesso a questo fascicolo.", "danger")
                return redirect(url_for("lista_fascicoli"))
            cfg_studio = get_config_studio()
            return render_template(
                "fascicoli/copertina.html",
                fascicolo=fascicolo,
                cliente=cliente,
                studio_nome=cfg_studio.nome or app.config.get("PCT_STUDIO_NOME", "Studio Legale"),
                oggi=date.today(),
            )
        except Exception as exc:
            app.logger.exception("Errore copertina_fascicolo %s: %s", id_fasc, exc)
            flash(f"Errore copertina fascicolo: {exc}", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/quadro")
    def quadro_fascicolo(id_fasc: str):
        if not _richiede_vista_classica():
            return render_react_shell_response(f"fascicoli/{id_fasc}/quadro")

        gf = get_fascicoli()
        gc = get_clienti()
        fascicolo = gf.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        cliente = gc.get(fascicolo.id_cliente) if fascicolo.id_cliente else None
        context = build_quadro_fascicolo_context(
            id_fasc=id_fasc,
            fascicolo=fascicolo,
            cliente=cliente,
            get_preventivi=get_preventivi,
            get_fatturazione=get_fatturazione,
            get_scadenziario=get_scadenziario,
            get_agenda=get_agenda,
            get_soggetti=get_soggetti,
            build_responsabile_conformita_fascicolo=build_responsabile_conformita_fascicolo,
        )
        return render_template(
            "fascicoli/quadro.html",
            fascicolo=fascicolo,
            cliente=cliente,
            oggi=date.today(),
            **context,
        )

    @app.route("/fascicoli/<id_fasc>/modifica", methods=["GET", "POST"])
    def modifica_fascicolo(id_fasc: str):
        if request.method == "GET" and not _richiede_vista_classica():
            return render_react_shell_response(f"fascicoli/{id_fasc}/modifica")

        gf = get_fascicoli()
        gc = get_clienti()
        fascicolo = gf.get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        if request.method == "POST":
            form = request.form
            id_cliente = form.get("id_cliente", fascicolo.id_cliente)
            nome_cliente = fascicolo.nome_cliente
            if id_cliente:
                cliente = gc.get(id_cliente)
                nome_cliente = cliente.nome_completo if cliente else nome_cliente
            try:
                avvocato_referente = (
                    form.get("avvocato_referente", "").strip()
                    or _avvocato_titolare_studio()
                    or str(getattr(fascicolo, "avvocato_referente", "") or "").strip()
                )
                gf.aggiorna(
                    id_fasc,
                    titolo=form.get("titolo", fascicolo.titolo),
                    tipo=TipoFascicolo(form.get("tipo", fascicolo.tipo.value)),
                    id_cliente=id_cliente,
                    nome_cliente=nome_cliente,
                    controparte=form.get("controparte", ""),
                    tribunale=form.get("tribunale", ""),
                    numero_rg=form.get("numero_rg", ""),
                    anno_rg=int(form.get("anno_rg") or 0),
                    giudice=form.get("giudice", ""),
                    sezione=form.get("sezione", ""),
                    data_prima_udienza=form.get("data_prima_udienza", ""),
                    data_notifica_citazione=form.get("data_notifica_citazione", ""),
                    avvocato_referente=avvocato_referente,
                    avvocato_dominus=form.get("avvocato_dominus", ""),
                    oggetto=form.get("oggetto", ""),
                    valore_causa=float(form.get("valore_causa") or 0),
                    note=form.get("note", ""),
                )
                flash("Fascicolo aggiornato.", "success")
                sync_pubblica("modifica", "fascicoli", id_fasc)
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            except (ValueError, KeyError) as exc:
                flash(str(exc), "danger")

        return render_template(
            "fascicoli/form.html",
            fascicolo=fascicolo,
            clienti=gc.tutti(stato=None),
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
            id_cliente_pre="",
            studio_avvocato_titolare=_avvocato_titolare_studio(),
            correction_context=fascicolo_form_correction_context(),
            oggi=date.today(),
        )

    @app.route("/fascicoli/<id_fasc>/stato", methods=["POST"])
    def cambia_stato_fascicolo(id_fasc: str):
        gf = get_fascicoli()
        form = request.form
        try:
            gf.cambia_stato(
                id_fasc,
                StatoFascicolo(form.get("stato")),
                note=form.get("note", ""),
                avvocato=form.get("avvocato", ""),
            )
            flash("Stato aggiornato.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/conformita/controlli", methods=["POST"])
    def toggle_controlli_conformita_fascicolo(id_fasc: str):
        gf = get_fascicoli()
        enabled = str(request.form.get("enabled", "1") or "").strip().lower() in {"1", "true", "on", "yes"}
        next_url = str(request.form.get("next") or "").strip()
        try:
            gf.aggiorna(id_fasc, compliance_controls_enabled=enabled)
            audit(
                "fascicoli.conformita.controlli",
                "fascicolo",
                id_fasc,
                dettagli=f"Controlli automatici {'attivati' if enabled else 'disattivati'}",
            )
            sync_pubblica("modifica", "fascicoli", id_fasc)
            flash(
                "Controlli automatici attivati." if enabled else "Controlli automatici disattivati.",
                "success",
            )
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        if next_url:
            return redirect(next_url)
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-responsabile-conformita")

    @app.route("/fascicoli/<id_fasc>/definisci", methods=["POST"])
    def definisci_fascicolo(id_fasc: str):
        gf = get_fascicoli()
        form = request.form
        try:
            gf.definisci(
                id_fasc,
                esito_finale=form.get("esito_finale", ""),
                motivo=form.get("motivo", ""),
                note=form.get("note", ""),
                avvocato=form.get("avvocato", ""),
            )
            flash("Fascicolo definito. Pronto per l'archiviazione.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/archivia", methods=["POST"])
    def archivia_fascicolo(id_fasc: str):
        gf = get_fascicoli()
        try:
            gf.archivia(
                id_fasc,
                crea_zip=request.form.get("crea_zip", "1") == "1",
                avvocato=request.form.get("avvocato", ""),
            )
            flash("Fascicolo archiviato con successo.", "success")
            return redirect(url_for("lista_archivio"))
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/ripristina", methods=["POST"])
    def ripristina_fascicolo(id_fasc: str):
        try:
            get_fascicoli().ripristina_da_archivio(id_fasc, avvocato=request.form.get("avvocato", ""))
            flash("Fascicolo ripristinato dall'archivio.", "success")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
            return redirect(url_for("lista_archivio"))

    @app.route("/fascicoli/<id_fasc>/elimina", methods=["POST"])
    def elimina_fascicolo(id_fasc: str):
        try:
            get_fascicoli().elimina(id_fasc)
            session["recenti"] = [
                item
                for item in session.get("recenti", [])
                if not (item["tipo"] == "fascicolo" and item["id"] == id_fasc)
            ]
            msg = "Fascicolo eliminato."
            flash(msg, "success")
            sync_pubblica("elimina", "fascicoli", id_fasc)
            if _wants_json_response():
                return jsonify({"ok": True, "messaggio": msg, "redirect_url": url_for("lista_fascicoli")})
        except KeyError as exc:
            if _wants_json_response():
                return jsonify({"ok": False, "messaggio": str(exc)}), 404
            flash(str(exc), "danger")
        return redirect(url_for("lista_fascicoli"))

    @app.route("/fascicoli/<id_fasc>/archivio/contenuto")
    def archivio_contenuto(id_fasc: str):
        try:
            return jsonify(get_fascicoli().contenuto_archivio(id_fasc))
        except Exception as exc:
            app.logger.exception("archivio_contenuto %s: %s", id_fasc, exc)
            return jsonify({"errore": str(exc)}), 200

    @app.route("/fascicoli/<id_fasc>/archivio/file/<path:nome_file>")
    def archivio_scarica_file(id_fasc: str, nome_file: str):
        try:
            dati = get_fascicoli().estrai_file_archivio(id_fasc, nome_file)
        except FileNotFoundError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("lista_archivio"))

        mime, _ = mimetypes.guess_type(nome_file)
        return send_file(
            io.BytesIO(dati),
            mimetype=mime or "application/octet-stream",
            as_attachment=True,
            download_name=Path(nome_file).name,
        )

    @app.route("/fascicoli/<id_fasc>/archivio/scarica")
    def scarica_archivio(id_fasc: str):
        fascicolo = get_fascicoli().get(id_fasc)
        if not fascicolo or not fascicolo.archivio or not fascicolo.archivio.percorso_zip:
            flash("Archivio ZIP non disponibile.", "warning")
            return redirect(url_for("lista_archivio"))
        path = Path(fascicolo.archivio.percorso_zip)
        if not path.exists():
            flash("File archivio non trovato su disco.", "danger")
            return redirect(url_for("lista_archivio"))
        return send_file(
            path,
            as_attachment=True,
            download_name=f"fascicolo_{fascicolo.numero.replace('/', '_')}.zip",
        )

    @app.route("/api/fascicoli")
    def api_fascicoli():
        try:
            query = request.args.get("q", "")
            archiviati = request.args.get("archiviati", "0") == "1"
            fascicoli = get_fascicoli().cerca(testo=query, archiviati=archiviati)
            return jsonify([fascicolo.to_dict() for fascicolo in fascicoli])
        except Exception as exc:
            app.logger.exception("Errore api_fascicoli: %s", exc)
            return jsonify([])

    @app.route("/api/fascicoli/<id_fasc>")
    def api_fascicolo(id_fasc: str):
        try:
            fascicolo = get_fascicoli().get(id_fasc)
            if not fascicolo:
                return jsonify({"errore": "Non trovato"}), 404
            return jsonify(fascicolo.to_dict())
        except Exception as exc:
            app.logger.exception("Errore api_fascicolo: %s", exc)
            return jsonify({"errore": str(exc)})

    @app.route("/api/fascicoli/statistiche")
    def api_fascicoli_statistiche():
        try:
            return jsonify(get_fascicoli().statistiche())
        except Exception as exc:
            app.logger.exception("Errore api_fascicoli_statistiche: %s", exc)
            return jsonify({"errore": str(exc)})
