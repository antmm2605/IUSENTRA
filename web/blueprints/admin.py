"""
Blueprint pannello amministrazione IUSENTRA — gestione multi-tenant studi legali.

Accesso: solo utenti con ruolo SUPERADMIN.
Prefix:  /admin/
"""

from __future__ import annotations

from datetime import datetime
from functools import wraps
from pathlib import Path
import sqlite3
from time import monotonic

from flask import (
    Blueprint,
    render_template,
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
    DatabaseConfig,
    DbMode,
    DB_MODE_INFO,
    SELECTABLE_DB_MODES,
    MODULI_DISPONIBILI,
    PIANI,
    PianoTenant,
    StatoTenant,
    normalize_db_mode,
)
from pct.auth import (
    GestioneUtenti,
    RuoloUtente,
    DESCRIZIONI_RUOLI,
)
from pct.core_storage_backend import build_core_storage_backend
from web.services.lex_eval_scorecard import build_lex_eval_scorecard
from web.services.migration_assistant import (
    build_migration_assistant,
    execute_migration_assistant,
)
from web.services.observability_runtime import build_observability_payload
from web.services.product_governance_surface import build_product_governance_surface
from web.services.security_redaction import redacted_json_response
from web.services.studio_installation_status import build_studio_installation_status
from web.services.system_health_surface import build_system_health_surface
from web.services.system_health_surface import build_system_health_api_payload
from web.blueprints.react_shell import render_react_shell_response

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
    tm = _tenant_manager()
    tm.verifica_scadenze()
    studi = tm.lista()
    stats = tm.statistiche()

    # Studi in scadenza nei prossimi 14 giorni
    in_scadenza = [
        s for s in studi
        if s.giorni_alla_scadenza is not None and 0 < s.giorni_alla_scadenza <= 14
    ]

    return render_template(
        "admin/dashboard.html",
        studi=studi,
        stats=stats,
        in_scadenza=in_scadenza,
        piani=PIANI,
    )


@admin_bp.route("/utenti-piattaforma")
@superadmin_required
def utenti_piattaforma():
    gu = _utenti_piattaforma()
    gu.ensure_platform_superadmin()
    utenti_globali = _utenti_globali_piattaforma(gu)
    superadmin_rows = [u for u in utenti_globali if u.ruolo == RuoloUtente.SUPERADMIN]
    superadmin_corrente = superadmin_rows[0] if len(superadmin_rows) == 1 else None
    anomalie = []
    if len(superadmin_rows) != 1:
        anomalie.append(
            "La piattaforma deve avere un solo SUPERADMIN attivo. Verifica gli utenti globali e riallinea il ruolo."
        )
    for utente in utenti_globali:
        if utente.ruolo != RuoloUtente.SUPERADMIN:
            anomalie.append(
                f"L'utente globale {utente.username} non e' SUPERADMIN: correggere il ruolo o spostarlo dentro uno studio."
            )
    return render_template(
        "admin/utenti_piattaforma.html",
        utenti=utenti_globali,
        superadmin_rows=superadmin_rows,
        superadmin_corrente=superadmin_corrente,
        anomalie=anomalie,
        studi=_studi_assegnabili(),
        ruoli_studio=[ruolo for ruolo in RuoloUtente if ruolo != RuoloUtente.SUPERADMIN],
        descrizioni_ruoli=DESCRIZIONI_RUOLI,
    )


@admin_bp.route("/utenti-piattaforma/genera-superadmin", methods=["POST"])
@superadmin_required
def genera_superadmin_piattaforma():
    gu = _utenti_piattaforma()
    current_superadmin = _superadmin_corrente_piattaforma(gu)
    current_superadmin_id = current_superadmin.id if current_superadmin else ""
    username = str(request.form.get("username", "") or "").strip().lower()
    password = str(request.form.get("password", "") or "").strip()
    email = str(request.form.get("email", "") or "").strip()
    nome_completo = str(request.form.get("nome_completo", "") or "").strip()
    ruolo_precedente_raw = str(
        request.form.get("ruolo_superadmin_precedente", RuoloUtente.AMMINISTRATORE.value) or ""
    ).strip().upper()

    try:
        ruolo_precedente = RuoloUtente(ruolo_precedente_raw)
        nuovo_superadmin = gu.genera_superadmin_piattaforma(
            username=username,
            password=password,
            email=email,
            nome_completo=nome_completo,
            must_change_password=True,
            ruolo_superadmin_precedente=ruolo_precedente,
        )
        gu.registra_evento(
            azione="piattaforma.superadmin.generato",
            id_utente=nuovo_superadmin.id,
            username=nuovo_superadmin.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=nuovo_superadmin.id,
            dettagli=(
                "Generato o riallineato account SUPERADMIN dalla piattaforma "
                f"con ruolo precedente assegnato a {ruolo_precedente.value}."
            ),
            ip=request.remote_addr or "",
            esito="OK",
        )
        _sync_tenant_user_directory()
    except Exception as exc:
        current_app.logger.exception("Errore generazione superadmin piattaforma: %s", exc)
        flash(f"Errore durante la generazione del SUPERADMIN: {exc}", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    if current_superadmin_id and nuovo_superadmin.id != current_superadmin_id:
        session.clear()
        flash(
            "Il ruolo SUPERADMIN e' stato trasferito al nuovo account piattaforma. "
            "Accedi di nuovo con le nuove credenziali per continuare.",
            "success",
        )
        return redirect(url_for("login"))

    flash(
        f"Account piattaforma '{nuovo_superadmin.username}' riallineato come SUPERADMIN.",
        "success",
    )
    return redirect(url_for("admin.utenti_piattaforma"))


@admin_bp.route("/utenti-piattaforma/<uid>/reset-password", methods=["POST"])
@superadmin_required
def reset_password_piattaforma(uid: str):
    gu = _utenti_piattaforma()
    nuova_password = request.form.get("nuova_password", "").strip()
    if not nuova_password:
        flash("La nuova password non puo' essere vuota.", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    utente = gu.get(uid)
    if not utente or str(getattr(utente, "tenant_slug", "") or "").strip():
        abort(404)

    gu.cambia_password(uid, nuova_password, must_change_password=True)
    flash(
        f"Password temporanea dell'account piattaforma '{utente.username}' aggiornata. Al prossimo accesso dovra cambiarla.",
        "success",
    )
    return redirect(url_for("admin.utenti_piattaforma"))


@admin_bp.route("/utenti-piattaforma/<uid>/modifica", methods=["POST"])
@superadmin_required
def modifica_utente_piattaforma(uid: str):
    gu = _utenti_piattaforma()
    utente = gu.get(uid)
    if not utente or str(getattr(utente, "tenant_slug", "") or "").strip():
        abort(404)

    nome_completo = str(request.form.get("nome_completo", "") or "").strip()
    email = str(request.form.get("email", "") or "").strip()
    attivo = bool(request.form.get("attivo"))

    if utente.ruolo == RuoloUtente.SUPERADMIN and not attivo:
        flash(
            "Il SUPERADMIN di piattaforma non puo' essere disattivato da qui. Trasferisci prima il ruolo a un altro account globale.",
            "danger",
        )
        return redirect(url_for("admin.utenti_piattaforma"))

    try:
        aggiornato = gu.aggiorna(
            uid,
            nome_completo=nome_completo,
            email=email,
            attivo=(True if utente.ruolo == RuoloUtente.SUPERADMIN else attivo),
        )
        gu.registra_evento(
            azione="piattaforma.utente.modificato",
            id_utente=aggiornato.id,
            username=aggiornato.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=aggiornato.id,
            dettagli="Account piattaforma aggiornato dal pannello superadmin.",
            ip=request.remote_addr or "",
            esito="OK",
        )
        _sync_tenant_user_directory()
        flash(
            f"Account piattaforma '{aggiornato.username}' aggiornato correttamente.",
            "success",
        )
    except Exception as exc:
        current_app.logger.exception("Errore modifica account piattaforma %s: %s", uid, exc)
        flash(f"Errore durante la modifica dell'account piattaforma: {exc}", "danger")
    return redirect(url_for("admin.utenti_piattaforma"))


@admin_bp.route("/utenti-piattaforma/<uid>/trasferisci-superadmin", methods=["POST"])
@superadmin_required
def trasferisci_superadmin_piattaforma(uid: str):
    gu = _utenti_piattaforma()
    destinazione = gu.get(uid)
    if not destinazione or str(getattr(destinazione, "tenant_slug", "") or "").strip():
        abort(404)

    sorgente = _superadmin_corrente_piattaforma(gu)
    if not sorgente:
        flash("Nessun SUPERADMIN globale attivo trovato in piattaforma.", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    ruolo_precedente_raw = str(
        request.form.get("ruolo_superadmin_precedente", RuoloUtente.AMMINISTRATORE.value) or ""
    ).strip().upper()
    try:
        ruolo_precedente = RuoloUtente(ruolo_precedente_raw)
        nuovo_superadmin = gu.trasferisci_superadmin_piattaforma(
            source_id=sorgente.id,
            target_id=destinazione.id,
            ruolo_sorgente=ruolo_precedente,
        )
        gu.registra_evento(
            azione="piattaforma.superadmin.trasferito",
            id_utente=nuovo_superadmin.id,
            username=nuovo_superadmin.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=nuovo_superadmin.id,
            dettagli=(
                f"Ruolo SUPERADMIN trasferito da {sorgente.username} a {nuovo_superadmin.username}. "
                f"Il ruolo precedente e' diventato {ruolo_precedente.value}."
            ),
            ip=request.remote_addr or "",
            esito="OK",
        )
        _sync_tenant_user_directory()
    except Exception as exc:
        current_app.logger.exception(
            "Errore trasferimento ruolo SUPERADMIN a %s: %s",
            uid,
            exc,
        )
        flash(f"Errore durante il trasferimento del ruolo SUPERADMIN: {exc}", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    if getattr(getattr(g, "utente_corrente", None), "id", "") == sorgente.id:
        session.clear()
        flash(
            "Il ruolo SUPERADMIN e' stato trasferito a un altro account piattaforma. "
            "Accedi di nuovo con il nuovo account SUPERADMIN per continuare.",
            "success",
        )
        return redirect(url_for("login"))

    flash(
        f"Il ruolo SUPERADMIN ora appartiene all'account piattaforma '{nuovo_superadmin.username}'.",
        "success",
    )
    return redirect(url_for("admin.utenti_piattaforma"))


@admin_bp.route("/utenti-piattaforma/<uid>/sposta-nello-studio", methods=["POST"])
@superadmin_required
def sposta_utente_piattaforma_nello_studio(uid: str):
    tenant_slug = str(request.form.get("tenant_slug", "") or "").strip().lower()
    ruolo_raw = str(request.form.get("ruolo", RuoloUtente.AVVOCATO.value) or "").strip().upper()

    if not tenant_slug:
        flash("Seleziona lo studio di destinazione.", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    try:
        ruolo_destinazione = RuoloUtente(ruolo_raw)
    except ValueError:
        flash("Ruolo di studio non valido.", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    if ruolo_destinazione == RuoloUtente.SUPERADMIN:
        flash("Il ruolo SUPERADMIN non puo' essere assegnato dentro uno studio.", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    tm = _tenant_manager()
    studio = tm.get(tenant_slug)
    if not studio:
        flash("Studio di destinazione non trovato.", "danger")
        return redirect(url_for("admin.utenti_piattaforma"))

    gu_piattaforma = _utenti_piattaforma()
    utente = gu_piattaforma.get(uid)
    if not utente or str(getattr(utente, "tenant_slug", "") or "").strip():
        abort(404)
    if utente.ruolo == RuoloUtente.SUPERADMIN:
        flash(
            "Non puoi spostare fuori dalla piattaforma l'unico SUPERADMIN. Trasferisci prima il ruolo a un altro account.",
            "danger",
        )
        return redirect(url_for("admin.utenti_piattaforma"))

    gu_tenant = _utenti_tenant(tenant_slug)
    if gu_tenant.get_by_username(utente.username):
        flash(
            f"Nello studio '{studio.nome}' esiste gia' un utente con username '{utente.username}'.",
            "danger",
        )
        return redirect(url_for("admin.utenti_piattaforma"))

    importato = None
    try:
        importato = gu_tenant.importa_utente_esistente(
            utente,
            ruolo=ruolo_destinazione,
            tenant_slug=tenant_slug,
            preserve_id=False,
        )
        gu_tenant.registra_evento(
            azione="tenant.utente.importato_da_piattaforma",
            id_utente=importato.id,
            username=importato.username,
            risorsa_tipo="utente",
            risorsa_id=importato.id,
            dettagli=(
                f"Utente importato dalla piattaforma nello studio {tenant_slug} "
                f"con ruolo {ruolo_destinazione.value}."
            ),
            ip=request.remote_addr or "",
            esito="OK",
        )
        gu_piattaforma.elimina(uid, force=True)
        gu_piattaforma.registra_evento(
            azione="piattaforma.utente.spostato_nello_studio",
            id_utente=uid,
            username=utente.username,
            risorsa_tipo="utente_piattaforma",
            risorsa_id=uid,
            dettagli=(
                f"Account globale spostato nello studio {tenant_slug} "
                f"come {ruolo_destinazione.value}."
            ),
            ip=request.remote_addr or "",
            esito="OK",
        )
        _sync_tenant_user_directory()
        flash(
            f"L'account piattaforma '{utente.username}' ora appartiene allo studio '{studio.nome}' come {ruolo_destinazione.value}.",
            "success",
        )
    except Exception as exc:
        current_app.logger.exception(
            "Errore spostamento utente piattaforma %s nello studio %s: %s",
            uid,
            tenant_slug,
            exc,
        )
        if importato is not None:
            try:
                gu_tenant.elimina(importato.id, force=True)
            except Exception as rollback_exc:
                current_app.logger.exception(
                    "Rollback import utente piattaforma %s fallito nello studio %s: %s",
                    uid,
                    tenant_slug,
                    rollback_exc,
                )
        flash(f"Errore durante lo spostamento nello studio: {exc}", "danger")
    return redirect(url_for("admin.utenti_piattaforma"))


@admin_bp.route("/osservabilita")
def osservabilita():
    utente = getattr(g, "utente_corrente", None)
    if not utente:
        return redirect(url_for("login", next=request.full_path.rstrip("?")))
    if request.args.get("_legacy") != "1":
        if not utente.ha_permesso("audit.leggi"):
            abort(403)
        return render_react_shell_response("admin/osservabilita")
    if not utente.is_superadmin:
        abort(403)
    payload = build_observability_payload(current_app._get_current_object())
    return render_template("admin/osservabilita.html", payload=payload)


@admin_bp.route("/governance")
@superadmin_required
def governance():
    payload = build_product_governance_surface(selected_slug=request.args.get("slug", ""))
    return render_template("admin/governance.html", payload=payload)


@admin_bp.route("/stato-installazione")
@superadmin_required
def stato_installazione():
    payload = build_studio_installation_status()
    return render_template("admin/stato_installazione.html", payload=payload)


@admin_bp.route("/assistente-migrazione")
@superadmin_required
def assistente_migrazione():
    payload = build_migration_assistant(
        selected_slug=request.args.get("slug", ""),
        execution_state=session.get("assistente_migrazione_last_execution"),
    )
    return render_template("admin/assistente_migrazione.html", payload=payload)


@admin_bp.route("/assistente-migrazione/esegui", methods=["POST"])
@superadmin_required
def assistente_migrazione_esegui():
    selected_slug = str(request.form.get("slug", "") or "").strip().lower()
    target = str(request.form.get("target", "") or "").strip().lower()
    try:
        report = execute_migration_assistant(selected_slug=selected_slug, target=target)
        session["assistente_migrazione_last_execution"] = {
            "slug": selected_slug,
            "target": target,
            "report_path": str(report.get("report_path") or "").strip(),
            "generated_at": str(
                report.get("generated_at") or datetime.now().replace(microsecond=0).isoformat()
            ),
        }
        if target == "postgresql":
            flash("Migrazione completa su PostgreSQL eseguita con report reale.", "success")
        else:
            flash("Migrazione completa su SQL locale eseguita con report reale.", "success")
        report_path = str(report.get("report_path") or "").strip()
        if report_path:
            flash(f"Report generato: {report_path}", "info")
    except Exception as exc:
        current_app.logger.exception("Errore assistente migrazione %s: %s", target, exc)
        session["assistente_migrazione_last_execution"] = {
            "slug": selected_slug,
            "target": target,
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "error_message": "Migrazione non completata.",
        }
        flash("Errore durante la migrazione completa.", "danger")
    return redirect(url_for("admin.assistente_migrazione", slug=selected_slug))


@admin_bp.route("/salute-sistema")
@superadmin_required
def salute_sistema():
    payload = build_system_health_surface()
    return render_template("admin/salute_sistema.html", payload=payload)


@admin_bp.route("/system-health")
@superadmin_required
def system_health():
    return redacted_json_response(build_system_health_api_payload())


@admin_bp.route("/lex-scorecard")
@superadmin_required
def lex_scorecard():
    payload = build_lex_eval_scorecard()
    return render_template("admin/lex_scorecard.html", payload=payload)


# ============================================================= CRUD Studi

@admin_bp.route("/studi")
@superadmin_required
def lista_studi():
    tm = _tenant_manager()
    tm.verifica_scadenze()
    filtro_stato = request.args.get("stato", "")
    filtro_piano = request.args.get("piano", "")
    q = request.args.get("q", "").lower().strip()

    studi = tm.lista()
    if filtro_stato:
        studi = [s for s in studi if s.stato == filtro_stato]
    if filtro_piano:
        studi = [s for s in studi if s.piano == filtro_piano]
    if q:
        studi = [s for s in studi if q in s.nome.lower() or q in s.slug or q in (s.piva or "")]

    return render_template(
        "admin/studi_lista.html",
        studi=studi,
        piani=PIANI,
        filtro_stato=filtro_stato,
        filtro_piano=filtro_piano,
        q=q,
    )


@admin_bp.route("/studi/nuovo", methods=["GET", "POST"])
@superadmin_required
def nuovo_studio():
    if request.method == "POST":
        nome         = request.form.get("nome", "").strip()
        slug         = request.form.get("slug", "").strip()
        piano        = request.form.get("piano", PianoTenant.TRIAL)
        piva         = request.form.get("piva", "").strip()
        cf           = request.form.get("cf", "").strip()
        indirizzo    = request.form.get("indirizzo", "").strip()
        telefono     = request.form.get("telefono", "").strip()
        email        = request.form.get("email", "").strip()
        pec          = request.form.get("pec", "").strip()
        avvocato_ref = request.form.get("avvocato_ref", "").strip()
        note_admin   = request.form.get("note_admin", "").strip()

        # Creazione admin dello studio
        admin_username = request.form.get("admin_username", "amministratore").strip()
        admin_password = request.form.get("admin_password", "").strip()
        admin_nome     = request.form.get("admin_nome", nome).strip()
        admin_email    = request.form.get("admin_email", email).strip()
        db_mode = normalize_db_mode(request.form.get("db_mode", DbMode.SQLITE))

        if not nome or not slug:
            flash("Nome e slug sono obbligatori.", "danger")
            return render_template("admin/studio_nuovo.html", piani=PIANI,
                                   db_mode_info=DB_MODE_INFO, db_mode_choices=_db_mode_choices(), form=request.form)

        if not admin_password:
            flash("Imposta una password per l'amministratore dello studio.", "danger")
            return render_template("admin/studio_nuovo.html", piani=PIANI,
                                   db_mode_info=DB_MODE_INFO, db_mode_choices=_db_mode_choices(), form=request.form)

        if db_mode not in _db_mode_choices():
            flash("Modalità storage non consentita per i nuovi studi.", "danger")
            return render_template("admin/studio_nuovo.html", piani=PIANI,
                                   db_mode_info=DB_MODE_INFO, db_mode_choices=_db_mode_choices(), form=request.form)

        tm = _tenant_manager()
        try:
            tm.crea(
                nome=nome,
                slug=slug,
                piano=piano,
                piva=piva,
                cf=cf,
                indirizzo=indirizzo,
                telefono=telefono,
                email=email,
                pec=pec,
                avvocato_ref=avvocato_ref,
                note_admin=note_admin,
            )
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("admin/studio_nuovo.html", piani=PIANI,
                                   db_mode_info=DB_MODE_INFO, db_mode_choices=_db_mode_choices(), form=request.form)

        # Salva la modalità DB scelta (per LOCAL basta il default, per gli altri serve config dettagliata)
        tm.aggiorna_db_config(slug, DatabaseConfig(mode=db_mode))

        # Crea utente amministratore dello studio
        percorsi = tm.percorsi_dati(slug)
        gu = GestioneUtenti(
            db_path=percorsi["AUTH_DB"],
            audit_path=percorsi["AUDIT_DB"],
            secret_key=current_app.secret_key,
            crea_admin_se_vuoto=False,
        )
        try:
            gu.crea(
                username=admin_username,
                password=admin_password,
                ruolo=RuoloUtente.AMMINISTRATORE,
                nome_completo=admin_nome,
                email=admin_email,
                tenant_slug=slug,
            )
        except Exception as e:
            current_app.logger.exception("Errore creazione amministratore studio: %s", e)
            flash("Studio creato, ma la creazione dell'amministratore non è riuscita.", "warning")
            return redirect(url_for("admin.dettaglio_studio", slug=slug))

        provisioning = tm.provision_storage_backend(
            slug,
            migrate_existing=db_mode == DbMode.SQLITE,
        )
        _sync_tenant_user_directory()

        flash(f"Studio '{nome}' creato con successo!", "success")
        if db_mode == DbMode.SQLITE:
            if provisioning.get("migrated"):
                flash("SQLite attivato e dati iniziali migrati in studio.db.", "info")
            elif provisioning.get("sqlite_ready"):
                flash("SQLite attivato: studio.db è pronto per questo tenant.", "info")
        if db_mode == DbMode.POSTGRESQL:
            flash("Configura ora i parametri di connessione PostgreSQL.", "info")
            return redirect(url_for("admin.database_studio", slug=slug))
        return redirect(url_for("admin.dettaglio_studio", slug=slug))

    return render_template("admin/studio_nuovo.html", piani=PIANI,
                           db_mode_info=DB_MODE_INFO, db_mode_choices=_db_mode_choices(), form={})


@admin_bp.route("/studi/<slug>")
@superadmin_required
def dettaglio_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)

    gu = _utenti_tenant(slug)
    utenti = gu.lista()
    # Conta solo utenti di questo tenant
    utenti_studio = [u for u in utenti if _utente_del_tenant(u, slug)]

    # Solo lettura: evita riconciliazioni di archivio durante il rendering.
    storage_paths = tm.percorsi_dati(slug, reconcile_aliases=False)
    data_dir = Path(storage_paths["STUDIO_DB"]).parent

    return render_template(
        "admin/studio_dettaglio.html",
        studio=studio,
        utenti=utenti_studio,
        moduli_disponibili=MODULI_DISPONIBILI,
        piani=PIANI,
        db_mode_info=DB_MODE_INFO,
        db_mode_choices=_db_mode_choices(studio.database.mode),
        storage_manifest=tm.storage_manifest(slug, reconcile_aliases=False),
        storage_paths=storage_paths,
        storage_root_path=str(data_dir),
        storage_mb=None,
    )


@admin_bp.route("/studi/<slug>/modifica", methods=["POST"])
@superadmin_required
def modifica_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)

    tm.aggiorna(
        slug,
        nome=request.form.get("nome", studio.nome).strip(),
        piva=request.form.get("piva", "").strip(),
        cf=request.form.get("cf", "").strip(),
        indirizzo=request.form.get("indirizzo", "").strip(),
        telefono=request.form.get("telefono", "").strip(),
        email=request.form.get("email", "").strip(),
        pec=request.form.get("pec", "").strip(),
        avvocato_ref=request.form.get("avvocato_ref", "").strip(),
        note_admin=request.form.get("note_admin", "").strip(),
    )
    flash("Dati studio aggiornati.", "success")
    return redirect(url_for("admin.dettaglio_studio", slug=slug))


@admin_bp.route("/studi/<slug>/moduli", methods=["POST"])
@superadmin_required
def aggiorna_moduli(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)

    moduli_selezionati = request.form.getlist("moduli")
    tm.aggiorna_moduli(slug, moduli_selezionati)
    flash(f"Moduli aggiornati: {len(moduli_selezionati)} attivi.", "success")
    return redirect(url_for("admin.dettaglio_studio", slug=slug))


@admin_bp.route("/studi/<slug>/piano", methods=["POST"])
@superadmin_required
def aggiorna_piano(slug: str):
    tm = _tenant_manager()
    piano = request.form.get("piano", PianoTenant.TRIAL)
    studio = tm.aggiorna_piano(slug, piano)
    if studio:
        flash(f"Piano aggiornato a {PIANI[piano]['nome']}.", "success")
    return redirect(url_for("admin.dettaglio_studio", slug=slug))


@admin_bp.route("/studi/<slug>/sospendi", methods=["POST"])
@superadmin_required
def sospendi_studio(slug: str):
    tm = _tenant_manager()
    tm.sospendi(slug)
    flash("Studio sospeso.", "warning")
    return redirect(url_for("admin.dettaglio_studio", slug=slug))


@admin_bp.route("/studi/<slug>/riattiva", methods=["POST"])
@superadmin_required
def riattiva_studio(slug: str):
    tm = _tenant_manager()
    tm.riattiva(slug)
    flash("Studio riattivato.", "success")
    return redirect(url_for("admin.dettaglio_studio", slug=slug))


@admin_bp.route("/studi/<slug>/rigenera-api-key", methods=["POST"])
@superadmin_required
def rigenera_api_key(slug: str):
    tm = _tenant_manager()
    nuova = tm.rigenera_api_key(slug)
    if nuova:
        flash(f"Nuova API key generata: {nuova}", "info")
    return redirect(url_for("admin.dettaglio_studio", slug=slug))


@admin_bp.route("/studi/<slug>/impersona", methods=["POST"])
@superadmin_required
def impersona_studio(slug: str):
    """
    Il SUPERADMIN entra come amministratore dello studio (impersonazione).
    Salva il proprio user_id originale in sessione per poter tornare indietro.
    """
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio or studio.stato == StatoTenant.SOSPESO:
        abort(404)

    gu = _utenti_tenant(slug)
    # Trova il primo admin dello studio
    admin_studio = next(
        (u for u in gu.lista() if u.ruolo == RuoloUtente.AMMINISTRATORE and _utente_del_tenant(u, slug)),
        None,
    )
    if not admin_studio:
        flash("Nessun utente AMMINISTRATORE trovato per questo studio.", "danger")
        return redirect(url_for("admin.dettaglio_studio", slug=slug))

    # Salva sessione superadmin originale
    session["superadmin_user_id"]     = session.get("user_id")
    session["superadmin_auth_db"]     = current_app.config.get("AUTH_DB")
    session["superadmin_tenant_slug"] = ""

    # Imposta contesto tenant
    session["user_id"]      = admin_studio.id
    session["tenant_slug"]  = slug
    session["auth_scope"]   = "tenant"
    session["auth_tenant_slug"] = slug
    session["_fresh"]       = True

    flash(f"Stai operando come studio '{studio.nome}'. Clicca 'Esci impersonazione' per tornare.", "warning")
    return redirect(url_for("dashboard"))


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
    gu = _utenti_tenant(slug)
    utenti = [u for u in gu.lista() if _utente_del_tenant(u, slug)]
    return render_template(
        "admin/studio_utenti.html",
        studio=studio,
        utenti=utenti,
        ruoli=RuoloUtente,
        descrizioni_ruoli=DESCRIZIONI_RUOLI,
    )


@admin_bp.route("/studi/<slug>/utenti/nuovo", methods=["POST"])
@superadmin_required
def crea_utente(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)

    gu = _utenti_tenant(slug)

    # Verifica limite utenti
    utenti_esistenti = [u for u in gu.lista() if _utente_del_tenant(u, slug)]
    limite = studio.limite_utenti
    if limite > 0 and len(utenti_esistenti) >= limite:
        flash(f"Limite utenti raggiunto ({limite}) per il piano {studio.piano}.", "danger")
        return redirect(url_for("admin.utenti_studio", slug=slug))

    username     = request.form.get("username", "").strip()
    password     = request.form.get("password", "").strip()
    nome_completo = request.form.get("nome_completo", "").strip()
    email        = request.form.get("email", "").strip()
    ruolo_str    = request.form.get("ruolo", "SEGRETERIA")

    if not username or not password:
        flash("Username e password sono obbligatori.", "danger")
        return redirect(url_for("admin.utenti_studio", slug=slug))

    try:
        ruolo = RuoloUtente(ruolo_str)
        if ruolo == RuoloUtente.SUPERADMIN:
            ruolo = RuoloUtente.AMMINISTRATORE  # Impedisci creazione superadmin da qui
    except ValueError:
        ruolo = RuoloUtente.SEGRETERIA

    try:
        gu.crea(
            username=username,
            password=password,
            ruolo=ruolo,
            nome_completo=nome_completo,
            email=email,
            tenant_slug=slug,
        )
        _sync_tenant_user_directory()
        flash(f"Utente '{username}' creato.", "success")
    except Exception as e:
        flash(f"Errore: {e}", "danger")

    return redirect(url_for("admin.utenti_studio", slug=slug))


@admin_bp.route("/studi/<slug>/utenti/<uid>/reset-password", methods=["POST"])
@superadmin_required
def reset_password_utente(slug: str, uid: str):
    gu = _utenti_tenant(slug)
    nuova_password = request.form.get("nuova_password", "").strip()
    if not nuova_password:
        flash("La nuova password non può essere vuota.", "danger")
        return redirect(url_for("admin.utenti_studio", slug=slug))

    u = gu.get(uid)
    if not u or not _utente_del_tenant(u, slug):
        abort(404)

    gu.cambia_password(uid, nuova_password, must_change_password=True)
    _sync_tenant_user_directory()
    flash(
        f"Password temporanea di '{u.username}' aggiornata. Al prossimo accesso dovra cambiarla.",
        "success",
    )
    return redirect(url_for("admin.utenti_studio", slug=slug))


@admin_bp.route("/studi/<slug>/utenti/<uid>/attiva-disattiva", methods=["POST"])
@superadmin_required
def toggle_utente(slug: str, uid: str):
    gu = _utenti_tenant(slug)
    u = gu.get(uid)
    if not u or not _utente_del_tenant(u, slug):
        abort(404)
    gu.aggiorna(uid, attivo=not u.attivo)
    _sync_tenant_user_directory()
    stato = "attivato" if not u.attivo else "disattivato"
    flash(f"Utente '{u.username}' {stato}.", "info")
    return redirect(url_for("admin.utenti_studio", slug=slug))


@admin_bp.route("/studi/<slug>/utenti/<uid>/elimina", methods=["POST"])
@superadmin_required
def elimina_utente(slug: str, uid: str):
    gu = _utenti_tenant(slug)
    u = gu.get(uid)
    if not u or not _utente_del_tenant(u, slug):
        abort(404)
    gu.elimina(uid)
    _sync_tenant_user_directory()
    flash(f"Utente '{u.username}' eliminato.", "warning")
    return redirect(url_for("admin.utenti_studio", slug=slug))


# ============================================================= Database config

@admin_bp.route("/studi/<slug>/database", methods=["GET", "POST"])
@superadmin_required
def database_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)

    def _to_int(value, default: int) -> int:
        try:
            return int(value or default)
        except (TypeError, ValueError):
            return default

    if request.method == "POST":
        action = str(request.form.get("storage_action", "save") or "save").strip().lower()
        mode = normalize_db_mode(request.form.get("db_mode", studio.database.mode))
        current_mode = studio.database.normalized_mode

        if mode not in _db_mode_choices(studio.database.mode):
            flash("Strategia storage non consentita per questo studio.", "danger")
            return redirect(url_for("admin.database_studio", slug=slug))

        if current_mode == DbMode.SQLITE and mode == DbMode.JSON:
            flash(
                "Il ritorno diretto da SQLite a JSON non e' consentito senza una migrazione esplicita dei dati.",
                "danger",
            )
            return redirect(url_for("admin.database_studio", slug=slug))

        cfg = DatabaseConfig(
            mode=mode,
            host=(
                request.form.get("host")
                or request.form.get("db_host")
                or studio.database.host
                or "localhost"
            ).strip(),
            porta=_to_int(
                request.form.get("porta")
                or request.form.get("db_porta")
                or studio.database.porta,
                0,
            ),
            db_name=(
                request.form.get("db_name")
                or request.form.get("database")
                or request.form.get("nome_database")
                or studio.database.db_name
                or ""
            ).strip(),
            utente=(
                request.form.get("db_utente")
                or request.form.get("utente")
                or request.form.get("username")
                or studio.database.utente
                or ""
            ).strip(),
            password=(
                request.form.get("db_password")
                or request.form.get("password")
                or studio.database.password
                or ""
            ).strip(),
            ssl=request.form.get("ssl") == "on",
            pool_size=_to_int(request.form.get("pool_size", 5), 5),
            pool_timeout=_to_int(request.form.get("pool_timeout", 30), 30),
            connessione_ok=studio.database.connessione_ok,
            ultimo_test=studio.database.ultimo_test,
            errore_connessione=studio.database.errore_connessione,
            core_runtime_enabled=(
                studio.database.core_runtime_enabled if mode == DbMode.POSTGRESQL else False
            ),
            last_migration_report=(
                studio.database.last_migration_report if mode == DbMode.POSTGRESQL else ""
            ),
            last_migration_at=(
                studio.database.last_migration_at if mode == DbMode.POSTGRESQL else ""
            ),
        )

        studio = tm.aggiorna_db_config(slug, cfg) or studio

        if mode == DbMode.SQLITE:
            provisioning = tm.provision_storage_backend(
                slug,
                migrate_existing=current_mode != DbMode.SQLITE,
            )
            flash("Configurazione storage salvata.", "success")
            if provisioning.get("migrated"):
                flash("Dati JSON migrati in studio.db.", "info")
            elif provisioning.get("sqlite_ready"):
                flash("SQLite pronto: studio.db disponibile per i moduli core compatibili.", "info")
            return redirect(url_for("admin.database_studio", slug=slug))

        if mode == DbMode.POSTGRESQL and action == "activate_postgres":
            provisioning = tm.provision_storage_backend(
                slug,
                migrate_existing=True,
                activate_external=True,
                secret_key=current_app.secret_key,
            )
            if provisioning.get("ok") and provisioning.get("activated"):
                flash(
                    "PostgreSQL attivato come backend R/W per utenti, clienti, fascicoli, agenda e scadenziario.",
                    "success",
                )
                report_path = str(provisioning.get("migration_report_path") or "").strip()
                if report_path:
                    flash(f"Report di consistenza generato: {report_path}", "info")
            else:
                flash(
                    provisioning.get("error")
                    or "Attivazione PostgreSQL non completata: verifica connessione e report di migrazione.",
                    "danger",
                )
            return redirect(url_for("admin.database_studio", slug=slug))

        flash(
            "Configurazione PostgreSQL salvata. Esegui il test connessione e poi l'attivazione esplicita del backend core.",
            "success",
        )
        return redirect(url_for("admin.database_studio", slug=slug))

    return render_template(
        "admin/studio_database.html",
        studio=studio,
        db=studio.database,
        db_mode_info=DB_MODE_INFO,
        db_mode_choices=_db_mode_choices(studio.database.mode),
        storage_manifest=tm.storage_manifest(slug, reconcile_aliases=False),
        storage_paths=tm.percorsi_dati(slug, reconcile_aliases=False),
        DbMode=DbMode,
    )


@admin_bp.route("/studi/<slug>/database/ripara-runtime", methods=["POST"])
@superadmin_required
def ripara_runtime_studio(slug: str):
    tm = _tenant_manager()
    studio = tm.get(slug)
    if not studio:
        abort(404)

    report = tm.repair_studio_runtime(slug, secret_key=current_app.secret_key)
    utente = getattr(g, "utente_corrente", None)
    try:
        _utenti_piattaforma().registra_evento(
            azione="studio.runtime.ripara",
            id_utente=str(getattr(utente, "id", "") or ""),
            username=str(getattr(utente, "username", "") or "superadmin"),
            risorsa_tipo="studio",
            risorsa_id=slug,
            dettagli=(
                f"Riparazione studio: utenti controllati {report.get('users_checked', 0)}, "
                f"utenti corretti {report.get('users_repaired', 0)}, "
                f"indice utenti {report.get('directory_entries', 0)} voci."
            ),
            ip=request.remote_addr or "",
            esito="OK" if report.get("ok") else "ERRORE",
        )
    except Exception as exc:  # noqa: BLE001 - audit piattaforma non deve impedire report superadmin
        current_app.logger.exception("Audit riparazione studio non registrato: %s", exc)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.accept_mimetypes:
        status = 200 if report.get("ok") else 500
        return redacted_json_response(report), status

    if report.get("ok"):
        flash(
            "Riparazione completata: accesso studio, indice utenti e storage sono stati riallineati.",
            "success",
        )
    else:
        flash(
            "Riparazione non completata: controlla gli avvisi e riprova dal pannello Superadmin.",
            "danger",
        )
        for errore in report.get("errors", [])[:3]:
            flash(str(errore), "warning")
    return redirect(url_for("admin.database_studio", slug=slug))


@admin_bp.route("/studi/<slug>/database/test", methods=["POST"])

@superadmin_required
def testa_connessione_db(slug: str):
    try:
        tm = _tenant_manager()
        risultato = tm.testa_connessione(slug)
        return redacted_json_response(risultato)
    except Exception:
        current_app.logger.exception("Errore test connessione DB")
        return jsonify({
            "ok": False,
            "errore": "Test connessione non completato.",
        }), 500

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
