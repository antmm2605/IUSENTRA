"""Riconvalida dei dati salvati (collaudo 10/11/2026, G-4 e G-13): repository finti, nessun dato reale."""

from __future__ import annotations

from types import SimpleNamespace

import web.services.riconvalida_economia_runtime as runtime


class _Fascicoli:
    def __init__(self, fascicolo):
        self.fascicolo, self.scritture = fascicolo, []

    def aggiorna(self, fid, **campi):
        self.scritture.append((fid, campi))
        self.fascicolo.pagamenti = campi["pagamenti"]


class _Fatturazione:
    def __init__(self, parcelle):
        self.parcelle, self.scritture = parcelle, []

    def per_fascicolo(self, _fid):
        return self.parcelle

    def aggiorna(self, pid, **campi):
        self.scritture.append((pid, campi))
        parcella = next(p for p in self.parcelle if p.id == pid)
        for chiave, valore in campi.items():
            setattr(parcella, chiave, valore)


def _parcella(pid, origine, creato_il, totale, data_emissione):
    return SimpleNamespace(id=pid, numero=pid, origine=origine, stato=SimpleNamespace(value="BOZZA"), creato_il=creato_il,
                           totale=totale, data_emissione=data_emissione, dati_personalizzati={})


def test_pagato_automatico_torna_da_incassare_e_la_decisione_umana_resta(monkeypatch):
    monkeypatch.setattr(runtime, "incasso_registrato", lambda _fid: False)
    fascicolo = SimpleNamespace(id="F1", pagamenti={
        "liquidazione_giudice": {"status": "pagato", "importo": 515.0, "data_pagamento": "2026-04-17", "updated_by": "Lex AI backfill",
                                 "history": [{"by": "Lex AI backfill", "toStatus": "pagato"}]},
        "parcella": {"status": "pagato", "importo": 600.0, "history": [{"by": "Mario Rossi", "toStatus": "pagato"}]}})
    repo = _Fascicoli(fascicolo)
    assert runtime.riconvalida_incassi(fascicolo, repository=repo) == ["liquidazione_giudice"]
    assert fascicolo.pagamenti["liquidazione_giudice"]["status"] == "da_incassare"
    assert fascicolo.pagamenti["parcella"]["status"] == "pagato"
    assert runtime.riconvalida_incassi(fascicolo, repository=repo) == [] and len(repo.scritture) == 1


def test_bozza_superata_dichiarata_voce_parcella_e_data_allineate():
    presidio = _parcella("2026/036", "presidio_economico_fascicolo_definito", "2026-07-27T10:00", 298.7, "2026-07-27")
    sentenza = _parcella("2026/062", "lex_ai_sentenza_tribunale", "2026-09-20T08:33", 617.94, "2026-04-17")
    fattura = _Fatturazione([presidio, sentenza])
    fascicolo = SimpleNamespace(id="F1", pagamenti={"parcella": {"status": "da_emettere", "importo": 751.45, "updated_by": "Lex AI backfill",
                                                                 "proforma_id": "2026/062"}})
    esito = runtime.riconvalida_proforme(fascicolo, repository=_Fascicoli(fascicolo), fatturazione=fattura)
    assert esito["superate"] == ["2026/036"] and presidio.dati_personalizzati["superata"]["da_numero"] == "2026/062"
    assert presidio.stato.value == "BOZZA"  # non si annulla: è una proposta per l'avvocato
    assert fascicolo.pagamenti["parcella"]["importo"] == 617.94
    assert sentenza.data_emissione == "2026-09-20" and sentenza.dati_personalizzati["document"]["data_sentenza"] == "2026-04-17"
    seconda = runtime.riconvalida_proforme(fascicolo, repository=_Fascicoli(fascicolo), fatturazione=fattura)
    assert seconda["superate"] == [] and not seconda["voce_parcella"] and "data_corretta" not in seconda
