"""Authentication and session bootstrap helpers extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

from pct.auth import GestioneUtenti, verifica_totp


def register_auth_runtime(
    app: Flask,
    *,
    get_utenti: Callable[[], GestioneUtenti],
    bootstrap_runtime_data_modules: Callable[[], dict[str, str]],
) -> None:
    """Register auth middleware and core authentication routes."""
    public_routes = {
        "login",
        "login_2fa",
        "static",
        "logout",
        "admin.esci_impersonazione",
        "polis_local_signer_download",
        "polis_local_ai_bridge_download",
        "polis_local_signer_download_uffici",
        "polis_local_signer_installa",
        "polis_local_signer_setup_windows",
        "polis_local_signer_setup_windows_exe",
        "polis_local_signer_setup_macos",
        "polis_local_signer_setup_linux",
    }

    def _tenant_user_manager(tenant_slug: str) -> GestioneUtenti:
        from pct.tenant import GestioneTenant

        tenants = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        paths = tenants.percorsi_dati(tenant_slug)
        return GestioneUtenti(
            db_path=paths["AUTH_DB"],
            audit_path=paths["AUDIT_DB"],
            secret_key=app.secret_key,
            crea_admin_se_vuoto=False,
        )

    @app.before_request
    def carica_utente_corrente():
        """Inject g.utente_corrente for every request; logout after 8h inactivity."""
        g.utente_corrente = None
        uid = session.get("user_id")
        if not uid:
            return None

        last = session.get("last_activity")
        if last:
            try:
                delta = datetime.now() - datetime.fromisoformat(last)
                if delta.total_seconds() > 8 * 3600:
                    session.clear()
                    return redirect(url_for("login", next=request.path, timeout=1))
            except ValueError:
                pass

        session["last_activity"] = datetime.now().isoformat()
        tenant_slug = session.get("tenant_slug", "")
        if tenant_slug and app.config.get("MULTI_TENANT"):
            manager = _tenant_user_manager(tenant_slug)
        else:
            manager = get_utenti()
        g.utente_corrente = manager.get(uid)
        return None

    @app.before_request
    def carica_tenant():
        """
        Inject g.tenant using tenant_slug in session.
        When multi-tenant is active, override per-request data paths in g.data_paths.
        """
        g.tenant = None
        g.data_paths = {}
        if not app.config.get("MULTI_TENANT"):
            return None

        user = getattr(g, "utente_corrente", None)
        tenant_slug = session.get("tenant_slug") or (user.tenant_slug if user else "")
        if not tenant_slug:
            return None

        from pct.tenant import GestioneTenant

        tenants = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        studio = tenants.get(tenant_slug)
        if studio:
            g.tenant = studio
            g.data_paths = tenants.percorsi_dati(tenant_slug)
            bootstrap_runtime_data_modules()
        return None

    @app.before_request
    def richiedi_login():
        if request.endpoint in public_routes:
            return None
        if request.endpoint and request.endpoint.startswith(("api_", "portale")):
            return None
        if g.utente_corrente is None:
            return redirect(url_for("login", next=request.path))
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.utente_corrente:
            return redirect(url_for("dashboard"))

        errore = None
        if request.method == "POST":
            studio_slug = request.form.get("studio_slug", "").strip().lower()
            if studio_slug and app.config.get("MULTI_TENANT"):
                from pct.tenant import GestioneTenant

                tenants = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
                studio = tenants.get(studio_slug)
                if not studio:
                    return render_template(
                        "auth/login.html",
                        errore="Studio non trovato.",
                        multi_tenant=True,
                    )
                manager = _tenant_user_manager(studio_slug)
            else:
                manager = get_utenti()

            utente = manager.autentica(
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
            if utente:
                if utente.totp_attivato:
                    session.clear()
                    session["totp_pending_uid"] = utente.id
                    session["totp_pending_next"] = request.args.get("next") or url_for(
                        "dashboard"
                    )
                    return redirect(url_for("login_2fa"))

                session.clear()
                session["user_id"] = utente.id
                session["tenant_slug"] = utente.tenant_slug or ""
                session["last_activity"] = datetime.now().isoformat()
                session.permanent = True
                manager.registra_evento(
                    "auth.login",
                    id_utente=utente.id,
                    username=utente.username,
                    ip=request.remote_addr or "",
                )
                next_url = request.args.get("next") or url_for("dashboard")
                return redirect(next_url)

            errore = "Credenziali non valide o utente disabilitato."
            manager.registra_evento(
                "auth.login_fallito",
                username=request.form.get("username", ""),
                ip=request.remote_addr or "",
                esito="ERRORE",
            )

        return render_template(
            "auth/login.html",
            errore=errore,
            multi_tenant=app.config.get("MULTI_TENANT", False),
        )

    @app.route("/logout", methods=["POST"])
    def logout():
        utente = g.utente_corrente
        if utente:
            get_utenti().registra_evento(
                "auth.logout",
                id_utente=utente.id,
                username=utente.username,
                ip=request.remote_addr or "",
            )
        session.clear()
        flash("Disconnessione effettuata.", "info")
        return redirect(url_for("login"))

    @app.route("/login/2fa", methods=["GET", "POST"])
    def login_2fa():
        """Second step of login: verify TOTP code."""
        uid = session.get("totp_pending_uid")
        if not uid:
            return redirect(url_for("login"))

        manager = get_utenti()
        utente = manager.get(uid)
        if not utente or not utente.totp_attivato:
            session.pop("totp_pending_uid", None)
            return redirect(url_for("login"))

        errore = None
        if request.method == "POST":
            codice = request.form.get("codice", "").strip()
            if verifica_totp(utente.totp_secret, codice):
                next_url = session.pop("totp_pending_next", url_for("dashboard"))
                session.clear()
                session["user_id"] = utente.id
                session["tenant_slug"] = utente.tenant_slug or ""
                session["last_activity"] = datetime.now().isoformat()
                session.permanent = True
                manager.registra_evento(
                    "auth.login",
                    id_utente=utente.id,
                    username=utente.username,
                    ip=request.remote_addr or "",
                )
                return redirect(next_url)

            errore = "Codice non valido. Riprova."
            manager.registra_evento(
                "auth.2fa_fallito",
                id_utente=utente.id,
                username=utente.username,
                ip=request.remote_addr or "",
                esito="ERRORE",
            )

        return render_template(
            "auth/login_2fa.html",
            errore=errore,
            username=utente.username,
        )
