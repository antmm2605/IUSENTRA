"""Documento d'identità collegato al cliente solo con identità congiunta: nome + codice fiscale o data di nascita."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.document_intelligence.catalog_identita_personale import (
    codici_fiscali_letti,
    date_lette,
    riscontro_identita,
)
from web.services import identita_cliente_runtime
from web.services.identita_cliente_runtime import identita_del_cliente

CARTA = ("REPUBBLICA ITALIANA CARTA D'IDENTITA' Cognome ROSSI Nome MARIO nato il 01/01/1980 a ROMA "
         "Codice fiscale RSSMRA80A01H501U Comune di Roma")


def test_codici_fiscali_e_date_lette():
    assert codici_fiscali_letti(CARTA) == {"RSSMRA80A01H501U"}
    assert codici_fiscali_letti("RSSMRA80A01H501A") == set()        # controllo errato
    assert date_lette("nato il 01/01/1980, scade 31.02.2030") == {"1980-01-01"}


@pytest.mark.parametrize("cf, nascita, esito", [
    ("RSSMRA80A01H501U", "", "concorde"),
    ("rssmra80a01h501u", "", "concorde"),
    ("RSSMRA80A01H50MM", "", "concorde"),            # forma omocodica dello stesso codice
    ("BNCNNA75E60F205I", "1980-01-01", "discordante"),  # CF diverso prevale sulla data
    ("", "1980-01-01", "concorde"),
    ("", "1975-05-20", "da_verificare"),
    ("", "", "da_verificare"),
])
def test_riscontro_identita(cf, nascita, esito):
    assert riscontro_identita(CARTA, codice_fiscale=cf, data_nascita=nascita)["esito"] == esito


def test_senza_codice_fiscale_nel_documento_vale_la_data():
    testo = "CARTA D'IDENTITA' Cognome ROSSI Nome MARIO nato il 01/01/1980"
    assert riscontro_identita(testo, codice_fiscale="RSSMRA80A01H501U", data_nascita="1980-01-01")["esito"] == "concorde"
    assert riscontro_identita(testo, codice_fiscale="RSSMRA80A01H501U")["esito"] == "da_verificare"


def test_identita_del_cliente(monkeypatch):
    import web.helpers as helpers

    cliente = SimpleNamespace(nome_completo="Rossi Mario", codice_fiscale="RSSMRA80A01H501U", data_nascita="1980-01-01")
    monkeypatch.setattr(helpers, "get_clienti", lambda: SimpleNamespace(get=lambda cid: cliente if cid == "C-1" else None))
    fascicolo = SimpleNamespace(id_cliente="C-1", nome_cliente="Rossi")
    assert identita_del_cliente(fascicolo) == {"id": "C-1", "nome": "Rossi Mario", "codice_fiscale": "RSSMRA80A01H501U",
                                               "data_nascita": "1980-01-01"}
    assert identita_del_cliente(SimpleNamespace(id_cliente="C-2", nome_cliente="Verdi"))["codice_fiscale"] == ""
    assert identita_del_cliente(SimpleNamespace(id_cliente="", nome_cliente="Verdi"))["nome"] == "Verdi"

    def guasto():
        raise RuntimeError("archivio")

    monkeypatch.setattr(helpers, "get_clienti", guasto)
    assert identita_del_cliente(fascicolo)["nome"] == "Rossi"
    assert identita_cliente_runtime.__all__ if hasattr(identita_cliente_runtime, "__all__") else True
