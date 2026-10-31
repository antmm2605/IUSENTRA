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


def test_stesso_termine_da_due_copie_del_provvedimento_resta_una_scadenza():
    """Visto in produzione il 31/10/2026: tre voci per lo stesso termine 127-ter del 17/12/2026."""
    from web.services.consegna_presidi_runtime import _stessa_scadenza

    contesto = "ASSEGNA alle parti, ai sensi dell'art. 127 ter c.p.c., termine del 17/12/2026 per il deposito di note scritte"
    generica = SimpleNamespace(stato="APERTO", data_scadenza="2026-12-17", titolo="Termine del 17/12/2026",
                               descrizione=contesto, note="Data verificata nell’archivio delle letture.\nARCHIVIO_FATTO:f1")
    altra_copia = SimpleNamespace(id="f2", valore="2026-12-17", etichetta="Termine del 17/12/2026", contesto=contesto,
                                  oggetto_id="DOC-2", tipo="documento", campo="termine", categoria="data")
    specifica = SimpleNamespace(id="f3", valore="2026-12-17", etichetta="Deposito note scritte ex art. 127-ter c.p.c. — 17/12/2026",
                                contesto=contesto, oggetto_id="DOC-3", tipo="documento", campo="termine", categoria="data")
    assert _stessa_scadenza(generica, altra_copia) and _stessa_scadenza(generica, specifica)
    # Un adempimento diverso nello stesso giorno resta distinto.
    notifica = SimpleNamespace(id="f4", valore="2026-12-17", etichetta="Termine per la notifica del ricorso",
                               contesto="termine del 17/12/2026 per la notifica del ricorso e del decreto",
                               oggetto_id="DOC-4", tipo="documento", campo="termine", categoria="data")
    from pct.archivio_letture.identita_eventi import adempimento_da_testo

    if adempimento_da_testo(notifica.contesto):
        assert not _stessa_scadenza(generica, notifica)
    # Una voce inserita a mano resta confrontata con rigore.
    manuale = SimpleNamespace(stato="APERTO", data_scadenza="2026-12-17", titolo="Termine del 17/12/2026", descrizione="", note="")
    assert not _stessa_scadenza(manuale, altra_copia)


def test_sentenza_di_altro_ufficio_dal_nome_e_un_precedente():
    """Visto in produzione: sentenze di Vicenza e Cosenza «da notificare» in fascicoli di Locri e Palmi."""
    from pct.archivio_letture.pertinenza_documentale import precedente_dal_nome

    assert precedente_dal_nome("Tribunale-di-Cosenza-Sentenza-n.-394-2023-del-08.03.23", "TRIBUNALE DI LOCRI")
    assert precedente_dal_nome("Sentenza_Tribunale_Vicenza_20-04-2023.PDF", "Tribunale di Palmi")
    assert not precedente_dal_nome("Sentenza Tribunale di Locri n. 12.pdf", "TRIBUNALE DI LOCRI")
    assert not precedente_dal_nome("Decreto fissazione udienza.PDF", "Tribunale di Locri")
    assert not precedente_dal_nome("Sentenza Tribunale di Santa Maria Capua Vetere.pdf", "Tribunale di Santa Maria Capua Vetere")
    assert not precedente_dal_nome("Sentenza Tribunale di Cosenza.pdf", "")
