"""
Blueprint pannello amministrazione IUSENTRA — gestione multi-tenant studi legali.

Accesso: solo utenti con ruolo SUPERADMIN.
Prefix:  /admin/
"""

from __future__ import annotations

from functools import wraps
from pathlib import Path
import sqlite3
from time import monotonic

from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    g,
    current_app,
    abort,
)

from pct.tenant import (
    GestioneTenant,
    PIANI,  # noqa: F401 - riesportato per il pannello React (react_piattaforma_pagine_governo)
    DbMode,
    SELECTABLE_DB_MODES,
    StatoTenant,
    normalize_db_mode,
)
from pct.auth import (
    GestioneUtenti,
    RuoloUtente,
)
from pct.core_storage_backend import build_core_storage_backend
from web.services.product_governance_surface import build_product_governance_surface
from web.services.security_redaction import redacted_json_response
from web.services.system_health_surface import build_system_health_api_payload
from web.services.piattaforma_shell_runtime import render_piattaforma_shell

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _tenant_manager() -> GestioneTenant:
    registry = current_app.config.get("TENANTS_REGISTRY", "./data/tenants.json")
    return GestioneTenant(registry_path=registry)


def _richiedi_superadmin():
    u = getattr(g, "utente_corrente", None)
    if not u or not u.is_superadmin:
        abort(403)


def _utenti_tenant(slug: str) -> GestioneUtenti:
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)
    percorsi = tm.percorsi_dati(slug, reconcile_aliases=False)
    studio_db = None
    try:
        studio_db = build_core_storage_backend(
            studio.database,
            studio_db_path=percorsi["STUDIO_DB"],
        )
    except (OSError, sqlite3.Error):
        studio_db = None
    try:
        return GestioneUtenti(
            db_path=percorsi["AUTH_DB"],
            audit_path=percorsi["AUDIT_DB"],
            secret_key=current_app.secret_key,
            crea_admin_se_vuoto=False,  # Non auto-creare admin — lo fa il pannello
            studio_db=studio_db,
            tenant_slug_context=slug,
        )
    except (OSError, sqlite3.Error):
        current_app.logger.warning(
            "Admin studio %s: archivio SQL non disponibile, uso archivio locale utenti",
            slug,
        )
        return GestioneUtenti(
            db_path=percorsi["AUTH_DB"],
            audit_path=percorsi["AUDIT_DB"],
            secret_key=current_app.secret_key,
            crea_admin_se_vuoto=False,
            studio_db=None,
            tenant_slug_context=slug,
        )


def _utenti_piattaforma() -> GestioneUtenti:
    return GestioneUtenti(
        db_path=current_app.config["AUTH_DB"],
        audit_path=current_app.config["AUDIT_DB"],
        secret_key=current_app.secret_key,
        crea_admin_se_vuoto=False,
        studio_db=None,
    )


def _sync_tenant_user_directory() -> None:
    try:
        _tenant_manager().sync_user_directory(secret_key=current_app.secret_key)
    except Exception as exc:
        current_app.logger.exception("Errore sincronizzazione tenant_user_directory: %s", exc)


def _superadmin_corrente_piattaforma(gu: GestioneUtenti):
    return next(
        (
            utente for utente in _utenti_globali_piattaforma(gu)
            if utente.ruolo == RuoloUtente.SUPERADMIN and utente.attivo
        ),
        None,
    )


def _utente_del_tenant(utente, slug: str) -> bool:
    tenant_slug = str(getattr(utente, "tenant_slug", "") or "").strip().lower()
    return bool(tenant_slug) and tenant_slug == slug


def _db_mode_choices(current_mode: str = "") -> list[str]:
    choices = list(SELECTABLE_DB_MODES)
    normalized = normalize_db_mode(current_mode)
    if normalized == DbMode.MYSQL and normalized not in choices:
        choices.append(normalized)
    return choices


def _studi_assegnabili() -> list:
    tm = _tenant_manager()
    return [
        studio
        for studio in tm.lista()
        if str(getattr(studio, "stato", "") or "").upper() != str(StatoTenant.SOSPESO)
    ]


def _utenti_globali_piattaforma(gu: GestioneUtenti) -> list:
    return [
        u
        for u in gu.lista()
        if not str(getattr(u, "tenant_slug", "") or "").strip()
    ]


# ============================================================= Decoratore


def superadmin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        _richiedi_superadmin()
        return fn(*args, **kwargs)
    return wrapper


# ============================================================= Dashboard

@admin_bp.route("/")
@superadmin_required
def dashboard():
    return render_piattaforma_shell("cruscotto", "Panoramica")


@admin_bp.route("/utenti-piattaforma")
@superadmin_required
def utenti_piattaforma():
    return render_piattaforma_shell("utenti-piattaforma", "Utenti di piattaforma")


@admin_bp.route("/osservabilita")
def osservabilita():
    utente = getattr(g, "utente_corrente", None)
    if not utente:
        return redirect(url_for("login", next=request.full_path.rstrip("?")))
    # Lo studio e la piattaforma usano registri con ambiti di accesso distinti.
    if utente.is_superadmin:
        return render_piattaforma_shell("osservabilita", "Osservabilità")
    if not utente.ha_permesso("audit.leggi"):
        abort(403)
    return redirect(url_for("audit_log"))


@admin_bp.route("/governance")
@superadmin_required
def governance():
    return render_piattaforma_shell("governance", "Governance del prodotto")


@admin_bp.route("/stato-installazione")
@superadmin_required
def stato_installazione():
    return render_piattaforma_shell("stato-installazione", "Stato installazione")


@admin_bp.route("/assistente-migrazione")
@superadmin_required
def assistente_migrazione():
    return render_piattaforma_shell("assistente-migrazione", "Assistente migrazione")


@admin_bp.route("/salute-sistema")
@superadmin_required
def salute_sistema():
    return render_piattaforma_shell("salute-sistema", "Salute del sistema")


@admin_bp.route("/system-health")
@superadmin_required
def system_health():
    return redacted_json_response(build_system_health_api_payload())


@admin_bp.route("/lex-scorecard")
@superadmin_required
def lex_scorecard():
    return render_piattaforma_shell("lex-scorecard", "Valutazione di Lex")


# ============================================================= CRUD Studi

@admin_bp.route("/studi")
@superadmin_required
def lista_studi():
    return render_piattaforma_shell("studi", "Studi legali")


@admin_bp.route("/studi/nuovo")
@superadmin_required
def nuovo_studio():
    return render_piattaforma_shell("studio-nuovo", "Nuovo studio")


@admin_bp.route("/studi/<slug>")
@superadmin_required
def dettaglio_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)
    return render_piattaforma_shell("studio", studio.nome, {"slug": slug})


@admin_bp.route("/esci-impersonazione", methods=["POST"])
def esci_impersonazione():
    """Torna al SUPERADMIN originale."""
    orig_user_id  = session.pop("superadmin_user_id", None)
    session.pop("superadmin_auth_db", None)

    if not orig_user_id:
        return redirect(url_for("dashboard"))

    session["user_id"]     = orig_user_id
    session["tenant_slug"] = ""
    session["auth_scope"] = "global"
    session["auth_tenant_slug"] = ""
    session.pop("tenant_slug", None)

    flash("Sei tornato al pannello SUPERADMIN.", "info")
    return redirect(url_for("admin.dashboard"))


# ============================================================= Utenti studio

@admin_bp.route("/studi/<slug>/utenti")
@superadmin_required
def utenti_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)
    return render_piattaforma_shell("studio-utenti", f"Utenti di {studio.nome}", {"slug": slug})


# ============================================================= Database config

@admin_bp.route("/studi/<slug>/database")
@superadmin_required
def database_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)
    return render_piattaforma_shell("studio-database", f"Archivio di {studio.nome}", {"slug": slug})


# ============================================================= API JSON

@admin_bp.route("/api/statistiche")
@superadmin_required
def api_statistiche():
    tm = _tenant_manager()
    return jsonify(tm.statistiche())


@admin_bp.route("/api/studi/<slug>/storage")
@superadmin_required
def api_storage_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        return jsonify({"errore": "Studio non trovato"}), 404
    storage_paths = tm.percorsi_dati(slug, reconcile_aliases=False)
    data_dir = Path(storage_paths["STUDIO_DB"]).parent
    mb, complete = _calc_storage_mb_budget(data_dir)
    return jsonify(
        {
            "slug": slug,
            "storage_mb": mb,
            "limite_mb": studio.limite_storage_mb,
            "complete": complete,
        }
    )


@admin_bp.route("/api/governance")
@superadmin_required
def api_governance():
    return redacted_json_response(build_product_governance_surface(selected_slug=request.args.get("slug", "")))


# ============================================================= Utility

def _calc_storage_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)


def _calc_storage_mb_budget(path: Path, *, max_seconds: float = 2.0) -> tuple[float, bool]:
    if not path.exists():
        return 0.0, True

    deadline = monotonic() + max_seconds
    total = 0
    complete = True
    for item in path.rglob("*"):
        if monotonic() > deadline:
            complete = False
            break
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return round(total / (1024 * 1024), 2), complete
