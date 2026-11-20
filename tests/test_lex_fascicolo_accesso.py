"""Lex legge un fascicolo solo se l'utente può vederlo (art. 32 GDPR; art. 2-quaterdecies D.Lgs. 196/2003)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask, g

FASC = {"F-ALTRUI": SimpleNamespace(id="F-ALTRUI", id_cliente="C-NON-CONDIVISO"),
        "F-CONDIVISO": SimpleNamespace(id="F-CONDIVISO", id_cliente="C-CONDIVISO"),
        "F-SENZA-CLIENTE": SimpleNamespace(id="F-SENZA-CLIENTE", id_cliente="")}


class _Condivisioni:
    def ids_clienti_accessibili(self, _uid):
        return ["C-CONDIVISO"]


@pytest.fixture
def app():
    a = Flask(__name__)
    a.extensions["core_runtime"] = {"get_condivisioni": lambda: _Condivisioni()}
    return a


def _utente(*permessi):
    return SimpleNamespace(id="u1", ha_permesso=lambda p: p in permessi)


def _accesso(fid):
    from lex.fascicolo_accesso import fascicolo_accessibile

    return fascicolo_accessibile(fid, carica=FASC.get)


def test_senza_clienti_leggi_niente_fascicolo_di_cliente_non_condiviso(app):
    with app.test_request_context("/"):
        g.utente_corrente = _utente("fascicoli.leggi")
        assert _accesso("F-ALTRUI") == ""
        assert _accesso("F-CONDIVISO") == "F-CONDIVISO"
        assert _accesso("F-SENZA-CLIENTE") == "F-SENZA-CLIENTE"
        assert _accesso("F-INESISTENTE") == ""


def test_con_clienti_leggi_fascicolo_visibile(app):
    with app.test_request_context("/"):
        g.utente_corrente = _utente("clienti.leggi")
        assert _accesso("F-ALTRUI") == "F-ALTRUI"


def test_errore_nel_controllo_nega(app):
    from lex.fascicolo_accesso import fascicolo_accessibile

    def guasto(_):
        raise RuntimeError("archivio")

    with app.test_request_context("/"):
        g.utente_corrente = _utente("clienti.leggi")
        assert fascicolo_accessibile("F-ALTRUI", carica=guasto) == ""


def test_orchestratore_toglie_il_fascicolo_negato_e_lo_dichiara(app, monkeypatch):
    import lex.fascicolo_accesso as A
    from lex import orchestrator_http as O

    monkeypatch.setattr(A, "_carica_fascicolo", FASC.get)
    domanda = "Entro quando devo depositare le note scritte in questo fascicolo?"
    with app.test_request_context("/"):
        g.utente_corrente = _utente("fascicoli.leggi")
        negato = O._con_fascicolo_controllato({"fascicolo_id": "F-ALTRUI", "question": domanda})
        assert negato["fascicolo_id"] == "" and negato["_fascicolo_negato"]
        p = O._harness_http_payload(domanda, attachments=[], data=negato)
        assert p is not None and "Fascicolo non accessibile" in p["answer"] and "F-ALTRUI" not in p["answer"]
        ammesso = O._con_fascicolo_controllato({"fascicolo_id": "F-CONDIVISO"})
        assert ammesso["fascicolo_id"] == "F-CONDIVISO" and "_fascicolo_negato" not in ammesso
        g.utente_corrente = _utente("clienti.leggi")
        assert O._con_fascicolo_controllato({"fascicolo_id": "F-ALTRUI"})["fascicolo_id"] == "F-ALTRUI"
