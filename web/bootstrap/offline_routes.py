"""Opt-in device registration and offline notes API; existing session/RBAC apply."""

import os
from functools import wraps

from flask import g, jsonify, request, session

from pct.offline.notes import NoteSync
from web.services.tenant_paths import tenant_data_path


def register_offline_routes(app, *, get_fascicoli, get_utenti, audit):
    def context():
        enabled = app.config.get("OFFLINE_WORKSPACE_ENABLED", os.environ.get("IUSENTRA_OFFLINE_ENABLED") == "1")
        if not enabled:
            raise RuntimeError("Lavoro offline non attivato per questa installazione.")
        user = getattr(g, "utente_corrente", None)
        if not user or not getattr(user, "attivo", False):
            raise PermissionError("Accedi con una identità attiva dello studio.")
        if not user.ha_permesso("fascicoli.leggi"):
            raise PermissionError("Permesso di consultazione dei fascicoli richiesto.")
        tenant = str(getattr(getattr(g, "tenant", None), "slug", "") or "")
        if not tenant and not app.config.get("MULTI_TENANT"):
            tenant = "single-studio"
        if not tenant:
            raise PermissionError("Contesto dello studio richiesto.")
        from web.services.storage_runtime import get_request_studio_db

        db = get_request_studio_db(tenant_data_path("CLIENTI_DB", require_tenant=True))
        if db is None:
            raise RuntimeError("Il lavoro offline richiede il database SQL dello studio.")
        role = getattr(getattr(user, "ruolo", None), "value", "")
        admin = role == "AMMINISTRATORE" and user.ha_permesso("utenti.scrivi")
        return user, NoteSync(db, tenant, str(user.id)), admin

    def endpoint(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                if request.method == "POST":
                    # Explicit CSRF for all new endpoints, even without Origin.
                    from secrets import compare_digest

                    expected = session.get("_csrf_token", "")
                    if not expected or not compare_digest(expected, request.headers.get("X-CSRF-Token", "")):
                        raise PermissionError("Conferma di sicurezza richiesta: riapri IUSENTRA online.")
                    if request.content_length and request.content_length > 1500000:
                        raise ValueError("Richiesta troppo ampia.")
                return jsonify(function(*args, **kwargs))
            except PermissionError as exc:
                return jsonify(ok=False, code="access_denied", message=str(exc)), 403
            except (ValueError, TypeError) as exc:
                return jsonify(ok=False, code="invalid_request", message=str(exc)), 400
            except Exception:
                app.logger.exception("Operazione offline non confermata")
                return jsonify(
                    ok=False,
                    code="unavailable",
                    message="Lavoro offline non disponibile. Le bozze locali restano conservate.",
                ), 503

        return wrapped

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise TypeError("Richiesta non valida.")
        return value

    @app.after_request
    def offline_cache_policy(response):
        # HTTP caches must not retain authenticated APIs/documents/HTML.
        # Only static public assets and the anonymous offline fallback are cacheable.
        if (
            getattr(g, "utente_corrente", None)
            and request.endpoint not in {"static", "offline", "service_worker", "web_manifest", "favicon"}
        ) or request.path.startswith("/api/v1/offline/"):
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/api/v1/offline/context")
    @endpoint
    def offline_context():
        _user, registry, admin = context()
        from web.services.security_runtime import csrf_token_sessione

        return {
            "ok": True,
            "tenant": registry.tenant,
            "actor": registry.actor,
            "admin": admin,
            "csrf": csrf_token_sessione(),
            "devices": registry.list_devices(admin=admin),
        }

    @app.post("/api/v1/offline/devices")
    @endpoint
    def offline_register():
        _, registry, _ = context()
        data = body()
        return dict(ok=True, **registry.register(data.get("label"), data.get("public_key")))

    @app.post("/api/v1/offline/devices/<device_id>/challenge")
    @endpoint
    def offline_challenge(device_id):
        _, registry, _ = context()
        return dict(ok=True, **registry.challenge(device_id, body().get("purpose")))

    @app.post("/api/v1/offline/devices/<device_id>/prove")
    @endpoint
    def offline_prove(device_id):
        _, registry, _ = context()
        registry.prove(device_id, body().get("proof"))
        return {"ok": True}

    @app.post("/api/v1/offline/devices/<device_id>/<action>")
    @endpoint
    def offline_status(device_id, action):
        _, registry, admin = context()
        if not admin:
            # Owner may always revoke their own credential.
            if action != "revoke":
                raise PermissionError("Approvazione riservata all’amministratore dello studio.")
            with registry.transaction() as conn:
                registry.device(conn, device_id)
        registry.change_status(device_id, action, body().get("fingerprint", ""))
        audit("offline.device." + action, dettagli=device_id)
        return {"ok": True}

    @app.get("/api/v1/offline/audit")
    @endpoint
    def offline_audit():
        _, registry, admin = context()
        if not admin:
            raise PermissionError("Registro riservato all’amministratore dello studio.")
        return {"ok": True, "events": registry.events()}

    @app.post("/api/v1/offline/devices/<device_id>/sync")
    @endpoint
    def offline_sync(device_id):
        user, registry, _ = context()
        data = body()
        manager = get_fascicoli()

        def read(case_id):
            return bool(user.ha_permesso("fascicoli.leggi") and manager.get(case_id) is not None)

        def write(case_id):
            return bool(user.ha_permesso("fascicoli.scrivi") and read(case_id))

        ttl = max(300, min(86400, int(app.config.get("OFFLINE_LEASE_SECONDS", 86400))))
        result = registry.exchange(
            device_id, data.get("proof"), data.get("intent"), can_read=read, can_write=write, lease_seconds=ttl
        )
        result["can_write"] = bool(user.ha_permesso("fascicoli.scrivi"))
        with registry.transaction() as conn:
            rows = conn.execute("SELECT id,numero,oggetto FROM fascicoli ORDER BY numero DESC LIMIT 100").fetchall()
        result["cases"] = [
            {"id": row[0], "label": f"{row[1]} — {row[2] or 'Fascicolo'}"} for row in rows if read(row[0])
        ]
        return result
