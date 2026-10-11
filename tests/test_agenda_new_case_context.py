from inspect import signature
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask
import pytest

from web.bootstrap import dashboard_routes as routes


def test_case_agenda_explicit_link_does_not_depend_on_text_or_match_another_case():
    from web.services.react_fascicoli_bridge import _agenda_for_fascicolo, _appointments

    own = SimpleNamespace(id="OWN", id_fascicolo="CASE1", titolo="Collaudo")
    other = SimpleNamespace(id="OTHER", id_fascicolo="CASE2", titolo="RG 123/2026")
    agenda = SimpleNamespace(tutti=lambda: [own, other])
    case = SimpleNamespace(id="CASE1", numero_rg="123", anno_rg="2026")
    assert _agenda_for_fascicolo(lambda: agenda, case) == [own]
    assert _appointments([own])[0]["href"] == "/agenda/OWN"


@pytest.mark.parametrize("available", [True, False])
def test_new_appointment_preserves_only_current_studio_case(monkeypatch, available):
    app = Flask(__name__)
    app.secret_key = "controlled-test"
    agenda = Mock()
    agenda.aggiungi.return_value = SimpleNamespace(id="EVENT1", titolo="Prova")
    cases = Mock()
    cases.get.return_value = SimpleNamespace(id="CASE1") if available else None
    dependencies = {name: Mock() for name in signature(routes.register_dashboard_routes).parameters if name != "app"}
    dependencies.update(get_agenda=lambda: agenda, get_fascicoli=lambda: cases)
    monkeypatch.setattr(routes, "_agenda_non_autorizzato", lambda permission: None)
    monkeypatch.setattr(routes, "richiede_json", lambda: True)
    routes.register_dashboard_routes(app, **dependencies)
    response = app.test_client().post("/agenda/nuovo", data={
        "titolo": "Prova", "tipo": "UDIENZA", "data": "2026-10-20",
        "id_fascicolo": "CASE1",
    })
    cases.get.assert_called_once_with("CASE1")
    if available:
        assert response.status_code == 200
        assert agenda.aggiungi.call_args.kwargs["id_fascicolo"] == "CASE1"
    else:
        assert response.status_code == 404
        agenda.aggiungi.assert_not_called()
