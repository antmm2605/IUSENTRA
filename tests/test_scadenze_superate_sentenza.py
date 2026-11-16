"""V32: scadenze procedurali passate alla sentenza ricevono un avviso, non vengono chiuse (RG 2848/2026)."""

from __future__ import annotations

from datetime import date

from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from pct.scadenze_superate_sentenza import MARCATORE, segnala_scadenze_superate


def test_solo_le_scadenze_procedurali_passate_del_fascicolo_ricevono_l_avviso(tmp_path):
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    note = scadenziario.nuova(titolo="Deposito note scritte ex art. 127-ter c.p.c.", tipo=TipoTermine.DEPOSITO_MEMORIA,
                              data_scadenza="2026-10-09", id_fascicolo="F1")
    futura = scadenziario.nuova(titolo="Udienza di discussione", tipo=TipoTermine.UDIENZA, data_scadenza="2026-12-01", id_fascicolo="F1")
    impugnazione = scadenziario.nuova(titolo="Impugnazione sentenza - termine lungo", tipo=TipoTermine.IMPUGNAZIONE,
                                      data_scadenza="2026-10-01", id_fascicolo="F1")
    altro_fascicolo = scadenziario.nuova(titolo="Deposito memoria", tipo=TipoTermine.DEPOSITO_MEMORIA, data_scadenza="2026-10-01", id_fascicolo="F2")

    assert segnala_scadenze_superate(scadenziario, fascicolo_id="F1", giorno_sentenza="2026-10-12", origine="PEC del 12/10/2026") == 1
    voce = scadenziario.get(note.id)
    assert voce.stato == StatoTermine.APERTO  # nessuna chiusura automatica
    assert voce.descrizione.startswith("Possibile scadenza superata dalla sentenza del 12/10/2026") and MARCATORE in voce.note
    for intatta in (futura, impugnazione, altro_fascicolo):
        assert MARCATORE not in scadenziario.get(intatta.id).note
    # La stessa sentenza elaborata di nuovo non ripete l'avviso.
    assert segnala_scadenze_superate(scadenziario, fascicolo_id="F1", giorno_sentenza="2026-10-12", origine="PEC") == 0


def test_le_note_restano_storiche_anche_se_la_descrizione_cita_una_notifica(tmp_path, monkeypatch):
    from pct.scadenze_stato import SCADUTA, STORICA, stato_operativo
    from pct.scadenze_superate_sentenza import decisione_superante
    from web.services.react_scadenziario_bridge import _row

    calendario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    nota = calendario.nuova(
        titolo="Fissazione termine per note in sostituzione udienza - RG 795/2026",
        tipo=TipoTermine.UDIENZA, data_scadenza="2026-10-21", id_fascicolo="F1",
        hearing_mode="note_scritte", descrizione="Notifica PEC della cancelleria.",
    )
    rimedio = calendario.nuova(
        titolo="Appello", tipo=TipoTermine.IMPUGNAZIONE, data_scadenza="2026-10-30", id_fascicolo="F1",
    )
    assert segnala_scadenze_superate(
        calendario, fascicolo_id="F1", giorno_sentenza="2026-11-02", origine="dispositivo", documento_conclusivo="DOC",
    ) == 1
    storica = calendario.get(nota.id)
    assert decisione_superante(storica, al_giorno=date(2026, 11, 3)) == ("2026-11-02", "DOC")
    assert stato_operativo(storica, date(2026, 10, 31)) == SCADUTA
    assert stato_operativo(storica, date(2026, 11, 3)) == STORICA
    import pct.ora_italiana
    monkeypatch.setattr(pct.ora_italiana, "oggi_roma", lambda: date(2026, 11, 3))
    riga = _row(storica, gestione_fascicoli=None, gestione_utenti=None)
    assert riga["status"] == "STORICO" and not riga["overdue"]
    assert riga["decisionHref"] == "/fascicoli/F1/documenti/DOC/visualizza"
    assert "02/11/2026" in riga["proceduralFinding"]
    assert calendario.get(nota.id).stato == StatoTermine.APERTO
    assert not decisione_superante(calendario.get(rimedio.id))
