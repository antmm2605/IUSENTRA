"""Authentication and session bootstrap helpers extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import sqlite3

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

from pct.auth import GestioneUtenti, RuoloUtente, verifica_totp
from pct.core_storage_backend import build_core_storage_backend
from web.services.storage_runtime import get_request_storage_runtime
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data


def register_auth_runtime(
    app: Flask,
    *,
    get_utenti: Callable[[], GestioneUtenti],
    bootstrap_runtime_data_modules: Callable[[], dict[str, str]],
) -> None:
    """Register auth middleware and core authentication routes."""
    tenant_runtime_state = app.extensions.setdefault("tenant_runtime_state", {})

    public_routes = {
        "login",
        "login_2fa",
        "static",
        "service_worker",
        "offline",
        "logout",
        "admin.esci_impersonazione",
        "polis_local_signer_download",
        "polis_local_ai_bridge_download",
        "polis_local_ai_lex_context_download",
        "polis_local_signer_visible_signature_download",
        "polis_local_signer_download_uffici",
        "polis_local_signer_installa",
        "polis_local_signer_setup_windows",
        "polis_local_signer_setup_windows_exe",
        "polis_local_signer_setup_macos",
        "polis_local_signer_setup_linux",
    }
    password_change_routes = {
        "profilo",
        "logout",
        "static",
    }

    def _tenant_user_manager(tenant_slug: str) -> GestioneUtenti:
        from pct.tenant import GestioneTenant

        tenants = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        studio = tenants.get(tenant_slug)
        paths = tenants.percorsi_dati(tenant_slug, reconcile_aliases=False)
        studio_db = None
        if studio:
            try:
                studio_db = build_core_storage_backend(
                    studio.database,
                    studio_db_path=paths["STUDIO_DB"],
                )
            except (OSError, sqlite3.Error):
                studio_db = None
        try:
            return GestioneUtenti(
                db_path=paths["AUTH_DB"],
                audit_path=paths["AUDIT_DB"],
                secret_key=app.secret_key,
                crea_admin_se_vuoto=False,
                studio_db=studio_db,
            )
        except (OSError, sqlite3.Error):
            app.logger.warning(
                "Auth runtime tenant %s: archivio SQL non disponibile, uso archivio locale utenti",
                tenant_slug,
            )
            return GestioneUtenti(
                db_path=paths["AUTH_DB"],
                audit_path=paths["AUDIT_DB"],
                secret_key=app.secret_key,
                crea_admin_se_vuoto=False,
                studio_db=None,
            )

    def _session_auth_scope() -> str:
        return str(session.get("auth_scope", "") or "").strip().lower()

    def _session_auth_tenant_slug() -> str:
        return str(session.get("auth_tenant_slug", "") or "").strip().lower()

    def _session_user_manager(uid: str | None = None):
        auth_scope = _session_auth_scope()
        auth_tenant_slug = _session_auth_tenant_slug()

        if auth_scope == "tenant" and auth_tenant_slug and app.config.get("MULTI_TENANT"):
            manager = _tenant_user_manager(auth_tenant_slug)
            user = manager.get(uid) if uid else None
            return manager, user, "tenant", auth_tenant_slug

        if auth_scope == "global" or not app.config.get("MULTI_TENANT"):
            manager = get_utenti()
            user = manager.get(uid) if uid else None
            return manager, user, "global", ""

        tenant_slug = str(session.get("tenant_slug", "") or "").strip().lower()
        if tenant_slug and app.config.get("MULTI_TENANT"):
            manager = _tenant_user_manager(tenant_slug)
            user = manager.get(uid) if uid else None
            if user:
                return manager, user, "tenant", tenant_slug

        manager = get_utenti()
        user = manager.get(uid) if uid else None
        if user:
            return manager, user, "global", ""

        if tenant_slug and app.config.get("MULTI_TENANT"):
            manager = _tenant_user_manager(tenant_slug)
            user = manager.get(uid) if uid else None
            return manager, user, "tenant", tenant_slug

        return manager, user, "global", ""

    def _active_tenants() -> list:
        from pct.tenant import GestioneTenant

        tenants = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        active_states = {"ATTIVO", "TRIAL"}
        return [
            studio
            for studio in tenants.lista()
            if str(getattr(studio, "stato", "") or "").upper() in active_states
        ]

    def _single_active_tenant_slug() -> str:
        active = _active_tenants()
        if len(active) == 1:
            return str(getattr(active[0], "slug", "") or "")
        return ""

    def _skip_tenant_runtime_bootstrap() -> bool:
        endpoint = str(request.endpoint or "").strip().lower()
        path = str(request.path or "").strip().lower()
        return endpoint == "static" or path.startswith("/static/")

    def _tenant_runtime_entry(tenant_slug: str) -> dict:
        slug = str(tenant_slug or "").strip().lower()
        return tenant_runtime_state.setdefault(
            slug,
            {
                "legacy_bootstrap_completed": False,
                "storage_reconciled": False,
                "module_bootstrap_completed": False,
            },
        )

    def _ensure_tenant_runtime_ready(tenants, tenant_slug: str) -> None:
        state = _tenant_runtime_entry(tenant_slug)

        if not state.get("legacy_bootstrap_completed"):
            try:
                bootstrap_report = bootstrap_legacy_tenant_runtime_data(
                    app,
                    tenant_slug=tenant_slug,
                )
                state["legacy_bootstrap_completed"] = True
                if bootstrap_report.get("copied") or bootstrap_report.get("sqlite_migrated"):
                    app.logger.info(
                        "Bootstrap dati legacy per tenant %s: copied=%s sqlite=%s",
                        tenant_slug,
                        ",".join(sorted(bootstrap_report.get("copied", {}).keys())) or "-",
                        bootstrap_report.get("sqlite_migrated", False),
                    )
            except Exception as exc:
                app.logger.exception(
                    "Errore bootstrap dati legacy per tenant %s: %s",
                    tenant_slug,
                    exc,
                )

        if not state.get("storage_reconciled"):
            try:
                tenants.reconcile_storage_aliases(tenant_slug)
                state["storage_reconciled"] = True
            except Exception as exc:
                app.logger.exception(
                    "Errore riconciliazione storage tenant %s: %s",
                    tenant_slug,
                    exc,
                )

        if not state.get("module_bootstrap_completed"):
            try:
                bootstrap_runtime_data_modules()
                state["module_bootstrap_completed"] = True
            except Exception as exc:
                app.logger.exception(
                    "Errore bootstrap moduli dati tenant %s: %s",
                    tenant_slug,
                    exc,
                )

    if app.config.get("MULTI_TENANT"):
        try:
            promoted = GestioneUtenti(
                db_path=app.config["AUTH_DB"],
                audit_path=app.config["AUDIT_DB"],
                secret_key=app.secret_key,
                crea_admin_se_vuoto=False,
            ).ensure_platform_superadmin()
            if promoted is not None:
                app.logger.info(
                    "Auth runtime multi-tenant: ruolo piattaforma allineato a SUPERADMIN per %s",
                    promoted.username,
                )
        except Exception as exc:
            app.logger.exception("Errore riallineamento SUPERADMIN di piattaforma: %s", exc)

    def _resolve_tenant_login(username: str, password: str):
        matches = []
        for studio in _active_tenants():
            slug = str(getattr(studio, "slug", "") or "").strip().lower()
            if not slug:
                continue
            manager = _tenant_user_manager(slug)
            utente = manager.autentica(username, password)
            if utente:
                matches.append((slug, manager, utente))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return "ambiguous"
        return None

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
        manager, user, auth_scope, auth_tenant_slug = _session_user_manager(uid)
        g.utente_corrente = user
        g.utente_auth_manager = manager
        g.utente_auth_scope = auth_scope
        g.utente_auth_tenant_slug = auth_tenant_slug
        return None

    @app.before_request
    def carica_tenant():
        """
        Inject g.tenant using tenant_slug in session.
        When multi-tenant is active, override per-request data paths in g.data_paths.
        """
        g.tenant = None
        g.data_paths = {}
        g.storage_runtime = None
        if not app.config.get("MULTI_TENANT"):
            return None
        if _skip_tenant_runtime_bootstrap():
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
            g.data_paths = tenants.percorsi_dati(tenant_slug, reconcile_aliases=False)
            g.storage_runtime = get_request_storage_runtime(g.data_paths["CLIENTI_DB"]).to_dict()
            _ensure_tenant_runtime_ready(tenants, tenant_slug)
        return None

    @app.before_request
    def blocca_superadmin_fuori_dalla_piattaforma():
        if not app.config.get("MULTI_TENANT"):
            return None
        utente = getattr(g, "utente_corrente", None)
        if not utente or not utente.is_superadmin:
            return None
        if session.get("superadmin_user_id"):
            return None

        blueprint = str(request.blueprint or "").strip().lower()
        endpoint = str(request.endpoint or "").strip()
        path = str(request.path or "").strip().lower()
        allowed_blueprints = {
            "admin",
            "installation_pack_admin",
            "legal_coverage_admin",
            "legal_updates_admin",
            "operational_resilience_admin",
            "legal_intelligence",
            "support_remote",
            "studio_site_admin",
            "studio_site_public",
        }
        allowed_endpoints = public_routes | password_change_routes | {
            "profilo",
            "service_worker",
            "offline",
        }
        allowed_path_prefixes = (
            "/admin/database",
        )

        if (
            blueprint in allowed_blueprints
            or endpoint in allowed_endpoints
            or any(path.startswith(prefix) for prefix in allowed_path_prefixes)
        ):
            return None
        return redirect(url_for("admin.dashboard"))

    @app.before_request
    def richiedi_login():
        if request.endpoint in public_routes:
            return None
        if any(
            str(request.path or "").startswith(prefix)
            for prefix in ("/support/join/", "/support/api/", "/support/ws/", "/web/")
        ):
            return None
        if request.endpoint and request.endpoint.startswith(("api_", "portale")):
            return None
        if g.utente_corrente is None:
            return redirect(url_for("login", next=request.path))
        if (
            not app.testing
            and getattr(g.utente_corrente, "must_change_password", False)
            and request.endpoint not in password_change_routes
        ):
            flash(
                "Per motivi di sicurezza devi impostare una nuova password prima di continuare.",
                "warning",
            )
            return redirect(url_for("profilo", password_obbligatoria=1))
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.utente_corrente:
            return redirect(url_for("dashboard"))

        errore = None
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            studio_slug = request.form.get("studio_slug", "").strip().lower()
            selected_tenant_slug = ""
            manager = None
            utente = None
            auth_scope = "global"
            auth_tenant_slug = ""

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
                utente = manager.autentica(username, password)
                selected_tenant_slug = studio_slug
                auth_scope = "tenant"
                auth_tenant_slug = studio_slug
            else:
                manager = get_utenti()
                utente = manager.autentica(username, password)
                if utente and app.config.get("MULTI_TENANT"):
                    selected_tenant_slug = str(getattr(utente, "tenant_slug", "") or "")
                    ruolo = str(getattr(utente, "ruolo", "") or "")
                    if not selected_tenant_slug and ruolo != str(RuoloUtente.SUPERADMIN):
                        selected_tenant_slug = _single_active_tenant_slug()
                if not utente and app.config.get("MULTI_TENANT"):
                    tenant_match = _resolve_tenant_login(username, password)
                    if tenant_match == "ambiguous":
                        errore = (
                            "Sono stati trovati più studi per queste credenziali. "
                            "Indica lo studio nel campo dedicato."
                        )
                    elif tenant_match:
                        selected_tenant_slug, manager, utente = tenant_match
                        auth_scope = "tenant"
                        auth_tenant_slug = selected_tenant_slug
            if utente:
                if utente.totp_attivato:
                    session.clear()
                    session["totp_pending_uid"] = utente.id
                    session["totp_pending_tenant_slug"] = (
                        selected_tenant_slug or utente.tenant_slug or ""
                    )
                    session["totp_pending_auth_scope"] = auth_scope
                    session["totp_pending_auth_tenant_slug"] = auth_tenant_slug or ""
                    session["totp_pending_next"] = request.args.get("next") or url_for(
                        "dashboard"
                    )
                    session["totp_pending_force_password_change"] = bool(
                        getattr(utente, "must_change_password", False)
                    )
                    return redirect(url_for("login_2fa"))

                session.clear()
                session["user_id"] = utente.id
                session["tenant_slug"] = selected_tenant_slug or utente.tenant_slug or ""
                session["auth_scope"] = auth_scope
                session["auth_tenant_slug"] = auth_tenant_slug or ""
                session["last_activity"] = datetime.now().isoformat()
                session["must_change_password"] = bool(
                    getattr(utente, "must_change_password", False)
                )
                session.permanent = True
                manager.registra_evento(
                    "auth.login",
                    id_utente=utente.id,
                    username=utente.username,
                    ip=request.remote_addr or "",
                )
                if session.get("must_change_password") and not app.testing:
                    flash(
                        "Password iniziale temporanea rilevata. Prima di usare il gestionale devi sostituirla.",
                        "warning",
                    )
                    return redirect(url_for("profilo", password_obbligatoria=1))
                next_url = request.args.get("next")
                if not next_url:
                    next_url = (
                        url_for("admin.dashboard")
                        if utente.is_superadmin and not session.get("superadmin_user_id")
                        else url_for("dashboard")
                    )
                return redirect(next_url)

            if not errore:
                errore = "Credenziali non valide o utente disabilitato."
            manager.registra_evento(
                "auth.login_fallito",
                username=username,
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
            auth_manager = getattr(g, "utente_auth_manager", None) or get_utenti()
            auth_manager.registra_evento(
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

        pending_tenant_slug = session.get("totp_pending_tenant_slug", "")
        pending_auth_scope = str(session.get("totp_pending_auth_scope", "") or "").strip().lower()
        pending_auth_tenant_slug = str(
            session.get("totp_pending_auth_tenant_slug", "") or ""
        ).strip().lower()
        if (
            pending_auth_scope == "tenant"
            and pending_auth_tenant_slug
            and app.config.get("MULTI_TENANT")
        ):
            manager = _tenant_user_manager(pending_auth_tenant_slug)
        elif pending_tenant_slug and app.config.get("MULTI_TENANT"):
            manager = _tenant_user_manager(pending_tenant_slug)
        else:
            manager = get_utenti()
        utente = manager.get(uid)
        if not utente or not utente.totp_attivato:
            session.pop("totp_pending_uid", None)
            session.pop("totp_pending_tenant_slug", None)
            session.pop("totp_pending_auth_scope", None)
            session.pop("totp_pending_auth_tenant_slug", None)
            return redirect(url_for("login"))

        errore = None
        if request.method == "POST":
            codice = request.form.get("codice", "").strip()
            if verifica_totp(utente.totp_secret, codice):
                next_url = session.pop("totp_pending_next", "")
                force_password_change = bool(
                    session.pop("totp_pending_force_password_change", False)
                )
                tenant_slug = session.pop("totp_pending_tenant_slug", "")
                auth_scope = str(session.pop("totp_pending_auth_scope", "") or "").strip().lower()
                auth_tenant_slug = str(
                    session.pop("totp_pending_auth_tenant_slug", "") or ""
                ).strip().lower()
                session.clear()
                session["user_id"] = utente.id
                session["tenant_slug"] = tenant_slug or utente.tenant_slug or ""
                session["auth_scope"] = auth_scope or (
                    "tenant" if auth_tenant_slug or utente.tenant_slug else "global"
                )
                session["auth_tenant_slug"] = (
                    auth_tenant_slug or (utente.tenant_slug if session["auth_scope"] == "tenant" else "")
                )
                session["last_activity"] = datetime.now().isoformat()
                session["must_change_password"] = force_password_change
                session.permanent = True
                if not next_url:
                    next_url = (
                        url_for("admin.dashboard")
                        if utente.is_superadmin and not session.get("superadmin_user_id")
                        else url_for("dashboard")
                    )
                manager.registra_evento(
                    "auth.login",
                    id_utente=utente.id,
                    username=utente.username,
                    ip=request.remote_addr or "",
                )
                if force_password_change and not app.testing:
                    flash(
                        "Password iniziale temporanea rilevata. Prima di usare il gestionale devi sostituirla.",
                        "warning",
                    )
                    return redirect(url_for("profilo", password_obbligatoria=1))
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
