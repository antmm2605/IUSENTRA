"""
Blueprint pannello amministrazione HACS — gestione multi-tenant studi legali.

Accesso: solo utenti con ruolo SUPERADMIN.
Prefix:  /admin/
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

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
    StudioLegale,
    DatabaseConfig,
    DbMode,
    DB_MODE_INFO,
    MODULI_DISPONIBILI,
    PIANI,
    PianoTenant,
    StatoTenant,
)
from pct.auth import (
    GestioneUtenti,
    RuoloUtente,
    DESCRIZIONI_RUOLI,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ============================================================= Helper

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
    percorsi = tm.percorsi_dati(slug)
    return GestioneUtenti(
        db_path=percorsi["AUTH_DB"],
        audit_path=percorsi["AUDIT_DB"],
        secret_key=current_app.secret_key,
        crea_admin_se_vuoto=False,  # Non auto-creare admin — lo fa il pannello
    )


# ============================================================= Decoratore

from functools import wraps


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
        admin_username = request.form.get("admin_username", "admin").strip()
        admin_password = request.form.get("admin_password", "").strip()
        admin_nome     = request.form.get("admin_nome", nome).strip()
        admin_email    = request.form.get("admin_email", email).strip()

        if not nome or not slug:
            flash("Nome e slug sono obbligatori.", "danger")
            return render_template("admin/studio_nuovo.html", piani=PIANI,
                                   db_mode_info=DB_MODE_INFO, form=request.form)

        if not admin_password:
            flash("Imposta una password per l'amministratore dello studio.", "danger")
            return render_template("admin/studio_nuovo.html", piani=PIANI,
                                   db_mode_info=DB_MODE_INFO, form=request.form)

        tm = _tenant_manager()
        try:
            studio = tm.crea(
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
                                   db_mode_info=DB_MODE_INFO, form=request.form)

        # Salva la modalità DB scelta (per LOCAL basta il default, per gli altri serve config dettagliata)
        db_mode = request.form.get("db_mode", DbMode.LOCAL)
        if db_mode != DbMode.LOCAL:
            cfg = DatabaseConfig(mode=db_mode)
            tm.aggiorna_db_config(slug, cfg)

        # Crea utente amministratore dello studio
        gu = _utenti_tenant(slug)
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
            flash(f"Studio creato ma errore nella creazione utente admin: {e}", "warning")
            return redirect(url_for("admin.dettaglio_studio", slug=slug))

        flash(f"Studio '{nome}' creato con successo!", "success")
        # Se scelto MySQL/PostgreSQL, rimanda direttamente alla config DB
        if db_mode != DbMode.LOCAL:
            flash("Configura ora i parametri di connessione al database.", "info")
            return redirect(url_for("admin.database_studio", slug=slug))
        return redirect(url_for("admin.dettaglio_studio", slug=slug))

    return render_template("admin/studio_nuovo.html", piani=PIANI,
                           db_mode_info=DB_MODE_INFO, form={})


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
    utenti_studio = [u for u in utenti if u.tenant_slug == slug]

    # Uso storage
    data_dir = tm.data_dir(slug)
    storage_mb = _calc_storage_mb(data_dir)

    return render_template(
        "admin/studio_dettaglio.html",
        studio=studio,
        utenti=utenti_studio,
        moduli_disponibili=MODULI_DISPONIBILI,
        piani=PIANI,
        db_mode_info=DB_MODE_INFO,
        storage_mb=storage_mb,
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
        (u for u in gu.lista() if u.ruolo == RuoloUtente.AMMINISTRATORE and u.tenant_slug == slug),
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
    percorsi = tm.percorsi_dati(slug)
    session["user_id"]      = admin_studio.id
    session["tenant_slug"]  = slug
    session["_fresh"]       = True

    flash(f"Stai operando come studio '{studio.nome}'. Clicca 'Esci impersonazione' per tornare.", "warning")
    return redirect(url_for("dashboard"))


@admin_bp.route("/esci-impersonazione", methods=["POST"])
def esci_impersonazione():
    """Torna al SUPERADMIN originale."""
    orig_user_id  = session.pop("superadmin_user_id", None)
    orig_auth_db  = session.pop("superadmin_auth_db", None)

    if not orig_user_id:
        return redirect(url_for("dashboard"))

    session["user_id"]     = orig_user_id
    session["tenant_slug"] = ""
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
    utenti = [u for u in gu.lista() if u.tenant_slug == slug]
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
    utenti_esistenti = [u for u in gu.lista() if u.tenant_slug == slug]
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
    if not u or u.tenant_slug != slug:
        abort(404)

    gu.cambia_password(uid, nuova_password)
    flash(f"Password di '{u.username}' aggiornata.", "success")
    return redirect(url_for("admin.utenti_studio", slug=slug))


@admin_bp.route("/studi/<slug>/utenti/<uid>/attiva-disattiva", methods=["POST"])
@superadmin_required
def toggle_utente(slug: str, uid: str):
    gu = _utenti_tenant(slug)
    u = gu.get(uid)
    if not u or u.tenant_slug != slug:
        abort(404)
    gu.aggiorna(uid, attivo=not u.attivo)
    stato = "attivato" if not u.attivo else "disattivato"
    flash(f"Utente '{u.username}' {stato}.", "info")
    return redirect(url_for("admin.utenti_studio", slug=slug))


@admin_bp.route("/studi/<slug>/utenti/<uid>/elimina", methods=["POST"])
@superadmin_required
def elimina_utente(slug: str, uid: str):
    gu = _utenti_tenant(slug)
    u = gu.get(uid)
    if not u or u.tenant_slug != slug:
        abort(404)
    gu.elimina(uid)
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

    if request.method == "POST":
        mode = request.form.get("db_mode", DbMode.LOCAL)

        cfg = DatabaseConfig(
            mode=mode,
            host=(
                request.form.get("host")
                or request.form.get("db_host")
                or studio.database.host
                or "localhost"
            ).strip(),
            porta=int(
                request.form.get("porta")
                or request.form.get("db_porta")
                or studio.database.porta
                or 0
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
            channel_binding=request.form.get("channel_binding") == "on",
            pool_size=int(request.form.get("pool_size", 5) or 5),
            pool_timeout=int(request.form.get("pool_timeout", 30) or 30),
            connessione_ok=studio.database.connessione_ok,
            ultimo_test=studio.database.ultimo_test,
            errore_connessione=studio.database.errore_connessione,
        )

        tm.aggiorna_db_config(slug, cfg)
        flash("Configurazione database salvata.", "success")
        return redirect(url_for("admin.database_studio", slug=slug))

    return render_template(
        "admin/studio_database.html",
        studio=studio,
        db=studio.database,
        db_mode_info=DB_MODE_INFO,
        DbMode=DbMode,
    )


@admin_bp.route("/studi/<slug>/database/test", methods=["POST"])
@superadmin_required
def testa_connessione_db(slug: str):
    try:
        tm = _tenant_manager()
        risultato = tm.testa_connessione(slug)
        return jsonify(risultato)
    except Exception as e:
        current_app.logger.exception("Errore test connessione DB")
        return jsonify({
            "ok": False,
            "errore": str(e),
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
    data_dir = tm.data_dir(slug)
    mb = _calc_storage_mb(data_dir)
    return jsonify({"slug": slug, "storage_mb": mb, "limite_mb": studio.limite_storage_mb})


# ============================================================= Utility

def _calc_storage_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)
