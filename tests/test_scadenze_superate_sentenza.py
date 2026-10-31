"""V32: scadenze procedurali passate alla sentenza ricevono un avviso, non vengono chiuse (RG 2848/2026)."""

from __future__ import annotations

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
