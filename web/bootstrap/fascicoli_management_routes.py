"""Fascicoli management routes extracted from web.app."""

from __future__ import annotations

import io
import mimetypes
import sqlite3
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from pct.fascicoli import StatoFascicolo, TipoFascicolo
from web.blueprints.react_shell import render_react_shell_response
from web.services.app_v2_routing import is_safe_internal_path
from web.services.fascicoli_management_runtime import build_quadro_fascicolo_context


def _richiede_vista_classica() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def _wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def _sqlite_transient_message(exc: BaseException) -> str:
    message = str(exc).lower()
    if "database is locked" in message or "database table is locked" in message:
        return "Il database locale è momentaneamente occupato. Riprova il salvataggio tra pochi secondi."
    if "unable to open database file" in message:
        return "Il database locale non è raggiungibile in scrittura in questo momento. Riprova dopo il ricaricamento della pagina."
    return ""


def _form_result(message: str, *, status: int, redirect_to: str = "", category: str = "danger"):
    if _wants_json_response():
        return jsonify({"ok": status < 400, "message": message, "redirect": redirect_to}), status
    flash(message, category)
    if redirect_to:
        return redirect(redirect_to)
    return None


def _safe_internal_redirect(target: str, fallback: str) -> str:
    cleaned = str(target or "").strip()
    return cleaned if cleaned and is_safe_internal_path(cleaned) else fallback


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
                    giudice=form.get("giudice", "") or form.get("istruttore_pm_gip", ""),
                    sezione=form.get("sezione", ""),
                    data_prima_udienza=form.get("data_prima_udienza", ""),
                    data_notifica_citazione=form.get("data_notifica_citazione", ""),
                    avvocato_referente=avvocato_referente,
                    avvocato_dominus=form.get("avvocato_dominus", ""),
                    oggetto=form.get("oggetto", ""),
                    valore_causa=float(form.get("valore_causa") or 0),
                    valore_preventivato=float(form.get("valore_preventivato") or 0),
                    tipo_procedimento=form.get("tipo_procedimento", ""),
                    id_pratica=form.get("id_pratica", ""),
                    area_pratica=form.get("area_pratica", ""),
                    procedura_operativa_codice=form.get("procedura_operativa_codice", "").strip(),
                    codice_oggetto_pst=form.get("codice_oggetto_pst", "").strip(),
                    fonte_codice_oggetto=form.get("fonte_codice_oggetto", "").strip(),
                    file_fonte_codice_oggetto=form.get("file_fonte_codice_oggetto", "").strip(),
                    riferimento_cartaceo=form.get("riferimento_cartaceo", "").strip(),
                    attore_principale=form.get("attore_principale", "").strip(),
                    istruttore_pm_gip=form.get("istruttore_pm_gip", "").strip(),
                    cancelliere=form.get("cancelliere", "").strip(),
                    ctu=form.get("ctu", "").strip(),
                    ctp=form.get("ctp", "").strip(),
                    stato_pratica_operativa=form.get("stato_pratica_operativa", "").strip(),
                    personalizzabile=form.get("personalizzabile") in {"1", "true", "on", "si", "sì"},
                    data_apertura=form.get("data_apertura", "").strip() or getattr(fascicolo, "data_apertura", ""),
                    data_chiusura=form.get("data_chiusura", "").strip(),
                    compenso_pattuito=float(form.get("compenso_pattuito") or 0),
                    note=form.get("note", ""),
                )
                sync_pubblica("modifica", "fascicoli", id_fasc)
                redirect_to = url_for("dettaglio_fascicolo", id_fasc=id_fasc)
                result = _form_result("Fascicolo aggiornato.", status=200, redirect_to=redirect_to, category="success")
                if result is not None:
                    return result
                return redirect(redirect_to)
            except (ValueError, KeyError) as exc:
                app.logger.info("Validazione modifica_fascicolo %s non superata: %s", id_fasc, exc)
                result = _form_result("Dati fascicolo non validi.", status=400)
                if result is not None:
                    return result
            except sqlite3.OperationalError as exc:
                app.logger.exception("Errore SQLite modifica_fascicolo %s: %s", id_fasc, exc)
                message = _sqlite_transient_message(exc) or "Impossibile salvare il fascicolo per un errore del database locale."
                result = _form_result(message, status=503)
                if result is not None:
                    return result
            except Exception as exc:
                app.logger.exception("Errore modifica_fascicolo %s: %s", id_fasc, exc)
                result = _form_result("Errore imprevisto durante il salvataggio del fascicolo.", status=500)
                if result is not None:
                    return result

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
            app.logger.info("Cambio stato fascicolo %s non valido: %s", id_fasc, exc)
            flash("Stato fascicolo non aggiornato.", "danger")
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
            app.logger.info("Controlli conformita fascicolo %s non aggiornati: %s", id_fasc, exc)
            flash("Controlli automatici non aggiornati.", "danger")
        fallback_url = url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-responsabile-conformita"
        return redirect(_safe_internal_redirect(next_url, fallback_url))

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
            app.logger.info("Definizione fascicolo %s non valida: %s", id_fasc, exc)
            flash("Dati di definizione fascicolo non validi.", "danger")
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
            app.logger.info("Archiviazione fascicolo %s non completata: %s", id_fasc, exc)
            flash("Fascicolo non archiviato.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/ripristina", methods=["POST"])
    def ripristina_fascicolo(id_fasc: str):
        try:
            get_fascicoli().ripristina_da_archivio(id_fasc, avvocato=request.form.get("avvocato", ""))
            flash("Fascicolo ripristinato dall'archivio.", "success")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        except (ValueError, KeyError) as exc:
            app.logger.info("Ripristino fascicolo %s non completato: %s", id_fasc, exc)
            flash("Fascicolo non ripristinato.", "danger")
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
                return jsonify({"ok": False, "messaggio": "Fascicolo non trovato."}), 404
            app.logger.info("Eliminazione fascicolo %s non completata: %s", id_fasc, exc)
            flash("Fascicolo non trovato.", "danger")
        return redirect(url_for("lista_fascicoli"))

    @app.route("/fascicoli/<id_fasc>/archivio/contenuto")
    def archivio_contenuto(id_fasc: str):
        try:
            return jsonify(get_fascicoli().contenuto_archivio(id_fasc))
        except Exception as exc:
            app.logger.exception("archivio_contenuto %s: %s", id_fasc, exc)
            return jsonify({"errore": "Archivio non leggibile in questo momento."}), 200

    @app.route("/fascicoli/<id_fasc>/archivio/file/<path:nome_file>")
    def archivio_scarica_file(id_fasc: str, nome_file: str):
        try:
            dati = get_fascicoli().estrai_file_archivio(id_fasc, nome_file)
        except FileNotFoundError as exc:
            app.logger.info("File archivio non trovato %s/%s: %s", id_fasc, nome_file, exc)
            flash("File archivio non trovato.", "warning")
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
            return jsonify({"errore": "Fascicolo non leggibile in questo momento."})

    @app.route("/api/fascicoli/statistiche")
    def api_fascicoli_statistiche():
        try:
            return jsonify(get_fascicoli().statistiche())
        except Exception as exc:
            app.logger.exception("Errore api_fascicoli_statistiche: %s", exc)
            return jsonify({"errore": "Statistiche fascicoli non disponibili in questo momento."})
