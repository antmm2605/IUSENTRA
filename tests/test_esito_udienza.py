"""Udienze passate: «esito da registrare» e registrazione automatica dalle fonti certe (V28)."""

from __future__ import annotations

from datetime import date

from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.esito_udienza import MARCATORE, esito_dalle_fonti, registra_esiti
from pct.scadenze_stato import ESITO_UDIENZA, SCADUTA, stato_operativo
from pct.scadenziario import GestioneScadenziario, Scadenza, StatoTermine, TipoTermine

OGGI = date(2026, 10, 31)


def _scadenza(tipo: TipoTermine, giorno: str, stato: StatoTermine = StatoTermine.APERTO, **altri) -> Scadenza:
    return Scadenza(titolo="voce", tipo=tipo, data_scadenza=giorno, stato=stato, id_fascicolo="F1", **altri)


def test_udienza_passata_e_esito_da_registrare_non_scaduta():
    assert stato_operativo(_scadenza(TipoTermine.UDIENZA, "2026-10-20"), OGGI) == ESITO_UDIENZA
    assert stato_operativo(_scadenza(TipoTermine.DEPOSITO_MEMORIA, "2026-10-20"), OGGI) == SCADUTA
    assert stato_operativo(_scadenza(TipoTermine.UDIENZA, "2026-11-20"), OGGI) == "aperta"
    assert stato_operativo(_scadenza(TipoTermine.UDIENZA, "2026-10-20", StatoTermine.BOZZA), OGGI) == "bozza"


def test_esito_dalla_prima_comunicazione_di_cancelleria_dopo_l_udienza():
    eventi = [
        {"campo": "rinvio", "data_iso": "2026-09-01", "oggetto_id": "pec-vecchia"},
        {"campo": "rinvio", "data_iso": "2026-10-21", "oggetto_id": "pec-1"},
        {"campo": "sentenza", "data_iso": "2026-10-25", "oggetto_id": "pec-2"},
    ]
    esito = esito_dalle_fonti(date(2026, 10, 20), eventi, [date(2026, 10, 20), date(2027, 1, 15)])
    assert esito["esito"] == "rinviata" and esito["fonte"] == "pec-1"
    assert "15/01/2027" in esito["testo"]
    decisa = esito_dalle_fonti(date(2026, 10, 22), eventi)
    assert decisa["esito"] == "decisa" and "25/10/2026" in decisa["testo"]
    assert esito_dalle_fonti(date(2026, 10, 26), eventi) is None


def test_stesso_giorno_la_sentenza_prevale_sul_rinvio():
    eventi = [{"campo": "rinvio", "data_iso": "2026-10-21"}, {"campo": "sentenza", "data_iso": "2026-10-21"}]
    assert esito_dalle_fonti(date(2026, 10, 20), eventi)["esito"] == "decisa"


def test_registra_con_fonte_certa_una_sola_volta(tmp_path):
    gestione = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    con_fonte = gestione.nuova("Udienza di discussione", TipoTermine.UDIENZA, "2026-10-20", id_fascicolo="F1")
    precedente = gestione.nuova("Prima udienza", TipoTermine.UDIENZA, "2026-09-10", id_fascicolo="F1")
    memoria = gestione.nuova("Note scritte", TipoTermine.DEPOSITO_MEMORIA, "2026-10-19", id_fascicolo="F1")
    eventi = [{"campo": "deposito_provvedimento", "data_iso": "2026-10-23", "oggetto_id": "pec-9"}]
    # la comunicazione del 23/10 vale anche per l'udienza del 10/09: è successiva
    assert registra_esiti(gestione, fascicolo_id="F1", eventi=eventi, oggi=OGGI) == 2
    chiusa = gestione.get(con_fonte.id)
    assert chiusa.stato == StatoTermine.COMPLETATO and MARCATORE in chiusa.note and "23/10/2026" in chiusa.note
    assert gestione.get(memoria.id).stato == StatoTermine.APERTO  # gli adempimenti non si chiudono da soli
    assert registra_esiti(gestione, fascicolo_id="F1", eventi=eventi, oggi=OGGI) == 0
    assert gestione.get(precedente.id).stato == StatoTermine.COMPLETATO


def test_registra_in_agenda_solo_la_voce_collegata_alla_trattazione_decisa(tmp_path):
    gestione = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    termine = gestione.nuova(
        "Deposito delle note scritte", TipoTermine.DEPOSITO_ATTO, "2026-10-09", id_fascicolo="F1",
        deadline_profile_code="NOTE_127_TER", source_message_id="pec_decreto",
        note="SUPERATA_DA_SENTENZA:TRATTAZIONE_SCRITTA:2026-10-09:D1",
    )
    agenda = Agenda(str(tmp_path / "agenda.json"))
    note = f"PEC_AUDIT:pec_decreto\nScadenza: {termine.id}"
    trattazione = agenda.aggiungi("Deposito note", TipoAppuntamento.UDIENZA, "2026-10-09T10:00:00", note=note)
    altra = agenda.aggiungi(
        "Udienza di altra pratica", TipoAppuntamento.UDIENZA, "2026-10-09T11:00:00",
        note=note, id_fascicolo="F2",
    )
    manuale = agenda.aggiungi("Altra udienza", TipoAppuntamento.UDIENZA, "2026-10-09T12:00:00")

    assert registra_esiti(gestione, fascicolo_id="F1", eventi=[], oggi=OGGI, agenda=agenda) == 1
    assert agenda.get(trattazione.id).stato == StatoAppuntamento.COMPLETATO
    assert f"{MARCATORE}:decisa:2026-10-09:D1" in agenda.get(trattazione.id).note
    assert all(agenda.get(voce.id).stato == StatoAppuntamento.PROGRAMMATO for voce in (altra, manuale))
    assert gestione.get(termine.id).stato == StatoTermine.APERTO
    assert registra_esiti(gestione, fascicolo_id="F1", eventi=[], oggi=OGGI, agenda=agenda) == 0
