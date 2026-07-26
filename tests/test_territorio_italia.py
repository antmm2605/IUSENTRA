from __future__ import annotations

from scripts.audit_territorio_italia_db import audit
from pct.territorio_italia import DEFAULT_TERRITORIO_DB, get_comune, search_comuni, territorio_stats
from tests.test_react_shell import _app
from web.services.territorio_forms import normalize_address_fields, resolve_comune_italiano


def test_territorio_italia_db_copre_tutti_i_comuni_cap_province():
    result = audit(DEFAULT_TERRITORIO_DB)

    assert result["ok"] is True
    assert result["comuni"] == 7894
    assert result["comuni_con_cap"] == 7894
    assert result["comuni_con_provincia"] == 7894
    assert result["coverage_comuni_pct"] == 100.0
    assert result["coverage_cap_pct"] == 100.0


def test_territorio_italia_cerca_comune_con_cap_e_valore_giustizia_map():
    comuni = search_comuni("Palmi")
    palmi = next(comune for comune in comuni if comune.nome == "Palmi")

    assert palmi.codice_istat == "080057"
    assert palmi.sigla_provincia == "RC"
    assert "89015" in palmi.cap
    assert palmi.giustizia_map_value == "18080057#Palmi"
    assert territorio_stats()["comuni"] == 7894


def test_api_territorio_comuni_restituisce_lista_per_autocomplete(tmp_path):
    app = _app(tmp_path)

    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/territorio/comuni?q=Palmi",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    palmi = next(item for item in payload["items"] if item["nome"] == "Palmi")
    assert palmi["codiceIstat"] == "080057"
    assert palmi["siglaProvincia"] == "RC"
    assert "89015" in palmi["cap"]


def test_get_comune_da_codice_istat():
    palmi = get_comune(codice_istat="080057")

    assert palmi is not None
    assert palmi.label == "Palmi (RC)"


def test_normalizza_indirizzo_compila_cap_e_provincia_da_comune():
    indirizzo = normalize_address_fields(comune="Maddaloni", cap="", provincia="")

    assert indirizzo["comune"] == "Maddaloni"
    assert indirizzo["provincia"] == "CE"
    assert indirizzo["cap"] == "81024"


def test_resolve_comune_accetta_label_autocomplete():
    comune = resolve_comune_italiano("Maddaloni (CE)")

    assert comune is not None
    assert comune.nome == "Maddaloni"
    assert comune.sigla_provincia == "CE"


def test_resolve_comune_ignora_parentesi_non_provincia():
    assert resolve_comune_italiano("Maddaloni (Centro)") is None
