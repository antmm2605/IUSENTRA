from pct.auth import GestioneUtenti, RuoloUtente
from pct.tariffario import Grado, Materia
from web.app import create_app

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def _crea_admin(app) -> None:
    with app.app_context():
        gestore = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
            bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
        )
        if not any(user.username == "operatore" for user in gestore.tutti()):
            gestore.crea(
                username="operatore",
                password="Operatore123!",
                ruolo=RuoloUtente.AMMINISTRATORE,
                email="operatore@example.it",
                nome_completo="Operatore Tariffario",
                must_change_password=False,
            )


def _login(client) -> None:
    response = client.post(
        "/login",
        data={"username": "operatore", "password": "Operatore123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def _euro(value: str) -> float:
    return float(value.replace("€", "").replace(".", "").replace(",", ".").strip())


def _calcola(client, **campi) -> dict:
    """Calcolo dalla pagina React del tariffario (stesso motore della vecchia pagina Jinja)."""
    stato = dict(client.get("/api/v1/ui/tariffario").get_json()["state"])
    stato.update(campi)
    risposta = client.post("/api/v1/ui/tariffario/calcola", json=stato)
    assert risposta.status_code == 200
    corpo = risposta.get_json()
    assert corpo["ok"] is True, corpo
    return corpo


def test_tariffario_route_rispetta_toggle_spese_generali(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    base = {
        "materia": Materia.CIVILE_COGN.value,
        "grado": Grado.TRIBUNALE.value,
        "complessita": "media",
        "valore": "10000",
        "fasi": ["Studio", "Introduttiva", "Istruttoria / Istruzione", "Decisionale"],
        "perc_spese_generali": "15",
    }
    with app.test_client() as client:
        _login(client)
        senza_spese = _calcola(client, **base, spese_generali="0")
        con_spese = _calcola(client, **base, spese_generali="1")

    assert "Spese generali 15%" not in str(senza_spese["result"])
    assert "Spese generali 15%" in str(con_spese["result"])
    assert _euro(con_spese["result"]["selectedTotal"]) > _euro(senza_spese["result"]["selectedTotal"])


def test_tariffario_route_mediazione_odm_incide_sul_totale(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    base = {
        "materia": Materia.MEDIAZIONE.value,
        "grado": Grado.PROCEDURA_ADR.value,
        "complessita": "media",
        "valore": "10000",
        "perc_spese_generali": "15",
    }
    with app.test_client() as client:
        _login(client)
        senza_odm = _calcola(client, **base, mediazione_odm_attiva="0")
        con_odm = _calcola(
            client,
            **base,
            mediazione_odm_attiva="1",
            mediazione_odm_regime="volontaria",
            mediazione_odm_esito="primo_incontro_senza_accordo",
        )

    assert "Costi organismo mediazione D.M. 150/2023" in str(con_odm)
    assert "Costi organismo mediazione D.M. 150/2023" not in str(senza_odm)
    assert con_odm["economicRaw"]["totale"] > senza_odm["economicRaw"]["totale"]
