"""Test per il client PEC."""

import pytest
from pct.pec import ClientPEC, ConfigPEC


@pytest.fixture
def config_pec():
    return ConfigPEC(
        indirizzo="test@pec.example.com",
        password="test_password",
        smtp_host="smtp.pec.example.com",
        smtp_port=465,
        imap_host="imap.pec.example.com",
    )


@pytest.fixture
def client(config_pec):
    return ClientPEC(config_pec)


@pytest.mark.parametrize(
    "indirizzo,valido",
    [
        ("avvocato@pec.example.it", True),
        ("studio.legale@pec.it", True),
        ("tribunale.civile.milano@giustizia.it", True),
        ("non_valido", False),
        ("@pec.it", False),
        ("", False),
        ("spazi nel mezzo@pec.it", False),
    ],
)
def test_verifica_indirizzo_pec(client, indirizzo, valido):
    """Verifica la validazione degli indirizzi PEC."""
    assert client.verifica_indirizzo_pec(indirizzo) == valido
