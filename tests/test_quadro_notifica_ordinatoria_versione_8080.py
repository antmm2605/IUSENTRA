"""Test della versione locale dell'8080 (copia di lavoro del disco C:, 19/11/2026), conservati dopo l'unione.

I casi superati dalle correzioni del 18-19/11 (passi da avvocato, esenzioni del contributo, pannelli dipendenti) sono stati tolti:
la regola aggiornata è verificata nei test principali.
"""
from datetime import date

from pct.fascicolo_quadro import riga_notifiche
from web.services import obblighi_notifica_sintesi as sintesi


def test_quadro_recupera_la_natura_da_un_dettaglio_gia_salvato(monkeypatch):
    from web.services import obblighi_notifica_fonti

    scadenza = {"atto": "Decreto di fissazione udienza", "stato": "da_notificare", "scadenza": "2026-08-03"}
    record = {
        "impronta": "salvata", "riferimento": "corrente", "obblighi": [scadenza],
        "dettaglio": [{**scadenza, "atti": scadenza["atto"], "natura": "ordinatorio",
                       "dati_mancanti": [{"campo": "udienza"}]}],
    }
    monkeypatch.setattr(sintesi, "_leggi_record", lambda _: record)
    monkeypatch.setattr(obblighi_notifica_fonti, "riferimento_corrente", lambda _: "corrente")

    oggi = date(2026, 11, 18)
    obblighi = sintesi.leggi("F1")["obblighi"]
    riga = riga_notifiche(obblighi, oggi=oggi)
    assert riga["livello"] == "attenzione"
    assert "Termine ordinatorio decorso il 03/08/2026" in riga["testo"]
    assert "Termine a difesa da verificare" in riga["testo"]
    perentorio = {**scadenza, "atto": "Altro atto", "natura": "perentorio"}
    assert riga_notifiche([*obblighi, perentorio], oggi=oggi)["livello"] == "urgente"
