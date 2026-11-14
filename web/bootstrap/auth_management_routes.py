"""User profile, users, audit, and permissions routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, abort, flash, jsonify, redirect, request, session, url_for, g

from pct.auth import (
    PERMESSI,
    GestioneUtenti,
    RuoloUtente,
    genera_totp_secret,
    verifica_totp,
)
from web.blueprints.react_shell import render_react_shell_response
from web.services.accesso_shell_runtime import render_accesso_shell


def register_auth_management_routes(
    app: Flask,
    *,
    get_utenti: Callable[[], GestioneUtenti],
    audit: Callable[..., None],
) -> None:
    """Register profile, users, roles, and audit routes."""

    def _auth_manager() -> GestioneUtenti:
        return getattr(g, "utente_auth_manager", None) or get_utenti()

    def _ruoli_gestibili_legacy() -> list[RuoloUtente]:
        return [ruolo for ruolo in RuoloUtente if ruolo != RuoloUtente.SUPERADMIN]

    def _redirect_superadmin_piattaforma():
        utente = g.utente_corrente
        if not app.config.get("MULTI_TENANT"):
            return None
        if not utente or not getattr(utente, "is_superadmin", False):
            return None
        flash(
            "Il ruolo SUPERADMIN si gestisce solo dal pannello piattaforma dedicato.",
            "info",
        )
        return redirect(url_for("admin.utenti_piattaforma"))

    def _permessi_sessione() -> set[str]:
        return set(getattr(g.utente_corrente, "permessi_effettivi", []) or [])

    def _ruolo_legacy_da_form(ruolo_raw: str) -> RuoloUtente:
        ruolo = RuoloUtente(ruolo_raw)
        if ruolo == RuoloUtente.SUPERADMIN:
            raise ValueError(
                "Il ruolo SUPERADMIN si gestisce solo dal pannello piattaforma."
            )
        # Una delega parziale («utenti.scrivi») non diventa totale: si assegna
        # solo un ruolo i cui permessi la sessione possiede già (come nell'API React).
        if not getattr(g.utente_corrente, "is_superadmin", False) and not set(PERMESSI.get(ruolo, []) or []).issubset(_permessi_sessione()):
            raise ValueError(
                "Ruolo non assegnabile: richiede permessi che il tuo account non ha."
            )
        return ruolo


    def _wants_json_response() -> bool:
        return (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in (request.headers.get("Accept") or "")
        )

    @app.route("/profilo", methods=["GET", "POST"])
    def profilo():
        u = g.utente_corrente
        if request.method == "POST":
            azione = request.form.get("azione")
            password_obbligatoria = bool(getattr(u, "must_change_password", False))
            gu = _auth_manager()
            if password_obbligatoria and azione != "password":
                message = "Per motivi di sicurezza devi prima impostare una nuova password."
                if _wants_json_response():
                    return jsonify({"ok": False, "message": message, "redirect": url_for("profilo", password_obbligatoria=1)}), 400
                flash(message, "warning")
                return redirect(url_for("profilo", password_obbligatoria=1))
            ok = True
            status_code = 200
            category = "success"
            message = "Profilo aggiornato."
            if azione == "aggiorna":
                try:
                    gu.aggiorna(
                        u.id,
                        nome_completo=request.form.get("nome_completo", ""),
                        email=request.form.get("email", ""),
                    )
                    message = "Profilo aggiornato."
                except ValueError as e:
                    ok = False
                    status_code = 400
                    category = "danger"
                    message = "Profilo non aggiornato. Controlla i dati inseriti."
            elif azione == "password":
                pwd_old = request.form.get("password_old", "")
                pwd_new = request.form.get("password_new", "")
                if not gu.autentica(u.username, pwd_old):
                    ok = False
                    status_code = 400
                    category = "danger"
                    message = "Password attuale non corretta."
                elif len(pwd_new) < 8:
                    ok = False
                    status_code = 400
                    category = "danger"
                    message = "La nuova password deve avere almeno 8 caratteri."
                else:
                    gu.cambia_password(u.id, pwd_new)
                    session["must_change_password"] = False
                    # Questa sessione resta aperta; le altre dello stesso utente si chiudono.
                    from web.services.auth_runtime import impronta_credenziali

                    aggiornato = gu.get(u.id) if hasattr(gu, "get") else None
                    if aggiornato is not None:
                        session["credenziali"] = impronta_credenziali(aggiornato)
                    audit("auth.cambia_password")
                    if password_obbligatoria:
                        message = "Password aggiornata correttamente. Ora puoi continuare a usare il gestionale."
                    else:
                        message = "Password aggiornata."
            elif azione == "2fa_genera":
                segreto = genera_totp_secret()
                session["totp_temp_secret"] = segreto
                category = "info"
                message = "Configurazione avviata. Inserisci il codice dell'app di autenticazione per confermare."
            elif azione == "2fa_conferma":
                segreto = session.get("totp_temp_secret", "")
                codice = request.form.get("codice_2fa", "").strip()
                if segreto and verifica_totp(segreto, codice):
                    gu.imposta_verifica_due_passaggi(u.id, segreto=segreto, attiva=True)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_attivato")
                    message = "Verifica in due passaggi attivata con successo."
                else:
                    ok = False
                    status_code = 400
                    category = "danger"
                    message = "Codice non valido. Prova a generare di nuovo la configurazione."
            elif azione == "2fa_disattiva":
                pwd = request.form.get("pwd_disattiva", "")
                if gu.autentica(u.username, pwd):
                    gu.imposta_verifica_due_passaggi(u.id, segreto="", attiva=False)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_disattivato")
                    message = "Verifica in due passaggi disattivata."
                else:
                    ok = False
                    status_code = 400
                    category = "danger"
                    message = "Password non corretta."
            else:
                ok = False
                status_code = 400
                category = "danger"
                message = "Azione profilo non riconosciuta."
            if _wants_json_response():
                return jsonify({"ok": ok, "message": message, "redirect": url_for("profilo")}), status_code
            flash(message, category)
            return redirect(url_for("profilo"))
        password_obbligatoria = bool(
            request.args.get("password_obbligatoria")
            or getattr(u, "must_change_password", False)
        )
        if password_obbligatoria:
            # Cambio obbligatorio della password: pagina React di accesso,
            # senza la cornice dello studio (ancora inaccessibile).
            return render_accesso_shell("password", titolo="Nuova password")
        return render_react_shell_response("profilo")

    @app.route("/utenti")
    def lista_utenti():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        platform_redirect = _redirect_superadmin_piattaforma()
        if platform_redirect is not None:
            return platform_redirect
        # Utenti dello studio: pagina React (UtentiPage).
        return render_react_shell_response("utenti")

    @app.route("/utenti/nuovo", methods=["GET", "POST"])
    def nuovo_utente():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        platform_redirect = _redirect_superadmin_piattaforma()
        if platform_redirect is not None:
            return platform_redirect
        if request.method == "POST":
            gu = _auth_manager()
            try:
                nuovo = gu.crea(
                    username=request.form["username"],
                    password=request.form["password"],
                    ruolo=_ruolo_legacy_da_form(request.form["ruolo"]),
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
        # Nuovo utente: pagina React (UtentiPage); salvataggio da /api/v1/ui/utenti.
        if request.method == "POST":
            return redirect(request.path)
        return render_react_shell_response("utenti/nuovo")

    @app.route("/utenti/<id_utente>/modifica", methods=["GET", "POST"])
    def modifica_utente(id_utente):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        platform_redirect = _redirect_superadmin_piattaforma()
        if platform_redirect is not None:
            return platform_redirect
        gu = _auth_manager()
        target = gu.get(id_utente)
        if not target:
            flash("Utente non trovato.", "warning")
            return redirect(url_for("lista_utenti"))
        if target.ruolo == RuoloUtente.SUPERADMIN:
            flash(
                "L'account SUPERADMIN si gestisce solo dal pannello piattaforma.",
                "warning",
            )
            return redirect(url_for("admin.utenti_piattaforma"))
        if request.method == "POST":
            try:
                nuova_password = request.form.get("nuova_password") or request.form.get("password")
                gu.aggiorna(
                    id_utente,
                    nome_completo=request.form.get("nome_completo", ""),
                    email=request.form.get("email", ""),
                    ruolo=_ruolo_legacy_da_form(
                        request.form.get("ruolo", target.ruolo.value)
                    ),
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
        # Modifica utente: pagina React (UtentiPage).
        if request.method == "POST":
            return redirect(request.path)
        return render_react_shell_response(f"utenti/{id_utente}/modifica")

    @app.route("/utenti/<id_utente>/elimina", methods=["POST"])
    def elimina_utente(id_utente):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.elimina"):
            abort(403)
        platform_redirect = _redirect_superadmin_piattaforma()
        if platform_redirect is not None:
            return platform_redirect
        gu = _auth_manager()
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
        platform_redirect = _redirect_superadmin_piattaforma()
        if platform_redirect is not None:
            return platform_redirect
        # Registro attività: pagina React (AuditPage); eventi da /api/v1/ui/audit.
        return render_react_shell_response("audit")

    @app.route("/api/utenti/statistiche")
    def api_utenti_statistiche():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        if app.config.get("MULTI_TENANT") and u.is_superadmin:
            return (
                jsonify(
                    {
                        "errore": "Il ruolo SUPERADMIN usa il pannello piattaforma dedicato.",
                        "redirect_url": url_for("admin.utenti_piattaforma"),
                    }
                ),
                403,
            )
        try:
            return jsonify(_auth_manager().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_utenti_statistiche: %s", e)
            return jsonify({"errore": "Statistiche utenti non disponibili."}), 200

    @app.route("/profili")
    def profili():
        """Pagina matrice ruoli × permessi."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        platform_redirect = _redirect_superadmin_piattaforma()
        if platform_redirect is not None:
            return platform_redirect
        # Profili e permessi: pagina React (ProfiliPage).
        return render_react_shell_response("profili")

    @app.route("/utenti/<id_utente>/permessi", methods=["GET", "POST"])
    def permessi_utente(id_utente):
        """Gestione override permessi per un singolo utente."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            abort(403)
        platform_redirect = _redirect_superadmin_piattaforma()
        if platform_redirect is not None:
            return platform_redirect
        gu = _auth_manager()
        target = gu.get(id_utente)
        if not target:
            flash("Utente non trovato.", "warning")
            return redirect(url_for("lista_utenti"))
        if target.ruolo == RuoloUtente.SUPERADMIN:
            flash(
                "L'account SUPERADMIN si gestisce solo dal pannello piattaforma.",
                "warning",
            )
            return redirect(url_for("admin.utenti_piattaforma"))
        if request.method == "POST":
            extra = request.form.getlist("permessi_extra")
            negati = request.form.getlist("permessi_negati")
            if target.id == u.id:
                flash("Non puoi modificare i tuoi permessi: chiedi a un altro amministratore.", "danger")
                return redirect(url_for("permessi_utente", id_utente=id_utente))
            non_concedibili = sorted(set(extra) - _permessi_sessione())
            if non_concedibili and not getattr(u, "is_superadmin", False):
                flash("Non puoi concedere permessi che il tuo account non ha: " + ", ".join(non_concedibili), "danger")
                return redirect(url_for("permessi_utente", id_utente=id_utente))
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
        # Permessi del singolo utente: pagina React (UtentiPage).
        return render_react_shell_response(f"utenti/{id_utente}/permessi")
