"""Test per il client ReGINde."""

import pytest
from pct.reginde import ClientReGINde


@pytest.fixture
def client():
    return ClientReGINde()


def test_cerca_tribunale_milano(client):
    ufficio = client.cerca_ufficio_giudiziario("MILANO")
    assert ufficio is not None
    assert "Milano" in ufficio.nome
    assert ufficio.pec.endswith("@giustiziapec.it")


def test_cerca_tribunale_roma(client):
    ufficio = client.cerca_ufficio_giudiziario("ROMA")
    assert ufficio is not None
    assert "Roma" in ufficio.nome


def test_cerca_tribunale_inesistente(client):
    ufficio = client.cerca_ufficio_giudiziario("PAESE_CHE_NON_ESISTE")
    assert ufficio is None


def test_ottieni_pec_per_codice(client):
    pec = client.ottieni_pec_ufficio("0580010")
    assert pec is not None
    assert "@giustiziapec.it" in pec


def test_ottieni_pec_codice_inesistente(client):
    pec = client.ottieni_pec_ufficio("9999999")
    assert pec is None


def test_elenca_uffici(client):
    uffici = client.elenca_uffici()
    assert len(uffici) > 0


def test_elenca_uffici_per_distretto(client):
    uffici = client.elenca_uffici(distretto="Milano")
    assert all(u.distretto == "Milano" for u in uffici)


def test_cerca_case_insensitive(client):
    ufficio_upper = client.cerca_ufficio_giudiziario("MILANO")
    ufficio_lower = client.cerca_ufficio_giudiziario("milano")
    assert ufficio_upper is not None
    assert ufficio_lower is not None
    assert ufficio_upper.codice == ufficio_lower.codice
