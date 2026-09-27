"""Percorso di accesso (password e secondo fattore) condiviso da HTML e JSON.

Unica fonte della logica di accesso: le route storiche ``/login`` e
``/login/2fa`` (risposte HTML: redirect, flash, pagine con errore) e le API
pubbliche ``/api/v1/pubblico/accesso/*`` usate dalla pagina React chiamano le
stesse funzioni e ricevono un esito strutturato (:class:`EsitoAccesso`), che
ciascun ingresso traduce nella propria risposta.

Qui vivono, identici a prima: blocco anti brute-force (``login_guard``),
eventi di audit, chiavi di sessione (``totp_pending_*``), validazione di
``next`` con ``is_safe_internal_path``, scelta dello studio in ambiente
multi-studio e messaggi generici che non rivelano se un utente esiste.

Base normativa: misure di sicurezza del trattamento (GDPR art. 32; D.Lgs.
196/2003) per l'accesso ai dati riservati dello studio.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from flask import Flask, flash, request, session, url_for

from core.security.login_guard import get_login_guard
from pct.auth import GestioneUtenti, RuoloUtente, verifica_totp
from web.services.app_v2_routing import is_safe_internal_path

TOTP_TENTATIVI_MASSIMI = 5

# Tipi di esito.
ACCESSO = "accesso"
PASSWORD_DA_CAMBIARE = "password_da_cambiare"
SECONDO_FATTORE = "2fa_richiesta"
GIA_AUTENTICATO = "gia_autenticato"
ERRORE = "errore"
BLOCCATO = "bloccato"
VERIFICA_ANNULLATA = "verifica_annullata"
ESITI_RIUSCITI = frozenset({ACCESSO, PASSWORD_DA_CAMBIARE, SECONDO_FATTORE, GIA_AUTENTICATO})

MESSAGGIO_CREDENZIALI = "Credenziali non valide o utente disabilitato."
MESSAGGIO_STUDIO_NON_TROVATO = "Studio non trovato."
MESSAGGIO_STUDI_AMBIGUI = "Sono stati trovati più studi per queste credenziali. Indica lo studio nel campo dedicato."
MESSAGGIO_ACCOUNT_SENZA_STUDIO = (
    "Questo account non e' associato a uno studio. "
    "Usa l'amministratore dello studio corretto oppure accedi come SUPERADMIN."
)
MESSAGGIO_PASSWORD_TEMPORANEA = "Password iniziale temporanea rilevata. Prima di usare il gestionale devi sostituirla."
MESSAGGIO_CODICE_NON_VALIDO = "Codice non valido. Riprova."
MESSAGGIO_TROPPI_CODICI = "Troppi codici non validi: accedi di nuovo con la password."

_CHIAVI_ATTESA_2FA = (
    "totp_pending_uid",
    "totp_pending_tenant_slug",
    "totp_pending_auth_scope",
    "totp_pending_auth_tenant_slug",
)
_CHIAVI_ANNULLO_2FA = _CHIAVI_ATTESA_2FA + ("totp_pending_next", "totp_tentativi")

ESTENSIONE_RUNTIME = "iusentra_accesso_runtime"


@dataclass(frozen=True)
class AccessoRuntime:
    """Dipendenze del runtime di autenticazione (registrate da ``auth_runtime``)."""

    app: Flask
    get_utenti: Callable[[], GestioneUtenti]
    gestione_utenti_studio: Callable[[str], GestioneUtenti]
    allinea_multi_studio: Callable[[], bool]
    multi_studio_disponibile: Callable[[], bool]
    multi_studio_esplicito: bool
    risolvi_accesso_studio: Callable[[str, str], object]
    unico_studio_attivo: Callable[[], str]
    studi_attivi: Callable[[], list]
    avviso_certificato_firma: Callable[[], None]


@dataclass(frozen=True)
class EsitoAccesso:
    """Esito del tentativo: la route lo traduce in HTML o JSON."""

    tipo: str
    destinazione: str = ""
    errore: str = ""
    stato_http: int = 200
    retry_after: int = 0
    multi_studio: bool = False

    @property
    def riuscito(self) -> bool:
        return self.tipo in ESITI_RIUSCITI


def registra_runtime_accesso(app: Flask, runtime: AccessoRuntime) -> None:
    app.extensions[ESTENSIONE_RUNTIME] = runtime


def runtime_accesso(app: Flask) -> AccessoRuntime:
    runtime = app.extensions.get(ESTENSIONE_RUNTIME)
    if runtime is None:  # pragma: no cover - guardrail di wiring
        raise RuntimeError("Runtime di accesso non registrato: register_auth_runtime non eseguito.")
    return runtime


def destinazione_sicura(value: str) -> str:
    candidate = str(value or "").strip()
    return candidate if is_safe_internal_path(candidate) else ""


def ip_cliente() -> str:
    return (request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip()


def messaggio_blocco(secondi: int) -> str:
    minuti = max(1, (secondi + 59) // 60)
    return (
        "Troppi tentativi di accesso falliti. "
        f"Per sicurezza l'accesso e' sospeso: riprova tra circa {minuti} "
        f"{'minuto' if minuti == 1 else 'minuti'}."
    )


def destinazione_predefinita(utente) -> str:
    return (
        url_for("admin.dashboard")
        if getattr(utente, "is_superadmin", False) and not session.get("superadmin_user_id")
        else url_for("dashboard")
    )


def esito_gia_autenticato(utente_corrente) -> EsitoAccesso | None:
    if utente_corrente:
        return EsitoAccesso(GIA_AUTENTICATO, destinazione=url_for("dashboard"))
    return None


def _esito_bloccato(rt: AccessoRuntime, secondi: int) -> EsitoAccesso:
    return EsitoAccesso(
        BLOCCATO,
        errore=messaggio_blocco(secondi),
        stato_http=429,
        retry_after=secondi,
        multi_studio=rt.multi_studio_disponibile(),
    )


def _registra_blocco(rt: AccessoRuntime, username: str, attempt_username: str, client_ip: str, secondi: int) -> None:
    try:
        rt.get_utenti().registra_evento(
            "auth.login_bloccato",
            username=attempt_username or username,
            ip=client_ip,
            dettagli=(f"Accesso temporaneamente bloccato per troppi tentativi falliti ({secondi}s residui)."),
            esito="ERRORE",
        )
    except Exception:
        rt.app.logger.warning("Audit auth.login_bloccato non registrato", exc_info=True)


def _apri_sessione(utente, *, tenant_slug: str, auth_scope: str, auth_tenant_slug: str, must_change: bool) -> None:
    session.clear()
    session["user_id"] = utente.id
    session["tenant_slug"] = tenant_slug
    session["auth_scope"] = auth_scope
    session["auth_tenant_slug"] = auth_tenant_slug
    session["last_activity"] = datetime.now().isoformat()
    session["must_change_password"] = must_change
    session.permanent = True


def _esito_sessione_aperta(
    rt: AccessoRuntime, manager, utente, *, force_password_change: bool, next_url: str, fallback: str
) -> EsitoAccesso:
    manager.registra_evento(
        "auth.login",
        id_utente=utente.id,
        username=utente.username,
        ip=request.remote_addr or "",
    )
    rt.avviso_certificato_firma()
    if force_password_change and not rt.app.testing:
        flash(MESSAGGIO_PASSWORD_TEMPORANEA, "warning")
        return EsitoAccesso(PASSWORD_DA_CAMBIARE, destinazione=url_for("profilo", password_obbligatoria=1))
    return EsitoAccesso(ACCESSO, destinazione=destinazione_sicura(next_url) or fallback)


def _autentica(rt: AccessoRuntime, username: str, password: str, studio_slug: str, multi_studio: bool):
    """Ritorna (manager, utente, studio scelto, scope, studio di autenticazione, errore)."""
    if studio_slug and multi_studio:
        from pct.tenant import GestioneTenant

        tenants = GestioneTenant(registry_path=rt.app.config["TENANTS_REGISTRY"])
        if not tenants.get(studio_slug):
            return None, None, "", "tenant", studio_slug, MESSAGGIO_STUDIO_NON_TROVATO
        manager = rt.gestione_utenti_studio(studio_slug)
        return manager, manager.autentica(username, password), studio_slug, "tenant", studio_slug, None

    manager = rt.get_utenti()
    if multi_studio and not rt.multi_studio_esplicito:
        try:
            manager.ensure_platform_superadmin()
        except Exception as exc:
            rt.app.logger.exception("Errore riallineamento SUPERADMIN in login: %s", exc)
    utente = manager.autentica(username, password)
    selected, auth_scope, auth_tenant, errore = "", "global", "", None
    if utente and multi_studio:
        selected = str(getattr(utente, "tenant_slug", "") or "")
        ruolo = str(getattr(utente, "ruolo", "") or "")
        if not selected and ruolo != str(RuoloUtente.SUPERADMIN):
            selected = rt.unico_studio_attivo()
    if not utente and multi_studio:
        tenant_match = rt.risolvi_accesso_studio(username, password)
        if tenant_match == "ambiguous":
            errore = MESSAGGIO_STUDI_AMBIGUI
        elif tenant_match:
            selected, manager, utente = tenant_match
            auth_scope = "tenant"
            auth_tenant = selected
    return manager, utente, selected, auth_scope, auth_tenant, errore


def esegui_login(
    rt: AccessoRuntime, *, username: str, password: str, studio_slug: str, next_richiesto: str
) -> EsitoAccesso:
    """Primo passo dell'accesso: stessa sequenza della route ``/login`` storica."""
    multi_studio = rt.allinea_multi_studio()
    studio_slug = str(studio_slug or "").strip().lower()
    login_guard = get_login_guard(rt.app)
    client_ip = ip_cliente()
    attempt_username = username.strip().lower()
    locked_seconds = login_guard.lock_remaining_seconds(client_ip, attempt_username)
    if locked_seconds > 0:
        _registra_blocco(rt, username, attempt_username, client_ip, locked_seconds)
        return _esito_bloccato(rt, locked_seconds)

    manager, utente, selected, auth_scope, auth_tenant, errore = _autentica(
        rt, username, password, studio_slug, multi_studio
    )
    if errore == MESSAGGIO_STUDIO_NON_TROVATO:
        # Come prima: lo studio inesistente non conta come tentativo fallito.
        return EsitoAccesso(ERRORE, errore=errore, multi_studio=True)

    resolved_tenant_slug = ""
    if utente:
        resolved_tenant_slug = str(selected or getattr(utente, "tenant_slug", "") or "").strip().lower()
        if multi_studio and not getattr(utente, "is_superadmin", False) and not resolved_tenant_slug:
            errore = MESSAGGIO_ACCOUNT_SENZA_STUDIO
            manager.registra_evento(
                "auth.login_fallito",
                id_utente=getattr(utente, "id", ""),
                username=getattr(utente, "username", "") or username,
                dettagli="Login bloccato: account globale non consentito in ambiente multi-studio.",
                ip=request.remote_addr or "",
                esito="ERRORE",
            )
            utente = None

    if utente:
        # Credenziali corrette: azzera i tentativi falliti della coppia
        # (IP, username) prima di proseguire con sessione o secondo fattore.
        login_guard.register_success(client_ip, attempt_username)
        if utente.totp_attivato:
            session.clear()
            session["totp_pending_uid"] = utente.id
            session["totp_pending_tenant_slug"] = resolved_tenant_slug or ""
            session["totp_pending_auth_scope"] = auth_scope
            session["totp_pending_auth_tenant_slug"] = auth_tenant or ""
            session["totp_pending_next"] = destinazione_sicura(next_richiesto) or url_for("dashboard")
            session["totp_pending_force_password_change"] = bool(getattr(utente, "must_change_password", False))
            return EsitoAccesso(SECONDO_FATTORE, destinazione=url_for("login_2fa"))

        must_change = bool(getattr(utente, "must_change_password", False))
        _apri_sessione(
            utente,
            tenant_slug=resolved_tenant_slug,
            auth_scope=auth_scope,
            auth_tenant_slug=auth_tenant or "",
            must_change=must_change,
        )
        return _esito_sessione_aperta(
            rt,
            manager,
            utente,
            force_password_change=bool(session.get("must_change_password")),
            next_url=next_richiesto,
            fallback=destinazione_predefinita(utente),
        )

    manager.registra_evento(
        "auth.login_fallito",
        username=username,
        ip=request.remote_addr or "",
        esito="ERRORE",
    )
    # Tentativo non andato a buon fine: conta il fallimento e, alla soglia,
    # blocca temporaneamente questa coppia (IP, username) e l'IP.
    locked_after = login_guard.register_failure(client_ip, attempt_username)
    if locked_after > 0:
        return _esito_bloccato(rt, locked_after)
    return EsitoAccesso(ERRORE, errore=errore or MESSAGGIO_CREDENZIALI, multi_studio=rt.multi_studio_disponibile())


def attesa_secondo_fattore(rt: AccessoRuntime):
    """(manager, utente) della verifica in corso, oppure None (chiavi pulite)."""
    uid = session.get("totp_pending_uid")
    if not uid:
        return None
    pending_tenant_slug = session.get("totp_pending_tenant_slug", "")
    pending_auth_scope = str(session.get("totp_pending_auth_scope", "") or "").strip().lower()
    pending_auth_tenant_slug = str(session.get("totp_pending_auth_tenant_slug", "") or "").strip().lower()
    multi_studio = rt.allinea_multi_studio()
    if pending_auth_scope == "tenant" and pending_auth_tenant_slug and multi_studio:
        manager = rt.gestione_utenti_studio(pending_auth_tenant_slug)
    elif pending_tenant_slug and multi_studio:
        manager = rt.gestione_utenti_studio(pending_tenant_slug)
    else:
        manager = rt.get_utenti()
    utente = manager.get(uid)
    if not utente or not utente.totp_attivato:
        for chiave in _CHIAVI_ATTESA_2FA:
            session.pop(chiave, None)
        return None
    return manager, utente


def verifica_secondo_fattore(rt: AccessoRuntime, manager, utente, codice: str) -> EsitoAccesso:
    """Secondo passo: stessa sequenza della route ``/login/2fa`` storica."""
    codice = str(codice or "").strip()
    if verifica_totp(utente.totp_secret, codice):
        next_url = destinazione_sicura(session.pop("totp_pending_next", ""))
        force_password_change = bool(session.pop("totp_pending_force_password_change", False))
        tenant_slug = session.pop("totp_pending_tenant_slug", "")
        auth_scope = str(session.pop("totp_pending_auth_scope", "") or "").strip().lower()
        auth_tenant_slug = str(session.pop("totp_pending_auth_tenant_slug", "") or "").strip().lower()
        scope = auth_scope or ("tenant" if auth_tenant_slug or utente.tenant_slug else "global")
        _apri_sessione(
            utente,
            tenant_slug=tenant_slug or utente.tenant_slug or "",
            auth_scope=scope,
            auth_tenant_slug=auth_tenant_slug or (utente.tenant_slug if scope == "tenant" else ""),
            must_change=force_password_change,
        )
        if not next_url:
            next_url = destinazione_predefinita(utente)
        return _esito_sessione_aperta(
            rt,
            manager,
            utente,
            force_password_change=force_password_change,
            next_url=next_url,
            fallback=url_for("dashboard"),
        )

    manager.registra_evento(
        "auth.2fa_fallito",
        id_utente=utente.id,
        username=utente.username,
        ip=request.remote_addr or "",
        esito="ERRORE",
    )
    # Cinque codici sbagliati: si torna alla password. Senza limite un
    # codice a sei cifre si indovina per tentativi.
    tentativi = int(session.get("totp_tentativi", 0) or 0) + 1
    session["totp_tentativi"] = tentativi
    if tentativi >= TOTP_TENTATIVI_MASSIMI:
        for chiave in _CHIAVI_ANNULLO_2FA:
            session.pop(chiave, None)
        flash(MESSAGGIO_TROPPI_CODICI, "danger")
        return EsitoAccesso(VERIFICA_ANNULLATA, destinazione=url_for("login"), errore=MESSAGGIO_TROPPI_CODICI)
    return EsitoAccesso(ERRORE, errore=MESSAGGIO_CODICE_NON_VALIDO)


__all__ = [
    "ACCESSO",
    "BLOCCATO",
    "ERRORE",
    "GIA_AUTENTICATO",
    "PASSWORD_DA_CAMBIARE",
    "SECONDO_FATTORE",
    "TOTP_TENTATIVI_MASSIMI",
    "VERIFICA_ANNULLATA",
    "AccessoRuntime",
    "EsitoAccesso",
    "attesa_secondo_fattore",
    "destinazione_predefinita",
    "destinazione_sicura",
    "esegui_login",
    "esito_gia_autenticato",
    "registra_runtime_accesso",
    "runtime_accesso",
    "verifica_secondo_fattore",
]
