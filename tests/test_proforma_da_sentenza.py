"""Proforma per le spese liquidate in sentenza (collaudo Alessi, RG 2539/2025: 409 per le ricevute di notifica)."""

from __future__ import annotations

from types import SimpleNamespace

import web.services.fascicolo_conto_economico_runtime as conto_runtime
import web.services.react_fascicoli_bridge as bridge
from web.services.proforma_da_sentenza import base_dalla_sentenza_letta, voci_che_bloccano

LIQUIDAZIONE_SOSPESA = {
    "liquidazione_giudice": {
        "richiedeConferma": True, "status": "da_registrare", "importo": None,
        "verificheMancanti": ["Importi non attribuiti da CONSEGNA: Notificazione …: Codice fiscale della parte non valido."],
    },
}
SENTENZA_LETTA = [{"regolazione": "condanna", "importo": 250.0, "distrazione": True, "a_favore_del_cliente": True,
                   "fonti": [{"label": "20708622s.pdf", "href": "/x", "norma": "sentenza della causa"}]}]


def test_verifiche_su_altri_documenti_non_bloccano_la_proforma_dalla_sentenza():
    assert voci_che_bloccano(LIQUIDAZIONE_SOSPESA, base_da_sentenza=True) == []
    bloccanti = voci_che_bloccano(LIQUIDAZIONE_SOSPESA, base_da_sentenza=False)
    assert len(bloccanti) == 1 and bloccanti[0].startswith("Liquidazione del giudice: Importi non attribuiti")


def test_la_parcella_da_confermare_blocca_sempre_e_le_altre_voci_no():
    items = {"parcella": {"richiedeConferma": True, "verificheMancanti": ["Importi diversi letti: 300,00 e 296,70"]},
             "contributo_unificato": {"richiedeConferma": True}}
    assert voci_che_bloccano(items, base_da_sentenza=True) == ["Parcella: Importi diversi letti: 300,00 e 296,70"]
    assert voci_che_bloccano({"contributo_unificato": {"richiedeConferma": True}}, base_da_sentenza=False) == []


def test_base_dalla_sentenza_letta(monkeypatch):
    monkeypatch.setattr(conto_runtime, "sentenze_dall_archivio", lambda f: SENTENZA_LETTA)
    importo, fonte = base_dalla_sentenza_letta(SimpleNamespace(id="F1"))
    assert importo == 250.0
    assert fonte == "spese liquidate in sentenza € 250,00 distratte (art. 93 c.p.c.), oltre accessori (20708622s.pdf)"
    monkeypatch.setattr(conto_runtime, "sentenze_dall_archivio", lambda f: [dict(SENTENZA_LETTA[0], a_favore_del_cliente=False)])
    assert base_dalla_sentenza_letta(SimpleNamespace(id="F1")) == (None, "")


def test_genera_proforma_dalla_sentenza_letta_nonostante_le_ricevute(monkeypatch):
    import web.services.react_fatturazione_bridge as fatturazione_bridge

    fascicolo = SimpleNamespace(id="F1", pagamenti={}, compenso_pattuito=None, valore_preventivato=None)
    monkeypatch.setattr(bridge, "_resolve_fascicolo", lambda repo, fid: fascicolo)
    monkeypatch.setattr(bridge, "payment_summary_for_fascicolo", lambda f: {"items": LIQUIDAZIONE_SOSPESA})
    monkeypatch.setattr(conto_runtime, "sentenze_dall_archivio", lambda f: SENTENZA_LETTA)
    catturato = {}

    def _crea(**kwargs):
        catturato.update(kwargs)
        return {"ok": False, "message": "fermato dal test"}, 418

    monkeypatch.setattr(fatturazione_bridge, "create_react_fascicolo_proforma", _crea)
    fatturazione = SimpleNamespace(per_fascicolo=lambda fid: [])
    risultato, stato = bridge.generate_react_fascicolo_proforma(
        get_fascicoli=lambda: object(), get_fatturazione=lambda: fatturazione, get_clienti=lambda: object(),
        get_utenti=lambda: object(), get_preventivi=None, current_user=SimpleNamespace(id="U"), id_fasc="F1",
        payload={}, config={})
    assert stato == 418  # arrivata alla creazione della proforma, non più 409
    assert catturato["amount"] == 250.0 and "art. 93 c.p.c." in catturato["amount_source"]
