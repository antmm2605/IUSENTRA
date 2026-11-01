"""Un appuntamento a mezzanotte esatta è un orario non letto, non un'udienza alle 00:00 (verifica del 01/11/2026)."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from web.services.react_agenda_bridge import _agenda_event, _etichetta_ora_appuntamento

ROMA = ZoneInfo("Europe/Rome")


def test_mezzanotte_esatta_e_orario_da_verificare():
    assert _etichetta_ora_appuntamento(datetime(2026, 10, 29, 0, 0, tzinfo=ROMA)) == "Orario da verificare"
    assert _etichetta_ora_appuntamento(datetime(2026, 10, 29, 9, 30, tzinfo=ROMA)) == "09:30"
    assert _etichetta_ora_appuntamento(datetime(2026, 10, 29, 0, 15, tzinfo=ROMA)) == "00:15"


def test_evento_dell_agenda_senza_ora_letta():
    voce = SimpleNamespace(
        id="ag1", titolo="Fissazione udienza", tipo="UDIENZA", stato="PROGRAMMATO",
        data_ora="2026-10-29T00:00:00", durata_minuti=60, descrizione="", note="",
    )
    evento = _agenda_event(voce)
    assert evento is not None
    assert evento["timeLabel"] == "Orario da verificare"


def test_l_orario_scritto_nella_pec_prevale_sulla_mezzanotte():
    voce = SimpleNamespace(
        id="ag2", titolo="Fissazione udienza", tipo="UDIENZA", stato="PROGRAMMATO",
        data_ora="2026-10-29T00:00:00", durata_minuti=60,
        descrizione="Comunicazione di cancelleria da PEC: udienza fissata al 29/10/2026 ore 10:30", note="",
    )
    evento = _agenda_event(voce)
    assert evento is not None
    assert evento["timeLabel"] == "10:30"
