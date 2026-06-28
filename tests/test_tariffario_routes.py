import re

from werkzeug.datastructures import MultiDict

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


def _parse_euro_label(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def _extract_totale_compenso_base(html: str) -> float:
    match = re.search(
        r"Totale compenso</th>\s*"
        r"<th[^>]*>€ ([0-9.]+,[0-9]{2})</th>\s*"
        r"<th[^>]*>€ ([0-9.]+,[0-9]{2})</th>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    assert match, "Totale compenso non trovato nel markup del tariffario"
    return _parse_euro_label(match.group(2))


def _extract_totale_operativo(html: str) -> float:
    match = re.search(
        r"border-top pt-1 text-primary\">€ ([0-9.]+,[0-9]{2})</div>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    assert match, "Totale operativo non trovato nel markup del tariffario"
    return _parse_euro_label(match.group(1))


def test_tariffario_route_rispetta_toggle_spese_generali(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    data_base = [
        ("materia", Materia.CIVILE_COGN.value),
        ("grado", Grado.TRIBUNALE.value),
        ("complessita", "media"),
        ("valore", "10000"),
        ("fasi", "studio"),
        ("fasi", "introduttiva"),
        ("fasi", "istruttoria"),
        ("fasi", "decisionale"),
        ("perc_spese_generali", "15"),
    ]

    with app.test_client() as client:
        _login(client)
        senza_spese = client.post(
            "/tariffario",
            data=MultiDict(data_base + [("spese_generali", "0")]),
            follow_redirects=True,
        )
        con_spese = client.post(
            "/tariffario",
            data=MultiDict(data_base + [("spese_generali", "0"), ("spese_generali", "1")]),
            follow_redirects=True,
        )

    html_senza_spese = senza_spese.get_data(as_text=True)
    html_con_spese = con_spese.get_data(as_text=True)

    assert senza_spese.status_code == 200
    assert con_spese.status_code == 200
    assert ">Spese generali<" not in html_senza_spese
    assert ">Spese generali<" in html_con_spese
    assert "Motore di calcolo attivo" in html_senza_spese
    assert "Spese generali escluse dal totale." in html_senza_spese
    assert "Spese generali incluse nel totale." in html_con_spese
    assert _extract_totale_compenso_base(html_con_spese) > _extract_totale_compenso_base(html_senza_spese)


def test_tariffario_route_mediazione_odm_incide_sul_totale(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    data_base = [
        ("materia", Materia.MEDIAZIONE.value),
        ("grado", Grado.PROCEDURA_ADR.value),
        ("complessita", "media"),
        ("valore", "10000"),
        ("perc_spese_generali", "15"),
    ]

    with app.test_client() as client:
        _login(client)
        senza_odm = client.post(
            "/tariffario",
            data=MultiDict(data_base),
            follow_redirects=True,
        )
        con_odm = client.post(
            "/tariffario",
            data=MultiDict(
                data_base
                + [
                    ("mediazione_odm_attiva", "1"),
                    ("mediazione_odm_regime", "volontaria"),
                    ("mediazione_odm_esito", "primo_incontro_senza_accordo"),
                ]
            ),
            follow_redirects=True,
        )

    html_senza_odm = senza_odm.get_data(as_text=True)
    html_con_odm = con_odm.get_data(as_text=True)

    assert senza_odm.status_code == 200
    assert con_odm.status_code == 200
    assert "Mediazione civile - costi organismo D.M. 150/2023" in html_con_odm
    assert _extract_totale_operativo(html_con_odm) > _extract_totale_operativo(html_senza_odm)
