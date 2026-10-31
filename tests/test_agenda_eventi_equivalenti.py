"""La stessa udienza vista da più fonti resta una sola voce d'agenda (31/10/2026)."""

from __future__ import annotations

from types import SimpleNamespace

from pct.agenda import Agenda, TipoAppuntamento
from pct.agenda_eventi_equivalenti import ORA_DA_CONFERMARE, ora_da_confermare, riunisci_fonte, udienza_equivalente
from pct.scadenziario import GestioneScadenziario
from web.services.scadenza_proposta_agenda import crea_agenda_da_udienza_confermata


def _agenda(tmp_path):
    return Agenda(db_path=str(tmp_path / "agenda.json"))


def test_udienza_equivalente_per_fascicolo_o_ruolo(tmp_path):
    agenda = _agenda(tmp_path)
    voce = agenda.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2027-03-15T10:30:00", allow_overlap=True,
                           id_fascicolo="F-1", procedimento="RG 123/2026")
    tutti = agenda.tutti()
    assert udienza_equivalente(tutti, id_fascicolo="F-1", data_ora="2027-03-15T10:30:00").id == voce.id
    assert udienza_equivalente(tutti, procedimento="R.G. n. 123 / 2026", data_ora="2027-03-15T10:30:00").id == voce.id
    assert udienza_equivalente(tutti, id_fascicolo="F-1", data_ora="2027-03-15T09:00:00", ora_certa=False).id == voce.id
    assert udienza_equivalente(tutti, id_fascicolo="F-1", data_ora="2027-03-15T12:00:00") is None
    assert udienza_equivalente(tutti, id_fascicolo="F-2", data_ora="2027-03-15T10:30:00") is None
    assert udienza_equivalente(tutti, id_fascicolo="F-1", data_ora="2027-03-16T10:30:00") is None
    assert udienza_equivalente(tutti, data_ora="2027-03-15T10:30:00") is None
    agenda.aggiungi("Appuntamento", TipoAppuntamento.CONSULTAZIONE, "2027-03-20T10:30:00", allow_overlap=True, id_fascicolo="F-1")
    assert udienza_equivalente(agenda.tutti(), id_fascicolo="F-1", data_ora="2027-03-20T10:30:00") is None
    from pct.agenda import StatoAppuntamento

    agenda.cambia_stato(voce.id, StatoAppuntamento.ANNULLATO)
    assert udienza_equivalente(agenda.tutti(), id_fascicolo="F-1", data_ora="2027-03-15T10:30:00") is None


def test_ora_certa_sostituisce_il_segnaposto(tmp_path):
    agenda = _agenda(tmp_path)
    voce = agenda.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2027-03-15T09:00:00", allow_overlap=True,
                           id_fascicolo="F-1", note=f"Dalla PEC\n{ORA_DA_CONFERMARE}")
    assert ora_da_confermare(voce)
    trovata = udienza_equivalente(agenda.tutti(), id_fascicolo="F-1", data_ora="2027-03-15T10:30:00")
    aggiornata = riunisci_fonte(agenda, trovata, fonte="ARCHIVIO_FATTO:X", data_ora="2027-03-15T10:30:00", ora_certa=True)
    assert aggiornata.data_ora == "2027-03-15T10:30:00" and not ora_da_confermare(aggiornata)
    assert "Fonte aggiuntiva: ARCHIVIO_FATTO:X" in aggiornata.note and len(agenda.tutti()) == 1
    # Stessa fonte di nuovo: nulla da cambiare.
    assert riunisci_fonte(agenda, aggiornata, fonte="ARCHIVIO_FATTO:X", data_ora="2027-03-15T10:30:00", ora_certa=True) is aggiornata


def test_conferma_proposta_polisweb_non_duplica(tmp_path):
    agenda = _agenda(tmp_path)
    esistente = agenda.aggiungi("Udienza da PEC", TipoAppuntamento.UDIENZA, "2027-03-15T10:30:00", allow_overlap=True,
                                id_fascicolo="F-1")
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    from pct.scadenziario import TipoTermine

    proposta = scadenziario.nuova("Udienza", TipoTermine.UDIENZA, "2027-03-15", id_fascicolo="F-1")
    assert crea_agenda_da_udienza_confermata(proposta, gestione_agenda=agenda, gestione_scadenziario=scadenziario)
    assert len(agenda.tutti()) == 1 and scadenziario.get(proposta.id).id_appuntamento == esistente.id
    altra = scadenziario.nuova("Udienza", TipoTermine.UDIENZA, "2027-04-20", id_fascicolo="F-1")
    assert crea_agenda_da_udienza_confermata(altra, gestione_agenda=agenda, gestione_scadenziario=scadenziario)
    nuova = next(a for a in agenda.tutti() if a.data_ora.startswith("2027-04-20"))
    assert ora_da_confermare(nuova) and nuova.id_fascicolo == "F-1"
    assert SimpleNamespace  # import usato
