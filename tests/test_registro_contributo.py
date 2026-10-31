"""Registro del contributo unificato: dovuto, pagato, art. 30, esenzione e differenza (art. 16)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.registro_contributo import dovuto_del_fascicolo, registro_contributo
from pct.strumenti_legali import GestioneStrumentiLegali
from web.services import contributo_registro_runtime
from web.services.contributo_registro_runtime import registro_del_fascicolo


@pytest.fixture(scope="module")
def calcolatore():
    return GestioneStrumentiLegali()


def _fascicolo(**campi):
    base = {"id": "F-1", "id_pratica": "atto_citazione", "valore_causa": 30000.0, "tribunale": "Tribunale di Milano",
            "pagamenti": {}}
    base.update(campi)
    return SimpleNamespace(**base)


def test_dovuto_dal_valore_e_dalla_tipologia(calcolatore):
    assert dovuto_del_fascicolo(_fascicolo(), calcolatore) == (518.0, "art. 13 D.P.R. 115/2002, valore € 30.000,00")
    dovuto, motivo = dovuto_del_fascicolo(_fascicolo(valore_causa=0), calcolatore)
    assert dovuto is None and "art. 14" in motivo
    assert dovuto_del_fascicolo(_fascicolo(id_pratica="accesso_atti", valore_causa=0), calcolatore)[0] == 300.0
    assert dovuto_del_fascicolo(_fascicolo(id_pratica="procedimenti_famiglia"), calcolatore)[0] is None
    assert dovuto_del_fascicolo(_fascicolo(valore_causa="non numerico"), calcolatore)[0] is None

    class Guasto:
        def calcola_contributo_unificato(self, payload):
            raise ValueError("tipologia")

    assert dovuto_del_fascicolo(_fascicolo(), Guasto())[0] is None


@pytest.mark.parametrize("voce, dovuto, stato, differenza", [
    ({"status": "pagato", "importo": 518, "art_30": 27}, 518.0, "pagato", 0.0),
    ({"status": "pagato", "importo": 259}, 518.0, "insufficiente", 259.0),
    ({"status": "pagato", "importo": 600}, 518.0, "pagato", 0.0),
    ({"pagato": True, "importo": 98}, None, "pagato_da_verificare", None),
    ({"status": "da_registrare"}, 518.0, "da_pagare", 518.0),
    (None, None, "da_pagare", None),
    ({"status": "esente"}, 518.0, "esente", None),
    ({"esente": True}, None, "esente", None),
    ({"status": "prenotato_a_debito"}, 518.0, "prenotato_a_debito", None),
    ({"prenotato_a_debito": True}, None, "prenotato_a_debito", None),
])
def test_stati_del_registro(voce, dovuto, stato, differenza):
    registro = registro_contributo(voce, dovuto=dovuto, base_dovuto="base")
    assert registro.stato == stato and registro.differenza == differenza


def test_avvisi_insufficiente_eccedenza_art_30():
    insufficiente = registro_contributo({"status": "pagato", "importo": 259, "art_30": "x"}, dovuto=518.0)
    assert "€ 259,00" in insufficiente.avvisi[0] and "art. 16" in insufficiente.avvisi[0] and insufficiente.art_30 == 0.0
    eccedenza = registro_contributo({"status": "pagato", "importo": 545}, dovuto=518.0)
    assert "oltre il dovuto" in eccedenza.avvisi[0]
    senza_dovuto = registro_contributo({}, dovuto=None, base_dovuto="Valore non indicato")
    assert senza_dovuto.avvisi == ["Valore non indicato"] and senza_dovuto.to_dict()["stato"] == "da_pagare"


def test_runtime_registro_e_errori(monkeypatch):
    fascicolo = _fascicolo(pagamenti={"contributo_unificato": {"status": "pagato", "importo": 259}})
    registro = registro_del_fascicolo(fascicolo)
    assert registro["stato"] == "insufficiente" and registro["dovuto"] == 518.0

    def guasto():
        raise RuntimeError("tabelle")

    monkeypatch.setattr(contributo_registro_runtime, "_calcolatore", guasto)
    assert registro_del_fascicolo(fascicolo) == {}


def test_calcolatore_caricato_una_volta(monkeypatch):
    monkeypatch.setattr(contributo_registro_runtime, "_CALCOLATORE", None)
    primo = contributo_registro_runtime._calcolatore()
    assert contributo_registro_runtime._calcolatore() is primo
