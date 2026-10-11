"""Il rinvio usa il collegamento persistente, senza inferire un R.G. dalle date."""
from types import SimpleNamespace

import pytest

from pct.agenda import Appuntamento, TipoAppuntamento
from pct.fascicoli import Fascicolo, TipoFascicolo
from web.services.preparazione_udienza_associazione import fascicolo_udienza
from web.services.react_agenda_bridge import _extract_rg, build_react_agenda_payload


def test_hearing_dates_are_not_case_numbers():
    assert _extract_rg("Rinvio disposto all'udienza del 11/10/2026") == ""
    assert _extract_rg("Udienza 11 / 10 / 2026; RG 2313/2025") == "RG 2313/2025"
    assert _extract_rg("Udienza fascicolo 2313/2025") == "RG 2313/2025"


@pytest.mark.parametrize("state", ["completato", "archiviato"])
def test_postponed_hearing_uses_persistent_preparation_link(state):
    app = Appuntamento("R1", "Udienza di rinvio", TipoAppuntamento.UDIENZA,
                       "2026-12-16T09:00:00", 60, "Aula controllata",
                       note="Rinvio disposto all'udienza del 11/10/2026")
    case = Fascicolo("F1", "2026/001", "Caso controllato", TipoFascicolo.CIVILE)
    session = SimpleNamespace(id_appuntamento="A1", id_appuntamento_rinvio="R1",
                              id_fascicolo="F1", stato=state)
    assert fascicolo_udienza(app, [case], [session]) is case
    payload = build_react_agenda_payload(
        lambda: SimpleNamespace(tutti=lambda: [app]),
        lambda: SimpleNamespace(tutte=lambda **kwargs: []),
        lambda: SimpleNamespace(get=lambda key: case if key == case.id else None),
        from_value="2026-12-14", to_value="2026-12-20",
        preparazioni_loader=lambda: SimpleNamespace(lista=lambda: [session]),
    )
    row = payload["events"][0]
    assert row["matterId"] == "F1"
    assert row["matter"] == "2026/001"
    assert "10/2026" not in row["subtitle"]


def test_preparation_link_does_not_hide_conflicting_client():
    app = Appuntamento("R1", "Udienza di rinvio", TipoAppuntamento.UDIENZA,
                       "2026-12-16T09:00:00", 60, "Aula controllata", id_cliente="C2")
    case = Fascicolo("F1", "2026/001", "Caso controllato", TipoFascicolo.CIVILE, id_cliente="C1")
    session = SimpleNamespace(id_appuntamento="A1", id_appuntamento_rinvio="R1", id_fascicolo="F1")
    with pytest.raises(ValueError, match="discordante"):
        build_react_agenda_payload(
            lambda: SimpleNamespace(tutti=lambda: [app]),
            lambda: SimpleNamespace(tutte=lambda **kwargs: []),
            lambda: SimpleNamespace(get=lambda key: case),
            from_value="2026-12-14", to_value="2026-12-20",
            preparazioni_loader=lambda: SimpleNamespace(lista=lambda: [session]),
        )
