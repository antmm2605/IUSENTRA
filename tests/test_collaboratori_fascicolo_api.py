"""API JSON dei collaboratori del fascicolo (sostituiscono la pagina classica collaboratori_fascicolo.html)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pct.auth import GestioneUtenti, RuoloUtente
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_condivisioni import _seed_condivisioni
from tests.test_react_shell import _app


def _gestore_utenti(app) -> GestioneUtenti:
    return GestioneUtenti(
        db_path=app.config["AUTH_DB"],
        audit_path=app.config["AUDIT_DB"],
        secret_key=app.secret_key,
        bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
        bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
    )


def _crea_utente(app, username: str, ruolo: RuoloUtente) -> str:
    with app.app_context():
        utente = _gestore_utenti(app).crea(
            username=username,
            password="Collaudo123!",
            ruolo=ruolo,
            email=f"{username}@example.it",
            nome_completo=f"Profilo {username}",
            must_change_password=False,
        )
    return utente.id


def _audit(app) -> str:
    path = Path(app.config["AUDIT_DB"])
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_collaboratori_fascicolo_api_elenco_condivisione_revoca_e_audit(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    id_collega = _crea_utente(app, "collega", RuoloUtente.AVVOCATO)
    _cliente, fascicolo = _seed_condivisioni(app)
    base = f"/api/v1/fascicoli/{fascicolo.id}/collaboratori"

    with app.test_client() as client:
        _login(client)
        vecchia = client.get(f"/fascicoli/{fascicolo.id}/collaboratori")
        elenco = client.get(base).get_json()
        passato = client.post(base, json={"id_utente": id_collega, "data_scadenza": "2020-01-01"})
        ruolo_errato = client.post(base, json={"id_utente": id_collega, "ruolo": "PADRONE"})
        scadenza = (datetime.now(ZoneInfo("Europe/Rome")).date() + timedelta(days=30)).isoformat()
        condiviso = client.post(
            base,
            json={"id_utente": id_collega, "ruolo": "scrittura", "data_scadenza": scadenza, "tags": "udienza, CTU", "note": "Udienza"},
        )
        dopo = client.get(base).get_json()
        revoca = client.delete(f"{base}/{id_collega}")
        revoca_doppia = client.delete(f"{base}/{id_collega}")
        finale = client.get(base).get_json()
        assente = client.get("/api/v1/fascicoli/inesistente/collaboratori")

    assert vecchia.status_code == 302
    assert vecchia.headers["Location"].endswith(f"/fascicoli/{fascicolo.id}#collaboratori-fascicolo")
    assert elenco["matter"]["id"] == fascicolo.id
    assert [voce["idUser"] for voce in elenco["collaborators"]] == ["collab-1"]
    assert id_collega in {voce["id"] for voce in elenco["availableUsers"]}
    assert "operatore" not in {voce["username"] for voce in elenco["availableUsers"]}
    assert passato.status_code == 400
    assert ruolo_errato.status_code == 400
    assert condiviso.status_code == 201
    nuovo = next(voce for voce in dopo["collaborators"] if voce["idUser"] == id_collega)
    assert nuovo["role"] == "SCRITTURA"
    assert nuovo["tags"] == ["udienza", "CTU"]
    assert nuovo["deadline"] == scadenza
    assert id_collega not in {voce["id"] for voce in dopo["availableUsers"]}
    assert revoca.status_code == 200
    assert revoca_doppia.status_code == 404
    assert id_collega not in {voce["idUser"] for voce in finale["collaborators"]}
    assert assente.status_code == 404
    registro = _audit(app)
    assert "condivisione.fascicolo.condividi" in registro
    assert "condivisione.fascicolo.revoca" in registro


def test_collaboratori_fascicolo_api_richiede_permesso_di_gestione(tmp_path: Path):
    """Senza fascicoli.scrivi serve il ruolo GESTORE sul fascicolo, come nella pagina classica."""
    from pct.condivisione import RuoloCondivisione

    app = _app(tmp_path)
    _crea_operatore(app)
    id_praticante = _crea_utente(app, "praticante", RuoloUtente.PRATICANTE)
    _cliente, fascicolo = _seed_condivisioni(app)
    base = f"/api/v1/fascicoli/{fascicolo.id}/collaboratori"

    with app.test_client() as anonimo:
        assert anonimo.get(base, headers={"Accept": "application/json"}).status_code == 401

    def _accedi(client):
        response = client.post("/login", data={"username": "praticante", "password": "Collaudo123!"}, follow_redirects=True)
        assert response.status_code == 200

    with app.test_client() as client:
        _accedi(client)
        negato = [client.get(base), client.post(base, json={"id_utente": "collab-1"}), client.delete(f"{base}/collab-1")]
    assert [risposta.status_code for risposta in negato] == [403, 403, 403]

    with app.app_context():
        app.extensions["core_runtime"]["get_condivisioni"]().condividi_fascicolo(
            id_fascicolo=fascicolo.id,
            id_cliente=fascicolo.id_cliente,
            id_utente=id_praticante,
            username="praticante",
            nome_completo="Profilo praticante",
            ruolo=RuoloCondivisione.GESTORE,
            condiviso_da="operatore",
        )
    with app.test_client() as client:
        _accedi(client)
        gestore = client.get(base)
    assert gestore.status_code == 200
    assert id_praticante not in {voce["id"] for voce in gestore.get_json()["availableUsers"]}
