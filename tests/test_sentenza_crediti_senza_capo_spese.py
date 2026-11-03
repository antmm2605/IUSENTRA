"""«Dalla sentenza»: solo i crediti letti nel capo spese (artt. 91 e 93 c.p.c.).

Riverifica visiva 03/11/2026: in un fascicolo di esecuzione tre note scritte (art. 127-ter c.p.c.)
lette come «incerte» generavano tre proposte «Spese distratte al difensore antistatario» senza
importo né passaggio del capo spese, e «Visualizza sentenza» apriva le note. Un credito senza
importo e senza testo del capo spese non è stato letto in una sentenza: resta nel presidio
economico ma non compare tra le proposte dalla sentenza. Nessun dato reale di clienti.
"""
from __future__ import annotations

import web.services.sentenza_economic_runtime as economia
import web.services.sentenza_proposte_runtime as runtime


def _eventi(monkeypatch, eventi, fonti):
    monkeypatch.setattr(economia, "build_sentenza_economic_payload", lambda fid: {"ok": True, "eventi": eventi, "audits": []})
    monkeypatch.setattr(runtime, "_parcelle_per_evento", lambda fid: {})
    monkeypatch.setattr(runtime, "_fonti_crediti", lambda *a, **k: fonti)


def test_credito_senza_importo_ne_capo_spese_non_e_una_proposta_dalla_sentenza(monkeypatch):
    eventi = [{"id": f"fee{i}", "event_type": "apri_credito_avvocato_antistatario", "status": "to_review", "amount": None,
               "source_id": f"audit{i}"} for i in range(3)]
    fonti = {f"audit{i}": {"href": f"/fascicoli/F1/documenti/N{i}/visualizza", "documento": f"Note scritte {i}.pdf",
                           "citazione": "", "numero": "", "anno": "", "data": ""} for i in range(3)}
    _eventi(monkeypatch, eventi, fonti)
    attivo, crediti = runtime.crediti_da_sentenza("F1", registro=object(), tenant="studio")
    assert attivo is True
    assert crediti == []


def test_credito_con_capo_spese_resta_anche_senza_importo(monkeypatch):
    citazione = "condanna il convenuto alla rifusione delle spese di lite, con distrazione in favore del difensore antistatario"
    eventi = [
        {"id": "fee1", "event_type": "apri_credito_avvocato_antistatario", "status": "to_review", "amount": None, "source_id": "a1"},
        {"id": "fee2", "event_type": "apri_credito_cliente", "status": "to_review", "amount": 1300.0, "source_id": "a2"},
    ]
    fonti = {"a1": {"href": "/x", "documento": "Sentenza.pdf", "citazione": citazione, "numero": "", "anno": "", "data": ""},
             "a2": {"href": "/y", "documento": "Sentenza 2.pdf", "citazione": "", "numero": "1", "anno": "2026", "data": ""}}
    _eventi(monkeypatch, eventi, fonti)
    _attivo, crediti = runtime.crediti_da_sentenza("F1", registro=object(), tenant="studio")
    assert [c["eventId"] for c in crediti] == ["fee1", "fee2"]
    assert crediti[0]["citazione"] == citazione
    assert crediti[1]["importoLabel"] == "€ 1.300,00"
