"""Le scadenze automatiche di un adempimento già provato si chiudono da sole, con il motivo e il documento (20/11/2026).

Caso reale A8B49265: la proposta «Notifica di ricorso e decreto - almeno 30 giorni prima dell'udienza» restava da
verificare benché la controparte si fosse costituita (art. 156, terzo comma, c.p.c.). Dati fittizi.
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.fascicolo_lettura.termini_certi import adempimenti_provati

FATTO = {"codice": "notifica_ricorso_decreto_415", "stato": "fatto", "onerato_codice": "noi",
         "prova_o_motivo": "La controparte si è costituita con «CT 1762 2026 COMPARSA M.I.M..pdf.p7m»: la notifica ha "
                           "raggiunto il suo scopo e un suo eventuale vizio è sanato (art. 156, terzo comma, c.p.c.).",
         "letto": {"documento": "Decreto fissazione udienza.PDF"}}
BOZZA = {"id": "S1", "titolo": "Notifica di ricorso e decreto - almeno 30 giorni prima dell'udienza - RG 1854/2026",
         "note": "PEC_TERMINE_PROPOSTO:pec_x:LAV_415_NOTIFICA_TRENTA_GIORNI", "stato": "BOZZA"}


def test_costituzione_chiude_la_scadenza_della_notifica_con_la_prova():
    chiuse = adempimenti_provati([BOZZA], [FATTO])
    assert "CT 1762 2026 COMPARSA" in chiuse["S1"] and "art. 156, terzo comma, c.p.c." in chiuse["S1"]
    assert "Decreto fissazione udienza.PDF" in chiuse["S1"]


def test_senza_prova_o_con_conclusioni_ambigue_non_si_chiude():
    assert adempimenti_provati([BOZZA], [{**FATTO, "stato": "da_fare"}]) == {}
    assert adempimenti_provati([BOZZA], [{**FATTO, "prova_o_motivo": ""}]) == {}
    assert adempimenti_provati([BOZZA], [FATTO, {**FATTO, "stato": "dubbio"}]) == {}
    assert adempimenti_provati([BOZZA], [{**FATTO, "onerato_codice": "controparte"}]) == {}


def test_runtime_completa_solo_le_scadenze_automatiche(monkeypatch):
    from pct.scadenziario import StatoTermine
    from web.services.termini_certi_runtime import chiudi_adempimenti_provati

    automatica = SimpleNamespace(id="S1", titolo=BOZZA["titolo"], note=BOZZA["note"], stato=StatoTermine.BOZZA,
                                 id_utente_responsabile="")
    dell_avvocato = SimpleNamespace(id="S2", titolo=BOZZA["titolo"], note="scritta a mano", stato=StatoTermine.APERTO,
                                    id_utente_responsabile="")
    completate = []

    class Scadenziario:
        def tutte(self, **_):
            return [automatica, dell_avvocato]

        def completa(self, id_sc, note=""):
            completate.append((id_sc, note))

    monkeypatch.setattr("web.helpers.get_scadenziario", lambda: Scadenziario())
    lettura = {"ragionamento": {"conclusioni": [FATTO]}}
    assert chiudi_adempimenti_provati("F1", lettura) == ["S1"]
    assert completate[0][0] == "S1" and "COMPARSA" in completate[0][1]
    assert chiudi_adempimenti_provati("F1", {**lettura, "aggiornamento_pendente": True}) == []
