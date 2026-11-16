"""Proforma per le spese liquidate in sentenza (collaudo Alessi, RG 2539/2025: 409 per le ricevute di notifica)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize(("pagamento", "esito"), [
    ({}, 418),
    ({"origine": "lex_ai_sentenza_tribunale", "status": "da_registrare", "importo": 250.0, "updated_by": "utente-id"}, 418),
    ({"origine": "lex_ai_sentenza_tribunale", "status": "da_registrare", "importo": 210.0, "updated_by": "utente-id"}, 409),
    ({"origine": "Conferma operatore", "status": "da_registrare", "importo": 250.0, "updated_by": "utente-id"}, 409),
])
def test_genera_proforma_dalla_sentenza_letta_nonostante_le_ricevute(monkeypatch, pagamento, esito):
    import web.services.react_fatturazione_bridge as fatturazione_bridge

    fascicolo = SimpleNamespace(id="F1", pagamenti={"liquidazione_giudice": pagamento}, compenso_pattuito=None, valore_preventivato=None)
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
    assert stato == esito
    if esito == 418:
        assert catturato["amount"] == 250.0 and "art. 93 c.p.c." in catturato["amount_source"]
    else:
        assert not catturato


def test_riusa_solo_la_proforma_riferita_alla_stessa_liquidazione():
    from types import SimpleNamespace
    from web.services.proforma_da_sentenza import fonte_importo, proforma_della_liquidazione

    evento = {"id": "credito-1", "amount": 500, "event_type": "apri_credito_avvocato_antistatario"}
    bozza = SimpleNamespace(
        origine="controllo_economico_fascicolo", id_cliente="C1", stato="BOZZA", totale_competenze=500,
        note="Base di calcolo: " + fonte_importo(500, True, "dispositivo.pdf") + ".",
        dati_personalizzati={"document": {"documento_operativo": "PROFORMA"}},
    )
    assert proforma_della_liquidazione([bozza], evento=evento, documento="dispositivo.pdf", id_cliente="C1") is bozza
    assert proforma_della_liquidazione([bozza], evento=evento, documento="successivo.pdf", id_cliente="C1") is None
    assert proforma_della_liquidazione([bozza], evento=evento, documento="dispositivo.pdf", id_cliente="C2") is None
    cliente = {**evento, "event_type": "apri_credito_cliente"}
    assert proforma_della_liquidazione([bozza], evento=cliente, documento="dispositivo.pdf", id_cliente="C1") is None
    bozza.stato = "ANNULLATA"
    assert proforma_della_liquidazione([bozza], evento=evento, documento="dispositivo.pdf", id_cliente="C1") is None


def test_generazione_da_credito_riapre_la_proforma_del_conto_economico(monkeypatch):
    from pct.fatturazione import Parcella, VoceParcella
    from web import helpers
    from web.services import registro_letture_runtime, sentenza_economic_runtime, sentenza_proposte_runtime
    from web.services.proforma_da_sentenza import fonte_importo

    impronta = "a" * 64
    event = {"id": "E1", "source_id": "S1", "amount": 500, "status": "confirmed",
             "event_type": "apri_credito_avvocato_antistatario", "beneficiary_type": "avvocato"}
    fonte = SimpleNamespace(presente=True, impronta=impronta, tipo="documento", oggetto_id="D1", nome="dispositivo.pdf")
    bozza = Parcella(id="P1", numero="PF-2026/087", id_cliente="C1", id_fascicolo="F1", data_emissione="2026-11-14", data_scadenza=None,
        origine="controllo_economico_fascicolo", voci=[VoceParcella(descrizione="Compensi", prezzo_unitario=500)],
        note="Base di calcolo: " + fonte_importo(500, True, fonte.nome) + ".",
        dati_personalizzati={"document": {"documento_operativo": "PROFORMA"}})
    database = SimpleNamespace(
        list_economic_events=lambda *a, **k: [event],
        list_sentenza_audits=lambda *a, **k: [{"id": "S1", "documento_id": "D1", "document_hash_sha256": impronta}],
    )
    aggiornamenti = {}
    fatturazione = SimpleNamespace(per_fascicolo=lambda _id: [bozza], aggiorna=lambda _id, **k: aggiornamenti.update(k))
    monkeypatch.setattr(sentenza_economic_runtime, "_flag_on", lambda: True)
    monkeypatch.setattr(sentenza_economic_runtime, "_tenant_id", lambda: "studio")
    monkeypatch.setattr(sentenza_economic_runtime, "_repo", lambda: database)
    monkeypatch.setattr(sentenza_economic_runtime, "_resolve_fascicolo", lambda _id: SimpleNamespace(id="F1", id_cliente="C1"))
    monkeypatch.setattr(sentenza_proposte_runtime, "_parcelle_per_evento", lambda _id: {})
    monkeypatch.setattr(registro_letture_runtime, "registro_corrente", lambda **_: SimpleNamespace(oggetti=lambda *a: [fonte]))
    monkeypatch.setattr(helpers, "get_fatturazione", lambda: fatturazione)
    risultato = sentenza_economic_runtime.genera_parcella_from_event({"eventId": "E1", "fascicoloId": "F1"})
    assert risultato["alreadyPresent"] and risultato["parcellaId"] == "P1"
    assert aggiornamenti["dati_personalizzati"]["event_id"] == "E1"
    assert aggiornamenti["expected_revision"]
