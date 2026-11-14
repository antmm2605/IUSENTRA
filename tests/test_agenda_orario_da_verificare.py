"""Un appuntamento a mezzanotte esatta è un orario non letto, non un'udienza alle 00:00 (verifica del 01/11/2026)."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from web.services.react_agenda_bridge import (
    _agenda_event,
    _enrich_agenda_event_from_fascicolo,
    _etichetta_ora_appuntamento,
    _structured_detail_value,
    build_react_agenda_payload,
)

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


def test_agenda_distingue_le_note_sostitutive_dall_udienza_in_presenza():
    voce = SimpleNamespace(
        id="ag3", titolo="Udienza", tipo="UDIENZA", stato="PROGRAMMATO",
        data_ora="2027-05-25T00:00:00", durata_minuti=60, descrizione="", note="",
        hearing_mode="note_scritte", remote_hearing_detected=True, remote_hearing_pdf_required=True,
    )
    evento = _agenda_event(voce)
    assert evento is not None
    assert evento["legalLabel"] == "Trattazione scritta"
    assert evento["originTitle"] == "Deposito di note scritte in sostituzione dell’udienza"
    assert evento["kind"] == "UDIENZA"
    assert evento["remoteHearingDetected"] is False
    assert evento["remoteHearingPdfRequired"] is False

    voce.hearing_mode = "in_presenza"
    assert _agenda_event(voce)["legalLabel"] == "Udienza"


def test_orario_assente_anche_nella_riga_udienza_della_pec():
    assert _structured_detail_value("Udienza", "10/12/2026 00:00") == "10/12/2026 · Orario da verificare"
    assert _structured_detail_value("Udienza", "10/12/2026 14:00") == "10/12/2026 14:00"


def test_ufficio_generico_in_agenda_usa_il_fascicolo_gia_collegato():
    fascicolo = SimpleNamespace(id="f1", tribunale="Tribunale di Palmi", rg_completo="699/2026")
    event = {"matterId": "f1", "court": "Ufficio giudiziario civile"}
    assert _enrich_agenda_event_from_fascicolo(event, fascicolo)["court"] == "Tribunale di Palmi"

    event["matterId"] = ""
    assert _enrich_agenda_event_from_fascicolo(event, fascicolo)["court"] == "Ufficio giudiziario civile"

    event.update(matterId="f1", court="Tribunale di Vicenza")
    assert _enrich_agenda_event_from_fascicolo(event, fascicolo)["court"] == "Tribunale di Vicenza"


def test_agenda_dettaglio_proietta_il_riscontro_dello_stesso_termine(monkeypatch):
    from web.services import riscontri_processuali_runtime

    voce = SimpleNamespace(
        id="ag4", titolo="Deposito", tipo="DEPOSITO", stato="PROGRAMMATO",
        data_ora="2026-12-01T09:30:00", durata_minuti=15, descrizione="", note="",
        id_fascicolo="F4",
    )
    richieste = []

    def riscontro(fascicolo, giorno, *, titolo, note):
        richieste.append((fascicolo, giorno, titolo))
        return "Busta in attesa dell’esito della cancelleria."

    monkeypatch.setattr(riscontri_processuali_runtime, "riscontro_note_scritte", riscontro)
    payload = build_react_agenda_payload(
        lambda: SimpleNamespace(tutti=lambda: [voce], get=lambda _: voce),
        lambda: SimpleNamespace(tutte=lambda: []),
        from_value="2026-11-13", to_value="2026-11-13", selected_id="ag4",
    )
    assert richieste == [("F4", "2026-12-01", "Deposito")]
    assert payload["events"][0]["proceduralFinding"] == "Busta in attesa dell’esito della cancelleria."
