"""Scadenze di deposito adempiute dal deposito consegnato nel termine (V28)."""

from __future__ import annotations

from types import SimpleNamespace

from pct.deposito_adempimento import MARCATORE_AVVISO, MARCATORE_CHIUSURA, abbina_depositi, famiglia
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine


def _dep(id_, giorno, stato="ACCETTATO_CANCELLERIA", tipo="NOTE SCRITTE"):
    return SimpleNamespace(id=id_, timestamp=f"{giorno}T10:00:00", stato=stato, tipo_atto=tipo)


def test_famiglie_dell_atto():
    assert famiglia("Deposito note scritte ex art. 127-ter c.p.c.") == "note"
    assert famiglia("MEMORIA 171-TER N. 2") == "memoria"
    assert famiglia("DEPOSITO PCT") == ""


def test_deposito_compatibile_nel_termine_chiude_la_scadenza(tmp_path):
    gestione = GestioneScadenziario(str(tmp_path / "s.json"))
    voce = gestione.nuova("Deposito note scritte ex art. 127-ter c.p.c.", TipoTermine.DEPOSITO_MEMORIA, "2026-10-06", id_fascicolo="F1")
    esito = abbina_depositi(gestione, fascicolo_id="F1", depositi=[_dep("d1", "2026-10-05")])
    assert esito == {"chiuse": 1, "avvisate": 0}
    chiusa = gestione.get(voce.id)
    assert chiusa.stato == StatoTermine.COMPLETATO and MARCATORE_CHIUSURA in chiusa.note and "05/10/2026" in chiusa.note


def test_deposito_generico_avvisa_e_non_chiude(tmp_path):
    gestione = GestioneScadenziario(str(tmp_path / "s.json"))
    voce = gestione.nuova("Deposito note scritte", TipoTermine.DEPOSITO_MEMORIA, "2026-10-06", id_fascicolo="F1")
    esito = abbina_depositi(gestione, fascicolo_id="F1", depositi=[_dep("d1", "2026-10-02", tipo="DEPOSITO PCT")])
    assert esito == {"chiuse": 0, "avvisate": 1}
    aperta = gestione.get(voce.id)
    assert aperta.stato == StatoTermine.APERTO and MARCATORE_AVVISO in aperta.note and "02/10/2026" in aperta.descrizione
    assert abbina_depositi(gestione, fascicolo_id="F1", depositi=[_dep("d1", "2026-10-02", tipo="DEPOSITO PCT")]) == {"chiuse": 0, "avvisate": 0}


def test_deposito_tardivo_rifiutato_o_di_altro_tipo_non_conta(tmp_path):
    gestione = GestioneScadenziario(str(tmp_path / "s.json"))
    gestione.nuova("Deposito note scritte", TipoTermine.DEPOSITO_MEMORIA, "2026-10-06", id_fascicolo="F1")
    depositi = [
        _dep("tardivo", "2026-10-07"),
        _dep("rifiutato", "2026-10-03", stato="RIFIUTATO_CANCELLERIA"),
    ]
    assert abbina_depositi(gestione, fascicolo_id="F1", depositi=depositi) == {"chiuse": 0, "avvisate": 0}
    altro = abbina_depositi(gestione, fascicolo_id="F1", depositi=[_dep("memoria", "2026-10-03", tipo="MEMORIA 171-TER")])
    assert altro == {"chiuse": 0, "avvisate": 1}
