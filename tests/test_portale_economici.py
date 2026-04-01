from pct.portale import PermessiPortale


def test_permessi_portale_attiva_documenti_economici_di_default():
    permessi = PermessiPortale()
    assert permessi.vedi_economici is True


def test_permessi_portale_from_dict_supporta_flag_documenti_economici():
    permessi = PermessiPortale.from_dict({"vedi_economici": False, "vedi_fascicoli": True})
    assert permessi.vedi_economici is False
    assert permessi.vedi_fascicoli is True
