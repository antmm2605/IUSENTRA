"""User profile, users, audit, and permissions routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for, g

from pct.auth import (
    DESCRIZIONI_RUOLI,
    PERMESSI,
    TUTTI_PERMESSI,
    GestioneUtenti,
    RuoloUtente,
    genera_totp_secret,
    totp_uri,
    verifica_totp,
)


def register_auth_management_routes(
    app: Flask,
    *,
    get_utenti: Callable[[], GestioneUtenti],
    audit: Callable[..., None],
) -> None:
    """Register profile, users, roles, and audit routes."""

    @app.route("/profilo", methods=["GET", "POST"])
    def profilo():
        u = g.utente_corrente
        if request.method == "POST":
            azione = request.form.get("azione")
            password_obbligatoria = bool(getattr(u, "must_change_password", False))
            gu = get_utenti()
            if password_obbligatoria and azione != "password":
                flash(
                    "Per motivi di sicurezza devi prima impostare una nuova password.",
                    "warning",
                )
                return redirect(url_for("profilo", password_obbligatoria=1))
            if azione == "aggiorna":
                try:
                    gu.aggiorna(
                        u.id,
                        nome_completo=request.form.get("nome_completo", ""),
                        email=request.form.get("email", ""),
                    )
                    flash("Profilo aggiornato.", "success")
                except ValueError as e:
                    flash(str(e), "danger")
            elif azione == "password":
                pwd_old = request.form.get("password_old", "")
                pwd_new = request.form.get("password_new", "")
                if not gu.autentica(u.username, pwd_old):
                    flash("Password attuale non corretta.", "danger")
                elif len(pwd_new) < 8:
                    flash("La nuova password deve avere almeno 8 caratteri.", "danger")
                else:
                    gu.cambia_password(u.id, pwd_new)
                    session["must_change_password"] = False
                    audit("auth.cambia_password")
                    if password_obbligatoria:
                        flash(
                            "Password aggiornata correttamente. Ora puoi continuare a usare il gestionale.",
                            "success",
                        )
                    else:
                        flash("Password aggiornata.", "success")
            elif azione == "2fa_genera":
                segreto = genera_totp_secret()
                session["totp_temp_secret"] = segreto
                flash(
                    "Configurazione avviata. Scansiona il QR code con la tua app di autenticazione e inserisci il codice per confermare.",
                    "info",
                )
            elif azione == "2fa_conferma":
                segreto = session.get("totp_temp_secret", "")
                codice = request.form.get("codice_2fa", "").strip()
                if segreto and verifica_totp(segreto, codice):
                    gu.aggiorna(u.id, totp_secret=segreto, totp_attivato=True)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_attivato")
                    flash("Verifica in due passaggi attivata con successo.", "success")
                else:
                    flash(
                        "Codice non valido. Prova a scansionare di nuovo il QR code con l'app.",
                        "danger",
                    )
            elif azione == "2fa_disattiva":
                pwd = request.form.get("pwd_disattiva", "")
                if gu.autentica(u.username, pwd):
                    gu.aggiorna(u.id, totp_secret="", totp_attivato=False)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_disattivato")
                    flash("Verifica in due passaggi disattivata.", "success")
                else:
                    flash("Password non corretta.", "danger")
            return redirect(url_for("profilo"))
        totp_temp = session.get("totp_temp_secret", "")
        uri_qr = totp_uri(totp_temp, u.username) if totp_temp else ""
        return render_template(
            "auth/profilo.html",
            utente=u,
            totp_temp_secret=totp_temp,
            totp_uri_qr=uri_qr,
            password_obbligatoria=bool(
                request.args.get("password_obbligatoria")
                or getattr(u, "must_change_password", False)
            ),
            oggi=date.today(),
        )

    @app.route("/utenti")
    def lista_utenti():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        gu = get_utenti()
        utenti = gu.tutti()
        stats = gu.statistiche()
        return render_template(
            "auth/utenti.html",
            utenti=utenti,
            stats=stats,
            ruoli=list(RuoloUtente),
            oggi=date.today(),
        )

    @app.route("/utenti/nuovo", methods=["GET", "POST"])
    def nuovo_utente():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        if request.method == "POST":
            gu = get_utenti()
            try:
                nuovo = gu.crea(
                    username=request.form["username"],
                    password=request.form["password"],
                    ruolo=RuoloUtente(request.form["ruolo"]),
                    email=request.form.get("email", ""),
                    nome_completo=request.form.get("nome_completo", ""),
                )
                audit("utenti.crea", "utente", nuovo.id, f"username={nuovo.username}")
                flash(
                    f"Utente '{nuovo.username}' creato. Al primo accesso dovrà cambiare la password temporanea.",
                    "success",
                )
                return redirect(url_for("lista_utenti"))
            except ValueError as e:
                flash(str(e), "danger")
        return render_template(
            "auth/form_utente.html",
            ruoli=list(RuoloUtente),
            utente=None,
            oggi=date.today(),
        )

    @app.route("/utenti/<id_utente>/modifica", methods=["GET", "POST"])
    def modifica_utente(id_utente):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        gu = get_utenti()
        target = gu.get(id_utente)
        if not target:
            flash("Utente non trovato.", "warning")
            return redirect(url_for("lista_utenti"))
        if request.method == "POST":
            try:
                nuova_password = request.form.get("nuova_password") or request.form.get("password")
                gu.aggiorna(
                    id_utente,
                    nome_completo=request.form.get("nome_completo", ""),
                    email=request.form.get("email", ""),
                    ruolo=request.form.get("ruolo", target.ruolo.value),
                    attivo=request.form.get("attivo") == "1",
                )
                if nuova_password:
                    gu.cambia_password(
                        id_utente,
                        nuova_password,
                        must_change_password=True,
                    )
                audit("utenti.modifica", "utente", id_utente)
                if nuova_password:
                    flash(
                        "Utente aggiornato. La nuova password temporanea dovrà essere cambiata al primo accesso.",
                        "success",
                    )
                else:
                    flash("Utente aggiornato.", "success")
                return redirect(url_for("lista_utenti"))
            except ValueError as e:
                flash(str(e), "danger")
        return render_template(
            "auth/form_utente.html",
            ruoli=list(RuoloUtente),
            utente=target,
            oggi=date.today(),
        )

    @app.route("/utenti/<id_utente>/elimina", methods=["POST"])
    def elimina_utente(id_utente):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.elimina"):
            abort(403)
        gu = get_utenti()
        try:
            gu.elimina(id_utente)
            audit("utenti.elimina", "utente", id_utente)
            flash("Utente eliminato.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_utenti"))

    @app.route("/audit")
    def audit_log():
        u = g.utente_corrente
        if not u or not u.ha_permesso("audit.leggi"):
            abort(403)
        gu = get_utenti()
        id_utente = request.args.get("id_utente", "")
        azione = request.args.get("azione", "")
        eventi = gu.audit_log(id_utente=id_utente, azione=azione, limit=200)
        utenti = gu.tutti()
        return render_template(
            "auth/audit.html",
            eventi=eventi,
            utenti=utenti,
            filtro_utente=id_utente,
            filtro_azione=azione,
            oggi=date.today(),
        )

    @app.route("/api/utenti/statistiche")
    def api_utenti_statistiche():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        try:
            return jsonify(get_utenti().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_utenti_statistiche: %s", e)
            return jsonify({"errore": str(e)}), 200

    @app.route("/profili")
    def profili():
        """Pagina matrice ruoli × permessi."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        gu = get_utenti()
        utenti_per_ruolo = {r: gu.per_ruolo(r) for r in RuoloUtente}
        return render_template(
            "auth/profili.html",
            ruoli=list(RuoloUtente),
            tutti_permessi=TUTTI_PERMESSI,
            permessi=PERMESSI,
            descrizioni=DESCRIZIONI_RUOLI,
            utenti_per_ruolo=utenti_per_ruolo,
            oggi=date.today(),
        )

    @app.route("/utenti/<id_utente>/permessi", methods=["GET", "POST"])
    def permessi_utente(id_utente):
        """Gestione override permessi per un singolo utente."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        gu = get_utenti()
        target = gu.get(id_utente)
        if not target:
            flash("Utente non trovato.", "warning")
            return redirect(url_for("lista_utenti"))
        if request.method == "POST":
            extra = request.form.getlist("permessi_extra")
            negati = request.form.getlist("permessi_negati")
            try:
                gu.aggiorna_permessi(id_utente, extra, negati)
                audit(
                    "utenti.aggiorna_permessi",
                    risorsa_tipo="utente",
                    risorsa_id=id_utente,
                    dettagli=f"extra={extra} negati={negati}",
                )
                flash(f"Permessi di {target.username} aggiornati.", "success")
            except ValueError as e:
                flash(str(e), "danger")
            return redirect(url_for("permessi_utente", id_utente=id_utente))
        return render_template(
            "auth/permessi_utente.html",
            target=target,
            tutti_permessi=TUTTI_PERMESSI,
            permessi_ruolo=PERMESSI.get(target.ruolo, []),
            descrizioni=DESCRIZIONI_RUOLI,
            oggi=date.today(),
        )
