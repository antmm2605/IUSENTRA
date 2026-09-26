"""Scadenze dai PDF: la richiesta non apre file, i PDF si leggono una volta in sfondo."""

from __future__ import annotations

import time
from pathlib import Path

from pct.fascicoli import TipoDocumento, TipoFascicolo
from tests.test_pdf_deadline_import import _pdf_with_deadline_and_link
from tests.test_react_shell import _app, _fascicoli_repository
from web.services import pdf_deadline_import, scadenze_pdf_lettura

HEADERS = {"X-API-Key": "react-test-key"}
URL = "/api/v1/ui/scadenziario/pdf-scadenze/anteprima"


def _attendi(client, fascicolo_id: str, secondi: float = 60.0) -> dict:
    fine = time.monotonic() + secondi
    while True:
        dati = client.get(URL, query_string={"fascicoloId": fascicolo_id}, headers=HEADERS).get_json()
        if not dati["summary"]["pending"] or time.monotonic() > fine:
            return dati
        time.sleep(0.2)


def test_anteprima_dal_registro_e_lettura_in_sfondo(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    fascicoli = _fascicoli_repository(app)
    fascicolo = fascicoli.nuovo("Prova PDF", TipoFascicolo.CIVILE, nome_cliente="Rossi Mario", numero_rg="12345", anno_rg=2026)
    fascicoli.aggiungi_documento(fascicolo.id, "ordinanza.pdf", TipoDocumento.ORDINANZA, _pdf_with_deadline_and_link())

    letture: list[str] = []
    originale = pdf_deadline_import._candidates_from_document

    def conta(**kwargs):
        letture.append(kwargs["documento"].id)
        return originale(**kwargs)

    monkeypatch.setattr(pdf_deadline_import, "_candidates_from_document", conta)
    with app.test_client() as client:
        prima = client.get(URL, query_string={"fascicoloId": fascicolo.id}, headers=HEADERS).get_json()
        assert prima["ok"] is True
        assert prima["summary"]["pending"] == 1 or prima["candidates"]

        dati = _attendi(client, fascicolo.id)
        assert dati["summary"]["pending"] == 0
        assert {c["due_date"] for c in dati["candidates"]} == {"2026-06-10", "2026-06-20"}
        assert len(letture) == 1

        # Una seconda anteprima non rilegge il PDF: le scadenze vengono dal registro.
        client.get(URL, query_string={"fascicoloId": fascicolo.id}, headers=HEADERS)
        assert len(letture) == 1

        ids = [c["id"] for c in dati["candidates"]]
        esito = client.post(
            "/api/v1/ui/scadenziario/pdf-scadenze/importa",
            json={"selectedIds": ids, "fascicoloId": fascicolo.id},
            headers=HEADERS,
        ).get_json()
        assert esito["ok"] is True and esito["created"] == 2
        assert len(letture) == 1

        dopo = client.get(URL, query_string={"fascicoloId": fascicolo.id}, headers=HEADERS).get_json()
        assert all(c["duplicate"] for c in dopo["candidates"])
    assert not scadenze_pdf_lettura._IN_CORSO
