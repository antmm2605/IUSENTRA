"""Riunione dei doppioni già presenti (verifica di produzione del 31/10/2026, punto V6)."""

from __future__ import annotations

from pct.agenda import Agenda, StatoAppuntamento, TipoAppuntamento
from pct.agenda_eventi_equivalenti import ORA_DA_CONFERMARE
from pct.riunione_doppioni import automatica, gruppi_scadenze_doppie, riunisci
from pct.scadenziario import GestioneScadenziario, TipoTermine
from web.services import notifications_runtime

CONTESTO = "assegna alle parti termine del 17/12/2026 per il deposito di note scritte"


def _scadenziario(tmp_path):
    return GestioneScadenziario(str(tmp_path / "scadenze.json"))


def test_riunisce_il_triplo_termine_127_ter_e_lascia_le_manuali(tmp_path):
    s = _scadenziario(tmp_path)
    a = s.nuova("Termine del 17/12/2026", TipoTermine.DEPOSITO_ATTO, "2026-12-17", id_fascicolo="F1", descrizione=CONTESTO,
                note="ARCHIVIO_FATTO:canon-1")
    b = s.nuova("Termine del 17/12/2026", TipoTermine.DEPOSITO_ATTO, "2026-12-17", id_fascicolo="F1", descrizione=CONTESTO,
                note="ARCHIVIO_FATTO:fat-2")
    c = s.nuova("Deposito note scritte ex art. 127-ter c.p.c. — 17/12/2026", TipoTermine.DEPOSITO_ATTO, "2026-12-17",
                id_fascicolo="F1", descrizione=CONTESTO, note="ARCHIVIO_FATTO:fat-3")
    manuale = s.nuova("Termine del 17/12/2026", TipoTermine.DEPOSITO_ATTO, "2026-12-17", id_fascicolo="F1", note="")
    assegnata = s.nuova("Termine del 17/12/2026", TipoTermine.DEPOSITO_ATTO, "2026-12-17", id_fascicolo="F1",
                        note="ARCHIVIO_FATTO:fat-4", id_utente_responsabile="avv")
    notifica = s.nuova("Notifica del ricorso", TipoTermine.NOTIFICA, "2026-12-17", id_fascicolo="F1",
                       descrizione="termine per la notifica del ricorso e del decreto", note="PEC_AUDIT:m1")
    assert not automatica(manuale) and not automatica(assegnata)
    esito = riunisci(s, None)
    stati = {v.id: v.stato.value for v in s.tutte(solo_aperte=False)}
    assert esito["scadenze_riunite"] == 2
    assert stati[c.id] == "APERTO" and stati[a.id] == stati[b.id] == "ANNULLATO"
    assert stati[manuale.id] == stati[assegnata.id] == stati[notifica.id] == "APERTO"
    assert f"Riunita a {c.id}" in s.get(a.id).note
    assert riunisci(s, None)["scadenze_riunite"] == 0


def test_due_termini_generici_dello_stesso_giorno_si_riuniscono(tmp_path):
    s = _scadenziario(tmp_path)
    s.nuova("Termine del 07/03/2027", TipoTermine.TERMINE_PERENTORIO, "2027-03-07", id_fascicolo="F2", note="ARCHIVIO_FATTO:x")
    s.nuova("Termine del 07/03/2027", TipoTermine.ADEMPIMENTO, "2027-03-07", id_fascicolo="F2", note="ARCHIVIO_FATTO:y")
    (gruppo,) = gruppi_scadenze_doppie(s.tutte(solo_aperte=False))
    assert len(gruppo) == 2
    riunisci(s, None)
    aperte = [v for v in s.tutte(solo_aperte=False) if v.stato.value == "APERTO"]
    assert len(aperte) == 1 and aperte[0].tipo.value == "TERMINE_PERENTORIO"


def test_udienza_doppia_pec_e_documenti_con_collegamenti_spostati(tmp_path):
    s = _scadenziario(tmp_path)
    ag = Agenda(db_path=str(tmp_path / "agenda.json"))
    pec = ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2026-11-24T09:30:00", allow_overlap=True, id_fascicolo="F3",
                      external_uid="PEC_AUDIT:m9:deadline")
    doc = ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2026-11-24T09:30:00", allow_overlap=True, id_fascicolo="F3",
                      note="ARCHIVIO_FATTO:f9")
    segnaposto = ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2026-11-25T09:00:00", allow_overlap=True, id_fascicolo="F4",
                             note=f"PEC_AUDIT:m10\n{ORA_DA_CONFERMARE}")
    certa = ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2026-11-25T11:00:00", allow_overlap=True, id_fascicolo="F4",
                        note="ARCHIVIO_FATTO:f10")
    diversa = ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2026-11-25T15:00:00", allow_overlap=True, id_fascicolo="F4",
                          note="ARCHIVIO_FATTO:f11")
    memoria = s.nuova("Memoria", TipoTermine.DEPOSITO_MEMORIA, "2026-11-01", id_fascicolo="F3", id_appuntamento=doc.id)
    esito = riunisci(s, ag)
    stati = {a.id: a.stato for a in ag.tutti()}
    assert stati[pec.id] == StatoAppuntamento.PROGRAMMATO and stati[doc.id] == StatoAppuntamento.ANNULLATO
    assert s.get(memoria.id).id_appuntamento == pec.id
    # Due ore certe diverse nello stesso giorno: due udienze vere, non si riuniscono.
    assert stati[segnaposto.id] == stati[certa.id] == stati[diversa.id] == StatoAppuntamento.PROGRAMMATO
    assert esito["udienze_riunite"] == 1


def test_giro_notifiche_riunione_e_errori(tmp_path, monkeypatch):
    s = _scadenziario(tmp_path)
    assert notifications_runtime._riunisci_doppioni(s, None) == {"scadenze_riunite": 0, "udienze_riunite": 0}
    import pct.riunione_doppioni as modulo

    monkeypatch.setattr(modulo, "riunisci", lambda *a: (_ for _ in ()).throw(RuntimeError("archivio")))
    assert "errore" in notifications_runtime._riunisci_doppioni(s, None)


def test_generica_con_una_sola_specifica_e_casi_esclusi(tmp_path):
    s = _scadenziario(tmp_path)
    generica = s.nuova("Termine del 10/01/2027", TipoTermine.ADEMPIMENTO, "2027-01-10", id_fascicolo="F5", note="ARCHIVIO_FATTO:g")
    specifica = s.nuova("Deposito note scritte ex art. 127-ter c.p.c.", TipoTermine.DEPOSITO_ATTO, "2027-01-10",
                        id_fascicolo="F5", note="ARCHIVIO_FATTO:s")
    ag = Agenda(db_path=str(tmp_path / "agenda.json"))
    senza_chiave = ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2027-01-10T09:00:00", allow_overlap=True, note="PEC_AUDIT:z")
    ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2027-01-10T09:00:00", allow_overlap=True, id_fascicolo="F5", note="PEC_AUDIT:z1")
    annullata = ag.aggiungi("Udienza", TipoAppuntamento.UDIENZA, "2027-01-10T09:00:00", allow_overlap=True, id_fascicolo="F5",
                            note="PEC_AUDIT:z2")
    ag.cambia_stato(annullata.id, StatoAppuntamento.ANNULLATO)
    altra = s.nuova("Memoria", TipoTermine.DEPOSITO_MEMORIA, "2027-01-01", id_fascicolo="F5", id_appuntamento="ALTRO")
    esito = riunisci(s, ag)
    assert esito == {"scadenze_riunite": 1, "udienze_riunite": 0}
    assert s.get(generica.id).stato.value == "ANNULLATO" and s.get(specifica.id).stato.value == "APERTO"
    assert s.get(altra.id).id_appuntamento == "ALTRO" and ag.get(senza_chiave.id).stato == StatoAppuntamento.PROGRAMMATO
