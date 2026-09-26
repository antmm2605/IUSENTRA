"""Revisione 2.410.0: integrità dei dati (agenda ↔ scadenze, crediti aperti, pagamenti)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from web.services.agenda_scadenze_sync import allinea_dopo_eliminazione, allinea_dopo_spostamento


def _scadenziario(tmp_path):
    return GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))


def test_udienza_spostata_sposta_la_scadenza_udienza_e_annota_i_termini(tmp_path):
    sc = _scadenziario(tmp_path)
    prima = (date.today() + timedelta(days=30)).isoformat()
    dopo = (date.today() + timedelta(days=60)).isoformat()
    udienza = sc.nuova("Udienza di trattazione", TipoTermine.UDIENZA, prima, id_appuntamento="APP1")
    memoria = sc.nuova("Memoria 171-ter n. 1", TipoTermine.DEPOSITO_MEMORIA, (date.today() + timedelta(days=5)).isoformat(), id_appuntamento="APP1")
    estranea = sc.nuova("Altro", TipoTermine.ALTRO, prima, id_appuntamento="ALTRO")

    esito = allinea_dopo_spostamento(sc, "APP1", f"{prima}T09:00:00", f"{dopo}T10:00:00")

    assert esito == {"spostate": 1, "da_verificare": 1}
    assert sc.get(udienza.id).data_scadenza == dopo
    assert "spostata" in sc.get(udienza.id).note
    assert sc.get(memoria.id).data_scadenza != dopo
    assert "verificare se il termine va ricalcolato" in sc.get(memoria.id).note
    assert sc.get(estranea.id).data_scadenza == prima


def test_stesso_giorno_non_tocca_nulla(tmp_path):
    sc = _scadenziario(tmp_path)
    giorno = (date.today() + timedelta(days=10)).isoformat()
    udienza = sc.nuova("Udienza", TipoTermine.UDIENZA, giorno, id_appuntamento="APP1")
    assert allinea_dopo_spostamento(sc, "APP1", f"{giorno}T09:00:00", f"{giorno}T11:30:00") == {"spostate": 0, "da_verificare": 0}
    assert sc.get(udienza.id).note == ""


def test_appuntamento_eliminato_scollega_senza_cancellare(tmp_path):
    sc = _scadenziario(tmp_path)
    giorno = (date.today() + timedelta(days=10)).isoformat()
    udienza = sc.nuova("Udienza", TipoTermine.UDIENZA, giorno, id_appuntamento="APP1")
    chiusa = sc.nuova("Chiusa", TipoTermine.UDIENZA, giorno, id_appuntamento="APP1")
    sc.aggiorna(chiusa.id, stato=StatoTermine.COMPLETATO)

    assert allinea_dopo_eliminazione(sc, "APP1") == {"scollegate": 1}
    rimasta = sc.get(udienza.id)
    assert rimasta is not None and rimasta.id_appuntamento == ""
    assert "eliminato dall'agenda" in rimasta.note
    assert sc.get(chiusa.id).id_appuntamento == "APP1"


def _parcella(gestore, *, stato, anno_emissione):
    p = gestore.crea("CLI1", [VoceParcella("Onorario", 1, 1000.0)], data_emissione=f"{anno_emissione}-03-01", applica_iva=False, applica_cassa=False)
    gestore._parcelle[p.id].stato = stato
    return p


def test_crediti_aperti_unica_misura(tmp_path):
    g = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    anno = date.today().year
    _parcella(g, stato=StatoParcella.BOZZA, anno_emissione=anno)
    _parcella(g, stato=StatoParcella.EMESSA, anno_emissione=anno)
    _parcella(g, stato=StatoParcella.EMESSA, anno_emissione=anno - 1)
    _parcella(g, stato=StatoParcella.SCADUTA, anno_emissione=anno - 1)
    _parcella(g, stato=StatoParcella.PAGATA, anno_emissione=anno)
    _parcella(g, stato=StatoParcella.ANNULLATA, anno_emissione=anno)

    crediti = g.crediti_aperti()

    # Bozza, pagata e annullata non sono crediti; l'anno precedente sì.
    assert crediti["parcelle"] == 3
    assert crediti["importo"] == 3000.0
    assert crediti["non_scaduto"] == 2000.0
    assert crediti["scaduto"] == 1000.0


class _Link(SimpleNamespace):
    pass


def test_pagamento_non_confermato_dal_gestore_non_segna_pagato(monkeypatch):
    from pct import pagamenti_verifica as pv

    class _Risposta:
        status_code = 200

        def __init__(self, dati):
            self._dati = dati

        def json(self):
            return self._dati

    link = _Link(id="L1", importo=150.0)
    gp = SimpleNamespace(config=SimpleNamespace(sumup=SimpleNamespace(api_key="k")))
    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: _Risposta({"status": "PAID", "checkout_reference": "ALTRO", "amount": 150.0}))
    assert pv.sumup_pagamento_confermato(gp, "chk", link) is False
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Risposta({"status": "PAID", "checkout_reference": "L1", "amount": 1.0}))
    assert pv.sumup_pagamento_confermato(gp, "chk", link) is False
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Risposta({"status": "PENDING", "checkout_reference": "L1", "amount": 150.0}))
    assert pv.sumup_pagamento_confermato(gp, "chk", link) is False
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Risposta({"status": "PAID", "checkout_reference": "L1", "amount": 150.0}))
    assert pv.sumup_pagamento_confermato(gp, "chk", link) is True
    assert pv.sumup_pagamento_confermato(gp, "", link) is False


def test_sessione_stripe_di_un_altro_link_non_vale():
    from pct.pagamenti_verifica import stripe_sessione_del_link

    link = _Link(id="L1", importo=200.0)
    buona = SimpleNamespace(payment_status="paid", metadata={"link_id": "L1"}, amount_total=20000)
    altra = SimpleNamespace(payment_status="paid", metadata={"link_id": "L2"}, amount_total=20000)
    poca = SimpleNamespace(payment_status="paid", metadata={"link_id": "L1"}, amount_total=100)
    assert stripe_sessione_del_link(buona, link) is True
    assert stripe_sessione_del_link(altra, link) is False
    assert stripe_sessione_del_link(poca, link) is False
