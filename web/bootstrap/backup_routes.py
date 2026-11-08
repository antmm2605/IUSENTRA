"""Backup routes extracted from web.app."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, url_for

from pct.backup import StatoBackup, TipoBackup, backup_operations_disabled
from web.services.permessi_route import permesso_negato
from web.services.react_backup_bridge import cartella_ripristini

# Le copie contengono tutti i dati dello studio (anagrafiche, fascicoli, documenti):
# consultazione con «backup.leggi», creazione/verifica/eliminazione/ripristino con
# «backup.esegui» (art. 32 GDPR, controllo degli accessi; segreto professionale,
# art. 13 L. 247/2012). Il ripristino scrive solo in una sottocartella dei ripristini.
_CARTELLA_RIPRISTINO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def register_backup_routes(
    app: Flask,
    *,
    get_backup: Callable[[], object],
) -> None:
    """Register backup CRUD, verification, restore, and stats routes."""

    def _negato(permesso: str):
        messaggio = (
            "Non hai il permesso per consultare le copie di sicurezza."
            if permesso == "backup.leggi"
            else "Non hai il permesso per gestire le copie di sicurezza."
        )
        return permesso_negato(permesso, messaggio, url_for("lista_backup") if permesso != "backup.leggi" else url_for("dashboard"))

    def _audit(azione: str, id_bk: str, dettagli: str = "") -> None:
        try:
            audit = (app.extensions.get("core_runtime", {}) or {}).get("audit")
            if callable(audit):
                audit(azione, "backup", id_bk, dettagli)
        except Exception:
            app.logger.warning("Audit %s non registrato per il backup %s.", azione, id_bk)

    @app.route("/backup")
    def lista_backup():
        negato = _negato("backup.leggi")
        if negato is not None:
            return negato
        gb = get_backup()
        backup_list = gb.tutti()
        stats = gb.statistiche()
        return render_template(
            "backup/lista.html",
            backup_list=backup_list,
            stats=stats,
            config=gb.config,
            tipi=list(TipoBackup),
            stati=list(StatoBackup),
        )

    @app.route("/backup/esegui", methods=["POST"])
    def esegui_backup():
        negato = _negato("backup.esegui")
        if negato is not None:
            return negato
        if backup_operations_disabled(app.config):
            flash("Creazione copie disattivata dalla politica operativa dello studio.", "info")
            return redirect(url_for("lista_backup"))
        gb = get_backup()
        tipo = TipoBackup(request.form.get("tipo", "COMPLETO"))
        nota = request.form.get("nota", "")
        componenti_raw = request.form.getlist("componenti")
        componenti = componenti_raw if componenti_raw else None
        try:
            record = gb.esegui_backup(tipo=tipo, componenti=componenti, nota=nota)
            if record.stato == StatoBackup.OK:
                flash(
                    f"Backup completato: {record.num_file} file, "
                    f"{round(record.dimensione_bytes / 1024 / 1024, 2)} MB.",
                    "success",
                )
            else:
                flash(f"Backup fallito: {record.errore}", "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/verifica", methods=["POST"])
    def verifica_backup(id_bk):
        negato = _negato("backup.esegui")
        if negato is not None:
            return negato
        gb = get_backup()
        try:
            ris = gb.verifica_integrita(id_bk)
            if ris["ok"]:
                flash("Verifica completata: il backup è integro.", "success")
            else:
                flash("Attenzione: il file di backup potrebbe essere corrotto.", "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/elimina", methods=["POST"])
    def elimina_backup(id_bk):
        negato = _negato("backup.esegui")
        if negato is not None:
            return negato
        gb = get_backup()
        try:
            gb.elimina(id_bk)
            _audit("backup.elimina", id_bk)
            flash("Backup eliminato.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/scarica")
    def scarica_backup(id_bk):
        negato = _negato("backup.leggi")
        if negato is not None:
            return negato
        gb = get_backup()
        record = gb.get(id_bk)
        if not record:
            flash("Backup non trovato.", "warning")
            return redirect(url_for("lista_backup"))
        p = Path(record.percorso_file).resolve()
        if not p.exists():
            flash("File backup non trovato su disco.", "danger")
            return redirect(url_for("lista_backup"))
        _audit("backup.scarica", id_bk, f"Copia scaricata da {getattr(g.get('utente_corrente'), 'username', '')}")
        return send_file(p, as_attachment=True, download_name=p.name)

    @app.route("/backup/<id_bk>/ripristina", methods=["GET", "POST"])
    def ripristina_backup(id_bk):
        negato = _negato("backup.esegui")
        if negato is not None:
            return negato
        gb = get_backup()
        record = gb.get(id_bk)
        if not record:
            flash("Backup non trovato.", "warning")
            return redirect(url_for("lista_backup"))
        if request.method == "POST":
            nome_cartella = Path(request.form.get("destinazione", "") or "").name.strip()
            nome_cartella = nome_cartella or datetime.now().strftime("ripristino-%Y%m%d-%H%M%S")
            if not _CARTELLA_RIPRISTINO.fullmatch(nome_cartella):
                flash("Nome della cartella di ripristino non valido: usa solo lettere, cifre, trattini e trattini bassi.", "danger")
                return render_template("backup/ripristina.html", record=record)
            dest = str(cartella_ripristini(gb) / nome_cartella)
            componenti_raw = request.form.getlist("componenti")
            componenti = componenti_raw if componenti_raw else None
            sovrascrivi = request.form.get("sovrascrivi") == "1"
            password = request.form.get("password", "")
            try:
                ris = gb.ripristina(
                    id_bk,
                    dest,
                    componenti=componenti,
                    password=password,
                    sovrascrivi=sovrascrivi,
                )
                _audit("backup.ripristina", id_bk, f"Cartella {nome_cartella}: {ris['file_ripristinati']} file")
                flash(
                    f"Ripristino completato in «ripristini/{nome_cartella}»: {ris['file_ripristinati']} file ripristinati, "
                    f"{ris['file_saltati']} saltati.",
                    "success",
                )
                return redirect(url_for("lista_backup"))
            except Exception as e:
                flash(str(e), "danger")
        return render_template("backup/ripristina.html", record=record)

    @app.route("/api/backup/statistiche")
    def api_backup_statistiche():
        utente = g.get("utente_corrente")
        if utente is None or not utente.ha_permesso("backup.leggi"):
            return jsonify({"errore": "Permesso backup.leggi richiesto."}), 403
        try:
            return jsonify(get_backup().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_backup_statistiche: %s", e)
            return jsonify({"errore": str(e)})
