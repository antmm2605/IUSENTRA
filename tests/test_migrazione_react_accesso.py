"""Pagine pubbliche di accesso servite da React (AccessoApp).

Accesso, verifica in due passaggi e cambio obbligatorio della password usano
la stessa logica server (``web.services.auth_accesso_flow``) sia dalle route
HTML storiche sia dalle API ``/api/v1/pubblico/accesso/*``: stessi messaggi
generici, stesso blocco dei tentativi, stesso audit, stesse chiavi di sessione,
stessa protezione CSRF e stessa validazione di ``next``.
"""

from __future__ import annotations

import base64
import json
import re
import time
import uuid
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente, _hotp
from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app

API = "/api/v1/pubblico/accesso"
SEGRETO_TOTP = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
MESSAGGIO_GENERICO = "Credenziali non valide o utente disabilitato."


# ------------------------------------------------------------------ fixture


def _ip() -> dict[str, str]:
    """IP univoco per test: il login_guard (anche su Redis) non si trascina tra i test."""
    return {"X-Forwarded-For": f"test-{uuid.uuid4().hex}"}


def _app_studio(tmp_path: Path, *, testing: bool = True, **config):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["TESTING"] = testing
    app = create_app(cfg)
    app.config.update(config)
    return app


def _crea_utente_globale(app, username: str, password: str, **extra):
    with app.test_request_context("/login"):
        gestione = app.extensions["iusentra_accesso_runtime"].get_utenti()
        return gestione.crea(
            username=username,
            password=password,
            ruolo=RuoloUtente.AMMINISTRATORE,
            must_change_password=extra.pop("must_change_password", False),
            **extra,
        )


def _app_multi_studio(tmp_path: Path, **config):
    registry = tmp_path / "tenants.json"
    registry.write_text(
        json.dumps(
            {
                "studio-001": {
                    "slug": "studio-rossi",
                    "nome": "Studio Rossi",
                    "piano": "PROFESSIONAL",
                    "stato": "ATTIVO",
                    "db_config": "LOCAL",
                }
            }
        ),
        encoding="utf-8",
    )
    app = create_app(
        {
            "TESTING": True,
            "MULTI_TENANT": True,
            "TENANTS_REGISTRY": str(registry),
            "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
            "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
            "CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json"),
            "BOOTSTRAP_ADMIN_PASSWORD": "superpass123",
        }
    )
    app.config.update(config)
    tenants = GestioneTenant(str(registry))
    studio = tenants.get("studio-rossi")
    percorsi = tenants.percorsi_dati(studio.slug)
    utenti_studio = GestioneUtenti(
        db_path=percorsi["AUTH_DB"],
        audit_path=percorsi["AUDIT_DB"],
        secret_key=app.secret_key,
        crea_admin_se_vuoto=False,
    )
    avvocato = utenti_studio.crea(
        username="avvocato",
        password="StudioPass123!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=False,
    )
    verificato = utenti_studio.crea(
        username="verificato",
        password="StudioPass123!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        tenant_slug=studio.slug,
        must_change_password=False,
    )
    # Archivio utenti dello studio in JSON (login con include_studio_db=False):
    # il secondo fattore si attiva direttamente sul record.
    verificato.totp_secret = SEGRETO_TOTP
    verificato.totp_attivato = True
    utenti_studio._salva_utenti()
    return app, studio, percorsi, avvocato


def _codice_totp(segreto: str = SEGRETO_TOTP) -> str:
    return str(_hotp(base64.b32decode(segreto), int(time.time()) // 30)).zfill(6)


def _meta_csrf(html: str) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert match, "Token CSRF non presente nella pagina React di accesso."
    return match.group(1)


def _audit(percorso: str | Path) -> str:
    path = Path(percorso)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _attributo(html: str, nome: str) -> str:
    match = re.search(rf'{nome}="([^"]*)"', html)
    return match.group(1) if match else ""


# ------------------------------------------------------------------ pagina React


def test_login_serve_la_pagina_react_e_la_vista_classica_resta(tmp_path: Path):
    app = _app_studio(tmp_path)
    with app.test_client() as client:
        risposta = client.get("/login?next=/agenda")
        html = risposta.get_data(as_text=True)
        classica = client.get("/login?_legacy=1")

    assert risposta.status_code == 200
    assert 'id="accesso-react-root"' in html and 'data-accesso="1"' in html
    assert 'data-vista="login"' in html
    assert 'data-next="/agenda"' in html
    assert _meta_csrf(html)
    assert "no-store" in risposta.headers["Cache-Control"]
    assert "<form" not in html and "onclick" not in html.lower()
    if 'type="module"' in html:
        # Il modulo parte solo con il parametro di versione (main.tsx).
        assert ".js?v=" in html
    assert classica.status_code == 200
    assert 'class="auth-shell"' in classica.get_data(as_text=True)


def test_login_react_scarta_next_esterni_nella_pagina(tmp_path: Path):
    app = _app_studio(tmp_path)
    with app.test_client() as client:
        for esterno in ("//evil.example/x", "https://evil.example", "/\\evil.example"):
            html = client.get("/login", query_string={"next": esterno}).get_data(as_text=True)
            assert 'data-next=""' in html, esterno


def test_modello_della_pagina_avvia_il_modulo_con_la_versione():
    testo = Path("web/templates/accesso_shell.html").read_text(encoding="utf-8")
    assert 'src="{{ js_file }}?v={{ app_version }}"' in testo
    assert 'id="accesso-react-root"' in testo and 'data-accesso="1"' in testo
    assert '<meta name="csrf-token"' in testo
    assert "<style" not in testo and "style=" not in testo


def test_verifica_2fa_serve_la_pagina_react_solo_con_verifica_in_corso(tmp_path: Path):
    app, _studio, _percorsi, _avvocato = _app_multi_studio(tmp_path)
    with app.test_client() as client:
        senza_attesa = client.get("/login/2fa", follow_redirects=False)
        esito = client.post(
            f"{API}/login", json={"username": "verificato", "password": "StudioPass123!"}, headers=_ip()
        )
        pagina = client.get("/login/2fa")
        classica = client.get("/login/2fa?_legacy=1")

    assert senza_attesa.status_code == 302 and senza_attesa.headers["Location"].endswith("/login")
    assert esito.get_json()["esito"] == "2fa_richiesta"
    assert pagina.status_code == 200
    assert 'data-vista="2fa"' in pagina.get_data(as_text=True)
    assert "no-store" in pagina.headers["Cache-Control"]
    assert classica.status_code == 200
    assert "Conferma la tua identità" in classica.get_data(as_text=True)


def test_cambio_password_obbligatorio_nella_pagina_react(tmp_path: Path):
    app = _app_studio(tmp_path, testing=False)
    with app.test_client() as client:
        token = _meta_csrf(client.get("/login").get_data(as_text=True))
        accesso = client.post(
            f"{API}/login",
            json={"username": "admin", "password": "admin"},
            headers={"X-CSRF-Token": token, **_ip()},
        )
        corpo = accesso.get_json()
        assert accesso.status_code == 200
        assert corpo["esito"] == "password_da_cambiare"
        assert corpo["redirect"].endswith("/profilo?password_obbligatoria=1")

        bloccata = client.get("/", follow_redirects=False)
        assert bloccata.headers["Location"].endswith("/profilo?password_obbligatoria=1")

        pagina = client.get("/profilo?password_obbligatoria=1")
        html = pagina.get_data(as_text=True)
        assert pagina.status_code == 200 and 'data-vista="password"' in html

        # La pagina React mostra i messaggi flash letti dallo stato (e li consuma).
        stato = client.get(f"{API}/stato").get_json()
        assert stato["autenticato"] is True and stato["password_obbligatoria"] is True
        assert any("Password iniziale temporanea" in m["testo"] for m in stato["messaggi"])
        assert client.get(f"{API}/stato").get_json()["messaggi"] == []

        classica = client.get("/profilo?password_obbligatoria=1&_legacy=1")
        assert "accesso-react-root" not in classica.get_data(as_text=True)

        cambio = client.post(
            "/profilo",
            data={"azione": "password", "password_old": "admin", "password_new": "NuovaPassword123!"},
            headers={
                "X-CSRF-Token": _meta_csrf(html),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )
        assert cambio.status_code == 200 and cambio.get_json()["ok"] is True
        dopo = client.get("/", follow_redirects=False)
        assert "password_obbligatoria" not in (dopo.headers.get("Location") or "")


# ------------------------------------------------------------------ API di accesso


def test_login_json_riuscito_apre_la_stessa_sessione_del_login_html(tmp_path: Path):
    app = _app_studio(tmp_path)
    _crea_utente_globale(app, "mario", "MarioPass123!")
    chiavi = ("user_id", "tenant_slug", "auth_scope", "auth_tenant_slug", "must_change_password")
    with app.test_client() as html_client:
        html = html_client.post("/login", data={"username": "mario", "password": "MarioPass123!"}, headers=_ip())
        with html_client.session_transaction() as sessione:
            sessione_html = {k: sessione.get(k) for k in chiavi}
    with app.test_client() as client:
        risposta = client.post(f"{API}/login", json={"username": "mario", "password": "MarioPass123!"}, headers=_ip())
        with client.session_transaction() as sessione:
            sessione_json = {k: sessione.get(k) for k in chiavi}
            assert sessione.permanent is True and sessione.get("last_activity")
        stato = client.get(f"{API}/stato").get_json()

    assert html.status_code == 302 and html.headers["Location"] == "/"
    corpo = risposta.get_json()
    assert risposta.status_code == 200 and corpo == {**corpo, "ok": True, "esito": "accesso", "redirect": "/"}
    assert corpo["csrf_token"]
    assert sessione_json == sessione_html and sessione_json["user_id"]
    assert stato["autenticato"] is True and stato["utente"] == "mario"
    assert _audit(app.config["AUDIT_DB"]).count("auth.login") >= 2


def test_login_json_messaggio_generico_non_rivela_l_utente(tmp_path: Path):
    app = _app_studio(tmp_path)
    with app.test_client() as client:
        esistente = client.post(f"{API}/login", json={"username": "admin", "password": "sbagliata"}, headers=_ip())
        inesistente = client.post(f"{API}/login", json={"username": "nessuno", "password": "sbagliata"}, headers=_ip())
        html = client.post("/login", data={"username": "nessuno", "password": "sbagliata"}, headers=_ip())

    for risposta in (esistente, inesistente):
        corpo = risposta.get_json()
        assert risposta.status_code == 401
        assert corpo["ok"] is False and corpo["code"] == "accesso_non_riuscito"
        assert corpo["message"] == MESSAGGIO_GENERICO
        assert "user_id" not in corpo and "redirect" not in corpo
    assert {k: v for k, v in esistente.get_json().items() if k != "csrf_token"} == {
        k: v for k, v in inesistente.get_json().items() if k != "csrf_token"
    }
    assert MESSAGGIO_GENERICO in html.get_data(as_text=True)
    assert _audit(app.config["AUDIT_DB"]).count("auth.login_fallito") >= 3


def test_login_json_bloccato_dopo_5_tentativi_con_retry_after(tmp_path: Path):
    app = _app_studio(
        tmp_path,
        LOGIN_GUARD_ENABLED=True,
        LOGIN_GUARD_MAX_PER_USER=5,
        LOGIN_GUARD_MAX_PER_IP=50,
        LOGIN_GUARD_WINDOW_SECONDS=900,
        LOGIN_GUARD_LOCK_SECONDS=900,
    )
    ip = _ip()
    with app.test_client() as client:
        for _ in range(4):
            assert (
                client.post(f"{API}/login", json={"username": "admin", "password": "x"}, headers=ip).status_code == 401
            )
        quinto = client.post(f"{API}/login", json={"username": "admin", "password": "x"}, headers=ip)
        corretta = client.post(f"{API}/login", json={"username": "admin", "password": "admin"}, headers=ip)
        # Stesso login_guard della route HTML: anche il modulo classico resta bloccato.
        html = client.post("/login", data={"username": "admin", "password": "admin"}, headers=ip)
        with client.session_transaction() as sessione:
            assert "user_id" not in sessione

    for risposta in (quinto, corretta):
        corpo = risposta.get_json()
        assert risposta.status_code == 429
        assert int(risposta.headers["Retry-After"]) > 0
        assert corpo["code"] == "accesso_sospeso" and corpo["retry_after"] > 0
        assert "sospeso" in corpo["message"]
    assert html.status_code == 429 and int(html.headers["Retry-After"]) > 0
    assert "auth.login_bloccato" in _audit(app.config["AUDIT_DB"])


def test_login_json_next_protetto_da_open_redirect(tmp_path: Path):
    app = _app_studio(tmp_path)
    _crea_utente_globale(app, "mario", "MarioPass123!")
    casi = {
        "//evil.example/rubare": "/",
        "https://evil.example": "/",
        "/\\evil.example": "/",
        "javascript:alert(1)": "/",
        "/agenda?vista=week": "/agenda?vista=week",
    }
    for richiesto, atteso in casi.items():
        with app.test_client() as client:
            corpo = client.post(
                f"{API}/login",
                json={"username": "mario", "password": "MarioPass123!", "next": richiesto},
                headers=_ip(),
            ).get_json()
            assert corpo["redirect"] == atteso, richiesto
    with app.test_client() as client:
        # `next` anche in query string, come per /login.
        corpo = client.post(
            f"{API}/login?next=//evil.example",
            json={"username": "mario", "password": "MarioPass123!"},
            headers=_ip(),
        ).get_json()
        assert corpo["redirect"] == "/"


def test_login_json_richiede_csrf_come_il_login_html(tmp_path: Path):
    app = _app_studio(tmp_path, testing=False)
    with app.test_client() as client:
        token = _meta_csrf(client.get("/login").get_data(as_text=True))
        senza = client.post(f"{API}/login", json={"username": "admin", "password": "x"}, headers=_ip())
        sbagliato = client.post(
            f"{API}/login",
            json={"username": "admin", "password": "x"},
            headers={"X-CSRF-Token": "falso", "Origin": "https://evil.example", **_ip()},
        )
        verifica = client.post(f"{API}/2fa", json={"codice": "123456"}, headers=_ip())
        html_senza = client.post(
            "/login", data={"username": "admin", "password": "x"}, headers={"Origin": "https://evil.example", **_ip()}
        )
        valido = client.post(
            f"{API}/login", json={"username": "admin", "password": "x"}, headers={"X-CSRF-Token": token, **_ip()}
        )

    for risposta in (senza, sbagliato, verifica):
        assert risposta.status_code == 400
        assert risposta.get_json()["code"] == "csrf_non_valido"
    assert html_senza.status_code == 400
    assert valido.status_code == 401 and valido.get_json()["message"] == MESSAGGIO_GENERICO

    from web.services.security_runtime import _CSRF_PROTECTED_ENDPOINTS

    assert {
        "api_v1_accesso_pubblico.accesso_login",
        "api_v1_accesso_pubblico.accesso_login_2fa",
    } <= _CSRF_PROTECTED_ENDPOINTS


def test_stato_anonimo_non_espone_dati(tmp_path: Path):
    app = _app_studio(tmp_path)
    with app.test_client() as client:
        risposta = client.get(f"{API}/stato")
    corpo = risposta.get_json()
    assert risposta.status_code == 200 and corpo["ok"] is True
    assert corpo["autenticato"] is False and corpo["utente"] == ""
    assert corpo["verifica_2fa"] == {"in_attesa": False, "utente": ""}
    assert corpo["multi_studio"] is False and corpo["studi"] == []
    assert corpo["csrf_token"]
    assert "no-store" in risposta.headers["Cache-Control"]


# ------------------------------------------------------------------ secondo fattore e multi-studio


def test_verifica_2fa_json_codice_errato_e_corretto(tmp_path: Path):
    app, studio, percorsi, _avvocato = _app_multi_studio(tmp_path)
    with app.test_client() as client:
        primo = client.post(
            f"{API}/login",
            json={
                "username": "verificato",
                "password": "StudioPass123!",
                "studio_slug": studio.slug,
                "next": "/agenda",
            },
            headers=_ip(),
        )
        corpo = primo.get_json()
        assert primo.status_code == 200 and corpo["esito"] == "2fa_richiesta"
        assert corpo["redirect"].endswith("/login/2fa")
        with client.session_transaction() as sessione:
            assert sessione.get("totp_pending_uid") and "user_id" not in sessione
            assert sessione.get("totp_pending_next") == "/agenda"
            assert sessione.get("totp_pending_auth_scope") == "tenant"

        stato = client.get(f"{API}/stato").get_json()
        assert stato["verifica_2fa"] == {"in_attesa": True, "utente": "verificato"}

        errato = client.post(f"{API}/2fa", json={"codice": "000000"}, headers=_ip())
        assert errato.status_code == 401
        assert errato.get_json()["code"] == "codice_non_valido"
        assert errato.get_json()["message"] == "Codice non valido. Riprova."

        corretto = client.post(f"{API}/2fa", json={"codice": _codice_totp()}, headers=_ip())
        with client.session_transaction() as sessione:
            assert sessione.get("user_id") and sessione.get("tenant_slug") == studio.slug
            assert sessione.get("auth_scope") == "tenant" and "totp_pending_uid" not in sessione

    assert corretto.status_code == 200
    assert corretto.get_json()["esito"] == "accesso" and corretto.get_json()["redirect"] == "/agenda"
    audit = _audit(percorsi["AUDIT_DB"])
    assert "auth.2fa_fallito" in audit and "auth.login" in audit


def test_verifica_2fa_json_annullata_dopo_5_codici_errati(tmp_path: Path):
    app, studio, _percorsi, _avvocato = _app_multi_studio(tmp_path)
    with app.test_client() as client:
        client.post(
            f"{API}/login",
            json={"username": "verificato", "password": "StudioPass123!", "studio_slug": studio.slug},
            headers=_ip(),
        )
        esiti = [client.post(f"{API}/2fa", json={"codice": "000000"}, headers=_ip()) for _ in range(5)]
        dopo = client.post(f"{API}/2fa", json={"codice": _codice_totp()}, headers=_ip())
        stato = client.get(f"{API}/stato").get_json()

    assert [r.get_json()["code"] for r in esiti[:4]] == ["codice_non_valido"] * 4
    ultimo = esiti[4].get_json()
    assert ultimo["code"] == "verifica_annullata" and ultimo["redirect"].endswith("/login")
    assert dopo.status_code == 401 and dopo.get_json()["code"] == "verifica_non_in_corso"
    assert any("Troppi codici non validi" in m["testo"] for m in stato["messaggi"])


def test_multi_studio_selezione_dello_studio(tmp_path: Path):
    app, studio, _percorsi, avvocato = _app_multi_studio(tmp_path)
    with app.test_client() as client:
        stato = client.get(f"{API}/stato").get_json()
        assert stato["multi_studio"] is True and stato["studi"] == []

        sconosciuto = client.post(
            f"{API}/login",
            json={"username": "avvocato", "password": "StudioPass123!", "studio_slug": "studio-inesistente"},
            headers=_ip(),
        )
        assert sconosciuto.status_code == 401 and sconosciuto.get_json()["message"] == "Studio non trovato."

        riuscito = client.post(
            f"{API}/login",
            json={"username": "avvocato", "password": "StudioPass123!", "studio_slug": " Studio-Rossi "},
            headers=_ip(),
        )
        assert riuscito.status_code == 200 and riuscito.get_json()["esito"] == "accesso"
        with client.session_transaction() as sessione:
            assert sessione["user_id"] == avvocato.id
            assert sessione["tenant_slug"] == studio.slug
            assert sessione["auth_scope"] == "tenant" and sessione["auth_tenant_slug"] == studio.slug

    with app.test_client() as client:
        # Senza studio indicato lo studio si ricava dalle credenziali, come in /login.
        dedotto = client.post(
            f"{API}/login", json={"username": "avvocato", "password": "StudioPass123!"}, headers=_ip()
        )
        assert dedotto.status_code == 200
        with client.session_transaction() as sessione:
            assert sessione["tenant_slug"] == studio.slug and sessione["auth_scope"] == "tenant"

    app.config["LOGIN_ELENCO_STUDI_PUBBLICO"] = True
    with app.test_client() as client:
        elenco = client.get(f"{API}/stato").get_json()["studi"]
    assert elenco == [{"slug": "studio-rossi", "nome": "Studio Rossi"}]


def test_api_di_accesso_pubbliche_in_multi_studio(tmp_path: Path):
    app, _studio, _percorsi, _avvocato = _app_multi_studio(tmp_path)
    with app.test_client() as client:
        stato = client.get(f"{API}/stato")
        login = client.post(f"{API}/login", json={"username": "x", "password": "y"}, headers=_ip())
        verifica = client.post(f"{API}/2fa", json={"codice": "1"}, headers=_ip())
    # Nessun 401 «autenticazione richiesta» né 409 di contesto studio: sono pubbliche.
    assert stato.status_code == 200
    assert login.status_code == 401 and login.get_json()["code"] == "accesso_non_riuscito"
    assert verifica.status_code == 401 and verifica.get_json()["code"] == "verifica_non_in_corso"
