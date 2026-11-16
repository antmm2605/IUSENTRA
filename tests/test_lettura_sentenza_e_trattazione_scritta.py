"""Lettura del fascicolo dopo la sentenza e con l'udienza sostituita da note scritte.

- La sentenza comunicata dalla cancelleria con PEC (art. 133 c.p.c.; art. 16, c. 4, D.L. 179/2012) porta la
  fase a «decisa» anche se non è fra i documenti: nessuna udienza da preparare.
- Con la trattazione scritta (art. 127-ter c.p.c.) non c'è discussione da preparare: il passo è il deposito
  delle note, una volta sola.
- Il riquadro «Udienze e scadenze» del presidio mostra la prossima scadenza futura, mai un rinvio trascorso.
Esempi costruiti, nessun dato reale.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from pct.fascicolo_lettura import costruisci_lettura
from tests.test_fascicolo_lettura import OGGI, _caso_completo, _pec_messaggio


def test_sentenza_comunicata_via_pec_porta_la_fase_a_decisa_senza_udienza_da_preparare():
    dati = _caso_completo()
    dati.pec = [_pec_messaggio(subject="Deposito sentenza RG 1234/2026", eventi=[
        {"primary_event": "deposito_sentenza", "family": "cancelleria", "priority": "alta", "human_review_required": 0}])]
    lettura = costruisci_lettura(dati)
    assert lettura["fase"]["codice"] == "decisa"
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert not any(azione.startswith("Preparare l'udienza") for azione in azioni)
    assert any(azione.startswith("Valutare l'impugnazione") for azione in azioni)


def test_evento_sentenza_ancora_da_confermare_non_cambia_la_fase():
    dati = _caso_completo()
    dati.pec = [_pec_messaggio(eventi=[{"primary_event": "deposito_sentenza", "family": "cancelleria", "priority": "alta",
                                         "human_review_required": 1}])]
    assert costruisci_lettura(dati)["fase"]["codice"] != "decisa"


def test_udienza_sostituita_da_note_scritte_non_propone_la_discussione():
    dati = _caso_completo()
    giorno = (OGGI + timedelta(days=20)).isoformat()
    dati.scadenze = [
        {"id": "SC2", "titolo": "Udienza di discussione", "data": giorno, "stato": "APERTO"},
        {"id": "SC3", "titolo": "Riassegnazione termine per note scritte", "data": giorno, "stato": "APERTO"},
    ]
    azioni = [passo["azione"] for passo in costruisci_lettura(dati)["prossimi_passi"]]
    assert not any(azione.startswith("Preparare l'udienza") for azione in azioni)


def test_udienza_in_presenza_resta_da_preparare():
    azioni = [passo["azione"] for passo in costruisci_lettura(_caso_completo())["prossimi_passi"]]
    assert any(azione.startswith("Preparare l'udienza") for azione in azioni)


def test_presidio_mostra_prima_le_scadenze_future_poi_le_trascorse(monkeypatch):
    import web.services.react_fascicoli_bridge as bridge

    monkeypatch.setattr(bridge, "oggi_rome", lambda: OGGI)
    scadenze = [SimpleNamespace(id=i, titolo=t, data_scadenza=d, tipo="", priorita="", stato="APERTO", perentorio=False, note="")
                for i, t, d in (("R", "Rinvio udienza", (OGGI - timedelta(days=27)).isoformat()),
                                ("N", "Termine note", (OGGI + timedelta(days=1)).isoformat()),
                                ("V", "Vecchia", (OGGI - timedelta(days=60)).isoformat()),
                                ("U", "Udienza", (OGGI + timedelta(days=30)).isoformat()))]
    assert [voce["id"] for voce in bridge._deadlines(scadenze)] == ["N", "U", "R", "V"]


def test_agenda_riusa_la_scadenza_note_collegata_senza_copia_del_provvedimento(monkeypatch):
    from web.services import react_fascicoli_bridge as bridge

    monkeypatch.setattr(bridge, "oggi_rome", lambda: OGGI)
    giorno = (OGGI + timedelta(days=20)).isoformat()
    anticipata = (OGGI + timedelta(days=14)).isoformat()
    appuntamenti = [SimpleNamespace(id="A", data_ora=f"{giorno}T14:00")]
    scadenza = SimpleNamespace(
        id="S", titolo="Deposito note", data_scadenza=giorno, stato="APERTO", tipo="DEPOSITO_MEMORIA",
        priorita="CRITICA", perentorio=True, note="", deadline_profile_code="NOTE_127_TER",
        hearing_mode="note_scritte", id_appuntamento="A", operational_due_at=f"{giorno}T14:00",
    )
    riga, = bridge._deadlines([scadenza], appuntamenti=appuntamenti)
    assert riga["replacesAppointmentId"] == "A"
    assert riga["writtenHearingTime"] == "14:00"

    scadenza.data_scadenza = anticipata
    riga, = bridge._deadlines([scadenza], appuntamenti=appuntamenti)
    assert "replacesAppointmentId" not in riga
    assert "writtenHearingTime" not in riga


def test_agenda_fascicolo_riusa_bozza_scritta_con_presidio_storico_e_udienza():
    from types import SimpleNamespace
    from web.services.react_fascicoli_bridge import _deadlines

    titolo = "Deposito note scritte ex art. 127-ter c.p.c."
    bozza = SimpleNamespace(id="bozza", titolo=titolo, data_scadenza="2026-12-16",
                            deadline_profile_code="NOTE_127_TER", stato="BOZZA", perentorio=True,
                            hearing_mode="note_scritte", operational_due_at="2026-12-16T14:00:00")
    presidio = SimpleNamespace(id="vecchio", titolo=titolo, data_scadenza="2026-12-16",
                               deadline_profile_code="PEC_AUTO_PRESIDIO", stato="APERTO",
                               id_appuntamento="storico_rimosso", operational_due_at="2026-12-16")
    udienza = SimpleNamespace(id="oggi", tipo="UDIENZA", stato="PROGRAMMATO",
                              data_ora="2026-12-16T14:00:00", hearing_mode="note_scritte")
    altra = SimpleNamespace(id="altra", tipo="UDIENZA", stato="PROGRAMMATO",
                            data_ora="2026-12-16T15:00:00", hearing_mode="note_scritte")
    righe = {r["id"]: r for r in _deadlines([bozza, presidio], appuntamenti=[udienza, altra])}
    assert righe["vecchio"]["representedByDeadlineId"] == "bozza"
    assert righe["bozza"]["replacesAppointmentId"] == "oggi"
    assert righe["bozza"]["writtenHearingTime"] == "14:00"

    presidio.operational_due_at = "2026-12-16T15:00:00"
    righe = {r["id"]: r for r in _deadlines([bozza, presidio], appuntamenti=[altra])}
    assert "representedByDeadlineId" not in righe["vecchio"]
    assert "replacesAppointmentId" not in righe["bozza"]
