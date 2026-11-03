"""CSV economico dei fascicoli (/export/fascicoli.csv) dal riepilogo consolidato.

Riverifica visiva 03/11/2026: il preset «CSV economico» di /fascicoli/esporta non rispondeva entro
3 minuti perché rileggeva i documenti di ognuno dei 336 fascicoli. Il CSV usa ora lo stesso
riepilogo consolidato della vista «Economica» (presidio economico pianificato), senza riletture.
"""
from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g

import web.blueprints.export_csv as modulo


def _voce(etichetta: str) -> dict[str, str]:
    return {"statusLabel": etichetta, "importoLabel": "€ 49,00"}


def test_csv_economico_usa_il_riepilogo_consolidato(monkeypatch):
    fascicolo = SimpleNamespace(id="F1", id_cliente="", numero_rg="1/2026", titolo="Prova c. Ente", tipo=None, stato=None,
                                tribunale="Tribunale di Roma", data_apertura="2026-01-10", data_chiusura="",
                                avvocato_referente="", descrizione="")
    chiamate = []

    def veloce(f, **_):
        chiamate.append(f.id)
        voci = {k: _voce("Da registrare") for k in ("contributo_unificato", "fondo_spese", "liquidazione_giudice", "parcella")}
        return {"items": voci, "totaleRegistratoLabel": "€ 0,00", "updatedAtLabel": "", "updatedBy": ""}

    monkeypatch.setattr(modulo, "payment_summary_for_fascicolo_fast", veloce)
    monkeypatch.setattr(modulo, "get_fascicoli", lambda: SimpleNamespace(tutti=lambda archiviati=True: [fascicolo]))
    monkeypatch.setattr(modulo, "get_clienti", lambda: SimpleNamespace(get=lambda _id: None))
    assert not hasattr(modulo, "payment_summary_for_fascicolo")

    app = Flask(__name__)
    app.register_blueprint(modulo.export_csv)

    @app.before_request
    def _utente():
        g.utente_corrente = SimpleNamespace(username="avvocato")

    risposta = app.test_client().get("/export/fascicoli.csv")
    testo = risposta.get_data(as_text=True)
    assert risposta.status_code == 200
    assert chiamate == ["F1"]
    assert "Contributo unificato - stato" in testo.splitlines()[0]
    assert "Da registrare" in testo
