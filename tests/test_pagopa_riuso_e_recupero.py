"""Ricevute pagoPA: la stessa RT non prova due versamenti (avviso, mai blocco) e il recupero dal PST.

Nessun controllo nuovo blocca il deposito: con l'autocertificazione di esenzione il contributo resta
«non previsto» e l'avviso pagoPA non viene proposto.
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from pct.pagamenti_giustizia_registro import avviso_riuso, forme_iuv, usi_altrove
from tests.test_pagamenti_giustizia import _rt_xml
from web.services import pagopa_avvisi_runtime as runtime
from web.services.pagopa_prefill import dati_precompilazione

NUMERO = "330000000000000001"


def _fascicolo(fid, titolo, pagamenti):
    return SimpleNamespace(id=fid, titolo=titolo, numero_rg="12/2026", pagamenti=pagamenti)


def test_forme_iuv_e_usi_in_altri_fascicoli():
    assert forme_iuv(NUMERO) == {NUMERO, NUMERO[1:]}
    usato = _fascicolo("A", "Rossi c. Bianchi", {"pagopa_portale": {"avvisi": [
        {"numero_avviso": NUMERO, "iuv": NUMERO[1:], "documento_id": "D1"}]}})
    pagato = _fascicolo("B", "Verdi c. Neri", {"contributo_unificato": {"pagato": True, "iuv": NUMERO[1:]}})
    non_pagato = _fascicolo("C", "Gialli", {"pagopa_portale": {"avvisi": [{"numero_avviso": NUMERO}]}})
    usi = usi_altrove([usato, pagato, non_pagato], NUMERO[1:], escludi="A")
    assert [u["id"] for u in usi] == ["B"]
    assert "Verdi c. Neri (RG 12/2026)" in avviso_riuso(usi)
    assert usi_altrove([usato], "", escludi="X") == [] and avviso_riuso([]) == ""


class Gestore:
    def __init__(self, altri=()):
        self.fascicolo = SimpleNamespace(id="CASO", titolo="Caso", numero_rg="", pagamenti={})
        self.altri = list(altri)
        self.docs = []

    def get(self, fid):
        return self.fascicolo if fid == "CASO" else None

    def tutti(self, **_):
        return [self.fascicolo, *self.altri]

    def aggiorna(self, fid, **dati):
        self.fascicolo.pagamenti = deepcopy(dati["pagamenti"])

    def aggiungi_documento(self, *args, **kwargs):
        self.docs.append((args, kwargs))
        return SimpleNamespace(id="DOC")


def _registra(g, **extra):
    return runtime.registra_avviso(g, "CASO", {"numero_avviso": NUMERO, "importo": "21,50", **extra}, "test")


def test_recupero_dal_pst_acquisisce_e_avvisa_del_riuso(monkeypatch):
    altro = _fascicolo("ALTRO", "Pratica vecchia", {"contributo_unificato": {"pagato": True, "iuv": NUMERO[1:]}})
    g = Gestore([altro])
    _registra(g, codice_fiscale_debitore="rssmra80a01h501u")
    chiamate = []

    def finto_recupero(numero, cf, *, verify):
        chiamate.append((numero, cf, verify))
        return _rt_xml(iuv=NUMERO[1:], importo="21.50")

    monkeypatch.setattr("web.services.pagopa_pst_receipts.recupera_rt", finto_recupero)
    esito = runtime.recupera_dal_pst(g, "CASO", NUMERO, "", "test", verify="ca.pem")
    assert esito["trovata"] and esito["avviso"]["documento_id"] == "DOC"
    assert chiamate == [(NUMERO, "RSSMRA80A01H501U", "ca.pem")]
    assert "Pratica vecchia" in runtime.avviso_riuso(g, "CASO", NUMERO)
    # Seconda volta: nessuna nuova chiamata, la ricevuta è già nel fascicolo.
    assert runtime.recupera_dal_pst(g, "CASO", NUMERO, "", "test", verify="ca.pem")["gia_acquisita"]
    assert len(chiamate) == 1


def test_recupero_senza_ricevuta_pubblicata_non_cambia_nulla(monkeypatch):
    g = Gestore()
    _registra(g, codice_fiscale_debitore="RSSMRA80A01H501U")
    prima = deepcopy(g.fascicolo.pagamenti)
    monkeypatch.setattr("web.services.pagopa_pst_receipts.recupera_rt", lambda *a, **k: None)
    assert runtime.recupera_dal_pst(g, "CASO", NUMERO, "", "test", verify="ca.pem") == {"trovata": False, "avviso": prima["pagopa_portale"]["avvisi"][0]}
    assert g.fascicolo.pagamenti == prima and not g.docs
    with pytest.raises(ValueError, match="Avviso non conservato"):
        runtime.recupera_dal_pst(g, "CASO", "330000000000000009", "", "test", verify="ca.pem")


def test_proposta_importo_solo_se_il_contributo_e_dovuto():
    dovuto = SimpleNamespace(pagamenti={"contributo_unificato": {"previsto": True, "status": "da_registrare", "importo": 237}})
    esente = SimpleNamespace(pagamenti={"contributo_unificato": {"previsto": False, "status": "non_previsto", "importo": None,
                                                                 "natura": "esenzione_contributo_unificato"}})
    pagato = SimpleNamespace(pagamenti={"contributo_unificato": {"pagato": True, "status": "pagato", "importo": 98}})
    assert dati_precompilazione(dovuto, None, [])["importoContributo"] == "237.00"
    assert dati_precompilazione(esente, None, [])["importoContributo"] == ""
    assert dati_precompilazione(pagato, None, [])["importoContributo"] == ""


def test_la_busta_non_blocca_con_esenzione():
    from pct.pagamenti_giustizia import riepilogo_rt_allegate

    esito = riepilogo_rt_allegate([("RT.xml", _rt_xml(iuv=NUMERO[1:], importo="21.50"))], importo_atteso=None, pagamento_richiesto=False)
    assert all(issue["level"] != "BLOCK" for issue in esito["issues"])


def test_rotta_recupera_dal_pst(tmp_path, monkeypatch):
    from pct.fascicoli import TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.helpers import get_fascicoli

    app = _app(tmp_path)
    with app.test_request_context("/"):
        fid = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE).id
    risposte = iter([None, _rt_xml(iuv=NUMERO[1:], importo="21.50")])
    monkeypatch.setattr("web.services.pagopa_pst_receipts.recupera_rt", lambda *a, **k: next(risposte))
    intestazioni = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    with app.test_client() as client:
        _login(client)
        base = f"/api/v1/ui/fascicoli/{fid}/pagopa"
        assert client.post(f"{base}/avvisi", json={"numero_avviso": NUMERO, "importo": "21,50",
                                                    "codice_fiscale_debitore": "RSSMRA80A01H501U"}, headers=intestazioni).get_json()["ok"]
        prima = client.post(f"{base}/recupera", json={"numero_avviso": NUMERO}, headers=intestazioni).get_json()
        assert prima["ok"] and prima["trovata"] is False and "Non significa" in prima["message"]
        dopo = client.post(f"{base}/recupera", json={"numero_avviso": NUMERO}, headers=intestazioni).get_json()
        assert dopo["ok"] and dopo["trovata"] and dopo["avviso"]["documento_id"]
        avvisi = client.get(f"{base}/avvisi", headers=intestazioni).get_json()["avvisi"]
        assert avvisi[0]["stato"] == "ricevuta_acquisita"
