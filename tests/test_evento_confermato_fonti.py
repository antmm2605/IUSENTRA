from datetime import date

import pytest

from lex.normativa.applicabilita import data_evento_confermato


@pytest.mark.parametrize("value", [
    {"confermato": True, "data": "2026-02-30", "fonte_sha256": "a" * 64},
    {"confermato": True, "data": "2026-10-26", "fonte_sha256": "si"},
    {"confermato": True, "data": "2026-10-26", "fonte_sha256": "z" * 64},
    {"confermato": False, "data": "2026-10-26", "fonte_sha256": "a" * 64},
    {"confermato": True, "fonte_sha256": "a" * 64},
    "2026-10-26",
])
def test_evento_non_provato_non_diventa_data_di_acquisizione(value):
    assert data_evento_confermato({"notifica": value}, "notifica") is None


def test_evento_confermato_valido_restituisce_data_esatta():
    assert data_evento_confermato({"notifica": {
        "confermato": True, "data": "2026-10-26", "fonte_sha256": "a" * 64,
    }}, "notifica") == date(2026, 10, 26)
