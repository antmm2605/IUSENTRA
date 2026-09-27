"""API pubbliche della pagina React di accesso (``AccessoApp``).

Gli endpoint traducono in JSON gli esiti di ``web.services.auth_accesso_flow``,
la stessa logica usata da ``/login`` e ``/login/2fa``: stesso blocco
anti brute-force, stesso audit, stesse chiavi di sessione, stessi messaggi
generici (nessuna indicazione sull'esistenza di un utente). Le scritture sono
protette dal token CSRF di sessione come le route HTML
(``_CSRF_PROTECTED_ENDPOINTS``) e soggette al limite stretto del rate limiter
(nome dell'endpoint con «login»).

Base normativa: misure di sicurezza del trattamento (GDPR art. 32; D.Lgs.
196/2003) per l'accesso ai dati riservati dello studio.
"""

from __future__ import annotations

import os

from flask import Blueprint, current_app, g, get_flashed_messages, jsonify, request, url_for

from web.services.auth_accesso_flow import (
    BLOCCATO,
    VERIFICA_ANNULLATA,
    EsitoAccesso,
    attesa_secondo_fattore,
    destinazione_predefinita,
    esegui_login,
    esito_gia_autenticato,
    runtime_accesso,
    verifica_secondo_fattore,
)
from web.services.security_runtime import csrf_token_sessione

api_v1_accesso_pubblico = Blueprint("api_v1_accesso_pubblico", __name__)

MESSAGGIO_VERIFICA_NON_IN_CORSO = "La verifica non è più in corso: accedi di nuovo con la password."
_VALORI_VERI = {"1", "true", "yes", "si", "on"}


def _risposta_json(body: dict, status: int = 200, *, retry_after: int = 0):
    body["csrf_token"] = csrf_token_sessione()
    response = jsonify(body)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    if retry_after:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _risposta_esito(esito: EsitoAccesso, *, codice_errore: str):
    body: dict = {"ok": esito.riuscito, "esito": esito.tipo}
    if esito.destinazione:
        body["redirect"] = esito.destinazione
    if esito.riuscito:
        return _risposta_json(body)
    body["message"] = esito.errore
    if esito.tipo == BLOCCATO:
        body["code"] = "accesso_sospeso"
        body["retry_after"] = esito.retry_after
        return _risposta_json(body, 429, retry_after=esito.retry_after)
    body["code"] = "verifica_annullata" if esito.tipo == VERIFICA_ANNULLATA else codice_errore
    return _risposta_json(body, 401)


def _campi_richiesta() -> dict[str, str]:
    payload = request.get_json(silent=True)
    source = payload if isinstance(payload, dict) else request.form
    return {str(key): value for key, value in source.items() if isinstance(value, str)}


def _elenco_studi_pubblico() -> bool:
    value = current_app.config.get("LOGIN_ELENCO_STUDI_PUBBLICO")
    if value is None:
        value = os.environ.get("IUSENTRA_LOGIN_ELENCO_STUDI_PUBBLICO")
    return str(value or "").strip().lower() in _VALORI_VERI


def _studi_pubblici(rt, multi_studio: bool) -> list[dict[str, str]]:
    """Elenco degli studi attivi: solo se l'installazione lo pubblica esplicitamente."""
    if not multi_studio or not _elenco_studi_pubblico():
        return []
    try:
        studi = rt.studi_attivi()
    except Exception as exc:  # pragma: no cover - registro studi illeggibile
        current_app.logger.warning("Elenco studi per l'accesso non disponibile: %s", exc)
        return []
    elenco = []
    for studio in studi:
        slug = str(getattr(studio, "slug", "") or "").strip().lower()
        if slug:
            elenco.append({"slug": slug, "nome": str(getattr(studio, "nome", "") or slug)})
    return elenco


def _messaggi_flash() -> list[dict[str, str]]:
    return [
        {"categoria": str(categoria or "info"), "testo": str(testo)}
        for categoria, testo in get_flashed_messages(with_categories=True)
    ]


@api_v1_accesso_pubblico.errorhandler(400)
def _richiesta_non_valida(error):
    descrizione = str(getattr(error, "description", "") or "")
    csrf = "conferma di sicurezza" in descrizione or "sito diverso" in descrizione
    body = {
        "ok": False,
        "code": "csrf_non_valido" if csrf else "richiesta_non_valida",
        "message": ("La pagina di accesso è scaduta: ricaricala e riprova." if csrf else "Richiesta non valida."),
    }
    return _risposta_json(body, 400)


@api_v1_accesso_pubblico.errorhandler(429)
def _troppe_richieste(_error):
    body = {"ok": False, "code": "troppe_richieste", "message": "Troppe richieste: riprova tra poco."}
    return _risposta_json(body, 429)


@api_v1_accesso_pubblico.get("/stato")
def accesso_stato():
    """Cosa deve mostrare la pagina di accesso (nessun dato di studio)."""
    rt = runtime_accesso(current_app)
    multi_studio = rt.multi_studio_disponibile()
    utente = g.get("utente_corrente")
    body: dict = {
        "ok": True,
        "autenticato": bool(utente),
        "multi_studio": multi_studio,
        "studi": _studi_pubblici(rt, multi_studio),
        "verifica_2fa": {"in_attesa": False, "utente": ""},
        "password_obbligatoria": False,
        "utente": "",
        "destinazione": "",
    }
    if utente:
        body["utente"] = str(getattr(utente, "username", "") or "")
        body["password_obbligatoria"] = bool(getattr(utente, "must_change_password", False))
        body["destinazione"] = destinazione_predefinita(utente)
    else:
        attesa = attesa_secondo_fattore(rt)
        if attesa is not None:
            body["verifica_2fa"] = {"in_attesa": True, "utente": str(attesa[1].username or "")}
    body["messaggi"] = _messaggi_flash()
    return _risposta_json(body)


@api_v1_accesso_pubblico.post("/login")
def accesso_login():
    """Primo passo dell'accesso: stessa logica della route ``/login``."""
    gia_autenticato = esito_gia_autenticato(g.get("utente_corrente"))
    if gia_autenticato is not None:
        return _risposta_esito(gia_autenticato, codice_errore="accesso_non_riuscito")
    campi = _campi_richiesta()
    esito = esegui_login(
        runtime_accesso(current_app),
        username=campi.get("username", ""),
        password=campi.get("password", ""),
        studio_slug=campi.get("studio_slug", ""),
        next_richiesto=campi.get("next", "") or request.args.get("next", ""),
    )
    return _risposta_esito(esito, codice_errore="accesso_non_riuscito")


@api_v1_accesso_pubblico.post("/2fa")
def accesso_login_2fa():
    """Secondo passo: stessa logica della route ``/login/2fa``."""
    rt = runtime_accesso(current_app)
    attesa = attesa_secondo_fattore(rt)
    if attesa is None:
        body = {
            "ok": False,
            "esito": "verifica_non_in_corso",
            "code": "verifica_non_in_corso",
            "message": MESSAGGIO_VERIFICA_NON_IN_CORSO,
            "redirect": url_for("login"),
        }
        return _risposta_json(body, 401)
    manager, utente = attesa
    esito = verifica_secondo_fattore(rt, manager, utente, _campi_richiesta().get("codice", ""))
    return _risposta_esito(esito, codice_errore="codice_non_valido")


__all__ = ["api_v1_accesso_pubblico"]
