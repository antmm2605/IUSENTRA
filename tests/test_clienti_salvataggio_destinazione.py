"""Dopo «Salva modifiche» la scheda cliente non butta fuori chi sta correggendo.

La scheda React e' la stessa per creazione e modifica. Il salvataggio navigava
sempre: in creazione va bene — si finisce nella cartella del cliente appena
nato — in modifica no, perche' l'avvocato che sta correggendo una scheda
doveva rientrare nel modulo a ogni salvataggio.
"""

from __future__ import annotations

from pct.clienti import TipoCliente
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from web.app import create_app
from web.helpers import get_clienti

DATI = {
    "tipo": TipoCliente.PERSONA_FISICA.value,
    "nome": "Mario",
    "cognome": "Rossi",
    "codice_fiscale": "RSSMRA80A01H501U",
}


def _cliente(app):
    with app.app_context():
        return get_clienti().nuovo(
            TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi",
            codice_fiscale="RSSMRA80A01H501U",
        )


def _salva(client, id_cliente: str, **extra):
    return client.post(
        f"/clienti/{id_cliente}/modifica",
        data={**DATI, **extra},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )


def test_la_modifica_non_manda_da_nessuna_parte(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    cliente = _cliente(app)
    with app.test_client() as client:
        _login(client)
        risposta = _salva(client, cliente.id)
    corpo = risposta.get_json() or {}
    assert corpo.get("ok") is True, corpo
    assert not corpo.get("redirect"), "in modifica l'avvocato deve restare sulla scheda"
    assert corpo.get("message") == "Modifiche salvate."


def test_la_modifica_aperta_da_un_altra_pagina_torna_li(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    cliente = _cliente(app)
    with app.test_client() as client:
        _login(client)
        risposta = _salva(client, cliente.id, next_url="/fascicoli/5E864356/modifica")
    corpo = risposta.get_json() or {}
    assert corpo.get("redirect") == "/fascicoli/5E864356/modifica"


def test_un_ritorno_fuori_dal_gestionale_non_viene_seguito(tmp_path):
    """Il momento in cui l'utente uscirebbe e' subito dopo un salvataggio riuscito.

    E' quando si fida di quello che vede: un `next_url` confezionato ad arte
    non deve portarlo via. La regola e' una sola per tutto il gestionale
    (`web.services.app_v2_routing.is_safe_internal_path`).
    """
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    cliente = _cliente(app)
    ostili = [
        "https://esterno.example/x",
        "//esterno.example",
        "/\\esterno.example",
        "/\tevil",
        "/a/../../etc/passwd",
    ]
    with app.test_client() as client:
        _login(client)
        for ostile in ostili:
            corpo = _salva(client, cliente.id, next_url=ostile).get_json() or {}
            assert not corpo.get("redirect"), f"seguito un ritorno ostile: {ostile}"


def test_la_regola_del_ritorno_interno_e_una_sola():
    """Tre copie della stessa regola si disallineano: due erano gia' piu' deboli."""
    from web.bootstrap.soggetti_routes import _safe_internal_next_url
    from web.services.react_clienti_bridge import _safe_internal_path

    for ostile in ("https://esterno.example/x", "//esterno.example", "/\\esterno.example", "/\tevil"):
        assert _safe_internal_path(ostile) == "", f"bridge clienti accetta {ostile!r}"
        assert _safe_internal_next_url(ostile) == "", f"rotte soggetti accettano {ostile!r}"
    assert _safe_internal_path("/fascicoli/X") == "/fascicoli/X"
    assert _safe_internal_next_url("/fascicoli/X") == "/fascicoli/X"
