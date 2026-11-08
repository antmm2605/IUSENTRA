"""Accesso e amministrazione: TOTP sul server, IP affidabile, registro art. 30, CSV, deleghe utenti."""

from __future__ import annotations

from pathlib import Path

import base64
import time

from pct.auth import GestioneUtenti, RuoloUtente, _cella_csv_sicura, _hotp, genera_totp_secret
from tests.test_topbar_operational_api import _cfg_web, _create_user, _login
from web.app import create_app

JSON = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


def _gestore(app) -> GestioneUtenti:
    return GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        bootstrap_admin_password="admin",
        bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
    )


def _app(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    cfg["PRIVACY_DB"] = str(tmp_path / "privacy" / "registro.json")  # mai il registro del repository
    app = create_app(cfg)
    _create_user(app, "admin2", "Admin12345!")
    return app


def test_cella_csv_neutralizza_le_formule():
    assert _cella_csv_sicura("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert _cella_csv_sicura("+1") == "'+1"
    assert _cella_csv_sicura("@SUM(A1)") == "'@SUM(A1)"
    assert _cella_csv_sicura("mario.rossi") == "mario.rossi"
    assert _cella_csv_sicura(None) == ""


def test_esportazione_csv_audit_non_contiene_formule(tmp_path):
    app = _app(tmp_path)
    gestore = _gestore(app)
    gestore.registra_evento("auth.login_fallito", username="=cmd|' /C calc'!A0", esito="ERRORE")
    csv = gestore.esporta_audit_csv()
    assert "'=cmd" in csv
    assert ",=cmd" not in csv


def test_limite_totp_resta_sul_server_anche_ripresentando_il_cookie(tmp_path):
    app = _app(tmp_path)
    _create_user(app, "dueffe", "Dueffe12345!", ruolo=RuoloUtente.AVVOCATO)
    gestore = _gestore(app)
    utente = next(u for u in gestore.tutti() if u.username == "dueffe")
    segreto = genera_totp_secret()
    utente.totp_secret = segreto
    utente.totp_attivato = True
    gestore._salva_utenti()
    with app.test_client() as client:
        client.post("/login", data={"username": "dueffe", "password": "Dueffe12345!"})
        with client.session_transaction() as sessione:
            assert sessione.get("totp_pending_uid") == utente.id  # siamo al secondo fattore
        nome_cookie = app.config.get("SESSION_COOKIE_NAME") or "session"
        cookie = client.get_cookie(nome_cookie)
        assert cookie is not None
        valore_iniziale = cookie.value
        esiti = []
        for _ in range(7):
            client.set_cookie(nome_cookie, valore_iniziale)  # cookie del primo passo, totp_tentativi=0
            esiti.append(client.post("/login/2fa", data={"codice": "000000"}).status_code)
        client.set_cookie(nome_cookie, valore_iniziale)
        corretto = str(_hotp(base64.b32decode(segreto), int(time.time()) // 30)).zfill(6)
        client.post("/login/2fa", data={"codice": corretto})
        with client.session_transaction() as sessione:
            assert "user_id" not in sessione, "dopo cinque codici errati il codice giusto non basta più"


def test_registro_trattamenti_non_si_modifica_con_sola_lettura(tmp_path):
    app = _app(tmp_path)
    gestore = _gestore(app)
    gestore.crea(username="lettore", password="Lettore12345!", ruolo=RuoloUtente.SEGRETERIA,
                 email="lettore@example.it", nome_completo="Lettore", must_change_password=False)
    lettore = next(u for u in gestore.tutti() if u.username == "lettore")
    gestore.aggiorna_permessi(lettore.id, ["utenti.leggi"], [])
    with app.test_client() as client:
        _login(client, "admin2", "Admin12345!")
        creato = client.post("/privacy/registro/nuovo", data={"nome": "Gestione pratiche", "finalita": "Difesa"}, headers=JSON)
        assert creato.status_code == 200
    with app.app_context():
        trattamenti = app.extensions["core_runtime"]["get_trattamenti"]().tutti()
    id_t = trattamenti[0].id
    prima = sorted(t.id for t in trattamenti)
    with app.test_client() as client:
        _login(client, "lettore", "Lettore12345!")
        assert client.post("/privacy/registro/nuovo", data={"nome": "Abusivo"}, headers=JSON).status_code == 403
        assert client.post(f"/privacy/registro/{id_t}/elimina", headers=JSON).status_code == 403
    with app.app_context():
        assert sorted(t.id for t in app.extensions["core_runtime"]["get_trattamenti"]().tutti()) == prima


def test_delega_utenti_scrivi_non_diventa_amministratore(tmp_path):
    app = _app(tmp_path)
    gestore = _gestore(app)
    gestore.crea(username="delegato", password="Delegato12345!", ruolo=RuoloUtente.SEGRETERIA,
                 email="delegato@example.it", nome_completo="Delegato", must_change_password=False)
    delegato = next(u for u in gestore.tutti() if u.username == "delegato")
    gestore.aggiorna_permessi(delegato.id, ["utenti.leggi", "utenti.scrivi"], [])
    with app.test_client() as client:
        _login(client, "delegato", "Delegato12345!")
        client.post(f"/utenti/{delegato.id}/modifica",
                    data={"nome_completo": "Delegato", "email": "delegato@example.it", "ruolo": "AMMINISTRATORE", "attivo": "1"})
        client.post(f"/utenti/{delegato.id}/permessi", data={"permessi_extra": ["admin.configura", "utenti.scrivi"]})
    ricaricato = _gestore(app).get(delegato.id)
    assert ricaricato.ruolo == RuoloUtente.SEGRETERIA
    assert "admin.configura" not in ricaricato.permessi_effettivi
