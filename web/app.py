"""
Flask web application — Studio Legale PCT.

Avvio:
    python -m web
    oppure: flask --app web.app run --debug
"""

import csv
import io
import os
import json
import zipfile as _zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    Response,
)

from pct.agenda import (
    Agenda,
    TipoAppuntamento,
    StatoAppuntamento,
)
from pct.reginde import ClientReGINde
from pct.clienti import (
    GestioneClienti,
    Cliente,
    TipoCliente,
    StatoCliente,
    TipoDocumento as TipoDocumentoCliente,
    Indirizzo,
    Recapiti,
    DocumentoIdentita,
    RiferimentoProcedimento,
)
from pct.fascicoli import (
    GestioneFascicoli,
    Fascicolo,
    TipoFascicolo,
    StatoFascicolo,
    TipoDocumento,
    TipoAttivita,
    EsitoAttivita,
    AttivitaProcessuale,
    Documento,
    DocumentoVersione,
)
from pct.messaggi import (
    GestioneMessaggi,
    CanaleMsggio,
    StatoMessaggio,
    TipoAutomazione,
    ConfigEmail,
    ConfigTwilio,
    ConfigMessaggistica,
)
from pct.backup import (
    GestioneBackup,
    TipoBackup,
    StatoBackup,
    FrequenzaBackup,
    ConfigBackup,
)
from pct.auth import (
    GestioneUtenti,
    Utente,
    RuoloUtente,
    PERMESSI,
    TUTTI_PERMESSI,
    DESCRIZIONI_RUOLI,
    genera_totp_secret,
    verifica_totp,
    totp_uri,
)
from pct.privacy import GestioneTrattamenti, TrattamentoDati
from pct.scadenziario import (
    GestioneScadenziario,
    Scadenza,
    TipoTermine,
    PrioritaTermine,
    StatoTermine,
    PRESET_TERMINI,
    calcola_termine,
    festività_italiane,
    è_giorno_lavorativo,
)
from pct.search_index import IndiceRicerca
from pct.reports import fascicolo_pdf, scadenze_pdf
from pct.database import GestioneDatabase
from pct.sync import GestoreSincronizzazione, get_gestore
from pct.condivisione import GestioneCondivisioni, RuoloCondivisione

# ------------------------------------------------------------------ cifratura documenti (AES-256-GCM)

_ENC_MAGIC = b"PCTENC\x01"


def _doc_key() -> bytes | None:
    """Restituisce la chiave AES-256 da env var PCT_DOC_KEY, o None se non configurata."""
    raw = os.getenv("PCT_DOC_KEY", "")
    if not raw:
        return None
    import hashlib as _hl
    return _hl.sha256(raw.encode()).digest()


def _encrypt_doc(data: bytes) -> bytes:
    """Cifra i byte del documento con AES-256-GCM. No-op se PCT_DOC_KEY non impostata."""
    key = _doc_key()
    if not key:
        return data
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, data, None)
    return _ENC_MAGIC + nonce + ct


def _decrypt_doc(data: bytes) -> bytes:
    """Decifra i byte del documento. No-op se il file non è cifrato (magic header assente)."""
    if not data.startswith(_ENC_MAGIC):
        return data
    key = _doc_key()
    if not key:
        raise ValueError("Documento cifrato ma PCT_DOC_KEY non configurata nel server.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    payload = data[len(_ENC_MAGIC):]
    nonce, ct = payload[:12], payload[12:]
    return AESGCM(key).decrypt(nonce, ct, None)


# ------------------------------------------------------------------ factory

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("PCT_SECRET_KEY", "dev-secret-pct-2024")

    # Sicurezza sessioni
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("PCT_HTTPS", "").lower() in ("1", "true", "yes")

    cfg = config or {}
    app.config["AGENDA_DB"] = cfg.get(
        "AGENDA_DB", os.getenv("PCT_AGENDA_DB", "./agenda/appuntamenti.json")
    )
    app.config["CLIENTI_DB"] = cfg.get(
        "CLIENTI_DB", os.getenv("PCT_CLIENTI_DB", "./clienti/anagrafica.json")
    )
    app.config["CONDIVISIONI_DB"] = cfg.get(
        "CONDIVISIONI_DB", os.getenv("PCT_CONDIVISIONI_DB", "./clienti/condivisioni.json")
    )
    app.config["FASCICOLI_DB"] = cfg.get(
        "FASCICOLI_DB", os.getenv("PCT_FASCICOLI_DB", "./fascicoli/fascicoli.json")
    )
    app.config["FASCICOLI_DOCS"] = cfg.get(
        "FASCICOLI_DOCS", os.getenv("PCT_FASCICOLI_DOCS", "./fascicoli/documenti")
    )
    app.config["FASCICOLI_ARCH"] = cfg.get(
        "FASCICOLI_ARCH", os.getenv("PCT_FASCICOLI_ARCH", "./fascicoli/archivio")
    )
    app.config["MESSAGGI_DB"] = cfg.get(
        "MESSAGGI_DB", os.getenv("PCT_MESSAGGI_DB", "./messaggi/storico.json")
    )
    app.config["BACKUP_DIR"] = cfg.get(
        "BACKUP_DIR", os.getenv("PCT_BACKUP_DIR", "./backup")
    )
    app.config["AUTH_DB"] = cfg.get(
        "AUTH_DB", os.getenv("PCT_AUTH_DB", "./auth/utenti.json")
    )
    app.config["AUDIT_DB"] = cfg.get(
        "AUDIT_DB", os.getenv("PCT_AUDIT_DB", "./auth/audit.json")
    )
    app.config["SCADENZIARIO_DB"] = cfg.get(
        "SCADENZIARIO_DB", os.getenv("PCT_SCADENZIARIO_DB", "./scadenziario/scadenze.json")
    )
    app.config["SEARCH_INDEX"] = cfg.get(
        "SEARCH_INDEX", os.getenv("PCT_SEARCH_INDEX", "./search/index.db")
    )
    app.config["PRIVACY_DB"] = cfg.get(
        "PRIVACY_DB", os.getenv("PCT_PRIVACY_DB", "./privacy/registro.json")
    )

    def get_agenda() -> Agenda:
        return Agenda(db_path=app.config["AGENDA_DB"])

    def get_clienti() -> GestioneClienti:
        return GestioneClienti(db_path=app.config["CLIENTI_DB"])

    def get_fascicoli() -> GestioneFascicoli:
        return GestioneFascicoli(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )

    def get_messaggi() -> GestioneMessaggi:
        cfg = ConfigMessaggistica(
            email=ConfigEmail(
                smtp_host=os.getenv("PCT_SMTP_HOST", ""),
                smtp_port=int(os.getenv("PCT_SMTP_PORT", "587")),
                username=os.getenv("PCT_SMTP_USER", ""),
                password=os.getenv("PCT_SMTP_PASS", ""),
                mittente_email=os.getenv("PCT_SMTP_FROM", ""),
                mittente_nome=os.getenv("PCT_STUDIO_NOME", "Studio Legale"),
            ),
            twilio=ConfigTwilio(
                account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
                auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
                numero_sms=os.getenv("TWILIO_SMS_NUMBER", ""),
                numero_whatsapp=os.getenv("TWILIO_WA_NUMBER", ""),
            ),
            studio_nome=os.getenv("PCT_STUDIO_NOME", "Studio Legale"),
        )
        return GestioneMessaggi(config=cfg, db_path=app.config["MESSAGGI_DB"])

    def get_backup() -> GestioneBackup:
        data_paths = {
            "agenda": app.config["AGENDA_DB"],
            "clienti": app.config["CLIENTI_DB"],
            "fascicoli": app.config["FASCICOLI_DB"],
            "messaggi": app.config["MESSAGGI_DB"],
            "documenti": app.config["FASCICOLI_DOCS"],
        }
        return GestioneBackup(
            directory_backup=app.config["BACKUP_DIR"],
            percorsi_dati=data_paths,
        )

    def get_utenti() -> GestioneUtenti:
        return GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
        )

    def get_scadenziario() -> GestioneScadenziario:
        return GestioneScadenziario(db_path=app.config["SCADENZIARIO_DB"])

    def get_indice() -> IndiceRicerca:
        return IndiceRicerca(index_path=app.config["SEARCH_INDEX"])

    def get_trattamenti() -> GestioneTrattamenti:
        return GestioneTrattamenti(db_path=app.config["PRIVACY_DB"])

    def get_condivisioni() -> GestioneCondivisioni:
        return GestioneCondivisioni(
            db_path=app.config["CONDIVISIONI_DB"],
            secret_key=app.config["SECRET_KEY"],
        )

    def cliente_accessibile(id_cliente: str, richiesto: RuoloCondivisione = RuoloCondivisione.LETTURA) -> bool:
        """
        Verifica se l'utente corrente può accedere alla cartella di un cliente.
        - Utenti con permesso globale 'clienti.leggi' → sempre True
        - Altri → solo se la cartella è stata condivisa con loro al livello richiesto
        """
        u = g.utente_corrente
        if not u:
            return False
        if u.ha_permesso("clienti.leggi"):
            return True
        return get_condivisioni().ha_accesso(u.id, id_cliente, richiesto)

    def get_database() -> GestioneDatabase:
        return GestioneDatabase({
            "clienti": app.config["CLIENTI_DB"],
            "fascicoli": app.config["FASCICOLI_DB"],
            "appuntamenti": app.config["AGENDA_DB"],
            "scadenze": app.config["SCADENZIARIO_DB"],
            "messaggi": app.config["MESSAGGI_DB"],
            "utenti": app.config["AUTH_DB"],
            "audit": app.config["AUDIT_DB"],
            "search_index": app.config["SEARCH_INDEX"],
        })

    # Singleton di sincronizzazione (uno per processo Flask)
    _sync = get_gestore()

    # ---------------------------------------------------------------- auth middleware

    from flask import session, g, abort

    @app.before_request
    def carica_utente_corrente():
        """Inietta g.utente_corrente ad ogni request; verifica inattività (8h)."""
        g.utente_corrente = None
        uid = session.get("user_id")
        if uid:
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
            gu = get_utenti()
            g.utente_corrente = gu.get(uid)

    # Route pubbliche che non richiedono login
    _ROUTE_PUBBLICHE = {"login", "login_2fa", "static", "logout"}

    @app.before_request
    def richiedi_login():
        if request.endpoint in _ROUTE_PUBBLICHE:
            return
        if request.endpoint and request.endpoint.startswith("api_"):
            return  # API gestiscono autonomamente
        if g.utente_corrente is None:
            return redirect(url_for("login", next=request.path))

    def audit(azione: str, risorsa_tipo: str = "", risorsa_id: str = "", dettagli: str = ""):
        """Helper per registrare un evento audit."""
        u = g.utente_corrente
        get_utenti().registra_evento(
            azione=azione,
            id_utente=u.id if u else "",
            username=u.username if u else "anonimo",
            risorsa_tipo=risorsa_tipo,
            risorsa_id=risorsa_id,
            dettagli=dettagli,
            ip=request.remote_addr or "",
        )

    def track_recente(tipo: str, id_: str, titolo: str, url_: str, icona: str = "bi-file"):
        """Aggiorna la cronologia Recenti nella sessione utente (ultimi 5 elementi)."""
        recenti = session.get("recenti", [])
        recenti = [r for r in recenti if not (r["tipo"] == tipo and r["id"] == id_)]
        recenti.insert(0, {"tipo": tipo, "id": id_, "titolo": titolo[:48], "url": url_, "icona": icona})
        session["recenti"] = recenti[:5]

    def sync_pubblica(tipo: str, modulo: str, id_risorsa: str = ""):
        """Pubblica un evento di sincronizzazione a tutti gli operatori connessi."""
        u = g.utente_corrente
        _sync.pubblica(
            tipo=tipo,
            modulo=modulo,
            id_risorsa=id_risorsa,
            utente=u.username if u else "sistema",
        )

    # ---------------------------------------------------------------- context

    @app.template_filter("fmt_data")
    def fmt_data(val: str) -> str:
        if not val:
            return "—"
        try:
            from datetime import date
            d = date.fromisoformat(val[:10])
            return d.strftime("%d/%m/%Y")
        except ValueError:
            return val

    @app.context_processor
    def inject_globals():
        return {
            "oggi": date.today(),
            "ora_adesso": datetime.now().strftime("%H:%M"),
            "TipoAppuntamento": TipoAppuntamento,
            "StatoAppuntamento": StatoAppuntamento,
            "TipoCliente": TipoCliente,
            "StatoCliente": StatoCliente,
            "TipoFascicolo": TipoFascicolo,
            "StatoFascicolo": StatoFascicolo,
            "TipoAttivita": TipoAttivita,
            "EsitoAttivita": EsitoAttivita,
            "utente_corrente": g.get("utente_corrente"),
            "RuoloUtente": RuoloUtente,
            "DESCRIZIONI_RUOLI": DESCRIZIONI_RUOLI,
            "n_operatori_connessi": _sync.n_connessi,
            "RuoloCondivisione": RuoloCondivisione,
            "recenti": session.get("recenti", []),
        }

    # ================================================================ PWA

    @app.route("/sw.js")
    def service_worker():
        """Service Worker servito dalla root per scope '/'."""
        return send_file(
            app.root_path + "/static/sw.js",
            mimetype="application/javascript",
        )

    @app.route("/offline")
    def offline():
        """Pagina fallback mostrata dal service worker quando si è offline."""
        return render_template("offline.html")

    # ================================================================ ERRORI

    @app.errorhandler(403)
    def errore_403(e):
        return render_template("errori/403.html"), 403

    @app.errorhandler(404)
    def errore_404(e):
        return render_template("errori/404.html"), 404

    @app.errorhandler(500)
    def errore_500(e):
        return render_template("errori/500.html"), 500

    # ================================================================ AUTH

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.utente_corrente:
            return redirect(url_for("dashboard"))
        errore = None
        if request.method == "POST":
            gu = get_utenti()
            utente = gu.autentica(
                request.form.get("username", ""),
                request.form.get("password", ""),
            )
            if utente:
                if utente.totp_attivato:
                    # Credenziali OK ma serve verifica 2FA
                    session.clear()
                    session["totp_pending_uid"] = utente.id
                    session["totp_pending_next"] = request.args.get("next") or url_for("dashboard")
                    return redirect(url_for("login_2fa"))
                session.clear()
                session["user_id"] = utente.id
                session["last_activity"] = datetime.now().isoformat()
                session.permanent = True
                gu.registra_evento(
                    "auth.login",
                    id_utente=utente.id,
                    username=utente.username,
                    ip=request.remote_addr or "",
                )
                next_url = request.args.get("next") or url_for("dashboard")
                return redirect(next_url)
            else:
                errore = "Credenziali non valide o utente disabilitato."
                gu.registra_evento(
                    "auth.login_fallito",
                    username=request.form.get("username", ""),
                    ip=request.remote_addr or "",
                    esito="ERRORE",
                )
        return render_template("auth/login.html", errore=errore)

    @app.route("/logout", methods=["POST"])
    def logout():
        u = g.utente_corrente
        if u:
            get_utenti().registra_evento(
                "auth.logout",
                id_utente=u.id,
                username=u.username,
                ip=request.remote_addr or "",
            )
        session.clear()
        flash("Disconnessione effettuata.", "info")
        return redirect(url_for("login"))

    @app.route("/login/2fa", methods=["GET", "POST"])
    def login_2fa():
        """Secondo step di login: verifica codice TOTP."""
        uid = session.get("totp_pending_uid")
        if not uid:
            return redirect(url_for("login"))
        gu = get_utenti()
        utente = gu.get(uid)
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
                session["last_activity"] = datetime.now().isoformat()
                session.permanent = True
                gu.registra_evento("auth.login", id_utente=utente.id,
                                   username=utente.username, ip=request.remote_addr or "")
                return redirect(next_url)
            errore = "Codice non valido. Riprova."
            gu.registra_evento("auth.2fa_fallito", id_utente=utente.id,
                               username=utente.username, ip=request.remote_addr or "",
                               esito="ERRORE")
        return render_template("auth/login_2fa.html", errore=errore, username=utente.username)

    @app.route("/profilo", methods=["GET", "POST"])
    def profilo():
        u = g.utente_corrente
        if request.method == "POST":
            azione = request.form.get("azione")
            gu = get_utenti()
            if azione == "aggiorna":
                try:
                    gu.aggiorna(u.id,
                                nome_completo=request.form.get("nome_completo", ""),
                                email=request.form.get("email", ""))
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
                    audit("auth.cambia_password")
                    flash("Password aggiornata.", "success")
            elif azione == "2fa_genera":
                segreto = genera_totp_secret()
                session["totp_temp_secret"] = segreto
                flash("Segreto 2FA generato. Scansiona il QR code e conferma con un codice.", "info")
            elif azione == "2fa_conferma":
                segreto = session.get("totp_temp_secret", "")
                codice = request.form.get("codice_2fa", "").strip()
                if segreto and verifica_totp(segreto, codice):
                    gu.aggiorna(u.id, totp_secret=segreto, totp_attivato=True)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_attivato")
                    flash("Autenticazione a due fattori attivata.", "success")
                else:
                    flash("Codice non valido. Riprova a scansionare il QR code.", "danger")
            elif azione == "2fa_disattiva":
                pwd = request.form.get("pwd_disattiva", "")
                if gu.autentica(u.username, pwd):
                    gu.aggiorna(u.id, totp_secret="", totp_attivato=False)
                    session.pop("totp_temp_secret", None)
                    audit("auth.2fa_disattivato")
                    flash("2FA disattivato.", "success")
                else:
                    flash("Password non corretta.", "danger")
            return redirect(url_for("profilo"))
        totp_temp = session.get("totp_temp_secret", "")
        uri_qr = totp_uri(totp_temp, u.username) if totp_temp else ""
        return render_template("auth/profilo.html", utente=u,
                               totp_temp_secret=totp_temp, totp_uri_qr=uri_qr)

    # ---- Gestione utenti (solo AMMINISTRATORE)

    @app.route("/utenti")
    def lista_utenti():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        gu = get_utenti()
        utenti = gu.tutti()
        stats = gu.statistiche()
        return render_template("auth/utenti.html",
                               utenti=utenti, stats=stats, ruoli=list(RuoloUtente))

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
                flash(f"Utente '{nuovo.username}' creato.", "success")
                return redirect(url_for("lista_utenti"))
            except ValueError as e:
                flash(str(e), "danger")
        return render_template("auth/form_utente.html", ruoli=list(RuoloUtente), utente=None)

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
                gu.aggiorna(id_utente,
                            nome_completo=request.form.get("nome_completo", ""),
                            email=request.form.get("email", ""),
                            ruolo=request.form.get("ruolo", target.ruolo.value),
                            attivo=request.form.get("attivo") == "1")
                if request.form.get("nuova_password"):
                    gu.cambia_password(id_utente, request.form["nuova_password"])
                audit("utenti.modifica", "utente", id_utente)
                flash("Utente aggiornato.", "success")
                return redirect(url_for("lista_utenti"))
            except ValueError as e:
                flash(str(e), "danger")
        return render_template("auth/form_utente.html",
                               ruoli=list(RuoloUtente), utente=target)

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
        return render_template("auth/audit.html",
                               eventi=eventi, utenti=utenti,
                               filtro_utente=id_utente, filtro_azione=azione)

    @app.route("/api/utenti/statistiche")
    def api_utenti_statistiche():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        return jsonify(get_utenti().statistiche())

    # ---- Gestione profili / matrice permessi

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
                audit("utenti.aggiorna_permessi",
                      risorsa_tipo="utente", risorsa_id=id_utente,
                      dettagli=f"extra={extra} negati={negati}")
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
        )

    # ================================================================ SCADENZIARIO

    @app.route("/scadenziario")
    def scadenziario():
        gs = get_scadenziario()
        filtro_tipo = request.args.get("tipo", "")
        filtro_priorita = request.args.get("priorita", "")
        id_fascicolo = request.args.get("id_fascicolo", "")
        scadenze = gs.tutte(
            tipo=TipoTermine(filtro_tipo) if filtro_tipo else None,
            priorita=PrioritaTermine(filtro_priorita) if filtro_priorita else None,
            id_fascicolo=id_fascicolo,
        )
        scadute = gs.scadute()
        imminenti = gs.imminenti(entro_giorni=7)
        stats = gs.statistiche()
        return render_template(
            "scadenziario/lista.html",
            scadenze=scadenze,
            scadute=scadute,
            imminenti=imminenti,
            stats=stats,
            tipi=list(TipoTermine),
            priorita_list=list(PrioritaTermine),
            filtro_tipo=filtro_tipo,
            filtro_priorita=filtro_priorita,
            id_fascicolo=id_fascicolo,
        )

    @app.route("/scadenziario/nuova", methods=["GET", "POST"])
    def nuova_scadenza():
        if request.method == "POST":
            gs = get_scadenziario()
            f = request.form
            try:
                preset = f.get("preset", "")
                if preset:
                    sc = gs.nuova_da_preset(
                        preset_key=preset,
                        titolo=f["titolo"].strip(),
                        data_decorrenza=f["data_decorrenza"],
                        id_fascicolo=f.get("id_fascicolo", ""),
                        perentorio=f.get("perentorio") == "1",
                        id_utente_responsabile=f.get("id_utente", ""),
                    )
                else:
                    sc = gs.nuova(
                        titolo=f["titolo"].strip(),
                        tipo=TipoTermine(f["tipo"]),
                        data_scadenza=f["data_scadenza"],
                        id_fascicolo=f.get("id_fascicolo", ""),
                        descrizione=f.get("descrizione", ""),
                        data_decorrenza=f.get("data_decorrenza", ""),
                        perentorio=f.get("perentorio") == "1",
                        id_utente_responsabile=f.get("id_utente", ""),
                    )
                audit("scadenziario.crea", "scadenza", sc.id, sc.titolo)
                flash(f"Scadenza '{sc.titolo}' creata.", "success")
                sync_pubblica("crea", "scadenze", sc.id)
                return redirect(url_for("scadenziario"))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")
        gf = get_fascicoli()
        gu = get_utenti()
        return render_template(
            "scadenziario/form.html",
            tipi=list(TipoTermine),
            preset_list=PRESET_TERMINI,
            fascicoli=gf.tutti(),
            utenti=gu.tutti(solo_attivi=True),
            scadenza=None,
        )

    @app.route("/scadenziario/<id_sc>")
    def dettaglio_scadenza(id_sc):
        gs = get_scadenziario()
        sc = gs.get(id_sc)
        if not sc:
            flash("Scadenza non trovata.", "warning")
            return redirect(url_for("scadenziario"))
        return render_template("scadenziario/dettaglio.html", sc=sc)

    @app.route("/scadenziario/<id_sc>/modifica", methods=["GET", "POST"])
    def modifica_scadenza(id_sc):
        gs = get_scadenziario()
        sc = gs.get(id_sc)
        if not sc:
            flash("Scadenza non trovata.", "warning")
            return redirect(url_for("scadenziario"))
        if request.method == "POST":
            f = request.form
            try:
                gs.aggiorna(
                    id_sc,
                    titolo=f.get("titolo", sc.titolo),
                    tipo=f.get("tipo", sc.tipo.value),
                    data_scadenza=f.get("data_scadenza", sc.data_scadenza),
                    descrizione=f.get("descrizione", sc.descrizione),
                    perentorio=f.get("perentorio") == "1",
                    note=f.get("note", sc.note),
                )
                audit("scadenziario.modifica", "scadenza", id_sc)
                flash("Scadenza aggiornata.", "success")
                sync_pubblica("modifica", "scadenze", id_sc)
                return redirect(url_for("scadenziario"))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")
        gf = get_fascicoli()
        gu = get_utenti()
        return render_template(
            "scadenziario/form.html",
            tipi=list(TipoTermine),
            preset_list=PRESET_TERMINI,
            fascicoli=gf.tutti(),
            utenti=gu.tutti(solo_attivi=True),
            scadenza=sc,
        )

    @app.route("/scadenziario/<id_sc>/completa", methods=["POST"])
    def completa_scadenza(id_sc):
        gs = get_scadenziario()
        note = request.form.get("note", "")
        try:
            gs.completa(id_sc, note=note)
            audit("scadenziario.completa", "scadenza", id_sc)
            sync_pubblica("modifica", "scadenze", id_sc)
        except ValueError as e:
            if request.headers.get("HX-Request"):
                return f'<tr id="sc-{id_sc}"><td colspan="7" class="text-danger small p-2">{e}</td></tr>', 422
            flash(str(e), "danger")
            return redirect(url_for("scadenziario"))
        # htmx: rimuove la riga dalla tabella con animazione
        if request.headers.get("HX-Request"):
            return f'<tr id="sc-{id_sc}" class="sc-completed"><td colspan="7"></td></tr>', 200
        flash("Scadenza segnata come completata.", "success")
        return redirect(url_for("scadenziario"))

    @app.route("/api/notifiche/pending")
    def notifiche_pending():
        """Restituisce notifiche urgenti da mostrare via Browser Notification API."""
        if not g.utente_corrente:
            return jsonify([])
        gs = get_scadenziario()
        alerts = []
        oggi = date.today()
        scadute = [s for s in gs.imminenti(entro_giorni=0) if s.giorni_alla_scadenza is not None and s.giorni_alla_scadenza < 0]
        critiche_oggi = [s for s in gs.imminenti(entro_giorni=1) if s.giorni_alla_scadenza == 0]
        imminenti = [s for s in gs.imminenti(entro_giorni=3) if s.perentorio and (s.giorni_alla_scadenza or 0) > 0]
        if scadute:
            alerts.append({
                "titolo": f"⚠️ {len(scadute)} scadenza/e SCADUTA/E",
                "corpo": " • ".join(s.titolo for s in scadute[:3]),
                "url": "/scadenziario",
                "delay": 2000,
            })
        if critiche_oggi:
            alerts.append({
                "titolo": f"🔴 {len(critiche_oggi)} scadenza/e OGGI",
                "corpo": " • ".join(s.titolo for s in critiche_oggi[:3]),
                "url": "/scadenziario",
                "delay": 4000,
            })
        if imminenti:
            alerts.append({
                "titolo": f"🔔 {len(imminenti)} termine/i perentorio/i imminente/i",
                "corpo": " • ".join(s.titolo for s in imminenti[:3]),
                "url": "/scadenziario",
                "delay": 6000,
            })
        return jsonify(alerts)

    @app.route("/scadenziario/<id_sc>/elimina", methods=["POST"])
    def elimina_scadenza(id_sc):
        gs = get_scadenziario()
        try:
            gs.elimina(id_sc)
            audit("scadenziario.elimina", "scadenza", id_sc)
            flash("Scadenza eliminata.", "success")
            sync_pubblica("elimina", "scadenze", id_sc)
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("scadenziario"))

    @app.route("/scadenziario/calcola-termine", methods=["POST"])
    def calcola_termine_route():
        """API AJAX per il calcolo dinamico del termine."""
        data = request.get_json() or {}
        try:
            d_inizio = date.fromisoformat(data["data_inizio"])
            giorni = int(data["giorni"])
            tipo = data.get("tipo", "liberi")
            sospensione = data.get("sospensione_feriale", True)
            d_scadenza = calcola_termine(d_inizio, giorni, tipo, sospensione)
            return jsonify({
                "data_scadenza": d_scadenza.isoformat(),
                "lavorativo": è_giorno_lavorativo(d_scadenza),
            })
        except (KeyError, ValueError) as e:
            return jsonify({"errore": str(e)}), 400

    @app.route("/api/scadenziario/imminenti")
    def api_scadenze_imminenti():
        giorni = int(request.args.get("giorni", 7))
        gs = get_scadenziario()
        sc = gs.imminenti(entro_giorni=giorni)
        return jsonify([s.to_dict() for s in sc])

    @app.route("/api/scadenziario/statistiche")
    def api_scadenziario_statistiche():
        return jsonify(get_scadenziario().statistiche())

    # ---------------------------------------------------------------- dashboard

    @app.route("/")
    def dashboard():
        agenda = get_agenda()
        oggi = date.today()
        apps_oggi = agenda.per_giorno(oggi)
        apps_settimana = agenda.per_settimana(oggi)
        reminder = agenda.prossimi_reminder(entro_minuti=120)
        stats = agenda.statistiche()
        # Scadenze imminenti per dashboard
        gs = get_scadenziario()
        scadenze_critiche = gs.imminenti(entro_giorni=3)
        scadenze_imminenti = gs.imminenti(entro_giorni=7)
        stats_sc = gs.statistiche()
        stats_fascicoli = get_fascicoli().statistiche()
        stats_clienti = get_clienti().statistiche()
        # #4 — Cartelle condivise per collaboratori
        u_dash = g.utente_corrente
        cartelle_mie = []
        accessi_in_scadenza = []
        if u_dash and not u_dash.ha_permesso("clienti.leggi"):
            gcd = get_condivisioni()
            gc = get_clienti()
            cartelle_mie = [
                (gc.get(id_c), ac)
                for id_c, ac in gcd.cartelle_condivise_con(u_dash.id)
                if gc.get(id_c) and not ac.is_scaduto
            ][:5]
            accessi_in_scadenza = gcd.accessi_in_scadenza(entro_giorni=7)
        return render_template(
            "dashboard.html",
            apps_oggi=apps_oggi,
            apps_settimana=apps_settimana,
            reminder=reminder,
            stats=stats,
            scadenze_critiche=scadenze_critiche,
            scadenze_imminenti=scadenze_imminenti,
            stats_sc=stats_sc,
            stats_fascicoli=stats_fascicoli,
            stats_clienti=stats_clienti,
            cartelle_mie=cartelle_mie,
            accessi_in_scadenza=accessi_in_scadenza,
        )

    # ---------------------------------------------------------------- agenda

    @app.route("/agenda")
    def agenda_view():
        agenda = get_agenda()
        vista = request.args.get("vista", "settimana")
        oggi = date.today()

        # navigazione settimana / mese
        offset = int(request.args.get("offset", 0))

        if vista == "giorno":
            giorno = oggi + timedelta(days=offset)
            apps = agenda.per_giorno(giorno)
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                giorno=giorno,
                offset=offset,
            )

        if vista == "mese":
            # offset in mesi
            anno = oggi.year
            mese = oggi.month + offset
            while mese > 12:
                mese -= 12
                anno += 1
            while mese < 1:
                mese += 12
                anno -= 1
            apps = agenda.per_mese(anno, mese)
            primo = date(anno, mese, 1)
            # padding giorni iniziali per griglia
            pad = primo.weekday()  # lunedì=0
            import calendar
            giorni_mese = calendar.monthrange(anno, mese)[1]
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                anno=anno,
                mese=mese,
                primo=primo,
                pad=pad,
                giorni_mese=giorni_mese,
                offset=offset,
                nomi_mesi=[
                    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio",
                    "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre",
                    "Novembre", "Dicembre",
                ],
            )

        # default: settimana
        inizio = oggi + timedelta(weeks=offset) - timedelta(days=oggi.weekday())
        fine = inizio + timedelta(days=6)
        apps = agenda.per_settimana(inizio)
        giorni = [inizio + timedelta(days=i) for i in range(7)]
        apps_per_giorno = {g: [a for a in apps if a.data_ora_dt.date() == g] for g in giorni}
        return render_template(
            "agenda.html",
            vista=vista,
            apps=apps,
            apps_per_giorno=apps_per_giorno,
            giorni=giorni,
            inizio=inizio,
            fine=fine,
            offset=offset,
        )

    @app.route("/agenda/nuovo", methods=["GET", "POST"])
    def nuovo_appuntamento():
        if request.method == "POST":
            agenda = get_agenda()
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            data_ora = f"{data}T{ora}:00" if data else ""
            try:
                app = agenda.aggiungi(
                    titolo=request.form["titolo"],
                    tipo=TipoAppuntamento(request.form["tipo"]),
                    data_ora=data_ora,
                    durata_minuti=int(request.form.get("durata", 60)),
                    luogo=request.form.get("luogo", ""),
                    cliente=request.form.get("cliente", ""),
                    cf_cliente=request.form.get("cf_cliente", ""),
                    procedimento=request.form.get("procedimento", ""),
                    tribunale=request.form.get("tribunale", ""),
                    avvocato=request.form.get("avvocato", ""),
                    note=request.form.get("note", ""),
                    reminder_minuti=int(request.form.get("reminder", 60)),
                )
                flash(f"Appuntamento '{app.titolo}' aggiunto.", "success")
                return redirect(url_for("dettaglio_appuntamento", id_app=app.id))
            except ValueError as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        tribunali = reginde.elenca_uffici()
        return render_template(
            "form_appuntamento.html",
            app=None,
            tipi=list(TipoAppuntamento),
            tribunali=tribunali,
        )

    @app.route("/agenda/<id_app>")
    def dettaglio_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))
        track_recente("appuntamento", id_app, app.titolo,
                      url_for("dettaglio_appuntamento", id_app=id_app), "bi-calendar-event")
        return render_template("dettaglio_appuntamento.html", app=app)

    @app.route("/agenda/<id_app>/modifica", methods=["GET", "POST"])
    def modifica_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))

        if request.method == "POST":
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            campi = {
                "titolo": request.form["titolo"],
                "tipo": TipoAppuntamento(request.form["tipo"]),
                "data_ora": f"{data}T{ora}:00" if data else app.data_ora,
                "durata_minuti": int(request.form.get("durata", app.durata_minuti)),
                "luogo": request.form.get("luogo", ""),
                "cliente": request.form.get("cliente", ""),
                "cf_cliente": request.form.get("cf_cliente", ""),
                "procedimento": request.form.get("procedimento", ""),
                "tribunale": request.form.get("tribunale", ""),
                "avvocato": request.form.get("avvocato", ""),
                "note": request.form.get("note", ""),
                "reminder_minuti": int(request.form.get("reminder", app.reminder_minuti)),
            }
            try:
                agenda.modifica(id_app, **campi)
                flash("Appuntamento aggiornato.", "success")
                sync_pubblica("modifica", "agenda", id_app)
                return redirect(url_for("dettaglio_appuntamento", id_app=id_app))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        tribunali = reginde.elenca_uffici()
        return render_template(
            "form_appuntamento.html",
            app=app,
            tipi=list(TipoAppuntamento),
            tribunali=tribunali,
        )

    @app.route("/agenda/<id_app>/stato", methods=["POST"])
    def cambia_stato(id_app):
        agenda = get_agenda()
        nuovo = request.form.get("stato")
        try:
            agenda.cambia_stato(id_app, StatoAppuntamento(nuovo))
            flash("Stato aggiornato.", "success")
        except (KeyError, ValueError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_appuntamento", id_app=id_app))

    @app.route("/agenda/<id_app>/elimina", methods=["POST"])
    def elimina_appuntamento(id_app):
        agenda = get_agenda()
        try:
            agenda.elimina(id_app)
            flash("Appuntamento eliminato.", "success")
            sync_pubblica("elimina", "agenda", id_app)
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("agenda_view"))

    # ---------------------------------------------------------------- API JSON

    @app.route("/api/agenda/<id_app>/sposta", methods=["POST"])
    def api_sposta_appuntamento(id_app):
        """Sposta un appuntamento in una nuova data/ora (drag-and-drop)."""
        if not g.utente_corrente or not g.utente_corrente.ha_permesso("agenda.scrivi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        ag = get_agenda()
        appt = ag.get(id_app)
        if not appt:
            return jsonify({"errore": "Appuntamento non trovato"}), 404
        payload = request.get_json(silent=True) or {}
        nuova_data = payload.get("data")          # "YYYY-MM-DD"
        nuova_data_ora = payload.get("data_ora")  # "YYYY-MM-DDTHH:MM:SS"
        if nuova_data and not nuova_data_ora:
            ora_orig = appt.data_ora_dt.strftime("%H:%M:%S")
            nuova_data_ora = f"{nuova_data}T{ora_orig}"
        if not nuova_data_ora:
            return jsonify({"errore": "Parametro 'data' o 'data_ora' richiesto"}), 400
        try:
            appt = ag.modifica(id_app, data_ora=nuova_data_ora)
            audit("agenda.sposta", "appuntamento", id_app,
                  dettagli=f"→ {nuova_data_ora}")
            return jsonify({"ok": True, "data_ora": appt.data_ora})
        except (ValueError, KeyError) as e:
            return jsonify({"errore": str(e)}), 409

    @app.route("/api/agenda")
    def api_agenda():
        agenda = get_agenda()
        da_str = request.args.get("da")
        a_str = request.args.get("a")
        da = date.fromisoformat(da_str) if da_str else None
        a = date.fromisoformat(a_str) if a_str else None
        apps = agenda.cerca(da=da, a=a)
        return jsonify([a.to_dict() for a in apps])

    @app.route("/api/agenda/<id_app>")
    def api_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            return jsonify({"errore": "Non trovato"}), 404
        return jsonify(app.to_dict())

    @app.route("/api/reminder")
    def api_reminder():
        agenda = get_agenda()
        entro = int(request.args.get("entro", 60))
        apps = agenda.prossimi_reminder(entro_minuti=entro)
        return jsonify([a.to_dict() for a in apps])

    @app.route("/api/statistiche")
    def api_statistiche():
        return jsonify(get_agenda().statistiche())

    # ---------------------------------------------------------------- tribunali

    @app.route("/tribunali")
    def tribunali():
        reginde = ClientReGINde()
        uffici = reginde.elenca_uffici()
        return render_template("tribunali.html", uffici=uffici)

    # ================================================================ CLIENTI

    @app.route("/clienti")
    def lista_clienti():
        gc = get_clienti()
        u = g.utente_corrente
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "ATTIVO")

        tipo = TipoCliente(tipo_f) if tipo_f else None
        stato = StatoCliente(stato_f) if stato_f else None

        clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)

        # Utenti senza accesso globale vedono solo i clienti condivisi con loro
        if u and not u.ha_permesso("clienti.leggi"):
            ids_accessibili = get_condivisioni().ids_clienti_accessibili(u.id)
            clienti = [c for c in clienti if c.id in ids_accessibili]

        stats = gc.statistiche()
        return render_template(
            "clienti/lista.html",
            clienti=clienti,
            stats=stats,
            q=testo,
            tipo_filtro=tipo_f or "",
            stato_filtro=stato_f or "",
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
        )

    @app.route("/clienti/nuovo", methods=["GET", "POST"])
    def nuovo_cliente():
        gc = get_clienti()
        if request.method == "POST":
            f = request.form
            tipo = TipoCliente(f["tipo"])
            try:
                c = gc.nuovo(
                    tipo=tipo,
                    nome=f.get("nome", ""),
                    cognome=f.get("cognome", ""),
                    ragione_sociale=f.get("ragione_sociale", ""),
                    codice_fiscale=f.get("codice_fiscale", "").upper(),
                    partita_iva=f.get("partita_iva", ""),
                    forma_giuridica=f.get("forma_giuridica", ""),
                    data_nascita=f.get("data_nascita", ""),
                    luogo_nascita=f.get("luogo_nascita", ""),
                    provincia_nascita=f.get("provincia_nascita", ""),
                    sesso=f.get("sesso", ""),
                    nazionalita=f.get("nazionalita", "Italiana"),
                    rappresentante_legale=f.get("rappresentante_legale", ""),
                    cf_rappresentante=f.get("cf_rappresentante", "").upper(),
                    avvocato_referente=f.get("avvocato_referente", ""),
                    provenienza=f.get("provenienza", ""),
                    note=f.get("note", ""),
                )
                # indirizzi e recapiti
                _salva_indirizzo(gc, c.id, "residenza", f)
                _salva_indirizzo(gc, c.id, "domicilio", f, prefix="dom_")
                _salva_indirizzo(gc, c.id, "sede_legale", f, prefix="sl_")
                gc.aggiorna_recapiti(c.id,
                    telefono=f.get("telefono", ""),
                    cellulare=f.get("cellulare", ""),
                    email=f.get("email", ""),
                    pec=f.get("pec", ""),
                    fax=f.get("fax", ""),
                    sito_web=f.get("sito_web", ""),
                )
                flash(f"Cliente '{c.nome_completo}' aggiunto.", "success")
                sync_pubblica("crea", "clienti", c.id)
                return redirect(url_for("dettaglio_cliente", id_cliente=c.id))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        return render_template(
            "clienti/form.html",
            cliente=None,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumentoCliente),
            tribunali=reginde.elenca_uffici(),
        )

    @app.route("/clienti/<id_cliente>")
    def dettaglio_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))
        agenda = get_agenda()
        apps_cliente = agenda.cerca(cliente=c.nome_completo)
        gcd = get_condivisioni()
        n_collaboratori = gcd.n_collaboratori(id_cliente)
        u = g.utente_corrente
        ruolo_cond = gcd.ruolo_accesso(u.id, id_cliente) if u else None
        # #3 — Audit: registra accesso a cartella condivisa
        if u and not u.ha_permesso("clienti.leggi") and ruolo_cond:
            audit("condivisione.accesso", "cliente", id_cliente,
                  dettagli=f"accesso lettura [{ruolo_cond.value}]")
        link_attivi = gcd.link_attivi_per_cliente(id_cliente)
        track_recente("cliente", id_cliente, c.nome_completo,
                      url_for("dettaglio_cliente", id_cliente=id_cliente), "bi-person")
        return render_template(
            "clienti/dettaglio.html",
            cliente=c,
            apps_cliente=apps_cliente,
            n_collaboratori=n_collaboratori,
            ruolo_condivisione=ruolo_cond,
            link_attivi=link_attivi,
        )

    @app.route("/clienti/<id_cliente>/modifica", methods=["GET", "POST"])
    def modifica_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente, RuoloCondivisione.SCRITTURA):
            flash("Non hai permesso di modificare questa cartella cliente.", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

        if request.method == "POST":
            f = request.form
            try:
                gc.aggiorna(id_cliente,
                    nome=f.get("nome", c.nome),
                    cognome=f.get("cognome", c.cognome),
                    ragione_sociale=f.get("ragione_sociale", c.ragione_sociale),
                    codice_fiscale=f.get("codice_fiscale", c.codice_fiscale).upper(),
                    partita_iva=f.get("partita_iva", c.partita_iva),
                    forma_giuridica=f.get("forma_giuridica", c.forma_giuridica),
                    data_nascita=f.get("data_nascita", c.data_nascita),
                    luogo_nascita=f.get("luogo_nascita", c.luogo_nascita),
                    provincia_nascita=f.get("provincia_nascita", c.provincia_nascita),
                    sesso=f.get("sesso", c.sesso),
                    nazionalita=f.get("nazionalita", c.nazionalita),
                    rappresentante_legale=f.get("rappresentante_legale", c.rappresentante_legale),
                    cf_rappresentante=f.get("cf_rappresentante", c.cf_rappresentante).upper(),
                    avvocato_referente=f.get("avvocato_referente", c.avvocato_referente),
                    provenienza=f.get("provenienza", c.provenienza),
                    note=f.get("note", c.note),
                    stato=StatoCliente(f.get("stato", c.stato.value)),
                )
                _salva_indirizzo(gc, id_cliente, "residenza", f)
                _salva_indirizzo(gc, id_cliente, "domicilio", f, prefix="dom_")
                _salva_indirizzo(gc, id_cliente, "sede_legale", f, prefix="sl_")
                gc.aggiorna_recapiti(id_cliente,
                    telefono=f.get("telefono", ""),
                    cellulare=f.get("cellulare", ""),
                    email=f.get("email", ""),
                    pec=f.get("pec", ""),
                    fax=f.get("fax", ""),
                    sito_web=f.get("sito_web", ""),
                )
                gc.aggiorna_documento(id_cliente,
                    tipo=TipoDocumentoCliente(f.get("doc_tipo", c.documento.tipo.value)),
                    numero=f.get("doc_numero", ""),
                    rilasciato_da=f.get("doc_rilasciato_da", ""),
                    data_rilascio=f.get("doc_data_rilascio", ""),
                    data_scadenza=f.get("doc_data_scadenza", ""),
                )
                flash("Cliente aggiornato.", "success")
                sync_pubblica("modifica", "clienti", id_cliente)
                return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        return render_template(
            "clienti/form.html",
            cliente=c,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumentoCliente),
            tribunali=reginde.elenca_uffici(),
        )

    @app.route("/clienti/<id_cliente>/elimina", methods=["POST"])
    def elimina_cliente(id_cliente):
        gc = get_clienti()
        try:
            gc.elimina(id_cliente)
            flash("Cliente eliminato.", "success")
            sync_pubblica("elimina", "clienti", id_cliente)
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_clienti"))

    @app.route("/clienti/<id_cliente>/procedimento", methods=["POST"])
    def aggiungi_procedimento(id_cliente):
        gc = get_clienti()
        f = request.form
        try:
            proc = RiferimentoProcedimento(
                numero_rg=f["numero_rg"],
                anno=int(f.get("anno", datetime.now().year)),
                tribunale=f.get("tribunale", ""),
                descrizione=f.get("descrizione", ""),
                data_apertura=f.get("data_apertura", date.today().isoformat()),
            )
            gc.aggiungi_procedimento(id_cliente, proc)
            flash("Procedimento aggiunto.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    # ---- API clienti

    @app.route("/api/clienti")
    def api_clienti():
        gc = get_clienti()
        q = request.args.get("q", "")
        clienti = gc.cerca(testo=q) if q else gc.tutti()
        return jsonify([c.to_dict() for c in clienti])

    @app.route("/api/clienti/<id_cliente>")
    def api_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            return jsonify({"errore": "Non trovato"}), 404
        return jsonify(c.to_dict())

    @app.route("/api/clienti/statistiche")
    def api_clienti_statistiche():
        return jsonify(get_clienti().statistiche())

    # ---------------------------------------------------------------- helpers

    def _salva_indirizzo(gc, id_c, tipo, f, prefix=""):
        gc.aggiorna_indirizzo(id_c, tipo,
            via=f.get(f"{prefix}via", ""),
            civico=f.get(f"{prefix}civico", ""),
            cap=f.get(f"{prefix}cap", ""),
            comune=f.get(f"{prefix}comune", ""),
            provincia=f.get(f"{prefix}provincia", ""),
            nazione=f.get(f"{prefix}nazione", "Italia"),
        )

    # ================================================================ CONDIVISIONE CARTELLE

    @app.route("/cartelle-condivise")
    def cartelle_condivise():
        """Elenco delle cartelle clienti condivise con l'utente corrente."""
        u = g.utente_corrente
        gcd = get_condivisioni()
        gc = get_clienti()

        # Utenti con accesso globale vedono le cartelle che LORO hanno condiviso
        if u.ha_permesso("clienti.leggi"):
            # Mostra statistiche e chi gestisco
            accessi_da_me = [
                (gc.get(id_c), ac)
                for id_c, ac in gcd.cartelle_condivise_con(u.id)
                if gc.get(id_c)
            ]
            cartelle_gestite = [
                (gc.get(id_c), gcd.collaboratori_di(id_c))
                for id_c in gc.tutti(stato=None)
                if gc.get(id_c) and gcd.n_collaboratori(id_c) > 0
            ]
            return render_template(
                "clienti/cartelle_condivise.html",
                modalita="gestore",
                cartelle_gestite=cartelle_gestite,
                accessi_da_me=accessi_da_me,
                stats=gcd.statistiche(),
            )

        # Utenti con accesso limitato vedono le cartelle condivise con loro
        condivisioni = gcd.cartelle_condivise_con(u.id)
        cartelle = [
            (gc.get(id_c), accesso)
            for id_c, accesso in condivisioni
            if gc.get(id_c)
        ]
        return render_template(
            "clienti/cartelle_condivise.html",
            modalita="collaboratore",
            cartelle=cartelle,
            stats=gcd.statistiche(),
        )

    @app.route("/clienti/<id_cliente>/collaboratori", methods=["GET", "POST"])
    def gestione_collaboratori(id_cliente):
        """
        Gestione collaboratori di una cartella cliente.
        Accessibile a chi ha il permesso globale clienti.scrivi
        oppure è GESTORE della specifica cartella.
        """
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        u = g.utente_corrente
        puo_gestire = (
            u.ha_permesso("clienti.scrivi")
            or get_condivisioni().ha_accesso(u.id, id_cliente, RuoloCondivisione.GESTORE)
        )
        if not puo_gestire:
            flash("Non hai il permesso di gestire i collaboratori di questa cartella.", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

        gcd = get_condivisioni()
        gu = get_utenti()

        if request.method == "POST":
            azione = request.form.get("azione", "condividi")

            if azione == "condividi":
                id_dest = request.form.get("id_utente", "").strip()
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                note = request.form.get("note", "").strip()
                # #2 — Scadenza accesso
                data_scadenza = request.form.get("data_scadenza", "").strip()
                # #9 — Tag
                tags_raw = request.form.get("tags", "").strip()
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                utente_dest = gu.get(id_dest)
                if not utente_dest:
                    flash("Utente non trovato.", "danger")
                else:
                    try:
                        gcd.condividi(
                            id_cliente=id_cliente,
                            id_utente=utente_dest.id,
                            username=utente_dest.username,
                            nome_completo=utente_dest.nome_completo or utente_dest.username,
                            ruolo=RuoloCondivisione(ruolo_str),
                            condiviso_da=u.username,
                            note=note,
                            data_scadenza=data_scadenza,
                            tags=tags,
                        )
                        flash(
                            f"Cartella condivisa con {utente_dest.username} "
                            f"({RuoloCondivisione(ruolo_str).value}).",
                            "success",
                        )
                        audit("condivisione.condividi", "cliente", id_cliente,
                              dettagli=f"→ {utente_dest.username} [{ruolo_str}]"
                                       + (f" scade {data_scadenza}" if data_scadenza else ""))
                        _sync.pubblica("info", "clienti", id_cliente, u.username,
                                       messaggio=f"Cartella condivisa con {utente_dest.username}")
                        # #1 — Notifica email all'utente destinatario
                        if utente_dest.email:
                            try:
                                get_messaggi().invia_email(
                                    destinatario=utente_dest.email,
                                    oggetto=f"Cartella condivisa: {c.nome_completo}",
                                    corpo_testo=(
                                        f"Ciao {utente_dest.nome_completo or utente_dest.username},\n\n"
                                        f"{u.nome_completo or u.username} ha condiviso con te "
                                        f"la cartella cliente di {c.nome_completo} "
                                        f"con accesso {RuoloCondivisione(ruolo_str).value}.\n"
                                        + (f"L'accesso scade il {data_scadenza}.\n" if data_scadenza else "")
                                        + (f"Note: {note}\n" if note else "")
                                        + "\nAccedi allo studio per visualizzare la cartella."
                                    ),
                                    nome_destinatario=utente_dest.nome_completo or utente_dest.username,
                                )
                            except Exception:
                                pass  # Notifica email non bloccante
                    except ValueError as e:
                        flash(str(e), "danger")

            elif azione == "revoca":
                id_dest = request.form.get("id_utente", "").strip()
                utente_dest = gu.get(id_dest)
                username_dest = utente_dest.username if utente_dest else id_dest
                if gcd.revoca(id_cliente, id_dest):
                    flash(f"Accesso revocato per {username_dest}.", "success")
                    audit("condivisione.revoca", "cliente", id_cliente,
                          dettagli=f"→ {username_dest}")
                    _sync.pubblica("info", "clienti", id_cliente, u.username,
                                   messaggio=f"Accesso revocato per {username_dest}")
                    # #1 — Notifica revoca
                    if utente_dest and utente_dest.email:
                        try:
                            get_messaggi().invia_email(
                                destinatario=utente_dest.email,
                                oggetto=f"Accesso revocato: {c.nome_completo}",
                                corpo_testo=(
                                    f"Ciao {utente_dest.nome_completo or utente_dest.username},\n\n"
                                    f"Il tuo accesso alla cartella cliente di {c.nome_completo} "
                                    f"è stato revocato da {u.nome_completo or u.username}."
                                ),
                                nome_destinatario=utente_dest.nome_completo or utente_dest.username,
                            )
                        except Exception:
                            pass
                else:
                    flash("Accesso non trovato.", "warning")

            elif azione == "crea_link":
                # #6 — Crea link temporaneo
                ore = int(request.form.get("ore_validita", 72))
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                monouso = request.form.get("monouso") == "1"
                descrizione = request.form.get("descrizione", "").strip()
                token, link = gcd.crea_link_temporaneo(
                    id_cliente=id_cliente,
                    creato_da=u.username,
                    ruolo=RuoloCondivisione(ruolo_str),
                    ore_validita=ore,
                    monouso=monouso,
                    descrizione=descrizione,
                )
                audit("condivisione.link_creato", "cliente", id_cliente,
                      dettagli=f"link {link.id} [{ruolo_str}] {ore}h")
                link_url = url_for("accesso_link_temporaneo", token=token, _external=True)
                flash(
                    f"Link creato (valido {ore}h). Copialo e invialo al destinatario.",
                    "success",
                )
                # Mostra il link nella pagina (non nel redirect)
                collaboratori = gcd.collaboratori_di(id_cliente)
                ids_collaboratori = {a.id_utente for a in collaboratori}
                tutti_utenti = [
                    ut for ut in gu.tutti(solo_attivi=True)
                    if ut.id != u.id and ut.id not in ids_collaboratori
                ]
                return render_template(
                    "clienti/collaboratori.html",
                    cliente=c,
                    collaboratori=collaboratori,
                    utenti_disponibili=tutti_utenti,
                    ruoli_condivisione=list(RuoloCondivisione),
                    link_temporanei=gcd.link_attivi_per_cliente(id_cliente),
                    nuovo_link_url=link_url,
                )

            elif azione == "revoca_link":
                id_link = request.form.get("id_link", "").strip()
                if gcd.revoca_link_temporaneo(id_link):
                    flash("Link revocato.", "success")
                    audit("condivisione.link_revocato", "cliente", id_cliente,
                          dettagli=f"link {id_link}")
                else:
                    flash("Link non trovato.", "warning")

            return redirect(url_for("gestione_collaboratori", id_cliente=id_cliente))

        # GET — mostra pagina di gestione
        collaboratori = gcd.collaboratori_di(id_cliente)
        ids_collaboratori = {a.id_utente for a in collaboratori}
        tutti_utenti = [
            ut for ut in gu.tutti(solo_attivi=True)
            if ut.id != u.id and ut.id not in ids_collaboratori
        ]
        return render_template(
            "clienti/collaboratori.html",
            cliente=c,
            collaboratori=collaboratori,
            utenti_disponibili=tutti_utenti,
            ruoli_condivisione=list(RuoloCondivisione),
            link_temporanei=gcd.link_attivi_per_cliente(id_cliente),
            nuovo_link_url=None,
        )

    # ================================================================ #6 LINK TEMPORANEI

    @app.route("/accesso/<token>")
    def accesso_link_temporaneo(token):
        """Accesso a una cartella via link temporaneo (senza login obbligatorio)."""
        gcd = get_condivisioni()
        link = gcd.verifica_link_temporaneo(token)
        if not link:
            return render_template("clienti/link_scaduto.html"), 410

        gc = get_clienti()
        cliente = gc.get(link.id_cliente)
        if not cliente:
            return render_template("clienti/link_scaduto.html"), 404

        fascicolo = None
        if link.id_fascicolo:
            gf = get_fascicoli()
            fascicolo = gf.get(link.id_fascicolo)

        audit("condivisione.link_accesso", "cliente", link.id_cliente,
              dettagli=f"link {link.id} desc={link.descrizione}")

        return render_template(
            "clienti/link_temporaneo.html",
            cliente=cliente,
            fascicolo=fascicolo,
            link=link,
            ruolo=link.ruolo,
        )

    # ================================================================ #8 EXPORT CARTELLA ZIP

    @app.route("/clienti/<id_cliente>/esporta")
    def esporta_cartella(id_cliente):
        """Esporta l'intera cartella cliente come ZIP (anagrafica + fascicoli + documenti)."""
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))

        gc = get_clienti()
        cliente = gc.get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        gf = get_fascicoli()
        fascicoli_cliente = [f for f in gf.tutti() if f.id_cliente == id_cliente]

        buf = io.BytesIO()
        with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
            # Anagrafica cliente
            zf.writestr(
                "anagrafica.json",
                json.dumps(cliente.__dict__ if hasattr(cliente, "__dict__") else vars(cliente),
                           default=str, ensure_ascii=False, indent=2),
            )
            # Fascicoli e documenti
            for fasc in fascicoli_cliente:
                prefix = f"fascicoli/{fasc.numero or fasc.id}/"
                fasc_dict = fasc.to_dict() if hasattr(fasc, "to_dict") else vars(fasc)
                zf.writestr(prefix + "fascicolo.json",
                            json.dumps(fasc_dict, default=str, ensure_ascii=False, indent=2))
                for doc in fasc.documenti:
                    try:
                        percorso = gf.percorso_documento(fasc.id, doc.id)
                        if percorso.exists():
                            zf.write(percorso, prefix + "documenti/" + doc.nome)
                    except (KeyError, OSError):
                        pass
            # Indice
            indice = {
                "cliente": cliente.nome_completo,
                "fascicoli": [{"id": f.id, "numero": f.numero, "titolo": f.titolo}
                               for f in fascicoli_cliente],
                "esportato_il": datetime.now().isoformat(),
                "esportato_da": g.utente_corrente.username if g.utente_corrente else "—",
            }
            zf.writestr("indice.json", json.dumps(indice, ensure_ascii=False, indent=2))

        buf.seek(0)
        audit("condivisione.esporta", "cliente", id_cliente,
              dettagli=f"ZIP cartella {cliente.nome_completo}")
        nome_zip = f"cartella_{cliente.nome_completo.replace(' ', '_')}.zip"
        return send_file(buf, as_attachment=True, download_name=nome_zip,
                         mimetype="application/zip")

    # ================================================================ #5 FASCICOLI CONDIVISI

    @app.route("/fascicoli/<id_fasc>/collaboratori", methods=["GET", "POST"])
    def gestione_collaboratori_fascicolo(id_fasc):
        """Gestione collaboratori di un singolo fascicolo."""
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        u = g.utente_corrente
        puo_gestire = (
            u.ha_permesso("fascicoli.scrivi")
            or get_condivisioni().ha_accesso_fascicolo(u.id, id_fasc, RuoloCondivisione.GESTORE)
        )
        if not puo_gestire:
            flash("Non hai il permesso di gestire i collaboratori di questo fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        gcd = get_condivisioni()
        gu = get_utenti()

        if request.method == "POST":
            azione = request.form.get("azione", "condividi")
            id_dest = request.form.get("id_utente", "").strip()
            utente_dest = gu.get(id_dest)

            if azione == "condividi" and utente_dest:
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                note = request.form.get("note", "").strip()
                data_scadenza = request.form.get("data_scadenza", "").strip()
                tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
                gcd.condividi_fascicolo(
                    id_fascicolo=id_fasc,
                    id_cliente=fasc.id_cliente,
                    id_utente=utente_dest.id,
                    username=utente_dest.username,
                    nome_completo=utente_dest.nome_completo or utente_dest.username,
                    ruolo=RuoloCondivisione(ruolo_str),
                    condiviso_da=u.username,
                    note=note,
                    data_scadenza=data_scadenza,
                    tags=tags,
                )
                flash(f"Fascicolo condiviso con {utente_dest.username}.", "success")
                audit("condivisione.fascicolo.condividi", "fascicolo", id_fasc,
                      dettagli=f"→ {utente_dest.username} [{ruolo_str}]")
            elif azione == "revoca":
                username_dest = utente_dest.username if utente_dest else id_dest
                if gcd.revoca_fascicolo(id_fasc, id_dest):
                    flash(f"Accesso fascicolo revocato per {username_dest}.", "success")
                    audit("condivisione.fascicolo.revoca", "fascicolo", id_fasc,
                          dettagli=f"→ {username_dest}")
                else:
                    flash("Accesso non trovato.", "warning")
            return redirect(url_for("gestione_collaboratori_fascicolo", id_fasc=id_fasc))

        collaboratori = gcd.collaboratori_fascicolo(id_fasc)
        ids_collab = {a.id_utente for a in collaboratori}
        tutti_utenti = [
            ut for ut in gu.tutti(solo_attivi=True)
            if ut.id != u.id and ut.id not in ids_collab
        ]
        return render_template(
            "fascicoli/collaboratori_fascicolo.html",
            fascicolo=fasc,
            collaboratori=collaboratori,
            utenti_disponibili=tutti_utenti,
            ruoli_condivisione=list(RuoloCondivisione),
        )

    # ================================================================ #7 DOCUMENT VERSIONING

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/sostituisci", methods=["POST"])
    def sostituisci_documento(id_fasc, id_doc):
        """Sostituisce un documento mantenendo lo storico delle versioni."""
        gf = get_fascicoli()
        if "file" not in request.files or not request.files["file"].filename:
            flash("Nessun file selezionato.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        file = request.files["file"]
        note = request.form.get("note", "").strip()
        u = g.utente_corrente
        try:
            doc = gf.sostituisci_documento(
                id_fasc=id_fasc,
                id_doc=id_doc,
                nome_file=file.filename,
                contenuto=_encrypt_doc(file.read()),
                caricato_da=u.username if u else "",
                note=note,
            )
            flash(f"Documento '{doc.nome}' aggiornato (versione precedente archiviata).", "success")
            audit("fascicoli.documento.sostituisci", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} → {doc.nome}")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ================================================================ #10 API REST

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["GET"])
    def api_condivisioni_cliente(id_cliente):
        """API REST: collaboratori di una cartella cliente."""
        if not cliente_accessibile(id_cliente):
            return jsonify({"errore": "Accesso negato"}), 403
        gcd = get_condivisioni()
        collaboratori = gcd.collaboratori_di(id_cliente)
        return jsonify({
            "id_cliente": id_cliente,
            "collaboratori": [a.to_dict() for a in collaboratori],
            "n_collaboratori": len(collaboratori),
            "link_attivi": len(gcd.link_attivi_per_cliente(id_cliente)),
            "statistiche": gcd.statistiche(),
        })

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["POST"])
    def api_aggiungi_collaboratore(id_cliente):
        """API REST: aggiunge un collaboratore a una cartella cliente."""
        u = g.utente_corrente
        puo = u and (u.ha_permesso("clienti.scrivi")
                     or get_condivisioni().ha_accesso(u.id, id_cliente, RuoloCondivisione.GESTORE))
        if not puo:
            return jsonify({"errore": "Permesso insufficiente"}), 403

        data = request.get_json(silent=True) or {}
        gu = get_utenti()
        utente_dest = gu.get(data.get("id_utente", ""))
        if not utente_dest:
            return jsonify({"errore": "Utente non trovato"}), 404

        ruolo_str = data.get("ruolo", RuoloCondivisione.LETTURA.value)
        try:
            ruolo = RuoloCondivisione(ruolo_str)
        except ValueError:
            return jsonify({"errore": f"Ruolo '{ruolo_str}' non valido"}), 400

        gcd = get_condivisioni()
        gcd.condividi(
            id_cliente=id_cliente,
            id_utente=utente_dest.id,
            username=utente_dest.username,
            nome_completo=utente_dest.nome_completo or utente_dest.username,
            ruolo=ruolo,
            condiviso_da=u.username,
            note=data.get("note", ""),
            data_scadenza=data.get("data_scadenza", ""),
            tags=data.get("tags", []),
        )
        audit("condivisione.api.condividi", "cliente", id_cliente,
              dettagli=f"→ {utente_dest.username} [{ruolo_str}]")
        return jsonify({"stato": "ok", "username": utente_dest.username, "ruolo": ruolo_str}), 201

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni/<id_utente>", methods=["DELETE"])
    def api_revoca_collaboratore(id_cliente, id_utente):
        """API REST: revoca accesso di un utente a una cartella cliente."""
        u = g.utente_corrente
        puo = u and (u.ha_permesso("clienti.scrivi")
                     or get_condivisioni().ha_accesso(u.id, id_cliente, RuoloCondivisione.GESTORE))
        if not puo:
            return jsonify({"errore": "Permesso insufficiente"}), 403
        rimosso = get_condivisioni().revoca(id_cliente, id_utente)
        if rimosso:
            audit("condivisione.api.revoca", "cliente", id_cliente, dettagli=f"→ {id_utente}")
            return jsonify({"stato": "ok"}), 200
        return jsonify({"errore": "Accesso non trovato"}), 404

    @app.route("/api/v1/condivisioni/statistiche")
    def api_statistiche_condivisioni():
        """API REST: statistiche globali condivisioni."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Permesso insufficiente"}), 403
        return jsonify(get_condivisioni().statistiche())

    @app.route("/api/v1/condivisioni/pulizia-scaduti", methods=["POST"])
    def api_pulizia_scaduti():
        """API REST: revoca automatica accessi scaduti (utile come cron task)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.scrivi"):
            return jsonify({"errore": "Permesso insufficiente"}), 403
        gcd = get_condivisioni()
        n_scaduti = gcd.revoca_scaduti()
        n_link = gcd.pulisci_link_scaduti()
        audit("condivisione.pulizia", "sistema", "",
              dettagli=f"rimossi {n_scaduti} accessi + {n_link} link scaduti")
        return jsonify({"accessi_rimossi": n_scaduti, "link_rimossi": n_link})

    # ================================================================ FASCICOLI

    import io

    def _fascicoli_kwargs(tmp=None):
        return dict(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=tmp or app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )

    @app.route("/fascicoli")
    def lista_fascicoli():
        gf = get_fascicoli()
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        stato_f = request.args.get("stato", "")
        tipo_f = request.args.get("tipo", "")
        stato = StatoFascicolo(stato_f) if stato_f else None
        tipo = TipoFascicolo(tipo_f) if tipo_f else None
        fascicoli = gf.cerca(testo=testo, stato=stato, tipo=tipo) if testo else gf.tutti(stato=stato, tipo=tipo)
        stats = gf.statistiche()
        scadenze = gf.fascicoli_con_scadenze_imminenti(entro_giorni=7)
        return render_template(
            "fascicoli/lista.html",
            fascicoli=fascicoli,
            stats=stats,
            scadenze=scadenze,
            q=testo,
            stato_filtro=stato_f,
            tipo_filtro=tipo_f,
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
        )

    @app.route("/fascicoli/archivio")
    def lista_archivio():
        gf = get_fascicoli()
        testo = request.args.get("q", "").strip()
        fascicoli = gf.cerca(testo=testo, stato=StatoFascicolo.ARCHIVIATO, archiviati=True)
        return render_template("fascicoli/archivio.html", fascicoli=fascicoli, q=testo)

    @app.route("/fascicoli/nuovo", methods=["GET", "POST"])
    def nuovo_fascicolo():
        gc = get_clienti()
        gf = get_fascicoli()
        reginde = ClientReGINde()
        if request.method == "POST":
            f = request.form
            id_cliente = f.get("id_cliente", "")
            nome_cliente = ""
            if id_cliente:
                c = gc.get(id_cliente)
                nome_cliente = c.nome_completo if c else ""
            try:
                fasc = gf.nuovo(
                    titolo=f["titolo"],
                    tipo=TipoFascicolo(f["tipo"]),
                    id_cliente=id_cliente,
                    nome_cliente=nome_cliente,
                    controparte=f.get("controparte", ""),
                    tribunale=f.get("tribunale", ""),
                    numero_rg=f.get("numero_rg", ""),
                    anno_rg=int(f.get("anno_rg") or 0),
                    giudice=f.get("giudice", ""),
                    sezione=f.get("sezione", ""),
                    avvocato_referente=f.get("avvocato_referente", ""),
                    avvocato_dominus=f.get("avvocato_dominus", ""),
                    oggetto=f.get("oggetto", ""),
                    valore_causa=float(f.get("valore_causa") or 0),
                    note=f.get("note", ""),
                )
                flash(f"Fascicolo {fasc.numero} creato.", "success")
                sync_pubblica("crea", "fascicoli", fasc.id)
                return redirect(url_for("dettaglio_fascicolo", id_fasc=fasc.id))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        clienti = gc.tutti(stato=None)
        return render_template(
            "fascicoli/form.html",
            fascicolo=None,
            clienti=clienti,
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
            tribunali=reginde.elenca_uffici(),
            id_cliente_pre=request.args.get("id_cliente", ""),
        )

    @app.route("/fascicoli/<id_fasc>")
    def dettaglio_fascicolo(id_fasc):
        gf = get_fascicoli()
        gc = get_clienti()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        cliente = gc.get(fasc.id_cliente) if fasc.id_cliente else None
        agenda = get_agenda()
        # appuntamenti collegati al procedimento
        apps = []
        if fasc.numero_rg:
            apps = agenda.cerca(testo=fasc.numero_rg)
        track_recente("fascicolo", id_fasc, f"{fasc.numero} — {fasc.titolo}",
                      url_for("dettaglio_fascicolo", id_fasc=id_fasc), "bi-folder2-open")
        return render_template(
            "fascicoli/dettaglio.html",
            fascicolo=fasc,
            cliente=cliente,
            apps=apps,
            tipi_doc=list(TipoDocumento),
            tipi_att=list(TipoAttivita),
            esiti=list(EsitoAttivita),
        )

    @app.route("/fascicoli/<id_fasc>/modifica", methods=["GET", "POST"])
    def modifica_fascicolo(id_fasc):
        gf = get_fascicoli()
        gc = get_clienti()
        reginde = ClientReGINde()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        if request.method == "POST":
            f = request.form
            id_cliente = f.get("id_cliente", fasc.id_cliente)
            nome_cliente = fasc.nome_cliente
            if id_cliente:
                c = gc.get(id_cliente)
                nome_cliente = c.nome_completo if c else nome_cliente
            try:
                gf.aggiorna(id_fasc,
                    titolo=f.get("titolo", fasc.titolo),
                    tipo=TipoFascicolo(f.get("tipo", fasc.tipo.value)),
                    id_cliente=id_cliente,
                    nome_cliente=nome_cliente,
                    controparte=f.get("controparte", ""),
                    tribunale=f.get("tribunale", ""),
                    numero_rg=f.get("numero_rg", ""),
                    anno_rg=int(f.get("anno_rg") or 0),
                    giudice=f.get("giudice", ""),
                    sezione=f.get("sezione", ""),
                    avvocato_referente=f.get("avvocato_referente", ""),
                    avvocato_dominus=f.get("avvocato_dominus", ""),
                    oggetto=f.get("oggetto", ""),
                    valore_causa=float(f.get("valore_causa") or 0),
                    note=f.get("note", ""),
                )
                flash("Fascicolo aggiornato.", "success")
                sync_pubblica("modifica", "fascicoli", id_fasc)
                return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        clienti = gc.tutti(stato=None)
        return render_template(
            "fascicoli/form.html",
            fascicolo=fasc,
            clienti=clienti,
            tipi=list(TipoFascicolo),
            stati=list(StatoFascicolo),
            tribunali=reginde.elenca_uffici(),
            id_cliente_pre="",
        )

    @app.route("/fascicoli/<id_fasc>/stato", methods=["POST"])
    def cambia_stato_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = request.form
        nuovo = f.get("stato")
        try:
            gf.cambia_stato(
                id_fasc,
                StatoFascicolo(nuovo),
                note=f.get("note", ""),
                avvocato=f.get("avvocato", ""),
            )
            flash("Stato aggiornato.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/definisci", methods=["POST"])
    def definisci_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = request.form
        try:
            gf.definisci(
                id_fasc,
                esito_finale=f.get("esito_finale", ""),
                motivo=f.get("motivo", ""),
                note=f.get("note", ""),
                avvocato=f.get("avvocato", ""),
            )
            flash("Fascicolo definito. Pronto per l'archiviazione.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/archivia", methods=["POST"])
    def archivia_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = request.form
        try:
            gf.archivia(
                id_fasc,
                crea_zip=f.get("crea_zip", "1") == "1",
                avvocato=f.get("avvocato", ""),
            )
            flash("Fascicolo archiviato con successo.", "success")
            return redirect(url_for("lista_archivio"))
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/ripristina", methods=["POST"])
    def ripristina_fascicolo(id_fasc):
        gf = get_fascicoli()
        try:
            gf.ripristina_da_archivio(id_fasc, avvocato=request.form.get("avvocato", ""))
            flash("Fascicolo ripristinato dall'archivio.", "success")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
            return redirect(url_for("lista_archivio"))

    @app.route("/fascicoli/<id_fasc>/elimina", methods=["POST"])
    def elimina_fascicolo(id_fasc):
        gf = get_fascicoli()
        try:
            gf.elimina(id_fasc)
            flash("Fascicolo eliminato.", "success")
            sync_pubblica("elimina", "fascicoli", id_fasc)
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_fascicoli"))

    # ---- Documenti

    @app.route("/fascicoli/<id_fasc>/documenti/carica", methods=["POST"])
    def carica_documento(id_fasc):
        gf = get_fascicoli()
        if "file" not in request.files:
            flash("Nessun file selezionato.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        file = request.files["file"]
        if not file.filename:
            flash("Nome file non valido.", "warning")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))
        f = request.form
        u = g.utente_corrente
        try:
            contenuto = _encrypt_doc(file.read())
            gf.aggiungi_documento(
                id_fasc,
                nome_file=file.filename,
                tipo=TipoDocumento(f.get("tipo_doc", "ALTRO")),
                contenuto=contenuto,
                note=f.get("note", ""),
                data_documento=f.get("data_documento", ""),
                firmato=f.get("firmato") == "1",
                caricato_da=u.username if u else "",
            )
            flash(f"Documento '{file.filename}' caricato.", "success")
            audit("fascicoli.documento.carica", "fascicolo", id_fasc,
                  dettagli=f"file: {file.filename}")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/scarica")
    def scarica_documento(id_fasc, id_doc):
        gf = get_fascicoli()
        try:
            percorso = gf.percorso_documento(id_fasc, id_doc)
            fasc = gf.get(id_fasc)
            doc = next(d for d in fasc.documenti if d.id == id_doc)
            data = _decrypt_doc(percorso.read_bytes())
            audit("fascicoli.documento.scarica", "fascicolo", id_fasc,
                  dettagli=f"doc {id_doc} — {doc.nome}")
            return send_file(io.BytesIO(data), as_attachment=True, download_name=doc.nome)
        except (KeyError, StopIteration, ValueError) as e:
            flash(str(e), "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/elimina", methods=["POST"])
    def elimina_documento(id_fasc, id_doc):
        gf = get_fascicoli()
        try:
            gf.rimuovi_documento(id_fasc, id_doc)
            flash("Documento eliminato.", "success")
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ---- Attività processuali

    @app.route("/fascicoli/<id_fasc>/attivita/aggiungi", methods=["POST"])
    def aggiungi_attivita(id_fasc):
        gf = get_fascicoli()
        f = request.form
        try:
            gf.aggiungi_attivita(
                id_fasc,
                tipo=TipoAttivita(f["tipo"]),
                data=f["data"],
                titolo=f["titolo"],
                descrizione=f.get("descrizione", ""),
                luogo=f.get("luogo", ""),
                esito=EsitoAttivita(f.get("esito", "IN_ATTESA")),
                note=f.get("note", ""),
                avvocato=f.get("avvocato", ""),
                id_appuntamento=f.get("id_appuntamento", ""),
            )
            flash("Attività aggiunta.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    @app.route("/fascicoli/<id_fasc>/attivita/<id_att>/esito", methods=["POST"])
    def aggiorna_esito_attivita(id_fasc, id_att):
        gf = get_fascicoli()
        try:
            gf.aggiorna_attivita(
                id_fasc, id_att,
                esito=EsitoAttivita(request.form["esito"]),
                note=request.form.get("note", ""),
            )
            flash("Esito aggiornato.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

    # ---- Download archivio ZIP

    @app.route("/fascicoli/<id_fasc>/archivio/scarica")
    def scarica_archivio(id_fasc):
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc or not fasc.archivio or not fasc.archivio.percorso_zip:
            flash("Archivio ZIP non disponibile.", "warning")
            return redirect(url_for("lista_archivio"))
        p = Path(fasc.archivio.percorso_zip)
        if not p.exists():
            flash("File archivio non trovato su disco.", "danger")
            return redirect(url_for("lista_archivio"))
        return send_file(p, as_attachment=True,
                         download_name=f"fascicolo_{fasc.numero.replace('/','_')}.zip")

    # ---- API fascicoli

    @app.route("/api/fascicoli")
    def api_fascicoli():
        gf = get_fascicoli()
        q = request.args.get("q", "")
        archiviati = request.args.get("archiviati", "0") == "1"
        fascicoli = gf.cerca(testo=q, archiviati=archiviati)
        return jsonify([f.to_dict() for f in fascicoli])

    @app.route("/api/fascicoli/<id_fasc>")
    def api_fascicolo(id_fasc):
        gf = get_fascicoli()
        f = gf.get(id_fasc)
        if not f:
            return jsonify({"errore": "Non trovato"}), 404
        return jsonify(f.to_dict())

    @app.route("/api/fascicoli/statistiche")
    def api_fascicoli_statistiche():
        return jsonify(get_fascicoli().statistiche())

    # ================================================================ MESSAGGI

    @app.route("/messaggi")
    def lista_messaggi():
        gm = get_messaggi()
        canale = request.args.get("canale", "")
        stato = request.args.get("stato", "")
        q = request.args.get("q", "")
        messaggi = gm.tutti(
            canale=CanaleMsggio(canale) if canale else None,
            stato=StatoMessaggio(stato) if stato else None,
        )
        if q:
            ql = q.lower()
            messaggi = [
                m for m in messaggi
                if ql in (m.email_destinatario or m.telefono_destinatario or "").lower()
                or ql in m.nome_destinatario.lower()
                or ql in m.oggetto.lower()
                or ql in m.corpo.lower()
            ]
        return render_template(
            "messaggi/lista.html",
            messaggi=messaggi,
            canali=list(CanaleMsggio),
            stati=list(StatoMessaggio),
            canale=canale,
            stato=stato,
            q=q,
            stats=gm.statistiche(),
        )

    @app.route("/messaggi/nuovo", methods=["GET", "POST"])
    def nuovo_messaggio():
        gm = get_messaggi()
        gc = get_clienti()
        clienti = gc.tutti()
        if request.method == "POST":
            f = request.form
            canale_str = f["canale"]
            canale = CanaleMsggio(canale_str)
            destinatario = f["destinatario"].strip()
            testo = f.get("testo", "").strip()
            oggetto = f.get("oggetto", "").strip()
            id_cliente = f.get("id_cliente", "") or ""
            try:
                if canale == CanaleMsggio.EMAIL:
                    gm.invia_email(
                        destinatario=destinatario,
                        oggetto=oggetto,
                        corpo_testo=testo,
                        id_cliente=id_cliente,
                    )
                elif canale == CanaleMsggio.SMS:
                    gm.invia_sms(
                        telefono=destinatario,
                        testo=testo,
                        id_cliente=id_cliente,
                    )
                else:
                    gm.invia_whatsapp(
                        telefono=destinatario,
                        testo=testo,
                        id_cliente=id_cliente,
                    )
                flash("Messaggio inviato.", "success")
                return redirect(url_for("lista_messaggi"))
            except Exception as e:
                flash(str(e), "danger")
        return render_template(
            "messaggi/form.html",
            clienti=clienti,
            canali=list(CanaleMsggio),
            tipi_automazione=list(TipoAutomazione),
        )

    @app.route("/messaggi/<id_msg>")
    def dettaglio_messaggio(id_msg):
        gm = get_messaggi()
        msg = gm.get(id_msg)
        if not msg:
            flash("Messaggio non trovato.", "warning")
            return redirect(url_for("lista_messaggi"))
        return render_template("messaggi/dettaglio.html", msg=msg)

    @app.route("/messaggi/<id_msg>/elimina", methods=["POST"])
    def elimina_messaggio(id_msg):
        gm = get_messaggi()
        try:
            gm.elimina(id_msg)
            flash("Messaggio eliminato.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_messaggi"))

    @app.route("/api/messaggi/statistiche")
    def api_messaggi_statistiche():
        return jsonify(get_messaggi().statistiche())

    # ================================================================ BACKUP

    @app.route("/backup")
    def lista_backup():
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
        gb = get_backup()
        tipo = TipoBackup(request.form.get("tipo", "COMPLETO"))
        nota = request.form.get("nota", "")
        componenti_raw = request.form.getlist("componenti")
        componenti = componenti_raw if componenti_raw else None
        try:
            record = gb.esegui_backup(tipo=tipo, componenti=componenti, nota=nota)
            if record.stato == StatoBackup.OK:
                flash(f"Backup completato: {record.num_file} file, "
                      f"{round(record.dimensione_bytes/1024/1024, 2)} MB.", "success")
            else:
                flash(f"Backup fallito: {record.errore}", "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/verifica", methods=["POST"])
    def verifica_backup(id_bk):
        gb = get_backup()
        try:
            ris = gb.verifica_integrita(id_bk)
            if ris["ok"]:
                flash("Integrità verificata: backup integro.", "success")
            else:
                flash("ATTENZIONE: integrità compressa! Il file potrebbe essere corrotto.", "danger")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/elimina", methods=["POST"])
    def elimina_backup(id_bk):
        gb = get_backup()
        try:
            gb.elimina(id_bk)
            flash("Backup eliminato.", "success")
        except Exception as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_backup"))

    @app.route("/backup/<id_bk>/scarica")
    def scarica_backup(id_bk):
        gb = get_backup()
        record = gb.get(id_bk)
        if not record:
            flash("Backup non trovato.", "warning")
            return redirect(url_for("lista_backup"))
        p = Path(record.percorso_file)
        if not p.exists():
            flash("File backup non trovato su disco.", "danger")
            return redirect(url_for("lista_backup"))
        return send_file(p, as_attachment=True, download_name=p.name)

    @app.route("/backup/<id_bk>/ripristina", methods=["GET", "POST"])
    def ripristina_backup(id_bk):
        gb = get_backup()
        record = gb.get(id_bk)
        if not record:
            flash("Backup non trovato.", "warning")
            return redirect(url_for("lista_backup"))
        if request.method == "POST":
            dest = request.form.get("destinazione", "./ripristino").strip()
            componenti_raw = request.form.getlist("componenti")
            componenti = componenti_raw if componenti_raw else None
            sovrascrivi = request.form.get("sovrascrivi") == "1"
            password = request.form.get("password", "")
            try:
                ris = gb.ripristina(
                    id_bk, dest,
                    componenti=componenti,
                    password=password,
                    sovrascrivi=sovrascrivi,
                )
                flash(
                    f"Ripristino completato: {ris['file_ripristinati']} file ripristinati, "
                    f"{ris['file_saltati']} saltati.",
                    "success",
                )
                return redirect(url_for("lista_backup"))
            except Exception as e:
                flash(str(e), "danger")
        return render_template("backup/ripristina.html", record=record)

    @app.route("/api/backup/statistiche")
    def api_backup_statistiche():
        return jsonify(get_backup().statistiche())

    # ================================================================ HEALTH CHECK

    @app.route("/api/health")
    def api_health():
        """Endpoint di salute per monitoring — non richiede autenticazione."""
        stato = {"ok": True, "timestamp": datetime.now().isoformat(), "moduli": {}}
        try:
            gc = get_clienti()
            stato["moduli"]["clienti"] = {"ok": True, "totale": gc.statistiche()["totale"]}
        except Exception as e:
            stato["moduli"]["clienti"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            gf = get_fascicoli()
            stato["moduli"]["fascicoli"] = {"ok": True, "attivi": gf.statistiche()["attivi"]}
        except Exception as e:
            stato["moduli"]["fascicoli"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            ga = get_agenda()
            stato["moduli"]["agenda"] = {"ok": True, "totale": ga.statistiche()["totale"]}
        except Exception as e:
            stato["moduli"]["agenda"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            gs = get_scadenziario()
            stato["moduli"]["scadenziario"] = {"ok": True, "aperte": gs.statistiche()["aperte"]}
        except Exception as e:
            stato["moduli"]["scadenziario"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        codice = 200 if stato["ok"] else 503
        return jsonify(stato), codice

    # ================================================================ CSV EXPORT

    def _csv_response(righe: list[dict], nome_file: str) -> Response:
        """Genera una risposta CSV da una lista di dizionari."""
        if not righe:
            output = io.StringIO()
            output.write("# Nessun dato da esportare\n")
            csv_data = output.getvalue()
        else:
            output = io.StringIO()
            writer = csv.DictWriter(
                output, fieldnames=righe[0].keys(),
                extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(righe)
            csv_data = output.getvalue()
        return Response(
            csv_data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{nome_file}"'},
        )

    @app.route("/clienti/export.csv")
    def export_clienti_csv():
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "")
        tipo = TipoCliente(tipo_f) if tipo_f else None
        stato = StatoCliente(stato_f) if stato_f else None
        clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)
        righe = []
        for c in clienti:
            d = c.to_dict()
            ind = d.get("indirizzo") or {}
            righe.append({
                "id": d["id"],
                "cognome": d.get("cognome", ""),
                "nome": d.get("nome", ""),
                "ragione_sociale": d.get("ragione_sociale", ""),
                "tipo": d.get("tipo", ""),
                "stato": d.get("stato", ""),
                "codice_fiscale": d.get("codice_fiscale", ""),
                "partita_iva": d.get("partita_iva", ""),
                "email": d.get("email", ""),
                "telefono": d.get("telefono", ""),
                "citta": ind.get("citta", "") if isinstance(ind, dict) else "",
            })
        audit("clienti.export_csv")
        return _csv_response(righe, f"clienti_{date.today().isoformat()}.csv")

    @app.route("/fascicoli/export.csv")
    def export_fascicoli_csv():
        gf = get_fascicoli()
        testo = request.args.get("q", "").strip()
        stato_f = request.args.get("stato", "")
        tipo_f = request.args.get("tipo", "")
        stato = StatoFascicolo(stato_f) if stato_f else None
        tipo = TipoFascicolo(tipo_f) if tipo_f else None
        fascicoli = gf.cerca(testo=testo, stato=stato, tipo=tipo) if testo else gf.tutti(stato=stato, tipo=tipo)
        righe = []
        for f in fascicoli:
            d = f.to_dict()
            righe.append({
                "numero": d.get("numero", ""),
                "titolo": d.get("titolo", ""),
                "tipo": d.get("tipo", ""),
                "stato": d.get("stato", ""),
                "tribunale": d.get("tribunale", ""),
                "numero_rg": d.get("numero_rg", ""),
                "anno_rg": d.get("anno_rg", ""),
                "nome_cliente": d.get("nome_cliente", ""),
                "controparte": d.get("controparte", ""),
                "avvocato_referente": d.get("avvocato_referente", ""),
                "data_apertura": d.get("data_apertura", ""),
                "data_chiusura": d.get("data_chiusura", ""),
            })
        audit("fascicoli.export_csv")
        return _csv_response(righe, f"fascicoli_{date.today().isoformat()}.csv")

    @app.route("/scadenziario/export.csv")
    def export_scadenziario_csv():
        gs = get_scadenziario()
        filtro_tipo = request.args.get("tipo", "")
        filtro_priorita = request.args.get("priorita", "")
        id_fascicolo = request.args.get("id_fascicolo", "")
        solo_aperte = request.args.get("stato", "aperte") != "tutte"
        scadenze = gs.tutte(
            tipo=TipoTermine(filtro_tipo) if filtro_tipo else None,
            priorita=PrioritaTermine(filtro_priorita) if filtro_priorita else None,
            id_fascicolo=id_fascicolo,
            solo_aperte=solo_aperte,
        )
        righe = []
        for s in scadenze:
            d = s.to_dict() if hasattr(s, "to_dict") else vars(s)
            righe.append({
                "titolo": d.get("titolo", ""),
                "tipo": d.get("tipo", ""),
                "data_scadenza": d.get("data_scadenza", ""),
                "priorita": d.get("priorita", ""),
                "stato": d.get("stato", ""),
                "perentorio": d.get("perentorio", ""),
                "id_fascicolo": d.get("id_fascicolo", ""),
                "giorni_preavviso": str(d.get("giorni_preavviso", "")),
                "completata_il": d.get("completata_il", ""),
                "note": d.get("note", ""),
            })
        audit("scadenziario.export_csv")
        return _csv_response(righe, f"scadenziario_{date.today().isoformat()}.csv")

    # ================================================================ SEARCH

    @app.route("/api/cerca")
    def api_cerca():
        """Ricerca globale full-text — usata dall'autocomplete topbar."""
        q = request.args.get("q", "").strip()
        tipi_raw = request.args.getlist("tipo")
        limit = min(int(request.args.get("limit", 20)), 50)
        if not q:
            return jsonify([])
        indice = get_indice()
        risultati = indice.cerca(q, tipi=tipi_raw or None, limit=limit)
        return jsonify([
            {
                "tipo": r.tipo,
                "id": r.id,
                "titolo": r.titolo,
                "sottotitolo": r.sottotitolo,
                "url": r.url,
                "icona": r.icona,
                "snippet": r.snippet,
            }
            for r in risultati
        ])

    @app.route("/cerca")
    def cerca():
        """Pagina di ricerca completa."""
        q = request.args.get("q", "").strip()
        risultati = {}
        if q:
            indice = get_indice()
            risultati = indice.cerca_globale(q, limit=30)
        return render_template("cerca.html", q=q, risultati=risultati)

    @app.route("/api/ricerca/ricostruisci", methods=["POST"])
    def api_ricerca_ricostruisci():
        """Ricostruisce l'indice di ricerca (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        indice = get_indice()
        indice.ricostruisci(
            clienti=get_clienti().tutti(),
            fascicoli=get_fascicoli().tutti(),
            appuntamenti=get_agenda().tutti(),
            scadenze=get_scadenziario().tutte(solo_aperte=False),
        )
        audit("ricerca.ricostruisci_indice")
        return jsonify({"ok": True, "statistiche": indice.statistiche()})

    # ================================================================ PDF EXPORT

    @app.route("/fascicoli/<id_fasc>/pdf")
    def fascicolo_pdf_export(id_fasc):
        gf = get_fascicoli()
        fasc = gf.get(id_fasc)
        if not fasc:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))
        studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out = tmp.name
        fascicolo_pdf(fasc.to_dict(), out, studio_nome=studio_nome)
        nome_file = f"fascicolo_{fasc.numero or id_fasc}.pdf".replace("/", "-").replace(" ", "_")
        audit("fascicoli.esporta_pdf", risorsa_tipo="fascicolo", risorsa_id=id_fasc)
        return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")

    @app.route("/scadenziario/pdf")
    def scadenziario_pdf_export():
        gs = get_scadenziario()
        stato_raw = request.args.get("stato", "")
        solo_aperte = stato_raw != "tutte"
        lista = gs.tutte(solo_aperte=solo_aperte)
        studio_nome = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        mese_label = date.today().strftime("%B %Y").capitalize()
        titolo_pdf = f"Scadenziario — {mese_label}"
        dati = [
            {
                "scadenza": s.data_scadenza,
                "titolo": s.titolo,
                "tipo": s.tipo.value if hasattr(s.tipo, "value") else str(s.tipo),
                "fascicolo": s.id_fascicolo or "",
                "priorita": s.priorita.value if hasattr(s.priorita, "value") else str(s.priorita),
                "perentorio": s.perentorio,
            }
            for s in lista
        ]
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out = tmp.name
        scadenze_pdf(dati, out, titolo=titolo_pdf, studio_nome=studio_nome)
        nome_file = f"scadenziario_{date.today().isoformat()}.pdf"
        audit("scadenziario.esporta_pdf")
        return send_file(out, as_attachment=True, download_name=nome_file, mimetype="application/pdf")

    # ================================================================ SINCRONIZZAZIONE REAL-TIME

    @app.route("/api/eventi")
    def api_eventi():
        """
        SSE endpoint per notifiche in tempo reale agli operatori connessi.
        Ogni client connesso riceve gli aggiornamenti degli altri operatori.
        """
        if not g.utente_corrente:
            return jsonify({"errore": "Non autenticato"}), 401

        client_id, q = _sync.subscribe()

        def genera():
            yield from _sync.sse_stream(client_id, q)

        return Response(
            genera(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.route("/api/sync/stato")
    def api_sync_stato():
        """Stato sincronizzazione: operatori connessi e versioni file."""
        return jsonify({
            "connessi": _sync.n_connessi,
            "versioni": {
                "clienti": _sync.versione_file(app.config["CLIENTI_DB"]),
                "fascicoli": _sync.versione_file(app.config["FASCICOLI_DB"]),
                "scadenze": _sync.versione_file(app.config["SCADENZIARIO_DB"]),
                "agenda": _sync.versione_file(app.config["AGENDA_DB"]),
                "messaggi": _sync.versione_file(app.config["MESSAGGI_DB"]),
            },
        })

    @app.route("/api/sync/broadcast", methods=["POST"])
    def api_sync_broadcast():
        """Invia un messaggio informativo a tutti gli operatori (solo admin)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        msg = request.json.get("messaggio", "") if request.is_json else request.form.get("messaggio", "")
        if not msg:
            return jsonify({"errore": "Messaggio obbligatorio"}), 400
        n = _sync.pubblica_broadcast(msg, utente=u.username)
        audit("sync.broadcast", dettagli=msg)
        return jsonify({"ok": True, "raggiunti": n})

    # ================================================================ ADMIN DATABASE

    @app.route("/admin/database")
    def admin_database():
        """Dashboard gestione database — solo amministratori."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            flash("Accesso riservato agli amministratori.", "danger")
            return redirect(url_for("dashboard"))
        db = get_database()
        statistiche = db.statistiche()
        uso = db.analisi_uso()
        sqlite_info = db.statistiche_sqlite(
            os.path.join(app.config.get("BACKUP_DIR", "./backup"), "studio_legale.db")
        )
        return render_template(
            "admin/database.html",
            statistiche=statistiche,
            uso=uso,
            sqlite_info=sqlite_info,
        )

    @app.route("/admin/database/verifica")
    def admin_database_verifica():
        """Verifica integrità referenziale di tutti i moduli."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        db = get_database()
        problemi = db.verifica_integrita()
        audit("database.verifica_integrita")
        return jsonify({
            "ok": True,
            "n_problemi": len(problemi),
            "problemi": [
                {
                    "livello": p.severita,
                    "modulo": p.modulo,
                    "tipo": p.tipo,
                    "descrizione": p.messaggio,
                    "id_risorsa": p.id_record,
                    "campo": p.campo,
                    "suggerimento": p.suggerimento,
                }
                for p in problemi
            ],
        })

    @app.route("/admin/database/ottimizza", methods=["POST"])
    def admin_database_ottimizza():
        """Esegue ottimizzazione su tutti i moduli (JSON compaction + SQLite VACUUM)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        db = get_database()
        risultati = db.ottimizza()
        audit("database.ottimizza")
        return jsonify({
            "ok": True,
            "risultati": [
                {
                    "modulo": r.modulo,
                    "operazione": r.operazione,
                    "riuscita": r.riuscita,
                    "dettagli": r.dettagli,
                    "ms": r.ms,
                }
                for r in risultati
            ],
        })

    @app.route("/admin/database/migra", methods=["POST"])
    def admin_database_migra():
        """Migra tutti i dati JSON verso un singolo database SQLite."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        percorso_db = os.path.join(
            app.config.get("BACKUP_DIR", "./backup"),
            f"studio_legale_{date.today().isoformat()}.db",
        )
        db = get_database()
        risultato = db.migra_verso_sqlite(percorso_db)
        audit("database.migra_sqlite", risorsa_tipo="db", risorsa_id=percorso_db)
        totale = sum(risultato.record_migrati.values()) if risultato.record_migrati else 0
        return jsonify({
            "ok": risultato.riuscita,
            "percorso_db": risultato.percorso_db,
            "record_migrati": totale,
            "per_modulo": risultato.record_migrati,
            "errori": risultato.errori,
            "durata_secondi": round(risultato.ms / 1000, 3),
        })

    # ================================================================ REGISTRO TRATTAMENTI (GDPR Art. 30)

    @app.route("/privacy/registro")
    def registro_trattamenti():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        gt = get_trattamenti()
        return render_template("privacy/registro.html", trattamenti=gt.tutti())

    @app.route("/privacy/registro/nuovo", methods=["GET", "POST"])
    def nuovo_trattamento():
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        if request.method == "POST":
            f = request.form
            gt = get_trattamenti()
            gt.nuovo(
                nome=f.get("nome", ""),
                finalita=f.get("finalita", ""),
                categoria_dati=f.get("categoria_dati", ""),
                base_giuridica=f.get("base_giuridica", ""),
                soggetti_interessati=f.get("soggetti_interessati", ""),
                destinatari=f.get("destinatari", ""),
                trasferimento_extra_ue=f.get("trasferimento_extra_ue") == "1",
                paese_destinazione=f.get("paese_destinazione", ""),
                termine_conservazione=f.get("termine_conservazione", ""),
                misure_sicurezza=f.get("misure_sicurezza", ""),
                responsabile=f.get("responsabile", ""),
                note=f.get("note", ""),
            )
            audit("privacy.registro.nuovo")
            flash("Trattamento aggiunto al registro.", "success")
            return redirect(url_for("registro_trattamenti"))
        return render_template("privacy/registro.html",
                               trattamenti=get_trattamenti().tutti(), form_nuovo=True)

    @app.route("/privacy/registro/<id_t>/elimina", methods=["POST"])
    def elimina_trattamento(id_t):
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            abort(403)
        try:
            get_trattamenti().elimina(id_t)
            audit("privacy.registro.elimina", risorsa_id=id_t)
            flash("Trattamento eliminato.", "success")
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("registro_trattamenti"))

    # ================================================================ GDPR & PRIVACY

    @app.route("/clienti/<id_cliente>/consenso", methods=["POST"])
    def aggiorna_consenso(id_cliente):
        """Registra/aggiorna il consenso al trattamento dati del cliente."""
        if not g.utente_corrente or not g.utente_corrente.ha_permesso("clienti.scrivi"):
            abort(403)
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            abort(404)
        f = request.form
        consenso = f.get("consenso_trattamento") == "1"
        gc.aggiorna(id_cliente,
                    consenso_trattamento=consenso,
                    data_consenso=f.get("data_consenso", date.today().isoformat()),
                    modalita_consenso=f.get("modalita_consenso", ""))
        audit("clienti.consenso", "cliente", id_cliente,
              dettagli=f"{'concesso' if consenso else 'revocato'} via {f.get('modalita_consenso','')}")
        flash("Consenso aggiornato.", "success")
        return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    @app.route("/clienti/<id_cliente>/informativa.pdf")
    def informativa_privacy_pdf(id_cliente):
        """Genera PDF dell'informativa privacy per il cliente (GDPR Art. 13)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("clienti.leggi"):
            abort(403)
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            abort(404)
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib import colors
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2.5*cm, rightMargin=2.5*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("title", parent=styles["Title"],
                                     fontSize=14, spaceAfter=6)
        h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceAfter=4)
        body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9,
                              spaceAfter=6, leading=14)
        studio = os.getenv("PCT_STUDIO_NOME", "Studio Legale")
        elementi = [
            Paragraph("INFORMATIVA SUL TRATTAMENTO DEI DATI PERSONALI", title_style),
            Paragraph("ai sensi degli artt. 13-14 del Regolamento UE 2016/679 (GDPR)", body),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c")),
            Spacer(1, 0.4*cm),
            Paragraph("1. Titolare del trattamento", h2),
            Paragraph(f"{studio} — i recapiti sono disponibili presso lo studio.", body),
            Paragraph("2. Finalità e base giuridica del trattamento", h2),
            Paragraph("I Suoi dati personali sono trattati per l'erogazione di servizi legali, "
                      "la gestione dei fascicoli e procedimenti giudiziari e stragiudiziali, "
                      "nonché per adempiere ad obblighi legali e contabili. "
                      "La base giuridica è l'esecuzione di un contratto (art. 6.1.b GDPR) "
                      "e l'adempimento di obblighi legali (art. 6.1.c GDPR).", body),
            Paragraph("3. Categorie di dati trattati", h2),
            Paragraph("Dati anagrafici e di contatto, codice fiscale, dati relativi a procedimenti "
                      "giudiziari, dati economici e patrimoniali strettamente necessari "
                      "all'esercizio dell'attività professionale.", body),
            Paragraph("4. Destinatari dei dati", h2),
            Paragraph("I Suoi dati possono essere comunicati ad autorità giudiziarie e "
                      "amministrative, alla controparte e ai suoi difensori, nonché "
                      "a consulenti tecnici e periti nell'ambito dei procedimenti. "
                      "Non vengono trasferiti a Paesi terzi.", body),
            Paragraph("5. Periodo di conservazione", h2),
            Paragraph("I dati saranno conservati per l'intera durata del rapporto professionale "
                      "e per i successivi 10 anni, ai sensi dell'art. 2220 c.c. e delle norme "
                      "deontologiche forensi.", body),
            Paragraph("6. Diritti dell'interessato", h2),
            Paragraph("Ha diritto di accedere ai Suoi dati (art. 15), rettificarli (art. 16), "
                      "cancellarli (art. 17), limitarne il trattamento (art. 18), "
                      "riceverne copia portabile (art. 20) e opporsi al trattamento (art. 21). "
                      "Può esercitare tali diritti contattando direttamente lo studio.", body),
            Paragraph("7. Diritto di reclamo", h2),
            Paragraph("Ha il diritto di proporre reclamo al Garante per la protezione dei "
                      "dati personali (www.garanteprivacy.it).", body),
            Spacer(1, 1*cm),
            HRFlowable(width="100%", thickness=0.5, color=colors.grey),
            Spacer(1, 0.3*cm),
            Paragraph(f"Informativa generata il {date.today().strftime('%d/%m/%Y')} "
                      f"per: <b>{c.nome_completo}</b>", body),
        ]
        doc.build(elementi)
        buf.seek(0)
        audit("clienti.informativa_pdf", "cliente", id_cliente,
              dettagli=f"PDF Art.13 — {c.nome_completo}")
        nome = f"informativa_{c.nome_completo.replace(' ', '_').lower()}.pdf"
        resp = send_file(buf, as_attachment=True, download_name=nome,
                         mimetype="application/pdf")
        return resp

    @app.route("/clienti/<id_cliente>/porta-via")
    def gdpr_portabilita(id_cliente):
        """Esporta dati personali del cliente in JSON strutturato (GDPR Art. 20)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("clienti.leggi"):
            abort(403)
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            abort(404)
        gf = get_fascicoli()
        fascicoli_cliente = [f for f in gf.tutti() if f.id_cliente == id_cliente]
        export = {
            "metadati": {
                "standard": "GDPR Art. 20 — Portabilità dei dati personali",
                "regolamento": "Reg. UE 2016/679",
                "data_estrazione": datetime.now().isoformat(),
                "estratto_da": u.username,
                "versione": "1.0",
            },
            "anagrafica": {
                "tipo": c.tipo.value,
                "nome": c.nome,
                "cognome": c.cognome,
                "ragione_sociale": c.ragione_sociale,
                "codice_fiscale": c.codice_fiscale,
                "partita_iva": c.partita_iva,
                "data_nascita": c.data_nascita,
                "luogo_nascita": c.luogo_nascita,
                "provincia_nascita": c.provincia_nascita,
                "nazionalita": c.nazionalita,
                "sesso": c.sesso,
                "forma_giuridica": c.forma_giuridica,
                "rappresentante_legale": c.rappresentante_legale,
            },
            "recapiti": {
                "telefono": c.recapiti.telefono,
                "cellulare": c.recapiti.cellulare,
                "email": c.recapiti.email,
                "pec": c.recapiti.pec,
                "fax": c.recapiti.fax,
            },
            "indirizzi": {
                "residenza": str(c.indirizzo_residenza) or None,
                "domicilio": str(c.indirizzo_domicilio) or None,
                "sede_legale": str(c.indirizzo_sede_legale) or None,
            },
            "dati_studio": {
                "avvocato_referente": c.avvocato_referente,
                "data_prima_acquisizione": c.data_prima_acquisizione,
                "stato": c.stato.value,
                "provenienza": c.provenienza,
                "note": c.note,
            },
            "procedimenti": [
                {
                    "numero_rg": p.numero_rg,
                    "anno": p.anno,
                    "tribunale": p.tribunale,
                    "descrizione": p.descrizione,
                    "data_apertura": p.data_apertura,
                    "data_chiusura": p.data_chiusura,
                    "attivo": p.attivo,
                }
                for p in c.procedimenti
            ],
            "fascicoli": [
                {
                    "numero": f.numero,
                    "titolo": f.titolo,
                    "tipo": f.tipo.value,
                    "stato": f.stato.value,
                    "data_apertura": f.data_apertura,
                    "n_documenti": len(f.documenti),
                }
                for f in fascicoli_cliente
            ],
        }
        audit("gdpr.portabilita", "cliente", id_cliente,
              dettagli=f"Export Art.20 — {c.nome_completo}")
        nome = f"dati_{c.nome_completo.replace(' ', '_').lower()}_{date.today().isoformat()}.json"
        resp = Response(
            json.dumps(export, ensure_ascii=False, indent=2),
            mimetype="application/json",
        )
        resp.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
        return resp

    @app.route("/audit/esporta.csv")
    def esporta_audit_csv():
        """Esporta l'audit log come file CSV (richiede permesso audit.leggi)."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("audit.leggi"):
            abort(403)
        gu = get_utenti()
        csv_data = gu.esporta_audit_csv(
            id_utente=request.args.get("id_utente", ""),
            azione=request.args.get("azione", ""),
            da=request.args.get("da") or None,
            a=request.args.get("a") or None,
        )
        audit("audit.esporta_csv")
        resp = Response(csv_data, mimetype="text/csv; charset=utf-8")
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="audit_{date.today().isoformat()}.csv"'
        )
        return resp

    @app.route("/admin/database/export")
    def admin_database_export():
        """Esporta ZIP completo di tutti i dati."""
        u = g.utente_corrente
        if not u or not u.ha_permesso("utenti.leggi"):
            flash("Accesso riservato agli amministratori.", "danger")
            return redirect(url_for("dashboard"))
        import tempfile
        output_dir = tempfile.mkdtemp(prefix="hacs_export_")
        db = get_database()
        zip_path = db.esporta_tutto(output_dir)
        nome_file = f"export_{date.today().isoformat()}.zip"
        audit("database.esporta_zip")
        return send_file(zip_path, as_attachment=True, download_name=nome_file, mimetype="application/zip")

    return app
