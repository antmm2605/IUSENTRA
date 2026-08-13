"""Fase 5 sync Polisweb: consulta_scadenze sui registri SIECIC/SIGP oltre il SICID.

Fonte certa: cataloghi ministeriali WSDL v1.52 — la classe ``InfoScadenze``
esiste in SICID (catalog_sicc_be.xml), SIECIC (catalog_siecic_be.xml) e SIGP
(catalogJpw.xml) con parametri diversi per famiglia; i cataloghi CASSCI/CASSPE
non la espongono. Qui si verifica che il client costruisca la query con i
parametri del catalogo giusto e che la Cassazione resti esclusa senza errori.
"""

from __future__ import annotations

import pytest

from pct.polisWeb import ClientPolisWeb
from pct.polisweb_sync_job import _fascicolo_sincronizzabile

FUTURO = "2027-03-01"


class _Captura:
    def __init__(self):
        self.classe = None
        self.values = None


@pytest.fixture
def client_catturato(monkeypatch):
    """Client reale con rete mockata: cattura classe e parametri QBuilder."""

    client = ClientPolisWeb()
    captura = _Captura()

    def fake_body(base_pst, codice, classe, values, **kwargs):
        captura.classe = classe
        captura.values = values
        return "<body/>"

    monkeypatch.setattr(client, "_risolvi_codice_ufficio", lambda code: code)
    monkeypatch.setattr(client, "_soap_qbuilder_execute_body", fake_body)
    monkeypatch.setattr(
        client,
        "_execute_qbuilder",
        lambda base, body: (
            '<response><return><row class="InfoScadenze">'
            '<property name="dataScadenza">' + FUTURO + "</property>"
            '<property name="tipoScadenza">Udienza</property>'
            '<property name="descScadenza">Udienza di comparizione</property>'
            "</row></return></response>"
        ),
    )
    return client, captura, monkeypatch


def _base(servizio: str):
    return f"https://pst.example/proxy/{servizio}"


def _params(captura) -> dict:
    return {name: value for name, _tipo, value in captura.values}


def test_sicid_invia_registro_e_ruolo(client_catturato):
    client, captura, mp = client_catturato
    mp.setattr(client, "_risolvi_base_pst", lambda *a, **k: _base("JPW_SICID"))
    eventi = client.consulta_scadenze("0580010", "100", 2026, registro="CC")
    assert captura.classe == "InfoScadenze"
    params = _params(captura)
    assert params["registro"] == "CC"
    assert params["idRuoloJPW"] == "AVV"
    assert "subProcedimento" in params
    assert len(eventi) == 1 and eventi[0].tipo == "udienza"


def test_siecic_invia_registro_e_iddfa_senza_subprocedimento(client_catturato):
    client, captura, mp = client_catturato
    mp.setattr(client, "_risolvi_base_pst", lambda *a, **k: _base("JPW_SIECIC"))
    eventi = client.consulta_scadenze(
        "0580010", "100", 2026, registro="ESIM", id_dfa="DFA-1"
    )
    params = _params(captura)
    assert params["registro"] == "ESIM"
    assert params["idDfa"] == "DFA-1"
    assert "subProcedimento" not in params  # assente dal catalogo SIECIC
    assert len(eventi) == 1


def test_siecic_generico_non_filtra_registro(client_catturato):
    client, captura, mp = client_catturato
    mp.setattr(client, "_risolvi_base_pst", lambda *a, **k: _base("JPW_SIECIC"))
    client.consulta_scadenze("0580010", "100", 2026, registro="SIECIC")
    assert _params(captura)["registro"] == ""


def test_sigp_invia_solo_subprocedimento(client_catturato):
    client, captura, mp = client_catturato
    mp.setattr(client, "_risolvi_base_pst", lambda *a, **k: _base("JPW_SIGP"))
    eventi = client.consulta_scadenze(
        "0580010", "100", 2026, registro="GDP", sub_procedimento="2"
    )
    params = _params(captura)
    assert params["subProcedimento"] == "2"
    assert "registro" not in params  # assenti dal catalogo SIGP
    assert "idDfa" not in params
    assert len(eventi) == 1


def test_cassazione_resta_esclusa(client_catturato):
    client, captura, mp = client_catturato
    mp.setattr(client, "_risolvi_base_pst", lambda *a, **k: _base("JPW_CASSCI"))
    eventi = client.consulta_scadenze("CASS", "100", 2026, registro="CASSCI")
    assert eventi == []
    assert captura.classe is None  # nessuna query costruita


def test_lavoro_usa_catalogo_sicid(client_catturato):
    client, captura, mp = client_catturato
    mp.setattr(client, "_risolvi_base_pst", lambda *a, **k: _base("JPW_SIL_DISTR"))
    client.consulta_scadenze("0580010", "100", 2026, registro="LAV")
    assert _params(captura)["registro"] == "LAV"


# --- Selezione job Fase 3 estesa (Fase 5) ---------------------------------------


def _fascicolo(tipo: str):
    from types import SimpleNamespace

    return SimpleNamespace(
        id="F1", tipo=tipo, numero_rg="100", anno_rg=2026,
        codice_ufficio_portale="0580010", tribunale="MILANO",
        events_sync_enabled=True, stato="APERTO",
    )


def test_job_include_registri_polisweb_ed_esclude_altri_portali():
    for tipo in ("CIVILE", "LAVORO", "FAMIGLIA", "SUCCESSIONI", "ALTRO"):
        assert _fascicolo_sincronizzabile(_fascicolo(tipo)) is True, tipo
    for tipo in ("PENALE", "AMMINISTRATIVO", "TRIBUTARIO", "STRAGIUDIZIALE", "CONSULENZA"):
        assert _fascicolo_sincronizzabile(_fascicolo(tipo)) is False, tipo
